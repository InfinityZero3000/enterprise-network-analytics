"""
OpenOwnership Crawler (BODS — Beneficial Ownership Data Standard)
─────────────────────────────────────────────────────────────────
API: https://api.openownership.org
Docs: https://www.openownership.org/en/technology/
License: CC BY 4.0

OpenOwnership tổng hợp dữ liệu sở hữu hưởng lợi (beneficial ownership)
từ nhiều quốc gia, tuân theo chuẩn BODS (Beneficial Ownership Data Standard).

Dữ liệu bao gồm:
  • Beneficial owners (người sở hữu thực sự)
  • Tỷ lệ sở hữu, quyền voting
  • Chuỗi sở hữu qua nhiều tầng

Endpoints:
  GET /statements        — search statements (entity / person / ownership)
  GET /statements/{id}   — chi tiết một statement
  GET /submissions       — list submissions theo quốc gia
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


class OpenOwnershipCrawler(BaseCrawler):
    SOURCE_NAME = "openownership"

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=3.0)
        self._base = settings.openownership_base_url

    # ── API calls ─────────────────────────────────────────────────────────────

    async def _search_statements(
        self,
        client,
        statement_type: str = "ownershipOrControlStatement",
        page: int = 1,
        per_page: int = 200,
    ) -> dict:
        params = {
            "statementType": statement_type,
            "page": page,
            "perPage": per_page,
        }
        return await self._get(client, f"{self._base}/statements", params)

    async def _get_submissions(self, client) -> list[dict]:
        data = await self._get(client, f"{self._base}/submissions", {})
        return data if isinstance(data, list) else data.get("submissions", [])

    # ── Mappers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _map_entity_statement(stmt: dict) -> dict | None:
        entity = stmt.get("entity", {})
        name = entity.get("name", "")
        if not name:
            return None
        entity_type = entity.get("entityType", "")
        sid = stmt.get("statementID", stmt.get("id", ""))
        if entity_type in ("registeredEntity", "legalEntity"):
            identifiers = entity.get("identifiers", [])
            tax_code = next(
                (i.get("id") for i in identifiers if i.get("scheme") in ("VN-MST", "tax")),
                None,
            )
            return {
                "company_id": f"OO-{sid}",
                "name": name,
                "tax_code": tax_code,
                "company_type": "llc",
                "status": "active",
                "country": (entity.get("incorporatedInJurisdiction") or {}).get("code", "XX"),
                "address": None,
                "_source": "openownership",
                "_oo_id": sid,
            }
        if entity_type == "naturalPerson":
            return {
                "person_id": f"OO-P-{sid}",
                "full_name": name,
                "nationality": "",
                "is_pep": False,
                "is_sanctioned": False,
                "_source": "openownership",
                "_oo_id": sid,
            }
        return None

    @staticmethod
    def _map_ownership_statement(stmt: dict) -> dict | None:
        subject_id = (stmt.get("subject") or {}).get("describedByEntityStatement", "")
        interested_party = stmt.get("interestedParty", {})
        person_id = interested_party.get("describedByPersonStatement", "")
        entity_id = interested_party.get("describedByEntityStatement", "")
        owner_id = person_id or entity_id
        if not subject_id or not owner_id:
            return None

        # Extract ownership percent
        pct = None
        for interest in stmt.get("interests", []):
            share = interest.get("shareholdingDetails", {})
            exact = share.get("exact", {})
            if isinstance(exact, dict):
                pct = exact.get("value")
            elif isinstance(exact, (int, float)):
                pct = float(exact)
            if pct is not None:
                break

        prefix = "OO-P-" if person_id else "OO-"
        return {
            "source_id": f"{prefix}{owner_id}",
            "target_id": f"OO-{subject_id}",
            "source_type": "Person" if person_id else "Company",
            "target_type": "Company",
            "rel_type": "SHAREHOLDER",
            "ownership_percent": pct,
            "is_active": stmt.get("isComponent", True),
            "_source": "openownership",
            "_oo_stmt_id": stmt.get("statementID", ""),
        }

    # ── Main crawl ────────────────────────────────────────────────────────────

    async def crawl(
        self,
        max_pages: int = 20,
    ) -> CrawlResult:
        """
        Crawl BODS statements từ OpenOwnership API.

        Params
        ------
        max_pages : số trang tối đa cho mỗi loại statement
        """
        result = CrawlResult(source=self.SOURCE_NAME)
        seen_ids: set[str] = set()

        statement_types = [
            "entityStatement",
            "personStatement",
            "ownershipOrControlStatement",
        ]

        async with self._build_client() as client:
            for stype in statement_types:
                for page in range(1, max_pages + 1):
                    try:
                        data = await self._search_statements(client, stype, page=page)
                    except Exception as e:
                        result.errors.append(f"[OO] type={stype} page={page}: {e}")
                        break

                    statements = data if isinstance(data, list) else data.get("statements", data.get("data", []))
                    if not statements:
                        break

                    result.raw_count += len(statements)
                    for stmt in statements:
                        sid = stmt.get("statementID", stmt.get("id", ""))
                        if sid in seen_ids:
                            continue
                        seen_ids.add(sid)

                        stype_actual = stmt.get("statementType", stype)
                        if stype_actual in ("entityStatement",):
                            mapped = self._map_entity_statement(stmt)
                            if mapped:
                                if "company_id" in mapped:
                                    result.companies.append(mapped)
                                elif "person_id" in mapped:
                                    result.persons.append(mapped)
                        elif stype_actual == "ownershipOrControlStatement":
                            rel = self._map_ownership_statement(stmt)
                            if rel:
                                result.relationships.append(rel)

                    total = data.get("totalResults", data.get("total", 0)) if isinstance(data, dict) else 0
                    if page * 200 >= total and total > 0:
                        break

        if result.companies:
            result.minio_keys.append(
                self._upload_to_minio(result.companies, f"oo_companies_{len(result.companies)}.ndjson")
            )
        if result.persons:
            result.minio_keys.append(
                self._upload_to_minio(result.persons, f"oo_persons_{len(result.persons)}.ndjson")
            )
        if result.relationships:
            result.minio_keys.append(
                self._upload_to_minio(result.relationships, f"oo_relationships_{len(result.relationships)}.ndjson")
            )

        result.finished_at = datetime.now(timezone.utc)
        logger.info(f"[OpenOwnership] {result.summary()}")
        return result

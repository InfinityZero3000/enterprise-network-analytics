"""
GLEIF LEI Crawler
─────────────────
API: https://api.gleif.org/api/v1
Docs: https://www.gleif.org/en/lei-data/gleif-lei-look-up-api/full-lei-records-api-documentation
License: CC0 1.0 (hoàn toàn công khai)

LEI (Legal Entity Identifier) là mã định danh pháp nhân quốc tế ISO 17442.
Dữ liệu bao gồm:
  • Thông tin đăng ký pháp nhân (tên, địa chỉ, quốc gia, trạng thái)
  • Quan hệ trực tiếp (Direct Parent) và cuối cùng (Ultimate Parent)
  • Quan hệ con (children entities)

Endpoints:
  GET /lei-records            — search / list LEI records
  GET /lei-records/{lei}      — chi tiết một LEI
  GET /lei-records/{lei}/direct-parent     — công ty mẹ trực tiếp
  GET /lei-records/{lei}/ultimate-parent   — công ty mẹ cuối cùng
  GET /lei-records/{lei}/direct-children   — công ty con trực tiếp
"""
from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


class GleifCrawler(BaseCrawler):
    SOURCE_NAME = "gleif"

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=5.0)   # GLEIF không giới hạn chặt
        self._base = settings.gleif_base_url

    # ── API calls ─────────────────────────────────────────────────────────────

    async def _search_lei(
        self,
        client,
        name: str | None = None,
        country: str | None = None,
        page_number: int = 1,
        page_size: int = 200,
    ) -> dict:
        params: dict = {
            "page[number]": page_number,
            "page[size]": page_size,
        }
        if name:
            params["filter[entity.legalName]"] = name
        if country:
            params["filter[entity.legalAddress.country]"] = country
        return await self._get(client, f"{self._base}/lei-records", params)

    async def _get_lei_record(self, client, lei: str) -> dict:
        return await self._get(client, f"{self._base}/lei-records/{lei}", {})

    async def _get_relationships(
        self, client, lei: str, rel_type: str = "direct-parent"
    ) -> dict:
        """rel_type: direct-parent | ultimate-parent | direct-children"""
        url = f"{self._base}/lei-records/{lei}/{rel_type}"
        try:
            return await self._get(client, url, {})
        except Exception:
            return {}

    # ── Mappers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _map_lei_record(record: dict) -> dict:
        attr = record.get("attributes", {})
        entity = attr.get("entity", {})
        reg = attr.get("registration", {})
        addr = entity.get("legalAddress", {})
        addr_lines = addr.get("addressLines", [])
        first_line = addr_lines[0] if addr_lines else ""
        address_parts = [
            first_line,
            addr.get("city", ""),
            addr.get("region", ""),
            addr.get("postalCode", ""),
            addr.get("country", ""),
        ]
        address_str = ", ".join(part for part in address_parts if part)
        return {
            "company_id": f"GLEIF-{record['id']}",
            "name": entity.get("legalName", {}).get("name", ""),
            "tax_code": None,
            "company_type": _map_gleif_entity_type(entity.get("legalForm", {}).get("id", "")),
            "status": _map_gleif_status(entity.get("status", "")),
            "country": addr.get("country", "XX"),
            "address": address_str or None,
            "founded_date": None,
            "is_listed": False,
            "_source": "gleif",
            "_lei": record["id"],
            "_lei_status": reg.get("status"),
            "_lei_next_renewal": reg.get("nextRenewalDate"),
            "_gleif_entity_category": entity.get("category", ""),
        }

    # ── Main crawl ────────────────────────────────────────────────────────────

    async def crawl(
        self,
        countries: list[str] | None = None,
        lei_list: list[str] | None = None,
        max_pages: int = 10,
        fetch_relationships: bool = True,
    ) -> CrawlResult:
        """
        Crawl LEI records từ GLEIF.

        Params
        ------
        countries            : list ISO2 country codes (mặc định ["VN","SG","HK"])
        lei_list             : list LEI codes cụ thể cần lấy
        max_pages            : số trang tối đa mỗi country
        fetch_relationships  : có lấy parent/child relationships không
        """
        result = CrawlResult(source=self.SOURCE_NAME)
        countries = countries or ["VN", "SG", "HK", "MY", "TH", "ID"]
        seen: set[str] = set()

        async with self._build_client() as client:
            # 1. Duyệt theo country
            for country in countries:
                for page in range(1, max_pages + 1):
                    try:
                        data = await self._search_lei(client, country=country, page_number=page)
                    except Exception as e:
                        result.errors.append(f"[GLEIF] country={country} page={page}: {e}")
                        break

                    records = data.get("data", [])
                    if not records:
                        break
                    result.raw_count += len(records)

                    for rec in records:
                        lei = rec["id"]
                        if lei in seen:
                            continue
                        seen.add(lei)
                        company = self._map_lei_record(rec)
                        result.companies.append(company)

                        if fetch_relationships:
                            # Direct parent → ownership relationship
                            parent_data = await self._get_relationships(client, lei, "direct-parent")
                            parent_records = parent_data.get("data", [])
                            if isinstance(parent_records, dict):
                                parent_records = [parent_records]
                            for p_rec in (parent_records or []):
                                if not isinstance(p_rec, dict):
                                    continue
                                parent_lei = p_rec.get("id", "")
                                if not parent_lei or parent_lei == lei:
                                    continue
                                result.relationships.append({
                                        "source_id": f"GLEIF-{lei}",
                                        "target_id": f"GLEIF-{parent_lei}",
                                        "source_type": "Company",
                                        "target_type": "Company",
                                        "rel_type": "SUBSIDIARY",
                                        "ownership_percent": None,
                                        "is_active": True,
                                        "_source": "gleif",
                                        "_rel_type": "direct_parent",
                                    })

                    # Pagination
                    links = data.get("links", {})
                    if not links.get("next"):
                        break

            # 2. Lấy các LEI cụ thể (nếu có)
            if lei_list:
                for lei in lei_list:
                    if lei in seen:
                        continue
                    try:
                        data = await self._get_lei_record(client, lei)
                        rec = data.get("data", {})
                        if rec:
                            seen.add(lei)
                            result.companies.append(self._map_lei_record(rec))
                    except Exception as e:
                        result.errors.append(f"[GLEIF] lei={lei}: {e}")

        if result.companies:
            result.minio_keys.append(
                self._upload_to_minio(result.companies, f"lei_companies_{len(result.companies)}.ndjson")
            )
        if result.relationships:
            result.minio_keys.append(
                self._upload_to_minio(result.relationships, f"lei_relationships_{len(result.relationships)}.ndjson")
            )

        result.finished_at = datetime.now(timezone.utc)
        logger.info(f"[GLEIF] {result.summary()}")
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _map_gleif_status(raw: str) -> str:
    mapping = {"ACTIVE": "active", "INACTIVE": "inactive", "ANNULLED": "dissolved"}
    return mapping.get(raw.upper(), "inactive")


def _map_gleif_entity_type(form_id: str) -> str:
    form_id = form_id.upper()
    if "LLC" in form_id or "LIMITED" in form_id or "TNHH" in form_id:
        return "llc"
    if "JSC" in form_id or "JOINT" in form_id or "SHARE" in form_id:
        return "jsc"
    return "llc"

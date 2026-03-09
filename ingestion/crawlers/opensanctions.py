"""
OpenSanctions Crawler
─────────────────────
API: https://api.opensanctions.org
Docs: https://www.opensanctions.org/api/
License: CC BY NC 4.0 (research/non-commercial)

Dữ liệu bao gồm:
  • Danh sách trừng phạt OFAC, EU, UN
  • Politically Exposed Persons (PEP)
  • Wanted persons
  • Công ty bị trừng phạt

Endpoints:
  GET /entities/          — search entities
  GET /entities/{id}      — entity detail
  GET /datasets/          — list datasets
  POST /match/            — batch matching (fuzzy name matching)

Dataset IDs hữu ích:
  default          — tất cả nguồn
  us_ofac_sdn      — OFAC SDN (Mỹ)
  eu_fsf           — EU Financial Sanctions
  un_sc_sanctions  — UN Security Council
  peps             — Global PEPs database
  vn_mot_warnings  — Vietnam Ministry of Trade warnings
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from loguru import logger

from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


class OpenSanctionsCrawler(BaseCrawler):
    SOURCE_NAME = "opensanctions"

    # Datasets cần lấy
    DEFAULT_DATASETS = [
        "us_ofac_sdn",
        "eu_fsf",
        "un_sc_sanctions",
        "peps",
        "gb_hmt_sanctions",
    ]

    def __init__(self) -> None:
        # OpenSanctions free: 100 req/month; với API key: 10 req/s
        super().__init__(rate_limit_rps=2.0)
        self._api_key = settings.opensanctions_api_key
        self._base = settings.opensanctions_base_url

    def _headers(self) -> dict:
        h: dict = {}
        if self._api_key:
            h["Authorization"] = f"ApiKey {self._api_key}"
        return h

    # ── API calls ─────────────────────────────────────────────────────────────

    async def _search_entities(
        self,
        client,
        query: str,
        datasets: list[str],
        schema: str = "Thing",
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        params = {
            "q": query,
            "datasets": ",".join(datasets),
            "schema": schema,
            "limit": limit,
            "offset": offset,
        }
        return await self._get(client, f"{self._base}/entities/", params)

    async def _match_entities(self, client, candidates: list[dict]) -> dict:
        """POST /match/ — batch fuzzy matching."""
        import httpx
        url = f"{self._base}/match/default"
        async with self._limiter:
            resp = await client.post(url, json={"queries": {str(i): c for i, c in enumerate(candidates)}})
            resp.raise_for_status()
            return resp.json()

    async def _list_dataset_entities(
        self,
        client,
        dataset: str,
        entity_type: str = "Company",
        limit: int = 500,
        offset: int = 0,
    ) -> dict:
        params = {
            "dataset": dataset,
            "schema": entity_type,
            "limit": limit,
            "offset": offset,
        }
        return await self._get(client, f"{self._base}/entities/", params)

    # ── Mappers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_first(val, default=""):
        """Safely get first element from a list or return the value if it's a string."""
        if val is None:
            return default
        if isinstance(val, list):
            return val[0] if val else default
        return val

    @staticmethod
    def _map_entity(raw: dict) -> dict | None:
        schema = raw.get("schema", "")
        props = raw.get("properties", {})

        if schema in ("Company", "Organization", "LegalEntity"):
            return {
                "company_id": f"SANS-{raw['id']}",
                "name": OpenSanctionsCrawler._safe_first(props.get("name")),
                "tax_code": OpenSanctionsCrawler._safe_first(props.get("registrationNumber"), None),
                "company_type": "llc",
                "status": "active",
                "country": OpenSanctionsCrawler._safe_first(props.get("country"), "XX").upper(),
                "address": OpenSanctionsCrawler._safe_first(props.get("address"), None),
                "is_sanctioned": True,
                "_source": "opensanctions",
                "_sans_id": raw["id"],
                "_sans_datasets": raw.get("datasets", []),
                "_sans_caption": raw.get("caption"),
            }
        if schema in ("Person",):
            return {
                "person_id": f"SANS-{raw['id']}",
                "full_name": OpenSanctionsCrawler._safe_first(props.get("name")),
                "nationality": OpenSanctionsCrawler._safe_first(props.get("nationality")),
                "is_pep": "peps" in raw.get("datasets", []),
                "is_sanctioned": True,
                "_source": "opensanctions",
                "_sans_id": raw["id"],
                "_sans_datasets": raw.get("datasets", []),
            }
        return None

    # ── Main crawl ────────────────────────────────────────────────────────────

    async def crawl(
        self,
        queries: list[str] | None = None,
        datasets: list[str] | None = None,
        max_per_dataset: int = 1000,
    ) -> CrawlResult:
        """
        Crawl sanctions & PEP data từ OpenSanctions.

        Params
        ------
        queries         : list tên cần tìm kiếm (optional)
        datasets        : list dataset IDs, mặc định DEFAULT_DATASETS
        max_per_dataset : số entity tối đa mỗi dataset
        """
        result = CrawlResult(source=self.SOURCE_NAME)
        datasets = datasets or self.DEFAULT_DATASETS
        seen: set[str] = set()

        async with self._build_client(self._headers()) as client:
            # 1. Search by query (nếu có)
            if queries:
                for q in queries:
                    offset = 0
                    while offset < max_per_dataset:
                        try:
                            data = await self._search_entities(
                                client, q, datasets, limit=100, offset=offset
                            )
                        except Exception as e:
                            result.errors.append(f"[SANS] search '{q}': {e}")
                            break

                        entities = data.get("results", [])
                        if not entities:
                            break
                        result.raw_count += len(entities)
                        for ent in entities:
                            eid = ent.get("id", "")
                            if eid in seen:
                                continue
                            seen.add(eid)
                            mapped = self._map_entity(ent)
                            if mapped:
                                if "company_id" in mapped:
                                    result.companies.append(mapped)
                                elif "person_id" in mapped:
                                    result.persons.append(mapped)
                        offset += 100
                        if offset >= data.get("total", 0):
                            break

            else:
                # 2. List all entities từng dataset
                for ds in datasets:
                    for entity_type in ["Company", "Person"]:
                        offset = 0
                        while offset < max_per_dataset:
                            try:
                                data = await self._list_dataset_entities(
                                    client, ds, entity_type, limit=500, offset=offset
                                )
                            except Exception as e:
                                result.errors.append(f"[SANS] dataset={ds} type={entity_type} off={offset}: {e}")
                                break

                            entities = data.get("results", [])
                            if not entities:
                                break
                            result.raw_count += len(entities)
                            for ent in entities:
                                eid = ent.get("id", "")
                                if eid in seen:
                                    continue
                                seen.add(eid)
                                mapped = self._map_entity(ent)
                                if mapped:
                                    if "company_id" in mapped:
                                        result.companies.append(mapped)
                                    elif "person_id" in mapped:
                                        result.persons.append(mapped)
                            offset += 500
                            if offset >= data.get("total", 0):
                                break

        if result.companies:
            result.minio_keys.append(
                self._upload_to_minio(result.companies, f"sanctioned_companies_{len(result.companies)}.ndjson")
            )
        if result.persons:
            result.minio_keys.append(
                self._upload_to_minio(result.persons, f"sanctioned_persons_{len(result.persons)}.ndjson")
            )

        result.finished_at = datetime.now(timezone.utc)
        logger.info(f"[OpenSanctions] {result.summary()}")
        return result

    async def match_names(self, names: list[str]) -> dict[str, list[dict]]:
        """
        Kiểm tra danh sách tên có bị trừng phạt / là PEP không.
        Trả về {name: [matched_entities]}.
        """
        candidates = [{"schema": "Thing", "properties": {"name": [n]}} for n in names]
        async with self._build_client(self._headers()) as client:
            result = await self._match_entities(client, candidates)
        output: dict[str, list[dict]] = {}
        for k, v in result.get("responses", {}).items():
            try:
                idx = int(k)
                if 0 <= idx < len(names):
                    output[names[idx]] = list(v.get("results", []))
            except (ValueError, IndexError):
                logger.warning(f"[SANS] match_names: unexpected response key {k}")
        return output

    def run_match(self, names: list[str]) -> dict[str, list[dict]]:
        return asyncio.run(self.match_names(names))

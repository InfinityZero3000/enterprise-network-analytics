"""
OpenCorporates Crawler
─────────────────────
API: https://api.opencorporates.com/v0.4
Docs: https://api.opencorporates.com/documentation/API-Reference
License: CC BY 4.0

Endpoints sử dụng:
  GET /companies/search          — tìm kiếm công ty
  GET /companies/{jur}/{num}     — chi tiết công ty
  GET /officers/search           — tìm kiếm người đại diện/cổ đông
  GET /companies/{jur}/{num}/officers — danh sách officers của công ty

Jurisdictions hữu ích:
  vn   — Việt Nam
  sg   — Singapore
  hk   — Hong Kong
  us_* — Mỹ (mỗi bang)
  gb   — Anh

Rate limit:
  Free:     ~500 req/day, 1 req/s
  Premium:  10 req/s
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import date
from typing import Any

from loguru import logger

from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


class OpenCorporatesCrawler(BaseCrawler):
    SOURCE_NAME = "opencorporates"

    # Map OC jurisdiction code → country ISO2
    JURISDICTION_COUNTRY: dict[str, str] = {
        "vn": "VN", "sg": "SG", "hk": "HK", "gb": "GB",
        "us_de": "US", "us_ca": "US", "us_ny": "US",
        "cn": "CN", "jp": "JP", "kr": "KR", "th": "TH",
        "my": "MY", "id": "ID", "ph": "PH", "au": "AU",
    }

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=1.0)
        self._token = settings.opencorporates_api_token
        self._base = settings.opencorporates_base_url

    def _auth_params(self) -> dict:
        return {"api_token": self._token} if self._token else {}

    # ── Raw mappers ───────────────────────────────────────────────────────────

    @staticmethod
    def _map_company(raw: dict, jurisdiction: str) -> dict:
        """Map OC company dict → CompanyModel-compatible dict."""
        cid = f"OC-{raw.get('company_number', '')}-{jurisdiction}"
        country = OpenCorporatesCrawler.JURISDICTION_COUNTRY.get(jurisdiction, "XX")
        return {
            "company_id": cid,
            "name": raw.get("name", ""),
            "tax_code": raw.get("company_number", ""),
            "company_type": _normalise_company_type(raw.get("company_type", "")),
            "status": _normalise_status(raw.get("current_status", "")),
            "founded_date": raw.get("incorporation_date"),
            "address": _extract_address(raw.get("registered_address", {})),
            "country": country,
            "industry_code": None,
            "industry_name": raw.get("industry_codes", [{}])[0].get("description") if raw.get("industry_codes") else None,
            "is_listed": False,
            "charter_capital": None,
            "_source": "opencorporates",
            "_oc_number": raw.get("company_number"),
            "_oc_jurisdiction": jurisdiction,
            "_oc_url": raw.get("opencorporates_url"),
        }

    @staticmethod
    def _map_officer(raw: dict, company_id: str) -> tuple[dict | None, dict | None]:
        """Map OC officer → (PersonModel dict, RelationshipModel dict)."""
        name = raw.get("name", "").strip()
        if not name:
            return None, None
        person_id = "P-OC-" + hashlib.md5(name.lower().encode()).hexdigest()[:12]
        person = {
            "person_id": person_id,
            "full_name": name,
            "nationality": raw.get("nationality", ""),
            "is_pep": False,
            "is_sanctioned": False,
            "_source": "opencorporates",
        }
        position = raw.get("position", "").upper()
        rel_type = _officer_position_to_rel(position)
        rel = {
            "source_id": person_id,
            "target_id": company_id,
            "source_type": "Person",
            "target_type": "Company",
            "rel_type": rel_type,
            "ownership_percent": None,
            "start_date": raw.get("start_date"),
            "end_date": raw.get("end_date"),
            "is_active": raw.get("end_date") is None,
            "_source": "opencorporates",
        }
        return person, rel

    # ── API calls ─────────────────────────────────────────────────────────────

    async def _search_companies(
        self,
        client,
        query: str,
        jurisdiction: str = "vn",
        page: int = 1,
        per_page: int = 100,
    ) -> dict:
        params = {
            "q": query,
            "jurisdiction_code": jurisdiction,
            "per_page": per_page,
            "page": page,
            "sparse": "false",
            **self._auth_params(),
        }
        return await self._get(client, f"{self._base}/companies/search", params)

    async def _get_company_detail(
        self, client, jurisdiction: str, company_number: str
    ) -> dict:
        url = f"{self._base}/companies/{jurisdiction}/{company_number}"
        return await self._get(client, url, self._auth_params())

    async def _get_company_officers(
        self, client, jurisdiction: str, company_number: str
    ) -> list[dict]:
        url = f"{self._base}/companies/{jurisdiction}/{company_number}/officers"
        try:
            data = await self._get(client, url, self._auth_params())
            return data.get("results", {}).get("officers", [])
        except Exception as e:
            logger.warning(f"Could not fetch officers for {jurisdiction}/{company_number}: {e}")
            return []

    async def _search_officers(
        self, client, query: str, jurisdiction: str = "vn", page: int = 1
    ) -> dict:
        params = {
            "q": query,
            "jurisdiction_code": jurisdiction,
            "page": page,
            **self._auth_params(),
        }
        return await self._get(client, f"{self._base}/officers/search", params)

    # ── Main crawl ────────────────────────────────────────────────────────────

    async def crawl(
        self,
        queries: list[str] | None = None,
        jurisdictions: list[str] | None = None,
        max_pages: int = 5,
        fetch_officers: bool = True,
    ) -> CrawlResult:
        """
        Crawl companies (và officers tuỳ chọn) từ OpenCorporates.

        Params
        ------
        queries       : list từ khoá tìm kiếm, mặc định ["*"] (tất cả)
        jurisdictions : list mã jurisdiction, mặc định ["vn", "sg", "hk"]
        max_pages     : số trang tối đa mỗi query/jurisdiction
        fetch_officers: có lấy danh sách officers không
        """
        result = CrawlResult(source=self.SOURCE_NAME)
        queries = queries or ["*"]
        jurisdictions = jurisdictions or ["vn", "sg", "hk"]
        seen_companies: set[str] = set()

        async with self._build_client() as client:
            for jur in jurisdictions:
                for q in queries:
                    for page in range(1, max_pages + 1):
                        try:
                            data = await self._search_companies(client, q, jur, page)
                        except Exception as e:
                            msg = f"[OC] search {q}/{jur}/p{page}: {e}"
                            logger.error(msg)
                            result.errors.append(msg)
                            break

                        companies_raw = (
                            data.get("results", {})
                            .get("companies", [])
                        )
                        if not companies_raw:
                            break

                        result.raw_count += len(companies_raw)
                        for item in companies_raw:
                            c_raw = item.get("company", item)
                            cnum = c_raw.get("company_number", "")
                            ckey = f"{jur}:{cnum}"
                            if ckey in seen_companies:
                                continue
                            seen_companies.add(ckey)

                            company = self._map_company(c_raw, jur)
                            result.companies.append(company)

                            if fetch_officers and cnum:
                                officers = await self._get_company_officers(
                                    client, jur, cnum
                                )
                                for off_item in officers:
                                    off_raw = off_item.get("officer", off_item)
                                    person, rel = self._map_officer(
                                        off_raw, company["company_id"]
                                    )
                                    if person:
                                        result.persons.append(person)
                                    if rel:
                                        result.relationships.append(rel)

                        # Check if last page
                        total_pages = (
                            data.get("results", {})
                            .get("total_pages", 1)
                        )
                        if page >= total_pages:
                            break

        # Upload to MinIO
        if result.companies:
            key = self._upload_to_minio(
                result.companies,
                f"companies_{len(result.companies)}.ndjson",
            )
            result.minio_keys.append(key)
        if result.persons:
            key = self._upload_to_minio(
                result.persons,
                f"persons_{len(result.persons)}.ndjson",
            )
            result.minio_keys.append(key)
        if result.relationships:
            key = self._upload_to_minio(
                result.relationships,
                f"relationships_{len(result.relationships)}.ndjson",
            )
            result.minio_keys.append(key)

        from datetime import timezone
        from datetime import datetime as dt
        result.finished_at = dt.now(timezone.utc)
        logger.info(f"[OpenCorporates] {result.summary()}")
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_company_type(raw: str) -> str:
    raw = raw.lower()
    if "limited liability" in raw or "llc" in raw or "tnhh" in raw:
        return "llc"
    if "joint stock" in raw or "jsc" in raw or "co phan" in raw:
        return "jsc"
    if "sole" in raw or "tu nhan" in raw:
        return "sole_proprietor"
    if "partnership" in raw or "hop danh" in raw:
        return "partnership"
    return "llc"


def _normalise_status(raw: str) -> str:
    raw = raw.lower()
    if "active" in raw or "dang hoat dong" in raw:
        return "active"
    if "dissolved" in raw or "da giai the" in raw:
        return "dissolved"
    if "suspend" in raw or "tam ngung" in raw:
        return "suspended"
    return "inactive"


def _extract_address(addr: Any) -> str | None:
    if isinstance(addr, str):
        return addr
    if isinstance(addr, dict):
        parts = [
            addr.get("street_address"),
            addr.get("locality"),
            addr.get("region"),
            addr.get("postal_code"),
            addr.get("country"),
        ]
        return ", ".join(p for p in parts if p)
    return None


def _officer_position_to_rel(position: str) -> str:
    if "director" in position or "bo truong" in position:
        return "BOARD_MEMBER"
    if "secretary" in position:
        return "BOARD_MEMBER"
    if "shareholder" in position or "co dong" in position:
        return "SHAREHOLDER"
    return "LEGAL_REPRESENTATIVE"

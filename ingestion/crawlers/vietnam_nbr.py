"""
Vietnam National Business Registry (DKKD) Crawler
───────────────────────────────────────────────────
Nguồn: https://dangkykinhdoanh.gov.vn
       https://dichvucong.gov.vn (Cổng Dịch vụ công quốc gia)
       https://masothue.com (MST lookup, public)
       https://thongtin.doanhnghiep.vn (public company info)

Dữ liệu công khai bao gồm:
  • Thông tin đăng ký doanh nghiệp (tên, mã số thuế, địa chỉ, ngành nghề)
  • Danh sách người đại diện pháp luật
  • Vốn điều lệ, ngày thành lập
  • Trạng thái hoạt động

Lưu ý:
  - DKKD không có REST API công khai chính thức
  - Sử dụng kết hợp:
    a) masothue.com public API (không cần auth)
    b) HTML scraping với playwright cho trang DKKD
    c) dichvucong.gov.vn API (nếu có)

Cần tôn trọng ToS — chỉ thu thập dữ liệu công khai với rate thấp.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


class VietnamNBRCrawler(BaseCrawler):
    SOURCE_NAME = "vietnam_nbr"

    # masothue.com không cần auth — tra cứu theo MST
    MASOTHUE_API = "https://masothue.com/Services/Search"
    MASOTHUE_DETAIL = "https://masothue.com/{mst}"

    # thongtin.doanhnghiep.vn
    DOANHNGHIEP_API = "https://thongtin.doanhnghiep.vn/api/publiccp/company/search"

    # DKKD API của Bộ KH&ĐT (unofficial, dựa trên reverse engineering)
    DKKD_SEARCH = "https://dangkykinhdoanh.gov.vn/vn/api/enterprise/search"
    DKKD_DETAIL = "https://dangkykinhdoanh.gov.vn/vn/api/enterprise/{mst}"

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=1.0)   # rất thận trọng với gov sites

    # ── masothue.com ──────────────────────────────────────────────────────────

    async def _search_masothue(
        self, client: httpx.AsyncClient, keyword: str, page: int = 1
    ) -> dict:
        """Tìm kiếm công ty qua masothue.com public endpoints."""
        headers = {
            "Accept": "application/json, text/javascript, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://masothue.com/",
        }
        params = {"term": keyword, "page": page}
        async with self._semaphore:
            async with self._limiter:
                resp = await client.get(self.MASOTHUE_API, params=params, headers=headers)
                if resp.status_code != 200:
                    return {}
                return resp.json()

    async def _get_masothue_detail(
        self, client: httpx.AsyncClient, mst: str
    ) -> dict:
        """Lấy HTML chi tiết doanh nghiệp từ masothue.com và parse."""
        url = self.MASOTHUE_DETAIL.format(mst=mst.replace("-", "").replace(" ", ""))
        async with self._semaphore:
            async with self._limiter:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        return {}
                    return _parse_masothue_html(resp.text, mst)
                except Exception as e:
                    logger.debug(f"[VN-NBR] masothue detail {mst}: {e}")
                    return {}

    # ── thongtin.doanhnghiep.vn ───────────────────────────────────────────────

    async def _search_doanhnghiep_vn(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        page: int = 1,
        size: int = 50,
    ) -> list[dict]:
        params = {
            "keyword": keyword,
            "page": page - 1,
            "size": size,
        }
        try:
            # SSL cert có hostname mismatch — dùng client riêng với verify=False
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                verify=False,
            ) as no_ssl_client:
                async with self._semaphore:
                    async with self._limiter:
                        resp = await no_ssl_client.get(self.DOANHNGHIEP_API, params=params)
                        resp.raise_for_status()
                        data = resp.json()
            return data.get("content", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.debug(f"[VN-NBR] doanhnghiep.vn '{keyword}' p{page}: {e}")
            return []

    # ── Mappers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _map_masothue(raw: dict) -> dict:
        mst = raw.get("mst") or raw.get("tax_code") or raw.get("id", "")
        return {
            "company_id": f"VN-{mst}",
            "name": raw.get("name") or raw.get("ten_doanh_nghiep", ""),
            "tax_code": mst,
            "company_type": _vn_map_company_type(raw.get("loai_hinh", "")),
            "status": _vn_map_status(raw.get("tinh_trang", raw.get("trang_thai", ""))),
            "industry_code": raw.get("ma_nganh", raw.get("industry_code")),
            "industry_name": raw.get("nganh_nghe", raw.get("nganh_nghe_chinh", "")),
            "founded_date": _parse_vn_date(raw.get("ngay_cap_phep", raw.get("ngay_thanh_lap", ""))),
            "charter_capital": _parse_capital(raw.get("von_dieu_le", raw.get("charter_capital"))),
            "address": raw.get("dia_chi", raw.get("address", "")),
            "province": raw.get("tinh_thanh", raw.get("province", "")),
            "country": "VN",
            "_source": "vietnam_nbr",
            "_mst": mst,
        }

    @staticmethod
    def _map_doanhnghiep_vn(raw: dict) -> dict:
        mst = raw.get("taxCode") or raw.get("mst", "")
        return {
            "company_id": f"VN-{mst}",
            "name": raw.get("companyName") or raw.get("name", ""),
            "tax_code": mst,
            "company_type": _vn_map_company_type(raw.get("companyType", "")),
            "status": _vn_map_status(raw.get("status", raw.get("companyStatus", ""))),
            "industry_code": raw.get("mainIndustryCode"),
            "industry_name": raw.get("mainIndustryName"),
            "founded_date": raw.get("foundedDate") or raw.get("registrationDate"),
            "charter_capital": raw.get("charterCapital"),
            "address": raw.get("address"),
            "province": raw.get("province") or raw.get("city"),
            "country": "VN",
            "_source": "vietnam_nbr",
            "_mst": mst,
        }

    @staticmethod
    def _map_legal_representative(company_id: str, rep: dict) -> tuple[dict, dict]:
        name = rep.get("name") or rep.get("nguoi_dai_dien", "")
        person_id = "P-VN-" + hashlib.md5(name.lower().encode()).hexdigest()[:12]
        person = {
            "person_id": person_id,
            "full_name": name,
            "nationality": "VN",
            "is_pep": False,
            "is_sanctioned": False,
            "_source": "vietnam_nbr",
        }
        rel = {
            "source_id": person_id,
            "target_id": company_id,
            "source_type": "Person",
            "target_type": "Company",
            "rel_type": "LEGAL_REPRESENTATIVE",
            "ownership_percent": None,
            "is_active": True,
            "_source": "vietnam_nbr",
        }
        return person, rel

    # ── Main crawl ────────────────────────────────────────────────────────────

    async def crawl(
        self,
        keywords: list[str] | None = None,
        mst_list: list[str] | None = None,
        max_pages: int = 5,
        use_doanhnghiep_vn: bool = True,
    ) -> CrawlResult:
        """
        Crawl dữ liệu doanh nghiệp Việt Nam.

        Params
        ------
        keywords            : danh sách từ khoá tìm kiếm
        mst_list            : danh sách MST (mã số thuế) cụ thể
        max_pages           : số trang tối đa
        use_doanhnghiep_vn  : sử dụng thongtin.doanhnghiep.vn song song
        """
        result = CrawlResult(source=self.SOURCE_NAME)
        keywords = keywords or ["cong ty", "corporation", "group"]
        seen: set[str] = set()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        }

        async with self._build_client(headers) as client:
            # 1. Tìm qua masothue.com
            for kw in keywords:
                for page in range(1, max_pages + 1):
                    try:
                        data = await self._search_masothue(client, kw, page)
                    except Exception as e:
                        result.errors.append(f"[VN-NBR] masothue '{kw}' p{page}: {e}")
                        break

                    items = data.get("suggestions") if isinstance(data, dict) else []
                    if not items:
                        items = data if isinstance(data, list) else []
                    if not items:
                        break

                    result.raw_count += len(items)
                    for item in items:
                        mst = item.get("data") or item.get("mst") or item.get("value", "")
                        mst = mst.strip().replace("-", "")
                        if not mst or mst in seen:
                            continue
                        seen.add(mst)
                        # Get detail
                        detail = await self._get_masothue_detail(client, mst)
                        if detail:
                            company = self._map_masothue(detail)
                            result.companies.append(company)
                            # Representatives
                            for rep in detail.get("representatives", []):
                                p, r = self._map_legal_representative(company["company_id"], rep)
                                result.persons.append(p)
                                result.relationships.append(r)
                        else:
                            result.companies.append(self._map_masothue({
                                "mst": mst,
                                "name": item.get("value", item.get("label", "")),
                            }))

            # 2. Tìm qua thongtin.doanhnghiep.vn
            if use_doanhnghiep_vn:
                for kw in keywords:
                    for page in range(1, max_pages + 1):
                        try:
                            items = await self._search_doanhnghiep_vn(client, kw, page)
                        except Exception as e:
                            result.errors.append(f"[VN-NBR] doanhnghiep.vn '{kw}' p{page}: {e}")
                            break

                        if not items:
                            break
                        result.raw_count += len(items)
                        for item in items:
                            mst = (item.get("taxCode") or item.get("mst", "")).strip()
                            if not mst or mst in seen:
                                continue
                            seen.add(mst)
                            result.companies.append(self._map_doanhnghiep_vn(item))

            # 3. Lấy MST cụ thể
            if mst_list:
                for mst in mst_list:
                    if mst in seen:
                        continue
                    seen.add(mst)
                    detail = await self._get_masothue_detail(client, mst)
                    if detail:
                        company = self._map_masothue(detail)
                        result.companies.append(company)

        if result.companies:
            result.minio_keys.append(
                self._upload_to_minio(result.companies, f"vn_companies_{len(result.companies)}.ndjson")
            )
        if result.persons:
            result.minio_keys.append(
                self._upload_to_minio(result.persons, f"vn_persons_{len(result.persons)}.ndjson")
            )
        if result.relationships:
            result.minio_keys.append(
                self._upload_to_minio(result.relationships, f"vn_relationships_{len(result.relationships)}.ndjson")
            )

        result.finished_at = datetime.now(timezone.utc)
        logger.info(f"[VietnamNBR] {result.summary()}")
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_masothue_html(html: str, mst: str) -> dict:
    """Parse HTML của masothue.com để lấy thông tin chi tiết."""
    try:
        soup = BeautifulSoup(html, "lxml")
        data: dict = {"mst": mst}

        # Tên doanh nghiệp
        h1 = soup.find("h1", class_=re.compile("company|name|title", re.I))
        if h1:
            data["name"] = h1.get_text(strip=True)

        # Table thông tin
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                if "mã số thuế" in label or "tax code" in label:
                    data["mst"] = value
                elif "tên" in label and "name" in label:
                    data["name"] = value
                elif "địa chỉ" in label or "address" in label:
                    data["dia_chi"] = value
                elif "loại hình" in label or "company type" in label:
                    data["loai_hinh"] = value
                elif "tình trạng" in label or "status" in label:
                    data["tinh_trang"] = value
                elif "ngành nghề" in label or "industry" in label:
                    data["nganh_nghe"] = value
                elif "vốn" in label:
                    data["von_dieu_le"] = value
                elif "ngày" in label and ("thành lập" in label or "cấp" in label):
                    data["ngay_thanh_lap"] = value
                elif "người đại diện" in label or "representative" in label:
                    data.setdefault("representatives", []).append({"name": value})
                elif "tỉnh/thành" in label or "province" in label:
                    data["tinh_thanh"] = value
        return data
    except Exception as e:
        logger.debug(f"[VN-NBR] HTML parse error for {mst}: {e}")
        return {"mst": mst}


def _vn_map_company_type(raw: str) -> str:
    raw = raw.lower()
    if "tnhh" in raw or "limited" in raw or "llc" in raw:
        return "llc"
    if "cổ phần" in raw or "co phan" in raw or "jsc" in raw:
        return "jsc"
    if "nhà nước" in raw or "state" in raw:
        return "soe"
    if "đầu tư nước ngoài" in raw or "fdi" in raw or "foreign" in raw:
        return "fdi"
    if "hợp danh" in raw or "partnership" in raw:
        return "partnership"
    if "tư nhân" in raw or "sole" in raw:
        return "sole_proprietor"
    return "llc"


def _vn_map_status(raw: str) -> str:
    raw = raw.lower()
    if "đang hoạt động" in raw or "active" in raw or "hoạt động" in raw:
        return "active"
    if "giải thể" in raw or "dissolved" in raw:
        return "dissolved"
    if "tạm ngưng" in raw or "suspended" in raw or "ngừng" in raw:
        return "suspended"
    return "inactive"


def _parse_vn_date(raw: str | None) -> str | None:
    if not raw:
        return None
    # Try dd/mm/yyyy
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw.strip())
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    # Try yyyy-mm-dd
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw.strip())
    if m:
        return raw.strip()
    return None


def _parse_capital(raw: str | float | int | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    # "10.000.000.000 VNĐ" → 10000000000.0
    cleaned = re.sub(r"[^\d,.]", "", str(raw)).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None

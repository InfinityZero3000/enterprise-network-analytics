"""
Crawl4AI Company Pages Crawler

Collects public company data from aggregate pages and company profile pages,
then maps into the project's normalized company schema.

Primary target (public pages):
  - https://companiesmarketcap.com/page/<n>/
  - company profile pages discovered from ranking tables
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger

from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
except Exception:  # pragma: no cover - runtime environment may not have Playwright deps installed
    AsyncWebCrawler = None
    BrowserConfig = None
    CacheMode = None
    CrawlerRunConfig = None


class Crawl4AICompanyPagesCrawler(BaseCrawler):
    SOURCE_NAME = "crawl4ai_company_pages"
    BASE_URL = "https://companiesmarketcap.com"

    def __init__(self) -> None:
        # Conservative crawl rate to avoid stressing target websites.
        super().__init__(rate_limit_rps=0.8, concurrency=2, timeout=45)

    @staticmethod
    def _clean_country(raw: str) -> str:
        text = (raw or "").strip()
        if not text:
            return "XX"
        text = re.sub(r"[^\w\s\-()]+", "", text).strip()
        return text or "XX"

    @staticmethod
    def _extract_html(crawl_result: Any) -> str:
        html = getattr(crawl_result, "cleaned_html", "") or getattr(crawl_result, "html", "")
        return html or ""

    @classmethod
    def _parse_ranking_rows(cls, html: str, base_url: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("table tbody tr")
        records: list[dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            link = row.select_one("a[href*='/marketcap/']")
            if not link:
                continue

            href = (link.get("href") or "").strip()
            if not href:
                continue

            profile_url = urljoin(base_url, href)
            name = link.get_text(" ", strip=True)
            if not name:
                continue

            tds = row.find_all("td")
            market_cap = tds[3].get_text(" ", strip=True) if len(tds) >= 4 else None
            country = tds[-1].get_text(" ", strip=True) if len(tds) >= 1 else ""

            records.append(
                {
                    "rank": idx,
                    "name": name,
                    "profile_url": profile_url,
                    "country": cls._clean_country(country),
                    "market_cap": market_cap,
                }
            )

        return records

    @staticmethod
    def _parse_profile_fields(html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        title_text = ""
        h1 = soup.select_one("h1")
        if h1:
            title_text = h1.get_text(" ", strip=True)

        ticker = None
        ticker_match = re.search(r"\(([A-Z0-9.\-]+)\)", title_text)
        if ticker_match:
            ticker = ticker_match.group(1)

        return {
            "title": title_text,
            "ticker": ticker,
        }

    @staticmethod
    def _company_id(profile_url: str, ticker: str | None = None) -> str:
        if ticker:
            return f"CMC-{ticker.upper()}"
        parsed = urlparse(profile_url)
        slug = parsed.path.strip("/").split("/")[0] if parsed.path else "unknown"
        slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", slug).upper()
        return f"CMC-{slug or 'UNKNOWN'}"

    @classmethod
    def _to_company(cls, row: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        ticker = profile.get("ticker")
        return {
            "company_id": cls._company_id(str(row.get("profile_url", "")), ticker=ticker),
            "name": str(row.get("name") or profile.get("title") or "").strip(),
            "tax_code": None,
            "company_type": "public",
            "status": "active",
            "country": cls._clean_country(str(row.get("country") or "XX")),
            "address": None,
            "founded_date": None,
            "is_listed": True,
            "_source": cls.SOURCE_NAME,
            "_url": row.get("profile_url"),
            "_ticker": ticker,
            "_market_cap": row.get("market_cap"),
            "_rank": row.get("rank"),
        }

    @staticmethod
    def _write_local_snapshot(companies: list[dict[str, Any]]) -> str:
        output_dir = Path("dataset/crawl4ai")
        output_dir.mkdir(parents=True, exist_ok=True)

        ndjson_path = output_dir / "latest_companies.ndjson"
        with ndjson_path.open("w", encoding="utf-8") as f:
            for row in companies:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        # Human-friendly snapshot for quick inspection and screenshots.
        pretty_json_path = output_dir / "latest_companies.pretty.json"
        pretty_json_path.write_text(
            json.dumps(companies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary_path = output_dir / "latest_summary.json"
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_companies": len(companies),
            "countries": sorted({str(c.get("country") or "XX") for c in companies}),
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(ndjson_path)

    async def crawl(
        self,
        cmc_pages: int = 2,
        max_companies: int = 80,
        fetch_profiles: bool = True,
        extra_company_urls: list[str] | None = None,
    ) -> CrawlResult:
        """
        Crawl ranked company pages and map into normalized company records.

        Params
        ------
        cmc_pages        : number of ranking pages to fetch from CompaniesMarketCap
        max_companies    : maximum number of company profile pages to process
        fetch_profiles   : whether to fetch each company profile page for richer fields
        extra_company_urls : additional public company profile URLs to include
        """
        result = CrawlResult(source=self.SOURCE_NAME)

        if AsyncWebCrawler is None:
            result.errors.append("crawl4ai is unavailable in current runtime")
            result.finished_at = datetime.now(timezone.utc)
            return result

        page_urls = [f"{self.BASE_URL}/page/{i}/" for i in range(1, max(1, cmc_pages) + 1)]

        browser_cfg = BrowserConfig(headless=True, verbose=False)
        run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_until="domcontentloaded")

        discovered_rows: list[dict[str, Any]] = []
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            for page_url in page_urls:
                try:
                    crawl_res = await crawler.arun(url=page_url, config=run_cfg)
                    if not getattr(crawl_res, "success", False):
                        result.errors.append(
                            f"[crawl4ai] ranking page failed: {page_url} | {getattr(crawl_res, 'error_message', 'unknown')}"
                        )
                        continue
                    html = self._extract_html(crawl_res)
                    discovered_rows.extend(self._parse_ranking_rows(html, self.BASE_URL))
                except Exception as e:
                    result.errors.append(f"[crawl4ai] ranking page error: {page_url} | {e}")

            if extra_company_urls:
                for url in extra_company_urls:
                    u = (url or "").strip()
                    if not u:
                        continue
                    discovered_rows.append(
                        {
                            "rank": None,
                            "name": urlparse(u).path.strip("/").split("/")[0] or "Unknown",
                            "profile_url": u,
                            "country": "XX",
                            "market_cap": None,
                        }
                    )

            unique: dict[str, dict[str, Any]] = {}
            for row in discovered_rows:
                url = str(row.get("profile_url") or "").strip()
                if url and url not in unique:
                    unique[url] = row

            for row in list(unique.values())[: max(1, max_companies)]:
                profile: dict[str, Any] = {}
                if fetch_profiles:
                    try:
                        p_res = await crawler.arun(url=row["profile_url"], config=run_cfg)
                        if getattr(p_res, "success", False):
                            profile = self._parse_profile_fields(self._extract_html(p_res))
                        else:
                            result.errors.append(
                                f"[crawl4ai] profile failed: {row['profile_url']} | {getattr(p_res, 'error_message', 'unknown')}"
                            )
                    except Exception as e:
                        result.errors.append(f"[crawl4ai] profile error: {row['profile_url']} | {e}")

                company = self._to_company(row, profile)
                if company.get("company_id") and company.get("name"):
                    result.companies.append(company)
                    result.raw_count += 1

        if result.companies:
            result.minio_keys.append(
                self._upload_to_minio(
                    result.companies,
                    f"crawl4ai_companies_{len(result.companies)}.ndjson",
                )
            )
            local_snapshot = self._write_local_snapshot(result.companies)
            logger.info(f"[crawl4ai] Local snapshot written: {local_snapshot}")

        result.finished_at = datetime.now(timezone.utc)
        logger.info(f"[crawl4ai] {result.summary()}")
        return result
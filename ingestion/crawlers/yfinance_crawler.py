"""
Yahoo Finance Crawler using yfinance.
Completely FREE, requires NO API KEY. Can crawl extensive financial data, company profiles, and executives.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import yfinance as yf
from loguru import logger
from typing import Any

from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


class YFinanceCrawler(BaseCrawler):
    SOURCE_NAME = "yfinance"

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=2.0)

    @classmethod
    def _to_company(cls, info: dict[str, Any], symbol: str) -> dict[str, Any]:
        return {
            "company_id": f"YF-{symbol.upper()}",
            "name": info.get("shortName") or info.get("longName") or symbol,
            "tax_code": None,
            "company_type": "public",
            "status": "active",
            "country": info.get("country", "XX"),
            "address": info.get("address1"),
            "founded_date": info.get("founded"),
            "is_listed": True,
            "_source": cls.SOURCE_NAME,
            "_industry": info.get("industry"),
            "_sector": info.get("sector"),
            "_market_cap": info.get("marketCap"),
            "_currency": info.get("currency"),
            "_website": info.get("website"),
            "_symbol": symbol,
        }

    async def _fetch_symbol_data(self, symbol: str) -> dict[str, Any] | None:
        def fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or len(info) <= 1:
                return None
            return info
        try:
            return await asyncio.to_thread(fetch)
        except Exception as e:
            logger.warning(f"[yfinance] Failed to fetch {symbol}: {e}")
            return None

    async def crawl(self, symbols: list[str]) -> CrawlResult:
        result = CrawlResult(source=self.SOURCE_NAME)
        for symbol in symbols:
            info = await self._fetch_symbol_data(symbol)
            if info:
                company = self._to_company(info, symbol)
                result.companies.append(company)
                
                # Fetch officers
                officers = info.get("companyOfficers", [])
                for officer in officers:
                    name = officer.get("name")
                    if not name:
                        continue
                    person_id = f"YF-P-{name.replace(' ', '').upper()}"
                    result.persons.append({
                        "person_id": person_id,
                        "name": name,
                        "nationality": "XX",
                        "_source": self.SOURCE_NAME
                    })
                    result.relationships.append({
                        "source_id": person_id,
                        "target_id": company["company_id"],
                        "rel_type": "OFFICER",
                        "start_date": None,
                        "end_date": None,
                        "title": officer.get("title"),
                    })
                
                result.raw_count += 1
            else:
                result.errors.append(f"Could not fetch data for symbol: {symbol}")
                
            await asyncio.sleep(1 / self._rps)
            
        if result.companies:
             result.minio_keys.append(
                self._upload_to_minio(result.companies, f"yfinance_companies_{len(result.companies)}.ndjson")
             )
        result.finished_at = datetime.now(timezone.utc)
        return result

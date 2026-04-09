"""
Finnhub API Crawler. Requires a free API key from finnhub.io
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import aiohttp
from loguru import logger
from typing import Any

from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


class FinnhubCrawler(BaseCrawler):
    SOURCE_NAME = "finnhub"

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=1.0)
        self.api_key = settings.finnhub_api_key

    def _to_company(self, profile: dict[str, Any], symbol: str) -> dict[str, Any]:
        return {
            "company_id": f"FH-{symbol.upper()}",
            "name": profile.get("name") or symbol,
            "status": "active",
            "country": profile.get("country", "XX"),
            "website": profile.get("weburl"),
            "phone": profile.get("phone"),
            "company_type": "public",
            "is_listed": True,
            "_source": self.SOURCE_NAME,
            "_market_cap": profile.get("marketCapitalization"),
            "_ticker": profile.get("ticker"),
            "_exchange": profile.get("exchange"),
            "_industry": profile.get("finnhubIndustry"),
            "_ipo": profile.get("ipo")
        }

    async def crawl(self, symbols: list[str]) -> CrawlResult:
        result = CrawlResult(source=self.SOURCE_NAME)

        if not self.api_key:
            result.errors.append("FINNHUB_API_KEY is not configured in settings")
            result.finished_at = datetime.now(timezone.utc)
            return result

        async with await self._get_session() as session:
            for symbol in symbols:
                url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={self.api_key}"
                try:
                    data = await self.fetch_json(session, url)
                    if data and data.get("name"):
                        company = self._to_company(data, symbol)
                        result.companies.append(company)
                        result.raw_count += 1
                        
                        # Get basic financials
                        financials_url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={self.api_key}"
                        metric_data = await self.fetch_json(session, financials_url)
                        if metric_data and metric_data.get("metric"):
                            company["_financials"] = metric_data.get("metric")

                    else:
                         result.errors.append(f"No profile found for symbol: {symbol}")
                except Exception as e:
                    logger.warning(f"[Finnhub] error on {symbol}: {e}")
                    result.errors.append(f"Error fetching {symbol}: {e}")

                await asyncio.sleep(1 / self._rps)

        if result.companies:
             result.minio_keys.append(
                self._upload_to_minio(result.companies, f"finnhub_companies_{len(result.companies)}.ndjson")
             )
        result.finished_at = datetime.now(timezone.utc)
        return result

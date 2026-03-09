"""
World Bank Open Data Crawler
─────────────────────────────
API: https://api.worldbank.org/v2
Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation
License: CC BY 4.0

Dữ liệu hữu ích cho context rủi ro doanh nghiệp:
  • GDP, CPI, FDI per country/year
  • Ease of Doing Business index
  • Corruption Perception (via governance indicators)
  • Country-level risk data

Indicators key:
  NY.GDP.MKTP.CD  — GDP (USD)
  FP.CPI.TOTL.ZG  — Lạm phát CPI
  BX.KLT.DINV.CD.WD — FDI inflows
  IC.BUS.EASE.XQ  — Ease of Doing Business score
  CC.EST           — Control of Corruption estimate (WGI)
  GE.EST           — Government Effectiveness
  RQ.EST           — Regulatory Quality
  RL.EST           — Rule of Law
  VA.EST           — Voice and Accountability
  PV.EST           — Political Stability
"""
from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


# Indicators quan trọng cho risk scoring
KEY_INDICATORS: dict[str, str] = {
    "NY.GDP.MKTP.CD": "gdp_usd",
    "FP.CPI.TOTL.ZG": "inflation_cpi",
    "BX.KLT.DINV.CD.WD": "fdi_inflows_usd",
    "IC.BUS.EASE.XQ": "ease_of_business_score",
    "CC.EST": "corruption_control_estimate",
    "GE.EST": "govt_effectiveness",
    "RQ.EST": "regulatory_quality",
    "RL.EST": "rule_of_law",
    "VA.EST": "voice_accountability",
    "PV.EST": "political_stability",
    "SI.POV.GINI": "gini_coefficient",
}

COUNTRIES_OF_INTEREST = [
    "VN", "SG", "HK", "CN", "MY", "TH", "ID", "PH",
    "KR", "JP", "AU", "GB", "US", "DE", "FR",
]


class WorldBankCrawler(BaseCrawler):
    SOURCE_NAME = "worldbank"

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=5.0)   # World Bank rất thoáng
        self._base = settings.worldbank_base_url

    # ── API calls ─────────────────────────────────────────────────────────────

    async def _get_indicator(
        self,
        client,
        country: str,
        indicator: str,
        start_year: int = 2015,
        end_year: int = 2025,
        per_page: int = 500,
    ) -> list[dict]:
        url = f"{self._base}/country/{country}/indicator/{indicator}"
        params = {
            "format": "json",
            "per_page": per_page,
            "mrv": end_year - start_year + 1,  # Most Recent Values
            "date": f"{start_year}:{end_year}",
        }
        raw = await self._get(client, url, params)
        # World Bank trả về [metadata, [data]]
        if isinstance(raw, list) and len(raw) > 1:
            return raw[1] or []
        return []

    async def _get_country_info(self, client, country: str) -> dict:
        url = f"{self._base}/country/{country}?format=json"
        raw = await self._get(client, url, {})
        if isinstance(raw, list) and len(raw) > 1:
            records = raw[1] or []
            return records[0] if records else {}
        return {}

    # ── Mappers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _map_indicator_row(row: dict, indicator_key: str) -> dict | None:
        raw_value = row.get("value")
        if raw_value is None:
            return None
        # Coerce value to float — World Bank API may return strings
        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            value = raw_value
        country = row.get("country", {})
        return {
            "country_id": row.get("countryiso3code", row.get("country", {}).get("id", "")),
            "country_name": country.get("value", ""),
            "year": row.get("date", ""),
            "indicator_code": row.get("indicator", {}).get("id", ""),
            "indicator_name": row.get("indicator", {}).get("value", ""),
            "indicator_key": indicator_key,
            "value": value,
            "_source": "worldbank",
        }

    # ── Main crawl ────────────────────────────────────────────────────────────

    async def crawl(
        self,
        countries: list[str] | None = None,
        indicators: dict[str, str] | None = None,
        start_year: int = 2015,
        end_year: int = 2025,
    ) -> CrawlResult:
        """
        Crawl country-level economic & governance indicators từ World Bank.

        Params
        ------
        countries   : list ISO2 codes (mặc định COUNTRIES_OF_INTEREST)
        indicators  : dict {indicator_code: field_name} (mặc định KEY_INDICATORS)
        start_year  : năm bắt đầu
        end_year    : năm kết thúc
        """
        result = CrawlResult(source=self.SOURCE_NAME)
        countries = countries or COUNTRIES_OF_INTEREST
        indicators = indicators or KEY_INDICATORS
        all_indicator_rows: list[dict] = []

        async with self._build_client() as client:
            # Build tasks per country per indicator
            for country in countries:
                for ind_code, ind_key in indicators.items():
                    try:
                        rows = await self._get_indicator(
                            client, country, ind_code, start_year, end_year
                        )
                        result.raw_count += len(rows)
                        for row in rows:
                            mapped = self._map_indicator_row(row, ind_key)
                            if mapped:
                                all_indicator_rows.append(mapped)
                    except Exception as e:
                        result.errors.append(f"[WB] {country}/{ind_code}: {e}")

        # Flatten to country risk profiles
        country_profiles: dict[str, dict] = {}
        for row in all_indicator_rows:
            cid = row["country_id"]
            year = row["year"]
            k = f"{cid}-{year}"
            if k not in country_profiles:
                country_profiles[k] = {
                    "country_id": cid,
                    "country_name": row["country_name"],
                    "year": year,
                    "_source": "worldbank",
                }
            country_profiles[k][row["indicator_key"]] = row["value"]

        result.country_profiles = list(country_profiles.values())

        if all_indicator_rows:
            result.minio_keys.append(
                self._upload_to_minio(
                    all_indicator_rows,
                    f"wb_indicators_{len(all_indicator_rows)}.ndjson",
                )
            )
        if country_profiles:
            result.minio_keys.append(
                self._upload_to_minio(
                    list(country_profiles.values()),
                    f"wb_country_profiles_{len(country_profiles)}.ndjson",
                )
            )

        result.finished_at = datetime.now(timezone.utc)
        logger.info(f"[WorldBank] {result.summary()}")
        return result

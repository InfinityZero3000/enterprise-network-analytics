"""
Crawler Pipeline — orchestrate tất cả crawlers, publish kết quả lên Kafka.

Flow:
  1. Chạy từng crawler (parallel hoặc sequential)
  2. Dedup các entities thu thập được
  3. Publish lên Kafka topics (companies / relationships / persons)
  4. Trả về summary report
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from ingestion.crawlers.base_crawler import CrawlResult
from ingestion.crawlers.opencorporates import OpenCorporatesCrawler
from ingestion.crawlers.opensanctions import OpenSanctionsCrawler
from ingestion.crawlers.gleif import GleifCrawler
from ingestion.crawlers.openownership import OpenOwnershipCrawler
from ingestion.crawlers.worldbank import WorldBankCrawler
from ingestion.crawlers.vietnam_nbr import VietnamNBRCrawler
from ingestion.kafka_producer import EnterpriseProducer


@dataclass
class PipelineCrawlReport:
    results: list[CrawlResult] = field(default_factory=list)
    total_companies: int = 0
    total_persons: int = 0
    total_relationships: int = 0
    total_errors: int = 0
    published_companies: int = 0
    published_persons: int = 0
    published_relationships: int = 0
    duration_seconds: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> dict:
        return {
            "sources": [r.source for r in self.results],
            "total_companies": self.total_companies,
            "total_persons": self.total_persons,
            "total_relationships": self.total_relationships,
            "total_errors": self.total_errors,
            "published_companies": self.published_companies,
            "published_persons": self.published_persons,
            "published_relationships": self.published_relationships,
            "duration_s": round(self.duration_seconds, 2),
            "per_source": [r.summary() for r in self.results],
        }


class CrawlerPipeline:
    """
    Orchestrate toàn bộ crawlers và publish kết quả lên Kafka.

    Ví dụ sử dụng:
        pipeline = CrawlerPipeline()
        report = pipeline.run(sources=["opencorporates", "opensanctions", "vietnam_nbr"])
        print(report.summary())
    """

    ALL_SOURCES = [
        "opencorporates",
        "opensanctions",
        "gleif",
        "openownership",
        "worldbank",
        "vietnam_nbr",
    ]

    def __init__(self, publish_to_kafka: bool = True) -> None:
        self._publish = publish_to_kafka
        self._producer = EnterpriseProducer() if publish_to_kafka else None

    # ── Build crawlers ────────────────────────────────────────────────────────

    def _build_crawler(self, source: str, options: dict | None = None):
        opts = options or {}
        if source == "opencorporates":
            c = OpenCorporatesCrawler()
            return c, opts.get("crawl_kwargs", {
                "jurisdictions": opts.get("jurisdictions", ["vn", "sg", "hk"]),
                "queries": opts.get("queries", ["*"]),
                "max_pages": opts.get("max_pages", 3),
                "fetch_officers": opts.get("fetch_officers", True),
            })
        if source == "opensanctions":
            c = OpenSanctionsCrawler()
            return c, opts.get("crawl_kwargs", {
                "datasets": opts.get("datasets", OpenSanctionsCrawler.DEFAULT_DATASETS),
                "max_per_dataset": opts.get("max_per_dataset", 500),
            })
        if source == "gleif":
            c = GleifCrawler()
            return c, opts.get("crawl_kwargs", {
                "countries": opts.get("countries", ["VN", "SG", "HK", "MY"]),
                "max_pages": opts.get("max_pages", 5),
                "fetch_relationships": opts.get("fetch_relationships", True),
            })
        if source == "openownership":
            c = OpenOwnershipCrawler()
            return c, opts.get("crawl_kwargs", {
                "max_pages": opts.get("max_pages", 10),
            })
        if source == "worldbank":
            c = WorldBankCrawler()
            return c, opts.get("crawl_kwargs", {
                "countries": opts.get("countries", None),
                "start_year": opts.get("start_year", 2015),
                "end_year": opts.get("end_year", 2025),
            })
        if source == "vietnam_nbr":
            c = VietnamNBRCrawler()
            return c, opts.get("crawl_kwargs", {
                "keywords": opts.get("keywords", ["cong ty", "corporation"]),
                "mst_list": opts.get("mst_list", None),
                "max_pages": opts.get("max_pages", 3),
            })
        raise ValueError(f"Unknown crawler source: {source}")

    # ── Publish helpers ───────────────────────────────────────────────────────

    def _publish_result(self, result: CrawlResult, report: PipelineCrawlReport) -> None:
        if not self._producer:
            return
        for company in result.companies:
            # Skip non-company dicts (e.g. World Bank country profiles)
            if "company_id" not in company:
                continue
            try:
                self._producer.publish_company(company)
                report.published_companies += 1
            except Exception as e:
                logger.warning(f"Kafka publish company failed: {e}")

        for person in result.persons:
            if "person_id" not in person:
                continue
            try:
                self._producer.publish(
                    "ena.persons",
                    person["person_id"],
                    person,
                )
                report.published_persons += 1
            except Exception as e:
                logger.warning(f"Kafka publish person failed: {e}")

        for rel in result.relationships:
            try:
                self._producer.publish_relationship(rel)
                report.published_relationships += 1
            except Exception as e:
                logger.warning(f"Kafka publish relationship failed: {e}")

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self,
        sources: list[str] | None = None,
        source_options: dict[str, dict] | None = None,
        parallel: bool = False,
    ) -> PipelineCrawlReport:
        """
        Chạy các crawlers và publish kết quả.

        Params
        ------
        sources        : list source names (mặc định tất cả)
        source_options : {source_name: {kwarg overrides}} cho từng crawler
        parallel       : chạy song song (asyncio.gather) hay tuần tự
        """
        sources = sources or self.ALL_SOURCES
        source_options = source_options or {}
        report = PipelineCrawlReport()
        t_start = datetime.now(timezone.utc)

        if parallel:
            return asyncio.run(self._run_parallel(sources, source_options, report, t_start))
        else:
            return self._run_sequential(sources, source_options, report, t_start)

    def _run_sequential(
        self,
        sources: list[str],
        source_options: dict,
        report: PipelineCrawlReport,
        t_start: datetime,
    ) -> PipelineCrawlReport:
        for source in sources:
            try:
                crawler, kwargs = self._build_crawler(source, source_options.get(source))
                logger.info(f"[CrawlerPipeline] Starting {source} ...")
                result = crawler.run(**kwargs)
                report.results.append(result)
                report.total_companies += len(result.companies)
                report.total_persons += len(result.persons)
                report.total_relationships += len(result.relationships)
                report.total_errors += len(result.errors)
                self._publish_result(result, report)
            except Exception as e:
                logger.error(f"[CrawlerPipeline] {source} failed: {e}")
                report.total_errors += 1

        report.duration_seconds = (datetime.now(timezone.utc) - t_start).total_seconds()
        logger.info(f"[CrawlerPipeline] Done: {report.summary()}")
        return report

    async def _run_parallel(
        self,
        sources: list[str],
        source_options: dict,
        report: PipelineCrawlReport,
        t_start: datetime,
    ) -> PipelineCrawlReport:
        async def _run_one(source: str) -> CrawlResult | None:
            try:
                crawler, kwargs = self._build_crawler(source, source_options.get(source))
                return await crawler.crawl(**kwargs)
            except Exception as e:
                logger.error(f"[CrawlerPipeline] {source} failed: {e}")
                return None

        results = await asyncio.gather(*[_run_one(s) for s in sources])
        for r in results:
            if r:
                report.results.append(r)
                report.total_companies += len(r.companies)
                report.total_persons += len(r.persons)
                report.total_relationships += len(r.relationships)
                report.total_errors += len(r.errors)
                self._publish_result(r, report)

        report.duration_seconds = (datetime.now(timezone.utc) - t_start).total_seconds()
        logger.info(f"[CrawlerPipeline] Done (parallel): {report.summary()}")
        return report

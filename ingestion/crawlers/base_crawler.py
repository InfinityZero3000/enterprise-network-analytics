"""
Base Crawler — lớp nền tảng cho tất cả crawlers với:
  • Rate limiting (token-bucket via aiolimiter)
  • Retry với exponential back-off (backoff)
  • Async HTTP (httpx.AsyncClient)
  • Upload kết quả lên MinIO (ena-raw/<source>/)
  • Chuẩn hoá sang CompanyModel / PersonModel / RelationshipModel
"""
from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import backoff
import httpx
import orjson
from aiolimiter import AsyncLimiter
from loguru import logger

from config.settings import settings
from ingestion.batch_ingestion import BatchIngestion


# ─── Result container ─────────────────────────────────────────────────────────

@dataclass
class CrawlResult:
    """Kết quả của một lần crawl."""
    source: str
    companies: list[dict] = field(default_factory=list)
    persons: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    raw_count: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    minio_keys: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    def summary(self) -> dict:
        return {
            "source": self.source,
            "companies": len(self.companies),
            "persons": len(self.persons),
            "relationships": len(self.relationships),
            "raw_count": self.raw_count,
            "errors": len(self.errors),
            "duration_s": round(self.duration_seconds, 2),
            "minio_keys": self.minio_keys,
        }


# ─── Base class ───────────────────────────────────────────────────────────────

class BaseCrawler(ABC):
    """Abstract base crawler với HTTP client, rate limiter và MinIO upload."""

    SOURCE_NAME: str = "base"

    def __init__(
        self,
        rate_limit_rps: float | None = None,
        concurrency: int | None = None,
        timeout: int | None = None,
    ) -> None:
        self._rps = rate_limit_rps or settings.crawler_rate_limit_rps
        self._concurrency = concurrency or settings.crawler_concurrency
        self._timeout = timeout or settings.crawler_request_timeout
        self._limiter = AsyncLimiter(max_rate=self._rps, time_period=1)
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._minio = BatchIngestion()

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _build_client(self, headers: dict | None = None) -> httpx.AsyncClient:
        default_headers = {
            "Accept": "application/json",
            "User-Agent": (
                "EnterpriseNetworkAnalytics/1.0 "
                "(contact: admin@ena.internal; research purpose)"
            ),
        }
        if headers:
            default_headers.update(headers)
        return httpx.AsyncClient(
            timeout=self._timeout,
            headers=default_headers,
            follow_redirects=True,
            http2=True,
        )

    @backoff.on_exception(
        backoff.expo,
        (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError),
        max_tries=3,
        max_time=60,
        giveup=lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500,
        on_backoff=lambda d: logger.warning(
            f"Retry #{d['tries']} after {d['wait']:.1f}s — {d['exception']}"
        ),
    )
    async def _get(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict | None = None,
    ) -> Any:
        async with self._semaphore:
            async with self._limiter:
                resp = await client.get(url, params=params)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 10))
                    logger.warning(f"Rate limited by {url} — sleeping {retry_after}s")
                    await asyncio.sleep(retry_after)
                    resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()

    # ── MinIO upload ──────────────────────────────────────────────────────────

    def _upload_to_minio(
        self, data: list[dict], filename: str
    ) -> str:
        """Serialise list[dict] → NDJSON → upload tới ena-raw/<source>/."""
        import tempfile

        key = (
            f"{self.SOURCE_NAME}/"
            f"{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/"
            f"{filename}"
        )
        with tempfile.NamedTemporaryFile(suffix=".ndjson", delete=False, mode="wb") as f:
            for row in data:
                f.write(orjson.dumps(row) + b"\n")
            tmp_path = f.name

        self._minio.upload_file(tmp_path, key, bucket="ena-raw")
        Path(tmp_path).unlink(missing_ok=True)
        return key

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def crawl(self, **kwargs) -> CrawlResult:
        """Thực thi crawl và trả về CrawlResult."""

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self, **kwargs) -> CrawlResult:
        """Synchronous wrapper — sử dụng khi chạy từ pipeline."""
        return asyncio.run(self.crawl(**kwargs))

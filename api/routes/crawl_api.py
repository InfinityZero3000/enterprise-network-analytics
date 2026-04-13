"""
Crawl API routes — trigger crawlers qua REST API.

Endpoints:
  POST /api/v1/crawl/run          — chạy một hoặc nhiều crawlers
  GET  /api/v1/crawl/sources      — list available sources
  POST /api/v1/crawl/sanctions/match — kiểm tra tên trong sanctions list
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Body
from pydantic import BaseModel, Field
from loguru import logger

from ingestion.crawlers.crawler_pipeline import CrawlerPipeline
from ingestion.crawlers.opensanctions import OpenSanctionsCrawler
from pipeline.crawl_etl_pipeline import CrawlETLPipeline

router = APIRouter()

_pipeline = CrawlerPipeline(publish_to_kafka=True)
_sanctions = OpenSanctionsCrawler()
_etl = CrawlETLPipeline()
_job_lock = Lock()
_jobs: dict[str, dict] = {}


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    sources: list[str] = Field(
        default=["vietnam_nbr"],
        description=(
            "Danh sách nguồn cần crawl. Các giá trị hợp lệ: "
            "opencorporates, opensanctions, gleif, openownership, worldbank, vietnam_nbr, crawl4ai_company_pages, yfinance, finnhub"
        ),
    )
    parallel: bool = Field(default=False, description="Chạy song song các crawlers")
    source_options: dict[str, dict] = Field(
        default_factory=dict,
        description="Override parameters cho từng crawler theo {source_name: {kwarg: value}}",
        examples=[{
            "opencorporates": {"jurisdictions": ["vn", "sg"], "max_pages": 2},
            "vietnam_nbr": {"keywords": ["vingroup", "massan", "vinamilk"], "max_pages": 1},
        }],
    )


class SanctionsMatchRequest(BaseModel):
    names: list[str] = Field(..., min_length=1, max_length=100, description="Danh sách tên cần kiểm tra")


class CrawlRunningResponse(BaseModel):
    status: str
    message: str
    sources: list[str]
    job_id: str | None = None


class CrawlJobFlowStep(BaseModel):
    key: str
    label: str
    state: str


class CrawlJobStatusResponse(BaseModel):
    job_id: str
    mode: str
    status: str
    stage: str
    progress: int
    sources: list[str]
    parallel: bool
    dry_run: bool
    error: str | None = None
    started_at: str
    updated_at: str
    finished_at: str | None = None
    flow: list[CrawlJobFlowStep]
    result_summary: dict | None = None


class CrawlETLRequest(BaseModel):
    sources: list[str] = Field(
        default_factory=lambda: CrawlETLPipeline.FREE_SOURCES.copy(),
        description=(
            "Sources for end-to-end ETL (crawl -> quality gate -> Neo4j load). "
            "Default uses free/public sources."
        ),
    )
    parallel: bool = Field(default=True, description="Run crawlers in parallel")
    dry_run: bool = Field(default=False, description="Only crawl + quality gate, skip Neo4j load")
    source_options: dict[str, dict] = Field(
        default_factory=dict,
        description="Override crawler args by source: {source_name: {kwarg: value}}",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_flow(mode: str) -> list[dict]:
    if mode == "etl":
        return [
            {"key": "queued", "label": "Queued", "state": "running"},
            {"key": "crawl", "label": "Crawling sources", "state": "pending"},
            {"key": "quality_gate", "label": "Quality gate", "state": "pending"},
            {"key": "load_neo4j", "label": "Load to Neo4j", "state": "pending"},
            {"key": "completed", "label": "Completed", "state": "pending"},
        ]
    return [
        {"key": "queued", "label": "Queued", "state": "running"},
        {"key": "crawl", "label": "Crawling sources", "state": "pending"},
        {"key": "publish", "label": "Publish to Kafka", "state": "pending"},
        {"key": "completed", "label": "Completed", "state": "pending"},
    ]


def _create_job(mode: str, sources: list[str], parallel: bool, dry_run: bool) -> str:
    job_id = uuid4().hex
    now = _now_iso()
    with _job_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "mode": mode,
            "status": "queued",
            "stage": "queued",
            "progress": 5,
            "sources": sources,
            "parallel": parallel,
            "dry_run": dry_run,
            "error": None,
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
            "flow": _build_flow(mode),
            "result_summary": None,
        }
    return job_id


def _update_job(job_id: str, **changes) -> None:
    with _job_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = _now_iso()


def _set_flow_state(job_id: str, active_key: str, progress: int) -> None:
    with _job_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        for step in job["flow"]:
            if step["key"] == active_key:
                step["state"] = "running"
                break
            if step["state"] != "done":
                step["state"] = "done"
        job["stage"] = active_key
        job["progress"] = progress
        job["updated_at"] = _now_iso()


def _finish_job(job_id: str, success: bool, result_summary: dict | None = None, error: str | None = None) -> None:
    with _job_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if success:
            for step in job["flow"]:
                step["state"] = "done"
            job["status"] = "success"
            job["stage"] = "completed"
            job["progress"] = 100
            job["result_summary"] = result_summary
            job["error"] = None
        else:
            current = job.get("stage")
            for step in job["flow"]:
                if step["key"] == current:
                    step["state"] = "failed"
                    break
            job["status"] = "failed"
            job["error"] = error
        now = _now_iso()
        job["finished_at"] = now
        job["updated_at"] = now


# ─── Background task ──────────────────────────────────────────────────────────

def _run_crawl_background(job_id: str, req: CrawlRequest) -> None:
    try:
        _update_job(job_id, status="running")
        _set_flow_state(job_id, "crawl", 35)
        report = _pipeline.run(
            sources=req.sources,
            source_options=req.source_options,
            parallel=req.parallel,
        )
        _set_flow_state(job_id, "publish", 75)
        summary = report.summary()
        _finish_job(job_id, success=True, result_summary=summary)
        logger.info(f"[crawl-bg] Finished: {summary}")
    except Exception as e:
        _finish_job(job_id, success=False, error=str(e))
        logger.error(f"[crawl-bg] Error: {e}")


def _run_etl_background(job_id: str, req: CrawlETLRequest) -> None:
    try:
        _update_job(job_id, status="running")
        _set_flow_state(job_id, "crawl", 25)
        report = _etl.run(
            sources=req.sources,
            source_options=req.source_options,
            parallel=req.parallel,
            dry_run=req.dry_run,
        )
        _set_flow_state(job_id, "quality_gate", 60)
        if not req.dry_run:
            _set_flow_state(job_id, "load_neo4j", 85)
        summary = report.summary()
        _finish_job(job_id, success=True, result_summary=summary)
        logger.info(f"[crawl-etl-bg] Finished: {summary}")
    except Exception as e:
        _finish_job(job_id, success=False, error=str(e))
        logger.error(f"[crawl-etl-bg] Error: {e}")


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/sources", summary="List crawler sources khả dụng")
def list_sources():
    """Trả về danh sách tất cả data sources được hỗ trợ."""
    return {
        "sources": [
            {
                "id": "opencorporates",
                "name": "OpenCorporates",
                "url": "https://api.opencorporates.com/v0.4",
                "license": "CC BY 4.0",
                "data": ["companies", "officers"],
                "requires_api_key": True,
                "env_var": "OPENCORPORATES_API_TOKEN",
            },
            {
                "id": "opensanctions",
                "name": "OpenSanctions",
                "url": "https://api.opensanctions.org",
                "license": "CC BY NC 4.0",
                "data": ["sanctioned_companies", "sanctioned_persons", "peps"],
                "requires_api_key": False,
                "env_var": "OPENSANCTIONS_API_KEY",
            },
            {
                "id": "gleif",
                "name": "GLEIF (LEI Database)",
                "url": "https://api.gleif.org/api/v1",
                "license": "CC0 1.0",
                "data": ["companies", "parent_relationships"],
                "requires_api_key": False,
                "env_var": None,
            },
            {
                "id": "openownership",
                "name": "OpenOwnership (BODS)",
                "url": "https://api.openownership.org",
                "license": "CC BY 4.0",
                "data": ["beneficial_owners", "ownership_relationships"],
                "requires_api_key": False,
                "env_var": None,
            },
            {
                "id": "worldbank",
                "name": "World Bank Open Data",
                "url": "https://api.worldbank.org/v2",
                "license": "CC BY 4.0",
                "data": ["country_risk_profiles", "gdp", "governance_indicators"],
                "requires_api_key": False,
                "env_var": None,
            },
            {
                "id": "vietnam_nbr",
                "name": "Vietnam National Business Registry",
                "url": "https://masothue.com / https://thongtin.doanhnghiep.vn",
                "license": "Public",
                "data": ["vn_companies", "legal_representatives"],
                "requires_api_key": False,
                "env_var": None,
            },
            {
                "id": "crawl4ai_company_pages",
                "name": "Crawl4AI Company Pages (CompaniesMarketCap + optional URLs)",
                "url": "https://companiesmarketcap.com",
                "license": "Public web pages (respect robots.txt and terms)",
                "data": ["listed_companies", "market_cap_snapshots"],
                "requires_api_key": False,
                "env_var": None,
            },
            {
                "id": "yfinance",
                "name": "Yahoo Finance (via yfinance)",
                "url": "https://finance.yahoo.com",
                "license": "Public financial data",
                "data": ["company_profiles", "financials", "executives"],
                "requires_api_key": False,
                "env_var": None,
            },
            {
                "id": "finnhub",
                "name": "Finnhub Stock API",
                "url": "https://finnhub.io",
                "license": "Free tier available",
                "data": ["company_profiles", "basic_financials"],
                "requires_api_key": True,
                "env_var": "FINNHUB_API_KEY",
            },
        ]
    }


@router.post(
    "/run",
    summary="Chạy crawler (background)",
    response_model=CrawlRunningResponse,
    status_code=202,
)
def run_crawlers(req: CrawlRequest, background_tasks: BackgroundTasks):
    """
    Kích hoạt crawl data từ các nguồn được chọn.
    Crawl chạy ở background — trả về ngay lập tức với status 202.
    """
    valid = set(CrawlerPipeline.ALL_SOURCES)
    invalid = [s for s in req.sources if s not in valid]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown sources: {invalid}. Valid: {sorted(valid)}",
        )
    job_id = _create_job(mode="crawl", sources=req.sources, parallel=req.parallel, dry_run=False)
    background_tasks.add_task(_run_crawl_background, job_id, req)
    return CrawlRunningResponse(
        status="accepted",
        message=f"Crawl đã được lên lịch cho {len(req.sources)} nguồn. Kết quả sẽ được upload lên MinIO và publish lên Kafka.",
        sources=req.sources,
        job_id=job_id,
    )


@router.post(
    "/etl/run",
    summary="Chạy ETL crawl->quality->Neo4j (background)",
    response_model=CrawlRunningResponse,
    status_code=202,
)
def run_crawl_etl(req: CrawlETLRequest, background_tasks: BackgroundTasks):
    """
    Trigger end-to-end crawler ETL in background.
    Includes quality filtering before loading to Neo4j.
    """
    valid = set(CrawlerPipeline.ALL_SOURCES)
    invalid = [s for s in req.sources if s not in valid]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown sources: {invalid}. Valid: {sorted(valid)}",
        )

    job_id = _create_job(mode="etl", sources=req.sources, parallel=req.parallel, dry_run=req.dry_run)
    background_tasks.add_task(_run_etl_background, job_id, req)
    return CrawlRunningResponse(
        status="accepted",
        message=(
            "Crawl ETL đã được lên lịch (crawl -> quality gate -> Neo4j load). "
            "Kiểm tra logs API để theo dõi tiến trình."
        ),
        sources=req.sources,
        job_id=job_id,
    )


@router.get(
    "/jobs/{job_id}",
    summary="Lấy trạng thái tiến trình crawl/etl",
    response_model=CrawlJobStatusResponse,
)
def get_crawl_job_status(job_id: str):
    with _job_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Unknown crawl job: {job_id}")
        return CrawlJobStatusResponse(**job)


@router.post(
    "/etl/run/sync",
    summary="Chạy ETL crawl->quality->Neo4j (đồng bộ)",
)
def run_crawl_etl_sync(req: CrawlETLRequest):
    """
    Run end-to-end crawler ETL synchronously and return a full report.
    """
    valid = set(CrawlerPipeline.ALL_SOURCES)
    invalid = [s for s in req.sources if s not in valid]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown sources: {invalid}. Valid: {sorted(valid)}",
        )

    try:
        report = _etl.run(
            sources=req.sources,
            source_options=req.source_options,
            parallel=req.parallel,
            dry_run=req.dry_run,
        )
        return report.summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/run/sync",
    summary="Chạy crawler (đồng bộ — chờ kết quả)",
)
def run_crawlers_sync(req: CrawlRequest):
    """
    Chạy crawl đồng bộ và trả về report ngay.
    Lưu ý: có thể mất nhiều thời gian tuỳ số lượng sources.
    """
    valid = set(CrawlerPipeline.ALL_SOURCES)
    invalid = [s for s in req.sources if s not in valid]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown sources: {invalid}. Valid: {sorted(valid)}",
        )
    try:
        report = _pipeline.run(
            sources=req.sources,
            source_options=req.source_options,
            parallel=req.parallel,
        )
        return report.summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sanctions/match",
    summary="Kiểm tra tên trong danh sách trừng phạt & PEP",
)
def match_sanctions(req: SanctionsMatchRequest):
    """
    Kiểm tra nhanh danh sách tên có bị trừng phạt hoặc là PEP không.
    Sử dụng OpenSanctions /match/ endpoint.
    """
    try:
        result = _sanctions.run_match(req.names)
        return {
            "checked": len(req.names),
            "matches": {
                name: [
                    {
                        "id": e.get("id"),
                        "caption": e.get("caption"),
                        "schema": e.get("schema"),
                        "datasets": e.get("datasets", []),
                        "score": e.get("score"),
                    }
                    for e in entities
                ]
                for name, entities in result.items()
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/vietnam/company/{mst}",
    summary="Tra cứu doanh nghiệp Việt Nam theo MST",
)
async def get_vn_company(mst: str):
    """
    Tra cứu thông tin doanh nghiệp Việt Nam theo Mã số thuế.
    """
    from ingestion.crawlers.vietnam_nbr import VietnamNBRCrawler
    crawler = VietnamNBRCrawler()
    result = crawler.run(mst_list=[mst], keywords=[], max_pages=1, use_doanhnghiep_vn=False)
    if not result.companies:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy doanh nghiệp với MST: {mst}")
    return {
        "company": result.companies[0],
        "representatives": result.persons,
    }

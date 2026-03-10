"""
Crawl API routes — trigger crawlers qua REST API.

Endpoints:
  POST /api/v1/crawl/run          — chạy một hoặc nhiều crawlers
  GET  /api/v1/crawl/sources      — list available sources
  POST /api/v1/crawl/sanctions/match — kiểm tra tên trong sanctions list
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Body
from pydantic import BaseModel, Field
from loguru import logger

from ingestion.crawlers.crawler_pipeline import CrawlerPipeline
from ingestion.crawlers.opensanctions import OpenSanctionsCrawler

router = APIRouter()

_pipeline = CrawlerPipeline(publish_to_kafka=True)
_sanctions = OpenSanctionsCrawler()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    sources: list[str] = Field(
        default=["vietnam_nbr"],
        description=(
            "Danh sách nguồn cần crawl. Các giá trị hợp lệ: "
            "opencorporates, opensanctions, gleif, openownership, worldbank, vietnam_nbr"
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


# ─── Background task ──────────────────────────────────────────────────────────

def _run_crawl_background(req: CrawlRequest) -> None:
    try:
        report = _pipeline.run(
            sources=req.sources,
            source_options=req.source_options,
            parallel=req.parallel,
        )
        logger.info(f"[crawl-bg] Finished: {report.summary()}")
    except Exception as e:
        logger.error(f"[crawl-bg] Error: {e}")


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
                "id": "news_intelligence",
                "name": "News Intelligence (GDELT-style)",
                "url": "Tavily Search + crawl4ai + spaCy NLP",
                "license": "Varies by source",
                "data": ["companies", "persons", "relationships", "articles"],
                "requires_api_key": True,
                "env_var": "TAVILY_API_KEY",
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
    background_tasks.add_task(_run_crawl_background, req)
    return CrawlRunningResponse(
        status="accepted",
        message=f"Crawl đã được lên lịch cho {len(req.sources)} nguồn. Kết quả sẽ được upload lên MinIO và publish lên Kafka.",
        sources=req.sources,
    )


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
    _vn_crawler = VietnamNBRCrawler()
    result = _vn_crawler.run(mst_list=[mst], keywords=[], max_pages=1, use_doanhnghiep_vn=False)
    if not result.companies:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy doanh nghiệp với MST: {mst}")
    return {
        "company": result.companies[0],
        "representatives": result.persons,
    }


# ─── News Intelligence (GDELT-style) ─────────────────────────────────────────

class NewsSearchRequest(BaseModel):
    queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Từ khóa tìm kiếm tin tức (vd: ['Vingroup M&A', 'Vietnam banking fraud'])",
    )
    max_articles: int = Field(default=20, ge=1, le=100, description="Số bài tối đa")
    search_depth: str = Field(default="basic", description="basic hoặc advanced (Tavily)")
    include_domains: list[str] | None = Field(default=None, description="Chỉ crawl từ các domain này")
    exclude_domains: list[str] | None = Field(default=None, description="Bỏ qua domain này")
    extract_relationships: bool = Field(default=True, description="Chạy verb-triple extraction")


@router.post(
    "/news/search",
    summary="Tìm và phân tích tin tức (GDELT-style) — đồng bộ",
)
async def search_news(req: NewsSearchRequest):
    """
    Tìm bài báo qua Tavily → crawl nội dung → NLP entity & relationship extraction.
    Trả về entities, relationships, và articles đã phân tích.
    """
    from ingestion.crawlers.news_intelligence import NewsIntelligenceCrawler
    crawler = NewsIntelligenceCrawler()
    try:
        result = await crawler.crawl(
            queries=req.queries,
            max_articles=req.max_articles,
            search_depth=req.search_depth,
            include_domains=req.include_domains,
            exclude_domains=req.exclude_domains,
            extract_relationships=req.extract_relationships,
        )
        return {
            "summary": result.summary(),
            "companies": result.companies[:50],
            "persons": result.persons[:50],
            "relationships": result.relationships[:50],
            "errors": result.errors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/news/search/background",
    summary="Tìm và phân tích tin tức (background)",
    status_code=202,
)
def search_news_background(req: NewsSearchRequest, background_tasks: BackgroundTasks):
    """
    Kích hoạt news intelligence crawl ở background.
    Kết quả upload lên MinIO và publish lên Kafka.
    """
    def _run():
        try:
            from ingestion.crawlers.news_intelligence import NewsIntelligenceCrawler
            crawler = NewsIntelligenceCrawler()
            result = crawler.run(
                queries=req.queries,
                max_articles=req.max_articles,
                search_depth=req.search_depth,
                include_domains=req.include_domains,
                exclude_domains=req.exclude_domains,
                extract_relationships=req.extract_relationships,
            )
            logger.info(f"[news-bg] Finished: {result.summary()}")
        except Exception as e:
            logger.error(f"[news-bg] Error: {e}")

    background_tasks.add_task(_run)
    return {
        "status": "accepted",
        "message": f"News intelligence đã lên lịch cho {len(req.queries)} queries, tối đa {req.max_articles} bài.",
        "queries": req.queries,
    }

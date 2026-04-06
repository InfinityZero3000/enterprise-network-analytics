"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger

from config.settings import settings
from config.neo4j_config import Neo4jConnection, setup_constraints_and_indexes


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Enterprise Network Analytics API ...")
    try:
        setup_constraints_and_indexes()
        logger.info("Neo4j schema ready.")
    except Exception as e:
        logger.warning(f"Neo4j setup warning: {e}")
    yield
    Neo4jConnection.close()
    logger.info("API shutdown complete.")


app = FastAPI(
    title="Enterprise Network Analytics API",
    description="Phân tích mạng lưới doanh nghiệp — PySpark + Neo4j + Kafka",
    version="1.0.0",
    lifespan=lifespan,
    root_path=settings.api_root_path,
)

cors_allow_origins = _split_csv(settings.cors_allow_origins)
cors_allow_methods = _split_csv(settings.cors_allow_methods)
cors_allow_headers = _split_csv(settings.cors_allow_headers)

if "*" in cors_allow_origins and settings.cors_allow_credentials:
    # Browsers reject wildcard origin when credentials are enabled.
    logger.warning("CORS_ALLOW_CREDENTIALS=true is not compatible with CORS_ALLOW_ORIGINS=*. Disabling credentials.")
    cors_allow_credentials = False
else:
    cors_allow_credentials = settings.cors_allow_credentials

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins or ["*"],
    allow_origin_regex=settings.cors_allow_origin_regex or None,
    allow_credentials=cors_allow_credentials,
    allow_methods=cors_allow_methods or ["*"],
    allow_headers=cors_allow_headers or ["*"],
)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Optional X-API-Key authentication. Disabled when settings.api_key is empty."""
    if settings.api_key and request.url.path not in ("/health", "/docs", "/openapi.json", "/redoc"):
        provided = request.headers.get("X-API-Key", "")
        if provided != settings.api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})
    return await call_next(request)


from api.routes import companies, analytics, graph_api, ai_api, crawl_api  # noqa: E402

app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(graph_api.router, prefix="/api/v1/graph", tags=["Graph"])
app.include_router(ai_api.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(crawl_api.router, prefix="/api/v1/crawl", tags=["Crawlers"])


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "service": "enterprise-network-analytics",
        "neo4j": Neo4jConnection.health_check(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=settings.api_host, port=settings.api_port, reload=True)

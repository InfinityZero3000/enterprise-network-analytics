"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from config.settings import settings
from config.neo4j_config import Neo4jConnection, setup_constraints_and_indexes


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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

from api.routes import companies, analytics, graph_api, ai_api  # noqa: E402

app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(graph_api.router, prefix="/api/v1/graph", tags=["Graph"])
app.include_router(ai_api.router, prefix="/api/v1/ai", tags=["AI"])


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

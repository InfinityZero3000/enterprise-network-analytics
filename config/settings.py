"""
Cài đặt toàn cục từ biến môi trường — Enterprise Network Analytics
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # ── Neo4j ─────────────────────────────────────
    neo4j_uri: str = Field("bolt://localhost:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field("neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field("ena_password", validation_alias="NEO4J_PASSWORD")

    # ── Kafka ─────────────────────────────────────
    kafka_bootstrap_servers: str = Field("localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_schema_registry_url: str = Field("http://localhost:8081", validation_alias="KAFKA_SCHEMA_REGISTRY_URL")
    kafka_topic_companies: str = Field("ena.companies", validation_alias="KAFKA_TOPIC_COMPANIES")
    kafka_topic_relationships: str = Field("ena.relationships", validation_alias="KAFKA_TOPIC_RELATIONSHIPS")
    kafka_topic_transactions: str = Field("ena.transactions", validation_alias="KAFKA_TOPIC_TRANSACTIONS")
    kafka_topic_alerts: str = Field("ena.alerts", validation_alias="KAFKA_TOPIC_ALERTS")

    # ── Spark ─────────────────────────────────────
    spark_master_url: str = Field("spark://localhost:7077", validation_alias="SPARK_MASTER_URL")
    spark_app_name: str = Field("EnterpriseNetworkAnalytics", validation_alias="SPARK_APP_NAME")

    # ── MinIO ─────────────────────────────────────
    minio_endpoint: str = Field("http://localhost:9000", validation_alias="MINIO_ENDPOINT")
    minio_user: str = Field("minioadmin", validation_alias="MINIO_USER")
    minio_password: str = Field("minioadmin", validation_alias="MINIO_PASSWORD")
    minio_bucket_raw: str = Field("ena-raw", validation_alias="MINIO_BUCKET_RAW")
    minio_bucket_processed: str = Field("ena-processed", validation_alias="MINIO_BUCKET_PROCESSED")

    @property
    def minio_access_key(self) -> str:
        return self.minio_user

    @property
    def minio_secret_key(self) -> str:
        return self.minio_password

    # ── MLflow ────────────────────────────────────
    mlflow_tracking_uri: str = Field("http://localhost:5000", validation_alias="MLFLOW_TRACKING_URI")
    mlflow_experiment_name: str = Field(
        "enterprise-network-analytics", validation_alias="MLFLOW_EXPERIMENT_NAME"
    )

    # ── AI ────────────────────────────────────────
    gemini_api_key: str = Field("", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-1.5-pro", validation_alias="GEMINI_MODEL")
    groq_api_key: str = Field("", validation_alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.3-70b-versatile", validation_alias="GROQ_MODEL")
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", validation_alias="OPENAI_MODEL")
    ollama_base_url: str = Field("http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field("llama3.2", validation_alias="OLLAMA_MODEL")

    # ── Crawlers ──────────────────────────────────
    # OpenCorporates — https://api.opencorporates.com/
    opencorporates_api_token: str = Field("", validation_alias="OPENCORPORATES_API_TOKEN")
    opencorporates_base_url: str = Field(
        "https://api.opencorporates.com/v0.4", validation_alias="OPENCORPORATES_BASE_URL"
    )
    # OpenSanctions — https://api.opensanctions.org/
    opensanctions_api_key: str = Field("", validation_alias="OPENSANCTIONS_API_KEY")
    opensanctions_base_url: str = Field(
        "https://api.opensanctions.org", validation_alias="OPENSANCTIONS_BASE_URL"
    )
    # GLEIF LEI — https://api.gleif.org/api/v1/
    gleif_base_url: str = Field(
        "https://api.gleif.org/api/v1", validation_alias="GLEIF_BASE_URL"
    )
    # OpenOwnership — https://api.openownership.org/
    openownership_base_url: str = Field(
        "https://api.openownership.org", validation_alias="OPENOWNERSHIP_BASE_URL"
    )
    # World Bank — https://api.worldbank.org/v2/
    worldbank_base_url: str = Field(
        "https://api.worldbank.org/v2", validation_alias="WORLDBANK_BASE_URL"
    )
    # Vietnam DKKD — https://dangkykinhdoanh.gov.vn/
    vn_nbr_base_url: str = Field(
        "https://dangkykinhdoanh.gov.vn/vn/api", validation_alias="VN_NBR_BASE_URL"
    )
    # Crawler tunables
    crawler_request_timeout: int = Field(30, validation_alias="CRAWLER_REQUEST_TIMEOUT")
    crawler_max_retries: int = Field(3, validation_alias="CRAWLER_MAX_RETRIES")
    crawler_rate_limit_rps: float = Field(2.0, validation_alias="CRAWLER_RATE_LIMIT_RPS")
    crawler_concurrency: int = Field(5, validation_alias="CRAWLER_CONCURRENCY")

    # ── App ───────────────────────────────────────
    app_env: str = Field("development", validation_alias="APP_ENV")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    api_host: str = Field("0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(8000, validation_alias="API_PORT")
    api_key: str = Field("", validation_alias="API_KEY")  # optional; empty = auth disabled

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        populate_by_name=True,
    )


settings = Settings()

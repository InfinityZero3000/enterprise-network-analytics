"""
Cài đặt toàn cục từ biến môi trường — Enterprise Network Analytics
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── Neo4j ─────────────────────────────────────
    neo4j_uri: str = Field("bolt://localhost:7687", env="NEO4J_URI")
    neo4j_user: str = Field("neo4j", env="NEO4J_USER")
    neo4j_password: str = Field("ena_password", env="NEO4J_PASSWORD")

    # ── Kafka ─────────────────────────────────────
    kafka_bootstrap_servers: str = Field("localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    kafka_schema_registry_url: str = Field("http://localhost:8081", env="KAFKA_SCHEMA_REGISTRY_URL")
    kafka_topic_companies: str = Field("ena.companies", env="KAFKA_TOPIC_COMPANIES")
    kafka_topic_relationships: str = Field("ena.relationships", env="KAFKA_TOPIC_RELATIONSHIPS")
    kafka_topic_transactions: str = Field("ena.transactions", env="KAFKA_TOPIC_TRANSACTIONS")
    kafka_topic_alerts: str = Field("ena.alerts", env="KAFKA_TOPIC_ALERTS")

    # ── Spark ─────────────────────────────────────
    spark_master_url: str = Field("spark://localhost:7077", env="SPARK_MASTER_URL")
    spark_app_name: str = Field("EnterpriseNetworkAnalytics", env="SPARK_APP_NAME")

    # ── MinIO ─────────────────────────────────────
    minio_endpoint: str = Field("http://localhost:9000", env="MINIO_ENDPOINT")
    minio_user: str = Field("minioadmin", env="MINIO_USER")
    minio_password: str = Field("minioadmin", env="MINIO_PASSWORD")
    minio_bucket_raw: str = Field("ena-raw", env="MINIO_BUCKET_RAW")
    minio_bucket_processed: str = Field("ena-processed", env="MINIO_BUCKET_PROCESSED")

    # ── MLflow ────────────────────────────────────
    mlflow_tracking_uri: str = Field("http://localhost:5000", env="MLFLOW_TRACKING_URI")
    mlflow_experiment_name: str = Field(
        "enterprise-network-analytics", env="MLFLOW_EXPERIMENT_NAME"
    )

    # ── AI ────────────────────────────────────────
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", env="OPENAI_MODEL")
    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field("llama3.2", env="OLLAMA_MODEL")

    # ── App ───────────────────────────────────────
    app_env: str = Field("development", env="APP_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

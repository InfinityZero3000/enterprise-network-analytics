"""
Streaming Pipeline — PySpark Structured Streaming từ Kafka → Delta Lake + Neo4j
"""
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp, current_timestamp, lit
from pyspark.sql.types import StringType
from loguru import logger

from config.spark_config import create_spark_session
from config.settings import settings
from data.schemas.enterprise_schemas import COMPANY_SPARK_SCHEMA, TRANSACTION_SPARK_SCHEMA


def _kafka_options(topic: str) -> dict:
    return {
        "kafka.bootstrap.servers": settings.kafka_bootstrap_servers,
        "subscribe": topic,
        "startingOffsets": "latest",
        "maxOffsetsPerTrigger": "5000",
        "failOnDataLoss": "false",
    }


def run_company_stream(spark: SparkSession | None = None):
    """Stream company events → Delta Lake ena-processed/companies_stream"""
    spark = spark or create_spark_session("ENA-CompanyStream")
    logger.info("Starting Company Streaming pipeline ...")

    raw = (
        spark.readStream
        .format("kafka")
        .options(**_kafka_options(settings.kafka_topic_companies))
        .load()
    )

    parsed = (
        raw
        .select(from_json(col("value").cast(StringType()), COMPANY_SPARK_SCHEMA).alias("data"))
        .select("data.*")
        .withColumn("ingested_at", current_timestamp())
    )

    query = (
        parsed.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", "s3a://ena-processed/_checkpoints/companies")
        .option("path", "s3a://ena-processed/companies_stream")
        .partitionBy("status")
        .trigger(processingTime="30 seconds")
        .start()
    )

    logger.info("Company stream started. Awaiting termination ...")
    query.awaitTermination()


def run_transaction_alert_stream(spark: SparkSession | None = None, alert_threshold: float = 1_000_000_000):
    """Stream transactions → filter large transactions → write to alerts topic."""
    spark = spark or create_spark_session("ENA-TxAlertStream")
    logger.info("Starting Transaction Alert Streaming pipeline ...")

    from pyspark.sql.functions import to_json, struct

    raw = (
        spark.readStream
        .format("kafka")
        .options(**_kafka_options(settings.kafka_topic_transactions))
        .load()
    )

    parsed = (
        raw
        .select(from_json(col("value").cast(StringType()), TRANSACTION_SPARK_SCHEMA).alias("d"))
        .select("d.*")
    )

    alerts = parsed.filter(col("amount") >= alert_threshold)

    alert_stream = (
        alerts
        .withColumn("alert_type", lit("large_transaction"))
        .withColumn("ingested_at", current_timestamp())
        .select(
            col("transaction_id").cast(StringType()).alias("key"),
            to_json(struct("*")).alias("value"),
        )
    )

    query = (
        alert_stream.writeStream
        .format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("topic", settings.kafka_topic_alerts)
        .option("checkpointLocation", "s3a://ena-processed/_checkpoints/tx_alerts")
        .trigger(processingTime="10 seconds")
        .start()
    )

    logger.info("Transaction alert stream started. Awaiting termination ...")
    query.awaitTermination()


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "company"
    if mode == "company":
        run_company_stream()
    elif mode == "tx_alert":
        run_transaction_alert_stream()
    else:
        print(f"Unknown mode: {mode}. Use 'company' or 'tx_alert'")

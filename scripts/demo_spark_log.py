import os
import sys
# Add parent dir to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp, from_json
from loguru import logger
from config.settings import settings
from config.spark_config import create_spark_session
from data.schemas.enterprise_schemas import COMPANY_SPARK_SCHEMA

def run_demo():
    logger.info("Initializing Spark Session for Log Demo...")
    spark = create_spark_session("Processing-Flagging-Demo")
    spark.sparkContext.setLogLevel("WARN")

    logger.info("Connecting to Kafka stream on topic: ena.companies")
    raw_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", settings.kafka_topic_companies)
        .option("startingOffsets", "earliest")
        .load()
    )

    logger.info("[Processing] Parsing JSON from Kafka...")
    parsed_df = raw_df.select(
        from_json(col("value").cast("string"), COMPANY_SPARK_SCHEMA).alias("data"),
        col("timestamp").alias("kafka_ts")
    ).select("data.*", "kafka_ts")

    logger.info("[Flagging] Applying risk flags and cross-ownership checks...")
    # Add some mock processing rules to show on terminal as "output trung gian"
    flagged_df = parsed_df.withColumn(
        "is_high_risk", 
        col("country").isin(["XX", "UNKNOWN"])
    ).withColumn(
        "processing_time", current_timestamp()
    ).withColumn(
        "flag_reason", lit("Automated Risk Flagging Job")
    )

    logger.info("Starting output stream to Console for middle-tier output screenshots...")
    query = (
        flagged_df.writeStream
        .outputMode("append")
        .format("console")
        .option("truncate", "false")
        .trigger(processingTime="5 seconds")
        .start()
    )

    logger.info("Listening for new messages. Send a crawl request to see logs appear here!")
    query.awaitTermination()

if __name__ == "__main__":
    run_demo()

"""
PySpark ETL — quan hệ doanh nghiệp (Edges)
"""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from loguru import logger
from config.spark_config import create_spark_session
from config.settings import settings
from data.schemas.enterprise_schemas import RELATIONSHIP_SPARK_SCHEMA


def run_relationship_etl(spark: SparkSession | None = None) -> DataFrame:
    spark = spark or create_spark_session("relationship-etl")
    raw_path = f"s3a://{settings.minio_bucket_raw}/relationships/"
    output_path = f"s3a://{settings.minio_bucket_processed}/relationships/"

    df = (
        spark.read
        .option("header", True)
        .schema(RELATIONSHIP_SPARK_SCHEMA)
        .csv(raw_path)
    )

    df = (
        df
        .dropDuplicates(["source_id", "target_id", "rel_type"])
        .filter(
            F.col("source_id").isNotNull()
            & F.col("target_id").isNotNull()
            & F.col("rel_type").isNotNull()
        )
        .withColumn("rel_type", F.upper(F.col("rel_type")))
        .withColumn("ownership_percent",
            F.coalesce(F.col("ownership_percent"), F.lit(0.0)))
        .withColumn("ownership_percent",
            F.when(F.col("ownership_percent") > 100, 100.0)
            .when(F.col("ownership_percent") < 0, 0.0)
            .otherwise(F.col("ownership_percent")))
        .withColumn("is_active", F.coalesce(F.col("is_active"), F.lit(True)))
        .withColumn("ownership_tier",
            F.when(F.col("ownership_percent") >= 50, "majority")
            .when(F.col("ownership_percent") >= 25, "significant")
            .when(F.col("ownership_percent") > 0, "minority")
            .otherwise("none"))
        .withColumn("is_controlling", F.col("ownership_percent") >= 50)
        .withColumn("ingestion_ts", F.current_timestamp())
    )

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .partitionBy("rel_type")
        .option("overwriteSchema", True)
        .save(output_path)
    )
    logger.info(f"Relationship ETL complete → {output_path}")
    return df


if __name__ == "__main__":
    run_relationship_etl()

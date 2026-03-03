"""
PySpark ETL — dữ liệu công ty (Company nodes)
"""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from loguru import logger
from config.spark_config import create_spark_session
from config.settings import settings
from data.schemas.enterprise_schemas import COMPANY_SPARK_SCHEMA


def run_company_etl(spark: SparkSession | None = None) -> DataFrame:
    spark = spark or create_spark_session("company-etl")
    raw_path = f"s3a://{settings.minio_bucket_raw}/companies/"
    output_path = f"s3a://{settings.minio_bucket_processed}/companies/"

    logger.info(f"Reading companies from: {raw_path}")
    df = (
        spark.read
        .option("header", True)
        .schema(COMPANY_SPARK_SCHEMA)
        .csv(raw_path)
    )

    # Cleaning
    df = (
        df
        .dropDuplicates(["company_id"])
        .filter(F.col("company_id").isNotNull() & F.col("name").isNotNull())
        .withColumn("name", F.trim(F.upper(F.col("name"))))
        .withColumn("tax_code", F.trim(F.col("tax_code")))
        .withColumn("province", F.upper(F.trim(F.col("province"))))
        .withColumn("status", F.lower(F.col("status")))
        .withColumn("charter_capital",
            F.when(F.col("charter_capital") < 0, F.lit(0.0))
            .otherwise(F.col("charter_capital")))
    )

    # Risk feature engineering
    df = (
        df
        .withColumn("is_new_company",
            F.when(F.datediff(F.current_date(), F.col("founded_date")) < 365, True)
            .otherwise(False))
        .withColumn("low_capital_flag",
            F.when((F.col("charter_capital") < 1_000_000) & F.col("charter_capital").isNotNull(), True)
            .otherwise(False))
        .withColumn("inactive_flag",
            F.col("status").isin(["inactive", "suspended", "dissolved"]))
        .withColumn("ingestion_ts", F.current_timestamp())
    )

    # Write to Delta Lake
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .partitionBy("province", "status")
        .option("overwriteSchema", True)
        .save(output_path)
    )
    logger.info(f"Company ETL complete → {output_path}")
    return df


if __name__ == "__main__":
    run_company_etl()

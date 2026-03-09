"""
PySpark ETL — dữ liệu công ty (Company nodes)
"""
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from loguru import logger
from config.spark_config import create_spark_session
from config.settings import settings
from data.schemas.enterprise_schemas import COMPANY_SPARK_SCHEMA
from processing.transformers import clean_company_df, add_standard_company_flags


def run_company_etl(spark: SparkSession | None = None) -> DataFrame:
    spark = spark or create_spark_session("company-etl")
    raw_path = f"s3a://{settings.minio_bucket_raw}/companies/"
    output_path = f"s3a://{settings.minio_bucket_processed}/companies/"

    logger.info(f"Reading companies from: {raw_path}")
    try:
        df = (
            spark.read
            .option("header", True)
            .schema(COMPANY_SPARK_SCHEMA)
            .csv(raw_path)
        )
    except Exception as e:
        logger.error(f"Failed to read raw company data from {raw_path}: {e}")
        raise

    row_count = df.count()
    if row_count == 0:
        logger.warning(f"No company data found in {raw_path} — skipping ETL")
        return df

    logger.info(f"Read {row_count} raw company records")
    df = clean_company_df(df)
    df = add_standard_company_flags(df)

    # Write to Delta Lake
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .partitionBy("province", "status")
        .option("overwriteSchema", True)
        .save(output_path)
    )
    logger.info(f"Company ETL complete → {output_path} ({df.count()} records)")
    return df


if __name__ == "__main__":
    run_company_etl()

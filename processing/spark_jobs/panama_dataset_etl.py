"""
ETL for Panama/Bahamas/Paradise Papers dataset.

- Read local CSVs in dataset/.
- Write raw, schema-preserving tables to MinIO (panama_raw/*).
- Write normalized company/relationship/person/address CSVs to MinIO raw buckets
    so existing pipeline can consume them.
"""
from __future__ import annotations

import argparse
from typing import Iterable

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from config.settings import settings
from config.spark_config import create_spark_session
from data.schemas.enterprise_schemas import (
    COMPANY_SPARK_SCHEMA,
    RELATIONSHIP_SPARK_SCHEMA,
    PANAMA_ENTITIES_SPARK_SCHEMA,
    PANAMA_OFFICERS_SPARK_SCHEMA,
    PANAMA_INTERMEDIARIES_SPARK_SCHEMA,
    PANAMA_OTHERS_SPARK_SCHEMA,
    PANAMA_ADDRESSES_SPARK_SCHEMA,
    PANAMA_RELATIONSHIPS_SPARK_SCHEMA,
)


def _parse_date_multi(col: F.Column) -> F.Column:
    return F.coalesce(
        F.to_date(col, "dd-MMM-yyyy"),
        F.to_date(col, "yyyy-MM-dd"),
        F.to_date(col, "dd/MM/yyyy"),
    )


def _normalize_status(col: F.Column) -> F.Column:
    val = F.lower(F.trim(col))
    return (
        F.when(val.isNull() | (val == ""), F.lit("inactive"))
        .when(val.contains("active"), F.lit("active"))
        .when(val.contains("suspended"), F.lit("suspended"))
        .when(val.contains("dissolved") | val.contains("struck") | val.contains("inactive"), F.lit("inactive"))
        .otherwise(F.lit("inactive"))
    )


def _status_from_dates(*cols: Iterable[F.Column]) -> F.Column:
    cond = F.lit(False)
    for c in cols:
        cond = cond | c.isNotNull()
    return F.when(cond, F.lit("inactive")).otherwise(F.lit("active"))


def _country_code_or_name(code_col: F.Column, name_col: F.Column) -> F.Column:
    return F.coalesce(F.trim(code_col), F.trim(name_col))


def _read_csv(spark: SparkSession, path: str, schema) -> DataFrame:
    return (
        spark.read
        .option("header", True)
        .schema(schema)
        .csv(path)
    )


def _write_csv(df: DataFrame, path: str) -> None:
    (
        df.write
        .mode("overwrite")
        .option("header", True)
        .csv(path)
    )


def _write_delta(df: DataFrame, path: str) -> None:
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", True)
        .save(path)
    )


def _normalize_companies(
    entities_df: DataFrame,
    intermediaries_df: DataFrame,
    others_df: DataFrame,
) -> DataFrame:
    entities = (
        entities_df
        .withColumnRenamed("node_id", "company_id")
        .withColumn("tax_code", F.col("internal_id"))
        .withColumn("company_type", F.col("company_type"))
        .withColumn("status", _normalize_status(F.col("status")))
        .withColumn("founded_date", _parse_date_multi(F.col("incorporation_date")))
        .withColumn("country", _country_code_or_name(F.col("country_codes"), F.col("countries")))
        .select(
            "company_id",
            "name",
            "tax_code",
            "company_type",
            "status",
            F.lit(None).cast("string").alias("industry_code"),
            F.lit(None).cast("string").alias("industry_name"),
            "founded_date",
            F.lit(None).cast("double").alias("charter_capital"),
            "address",
            F.lit(None).cast("string").alias("province"),
            "country",
            F.lit(0.0).cast("double").alias("risk_score"),
            F.lit(False).cast("boolean").alias("is_listed"),
            F.lit(None).cast("string").alias("stock_code"),
        )
    )

    intermediaries = (
        intermediaries_df
        .withColumnRenamed("node_id", "company_id")
        .withColumn("tax_code", F.col("internal_id"))
        .withColumn("company_type", F.lit("service_provider"))
        .withColumn("status", _normalize_status(F.col("status")))
        .withColumn("founded_date", F.lit(None).cast("date"))
        .withColumn("country", _country_code_or_name(F.col("country_codes"), F.col("countries")))
        .select(
            "company_id",
            "name",
            "tax_code",
            "company_type",
            "status",
            F.lit(None).cast("string").alias("industry_code"),
            F.lit(None).cast("string").alias("industry_name"),
            "founded_date",
            F.lit(None).cast("double").alias("charter_capital"),
            "address",
            F.lit(None).cast("string").alias("province"),
            "country",
            F.lit(0.0).cast("double").alias("risk_score"),
            F.lit(False).cast("boolean").alias("is_listed"),
            F.lit(None).cast("string").alias("stock_code"),
        )
    )

    others = (
        others_df
        .withColumnRenamed("node_id", "company_id")
        .withColumn("tax_code", F.lit(None).cast("string"))
        .withColumn("company_type", F.col("type"))
        .withColumn(
            "status",
            _status_from_dates(
                _parse_date_multi(F.col("struck_off_date")),
                _parse_date_multi(F.col("closed_date")),
            ),
        )
        .withColumn("founded_date", _parse_date_multi(F.col("incorporation_date")))
        .withColumn("country", _country_code_or_name(F.col("country_codes"), F.col("countries")))
        .select(
            "company_id",
            "name",
            "tax_code",
            "company_type",
            "status",
            F.lit(None).cast("string").alias("industry_code"),
            F.lit(None).cast("string").alias("industry_name"),
            "founded_date",
            F.lit(None).cast("double").alias("charter_capital"),
            F.lit(None).cast("string").alias("address"),
            F.lit(None).cast("string").alias("province"),
            "country",
            F.lit(0.0).cast("double").alias("risk_score"),
            F.lit(False).cast("boolean").alias("is_listed"),
            F.lit(None).cast("string").alias("stock_code"),
        )
    )

    return entities.unionByName(intermediaries).unionByName(others)


def _build_node_type_lookup(
    entities_df: DataFrame,
    officers_df: DataFrame,
    intermediaries_df: DataFrame,
    others_df: DataFrame,
    addresses_df: DataFrame,
) -> DataFrame:
    def _label(df: DataFrame, label: str) -> DataFrame:
        return df.select(F.col("node_id").alias("node_id"), F.lit(label).alias("node_type"))

    return (
        _label(entities_df, "Company")
        .unionByName(_label(intermediaries_df, "Company"))
        .unionByName(_label(others_df, "Company"))
        .unionByName(_label(officers_df, "Person"))
        .unionByName(_label(addresses_df, "Address"))
        .dropDuplicates(["node_id"])
    )


def _normalize_relationships(rel_df: DataFrame, node_lookup: DataFrame) -> DataFrame:
    lookup_src = node_lookup.select(
        F.col("node_id").alias("node_id_start"),
        F.col("node_type").alias("source_type"),
    )
    lookup_tgt = node_lookup.select(
        F.col("node_id").alias("node_id_end"),
        F.col("node_type").alias("target_type"),
    )

    joined = (
        rel_df
        .join(lookup_src, on="node_id_start", how="left")
        .join(lookup_tgt, on="node_id_end", how="left")
    )

    status_norm = F.lower(F.trim(F.col("status")))
    is_active = (
        F.when(status_norm.isNull() | (status_norm == ""), F.lit(True))
        .when(status_norm.contains("active"), F.lit(True))
        .when(status_norm.contains("inactive") | status_norm.contains("ended"), F.lit(False))
        .otherwise(F.lit(True))
    )

    return (
        joined
        .withColumnRenamed("node_id_start", "source_id")
        .withColumnRenamed("node_id_end", "target_id")
        .withColumn("rel_type", F.upper(F.col("rel_type")))
        .withColumn("ownership_percent", F.lit(None).cast("double"))
        .withColumn("start_date", _parse_date_multi(F.col("start_date")))
        .withColumn("end_date", _parse_date_multi(F.col("end_date")))
        .withColumn("is_active", is_active)
        .select(
            "source_id",
            "target_id",
            "source_type",
            "target_type",
            "rel_type",
            "ownership_percent",
            "start_date",
            "end_date",
            "is_active",
        )
    )


def _normalize_persons(officers_df: DataFrame) -> DataFrame:
    return (
        officers_df
        .withColumnRenamed("node_id", "person_id")
        .withColumnRenamed("name", "full_name")
        .withColumn("nationality", _country_code_or_name(F.col("country_codes"), F.col("countries")))
        .withColumn("is_pep", F.lit(False).cast("boolean"))
        .withColumn("is_sanctioned", F.lit(False).cast("boolean"))
        .select("person_id", "full_name", "nationality", "is_pep", "is_sanctioned")
    )


def _normalize_addresses(addresses_df: DataFrame) -> DataFrame:
    return (
        addresses_df
        .withColumnRenamed("node_id", "address_id")
        .withColumn("country", _country_code_or_name(F.col("country_codes"), F.col("countries")))
        .select("address_id", "address", "name", "country")
    )


def run_panama_dataset_etl(
    spark: SparkSession | None = None,
    dataset_path: str = "dataset",
    write_raw: bool = True,
    write_normalized: bool = True,
) -> None:
    spark = spark or create_spark_session("panama-dataset-etl")

    entities_path = f"{dataset_path}/nodes-entities.csv"
    officers_path = f"{dataset_path}/nodes-officers.csv"
    intermediaries_path = f"{dataset_path}/nodes-intermediaries.csv"
    others_path = f"{dataset_path}/nodes-others.csv"
    addresses_path = f"{dataset_path}/nodes-addresses.csv"
    relationships_path = f"{dataset_path}/relationships.csv"

    logger.info("Reading Panama dataset CSVs...")
    entities_df = _read_csv(spark, entities_path, PANAMA_ENTITIES_SPARK_SCHEMA)
    officers_df = _read_csv(spark, officers_path, PANAMA_OFFICERS_SPARK_SCHEMA)
    intermediaries_df = _read_csv(spark, intermediaries_path, PANAMA_INTERMEDIARIES_SPARK_SCHEMA)
    others_df = _read_csv(spark, others_path, PANAMA_OTHERS_SPARK_SCHEMA)
    addresses_df = _read_csv(spark, addresses_path, PANAMA_ADDRESSES_SPARK_SCHEMA)
    relationships_df = _read_csv(spark, relationships_path, PANAMA_RELATIONSHIPS_SPARK_SCHEMA)

    if write_raw:
        raw_base = f"s3a://{settings.minio_bucket_raw}/panama_raw"
        logger.info(f"Writing raw Panama tables to {raw_base} ...")
        _write_delta(entities_df, f"{raw_base}/entities")
        _write_delta(officers_df, f"{raw_base}/officers")
        _write_delta(intermediaries_df, f"{raw_base}/intermediaries")
        _write_delta(others_df, f"{raw_base}/others")
        _write_delta(addresses_df, f"{raw_base}/addresses")
        _write_delta(relationships_df, f"{raw_base}/relationships")

    if write_normalized:
        logger.info("Normalizing companies, relationships, persons, and addresses...")
        companies_df = _normalize_companies(entities_df, intermediaries_df, others_df)
        persons_df = _normalize_persons(officers_df)
        addresses_norm = _normalize_addresses(addresses_df)
        node_lookup = _build_node_type_lookup(
            entities_df, officers_df, intermediaries_df, others_df, addresses_df
        )
        relationships_norm = _normalize_relationships(relationships_df, node_lookup)

        companies_out = f"s3a://{settings.minio_bucket_raw}/companies/panama"
        relationships_out = f"s3a://{settings.minio_bucket_raw}/relationships/panama"
        persons_out = f"s3a://{settings.minio_bucket_raw}/persons/panama"
        addresses_out = f"s3a://{settings.minio_bucket_raw}/addresses/panama"

        logger.info(f"Writing normalized companies to {companies_out} ...")
        _write_csv(companies_df.select([f.name for f in COMPANY_SPARK_SCHEMA.fields]), companies_out)

        logger.info(f"Writing normalized relationships to {relationships_out} ...")
        _write_csv(relationships_norm.select([f.name for f in RELATIONSHIP_SPARK_SCHEMA.fields]), relationships_out)

        logger.info(f"Writing normalized persons to {persons_out} ...")
        _write_csv(persons_df, persons_out)

        logger.info(f"Writing normalized addresses to {addresses_out} ...")
        _write_csv(addresses_norm, addresses_out)

    logger.success("Panama dataset ETL completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL for Panama/Bahamas/Paradise dataset")
    parser.add_argument("--dataset-path", default="dataset", help="Local folder containing CSV files")
    parser.add_argument("--skip-raw", action="store_true", help="Skip writing raw panama_raw tables")
    parser.add_argument("--skip-normalized", action="store_true", help="Skip writing normalized companies/relationships")
    args = parser.parse_args()

    run_panama_dataset_etl(
        dataset_path=args.dataset_path,
        write_raw=not args.skip_raw,
        write_normalized=not args.skip_normalized,
    )

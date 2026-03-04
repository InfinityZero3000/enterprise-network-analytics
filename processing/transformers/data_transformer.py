"""
DataTransformer — reusable PySpark DataFrame transformation helpers.

These are shared across company_etl, relationship_etl and any future ETL jobs
to avoid duplicating cleaning / feature-engineering logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


# ─── Generic helpers ──────────────────────────────────────────────────────────

class DataTransformer:
    """Chainable PySpark transformation utilities."""

    def __init__(self, df: DataFrame) -> None:
        self.df = df

    # ── Deduplication ──────────────────────────────────────────────────────
    def drop_duplicates(self, subset: list[str]) -> "DataTransformer":
        self.df = self.df.dropDuplicates(subset)
        return self

    def drop_nulls(self, cols: list[str]) -> "DataTransformer":
        """Drop rows where ANY of *cols* is null."""
        cond = F.lit(True)
        for c in cols:
            cond = cond & F.col(c).isNotNull()
        self.df = self.df.filter(cond)
        return self

    # ── String normalisation ───────────────────────────────────────────────
    def trim_and_upper(self, cols: list[str]) -> "DataTransformer":
        for c in cols:
            self.df = self.df.withColumn(c, F.trim(F.upper(F.col(c))))
        return self

    def trim(self, cols: list[str]) -> "DataTransformer":
        for c in cols:
            self.df = self.df.withColumn(c, F.trim(F.col(c)))
        return self

    def lower(self, cols: list[str]) -> "DataTransformer":
        for c in cols:
            self.df = self.df.withColumn(c, F.lower(F.col(c)))
        return self

    # ── Numeric guards ─────────────────────────────────────────────────────
    def clamp_min(self, col: str, min_val: float = 0.0) -> "DataTransformer":
        """Replace negative values with *min_val*."""
        self.df = self.df.withColumn(
            col,
            F.when(F.col(col) < min_val, F.lit(min_val).cast(DoubleType()))
            .otherwise(F.col(col)),
        )
        return self

    def fill_null_numeric(self, col: str, value: float = 0.0) -> "DataTransformer":
        self.df = self.df.fillna({col: value})
        return self

    # ── Date helpers ───────────────────────────────────────────────────────
    def add_age_days(self, date_col: str, alias: str = "age_days") -> "DataTransformer":
        """Add column counting days between *date_col* and today."""
        self.df = self.df.withColumn(alias, F.datediff(F.current_date(), F.col(date_col)))
        return self

    def flag_new_entity(
        self,
        date_col: str,
        threshold_days: int = 365,
        alias: str = "is_new_entity",
    ) -> "DataTransformer":
        self.df = self.df.withColumn(
            alias,
            F.when(F.datediff(F.current_date(), F.col(date_col)) < threshold_days, True)
            .otherwise(False),
        )
        return self

    # ── Risk feature engineering ───────────────────────────────────────────
    def add_low_capital_flag(
        self,
        capital_col: str = "charter_capital",
        threshold: float = 1_000_000.0,
        alias: str = "low_capital_flag",
    ) -> "DataTransformer":
        self.df = self.df.withColumn(
            alias,
            F.when(
                F.col(capital_col).isNotNull() & (F.col(capital_col) < threshold),
                True,
            ).otherwise(False),
        )
        return self

    def add_inactive_flag(
        self,
        status_col: str = "status",
        inactive_values: list[str] | None = None,
        alias: str = "inactive_flag",
    ) -> "DataTransformer":
        inactive_values = inactive_values or ["inactive", "suspended", "dissolved"]
        self.df = self.df.withColumn(alias, F.col(status_col).isin(inactive_values))
        return self

    # ── Audit columns ──────────────────────────────────────────────────────
    def add_ingestion_timestamp(self, alias: str = "ingestion_ts") -> "DataTransformer":
        self.df = self.df.withColumn(alias, F.current_timestamp())
        return self

    def add_etl_run_id(self, run_id: str, alias: str = "etl_run_id") -> "DataTransformer":
        self.df = self.df.withColumn(alias, F.lit(run_id))
        return self

    # ── Ownership helpers ──────────────────────────────────────────────────
    def normalize_ownership_pct(self, col: str = "ownership_percent") -> "DataTransformer":
        """Clamp ownership percentage to [0, 100], fill null with 0."""
        self.df = (
            self.df
            .fillna({col: 0.0})
            .withColumn(
                col,
                F.greatest(F.lit(0.0), F.least(F.lit(100.0), F.col(col).cast(DoubleType()))),
            )
        )
        return self

    # ── Build ──────────────────────────────────────────────────────────────
    def build(self) -> DataFrame:
        logger.debug(f"DataTransformer.build() → schema: {[f.name for f in self.df.schema.fields]}")
        return self.df


# ─── Functional helpers (stateless, for simple one-off use) ───────────────────

def add_standard_company_flags(df: DataFrame) -> DataFrame:
    """Apply the full set of company feature flags in one call.

    Equivalent to chaining:
        DataTransformer(df)
            .flag_new_entity("founded_date")
            .add_low_capital_flag()
            .add_inactive_flag()
            .add_ingestion_timestamp()
            .build()
    """
    return (
        DataTransformer(df)
        .flag_new_entity("founded_date")
        .add_low_capital_flag()
        .add_inactive_flag()
        .add_ingestion_timestamp()
        .build()
    )


def clean_company_df(df: DataFrame) -> DataFrame:
    """Standard cleaning pass for raw company CSVs."""
    return (
        DataTransformer(df)
        .drop_duplicates(["company_id"])
        .drop_nulls(["company_id", "name"])
        .trim_and_upper(["name", "province"])
        .trim(["tax_code"])
        .lower(["status"])
        .clamp_min("charter_capital")
        .build()
    )


def clean_relationship_df(df: DataFrame) -> DataFrame:
    """Standard cleaning pass for raw relationship CSVs."""
    return (
        DataTransformer(df)
        .drop_duplicates(["source_id", "target_id", "rel_type"])
        .drop_nulls(["source_id", "target_id", "rel_type"])
        .lower(["rel_type"])
        .normalize_ownership_pct("ownership_percent")
        .add_ingestion_timestamp()
        .build()
    )

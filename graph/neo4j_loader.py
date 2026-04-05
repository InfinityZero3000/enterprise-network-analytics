"""
Neo4j Loader — nạp DataFrames vào Neo4j graph
"""
import pandas as pd
from typing import Iterator
from pyspark.sql import DataFrame
from loguru import logger
from config.neo4j_config import Neo4jConnection

BATCH_SIZE = 1_000

MERGE_COMPANY = """
UNWIND $batch AS row
MERGE (c:Company {company_id: row.company_id})
SET c.name = row.name, c.tax_code = row.tax_code,
    c.company_type = row.company_type, c.status = row.status,
    c.industry_code = row.industry_code, c.charter_capital = row.charter_capital,
    c.province = row.province, c.country = row.country,
    c.risk_score = row.risk_score, c.is_listed = row.is_listed,
    c.updated_at = datetime()
WITH c, row WHERE row.industry_code IS NOT NULL
MERGE (i:Industry {code: row.industry_code})
SET i.name = row.industry_name
MERGE (c)-[:BELONGS_TO]->(i)
"""

MERGE_PERSON = """
UNWIND $batch AS row
MERGE (p:Person {person_id: row.person_id})
SET p.full_name = row.full_name,
    p.nationality = row.nationality,
    p.is_pep = row.is_pep,
    p.is_sanctioned = row.is_sanctioned,
    p.updated_at = datetime()
"""

MERGE_ADDRESS = """
UNWIND $batch AS row
MERGE (a:Address {address_id: row.address_id})
SET a.address = row.address,
    a.name = row.name,
    a.country = row.country,
    a.updated_at = datetime()
"""

MERGE_RELATIONSHIP = """
UNWIND $batch AS row
CALL {
    WITH row
    MATCH (source) WHERE
        (source:Company AND source.company_id = row.source_id) OR
        (source:Person  AND source.person_id  = row.source_id) OR
        (source:Address AND source.address_id = row.source_id)
    MATCH (target) WHERE
        (target:Company AND target.company_id = row.target_id) OR
        (target:Person  AND target.person_id  = row.target_id) OR
        (target:Address AND target.address_id = row.target_id)
    MERGE (source)-[r:RELATIONSHIP {rel_type: row.rel_type}]->(target)
    SET r.ownership_percent = row.ownership_percent,
        r.ownership_tier    = row.ownership_tier,
        r.is_controlling    = row.is_controlling,
        r.is_active         = row.is_active,
        r.updated_at        = datetime()
}
"""


class Neo4jLoader:
    def load_companies(self, df: DataFrame) -> int:
        return self._load(df, MERGE_COMPANY, "Company")

    def load_persons(self, df: DataFrame) -> int:
        return self._load(df, MERGE_PERSON, "Person")

    def load_addresses(self, df: DataFrame) -> int:
        return self._load(df, MERGE_ADDRESS, "Address")

    def load_relationships(self, df: DataFrame) -> int:
        return self._load(df, MERGE_RELATIONSHIP, "Relationship")

    def _load(self, df: DataFrame, cypher: str, label: str) -> int:
        total = 0
        pdf: pd.DataFrame = df.toPandas()
        for chunk in self._chunks(pdf, BATCH_SIZE):
            records = chunk.where(pd.notnull(chunk), None).to_dict("records")
            with Neo4jConnection.session() as s:
                s.run(cypher, batch=records)
            total += len(records)
            logger.debug(f"[{label}] {total}/{len(pdf)} loaded...")
        logger.info(f"[{label}] Total: {total} records into Neo4j.")
        return total

    @staticmethod
    def _chunks(df: pd.DataFrame, size: int) -> Iterator[pd.DataFrame]:
        for i in range(0, len(df), size):
            yield df.iloc[i: i + size]

#!/usr/bin/env python3
"""Load Panama dataset CSV files directly into Neo4j with long-running progress logs.

Usage examples:
  .venv/bin/python scripts/load_panama_to_neo4j.py
  .venv/bin/python scripts/load_panama_to_neo4j.py --dataset-path dataset --rel-chunk-rows 100000 --rel-batch-size 5000
  .venv/bin/python scripts/load_panama_to_neo4j.py --relationships-only --log-every 200000
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.neo4j_config import Neo4jConnection, setup_constraints_and_indexes
from graph.neo4j_loader import (
    MERGE_ADDRESS,
    MERGE_COMPANY,
    MERGE_PERSON,
    MERGE_RELATIONSHIP,
)


@dataclass
class ImportStats:
    companies: int = 0
    persons: int = 0
    addresses: int = 0
    relationships: int = 0
    started_at: float = 0.0


def _chunks(df: pd.DataFrame, size: int) -> Iterable[pd.DataFrame]:
    for i in range(0, len(df), size):
        yield df.iloc[i : i + size]


def _to_records(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notnull(df), None).to_dict("records")


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return pd.read_csv(path, dtype=str, low_memory=False, **kwargs)


def _normalize_active(status: object) -> bool:
    if status is None:
        return True
    s = str(status).strip().lower()
    if not s:
        return True
    return not ("inactive" in s or "ended" in s or "dissolved" in s or "struck" in s)


def _load_dataframe(cypher: str, df: pd.DataFrame, batch_size: int, label: str, log_every: int) -> int:
    total = len(df)
    loaded = 0

    if total == 0:
        logger.warning(f"[{label}] No rows to load.")
        return 0

    with Neo4jConnection.session() as session:
        for chunk in _chunks(df, batch_size):
            session.run(cypher, batch=_to_records(chunk))
            loaded += len(chunk)
            if loaded % log_every == 0 or loaded == total:
                logger.info(f"[{label}] {loaded}/{total}")

    return loaded


def _build_companies(entities: pd.DataFrame, intermediaries: pd.DataFrame, others: pd.DataFrame) -> pd.DataFrame:
    entities_df = pd.DataFrame(
        {
            "company_id": entities.get("node_id"),
            "name": entities.get("name"),
            "tax_code": entities.get("internal_id"),
            "company_type": entities.get("company_type"),
            "status": entities.get("status"),
            "industry_code": None,
            "industry_name": None,
            "charter_capital": None,
            "province": None,
            "country": entities.get("country_codes").fillna(entities.get("countries")),
            "risk_score": 0.0,
            "is_listed": False,
        }
    )

    intermediaries_df = pd.DataFrame(
        {
            "company_id": intermediaries.get("node_id"),
            "name": intermediaries.get("name"),
            "tax_code": intermediaries.get("internal_id"),
            "company_type": "service_provider",
            "status": intermediaries.get("status"),
            "industry_code": None,
            "industry_name": None,
            "charter_capital": None,
            "province": None,
            "country": intermediaries.get("country_codes").fillna(intermediaries.get("countries")),
            "risk_score": 0.0,
            "is_listed": False,
        }
    )

    others_df = pd.DataFrame(
        {
            "company_id": others.get("node_id"),
            "name": others.get("name"),
            "tax_code": None,
            "company_type": others.get("type"),
            "status": others.get("status"),
            "industry_code": None,
            "industry_name": None,
            "charter_capital": None,
            "province": None,
            "country": others.get("country_codes").fillna(others.get("countries")),
            "risk_score": 0.0,
            "is_listed": False,
        }
    )

    all_companies = pd.concat([entities_df, intermediaries_df, others_df], ignore_index=True)
    return all_companies.drop_duplicates(subset=["company_id"])


def _build_persons(officers: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "person_id": officers.get("node_id"),
            "full_name": officers.get("name"),
            "nationality": officers.get("country_codes").fillna(officers.get("countries")),
            "is_pep": False,
            "is_sanctioned": False,
        }
    ).drop_duplicates(subset=["person_id"])


def _build_addresses(addresses: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "address_id": addresses.get("node_id"),
            "address": addresses.get("address"),
            "name": addresses.get("name"),
            "country": addresses.get("country_codes").fillna(addresses.get("countries")),
        }
    ).drop_duplicates(subset=["address_id"])


def _load_nodes(dataset_path: Path, node_batch_size: int, log_every: int, stats: ImportStats) -> None:
    logger.info("Reading node CSV files...")
    entities = _read_csv(dataset_path / "nodes-entities.csv")
    intermediaries = _read_csv(dataset_path / "nodes-intermediaries.csv")
    others = _read_csv(dataset_path / "nodes-others.csv")
    officers = _read_csv(dataset_path / "nodes-officers.csv")
    addresses = _read_csv(dataset_path / "nodes-addresses.csv")

    companies_df = _build_companies(entities, intermediaries, others)
    persons_df = _build_persons(officers)
    addresses_df = _build_addresses(addresses)

    logger.info(f"Companies ready: {len(companies_df)}")
    stats.companies = _load_dataframe(MERGE_COMPANY, companies_df, node_batch_size, "Company", log_every)

    logger.info(f"Persons ready: {len(persons_df)}")
    stats.persons = _load_dataframe(MERGE_PERSON, persons_df, node_batch_size, "Person", log_every)

    logger.info(f"Addresses ready: {len(addresses_df)}")
    stats.addresses = _load_dataframe(MERGE_ADDRESS, addresses_df, node_batch_size, "Address", log_every)


def _load_relationships(
    dataset_path: Path,
    rel_chunk_rows: int,
    rel_batch_size: int,
    log_every: int,
    stats: ImportStats,
) -> None:
    rel_file = dataset_path / "relationships.csv"
    if not rel_file.exists():
        raise FileNotFoundError(f"Missing file: {rel_file}")

    logger.info("Loading relationships from chunked CSV...")
    loaded = 0

    with Neo4jConnection.session() as session:
        for csv_chunk in pd.read_csv(rel_file, dtype=str, chunksize=rel_chunk_rows, low_memory=False):
            rel_df = pd.DataFrame(
                {
                    "source_id": csv_chunk.get("node_id_start"),
                    "target_id": csv_chunk.get("node_id_end"),
                    "rel_type": csv_chunk.get("rel_type").fillna("RELATED").astype(str).str.upper(),
                    "ownership_percent": None,
                    "ownership_tier": None,
                    "is_controlling": None,
                    "is_active": csv_chunk.get("status").map(_normalize_active),
                }
            )

            rel_df = rel_df.dropna(subset=["source_id", "target_id"])
            rel_df = rel_df.drop_duplicates(subset=["source_id", "target_id", "rel_type"])

            for batch in _chunks(rel_df, rel_batch_size):
                session.run(MERGE_RELATIONSHIP, batch=_to_records(batch))
                loaded += len(batch)
                if loaded % log_every == 0:
                    logger.info(f"[Relationship] {loaded}")

    stats.relationships = loaded
    logger.info(f"[Relationship] Total loaded: {loaded}")


def _print_final_stats(stats: ImportStats) -> None:
    with Neo4jConnection.session() as session:
        result = session.run(
            "MATCH (n) WITH count(n) AS total_nodes "
            "MATCH ()-[r]->() RETURN total_nodes, count(r) AS total_rels"
        ).single()

    elapsed = time.time() - stats.started_at
    logger.success(
        "Done in {:.1f}s | loaded companies={} persons={} addresses={} relationships={} | "
        "neo4j total_nodes={} total_rels={}".format(
            elapsed,
            stats.companies,
            stats.persons,
            stats.addresses,
            stats.relationships,
            result["total_nodes"],
            result["total_rels"],
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Long-running Panama CSV -> Neo4j loader")
    parser.add_argument("--dataset-path", default="dataset", help="Path containing Panama CSV files")
    parser.add_argument("--node-batch-size", type=int, default=10_000, help="Batch size for Company/Person/Address")
    parser.add_argument("--rel-chunk-rows", type=int, default=100_000, help="CSV chunk rows for relationships")
    parser.add_argument("--rel-batch-size", type=int, default=5_000, help="Cypher batch size for relationships")
    parser.add_argument("--log-every", type=int, default=100_000, help="Progress logging interval")
    parser.add_argument("--nodes-only", action="store_true", help="Load only Company/Person/Address")
    parser.add_argument("--relationships-only", action="store_true", help="Load only relationships")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.nodes_only and args.relationships_only:
        raise ValueError("Use only one mode: --nodes-only OR --relationships-only")

    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset path not found: {dataset_path}")

    logger.info(f"Dataset path: {dataset_path.resolve()}")
    logger.info("Setting up constraints/indexes...")
    setup_constraints_and_indexes()

    stats = ImportStats(started_at=time.time())

    if not args.relationships_only:
        _load_nodes(dataset_path, args.node_batch_size, args.log_every, stats)

    if not args.nodes_only:
        _load_relationships(
            dataset_path,
            args.rel_chunk_rows,
            args.rel_batch_size,
            args.log_every,
            stats,
        )

    _print_final_stats(stats)
    Neo4jConnection.close()


if __name__ == "__main__":
    main()

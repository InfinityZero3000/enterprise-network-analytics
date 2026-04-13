#!/usr/bin/env python3
"""Load crawler JSON payload into Neo4j via project quality gate and loaders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.neo4j_config import setup_constraints_and_indexes, Neo4jConnection
from pipeline.crawl_etl_pipeline import CrawlETLPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load crawler output JSON to Neo4j."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to crawl output JSON file (contains companies/persons/relationships).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate/quality-gate only, do not write to Neo4j.",
    )
    return parser.parse_args()


def read_payload(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    payload = read_payload(input_path)
    raw_companies = payload.get("companies", [])
    raw_persons = payload.get("persons", [])
    raw_relationships = payload.get("relationships", [])

    etl = CrawlETLPipeline()
    companies, persons, relationships, quality = etl._quality_gate(
        raw_companies,
        raw_persons,
        raw_relationships,
    )

    print(f"INPUT={input_path}")
    print(
        "QUALITY="
        f"companies:{quality.companies_accepted}/{quality.companies_in},"
        f"persons:{quality.persons_accepted}/{quality.persons_in},"
        f"relationships:{quality.relationships_accepted}/{quality.relationships_in}"
    )

    if args.dry_run:
        print("DRY_RUN=1")
        return

    setup_constraints_and_indexes()

    loaded_companies = etl._load_companies(companies)
    loaded_persons = etl._load_persons(persons)
    loaded_relationships = etl._load_relationships(relationships)

    with Neo4jConnection.session() as s:
        counts = s.run(
            """
            RETURN
              count { MATCH (c:Company) } AS companies,
              count { MATCH (p:Person) } AS persons,
              count { MATCH ()-[r:RELATIONSHIP]-() } AS relationships
            """
        ).single()

    print(f"LOADED_COMPANIES={loaded_companies}")
    print(f"LOADED_PERSONS={loaded_persons}")
    print(f"LOADED_RELATIONSHIPS={loaded_relationships}")
    print(
        "GRAPH_COUNTS="
        f"companies:{counts['companies']},"
        f"persons:{counts['persons']},"
        f"relationships:{counts['relationships']}"
    )


if __name__ == "__main__":
    main()

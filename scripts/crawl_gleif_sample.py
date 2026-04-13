#!/usr/bin/env python3
"""Run a small GLEIF crawl and write JSON output to crawler_outputs/."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.crawlers.gleif import GleifCrawler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a GLEIF sample crawl and save result to a JSON file."
    )
    parser.add_argument(
        "--countries",
        nargs="+",
        default=["VN"],
        help="ISO country codes to crawl (default: VN)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Max pages per country (default: 1)",
    )
    parser.add_argument(
        "--fetch-relationships",
        action="store_true",
        help="Fetch direct-parent relationships",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help=(
            "Output JSON path. If omitted, use "
            "crawler_outputs/gleif_crawl_sample_<timestamp>.json"
        ),
    )
    return parser.parse_args()


def build_output_path(output_arg: str) -> Path:
    if output_arg:
        return Path(output_arg)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("crawler_outputs") / f"gleif_crawl_sample_{ts}.json"


def main() -> None:
    args = parse_args()

    crawler = GleifCrawler()
    result = crawler.run(
        countries=args.countries,
        max_pages=args.max_pages,
        fetch_relationships=args.fetch_relationships,
    )

    output_path = build_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "source": result.source,
        "raw_count": result.raw_count,
        "companies": result.companies,
        "persons": result.persons,
        "relationships": result.relationships,
        "errors": result.errors,
        "summary": result.summary(),
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"OUT={output_path}")
    print(f"RAW={result.raw_count}")
    print(f"COMPANIES={len(result.companies)}")
    print(f"RELATIONSHIPS={len(result.relationships)}")
    print(f"ERRORS={len(result.errors)}")


if __name__ == "__main__":
    main()

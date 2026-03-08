#!/usr/bin/env python3
"""Seed Neo4j với dữ liệu thực từ GLEIF API."""
import asyncio
from ingestion.crawlers.gleif import GleifCrawler
from config.neo4j_config import Neo4jConnection
from graph.neo4j_loader import MERGE_COMPANY, MERGE_RELATIONSHIP, BATCH_SIZE
from loguru import logger


async def main():
    c = GleifCrawler()
    logger.info("Crawling GLEIF (VN + SG)...")
    r = await c.crawl(countries=["VN", "SG"], max_pages=5, fetch_relationships=False)
    logger.info(f"companies={len(r.companies)} relationships={len(r.relationships)} errors={len(r.errors)}")

    if not r.companies:
        logger.error("No companies returned from GLEIF")
        return

    # Load companies trực tiếp bằng Cypher (không qua Spark)
    total = 0
    companies = r.companies
    for i in range(0, len(companies), BATCH_SIZE):
        batch = companies[i: i + BATCH_SIZE]
        with Neo4jConnection.session() as s:
            s.run(MERGE_COMPANY, batch=batch)
        total += len(batch)
        logger.info(f"Loaded {total}/{len(companies)} companies...")

    logger.info(f"✓ {total} companies loaded into Neo4j")
    logger.info(f"Sample: {r.companies[0]['name']} | {r.companies[0].get('country')}")

    for e in r.errors[:5]:
        logger.warning(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

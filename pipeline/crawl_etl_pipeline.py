"""
Crawl ETL Pipeline

Orchestrates:
1) Crawl data from external APIs
2) Apply quality gates (validate/normalize/deduplicate)
3) Load clean data into Neo4j

This pipeline is designed for API-sourced data and does not replace
Panama/CSV ETL jobs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from config.neo4j_config import Neo4jConnection, setup_constraints_and_indexes
from config.settings import settings
from ingestion.crawlers.crawler_pipeline import CrawlerPipeline


ALLOWED_REL_TYPES = {
    "SHAREHOLDER",
    "LEGAL_REPRESENTATIVE",
    "BOARD_MEMBER",
    "SUBSIDIARY",
    "ASSOCIATED",
    "SUPPLIER",
    "CUSTOMER",
    "PARTNER",
}


@dataclass
class QualityGateStats:
    companies_in: int = 0
    persons_in: int = 0
    relationships_in: int = 0

    companies_accepted: int = 0
    persons_accepted: int = 0
    relationships_accepted: int = 0

    companies_rejected_missing_id: int = 0
    companies_rejected_missing_name: int = 0

    persons_rejected_missing_id: int = 0
    persons_rejected_missing_name: int = 0

    relationships_rejected_missing_field: int = 0
    relationships_rejected_invalid_type: int = 0
    relationships_rejected_dangling: int = 0


@dataclass
class CrawlETLReport:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    requested_sources: list[str] = field(default_factory=list)
    effective_sources: list[str] = field(default_factory=list)
    skipped_sources: list[str] = field(default_factory=list)

    crawled_companies: int = 0
    crawled_persons: int = 0
    crawled_relationships: int = 0
    crawl_errors: int = 0

    quality: QualityGateStats = field(default_factory=QualityGateStats)

    loaded_companies: int = 0
    loaded_persons: int = 0
    loaded_relationships: int = 0

    success: bool = False
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        end = self.finished_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def summary(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "requested_sources": self.requested_sources,
            "effective_sources": self.effective_sources,
            "skipped_sources": self.skipped_sources,
            "crawled": {
                "companies": self.crawled_companies,
                "persons": self.crawled_persons,
                "relationships": self.crawled_relationships,
                "errors": self.crawl_errors,
            },
            "quality": self.quality.__dict__,
            "loaded": {
                "companies": self.loaded_companies,
                "persons": self.loaded_persons,
                "relationships": self.loaded_relationships,
            },
            "duration_s": round(self.duration_seconds, 2),
        }


class CrawlETLPipeline:
    """End-to-end ETL pipeline for crawler data into Neo4j."""

    # Keep defaults on stable sources. Some public endpoints can be geo-blocked
    # or intermittently unavailable (e.g. 502/404), but remain available as
    # optional manual sources via API/UI.
    FREE_SOURCES = ["gleif", "crawl4ai_company_pages", "yfinance", "openownership"]

    def __init__(self) -> None:
        self._crawler = CrawlerPipeline(publish_to_kafka=False)

    def _resolve_sources(self, sources: list[str] | None) -> tuple[list[str], list[str]]:
        requested = sources or self.FREE_SOURCES
        valid = set(CrawlerPipeline.ALL_SOURCES)
        effective: list[str] = []
        skipped: list[str] = []

        for source in requested:
            if source not in valid:
                skipped.append(source)
                continue

            if source == "opencorporates" and not settings.opencorporates_api_token:
                skipped.append(source)
                continue

            # For reliability: OpenSanctions is often rate-limited without key.
            if source == "opensanctions" and not settings.opensanctions_api_key:
                skipped.append(source)
                continue

            effective.append(source)

        return effective, skipped

    @staticmethod
    def _as_str(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _quality_gate(
        self,
        raw_companies: list[dict],
        raw_persons: list[dict],
        raw_relationships: list[dict],
    ) -> tuple[list[dict], list[dict], list[dict], QualityGateStats]:
        q = QualityGateStats(
            companies_in=len(raw_companies),
            persons_in=len(raw_persons),
            relationships_in=len(raw_relationships),
        )

        companies: list[dict] = []
        persons: list[dict] = []
        relationships: list[dict] = []

        seen_companies: set[str] = set()
        seen_persons: set[str] = set()
        seen_relationships: set[tuple[str, str, str]] = set()

        for row in raw_companies:
            company_id = self._as_str(row.get("company_id"))
            name = self._as_str(row.get("name"))
            if not company_id:
                q.companies_rejected_missing_id += 1
                continue
            if not name:
                q.companies_rejected_missing_name += 1
                continue
            if company_id in seen_companies:
                continue
            seen_companies.add(company_id)

            companies.append(
                {
                    "company_id": company_id,
                    "name": name,
                    "tax_code": self._as_str(row.get("tax_code")) or None,
                    "company_type": self._as_str(row.get("company_type")).lower() or "llc",
                    "status": self._as_str(row.get("status")).lower() or "active",
                    "industry_code": self._as_str(row.get("industry_code")) or None,
                    "industry_name": self._as_str(row.get("industry_name")) or None,
                    "charter_capital": row.get("charter_capital"),
                    "province": self._as_str(row.get("province")) or None,
                    "country": self._as_str(row.get("country")) or "XX",
                    "data_source": self._as_str(row.get("_source")) or "crawler",
                }
            )

        for row in raw_persons:
            person_id = self._as_str(row.get("person_id"))
            full_name = self._as_str(row.get("full_name"))
            if not person_id:
                q.persons_rejected_missing_id += 1
                continue
            if not full_name:
                q.persons_rejected_missing_name += 1
                continue
            if person_id in seen_persons:
                continue
            seen_persons.add(person_id)

            persons.append(
                {
                    "person_id": person_id,
                    "full_name": full_name,
                    "nationality": self._as_str(row.get("nationality")) or None,
                    "is_pep": bool(row.get("is_pep", False)),
                    "is_sanctioned": bool(row.get("is_sanctioned", False)),
                    "data_source": self._as_str(row.get("_source")) or "crawler",
                }
            )

        known_company_ids = {c["company_id"] for c in companies}
        known_person_ids = {p["person_id"] for p in persons}

        for row in raw_relationships:
            source_id = self._as_str(row.get("source_id"))
            target_id = self._as_str(row.get("target_id"))
            rel_type = self._as_str(row.get("rel_type")).upper()
            source_type = self._as_str(row.get("source_type"))
            target_type = self._as_str(row.get("target_type"))

            if not source_id or not target_id or not rel_type or not source_type or not target_type:
                q.relationships_rejected_missing_field += 1
                continue

            if rel_type not in ALLOWED_REL_TYPES:
                q.relationships_rejected_invalid_type += 1
                continue

            if source_type not in ("Company", "Person") or target_type not in ("Company", "Person"):
                q.relationships_rejected_invalid_type += 1
                continue

            # Keep relationship set internally consistent to avoid dangling edges
            source_ok = source_id in (known_company_ids if source_type == "Company" else known_person_ids)
            target_ok = target_id in (known_company_ids if target_type == "Company" else known_person_ids)
            if not source_ok or not target_ok:
                q.relationships_rejected_dangling += 1
                continue

            k = (source_id, target_id, rel_type)
            if k in seen_relationships:
                continue
            seen_relationships.add(k)

            ownership = row.get("ownership_percent")
            try:
                ownership = float(ownership) if ownership is not None else None
            except (TypeError, ValueError):
                ownership = None

            relationships.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "source_type": source_type,
                    "target_type": target_type,
                    "rel_type": rel_type,
                    "ownership_percent": ownership,
                    "is_active": bool(row.get("is_active", True)),
                    "source": self._as_str(row.get("_source")) or "crawler",
                }
            )

        q.companies_accepted = len(companies)
        q.persons_accepted = len(persons)
        q.relationships_accepted = len(relationships)
        return companies, persons, relationships, q

    @staticmethod
    def _chunk(items: list[dict], size: int = 1000):
        for i in range(0, len(items), size):
            yield items[i : i + size]

    def _load_companies(self, companies: list[dict]) -> int:
        if not companies:
            return 0
        cypher = """
        UNWIND $batch AS row
        MERGE (c:Company {company_id: row.company_id})
        SET c.name = row.name,
            c.tax_code = row.tax_code,
            c.company_type = row.company_type,
            c.status = row.status,
            c.industry_code = row.industry_code,
            c.industry_name = row.industry_name,
            c.charter_capital = row.charter_capital,
            c.province = row.province,
            c.country = row.country,
            c.data_source = row.data_source,
            c.updated_at = datetime()
        """
        loaded = 0
        for batch in self._chunk(companies):
            with Neo4jConnection.session() as s:
                s.run(cypher, batch=batch)
            loaded += len(batch)
        return loaded

    def _load_persons(self, persons: list[dict]) -> int:
        if not persons:
            return 0
        cypher = """
        UNWIND $batch AS row
        MERGE (p:Person {person_id: row.person_id})
        SET p.full_name = row.full_name,
            p.nationality = row.nationality,
            p.is_pep = row.is_pep,
            p.is_sanctioned = row.is_sanctioned,
            p.data_source = row.data_source,
            p.updated_at = datetime()
        """
        loaded = 0
        for batch in self._chunk(persons):
            with Neo4jConnection.session() as s:
                s.run(cypher, batch=batch)
            loaded += len(batch)
        return loaded

    def _load_relationships(self, relationships: list[dict]) -> int:
        if not relationships:
            return 0

        loaded = 0
        pair_groups: dict[tuple[str, str], list[dict]] = {}
        for row in relationships:
            pair_groups.setdefault((row["source_type"], row["target_type"]), []).append(row)

        id_key = {"Company": "company_id", "Person": "person_id"}

        for (source_type, target_type), rows in pair_groups.items():
            source_id_key = id_key[source_type]
            target_id_key = id_key[target_type]
            cypher = f"""
            UNWIND $batch AS row
            MATCH (s:{source_type} {{{source_id_key}: row.source_id}})
            MATCH (t:{target_type} {{{target_id_key}: row.target_id}})
            MERGE (s)-[r:RELATIONSHIP {{rel_type: row.rel_type}}]->(t)
            SET r.ownership_percent = row.ownership_percent,
                r.is_active = row.is_active,
                r.source = row.source,
                r.updated_at = datetime()
            """
            for batch in self._chunk(rows):
                with Neo4jConnection.session() as s:
                    s.run(cypher, batch=batch)
                loaded += len(batch)

        return loaded

    def run(
        self,
        sources: list[str] | None = None,
        source_options: dict[str, dict] | None = None,
        parallel: bool = True,
        dry_run: bool = False,
    ) -> CrawlETLReport:
        report = CrawlETLReport()
        source_options = source_options or {}

        requested_sources = sources or self.FREE_SOURCES
        report.requested_sources = requested_sources

        try:
            effective_sources, skipped_sources = self._resolve_sources(requested_sources)
            report.effective_sources = effective_sources
            report.skipped_sources = skipped_sources

            if not effective_sources:
                report.error = "No valid sources to run after source filtering"
                return report

            setup_constraints_and_indexes()

            crawl_report = self._crawler.run(
                sources=effective_sources,
                source_options=source_options,
                parallel=parallel,
            )

            raw_companies: list[dict] = []
            raw_persons: list[dict] = []
            raw_relationships: list[dict] = []

            for r in crawl_report.results:
                raw_companies.extend(r.companies)
                raw_persons.extend(r.persons)
                raw_relationships.extend(r.relationships)

            report.crawled_companies = len(raw_companies)
            report.crawled_persons = len(raw_persons)
            report.crawled_relationships = len(raw_relationships)
            report.crawl_errors = crawl_report.total_errors

            companies, persons, relationships, quality = self._quality_gate(
                raw_companies,
                raw_persons,
                raw_relationships,
            )
            report.quality = quality

            if not dry_run:
                report.loaded_companies = self._load_companies(companies)
                report.loaded_persons = self._load_persons(persons)
                report.loaded_relationships = self._load_relationships(relationships)

            report.success = True
            return report

        except Exception as exc:
            report.error = str(exc)
            logger.exception(f"[CrawlETLPipeline] failed: {exc}")
            return report
        finally:
            report.finished_at = datetime.now(timezone.utc)


if __name__ == "__main__":
    pipeline = CrawlETLPipeline()
    result = pipeline.run()
    logger.info(result.summary())

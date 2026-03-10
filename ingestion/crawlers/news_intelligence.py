"""
News Intelligence Crawler — GDELT-style entity & relationship extraction từ tin tức.

Flow:
  1. Discovery: Tavily search → candidate URLs theo keyword/company name
  2. Extraction: crawl4ai → clean text từ mỗi URL
  3. NLP: spaCy NER → trích Person, Org, GPE, Money, Date
  4. Relationship: verb-centered triples (subject, verb, object) từ dependency parse
  5. Output: CrawlResult với companies[], persons[], relationships[], articles[]

Endpoints sử dụng:
  Tavily Search API  — tìm bài báo liên quan
  crawl4ai           — extract nội dung bài báo

Rate limit:
  Tavily free: 1000 req/month
  crawl4ai:    tuỳ domain target (tôn trọng robots.txt)
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from ai.entity_extraction import (
    AggregatedEntity,
    VerbTriple,
    extract_all as extract_all_nlp,
    extract_entities_enhanced,
    extract_verb_triples_enhanced,
)
from ai.relationship_extractor import (
    ExtractedRelationship,
    extract_relationships_hybrid,
    map_verb_to_rel_type,
    resolve_relationships,
)
from config.settings import settings
from ingestion.crawlers.base_crawler import BaseCrawler, CrawlResult


# ─── Article container ────────────────────────────────────────────────────────

@dataclass
class ArticleRecord:
    """Một bài báo đã crawl và extract."""
    url: str
    title: str
    text: str
    published_date: str | None = None
    source_domain: str = ""
    entities: list[dict] = field(default_factory=list)
    triples: list[dict] = field(default_factory=list)
    crawled_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "text_length": len(self.text),
            "published_date": self.published_date,
            "source_domain": self.source_domain,
            "entity_count": len(self.entities),
            "triple_count": len(self.triples),
            "entities": self.entities,
            "triples": self.triples,
            "crawled_at": self.crawled_at,
        }


# ─── NLP helpers — delegate to ai.entity_extraction ──────────────────────────

_nlp_cache: dict[str, Any] = {}


def _get_spacy_model(lang: str = "en"):
    """Load spaCy model lazily, cache in module. (Kept for backward compat)"""
    from ai.entity_extraction import get_spacy_model
    return get_spacy_model(lang)


def extract_entities(text: str, lang: str = "en") -> list[dict]:
    """Extract named entities — delegates to enhanced module."""
    entities = extract_entities_enhanced(text, lang=lang)
    return [e.to_dict() for e in entities]


def extract_verb_triples(text: str, lang: str = "en") -> list[dict]:
    """Extract verb triples — delegates to enhanced module."""
    triples = extract_verb_triples_enhanced(text, lang=lang)
    return [t.to_dict() for t in triples]


# ─── Tavily Discovery ────────────────────────────────────────────────────────

async def _tavily_search(
    query: str,
    max_results: int = 10,
    search_depth: str = "basic",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[dict]:
    """Search Tavily for news articles matching query."""
    api_key = settings.tavily_api_key
    if not api_key:
        logger.warning("[Tavily] No API key configured — skipping discovery")
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
            "include_raw_content": True,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains

        result = await asyncio.to_thread(client.search, **kwargs)
        return result.get("results", [])
    except Exception as e:
        logger.error(f"[Tavily] Search failed: {e}")
        return []


# ─── crawl4ai Content Extraction ─────────────────────────────────────────────

async def _crawl_article(url: str, timeout: int = 60) -> dict | None:
    """Crawl a single URL using crawl4ai and return clean text."""
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await asyncio.wait_for(
                crawler.arun(url=url),
                timeout=timeout,
            )
            if result and result.success:
                return {
                    "url": url,
                    "title": result.metadata.get("title", "") if result.metadata else "",
                    "text": result.markdown or result.cleaned_html or "",
                    "published_date": (
                        result.metadata.get("published_date")
                        if result.metadata else None
                    ),
                }
    except asyncio.TimeoutError:
        logger.warning(f"[crawl4ai] Timeout crawling {url}")
    except Exception as e:
        logger.warning(f"[crawl4ai] Failed to crawl {url}: {e}")
    return None


# ─── Main Crawler Class ──────────────────────────────────────────────────────

class NewsIntelligenceCrawler(BaseCrawler):
    """
    GDELT-inspired news intelligence crawler.

    Workflow:
      1. Tavily search → find relevant news URLs
      2. crawl4ai → extract article text
      3. spaCy NER → extract entities
      4. Dependency parse → verb-centered triples
      5. Map entities to CompanyModel/PersonModel format
      6. Upload to MinIO + return CrawlResult
    """

    SOURCE_NAME = "news_intelligence"

    def __init__(self) -> None:
        super().__init__(rate_limit_rps=2.0)
        self._blocklist = self._parse_blocklist()

    def _parse_blocklist(self) -> set[str]:
        raw = settings.news_domains_blocklist
        if not raw:
            return set()
        return {d.strip().lower() for d in raw.split(",") if d.strip()}

    def _is_blocked(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(blocked in domain for blocked in self._blocklist)

    @staticmethod
    def _entity_to_company(ent: dict, article_url: str) -> dict | None:
        """Map ORG entity → company dict."""
        if ent["label"] != "ORG":
            return None
        name = ent["text"].strip()
        if len(name) < 2:
            return None
        cid = "NEWS-" + hashlib.md5(name.lower().encode()).hexdigest()[:12]
        return {
            "company_id": cid,
            "name": name,
            "tax_code": None,
            "company_type": None,
            "status": "unknown",
            "founded_date": None,
            "address": None,
            "country": None,
            "industry_code": None,
            "industry_name": None,
            "is_listed": False,
            "charter_capital": None,
            "_source": "news_intelligence",
            "_article_url": article_url,
            "_confidence": "low",
        }

    @staticmethod
    def _entity_to_person(ent: dict, article_url: str) -> dict | None:
        """Map PERSON entity → person dict."""
        if ent["label"] != "PERSON":
            return None
        name = ent["text"].strip()
        if len(name) < 2:
            return None
        pid = "P-NEWS-" + hashlib.md5(name.lower().encode()).hexdigest()[:12]
        return {
            "person_id": pid,
            "full_name": name,
            "nationality": "",
            "is_pep": False,
            "is_sanctioned": False,
            "_source": "news_intelligence",
            "_article_url": article_url,
            "_confidence": "low",
        }

    # ── Main crawl ────────────────────────────────────────────────────────────

    async def crawl(
        self,
        queries: list[str] | None = None,
        max_articles: int | None = None,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        extract_relationships: bool = True,
        use_llm: bool = True,
        max_llm_calls_per_article: int = 10,
        resolve_to_graph: bool = False,
    ) -> CrawlResult:
        """
        Crawl tin tức và extract entities/relationships kiểu GDELT.

        Params
        ------
        queries             : từ khóa tìm kiếm (vd: ["Vingroup M&A", "VN banking fraud"])
        max_articles        : tổng số bài tối đa
        search_depth        : "basic" hoặc "advanced" (Tavily)
        include_domains     : chỉ crawl từ các domain này
        exclude_domains     : bỏ qua các domain này
        extract_relationships : có chạy verb-triple extraction không
        use_llm             : dùng Groq LLM fallback cho triples không rõ rel_type
        max_llm_calls_per_article : giới hạn LLM calls per article (cost control)
        resolve_to_graph    : fuzzy match entities against Neo4j nodes
        """
        result = CrawlResult(source=self.SOURCE_NAME)
        queries = queries or ["Vietnam company acquisition merger"]
        max_articles = max_articles or settings.news_max_articles
        crawl_timeout = settings.news_crawl_timeout

        # Merge blocklist vào exclude_domains
        all_exclude = list(self._blocklist)
        if exclude_domains:
            all_exclude.extend(exclude_domains)

        seen_urls: set[str] = set()
        articles: list[ArticleRecord] = []
        entity_lookup: dict[str, str] = {}  # lowered name → entity_id
        entity_labels: dict[str, str] = {}  # lowered name → NER label

        # ── Step 1: Discovery via Tavily ──────────────────────────────────────
        articles_per_query = max(1, max_articles // len(queries))
        for query in queries:
            logger.info(f"[NewsIntel] Searching: {query}")
            search_results = await _tavily_search(
                query=query,
                max_results=articles_per_query,
                search_depth=search_depth,
                include_domains=include_domains,
                exclude_domains=all_exclude or None,
            )

            for sr in search_results:
                url = sr.get("url", "")
                if not url or url in seen_urls or self._is_blocked(url):
                    continue
                seen_urls.add(url)
                result.raw_count += 1

                # ── Step 2: Content Extraction via crawl4ai ───────────────────
                logger.debug(f"[NewsIntel] Crawling: {url}")
                article_data = await _crawl_article(url, timeout=crawl_timeout)
                article_text = (article_data or {}).get("text", "").strip()

                # Fallback to Tavily snippet if crawl4ai returned minimal text
                if len(article_text) < 100:
                    tavily_content = (
                        sr.get("raw_content", "").strip()
                        or sr.get("content", "").strip()
                    )
                    if tavily_content and len(tavily_content) > len(article_text):
                        logger.info(
                            f"[NewsIntel] crawl4ai returned {len(article_text)} chars, "
                            f"falling back to Tavily snippet ({len(tavily_content)} chars)"
                        )
                        article_text = tavily_content

                if not article_text or len(article_text) < 50:
                    result.errors.append(f"Empty content: {url}")
                    continue

                article = ArticleRecord(
                    url=url,
                    title=(article_data or {}).get(
                        "title", sr.get("title", "")
                    ),
                    text=article_text,
                    published_date=(article_data or {}).get("published_date"),
                    source_domain=urlparse(url).netloc,
                )

                # ── Step 3: NLP Entity Extraction (Enhanced) ─────────────
                nlp_result = extract_all_nlp(
                    article.text, title=article.title, lang="en",
                    min_entity_confidence=0.0, min_triple_confidence=0.0,
                )
                article.entities = nlp_result["entities"]
                if extract_relationships:
                    article.triples = nlp_result["triples"]

                articles.append(article)

                # ── Step 4: Map entities to company/person models ─────────────
                for ent in article.entities:
                    company = self._entity_to_company(ent, url)
                    if company:
                        result.companies.append(company)
                        entity_lookup[ent["text"].strip().lower()] = company["company_id"]
                        entity_labels[ent["text"].strip().lower()] = ent.get("label", "")

                    person = self._entity_to_person(ent, url)
                    if person:
                        result.persons.append(person)
                        entity_lookup[ent["text"].strip().lower()] = person["person_id"]
                        entity_labels[ent["text"].strip().lower()] = ent.get("label", "")

                # ── Step 5: Hybrid relationship extraction ────────────────────
                if extract_relationships and article.triples:
                    extracted_rels = extract_relationships_hybrid(
                        article.triples,
                        entity_labels=entity_labels,
                        min_confidence=0.2,
                        use_llm_for_unknown=use_llm,
                        max_llm_calls=max_llm_calls_per_article,
                    )
                    # Resolve entity IDs
                    extracted_rels = resolve_relationships(
                        extracted_rels,
                        resolve_neo4j=resolve_to_graph,
                    )
                    for rel in extracted_rels:
                        result.relationships.append(rel.to_crawl_dict())

                if len(articles) >= max_articles:
                    break

            if len(articles) >= max_articles:
                break

        # ── Dedup entities ────────────────────────────────────────────────────
        result.companies = _dedup_by_key(result.companies, "company_id")
        result.persons = _dedup_by_key(result.persons, "person_id")

        # ── Upload to MinIO ───────────────────────────────────────────────────
        if articles:
            key = self._upload_to_minio(
                [a.to_dict() for a in articles],
                f"articles_{len(articles)}.ndjson",
            )
            result.minio_keys.append(key)
        if result.companies:
            key = self._upload_to_minio(
                result.companies,
                f"companies_{len(result.companies)}.ndjson",
            )
            result.minio_keys.append(key)
        if result.persons:
            key = self._upload_to_minio(
                result.persons,
                f"persons_{len(result.persons)}.ndjson",
            )
            result.minio_keys.append(key)
        if result.relationships:
            key = self._upload_to_minio(
                result.relationships,
                f"relationships_{len(result.relationships)}.ndjson",
            )
            result.minio_keys.append(key)

        result.finished_at = datetime.now(timezone.utc)
        logger.info(
            f"[NewsIntel] Done: {len(articles)} articles, "
            f"{len(result.companies)} companies, "
            f"{len(result.persons)} persons, "
            f"{len(result.relationships)} relationships"
        )
        return result


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _dedup_by_key(items: list[dict], key: str) -> list[dict]:
    """Deduplicate dicts by a specific key."""
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        k = item.get(key, "")
        if k and k not in seen:
            seen.add(k)
            result.append(item)
    return result

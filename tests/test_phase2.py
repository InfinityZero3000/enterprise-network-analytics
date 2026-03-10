"""Quick E2E test for Phase 2 — run: python tests/test_phase2.py"""
import asyncio
import sys
sys.path.insert(0, ".")

from ai.entity_extraction import extract_all
from ai.relationship_extractor import (
    extract_relationships_hybrid,
    map_verb_to_rel_type,
)
from ingestion.crawlers.news_intelligence import NewsIntelligenceCrawler


def test_entity_extraction():
    text = (
        "Microsoft announced it has completed the acquisition of Activision Blizzard "
        "for 69 billion dollars. CEO Satya Nadella said the deal makes Microsoft "
        "the third-largest gaming company. Tencent holds a significant stake in Activision."
    )
    result = extract_all(text, title="Microsoft acquires Activision Blizzard")
    assert result["stats"]["total_entities"] > 0, "Should extract entities"
    assert result["stats"]["orgs"] > 0, "Should find ORG entities"
    assert result["stats"]["total_triples"] > 0, "Should find triples"

    orgs = [e for e in result["entities"] if e["label"] == "ORG"]
    org_names = [e["text"].lower() for e in orgs]
    assert any("microsoft" in n for n in org_names), "Should find Microsoft"
    print(f"  ✓ entity_extraction: {result['stats']}")


def test_relationship_extraction():
    text = (
        "Vingroup invested in VinFast, its electric vehicle subsidiary. "
        "Pham Nhat Vuong leads Vingroup as chairman. "
        "Samsung supplies components to VinFast."
    )
    result = extract_all(text, title="Vingroup and VinFast")
    entity_labels = {e["text"].lower(): e["label"] for e in result["entities"]}

    rels = extract_relationships_hybrid(
        result["triples"],
        entity_labels=entity_labels,
        min_confidence=0.0,
        use_llm_for_unknown=False,
    )
    rel_types = {r.rel_type for r in rels}
    print(f"  ✓ relationship_extraction: {len(rels)} rels, types={rel_types}")


def test_verb_mapping():
    cases = {
        "acquire": "ACQUIRED",
        "invest": "INVESTOR",
        "sue": "LEGAL_DISPUTE",
        "cung cấp": "SUPPLIER",
        "hợp tác": "PARTNER",
        "bổ nhiệm": "BOARD_MEMBER",
        "blah": "MENTIONED_WITH",
    }
    for verb, expected in cases.items():
        got = map_verb_to_rel_type(verb)
        assert got == expected, f"map_verb_to_rel_type('{verb}') = '{got}', expected '{expected}'"
    print(f"  ✓ verb_mapping: {len(cases)} cases passed")


async def test_crawl_e2e():
    crawler = NewsIntelligenceCrawler()
    result = await crawler.crawl(
        queries=["Vietnam Vingroup acquisition 2024"],
        max_articles=2,
        search_depth="basic",
        extract_relationships=True,
        use_llm=False,
        resolve_to_graph=False,
    )
    print(f"  ✓ crawl_e2e: {result.raw_count} articles, "
          f"{len(result.companies)} companies, "
          f"{len(result.persons)} persons, "
          f"{len(result.relationships)} rels, "
          f"{len(result.errors)} errors")

    if result.companies:
        print(f"    Sample ORGs: {[c['name'] for c in result.companies[:3]]}")
    if result.relationships:
        print(f"    Sample rels: {[(r['rel_type'], r.get('_confidence')) for r in result.relationships[:3]]}")


if __name__ == "__main__":
    print("=== Phase 2 Tests ===\n")

    print("[1] Entity Extraction")
    test_entity_extraction()

    print("[2] Relationship Extraction")
    test_relationship_extraction()

    print("[3] Verb Mapping")
    test_verb_mapping()

    print("[4] Full E2E Crawl (Tavily → crawl4ai → NLP → Rels)")
    asyncio.run(test_crawl_e2e())

    print("\n=== All Phase 2 tests passed ===")

"""
Relationship Extractor — Rule-based + LLM fallback cho extraction quan hệ.

Cung cấp:
  • Rule-based verb → relationship type mapping (EN + VI, mở rộng)
  • Groq LLM fallback cho triples mà rule-based không xử lý được
  • Entity Resolution: fuzzy match entities từ NLP vs nodes đã có trong Neo4j
  • Structured output phù hợp với schema CrawlResult.relationships[]
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from config.settings import settings

# ─── Relationship type constants ──────────────────────────────────────────────

REL_ACQUIRED = "ACQUIRED"
REL_MERGED = "MERGED"
REL_INVESTOR = "INVESTOR"
REL_SHAREHOLDER = "SHAREHOLDER"
REL_SUBSIDIARY = "SUBSIDIARY"
REL_DEBT_TO = "DEBT_TO"
REL_BOARD_MEMBER = "BOARD_MEMBER"
REL_DIRECTOR = "DIRECTOR"
REL_LEGAL_REP = "LEGAL_REP"
REL_SUPPLIER = "SUPPLIER"
REL_CUSTOMER = "CUSTOMER"
REL_PARTNER = "PARTNER"
REL_LEGAL_DISPUTE = "LEGAL_DISPUTE"
REL_COMPETITOR = "COMPETITOR"
REL_MENTIONED_WITH = "MENTIONED_WITH"

# Known relationship types for validation
VALID_REL_TYPES = frozenset({
    REL_ACQUIRED, REL_MERGED, REL_INVESTOR, REL_SHAREHOLDER, REL_SUBSIDIARY,
    REL_DEBT_TO, REL_BOARD_MEMBER, REL_DIRECTOR, REL_LEGAL_REP, REL_SUPPLIER,
    REL_CUSTOMER, REL_PARTNER, REL_LEGAL_DISPUTE, REL_COMPETITOR, REL_MENTIONED_WITH,
})


# ─── Extended verb → rel_type map ────────────────────────────────────────────

VERB_REL_MAP: dict[str, str] = {
    # ── Acquisition / M&A ──
    "acquire": REL_ACQUIRED, "acquired": REL_ACQUIRED,
    "buy": REL_ACQUIRED, "bought": REL_ACQUIRED,
    "purchase": REL_ACQUIRED, "purchased": REL_ACQUIRED,
    "take over": REL_ACQUIRED, "takeover": REL_ACQUIRED,
    "mua": REL_ACQUIRED, "mua lại": REL_ACQUIRED,
    "thâu tóm": REL_ACQUIRED,
    "merge": REL_MERGED, "merged": REL_MERGED,
    "sáp nhập": REL_MERGED,

    # ── Investment ──
    "invest": REL_INVESTOR, "invested": REL_INVESTOR,
    "fund": REL_INVESTOR, "funded": REL_INVESTOR,
    "finance": REL_INVESTOR, "financed": REL_INVESTOR,
    "back": REL_INVESTOR, "backed": REL_INVESTOR,
    "đầu tư": REL_INVESTOR, "rót vốn": REL_INVESTOR,
    "góp vốn": REL_INVESTOR,

    # ── Ownership / Shareholding ──
    "own": REL_SHAREHOLDER, "owned": REL_SHAREHOLDER,
    "hold": REL_SHAREHOLDER, "held": REL_SHAREHOLDER,
    "control": REL_SHAREHOLDER, "controlled": REL_SHAREHOLDER,
    "sở hữu": REL_SHAREHOLDER, "nắm giữ": REL_SHAREHOLDER,
    "chi phối": REL_SHAREHOLDER,

    # ── Subsidiary ──
    "subsidiary": REL_SUBSIDIARY, "spin off": REL_SUBSIDIARY,
    "thành lập": REL_SUBSIDIARY, "tách ra": REL_SUBSIDIARY,

    # ── Debt ──
    "owe": REL_DEBT_TO, "owed": REL_DEBT_TO,
    "borrow": REL_DEBT_TO, "borrowed": REL_DEBT_TO,
    "lend": REL_DEBT_TO, "loan": REL_DEBT_TO,
    "nợ": REL_DEBT_TO, "vay": REL_DEBT_TO, "cho vay": REL_DEBT_TO,

    # ── Board / Leadership ──
    "appoint": REL_BOARD_MEMBER, "appointed": REL_BOARD_MEMBER,
    "elect": REL_BOARD_MEMBER, "elected": REL_BOARD_MEMBER,
    "nominate": REL_BOARD_MEMBER, "nominated": REL_BOARD_MEMBER,
    "bổ nhiệm": REL_BOARD_MEMBER, "bầu": REL_BOARD_MEMBER,
    "lead": REL_DIRECTOR, "led": REL_DIRECTOR,
    "manage": REL_DIRECTOR, "managed": REL_DIRECTOR,
    "head": REL_DIRECTOR, "headed": REL_DIRECTOR,
    "run": REL_DIRECTOR,
    "điều hành": REL_DIRECTOR, "quản lý": REL_DIRECTOR,
    "represent": REL_LEGAL_REP, "đại diện": REL_LEGAL_REP,

    # ── Supply chain ──
    "supply": REL_SUPPLIER, "supplied": REL_SUPPLIER,
    "provide": REL_SUPPLIER, "provided": REL_SUPPLIER,
    "deliver": REL_SUPPLIER, "delivered": REL_SUPPLIER,
    "cung cấp": REL_SUPPLIER, "cung ứng": REL_SUPPLIER,
    "serve": REL_CUSTOMER, "served": REL_CUSTOMER,

    # ── Partnership ──
    "partner": REL_PARTNER, "partnered": REL_PARTNER,
    "collaborate": REL_PARTNER, "collaborated": REL_PARTNER,
    "cooperate": REL_PARTNER, "cooperated": REL_PARTNER,
    "ally": REL_PARTNER, "allied": REL_PARTNER,
    "sign": REL_PARTNER, "signed": REL_PARTNER,
    "hợp tác": REL_PARTNER, "liên kết": REL_PARTNER,
    "ký kết": REL_PARTNER,

    # ── Legal ──
    "sue": REL_LEGAL_DISPUTE, "sued": REL_LEGAL_DISPUTE,
    "litigate": REL_LEGAL_DISPUTE,
    "kiện": REL_LEGAL_DISPUTE, "khởi kiện": REL_LEGAL_DISPUTE,

    # ── Competition ──
    "compete": REL_COMPETITOR, "rival": REL_COMPETITOR,
    "cạnh tranh": REL_COMPETITOR,
}


def map_verb_to_rel_type(verb: str) -> str:
    """Map verb lemma → relationship type. Exact → partial → default."""
    v = verb.lower().strip()
    if v in VERB_REL_MAP:
        return VERB_REL_MAP[v]
    for key, rel_type in VERB_REL_MAP.items():
        if key in v or v in key:
            return rel_type
    return REL_MENTIONED_WITH


# ─── Data containers ─────────────────────────────────────────────────────────

@dataclass
class ExtractedRelationship:
    """Một relationship đã extract, sẵn sàng load vào graph."""
    source_name: str
    target_name: str
    source_label: str  # ORG, PERSON
    target_label: str
    rel_type: str
    confidence: float = 0.0
    verb: str = ""
    sentence: str = ""
    source_id: str | None = None  # resolved ID từ Neo4j hoặc generated
    target_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_crawl_dict(self) -> dict:
        """Convert sang schema CrawlResult.relationships[] format."""
        return {
            "source_id": self.source_id or self._generate_id(self.source_name, self.source_label),
            "target_id": self.target_id or self._generate_id(self.target_name, self.target_label),
            "source_type": "Company" if self.source_label == "ORG" else "Person",
            "target_type": "Company" if self.target_label == "ORG" else "Person",
            "rel_type": self.rel_type,
            "ownership_percent": None,
            "start_date": None,
            "end_date": None,
            "is_active": True,
            "_source": "news_intelligence",
            "_verb": self.verb,
            "_sentence": self.sentence[:300],
            "_confidence": self._confidence_label(),
        }

    def _confidence_label(self) -> str:
        if self.confidence >= 0.7:
            return "high"
        if self.confidence >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _generate_id(name: str, label: str) -> str:
        prefix = "NEWS-" if label == "ORG" else "P-NEWS-"
        return prefix + hashlib.md5(name.lower().encode()).hexdigest()[:12]


# ─── Rule-based Relationship Extraction ──────────────────────────────────────

def extract_relationships_rule_based(
    triples: list[dict],
    entity_labels: dict[str, str] | None = None,
    min_confidence: float = 0.0,
) -> list[ExtractedRelationship]:
    """
    Rule-based extraction: verb triples → typed relationships.

    Parameters
    ----------
    triples : list of dicts with keys: subject, verb/verb_lemma, object, sentence,
              optionally subject_label, object_label, confidence
    entity_labels : optional dict mapping entity name (lower) → NER label
    min_confidence : filter relationships below this threshold
    """
    entity_labels = entity_labels or {}
    relationships: list[ExtractedRelationship] = []

    for t in triples:
        verb = t.get("verb_lemma") or t.get("verb", "")
        subj = t.get("subject", "").strip()
        obj = t.get("object", "").strip()
        if not subj or not obj or not verb:
            continue

        rel_type = map_verb_to_rel_type(verb)

        subj_label = t.get("subject_label") or entity_labels.get(subj.lower(), "")
        obj_label = t.get("object_label") or entity_labels.get(obj.lower(), "")

        # Only create relationships where at least one side is ORG or PERSON
        if not subj_label and not obj_label:
            # Try to infer: if no label, skip weak triples
            if rel_type == REL_MENTIONED_WITH:
                continue

        confidence = t.get("confidence", 0.4)

        rel = ExtractedRelationship(
            source_name=subj,
            target_name=obj,
            source_label=subj_label or "ORG",
            target_label=obj_label or "ORG",
            rel_type=rel_type,
            confidence=confidence,
            verb=verb,
            sentence=t.get("sentence", "")[:300],
        )
        if rel.confidence >= min_confidence:
            relationships.append(rel)

    return relationships


# ─── Groq LLM Fallback ───────────────────────────────────────────────────────

_GROQ_SYSTEM_PROMPT = """You are an expert in business relationship extraction.
Given a sentence and two entities, determine the business relationship type.

VALID RELATIONSHIP TYPES:
- ACQUIRED (bought, merged with, took over)
- INVESTOR (invested in, funded, backed)
- SHAREHOLDER (owns shares in, controls)
- SUBSIDIARY (is subsidiary of, was spun off from)
- DEBT_TO (owes money to, borrowed from)
- BOARD_MEMBER (was appointed to board of, elected director of)
- DIRECTOR (leads, manages, heads)
- LEGAL_REP (represents legally)
- SUPPLIER (supplies to, provides goods/services)
- CUSTOMER (buys from, is customer of)
- PARTNER (partners with, collaborates with)
- LEGAL_DISPUTE (sues, litigates against)
- COMPETITOR (competes with)
- MENTIONED_WITH (co-mentioned, unclear relationship)

Respond ONLY with a JSON object:
{"rel_type": "TYPE", "confidence": 0.0-1.0, "direction": "subject_to_object" or "object_to_subject"}
"""


def _get_groq_client():
    """Initialize Groq client if API key is available."""
    api_key = settings.groq_api_key
    if not api_key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except Exception as e:
        logger.warning(f"[Groq] Failed to initialize client: {e}")
        return None


def extract_relationship_llm(
    subject: str,
    obj: str,
    sentence: str,
    subject_label: str = "",
    object_label: str = "",
) -> dict | None:
    """
    LLM fallback: dùng Groq để xác định relationship type.

    Returns dict with keys: rel_type, confidence, direction
    Returns None if LLM unavailable or failed.
    """
    client = _get_groq_client()
    if client is None:
        return None

    prompt = (
        f"Sentence: \"{sentence[:500]}\"\n"
        f"Subject: \"{subject}\" (type: {subject_label or 'unknown'})\n"
        f"Object: \"{obj}\" (type: {object_label or 'unknown'})\n\n"
        f"What is the business relationship between the subject and object?"
    )

    try:
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": _GROQ_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content or ""
        return _parse_llm_response(raw)
    except Exception as e:
        logger.warning(f"[Groq] Relationship extraction failed: {e}")
        return None


def _parse_llm_response(raw: str) -> dict | None:
    """Parse JSON response from LLM, handle markdown code blocks."""
    raw = raw.strip()
    # Strip markdown code fences
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON in response
        match = re.search(r"\{[^}]+\}", raw)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return None
        else:
            return None

    rel_type = data.get("rel_type", "").upper()
    if rel_type not in VALID_REL_TYPES:
        rel_type = REL_MENTIONED_WITH

    confidence = data.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "rel_type": rel_type,
        "confidence": confidence,
        "direction": data.get("direction", "subject_to_object"),
    }


# ─── Hybrid extraction (rule-based + LLM) ────────────────────────────────────

def extract_relationships_hybrid(
    triples: list[dict],
    entity_labels: dict[str, str] | None = None,
    min_confidence: float = 0.2,
    use_llm_for_unknown: bool = True,
    max_llm_calls: int = 20,
) -> list[ExtractedRelationship]:
    """
    Hybrid extraction: rule-based first, LLM fallback for MENTIONED_WITH.

    Parameters
    ----------
    triples : verb triples from entity_extraction module
    entity_labels : name (lower) → NER label
    min_confidence : min confidence to keep
    use_llm_for_unknown : whether to call Groq for MENTIONED_WITH triples
    max_llm_calls : cap on LLM calls per batch (cost control)
    """
    # First pass: rule-based
    rule_results = extract_relationships_rule_based(
        triples, entity_labels, min_confidence=0.0,
    )

    if not use_llm_for_unknown or not settings.groq_api_key:
        return [r for r in rule_results if r.confidence >= min_confidence]

    # Second pass: LLM for unresolved relationships
    llm_calls = 0
    final: list[ExtractedRelationship] = []

    for rel in rule_results:
        if rel.rel_type != REL_MENTIONED_WITH or llm_calls >= max_llm_calls:
            if rel.confidence >= min_confidence:
                final.append(rel)
            continue

        # Try LLM
        llm_result = extract_relationship_llm(
            subject=rel.source_name,
            obj=rel.target_name,
            sentence=rel.sentence,
            subject_label=rel.source_label,
            object_label=rel.target_label,
        )
        llm_calls += 1

        if llm_result:
            rel.rel_type = llm_result["rel_type"]
            rel.confidence = llm_result["confidence"]

            # Handle direction swap
            if llm_result.get("direction") == "object_to_subject":
                rel.source_name, rel.target_name = rel.target_name, rel.source_name
                rel.source_label, rel.target_label = rel.target_label, rel.source_label

            rel.metadata["llm_enhanced"] = True

        if rel.confidence >= min_confidence:
            final.append(rel)

    logger.info(
        f"[RelExtractor] {len(final)} relationships extracted "
        f"(rule-based: {len(final) - llm_calls}, LLM-enhanced: {llm_calls})"
    )
    return final


# ─── Entity Resolution ───────────────────────────────────────────────────────

def resolve_entity_to_neo4j(
    entity_name: str,
    entity_label: str,
    threshold: float = 0.75,
) -> dict | None:
    """
    Fuzzy match entity name từ NLP against nodes đã có trong Neo4j.

    Returns dict {node_id, name, match_score, match_type} or None.
    """
    try:
        from config.neo4j_config import Neo4jConnection
    except Exception:
        return None

    entity_lower = entity_name.strip().lower()

    try:
        with Neo4jConnection.session() as session:
            if entity_label in ("ORG", ""):
                # Try exact match on company name first
                result = session.run(
                    "MATCH (c:Company) WHERE toLower(c.name) = $name "
                    "RETURN c.company_id AS id, c.name AS name LIMIT 1",
                    name=entity_lower,
                ).single()
                if result:
                    return {
                        "node_id": result["id"],
                        "name": result["name"],
                        "match_score": 1.0,
                        "match_type": "exact",
                    }

                # Fuzzy: CONTAINS match
                result = session.run(
                    "MATCH (c:Company) "
                    "WHERE toLower(c.name) CONTAINS $name OR $name CONTAINS toLower(c.name) "
                    "RETURN c.company_id AS id, c.name AS name LIMIT 5",
                    name=entity_lower,
                ).values()
                best = _pick_best_fuzzy(entity_lower, result, threshold)
                if best:
                    return best

            if entity_label in ("PERSON", ""):
                # Exact match on person
                result = session.run(
                    "MATCH (p:Person) WHERE toLower(p.full_name) = $name "
                    "RETURN p.person_id AS id, p.full_name AS name LIMIT 1",
                    name=entity_lower,
                ).single()
                if result:
                    return {
                        "node_id": result["id"],
                        "name": result["name"],
                        "match_score": 1.0,
                        "match_type": "exact",
                    }

                result = session.run(
                    "MATCH (p:Person) "
                    "WHERE toLower(p.full_name) CONTAINS $name OR $name CONTAINS toLower(p.full_name) "
                    "RETURN p.person_id AS id, p.full_name AS name LIMIT 5",
                    name=entity_lower,
                ).values()
                best = _pick_best_fuzzy(entity_lower, result, threshold)
                if best:
                    return best

    except Exception as e:
        logger.debug(f"[EntityRes] Neo4j lookup failed for '{entity_name}': {e}")

    return None


def _pick_best_fuzzy(
    query: str,
    candidates: list,
    threshold: float,
) -> dict | None:
    """Pick best fuzzy match from Neo4j candidates using simple ratio."""
    best_score = 0.0
    best_match = None
    for row in candidates:
        if len(row) < 2:
            continue
        node_id, name = row[0], row[1]
        score = _simple_similarity(query, name.lower() if name else "")
        if score > best_score and score >= threshold:
            best_score = score
            best_match = {
                "node_id": node_id,
                "name": name,
                "match_score": round(score, 3),
                "match_type": "fuzzy",
            }
    return best_match


def _simple_similarity(a: str, b: str) -> float:
    """
    Simple string similarity (Sørensen–Dice coefficient on bigrams).
    Lightweight alternative to full Levenshtein.
    """
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0

    def bigrams(s: str) -> set[str]:
        return {s[i:i+2] for i in range(len(s) - 1)}

    bg_a = bigrams(a)
    bg_b = bigrams(b)
    if not bg_a or not bg_b:
        return 0.0
    overlap = len(bg_a & bg_b)
    return 2 * overlap / (len(bg_a) + len(bg_b))


def resolve_relationships(
    relationships: list[ExtractedRelationship],
    resolve_neo4j: bool = True,
    match_threshold: float = 0.75,
) -> list[ExtractedRelationship]:
    """
    Resolve entity IDs for all relationships.

    1. Try Neo4j match (exact → fuzzy)
    2. Fall back to generated hash ID
    """
    if not resolve_neo4j:
        for rel in relationships:
            rel.source_id = rel.source_id or ExtractedRelationship._generate_id(
                rel.source_name, rel.source_label
            )
            rel.target_id = rel.target_id or ExtractedRelationship._generate_id(
                rel.target_name, rel.target_label
            )
        return relationships

    # Cache resolved names to avoid duplicate Neo4j calls
    cache: dict[str, dict | None] = {}
    resolved_count = 0

    for rel in relationships:
        # Resolve source
        src_key = f"{rel.source_label}:{rel.source_name.lower()}"
        if src_key not in cache:
            cache[src_key] = resolve_entity_to_neo4j(
                rel.source_name, rel.source_label, match_threshold,
            )
        src_match = cache[src_key]
        if src_match:
            rel.source_id = src_match["node_id"]
            rel.metadata["source_match"] = src_match["match_type"]
            resolved_count += 1
        else:
            rel.source_id = ExtractedRelationship._generate_id(
                rel.source_name, rel.source_label
            )

        # Resolve target
        tgt_key = f"{rel.target_label}:{rel.target_name.lower()}"
        if tgt_key not in cache:
            cache[tgt_key] = resolve_entity_to_neo4j(
                rel.target_name, rel.target_label, match_threshold,
            )
        tgt_match = cache[tgt_key]
        if tgt_match:
            rel.target_id = tgt_match["node_id"]
            rel.metadata["target_match"] = tgt_match["match_type"]
            resolved_count += 1
        else:
            rel.target_id = ExtractedRelationship._generate_id(
                rel.target_name, rel.target_label
            )

    logger.info(f"[EntityRes] Resolved {resolved_count} entity references to Neo4j nodes")
    return relationships

"""
Entity Extraction — Enhanced NLP module cho trích xuất thực thể từ tin tức.

Cung cấp:
  • spaCy NER nâng cao (compound entity, multi-mention aggregation, confidence)
  • Verb-centered triple extraction (GDELT-style) với dependency parsing mở rộng
  • Entity mention scoring (frequency × position weight)

Thiết kế để dùng từ news_intelligence crawler và các module analytics khác.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# ─── spaCy lazy loading ──────────────────────────────────────────────────────

_nlp_cache: dict[str, Any] = {}

_MODEL_MAP: dict[str, str] = {
    "en": "en_core_web_sm",
}


def get_spacy_model(lang: str = "en"):
    """Load spaCy model lazily with caching."""
    if lang in _nlp_cache:
        return _nlp_cache[lang]
    try:
        import spacy
        model_name = _MODEL_MAP.get(lang, "en_core_web_sm")
        nlp = spacy.load(model_name)
        _nlp_cache[lang] = nlp
        logger.info(f"[NLP] Loaded spaCy model: {model_name}")
        return nlp
    except OSError:
        logger.warning(
            f"[NLP] spaCy model not found for lang={lang}. "
            f"Run: python -m spacy download {_MODEL_MAP.get(lang, 'en_core_web_sm')}"
        )
        return None


# ─── Data containers ─────────────────────────────────────────────────────────

@dataclass
class EntityMention:
    """Một lần xuất hiện của entity trong văn bản."""
    text: str
    label: str  # ORG, PERSON, GPE, MONEY, DATE, NORP
    start: int
    end: int
    sentence_idx: int = 0
    in_title: bool = False

    @property
    def normalized(self) -> str:
        return _normalize_entity_text(self.text)


@dataclass
class AggregatedEntity:
    """Entity được gom từ nhiều mentions, có confidence score."""
    text: str
    canonical: str  # normalized form
    label: str
    mentions: list[EntityMention] = field(default_factory=list)
    count: int = 0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "canonical": self.canonical,
            "label": self.label,
            "count": self.count,
            "confidence": round(self.confidence, 3),
            "first_mention_start": self.mentions[0].start if self.mentions else 0,
        }


@dataclass
class VerbTriple:
    """Subject-Verb-Object triple trích từ dependency parse."""
    subject: str
    verb: str
    verb_lemma: str
    object: str
    sentence: str
    subject_label: str = ""   # NER label nếu match
    object_label: str = ""    # NER label nếu match
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "verb": self.verb,
            "verb_lemma": self.verb_lemma,
            "object": self.object,
            "sentence": self.sentence[:300],
            "subject_label": self.subject_label,
            "object_label": self.object_label,
            "confidence": round(self.confidence, 3),
        }


# ─── Text normalization ──────────────────────────────────────────────────────

_TITLE_PREFIXES = re.compile(
    r"^(mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?|ceo|cfo|cto|chairman|director|"
    r"ông|bà|giám đốc|chủ tịch|tổng giám đốc)\s+",
    re.IGNORECASE,
)

_LEGAL_SUFFIXES = re.compile(
    r"\s+(inc\.?|corp\.?|ltd\.?|llc|plc|co\.?|sa|gmbh|ag|"
    r"tnhh|cổ phần|cp|jsc|.,?\s*jsc)$",
    re.IGNORECASE,
)


def _normalize_entity_text(text: str) -> str:
    """Normalize entity text for matching / dedup."""
    t = text.strip()
    t = _TITLE_PREFIXES.sub("", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _strip_legal_suffix(text: str) -> str:
    """Strip legal entity suffixes for fuzzy matching."""
    return _LEGAL_SUFFIXES.sub("", text).strip()


# ─── Entity Extraction (Enhanced) ────────────────────────────────────────────

# Labels we care about for enterprise network analysis
_RELEVANT_LABELS = frozenset({"ORG", "PERSON", "GPE", "MONEY", "DATE", "NORP"})

# Min length to keep an entity
_MIN_ENTITY_LEN = 2


def extract_entities_enhanced(
    text: str,
    title: str = "",
    lang: str = "en",
    min_confidence: float = 0.0,
) -> list[AggregatedEntity]:
    """
    Enhanced entity extraction với aggregation và confidence scoring.

    So với bản basic trong news_intelligence.py:
    - Gom nhiều mentions của cùng entity
    - Compound entity expansion (e.g., "Phạm Nhật Vượng" thay vì "Vượng")
    - Confidence score = f(frequency, position, title_mention)
    - Normalized form cho dedup
    """
    nlp = get_spacy_model(lang)
    if nlp is None:
        return []

    mentions: list[EntityMention] = []

    # Extract from title (higher weight)
    if title:
        title_doc = nlp(title[:5000])
        for ent in title_doc.ents:
            if ent.label_ not in _RELEVANT_LABELS or len(ent.text.strip()) < _MIN_ENTITY_LEN:
                continue
            mentions.append(EntityMention(
                text=ent.text.strip(),
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                sentence_idx=-1,
                in_title=True,
            ))

    # Extract from body
    doc = nlp(text[:100_000])
    for sent_idx, sent in enumerate(doc.sents):
        for ent in sent.ents:
            if ent.label_ not in _RELEVANT_LABELS or len(ent.text.strip()) < _MIN_ENTITY_LEN:
                continue
            mentions.append(EntityMention(
                text=ent.text.strip(),
                label=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
                sentence_idx=sent_idx,
                in_title=False,
            ))

    # Aggregate mentions by normalized text + label
    aggregated = _aggregate_mentions(mentions, total_sentences=sum(1 for _ in doc.sents))

    if min_confidence > 0:
        aggregated = [e for e in aggregated if e.confidence >= min_confidence]

    return aggregated


def _aggregate_mentions(
    mentions: list[EntityMention],
    total_sentences: int,
) -> list[AggregatedEntity]:
    """Gom mentions thành AggregatedEntity với confidence score."""
    groups: dict[str, list[EntityMention]] = {}
    for m in mentions:
        key = f"{m.label}:{m.normalized.lower()}"
        groups.setdefault(key, []).append(m)

    entities: list[AggregatedEntity] = []
    for key, group in groups.items():
        # Pick the most common surface form as canonical text
        surface_forms = Counter(m.text for m in group)
        best_text = surface_forms.most_common(1)[0][0]

        agg = AggregatedEntity(
            text=best_text,
            canonical=group[0].normalized,
            label=group[0].label,
            mentions=group,
            count=len(group),
        )
        agg.confidence = _compute_entity_confidence(group, total_sentences)
        entities.append(agg)

    # Sort by confidence descending
    entities.sort(key=lambda e: e.confidence, reverse=True)
    return entities


def _compute_entity_confidence(
    mentions: list[EntityMention],
    total_sentences: int,
) -> float:
    """
    Confidence score cho entity dựa trên:
      - frequency: số lần mention (log-scaled)
      - position: mention sớm trong text → score cao hơn
      - title_boost: entity xuất hiện trong tiêu đề
    """
    import math

    count = len(mentions)
    # Frequency component (0..0.4)
    freq_score = min(0.4, 0.1 * math.log2(count + 1))

    # Position component (0..0.3): earlier = higher
    if total_sentences > 0:
        earliest_sent = min(m.sentence_idx for m in mentions if m.sentence_idx >= 0) if any(m.sentence_idx >= 0 for m in mentions) else 0
        position_score = 0.3 * (1 - earliest_sent / max(total_sentences, 1))
    else:
        position_score = 0.15

    # Title boost (0..0.3)
    title_boost = 0.3 if any(m.in_title for m in mentions) else 0.0

    return min(1.0, freq_score + position_score + title_boost)


# ─── Verb-Centered Triple Extraction (Enhanced) ──────────────────────────────

# Dependency labels that indicate subject roles
_SUBJ_DEPS = frozenset({"nsubj", "nsubjpass", "csubj", "agent"})
# Dependency labels that indicate object roles
_OBJ_DEPS = frozenset({"dobj", "attr", "pobj", "oprd", "dative"})
# Dependency labels for prepositional complements
_PREP_DEPS = frozenset({"prep",})


def extract_verb_triples_enhanced(
    text: str,
    lang: str = "en",
    entity_set: set[str] | None = None,
) -> list[VerbTriple]:
    """
    Enhanced verb-centered triple extraction.

    Cải tiến so với bản basic:
    - Compound expansion cho cả subject và object: "Pham Nhat Vuong" thay vì "Vuong"
    - Xử lý passive voice: "BigC was acquired by Vingroup" → (Vingroup, acquire, BigC)
    - Prepositional objects: "invested in company X" → (subject, invest, company X)
    - NER label matching: tag subject/object nếu nó match entity đã biết
    - Confidence score cho mỗi triple
    """
    nlp = get_spacy_model(lang)
    if nlp is None:
        return []

    doc = nlp(text[:100_000])

    # Build entity lookup from NER results
    ent_lookup: dict[str, str] = {}
    for ent in doc.ents:
        if ent.label_ in _RELEVANT_LABELS:
            ent_lookup[ent.text.strip().lower()] = ent.label_
    if entity_set:
        for e in entity_set:
            if e.lower() not in ent_lookup:
                ent_lookup[e.lower()] = "UNKNOWN"

    triples: list[VerbTriple] = []
    for sent in doc.sents:
        sent_triples = _extract_triples_from_sent(sent, ent_lookup)
        triples.extend(sent_triples)

    return triples


def _expand_span(token) -> str:
    """Expand token to include compounds, flat, and appos children."""
    parts: list[tuple[int, str]] = []
    for child in token.children:
        if child.dep_ in ("compound", "flat", "flat:name", "amod"):
            parts.append((child.i, child.text))
            # Also check grandchildren compounds
            for gc in child.children:
                if gc.dep_ == "compound":
                    parts.append((gc.i, gc.text))
    parts.append((token.i, token.text))
    parts.sort(key=lambda x: x[0])
    return " ".join(p[1] for p in parts)


def _get_prep_objects(token) -> list[str]:
    """Get prepositional phrase objects: 'invested in X' → ['X']."""
    results = []
    for child in token.children:
        if child.dep_ == "prep":
            for pobj in child.children:
                if pobj.dep_ == "pobj":
                    results.append(_expand_span(pobj))
    return results


def _extract_triples_from_sent(sent, ent_lookup: dict[str, str]) -> list[VerbTriple]:
    """Extract all verb-centered triples from a single sentence."""
    triples: list[VerbTriple] = []

    for token in sent:
        if token.pos_ != "VERB":
            continue

        is_passive = any(child.dep_ == "nsubjpass" for child in token.children)

        # Collect subjects
        raw_subjects = []
        for child in token.children:
            if child.dep_ in _SUBJ_DEPS:
                expanded = _expand_span(child)
                raw_subjects.append(expanded)
                # Check for conjunct subjects: "A and B acquired"
                for conj in child.children:
                    if conj.dep_ == "conj":
                        raw_subjects.append(_expand_span(conj))

        # Collect direct objects
        raw_objects = []
        for child in token.children:
            if child.dep_ in _OBJ_DEPS:
                expanded = _expand_span(child)
                raw_objects.append(expanded)
                for conj in child.children:
                    if conj.dep_ == "conj":
                        raw_objects.append(_expand_span(conj))

        # Collect prepositional objects
        prep_objects = _get_prep_objects(token)

        # Collect agent in passive ("acquired by Vingroup")
        agents = []
        for child in token.children:
            if child.dep_ == "agent":
                for pobj in child.children:
                    if pobj.dep_ == "pobj":
                        agents.append(_expand_span(pobj))

        # Handle passive voice transformation
        if is_passive and agents:
            # Swap: passive subject → object, agent → subject
            effective_subjects = agents
            effective_objects = raw_subjects + raw_objects
        else:
            effective_subjects = raw_subjects
            effective_objects = raw_objects + prep_objects

        if not effective_subjects or not effective_objects:
            continue

        for subj in effective_subjects:
            for obj in effective_objects:
                if subj.lower() == obj.lower():
                    continue

                subj_label = _lookup_entity_label(subj, ent_lookup)
                obj_label = _lookup_entity_label(obj, ent_lookup)

                confidence = _compute_triple_confidence(
                    subj, obj, subj_label, obj_label, token
                )

                triples.append(VerbTriple(
                    subject=subj,
                    verb=token.text,
                    verb_lemma=token.lemma_,
                    object=obj,
                    sentence=sent.text.strip(),
                    subject_label=subj_label,
                    object_label=obj_label,
                    confidence=confidence,
                ))

    return triples


def _lookup_entity_label(text: str, ent_lookup: dict[str, str]) -> str:
    """Tìm NER label cho text, hỗ trợ partial match."""
    lower = text.strip().lower()
    if lower in ent_lookup:
        return ent_lookup[lower]
    # Partial: "Vingroup JSC" matches "Vingroup"
    for key, label in ent_lookup.items():
        if key in lower or lower in key:
            return label
    return ""


def _compute_triple_confidence(
    subj: str, obj: str, subj_label: str, obj_label: str, verb_token
) -> float:
    """
    Confidence cho triple:
      - Cả subject và object là named entity → 0.4
      - Verb là ROOT của câu → +0.2
      - Subject/Object dài (compound) → +0.1 mỗi cái
      - Có NER label cụ thể (ORG, PERSON) → +0.1
    """
    score = 0.2  # base

    # Both are known entities
    if subj_label and obj_label:
        score += 0.3
    elif subj_label or obj_label:
        score += 0.15

    # Verb is ROOT of sentence
    if verb_token.dep_ == "ROOT":
        score += 0.2

    # Entity quality bonus
    if subj_label in ("ORG", "PERSON"):
        score += 0.1
    if obj_label in ("ORG", "PERSON"):
        score += 0.1

    # Length bonus (compound entities are more specific)
    if " " in subj:
        score += 0.05
    if " " in obj:
        score += 0.05

    return min(1.0, score)


# ─── Convenience functions ────────────────────────────────────────────────────

def extract_all(
    text: str,
    title: str = "",
    lang: str = "en",
    min_entity_confidence: float = 0.0,
    min_triple_confidence: float = 0.0,
) -> dict:
    """
    One-shot extraction: entities + triples từ một bài báo.

    Returns dict with keys: entities, triples, stats
    """
    entities = extract_entities_enhanced(
        text, title=title, lang=lang, min_confidence=min_entity_confidence,
    )

    entity_names = {e.canonical.lower() for e in entities}
    triples = extract_verb_triples_enhanced(
        text, lang=lang, entity_set=entity_names,
    )

    if min_triple_confidence > 0:
        triples = [t for t in triples if t.confidence >= min_triple_confidence]

    return {
        "entities": [e.to_dict() for e in entities],
        "triples": [t.to_dict() for t in triples],
        "stats": {
            "total_entities": len(entities),
            "orgs": sum(1 for e in entities if e.label == "ORG"),
            "persons": sum(1 for e in entities if e.label == "PERSON"),
            "locations": sum(1 for e in entities if e.label == "GPE"),
            "total_triples": len(triples),
            "high_confidence_triples": sum(1 for t in triples if t.confidence >= 0.5),
        },
    }

"""AI API routes — LLM Q&A, NL→Cypher, Graph Embedding."""
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from ai.llm_integration import EnterpriseNetworkLLM
from ai.graph_embedding import GraphEmbedding
import json
import os

router = APIRouter()


def _load_cached_ai_settings() -> None:
    """Load persisted AI settings so providers remain available after service restart."""
    from config.settings import settings

    cache_file = "config/ai_keys_cache.json"
    if not os.path.exists(cache_file):
        return

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
    except Exception:
        return

    if cache_data.get("GEMINI_API_KEY"):
        settings.gemini_api_key = cache_data["GEMINI_API_KEY"]
    if cache_data.get("GEMINI_MODEL"):
        settings.gemini_model = cache_data["GEMINI_MODEL"]
    if cache_data.get("GROQ_API_KEY"):
        settings.groq_api_key = cache_data["GROQ_API_KEY"]
    if cache_data.get("GROQ_MODEL"):
        settings.groq_model = cache_data["GROQ_MODEL"]
    if cache_data.get("OPENROUTER_API_KEY"):
        settings.openrouter_api_key = cache_data["OPENROUTER_API_KEY"]
    if cache_data.get("OPENROUTER_MODEL"):
        settings.openrouter_model = cache_data["OPENROUTER_MODEL"]
    if cache_data.get("OPENAI_API_KEY"):
        settings.openai_api_key = cache_data["OPENAI_API_KEY"]
    if cache_data.get("OPENAI_MODEL"):
        settings.openai_model = cache_data["OPENAI_MODEL"]


_load_cached_ai_settings()
_llm = EnterpriseNetworkLLM()
_embedding: GraphEmbedding | None = None


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


def _validate_groq_key(api_key: str, model: str) -> tuple[bool, str | None]:
    """Best-effort Groq key validation for clearer settings feedback."""
    if not api_key:
        return False, "Groq API key is empty"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1", timeout=8.0)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
        return True, None
    except Exception as e:
        return False, str(e)


def _get_embedding() -> GraphEmbedding:
    global _embedding
    if _embedding is None:
        _embedding = GraphEmbedding()
    return _embedding


class AskRequest(BaseModel):
    question: str
    company_id: str | None = None
    page_context: str | None = None

class AISettingsRequest(BaseModel):
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    groq_api_key: str | None = None
    groq_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None

@router.post("/settings")
def update_ai_settings(req: AISettingsRequest):
    from config.settings import settings
    
    cache_file = "config/ai_keys_cache.json"
    cache_data = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
        except Exception:
            pass

    gemini_api_key = _normalize_text(req.gemini_api_key)
    gemini_model = _normalize_text(req.gemini_model)
    groq_api_key = _normalize_text(req.groq_api_key)
    groq_model = _normalize_text(req.groq_model)
    openrouter_api_key = _normalize_text(req.openrouter_api_key)
    openrouter_model = _normalize_text(req.openrouter_model)
    openai_api_key = _normalize_text(req.openai_api_key)
    openai_model = _normalize_text(req.openai_model)

    if gemini_api_key is not None:
        settings.gemini_api_key = gemini_api_key
        cache_data["GEMINI_API_KEY"] = gemini_api_key
    if gemini_model is not None:
        settings.gemini_model = gemini_model
        cache_data["GEMINI_MODEL"] = gemini_model
    if groq_api_key is not None:
        settings.groq_api_key = groq_api_key
        cache_data["GROQ_API_KEY"] = groq_api_key
    if groq_model is not None:
        settings.groq_model = groq_model
        cache_data["GROQ_MODEL"] = groq_model
    if openrouter_api_key is not None:
        settings.openrouter_api_key = openrouter_api_key
        cache_data["OPENROUTER_API_KEY"] = openrouter_api_key
    if openrouter_model is not None:
        settings.openrouter_model = openrouter_model
        cache_data["OPENROUTER_MODEL"] = openrouter_model
    if openai_api_key is not None:
        settings.openai_api_key = openai_api_key
        cache_data["OPENAI_API_KEY"] = openai_api_key
    if openai_model is not None:
        settings.openai_model = openai_model
        cache_data["OPENAI_MODEL"] = openai_model
        
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
    except Exception:
        pass
        
    global _llm
    _llm = EnterpriseNetworkLLM()

    providers = {
        "gemini": bool(settings.gemini_api_key),
        "groq": bool(settings.groq_api_key),
        "openrouter": bool(settings.openrouter_api_key),
        "openai": bool(settings.openai_api_key),
        "ollama": True,
    }

    groq_validation = {"ok": False, "error": None}
    if settings.groq_api_key:
        ok, err = _validate_groq_key(settings.groq_api_key, settings.groq_model)
        groq_validation = {"ok": ok, "error": err}

    return {
        "status": "ok",
        "message": "AI settings updated and LLM re-initialized.",
        "providers": providers,
        "groq_validation": groq_validation,
    }


class NLCypherRequest(BaseModel):
    natural_language: str


class ExecuteCypherRequest(BaseModel):
    cypher: str


class SimilarRequest(BaseModel):
    node_id: str
    top_n: int = 10


class InvestigationReportRequest(BaseModel):
    entity_name: str
    entity_id: str | None = None
    alert_type: str
    evidence: str | None = None
    with_signals: bool = False
    subgraph_nodes: int | None = None
    subgraph_links: int | None = None
    blast_impacted_nodes: int | None = None
    blast_high_risk_hits: int | None = None
    risk_path_hops: int | None = None
    risk_path_target: str | None = None


@router.post("/ask")
def ask(req: AskRequest):
    """Hỏi đáp tự nhiên về mạng lưới doanh nghiệp bằng AI."""
    answer = _llm.ask(req.question, company_id=req.company_id, page_context=req.page_context)
    return {"question": req.question, "answer": answer}


@router.post("/natural-to-cypher")
def natural_to_cypher(req: NLCypherRequest):
    """Chuyển câu hỏi tự nhiên thành Cypher query."""
    cypher = _llm.ask_cypher(req.natural_language)
    return {"natural_language": req.natural_language, "cypher": cypher}


@router.post("/execute-cypher")
def execute_cypher(req: ExecuteCypherRequest):
    """Thực thi Cypher query trực tiếp và trả về kết quả."""
    from config.neo4j_config import Neo4jConnection
    try:
        with Neo4jConnection.session() as s:
            results = [dict(r) for r in s.run(req.cypher)]
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(400, f"Cypher execution failed: {e}")


@router.post("/similar")
def find_similar(req: SimilarRequest):
    """Tìm node tương tự dựa trên graph embedding."""
    emb = _get_embedding()
    similar = emb.find_similar(req.node_id, req.top_n)
    return [{"node_id": node_id, "similarity": round(score, 4)} for node_id, score in similar]


@router.get("/anomaly/{node_id}")
def anomaly_score(node_id: str):
    """Tính điểm bất thường của node dựa trên khoảng cách embedding."""
    emb = _get_embedding()
    score = emb.anomaly_score(node_id)
    return {"node_id": node_id, "anomaly_score": score}


@router.post("/train-embedding")
def train_embedding():
    """Kích hoạt huấn luyện lại graph embedding (Node2Vec)."""
    emb = _get_embedding()
    emb.train()
    return {"status": "training_complete"}


@router.post("/investigation/report")
def generate_investigation_report(req: InvestigationReportRequest):
    """Sinh báo cáo điều tra ngắn gọn dựa trên context, tùy chọn kèm graph signals."""
    subgraph_nodes = req.subgraph_nodes
    subgraph_links = req.subgraph_links
    blast_impacted_nodes = req.blast_impacted_nodes
    blast_high_risk_hits = req.blast_high_risk_hits
    risk_path_hops = req.risk_path_hops
    risk_path_target = req.risk_path_target

    if req.with_signals and (
        subgraph_nodes is None
        or subgraph_links is None
        or blast_impacted_nodes is None
        or blast_high_risk_hits is None
        or risk_path_hops is None
        or risk_path_target is None
    ):
        # Fetch expensive graph analytics only when explicitly requested.
        from graph.graph_queries import GraphQueries

        subgraph = GraphQueries.get_investigation_subgraph(
            entity_name=req.entity_name,
            entity_id=req.entity_id,
            alert_type=req.alert_type,
            max_hops=2,
            limit=120,
        )
        risk_path = GraphQueries.get_shortest_path_to_risk(
            entity_name=req.entity_name,
            entity_id=req.entity_id,
            max_depth=6,
        )
        blast = GraphQueries.get_blast_radius(
            entity_name=req.entity_name,
            entity_id=req.entity_id,
            depth=2,
        )

        subgraph_nodes = len(subgraph.get('nodes', []))
        subgraph_links = len(subgraph.get('links', []))
        blast_impacted_nodes = blast.get('impacted_nodes', 0)
        blast_high_risk_hits = blast.get('high_risk_hits', 0)
        risk_path_hops = risk_path.get('hops')
        risk_path_target = risk_path.get('target')

    if subgraph_nodes is None:
        subgraph_nodes = 0
    if subgraph_links is None:
        subgraph_links = 0
    if blast_impacted_nodes is None:
        blast_impacted_nodes = 0
    if blast_high_risk_hits is None:
        blast_high_risk_hits = 0

    context = (
        f"Entity: {req.entity_name}\n"
        f"Alert type: {req.alert_type}\n"
        f"Evidence: {req.evidence or 'n/a'}\n"
        f"Subgraph nodes: {subgraph_nodes}, links: {subgraph_links}\n"
        f"Blast radius impacted nodes: {blast_impacted_nodes}, high risk hits: {blast_high_risk_hits}\n"
        f"Risk path hops: {risk_path_hops} to {risk_path_target}\n"
    )

    question = (
        "Write a concise investigation brief in 3-5 bullet points. "
        "Focus on risk propagation, suspicious connectivity, and immediate next checks. "
        "Be factual and avoid speculation."
    )

    try:
        answer = _llm.ask(question=question, page_context=context)
    except Exception:
        fallback = [
            f"- {req.entity_name} triggered {req.alert_type} and should be triaged immediately.",
            f"- Local subgraph includes {subgraph_nodes} nodes and {subgraph_links} links.",
            f"- Blast radius touches {blast_impacted_nodes} entities with {blast_high_risk_hits} high-risk hits.",
        ]
        if risk_path_hops is not None:
            fallback.append(
                f"- Shortest risk path reaches {risk_path_target} in {risk_path_hops} hops."
            )
        answer = "\n".join(fallback)

    return {
        "entity_name": req.entity_name,
        "alert_type": req.alert_type,
        "report": answer,
        "signals": {
            "subgraph_nodes": subgraph_nodes,
            "subgraph_links": subgraph_links,
            "blast_radius": {
                "source": req.entity_name,
                "impacted_nodes": blast_impacted_nodes,
                "high_risk_hits": blast_high_risk_hits,
            },
            "shortest_risk_path": {
                "start": req.entity_name,
                "target": risk_path_target,
                "hops": risk_path_hops,
            },
        },
    }

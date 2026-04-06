"""AI API routes — LLM Q&A, NL→Cypher, Graph Embedding."""
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from ai.llm_integration import EnterpriseNetworkLLM
from ai.graph_embedding import GraphEmbedding

router = APIRouter()
_llm = EnterpriseNetworkLLM()
_embedding: GraphEmbedding | None = None


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
    openai_api_key: str | None = None
    openai_model: str | None = None

@router.post("/settings")
def update_ai_settings(req: AISettingsRequest):
    from config.settings import settings
    import os
    import json
    
    cache_file = "config/ai_keys_cache.json"
    cache_data = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
        except Exception:
            pass

    if req.gemini_api_key is not None:
        settings.gemini_api_key = req.gemini_api_key
        cache_data["GEMINI_API_KEY"] = req.gemini_api_key
    if req.gemini_model is not None:
        settings.gemini_model = req.gemini_model
        cache_data["GEMINI_MODEL"] = req.gemini_model
    if req.groq_api_key is not None:
        settings.groq_api_key = req.groq_api_key
        cache_data["GROQ_API_KEY"] = req.groq_api_key
    if req.groq_model is not None:
        settings.groq_model = req.groq_model
        cache_data["GROQ_MODEL"] = req.groq_model
    if req.openai_api_key is not None:
        settings.openai_api_key = req.openai_api_key
        cache_data["OPENAI_API_KEY"] = req.openai_api_key
    if req.openai_model is not None:
        settings.openai_model = req.openai_model
        cache_data["OPENAI_MODEL"] = req.openai_model
        
    try:
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
    except Exception:
        pass
        
    global _llm
    _llm = EnterpriseNetworkLLM()
    return {"status": "ok", "message": "AI settings updated and LLM re-initialized."}


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
    """Sinh báo cáo điều tra ngắn gọn dựa trên graph signals + LLM."""
    from graph.graph_queries import GraphQueries

    subgraph = GraphQueries.get_investigation_subgraph(
        entity_name=req.entity_name,
        entity_id=req.entity_id,
        alert_type=req.alert_type,
        max_hops=2,
        limit=120,
    )
    risk_path = GraphQueries.get_shortest_path_to_risk(entity_name=req.entity_name, entity_id=req.entity_id, max_depth=6)
    blast = GraphQueries.get_blast_radius(entity_name=req.entity_name, entity_id=req.entity_id, depth=2)

    context = (
        f"Entity: {req.entity_name}\n"
        f"Alert type: {req.alert_type}\n"
        f"Evidence: {req.evidence or 'n/a'}\n"
        f"Subgraph nodes: {len(subgraph.get('nodes', []))}, links: {len(subgraph.get('links', []))}\n"
        f"Blast radius impacted nodes: {blast.get('impacted_nodes', 0)}, high risk hits: {blast.get('high_risk_hits', 0)}\n"
        f"Risk path hops: {risk_path.get('hops')} to {risk_path.get('target')}\n"
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
            f"- Local subgraph includes {len(subgraph.get('nodes', []))} nodes and {len(subgraph.get('links', []))} links.",
            f"- Blast radius touches {blast.get('impacted_nodes', 0)} entities with {blast.get('high_risk_hits', 0)} high-risk hits.",
        ]
        if risk_path.get("hops") is not None:
            fallback.append(
                f"- Shortest risk path reaches {risk_path.get('target')} in {risk_path.get('hops')} hops."
            )
        answer = "\n".join(fallback)

    return {
        "entity_name": req.entity_name,
        "alert_type": req.alert_type,
        "report": answer,
        "signals": {
            "subgraph_nodes": len(subgraph.get("nodes", [])),
            "subgraph_links": len(subgraph.get("links", [])),
            "blast_radius": blast,
            "shortest_risk_path": risk_path,
        },
    }

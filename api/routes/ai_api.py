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


class NLCypherRequest(BaseModel):
    natural_language: str


class ExecuteCypherRequest(BaseModel):
    cypher: str


class SimilarRequest(BaseModel):
    node_id: str
    top_n: int = 10


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

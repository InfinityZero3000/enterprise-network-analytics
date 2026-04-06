"""Analytics API routes — fraud, risk, ownership."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from loguru import logger
from analytics.fraud_detection.rule_based import RuleBasedFraudDetector
from analytics.risk.risk_scoring import RiskScoringEngine
from analytics.ownership.cross_ownership import OwnershipAnalyzer
from config.neo4j_config import Neo4jConnection

router = APIRouter()

_fraud = RuleBasedFraudDetector()
_risk = RiskScoringEngine()
_ownership = OwnershipAnalyzer()
_cases_store: dict[str, dict] = {}


def _load_snapshots_for_case(case_id: str) -> list[dict]:
    cypher = """
    MATCH (c:InvestigationCase {case_id:$case_id})-[:HAS_SNAPSHOT]->(s:InvestigationSnapshot)
    RETURN {
      snapshot_id: s.snapshot_id,
      note: s.note,
      graph_node_count: coalesce(s.graph_node_count, 0),
      graph_link_count: coalesce(s.graph_link_count, 0),
            image_data_url: s.image_data_url,
      created_at: s.created_at
    } AS snapshot
    ORDER BY s.created_at DESC
    """
    with Neo4jConnection.session() as s:
        return [dict(r["snapshot"]) for r in s.run(cypher, case_id=case_id)]


def _create_case_in_neo4j(case_payload: dict) -> dict:
    cypher = """
    MERGE (c:InvestigationCase {case_id:$case_id})
    SET c.entity_id = $entity_id,
        c.entity_name = $entity_name,
        c.alert_type = $alert_type,
        c.status = $status,
        c.note = $note,
        c.created_at = $created_at,
        c.updated_at = $updated_at
    RETURN {
      case_id: c.case_id,
      entity_id: c.entity_id,
      entity_name: c.entity_name,
      alert_type: c.alert_type,
      status: c.status,
      note: c.note,
      created_at: c.created_at,
      updated_at: c.updated_at,
      snapshots: []
    } AS case_data
    """
    with Neo4jConnection.session() as s:
        record = s.run(cypher, **case_payload).single()
        return dict(record["case_data"]) if record else {**case_payload, "snapshots": []}


def _list_cases_from_neo4j(status: str | None, limit: int) -> list[dict]:
    cypher = """
    MATCH (c:InvestigationCase)
    WHERE $status IS NULL OR c.status = $status
    RETURN {
      case_id: c.case_id,
      entity_id: c.entity_id,
      entity_name: c.entity_name,
      alert_type: c.alert_type,
      status: c.status,
      note: coalesce(c.note, ''),
      created_at: c.created_at,
      updated_at: c.updated_at
    } AS case_data
    ORDER BY c.updated_at DESC
    LIMIT $limit
    """
    with Neo4jConnection.session() as s:
        rows = [dict(r["case_data"]) for r in s.run(cypher, status=status, limit=limit)]
    for row in rows:
        row["snapshots"] = _load_snapshots_for_case(row["case_id"])
    return rows


def _update_case_status_in_neo4j(case_id: str, status: str, updated_at: str) -> dict | None:
    cypher = """
    MATCH (c:InvestigationCase {case_id:$case_id})
    SET c.status = $status,
        c.updated_at = $updated_at
    RETURN {
      case_id: c.case_id,
      entity_id: c.entity_id,
      entity_name: c.entity_name,
      alert_type: c.alert_type,
      status: c.status,
      note: coalesce(c.note, ''),
      created_at: c.created_at,
      updated_at: c.updated_at
    } AS case_data
    """
    with Neo4jConnection.session() as s:
        record = s.run(cypher, case_id=case_id, status=status, updated_at=updated_at).single()
    if not record:
        return None
    case_data = dict(record["case_data"])
    case_data["snapshots"] = _load_snapshots_for_case(case_id)
    return case_data


def _add_snapshot_to_neo4j(case_id: str, snapshot: dict) -> dict | None:
    cypher = """
    MATCH (c:InvestigationCase {case_id:$case_id})
    CREATE (s:InvestigationSnapshot {
      snapshot_id: $snapshot_id,
      note: $note,
      graph_node_count: $graph_node_count,
      graph_link_count: $graph_link_count,
            image_data_url: $image_data_url,
      created_at: $created_at
    })
    MERGE (c)-[:HAS_SNAPSHOT]->(s)
    SET c.updated_at = $created_at
    RETURN c.case_id AS case_id
    """
    with Neo4jConnection.session() as s:
        record = s.run(cypher, case_id=case_id, **snapshot).single()
        return dict(record) if record else None


class CaseCreateRequest(BaseModel):
    entity_id: str
    entity_name: str
    alert_type: str
    note: str | None = None


class CaseStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(NEW|INVESTIGATING|FALSE_POSITIVE|CONFIRMED_FRAUD)$")


class CaseSnapshotRequest(BaseModel):
    note: str = Field(min_length=2, max_length=2000)
    graph_node_count: int = Field(default=0, ge=0)
    graph_link_count: int = Field(default=0, ge=0)
    image_data_url: str | None = Field(default=None, max_length=2_000_000)


@router.get("/stats")
def get_global_stats():
    """Lấy tổng số node và relationship từ Neo4j."""
    from graph.graph_queries import GraphQueries
    return GraphQueries.get_global_stats()


@router.get("/fraud/alerts")
def get_fraud_alerts(limit: int = Query(default=100, ge=1, le=500)):
    """Chạy tất cả rule-based fraud detection và trả về alerts."""
    alerts = _fraud.run_all_rules()
    return [
        {
            "entity_id": a.entity_id,
            "entity_name": a.entity_name,
            "alert_type": a.alert_type,
            "level": a.level.value,
            "score": a.score,
            "description": a.description,
            "evidence": a.evidence,
        }
        for a in alerts[:limit]
    ]


@router.get("/risk/{company_id}")
def get_risk_profile(company_id: str):
    """Chấm điểm rủi ro cho một doanh nghiệp."""
    profile = _risk.score_company(company_id)
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(404, f"Company not found: {company_id}")
    return {
        "company_id": profile.company_id,
        "company_name": profile.company_name,
        "total_score": profile.total_score,
        "risk_level": profile.risk_level,
        "breakdown": {
            "topology": profile.topology_score,
            "ownership": profile.ownership_score,
            "fraud_signal": profile.fraud_signal_score,
            "pep_exposure": profile.pep_exposure_score,
            "activity": profile.activity_score,
        },
        "flags": profile.flags,
        "detail": profile.detail,
    }


@router.get("/ownership/ubo/{company_id}")
def get_ubo(
    company_id: str,
    min_pct: float = Query(default=5.0, ge=0.1, le=100.0),
):
    """Tìm Ultimate Beneficial Owner (UBO) của doanh nghiệp."""
    from config.neo4j_config import Neo4jConnection
    cypher = """
    MATCH path = (p:Person)-[:RELATIONSHIP*1..6 {rel_type:'SHAREHOLDER'}]->(c:Company {company_id:$cid})
    WITH p, c, length(path) AS depth,
         reduce(pct=1.0, r IN relationships(path) | pct * coalesce(r.ownership_pct,0)/100.0) AS eff_pct
    WHERE eff_pct * 100 >= $min_pct
    RETURN p.person_id AS ubo_id, p.full_name AS ubo_name,
           round(eff_pct*100,2) AS ownership_pct, depth
    ORDER BY ownership_pct DESC
    """
    with Neo4jConnection.session() as s:
        return [dict(r) for r in s.run(cypher, cid=company_id, min_pct=min_pct)]


@router.get("/ownership/cross")
def get_cross_ownership():
    """Phát hiện cặp công ty sở hữu chéo lẫn nhau."""
    pairs = _ownership.detect_cross_ownership()
    return [
        {
            "company_a": {"id": p.company_a_id, "name": p.company_a_name},
            "company_b": {"id": p.company_b_id, "name": p.company_b_name},
            "mutual": p.mutual,
        }
        for p in pairs
    ]


@router.get("/ownership/concentration")
def get_ownership_concentration(limit: int = Query(default=100, ge=1, le=500)):
    """Báo cáo tập trung vốn sở hữu."""
    return _ownership.ownership_concentration_report()[:limit]


@router.post("/cases")
def create_case(req: CaseCreateRequest):
    """Tạo case điều tra từ một alert."""
    now = datetime.now(timezone.utc).isoformat()
    case_id = f"CASE-{uuid4().hex[:10].upper()}"
    case = {
        "case_id": case_id,
        "entity_id": req.entity_id,
        "entity_name": req.entity_name,
        "alert_type": req.alert_type,
        "status": "NEW",
        "note": req.note or "",
        "created_at": now,
        "updated_at": now,
        "snapshots": [],
    }
    try:
        return _create_case_in_neo4j(case)
    except Exception as e:
        logger.warning(f"Falling back to in-memory case store (create_case): {e}")
        _cases_store[case_id] = case
        return case


@router.get("/cases")
def list_cases(
    status: str | None = Query(default=None, pattern="^(NEW|INVESTIGATING|FALSE_POSITIVE|CONFIRMED_FRAUD)$"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """Danh sách case điều tra."""
    try:
        return _list_cases_from_neo4j(status=status, limit=limit)
    except Exception as e:
        logger.warning(f"Falling back to in-memory case store (list_cases): {e}")
        values = list(_cases_store.values())
        if status:
            values = [c for c in values if c["status"] == status]
        values.sort(key=lambda c: c["updated_at"], reverse=True)
        return values[:limit]


@router.patch("/cases/{case_id}/status")
def update_case_status(case_id: str, req: CaseStatusUpdateRequest):
    """Cập nhật workflow status cho case."""
    from fastapi import HTTPException

    updated_at = datetime.now(timezone.utc).isoformat()
    try:
        case = _update_case_status_in_neo4j(case_id=case_id, status=req.status, updated_at=updated_at)
        if not case:
            raise HTTPException(404, f"Case not found: {case_id}")
        return case
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Falling back to in-memory case store (update_case_status): {e}")
        case = _cases_store.get(case_id)
        if not case:
            raise HTTPException(404, f"Case not found: {case_id}")
        case["status"] = req.status
        case["updated_at"] = updated_at
        return case


@router.post("/cases/{case_id}/snapshots")
def add_case_snapshot(case_id: str, req: CaseSnapshotRequest):
    """Lưu snapshot ghi chú điều tra cho case."""
    from fastapi import HTTPException

    snapshot = {
        "snapshot_id": uuid4().hex,
        "note": req.note,
        "graph_node_count": req.graph_node_count,
        "graph_link_count": req.graph_link_count,
        "image_data_url": req.image_data_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        created = _add_snapshot_to_neo4j(case_id=case_id, snapshot=snapshot)
        if not created:
            raise HTTPException(404, f"Case not found: {case_id}")
        snapshots = _load_snapshots_for_case(case_id)
        return {"case_id": case_id, "snapshot": snapshot, "snapshot_count": len(snapshots)}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Falling back to in-memory case store (add_case_snapshot): {e}")
        case = _cases_store.get(case_id)
        if not case:
            raise HTTPException(404, f"Case not found: {case_id}")
        case["snapshots"].append(snapshot)
        case["updated_at"] = snapshot["created_at"]
        return {"case_id": case_id, "snapshot": snapshot, "snapshot_count": len(case["snapshots"])}

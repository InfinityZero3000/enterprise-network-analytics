"""Analytics API routes — fraud, risk, ownership."""
from fastapi import APIRouter, Query
from analytics.fraud_detection.rule_based import RuleBasedFraudDetector
from analytics.risk.risk_scoring import RiskScoringEngine
from analytics.ownership.cross_ownership import OwnershipAnalyzer

router = APIRouter()

_fraud = RuleBasedFraudDetector()
_risk = RiskScoringEngine()
_ownership = OwnershipAnalyzer()


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

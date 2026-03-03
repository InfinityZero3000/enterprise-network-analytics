"""
Risk Scoring Engine — chấm điểm rủi ro doanh nghiệp đa chiều
"""
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger
from config.neo4j_config import Neo4jConnection


@dataclass
class RiskProfile:
    company_id: str
    company_name: str
    total_score: float                  # 0–100
    risk_level: str                     # low / medium / high / critical
    topology_score: float = 0.0
    ownership_score: float = 0.0
    fraud_signal_score: float = 0.0
    pep_exposure_score: float = 0.0
    activity_score: float = 0.0
    flags: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


WEIGHTS = {
    "topology": 0.15,
    "ownership": 0.20,
    "fraud_signal": 0.35,
    "pep_exposure": 0.25,
    "activity": 0.05,
}


def _risk_level(score: float) -> str:
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    if score < 75:
        return "high"
    return "critical"


class RiskScoringEngine:

    # ------------------------------------------------------------------ #
    # Raw metric queries
    # ------------------------------------------------------------------ #

    _TOPOLOGY_Q = """
    MATCH (c:Company {company_id: $cid})
    OPTIONAL MATCH (c)-[:RELATIONSHIP]-(n)
    WITH c, COUNT(n) AS degree
    OPTIONAL MATCH path = (c)-[:RELATIONSHIP*2..4]->(c)
    RETURN degree, COUNT(path) AS cycle_count,
           coalesce(c.pagerank, 0) AS pagerank,
           coalesce(c.betweenness, 0) AS betweenness
    """

    _OWNERSHIP_Q = """
    MATCH (c:Company {company_id: $cid})
    OPTIONAL MATCH (sh)-[r:RELATIONSHIP {rel_type:'SHAREHOLDER'}]->(c)
    WITH c, COUNT(r) AS sh_count,
         MAX(coalesce(r.ownership_pct,0)) AS top_sh_pct
    OPTIONAL MATCH (c)-[:RELATIONSHIP {rel_type:'SHAREHOLDER'}]->(inv:Company)
    RETURN sh_count, top_sh_pct,
           COUNT(inv) AS investee_count,
           coalesce(c.charter_capital, 0) AS capital
    """

    _PEP_Q = """
    MATCH (c:Company {company_id: $cid})
    OPTIONAL MATCH (p:Person {is_pep:true})-[:RELATIONSHIP]->(c)
    OPTIONAL MATCH (p2:Person {is_sanctioned:true})-[:RELATIONSHIP]->(c)
    RETURN COUNT(DISTINCT p) AS pep_count, COUNT(DISTINCT p2) AS sanctioned_count
    """

    def score_company(self, company_id: str) -> Optional[RiskProfile]:
        try:
            with Neo4jConnection.session() as s:
                t = s.run(self._TOPOLOGY_Q, cid=company_id).single()
                o = s.run(self._OWNERSHIP_Q, cid=company_id).single()
                p = s.run(self._PEP_Q, cid=company_id).single()

                if not t:
                    return None

                # --- Topology ---
                degree = t["degree"] or 0
                cycle_count = t["cycle_count"] or 0
                topo_raw = min((degree / 50) * 40 + (cycle_count * 30), 100)
                topo_score = topo_raw

                # --- Ownership ---
                sh_count = o["sh_count"] or 0 if o else 0
                top_pct = o["top_sh_pct"] or 0 if o else 0
                capital = o["capital"] or 0 if o else 0
                investee = o["investee_count"] or 0 if o else 0
                own_raw = 0.0
                flags = []
                if capital < 100_000_000:
                    own_raw += 30; flags.append("low_capital")
                if top_pct > 90:
                    own_raw += 20; flags.append("concentrated_ownership")
                own_raw += min(investee / 10 * 20, 20)
                own_score = min(own_raw, 100)

                # --- Fraud signal ---
                fraud_q = """
                MATCH (c:Company {company_id: $cid})
                OPTIONAL MATCH (c)-[:RELATIONSHIP*2..6 {rel_type:'SHAREHOLDER'}]->(c)
                RETURN COUNT(*) AS circular
                """
                fr = s.run(fraud_q, cid=company_id).single()
                circular = fr["circular"] if fr else 0
                fraud_score = min(circular * 30, 100)
                if circular > 0:
                    flags.append("circular_ownership")

                # --- PEP exposure ---
                pep = p["pep_count"] if p else 0
                sanc = p["sanctioned_count"] if p else 0
                pep_score = min(pep * 20 + sanc * 50, 100)
                if pep > 0:
                    flags.append("pep_connection")
                if sanc > 0:
                    flags.append("sanctioned_connection")

                # --- Activity (placeholder) ---
                activity_score = 0.0

                total = (
                    topo_score * WEIGHTS["topology"] +
                    own_score * WEIGHTS["ownership"] +
                    fraud_score * WEIGHTS["fraud_signal"] +
                    pep_score * WEIGHTS["pep_exposure"] +
                    activity_score * WEIGHTS["activity"]
                )

                # Get name
                nq = s.run("MATCH (c:Company {company_id:$cid}) RETURN c.name AS n", cid=company_id).single()
                name = nq["n"] if nq else company_id

                return RiskProfile(
                    company_id=company_id, company_name=name,
                    total_score=round(total, 2),
                    risk_level=_risk_level(total),
                    topology_score=round(topo_score, 2),
                    ownership_score=round(own_score, 2),
                    fraud_signal_score=round(fraud_score, 2),
                    pep_exposure_score=round(pep_score, 2),
                    activity_score=round(activity_score, 2),
                    flags=flags,
                    detail={"degree": degree, "circular": circular, "pep": pep, "sanctioned": sanc},
                )
        except Exception as e:
            logger.error(f"Risk scoring failed for {company_id}: {e}")
            return None

    def batch_score_all(self, limit: int = 1000) -> list[RiskProfile]:
        cypher = "MATCH (c:Company) RETURN c.company_id AS cid LIMIT $lim"
        profiles: list[RiskProfile] = []
        with Neo4jConnection.session() as s:
            ids = [r["cid"] for r in s.run(cypher, lim=limit)]
        for cid in ids:
            p = self.score_company(cid)
            if p:
                profiles.append(p)
        logger.info(f"Batch risk scoring complete: {len(profiles)} companies")
        return profiles

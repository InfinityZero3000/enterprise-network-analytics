"""
Rule-Based Fraud Detection — phát hiện gian lận qua Cypher patterns
"""
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
from config.neo4j_config import Neo4jConnection


class AlertLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FraudAlert:
    entity_id: str
    entity_name: str
    entity_type: str
    alert_type: str
    level: AlertLevel
    score: float
    description: str
    evidence: dict = field(default_factory=dict)


class RuleBasedFraudDetector:

    SHELL_COMPANY_CYPHER = """
    MATCH (a:Address)<-[r:RELATIONSHIP]-(c:Company)
    WITH a, count(c) as companies_count
    WHERE companies_count > 100
    RETURN a.node_id AS entity_id, a.address AS name, 'Address' AS type,
           companies_count AS investee_count, 0 AS capital
    ORDER BY investee_count DESC LIMIT 5
    """

    CIRCULAR_OWNERSHIP_CYPHER = """
    MATCH path = (c:Company)-[:RELATIONSHIP*2..3]->(c)
    WITH c, length(path) AS cycle_len, [n IN nodes(path) | coalesce(n.name, n.node_id)] AS cycle
    RETURN c.node_id AS entity_id, coalesce(c.name, c.node_id) AS name, 'Company' AS type,
           cycle_len, cycle
    LIMIT 5
    """

    PEP_CONNECTION_CYPHER = """
    MATCH (p:Person)-[:RELATIONSHIP]->(c:Company)
    WITH p, count(c) as companies_count
    WHERE companies_count > 500
    RETURN p.node_id AS entity_id, coalesce(p.name, p.full_name) AS name, 'Person' AS type,
           p.node_id AS pep_id, coalesce(p.name, p.full_name) AS pep_name, companies_count
    LIMIT 5
    """

    SANCTIONED_CYPHER = """
    MATCH (p:Person)-[:RELATIONSHIP]->(c:Company)
    WHERE p.is_sanctioned = true OR p.name CONTAINS 'SANCTION' OR c.name CONTAINS 'SANCTION'
    RETURN c.node_id AS entity_id, coalesce(c.name, c.node_id) AS name, 'Company' AS type,
           p.node_id AS sanctioned_id, coalesce(p.name, p.full_name) AS sanctioned_name
    LIMIT 5
    """

    def run_all_rules(self) -> list[FraudAlert]:
        alerts: list[FraudAlert] = []

        with Neo4jConnection.session() as s:
            # Shell companies / Mass Registration
            for r in s.run(self.SHELL_COMPANY_CYPHER):
                alerts.append(FraudAlert(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["type"], alert_type="mass_registration",
                    level=AlertLevel.HIGH, score=0.75,
                    description=f"Địa chỉ bưu điện ảo có {r['investee_count']} công ty đăng ký.",
                    evidence={"companies_count": r["investee_count"]},
                ))

            # Circular ownership
            for r in s.run(self.CIRCULAR_OWNERSHIP_CYPHER):
                alerts.append(FraudAlert(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["type"], alert_type="circular_ownership",
                    level=AlertLevel.CRITICAL, score=0.90,
                    description=f"Sở hữu vòng tròn {r['cycle_len']} đỉnh.",
                    evidence={"cycle": r["cycle"], "depth": r["cycle_len"]},
                ))

            # PEP connections / Super Nodes
            for r in s.run(self.PEP_CONNECTION_CYPHER):
                alerts.append(FraudAlert(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["type"], alert_type="high_risk_officer",
                    level=AlertLevel.MEDIUM, score=0.50,
                    description=f"Thực thể siêu kết nối với {r['companies_count']} công ty.",
                    evidence={"pep_id": r["pep_id"]},
                ))

            # Sanctioned
            for r in s.run(self.SANCTIONED_CYPHER):
                alerts.append(FraudAlert(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["type"], alert_type="sanctioned_connection",
                    level=AlertLevel.CRITICAL, score=0.95,
                    description=f"Kết nối với cá nhân bị trừng phạt: {r['sanctioned_name']}.",
                    evidence={"sanctioned_id": r["sanctioned_id"]},
                ))

        logger.info(f"Fraud detection: {len(alerts)} alerts found.")
        return alerts

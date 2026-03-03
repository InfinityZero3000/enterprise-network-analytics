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
    MATCH (c:Company)
    WHERE c.status = 'active'
      AND c.charter_capital < 100000000
      AND (c.is_listed IS NULL OR c.is_listed = false)
      AND NOT EXISTS { MATCH (c)-[:RELATIONSHIP {rel_type:'SUPPLIER'}]->() }
    OPTIONAL MATCH (c)-[r:RELATIONSHIP {rel_type:'SHAREHOLDER'}]->(:Company)
    WITH c, COUNT(r) AS investee_count
    WHERE investee_count >= 3
    RETURN c.company_id AS entity_id, c.name AS name, 'Company' AS type,
           investee_count, c.charter_capital AS capital
    ORDER BY investee_count DESC LIMIT 200
    """

    CIRCULAR_OWNERSHIP_CYPHER = """
    MATCH path = (c:Company)-[:RELATIONSHIP*2..6 {rel_type:'SHAREHOLDER'}]->(c)
    WITH c, length(path) AS cycle_len, [n IN nodes(path) | n.name] AS cycle
    RETURN c.company_id AS entity_id, c.name AS name, 'Company' AS type,
           cycle_len, cycle
    LIMIT 100
    """

    PEP_CONNECTION_CYPHER = """
    MATCH (p:Person {is_pep: true})-[:RELATIONSHIP]->(c:Company)
    RETURN c.company_id AS entity_id, c.name AS name, 'Company' AS type,
           p.person_id AS pep_id, p.full_name AS pep_name
    """

    SANCTIONED_CYPHER = """
    MATCH (p:Person {is_sanctioned: true})-[:RELATIONSHIP]->(c:Company)
    RETURN c.company_id AS entity_id, c.name AS name, 'Company' AS type,
           p.person_id AS sanctioned_id, p.full_name AS sanctioned_name
    """

    def run_all_rules(self) -> list[FraudAlert]:
        alerts: list[FraudAlert] = []

        with Neo4jConnection.session() as s:
            # Shell companies
            for r in s.run(self.SHELL_COMPANY_CYPHER):
                alerts.append(FraudAlert(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["type"], alert_type="shell_company",
                    level=AlertLevel.HIGH, score=0.75,
                    description=f"Vốn thấp ({r['capital']:,.0f} VND) nhưng sở hữu {r['investee_count']} công ty.",
                    evidence={"investee_count": r["investee_count"], "capital": r["capital"]},
                ))

            # Circular ownership
            for r in s.run(self.CIRCULAR_OWNERSHIP_CYPHER):
                alerts.append(FraudAlert(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["type"], alert_type="circular_ownership",
                    level=AlertLevel.CRITICAL, score=0.90,
                    description=f"Sở hữu vòng tròn {r['cycle_len']} bước.",
                    evidence={"cycle": r["cycle"], "depth": r["cycle_len"]},
                ))

            # PEP connections
            for r in s.run(self.PEP_CONNECTION_CYPHER):
                alerts.append(FraudAlert(
                    entity_id=r["entity_id"], entity_name=r["name"],
                    entity_type=r["type"], alert_type="pep_connection",
                    level=AlertLevel.MEDIUM, score=0.50,
                    description=f"Kết nối với PEP: {r['pep_name']}.",
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

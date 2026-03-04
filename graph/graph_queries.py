"""
Cypher Query Wrappers — các truy vấn graph hay dùng
"""
from loguru import logger
from config.neo4j_config import Neo4jConnection


class GraphQueries:

    @staticmethod
    def get_ownership_chain(company_id: str, max_depth: int = 5) -> list[dict]:
        """Chuỗi sở hữu ngược (upstream)."""
        cypher = """
        MATCH path = (c:Company {company_id: $cid})<-[:RELATIONSHIP*1..$depth {rel_type: 'SHAREHOLDER'}]-(owner)
        RETURN
            [n IN nodes(path) | {id: COALESCE(n.company_id, n.person_id), name: n.name, type: labels(n)[0]}] AS chain,
            [r IN relationships(path) | {ownership: r.ownership_percent, tier: r.ownership_tier}] AS weights,
            length(path) AS depth
        ORDER BY depth
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, cid=company_id, depth=max_depth)]

    @staticmethod
    def find_common_shareholders(company_ids: list[str]) -> list[dict]:
        """Cổ đông chung của nhiều công ty."""
        cypher = """
        MATCH (owner)-[:RELATIONSHIP {rel_type: 'SHAREHOLDER'}]->(c:Company)
        WHERE c.company_id IN $ids
        WITH owner, COUNT(DISTINCT c) AS cnt, COLLECT(c.name) AS companies
        WHERE cnt >= 2
        RETURN COALESCE(owner.company_id, owner.person_id) AS owner_id,
               owner.name AS owner_name, labels(owner)[0] AS owner_type,
               cnt AS shared_count, companies
        ORDER BY cnt DESC
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, ids=company_ids)]

    @staticmethod
    def detect_circular_ownership(
        max_depth: int = 6,
        company_id: str | None = None,
    ) -> list[dict]:
        """Phát hiện sở hữu vòng tròn. Lọc theo company_id nếu được cung cấp."""
        if company_id:
            cypher = """
            MATCH path = (c:Company {company_id: $cid})-[:RELATIONSHIP*2..$max {rel_type: 'SHAREHOLDER'}]->(c)
            RETURN c.company_id AS company_id, c.name AS company_name,
                   length(path) AS cycle_length,
                   [n IN nodes(path) | n.name] AS cycle_path
            LIMIT 100
            """
            with Neo4jConnection.session() as s:
                return [dict(r) for r in s.run(cypher, cid=company_id, max=max_depth)]
        cypher = """
        MATCH path = (c:Company)-[:RELATIONSHIP*2..$max {rel_type: 'SHAREHOLDER'}]->(c)
        RETURN c.company_id AS company_id, c.name AS company_name,
               length(path) AS cycle_length,
               [n IN nodes(path) | n.name] AS cycle_path
        LIMIT 100
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, max=max_depth)]

    @staticmethod
    def get_supply_chain_path(from_id: str, to_id: str, max_depth: int = 4) -> list[dict]:
        """Đường đi ngắn nhất trong chuỗi cung ứng."""
        cypher = """
        MATCH path = shortestPath(
            (a:Company {company_id: $from_id})-[:RELATIONSHIP*1..$depth]->(b:Company {company_id: $to_id})
        )
        RETURN [n IN nodes(path) | n.name] AS path_names,
               [r IN relationships(path) | r.rel_type] AS edge_types,
               length(path) AS hops
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, from_id=from_id, to_id=to_id, depth=max_depth)]

    @staticmethod
    def get_company_network_stats(company_id: str) -> dict:
        """Tổng quan network của một công ty."""
        cypher = """
        MATCH (c:Company {company_id: $cid})
        OPTIONAL MATCH (c)<-[:RELATIONSHIP {rel_type: 'SHAREHOLDER'}]-(sh)
        OPTIONAL MATCH (c)-[:RELATIONSHIP {rel_type: 'SHAREHOLDER'}]->(inv)
        OPTIONAL MATCH (c)-[:RELATIONSHIP {rel_type: 'SUBSIDIARY'}]->(sub)
        OPTIONAL MATCH (c)-[:RELATIONSHIP]->(partner)
        RETURN c.name AS name, c.status AS status, c.risk_score AS risk_score,
               COUNT(DISTINCT sh)     AS shareholder_count,
               COUNT(DISTINCT inv)    AS investee_count,
               COUNT(DISTINCT sub)    AS subsidiary_count,
               COUNT(DISTINCT partner) AS total_connections
        """
        with Neo4jConnection.session() as s:
            result = s.run(cypher, cid=company_id).single()
            return dict(result) if result else {}

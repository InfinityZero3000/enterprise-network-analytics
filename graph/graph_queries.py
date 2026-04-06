"""
Cypher Query Wrappers — các truy vấn graph hay dùng
"""
from loguru import logger
from config.neo4j_config import Neo4jConnection


class GraphQueries:

    @staticmethod
    def get_global_stats() -> dict:
        """Thống kê tổng quan mạng lưới."""
        cypher = """
        MATCH (n) WITH count(n) AS total_nodes
        MATCH ()-[r]->() RETURN total_nodes, count(r) AS total_rels
        """
        with Neo4jConnection.session() as s:
            result = s.run(cypher).single()
            if result:
                return {"total_nodes": result["total_nodes"], "total_rels": result["total_rels"]}
            return {"total_nodes": 0, "total_rels": 0}

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

    @staticmethod
    def get_investigation_subgraph(
        entity_name: str,
        alert_type: str,
        entity_id: str | None = None,
        max_hops: int = 2,
        limit: int = 160,
    ) -> dict:
        """Lấy subgraph tập trung cho luồng điều tra theo thực thể cảnh báo."""
        rel_filter = {
            "CIRCULAR_OWNERSHIP": ["SHAREHOLDER", "SUBSIDIARY"],
            "SHELL_COMPANY": ["SHAREHOLDER", "REGISTERED_AT", "DIRECTOR"],
            "PEP_EXPOSURE": ["PEP_RELATED", "DIRECTOR", "SHAREHOLDER"],
        }
        rel_types = rel_filter.get(alert_type, ["SHAREHOLDER", "DIRECTOR", "RELATED_TO", "RELATIONSHIP"])

        safe_max_hops = max(1, min(int(max_hops), 6))

        cypher = """
        MATCH (start)
        WITH start,
             CASE
                WHEN $entity_id IS NOT NULL AND (
                    coalesce(start.node_id, '') = $entity_id
                    OR coalesce(start.company_id, '') = $entity_id
                    OR coalesce(start.person_id, '') = $entity_id
                ) THEN 2
                WHEN toLower(coalesce(start.name, start.full_name, start.address, '')) CONTAINS toLower($entity_name) THEN 1
                ELSE 0
             END AS match_score
        WHERE match_score > 0
        WITH start, match_score
        ORDER BY match_score DESC
        LIMIT 1
        WITH start
        OPTIONAL MATCH path = (start)-[:RELATIONSHIP*1..__MAX_HOPS__]-(neighbor)
           WITH start, [p IN collect(path) WHERE p IS NOT NULL] AS paths
        WITH paths,
             [start] + reduce(all_nodes = [], p IN paths | all_nodes + coalesce(nodes(p), [])) AS raw_nodes,
               reduce(all_rels = [], p IN paths | all_rels + coalesce(relationships(p), [])) AS raw_rels
        UNWIND raw_nodes AS n
        WITH collect(DISTINCT n)[0..$limit] AS nodes, raw_rels
           WITH nodes, [r IN raw_rels
                     WHERE startNode(r) IN nodes
                       AND endNode(r) IN nodes
                       AND coalesce(r.rel_type, type(r)) IN $rel_types] AS rels
        RETURN
            [n IN nodes | {
                id: coalesce(n.node_id, n.company_id, n.person_id, elementId(n)),
                name: coalesce(n.name, n.full_name, n.address, coalesce(n.node_id, n.company_id, n.person_id, elementId(n))),
                group: CASE
                    WHEN 'Company' IN labels(n) THEN 1
                    WHEN 'Person' IN labels(n) THEN 2
                    ELSE 3
                END,
                risk: coalesce(n.risk_score, 0),
                labels: labels(n)
            }] AS nodes,
            [r IN rels | {
                source: coalesce(startNode(r).node_id, startNode(r).company_id, startNode(r).person_id, elementId(startNode(r))),
                target: coalesce(endNode(r).node_id, endNode(r).company_id, endNode(r).person_id, elementId(endNode(r))),
                label: coalesce(r.rel_type, type(r)),
                weight: coalesce(r.ownership_pct, r.weight, 1.0)
            }] AS links
        """.replace("__MAX_HOPS__", str(safe_max_hops))
        with Neo4jConnection.session() as s:
            record = s.run(
                cypher,
                entity_name=entity_name,
                entity_id=entity_id,
                rel_types=rel_types,
                limit=limit,
            ).single()

        if not record:
            return {"nodes": [], "links": []}
        return {"nodes": record["nodes"], "links": record["links"]}

    @staticmethod
    def get_shortest_path_to_risk(entity_name: str, entity_id: str | None = None, max_depth: int = 6) -> dict:
        """Tìm đường đi ngắn nhất từ thực thể đang điều tra đến node rủi ro cao."""
        safe_max_depth = max(1, min(int(max_depth), 10))

        cypher = """
        MATCH (start)
        WITH start,
             CASE
                WHEN $entity_id IS NOT NULL AND (
                    coalesce(start.node_id, '') = $entity_id
                    OR coalesce(start.company_id, '') = $entity_id
                    OR coalesce(start.person_id, '') = $entity_id
                ) THEN 2
                WHEN toLower(coalesce(start.name, start.full_name, start.address, '')) CONTAINS toLower($entity_name) THEN 1
                ELSE 0
             END AS match_score
        WHERE match_score > 0
        WITH start, match_score
        ORDER BY match_score DESC
        LIMIT 1
        WITH start
        MATCH (risk)
        WHERE risk <> start
          AND (
            'Sanctioned' IN labels(risk)
            OR coalesce(risk.risk_score, 0.0) >= 0.8
            OR toLower(coalesce(risk.status, '')) CONTAINS 'sanction'
          )
        MATCH path = shortestPath((start)-[:RELATIONSHIP*1..__MAX_DEPTH__]-(risk))
        RETURN {
            start: coalesce(start.name, start.full_name, start.node_id),
            target: coalesce(risk.name, risk.full_name, risk.node_id),
            hops: length(path),
            nodes: [n IN nodes(path) | coalesce(n.name, n.full_name, n.node_id)],
            edges: [r IN relationships(path) | coalesce(r.rel_type, type(r))]
        } AS path_result
        ORDER BY path_result.hops ASC
        LIMIT 1
        """.replace("__MAX_DEPTH__", str(safe_max_depth))
        with Neo4jConnection.session() as s:
            record = s.run(cypher, entity_name=entity_name, entity_id=entity_id).single()

        if not record:
            return {
                "start": entity_name,
                "target": None,
                "hops": None,
                "nodes": [],
                "edges": [],
            }
        return dict(record["path_result"])

    @staticmethod
    def get_blast_radius(entity_name: str, entity_id: str | None = None, depth: int = 2) -> dict:
        """Ước lượng phạm vi ảnh hưởng (blast radius) quanh thực thể rủi ro."""
        safe_depth = max(1, min(int(depth), 6))

        cypher = """
        MATCH (start)
        WITH start,
             CASE
                WHEN $entity_id IS NOT NULL AND (
                    coalesce(start.node_id, '') = $entity_id
                    OR coalesce(start.company_id, '') = $entity_id
                    OR coalesce(start.person_id, '') = $entity_id
                ) THEN 2
                WHEN toLower(coalesce(start.name, start.full_name, start.address, '')) CONTAINS toLower($entity_name) THEN 1
                ELSE 0
             END AS match_score
        WHERE match_score > 0
        WITH start, match_score
        ORDER BY match_score DESC
        LIMIT 1
        WITH start
        MATCH path = (start)-[:RELATIONSHIP*1..__DEPTH__]-(n)
        WITH start, n, min(length(path)) AS min_hop
        WITH start,
             collect(DISTINCT coalesce(n.name, n.full_name, n.node_id))[0..25] AS impacted_sample,
             count(DISTINCT n) AS impacted_nodes,
             sum(CASE WHEN coalesce(n.risk_score, 0.0) >= 0.5 THEN 1 ELSE 0 END) AS medium_risk_hits,
             sum(CASE WHEN coalesce(n.risk_score, 0.0) >= 0.8 THEN 1 ELSE 0 END) AS high_risk_hits
        RETURN {
            source: coalesce(start.name, start.full_name, start.node_id),
            impacted_nodes: impacted_nodes,
            impacted_sample: impacted_sample,
            medium_risk_hits: medium_risk_hits,
            high_risk_hits: high_risk_hits,
            risk_ratio: CASE WHEN impacted_nodes = 0 THEN 0.0 ELSE toFloat(high_risk_hits) / toFloat(impacted_nodes) END
        } AS blast
        """.replace("__DEPTH__", str(safe_depth))
        with Neo4jConnection.session() as s:
            record = s.run(cypher, entity_name=entity_name, entity_id=entity_id).single()

        if not record:
            return {
                "source": entity_name,
                "impacted_nodes": 0,
                "impacted_sample": [],
                "medium_risk_hits": 0,
                "high_risk_hits": 0,
                "risk_ratio": 0.0,
            }
        return dict(record["blast"])

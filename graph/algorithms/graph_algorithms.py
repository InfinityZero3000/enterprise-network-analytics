"""
Graph Algorithms — PageRank, Betweenness, Louvain via Neo4j GDS
"""
from loguru import logger
from config.neo4j_config import Neo4jConnection

GDS_GRAPH = "enterprise-network"


class GraphAlgorithms:

    @classmethod
    def project_graph(
        cls,
        graph_name: str = GDS_GRAPH,
        node_labels: list[str] | None = None,
        rel_types: list[str] | None = None,
    ) -> dict:
        """Chiếu đồ thị vào GDS in-memory."""
        node_labels = node_labels or ["Company", "Person"]
        rel_types = rel_types or ["RELATIONSHIP"]
        # Build dynamic node projection
        node_proj = node_labels if len(node_labels) > 1 else node_labels[0]
        rel_proj = {rt: {"orientation": "NATURAL"} for rt in rel_types}
        try:
            with Neo4jConnection.session() as s:
                s.run("CALL gds.graph.drop($n, false)", n=graph_name)
                result = s.run("""
                    CALL gds.graph.project($n, $nodes, $rels)
                    YIELD graphName, nodeCount, relationshipCount
                """, n=graph_name, nodes=node_proj, rels=rel_proj).single()
                if result is None:
                    logger.error(f"Graph projection returned no result for '{graph_name}'")
                    return {}
                logger.info(f"Graph projected: {result['nodeCount']} nodes, {result['relationshipCount']} edges")
                return dict(result)
        except Exception as e:
            logger.error(f"Failed to project graph '{graph_name}': {e}")
            raise

    @classmethod
    def run_pagerank(
        cls,
        graph_name: str = GDS_GRAPH,
        write: bool = True,
        top_n: int = 100,
    ) -> list[dict]:
        """PageRank — tầm ảnh hưởng trong mạng lưới."""
        try:
            if write:
                cypher = """
                CALL gds.pageRank.write($g, {dampingFactor:0.85, maxIterations:20, writeProperty:'pagerank_score'})
                YIELD nodePropertiesWritten, ranIterations
                """
                with Neo4jConnection.session() as s:
                    r = s.run(cypher, g=graph_name).single()
                    logger.info(f"PageRank: {r['nodePropertiesWritten']} nodes updated.")
                    return [dict(r)]
            else:
                cypher = """
                CALL gds.pageRank.stream($g, {dampingFactor:0.85, maxIterations:20})
                YIELD nodeId, score
                MATCH (n) WHERE id(n) = nodeId
                RETURN COALESCE(n.company_id, n.person_id) AS entity_id,
                       n.name AS name, labels(n)[0] AS type, score
                ORDER BY score DESC LIMIT $top_n
                """
                with Neo4jConnection.session() as s:
                    return [dict(r) for r in s.run(cypher, g=graph_name, top_n=top_n)]
        except Exception as e:
            logger.error(f"PageRank failed on graph '{graph_name}': {e}")
            raise

    @classmethod
    def run_betweenness_centrality(
        cls,
        graph_name: str = GDS_GRAPH,
        write: bool = True,
        top_n: int = 50,
    ) -> list[dict]:
        """Betweenness Centrality — nút cầu nối quan trọng."""
        try:
            if write:
                cypher = """
                CALL gds.betweenness.write($g, {writeProperty:'betweenness_score'})
                YIELD nodePropertiesWritten
                """
                with Neo4jConnection.session() as s:
                    r = s.run(cypher, g=graph_name).single()
                    logger.info(f"Betweenness: {r['nodePropertiesWritten']} nodes updated.")
                    return [dict(r)]
            else:
                cypher = """
                CALL gds.betweenness.stream($g)
                YIELD nodeId, score
                MATCH (n) WHERE id(n) = nodeId
                RETURN COALESCE(n.company_id, n.person_id) AS entity_id,
                       n.name AS name, labels(n)[0] AS type, score
                ORDER BY score DESC LIMIT $top_n
                """
                with Neo4jConnection.session() as s:
                    return [dict(r) for r in s.run(cypher, g=graph_name, top_n=top_n)]
        except Exception as e:
            logger.error(f"Betweenness centrality failed on graph '{graph_name}': {e}")
            raise

    @classmethod
    def run_community_detection(cls, graph_name: str = GDS_GRAPH, write: bool = True) -> list[dict]:
        """Louvain Community Detection — phát hiện nhóm doanh nghiệp."""
        try:
            if write:
                cypher = """
                CALL gds.louvain.write($g, {writeProperty:'community_id'})
                YIELD communityCount, modularity
                """
                with Neo4jConnection.session() as s:
                    r = s.run(cypher, g=graph_name).single()
                    logger.info(f"Louvain: {r['communityCount']} communities found.")
                    return [dict(r)]
            else:
                cypher = """
                CALL gds.louvain.stream($g)
                YIELD nodeId, communityId
                MATCH (n) WHERE id(n) = nodeId
                RETURN COALESCE(n.company_id, n.person_id) AS entity_id,
                       n.name AS name, labels(n)[0] AS type, communityId
                ORDER BY communityId
                """
                with Neo4jConnection.session() as s:
                    return [dict(r) for r in s.run(cypher, g=graph_name)]
        except Exception as e:
            logger.error(f"Community detection failed on graph '{graph_name}': {e}")
            raise

    @classmethod
    def get_top_connected_entities(
        cls,
        metric: str = "degree",
        top_n: int = 20,
    ) -> list[dict]:
        """Entities theo metric: 'degree' | 'pagerank' | 'betweenness'."""
        allowed = {"degree", "pagerank", "betweenness"}
        if metric not in allowed:
            raise ValueError(f"metric must be one of {allowed}")

        if metric == "degree":
            cypher = """
            MATCH (n) WHERE n:Company OR n:Person
            WITH n, SIZE([(n)-[]-() | 1]) AS score
            ORDER BY score DESC LIMIT $top_n
            RETURN COALESCE(n.company_id, n.person_id) AS entity_id,
                   n.name AS name, labels(n)[0] AS type, score,
                   n.risk_score AS risk_score
            """
        elif metric == "pagerank":
            cypher = """
            MATCH (n) WHERE (n:Company OR n:Person) AND n.pagerank_score IS NOT NULL
            RETURN COALESCE(n.company_id, n.person_id) AS entity_id,
                   n.name AS name, labels(n)[0] AS type,
                   n.pagerank_score AS score, n.risk_score AS risk_score
            ORDER BY score DESC LIMIT $top_n
            """
        else:  # betweenness
            cypher = """
            MATCH (n) WHERE (n:Company OR n:Person) AND n.betweenness_score IS NOT NULL
            RETURN COALESCE(n.company_id, n.person_id) AS entity_id,
                   n.name AS name, labels(n)[0] AS type,
                   n.betweenness_score AS score, n.risk_score AS risk_score
            ORDER BY score DESC LIMIT $top_n
            """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, top_n=top_n)]

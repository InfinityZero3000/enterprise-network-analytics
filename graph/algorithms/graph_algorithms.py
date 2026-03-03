"""
Graph Algorithms — PageRank, Betweenness, Louvain via Neo4j GDS
"""
from loguru import logger
from config.neo4j_config import Neo4jConnection

GDS_GRAPH = "enterprise-network"


class GraphAlgorithms:

    @classmethod
    def project_graph(cls, graph_name: str = GDS_GRAPH) -> dict:
        """Chiếu đồ thị vào GDS in-memory."""
        with Neo4jConnection.session() as s:
            s.run("CALL gds.graph.drop($n, false)", n=graph_name)
            result = s.run("""
                CALL gds.graph.project($n, ['Company','Person'],
                    {RELATIONSHIP: {orientation:'NATURAL', properties:['ownership_percent']}})
                YIELD graphName, nodeCount, relationshipCount
            """, n=graph_name).single()
            logger.info(f"Graph projected: {result['nodeCount']} nodes, {result['relationshipCount']} edges")
            return dict(result)

    @classmethod
    def run_pagerank(cls, graph_name: str = GDS_GRAPH, write: bool = True) -> list[dict]:
        """PageRank — tầm ảnh hưởng trong mạng lưới."""
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
            ORDER BY score DESC LIMIT 100
            """
            with Neo4jConnection.session() as s:
                return [dict(r) for r in s.run(cypher, g=graph_name)]

    @classmethod
    def run_betweenness_centrality(cls, graph_name: str = GDS_GRAPH, write: bool = True) -> list[dict]:
        """Betweenness Centrality — nút cầu nối quan trọng."""
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
            ORDER BY score DESC LIMIT 50
            """
            with Neo4jConnection.session() as s:
                return [dict(r) for r in s.run(cypher, g=graph_name)]

    @classmethod
    def run_community_detection(cls, graph_name: str = GDS_GRAPH, write: bool = True) -> list[dict]:
        """Louvain Community Detection — phát hiện nhóm doanh nghiệp."""
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

    @classmethod
    def get_top_connected_entities(cls, top_n: int = 20) -> list[dict]:
        """Entities có nhiều kết nối nhất."""
        cypher = """
        MATCH (n) WHERE n:Company OR n:Person
        WITH n, SIZE([(n)-[]-() | 1]) AS degree
        ORDER BY degree DESC LIMIT $top_n
        RETURN COALESCE(n.company_id, n.person_id) AS entity_id,
               n.name AS name, labels(n)[0] AS type, degree,
               n.risk_score AS risk_score
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, top_n=top_n)]

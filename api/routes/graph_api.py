"""Graph API routes — GDS algorithms, network queries."""
from fastapi import APIRouter, Query, HTTPException
from graph.algorithms.graph_algorithms import GraphAlgorithms
from graph.graph_queries import GraphQueries

router = APIRouter()
_algo = GraphAlgorithms()
_queries = GraphQueries()


@router.get("/top-entities")
def get_top_entities(
    metric: str = Query(default="pagerank", pattern="^(pagerank|betweenness|degree)$"),
    top_n: int = Query(default=20, ge=1, le=200),
):
    """Top entities theo PageRank / Betweenness / Degree."""
    return _algo.get_top_connected_entities(metric=metric, top_n=top_n)


@router.get("/pagerank")
def get_pagerank(top_n: int = Query(default=50, ge=1, le=500)):
    """Chạy PageRank và trả về top N."""
    return _algo.run_pagerank(write=False, top_n=top_n)


@router.get("/betweenness")
def get_betweenness(top_n: int = Query(default=50, ge=1, le=500)):
    """Chạy Betweenness Centrality và trả về top N."""
    return _algo.run_betweenness_centrality(write=False, top_n=top_n)


@router.get("/communities")
def get_communities():
    """Phân cụm cộng đồng (Louvain) và trả về danh sách."""
    return _algo.run_community_detection(write=False)


@router.get("/network")
def get_network_graph(
    limit: int = Query(default=150, ge=10, le=1000), 
    order_by: str = Query(default=None)
):
    """Lấy dữ liệu đồ thị dạng Nodes/Links để vẽ trên UI."""
    from config.neo4j_config import Neo4jConnection
    
    order_clause = ""
    if order_by == "pagerank":
        order_clause = "ORDER BY source.pagerank_score DESC"
        
    cypher = f"""
    MATCH (source:Entity)-[r:RELATIONSHIP]->(target:Entity)
    WITH source, r, target
    {order_clause}
    LIMIT $limit
    WITH collect(source) + collect(target) as allNodes, collect({{source: source.node_id, target: target.node_id, label: r.rel_type}}) as links
    UNWIND allNodes as n
    WITH DISTINCT n, links
    RETURN 
        collect({{
            id: n.node_id, 
            name: coalesce(n.name, n.full_name, n.address, n.node_id), 
            group: CASE WHEN "Company" IN labels(n) THEN 1 WHEN "Person" IN labels(n) THEN 2 ELSE 3 END,
            val: CASE WHEN n.pagerank_score IS NOT NULL THEN n.pagerank_score * 20 ELSE 5 END,
            pagerank: n.pagerank_score
        }}) as nodes,
        links
    """
    with Neo4jConnection.session() as s:
        record = s.run(cypher, limit=limit).single()
        if record:
            return {"nodes": record["nodes"], "links": record["links"]}
        return {"nodes": [], "links": []}


@router.get("/circular-ownership")
def get_all_circular():
    """Tìm tất cả vòng tròn sở hữu trong toàn bộ graph."""
    from config.neo4j_config import Neo4jConnection
    cypher = """
    MATCH path = (c:Company)-[:RELATIONSHIP*2..6 {rel_type:'SHAREHOLDER'}]->(c)
    WITH c, length(path) AS depth, [n IN nodes(path) | n.name] AS cycle
    RETURN c.company_id AS id, c.name AS name, depth, cycle
    ORDER BY depth LIMIT 100
    """
    with Neo4jConnection.session() as s:
        return [dict(r) for r in s.run(cypher)]


@router.post("/project")
def project_graph(
    graph_name: str = "enterprise-graph",
    node_labels: list[str] = None,
    rel_types: list[str] = None,
):
    """Tạo GDS named graph projection."""
    node_labels = node_labels or ["Company", "Person"]
    rel_types = rel_types or ["RELATIONSHIP"]
    try:
        _algo.project_graph(graph_name, node_labels, rel_types)
        return {"status": "ok", "graph_name": graph_name}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/supply-chain/{company_id}")
def get_supply_chain(
    company_id: str,
    target_id: str = Query(...),
):
    """Tìm đường cung ứng ngắn nhất giữa 2 công ty."""
    from analytics.supply_chain.analysis import SupplyChainAnalyzer
    analyzer = SupplyChainAnalyzer()
    paths = analyzer.find_paths(company_id, target_id)
    return [
        {"path_ids": p.path_ids, "path_names": p.path_names, "hops": p.hops}
        for p in paths
    ]

"""
Supply Chain Analysis — phân tích chuỗi cung ứng doanh nghiệp
"""
from dataclasses import dataclass
from loguru import logger
from config.neo4j_config import Neo4jConnection


@dataclass
class SupplyChainPath:
    source_id: str
    target_id: str
    path_ids: list[str]
    path_names: list[str]
    hops: int


@dataclass
class SupplierConcentration:
    company_id: str
    company_name: str
    supplier_count: int
    top_supplier_id: str
    top_supplier_name: str
    top_supplier_share: float


class SupplyChainAnalyzer:

    def find_paths(self, source_id: str, target_id: str, max_hops: int = 6) -> list[SupplyChainPath]:
        cypher = """
        MATCH path = shortestPath(
            (a:Company {company_id: $src})-[:RELATIONSHIP*..{max_hops} {rel_type:'SUPPLIER'}]->(b:Company {company_id: $tgt})
        )
        RETURN [n IN nodes(path) | n.company_id] AS ids,
               [n IN nodes(path) | n.name]       AS names,
               length(path)                       AS hops
        LIMIT 5
        """.replace("{max_hops}", str(max_hops))
        results: list[SupplyChainPath] = []
        with Neo4jConnection.session() as s:
            for r in s.run(cypher, src=source_id, tgt=target_id):
                results.append(SupplyChainPath(
                    source_id=source_id, target_id=target_id,
                    path_ids=r["ids"], path_names=r["names"], hops=r["hops"],
                ))
        return results

    def detect_supplier_concentration(self, top_n: int = 100) -> list[SupplierConcentration]:
        cypher = """
        MATCH (sup:Company)-[r:RELATIONSHIP {rel_type:'SUPPLIER'}]->(c:Company)
        WITH c, COUNT(DISTINCT sup) AS sup_count
        MATCH (top_sup:Company)-[tr:RELATIONSHIP {rel_type:'SUPPLIER'}]->(c)
        WITH c, sup_count, top_sup ORDER BY coalesce(tr.supply_volume_vnd,0) DESC
        WITH c, sup_count, COLLECT(top_sup)[0] AS top_sup
        WHERE top_sup IS NOT NULL
        RETURN c.company_id AS cid, c.name AS cname,
               sup_count,
               top_sup.company_id AS ts_id, top_sup.name AS ts_name,
               0.0 AS ts_share
        ORDER BY sup_count ASC LIMIT $n
        """
        results: list[SupplierConcentration] = []
        with Neo4jConnection.session() as s:
            for r in s.run(cypher, n=top_n):
                results.append(SupplierConcentration(
                    company_id=r["cid"], company_name=r["cname"],
                    supplier_count=r["sup_count"],
                    top_supplier_id=r["ts_id"], top_supplier_name=r["ts_name"],
                    top_supplier_share=r["ts_share"],
                ))
        return results

    def get_supply_chain_subgraph(self, company_id: str, depth: int = 3) -> dict:
        cypher = """
        MATCH (c:Company {company_id: $cid})
        CALL apoc.path.subgraphAll(c, {
            relationshipFilter: 'RELATIONSHIP>',
            maxLevel: $depth
        })
        YIELD nodes, relationships
        RETURN [n IN nodes | {id: n.company_id, name: n.name}] AS nodes,
               [r IN relationships | {from: startNode(r).company_id, to: endNode(r).company_id, type: r.rel_type}] AS rels
        """
        with Neo4jConnection.session() as s:
            r = s.run(cypher, cid=company_id, depth=depth).single()
            if r:
                return {"nodes": r["nodes"], "edges": r["rels"]}
        return {"nodes": [], "edges": []}

    def identify_critical_nodes(self, top_n: int = 20) -> list[dict]:
        """Nodes with highest betweenness in supply chain subgraph."""
        cypher = """
        MATCH (c:Company)
        WHERE c.betweenness IS NOT NULL
        RETURN c.company_id AS id, c.name AS name,
               c.betweenness AS betweenness,
               c.pagerank    AS pagerank
        ORDER BY c.betweenness DESC LIMIT $n
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher, n=top_n)]

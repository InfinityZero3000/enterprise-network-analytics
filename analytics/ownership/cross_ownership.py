"""
Cross-Ownership Analysis — phân tích sở hữu chéo, UBO, cấu trúc vốn
"""
from dataclasses import dataclass
from loguru import logger
from config.neo4j_config import Neo4jConnection


@dataclass
class UBORecord:
    company_id: str
    company_name: str
    ubo_id: str
    ubo_name: str
    total_ownership_pct: float
    chain_depth: int


@dataclass
class CrossOwnershipPair:
    company_a_id: str
    company_a_name: str
    company_b_id: str
    company_b_name: str
    mutual: bool
    overlap_shareholder: str | None = None


class OwnershipAnalyzer:

    def find_ultimate_beneficial_owners(self, min_pct: float = 5.0) -> list[UBORecord]:
        cypher = """
        MATCH path = (p:Person)-[:RELATIONSHIP*1..6 {rel_type:'SHAREHOLDER'}]->(c:Company)
        WITH c, p, length(path) AS depth,
             reduce(pct=1.0, r IN relationships(path) | pct * coalesce(r.ownership_pct,0)/100.0) AS eff_pct
        WHERE eff_pct * 100 >= $min_pct
        RETURN c.company_id AS company_id, c.name AS company_name,
               p.person_id AS ubo_id, p.full_name AS ubo_name,
               round(eff_pct*100, 2) AS total_pct, depth
        ORDER BY total_pct DESC
        """
        results: list[UBORecord] = []
        with Neo4jConnection.session() as s:
            for r in s.run(cypher, min_pct=min_pct):
                results.append(UBORecord(
                    company_id=r["company_id"], company_name=r["company_name"],
                    ubo_id=r["ubo_id"], ubo_name=r["ubo_name"],
                    total_ownership_pct=r["total_pct"], chain_depth=r["depth"],
                ))
        logger.info(f"UBO analysis: {len(results)} records (min_pct={min_pct}%)")
        return results

    def detect_cross_ownership(self) -> list[CrossOwnershipPair]:
        cypher = """
        MATCH (a:Company)-[:RELATIONSHIP {rel_type:'SHAREHOLDER'}]->(b:Company)
        OPTIONAL MATCH (b)-[:RELATIONSHIP {rel_type:'SHAREHOLDER'}]->(a)
        WITH a, b, COUNT(*) AS mutual_edge
        WHERE id(a) < id(b)
        RETURN a.company_id AS a_id, a.name AS a_name,
               b.company_id AS b_id, b.name AS b_name,
               mutual_edge > 0 AS is_mutual
        """
        results: list[CrossOwnershipPair] = []
        with Neo4jConnection.session() as s:
            for r in s.run(cypher):
                results.append(CrossOwnershipPair(
                    company_a_id=r["a_id"], company_a_name=r["a_name"],
                    company_b_id=r["b_id"], company_b_name=r["b_name"],
                    mutual=r["is_mutual"],
                ))
        return results

    def get_ownership_tree(self, company_id: str, max_depth: int = 4) -> dict:
        cypher = """
        MATCH path = (root:Company {company_id: $cid})<-[:RELATIONSHIP*1..$depth {rel_type:'SHAREHOLDER'}]-(n)
        RETURN [node IN nodes(path) | {id: coalesce(node.company_id, node.person_id), name: coalesce(node.name, node.full_name), label: labels(node)[0]}] AS chain,
               [rel IN relationships(path) | coalesce(rel.ownership_pct, 0)] AS pct_chain
        """
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        with Neo4jConnection.session() as s:
            for r in s.run(cypher, cid=company_id, depth=max_depth):
                chain = r["chain"]
                pcts = r["pct_chain"]
                for node in chain:
                    nodes[node["id"]] = node
                for i in range(len(chain) - 1):
                    edges.append({
                        "from": chain[i]["id"], "to": chain[i+1]["id"],
                        "ownership_pct": pcts[i] if i < len(pcts) else None,
                    })
        return {"company_id": company_id, "nodes": list(nodes.values()), "edges": edges}

    def ownership_concentration_report(self) -> list[dict]:
        cypher = """
        MATCH (sh)-[:RELATIONSHIP {rel_type:'SHAREHOLDER'}]->(c:Company)
        WITH c, COUNT(sh) AS shareholder_count, SUM(coalesce(r.ownership_pct, 0)) AS total_pct
        MATCH ()-[r:RELATIONSHIP {rel_type:'SHAREHOLDER'}]->(c)
        WITH c, shareholder_count,
             MAX(coalesce(r.ownership_pct,0)) AS top_shareholder_pct,
             total_pct
        RETURN c.company_id AS company_id, c.name AS name,
               shareholder_count, top_shareholder_pct,
               total_pct AS declared_pct
        ORDER BY top_shareholder_pct DESC
        LIMIT 500
        """
        with Neo4jConnection.session() as s:
            return [dict(r) for r in s.run(cypher)]

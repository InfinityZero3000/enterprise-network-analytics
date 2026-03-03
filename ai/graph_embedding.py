"""
Graph Embedding — Node2Vec embeddings cho phát hiện bất thường và similarity
"""
import os
import pickle
from pathlib import Path
import numpy as np
from loguru import logger
from config.neo4j_config import Neo4jConnection

MODEL_PATH = Path(os.getenv("EMBEDDING_MODEL_PATH", "models/node2vec_enterprise.pkl"))


class GraphEmbedding:

    def __init__(self, dimensions: int = 64, walk_length: int = 30,
                 num_walks: int = 200, workers: int = 4):
        self.dimensions = dimensions
        self.walk_length = walk_length
        self.num_walks = num_walks
        self.workers = workers
        self.model = None
        self._load_model()

    def _load_model(self):
        if MODEL_PATH.exists():
            with open(MODEL_PATH, "rb") as f:
                self.model = pickle.load(f)
            logger.info(f"Loaded embedding model from {MODEL_PATH}")

    def _fetch_graph(self) -> tuple[list[tuple], list[str]]:
        cypher = """
        MATCH (a)-[r:RELATIONSHIP]->(b)
        WHERE a.company_id IS NOT NULL OR a.person_id IS NOT NULL
        RETURN coalesce(a.company_id, a.person_id) AS src,
               coalesce(b.company_id, b.person_id) AS tgt
        LIMIT 200000
        """
        edges = []
        nodes_set: set[str] = set()
        with Neo4jConnection.session() as s:
            for r in s.run(cypher):
                if r["src"] and r["tgt"]:
                    edges.append((r["src"], r["tgt"]))
                    nodes_set.update([r["src"], r["tgt"]])
        return edges, list(nodes_set)

    def train(self):
        try:
            import networkx as nx
            from node2vec import Node2Vec
        except ImportError:
            logger.error("node2vec / networkx not installed. Run: pip install node2vec networkx")
            return

        logger.info("Fetching graph data for embedding training...")
        edges, _ = self._fetch_graph()
        G = nx.DiGraph()
        G.add_edges_from(edges)

        logger.info(f"Training Node2Vec on {G.number_of_nodes()} nodes, {G.number_of_edges()} edges ...")
        n2v = Node2Vec(G, dimensions=self.dimensions, walk_length=self.walk_length,
                       num_walks=self.num_walks, workers=self.workers, quiet=True)
        self.model = n2v.fit(window=10, min_count=1, batch_words=4)

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        logger.info(f"Node2Vec model saved → {MODEL_PATH}")

    def get_embedding(self, node_id: str) -> np.ndarray | None:
        if self.model is None:
            logger.warning("Model not trained yet.")
            return None
        try:
            return np.array(self.model.wv[node_id])
        except KeyError:
            return None

    def find_similar(self, node_id: str, top_n: int = 10) -> list[tuple[str, float]]:
        if self.model is None:
            return []
        try:
            return self.model.wv.most_similar(node_id, topn=top_n)
        except KeyError:
            return []

    def anomaly_score(self, node_id: str) -> float:
        """Simple isolation-based anomaly: distance from centroid."""
        if self.model is None:
            return 0.0
        vec = self.get_embedding(node_id)
        if vec is None:
            return 0.0
        all_vecs = np.array([self.model.wv[k] for k in self.model.wv.index_to_key[:5000]])
        centroid = all_vecs.mean(axis=0)
        dist = float(np.linalg.norm(vec - centroid))
        max_dist = float(np.linalg.norm(all_vecs - centroid, axis=1).max())
        return round(dist / max_dist, 4) if max_dist > 0 else 0.0

    def write_embeddings_to_neo4j(self, batch_size: int = 500):
        if self.model is None:
            logger.error("No model to write embeddings from.")
            return
        keys = self.model.wv.index_to_key
        total = len(keys)
        logger.info(f"Writing {total} embeddings to Neo4j ...")
        with Neo4jConnection.session() as s:
            for i in range(0, total, batch_size):
                batch = keys[i: i + batch_size]
                params = [{"id": k, "emb": self.model.wv[k].tolist()} for k in batch]
                s.run("""
                UNWIND $rows AS row
                MATCH (n) WHERE n.company_id = row.id OR n.person_id = row.id
                SET n.embedding = row.emb
                """, rows=params)
        logger.info("Embedding write complete.")

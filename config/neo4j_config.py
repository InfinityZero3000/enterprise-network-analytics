"""
Neo4j Driver + Context Manager
"""
from contextlib import contextmanager
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import Neo4jError
from loguru import logger
from config.settings import settings


class Neo4jConnection:
    _driver: Driver | None = None

    @classmethod
    def get_driver(cls) -> Driver:
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_pool_size=50,
            )
            logger.info(f"Neo4j driver: {settings.neo4j_uri}")
        return cls._driver

    @classmethod
    @contextmanager
    def session(cls, database: str = "neo4j"):
        driver = cls.get_driver()
        s: Session = driver.session(database=database)
        try:
            yield s
        finally:
            s.close()

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None

    @classmethod
    def health_check(cls) -> bool:
        try:
            with cls.session() as s:
                s.run("RETURN 1")
            return True
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False


def setup_constraints_and_indexes():
    """Tạo constraints và indexes khi khởi động."""
    statements = [
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.node_id IS UNIQUE",
        "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.company_id IS UNIQUE",
        "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
        "CREATE CONSTRAINT address_id IF NOT EXISTS FOR (a:Address) REQUIRE a.address_id IS UNIQUE",
        "CREATE CONSTRAINT transaction_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE",
        "CREATE CONSTRAINT industry_code IF NOT EXISTS FOR (i:Industry) REQUIRE i.code IS UNIQUE",
        "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
        "CREATE INDEX company_tax IF NOT EXISTS FOR (c:Company) ON (c.tax_code)",
        "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.full_name)",
        "CREATE INDEX address_text IF NOT EXISTS FOR (a:Address) ON (a.address)",
    ]

    def _auto_deduplicate_entity_node_ids(session: Session) -> tuple[int, int]:
        """Merge duplicate Entity nodes sharing the same node_id.

        Returns:
            tuple[int, int]: (duplicate_groups_before, merged_groups)
        """
        count_query = """
        MATCH (e:Entity)
        WHERE e.node_id IS NOT NULL
        WITH e.node_id AS node_id, count(*) AS cnt
        WHERE cnt > 1
        RETURN count(*) AS groups
        """
        groups_before = int(session.run(count_query).single()["groups"])
        if groups_before == 0:
            return 0, 0

        if settings.neo4j_auto_dedup_entity_node_id:
            dedup_query = """
            MATCH (e:Entity)
            WHERE e.node_id IS NOT NULL
            WITH e.node_id AS node_id, collect(e) AS nodes, count(*) AS cnt
            WHERE cnt > 1
            WITH nodes
            LIMIT $batch_size
            CALL apoc.refactor.mergeNodes(
                nodes,
                {
                    properties: 'discard',
                    mergeRels: true,
                    preserveExistingSelfRels: false,
                    singleElementAsArray: false
                }
            ) YIELD node
            RETURN count(*) AS merged
            """

            total_merged = 0
            while True:
                merged = int(session.run(dedup_query, batch_size=settings.neo4j_dedup_batch_size).single()["merged"])
                total_merged += merged
                if merged == 0:
                    break
            return groups_before, total_merged

        return groups_before, 0

    def _duplicate_entity_examples(session: Session, limit: int = 3) -> list[dict]:
        query = """
        MATCH (e:Entity)
        WHERE e.node_id IS NOT NULL
        WITH e.node_id AS node_id, collect(id(e)) AS ids, count(*) AS cnt
        WHERE cnt > 1
        RETURN node_id, ids[0..5] AS sample_node_internal_ids, cnt
        ORDER BY cnt DESC
        LIMIT $limit
        """
        return [dict(r) for r in session.run(query, limit=limit)]

    with Neo4jConnection.session() as session:
        try:
            groups_before, merged_groups = _auto_deduplicate_entity_node_ids(session)
            if groups_before > 0:
                if merged_groups > 0:
                    logger.info(
                        "Auto-deduplicated Entity.node_id groups before schema setup: "
                        f"before={groups_before}, merged={merged_groups}."
                    )
                else:
                    logger.warning(
                        "Duplicate Entity.node_id groups detected but auto-dedup is disabled. "
                        f"groups={groups_before}."
                    )
        except Neo4jError as e:
            logger.warning(f"Skip auto dedup Entity.node_id due to Neo4j/APOC error: {e}")

        for stmt in statements:
            try:
                session.run(stmt)
            except Neo4jError as e:
                # Keep startup healthy when legacy data violates uniqueness.
                if "CREATE CONSTRAINT entity_id" in stmt and "ConstraintCreationFailed" in str(e):
                    examples = _duplicate_entity_examples(session)
                    logger.warning(
                        "Skip Entity(node_id) uniqueness constraint because duplicates exist. "
                        f"Sample duplicates: {examples}"
                    )
                    continue
                raise
    logger.info("Neo4j constraints và indexes đã được thiết lập (bỏ qua ràng buộc trùng nếu có).")

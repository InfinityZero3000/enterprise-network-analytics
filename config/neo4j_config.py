"""
Neo4j Driver + Context Manager
"""
from contextlib import contextmanager
from neo4j import GraphDatabase, Driver, Session
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
        "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.company_id IS UNIQUE",
        "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
        "CREATE CONSTRAINT transaction_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE",
        "CREATE CONSTRAINT industry_code IF NOT EXISTS FOR (i:Industry) REQUIRE i.code IS UNIQUE",
        "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
        "CREATE INDEX company_tax IF NOT EXISTS FOR (c:Company) ON (c.tax_code)",
        "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
    ]
    with Neo4jConnection.session() as session:
        for stmt in statements:
            session.run(stmt)
    logger.info("Neo4j constraints và indexes đã được thiết lập.")

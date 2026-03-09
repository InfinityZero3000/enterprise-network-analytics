"""
Batch Pipeline — orchestrate toàn bộ pipeline ETL → Graph → Analytics
"""
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from config.spark_config import create_spark_session
from config.neo4j_config import Neo4jConnection, setup_constraints_and_indexes
from config.kafka_config import create_topics_if_not_exist
from config.settings import settings
from processing.spark_jobs.company_etl import run_company_etl
from processing.spark_jobs.relationship_etl import run_relationship_etl
from graph.neo4j_loader import Neo4jLoader
from graph.algorithms.graph_algorithms import GraphAlgorithms
from analytics.fraud_detection.rule_based import RuleBasedFraudDetector
from analytics.risk.risk_scoring import RiskScoringEngine
from ingestion.kafka_producer import EnterpriseProducer


@dataclass
class PipelineResult:
    run_id: str
    start_time: datetime
    end_time: datetime | None = None
    stages_completed: list[str] = field(default_factory=list)
    stages_failed: list[str] = field(default_factory=list)
    companies_processed: int = 0
    relationships_processed: int = 0
    alerts_generated: int = 0
    success: bool = False

    @property
    def duration_seconds(self) -> float | None:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class BatchPipeline:

    def __init__(self, app_name: str = "ENA-BatchPipeline"):
        self.app_name = app_name

    def _stage(self, result: PipelineResult, name: str, fn):
        logger.info(f"=== Stage: {name} ===")
        try:
            fn()
            result.stages_completed.append(name)
            logger.success(f"Stage '{name}' completed.")
        except Exception as e:
            result.stages_failed.append(name)
            logger.error(f"Stage '{name}' FAILED: {e}")
            raise

    def run(self) -> PipelineResult:
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        result = PipelineResult(run_id=run_id, start_time=datetime.utcnow())
        spark = create_spark_session(self.app_name)

        try:
            # 1. Infrastructure setup
            self._stage(result, "setup_kafka_topics", create_topics_if_not_exist)
            self._stage(result, "setup_neo4j_schema", setup_constraints_and_indexes)

            # 2. ETL
            def etl():
                company_df = run_company_etl(spark)
                rel_df = run_relationship_etl(spark)
                result.companies_processed = company_df.count()
                result.relationships_processed = rel_df.count()

            self._stage(result, "spark_etl", etl)

            # 3. Load into Neo4j (read from Delta Lake paths written by ETL)
            def load_graph():
                loader = Neo4jLoader()
                company_path = f"s3a://{settings.minio_bucket_processed}/companies"
                rel_path = f"s3a://{settings.minio_bucket_processed}/relationships"
                company_df = spark.read.format("delta").load(company_path)
                rel_df = spark.read.format("delta").load(rel_path)
                loaded_c = loader.load_companies(company_df)
                loaded_r = loader.load_relationships(rel_df)
                logger.info(f"Neo4j loaded: {loaded_c} companies, {loaded_r} relationships")

            self._stage(result, "neo4j_load", load_graph)

            # 4. GDS Algorithms
            def run_gds():
                algo = GraphAlgorithms()
                algo.project_graph("enterprise-graph", ["Company", "Person"], ["RELATIONSHIP"])
                algo.run_pagerank(write=True)
                algo.run_betweenness_centrality(write=True)
                algo.run_community_detection(write=True)

            self._stage(result, "gds_algorithms", run_gds)

            # 5. Fraud detection
            def fraud():
                detector = RuleBasedFraudDetector()
                alerts = detector.run_all_rules()
                result.alerts_generated = len(alerts)
                if alerts:
                    with EnterpriseProducer() as producer:
                        for alert in alerts:
                            producer.publish_alert({
                                "entity_id": alert.entity_id,
                                "alert_type": alert.alert_type,
                                "level": alert.level.value,
                                "score": alert.score,
                                "description": alert.description,
                                "run_id": run_id,
                            })

            self._stage(result, "fraud_detection", fraud)

            # 6. Risk scoring (top 500)
            def risk():
                engine = RiskScoringEngine()
                engine.batch_score_all(limit=500)

            self._stage(result, "risk_scoring", risk)

            result.success = True

        except Exception as e:
            logger.error(f"Pipeline aborted at failed stage: {e}")
        finally:
            result.end_time = datetime.utcnow()
            spark.stop()
            logger.info(
                f"Pipeline {run_id} finished in {result.duration_seconds:.1f}s "
                f"| completed={result.stages_completed} | failed={result.stages_failed}"
            )

        return result

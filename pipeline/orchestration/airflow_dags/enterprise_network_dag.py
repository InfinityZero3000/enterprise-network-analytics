"""
Airflow DAG — Enterprise Network Daily Pipeline
Schedule: 02:00 AM UTC daily
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "ena-team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="enterprise_network_daily_pipeline",
    default_args=default_args,
    description="Daily ETL + Graph + Analytics pipeline for enterprise network",
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ena", "bigdata", "graph"],
) as dag:

    # ------------------------------------------------------------------ #
    # Health checks
    # ------------------------------------------------------------------ #
    def _health_check_neo4j():
        from config.neo4j_config import Neo4jConnection
        ok = Neo4jConnection.health_check()
        if not ok:
            raise RuntimeError("Neo4j health check failed")

    def _health_check_kafka():
        from config.kafka_config import create_topics_if_not_exist
        create_topics_if_not_exist()

    health_neo4j = PythonOperator(task_id="health_neo4j", python_callable=_health_check_neo4j)
    health_kafka = PythonOperator(task_id="health_kafka", python_callable=_health_check_kafka)

    # ------------------------------------------------------------------ #
    # ETL
    # ------------------------------------------------------------------ #
    def _run_company_etl():
        from config.spark_config import create_spark_session
        from processing.spark_jobs.company_etl import run_company_etl
        spark = create_spark_session("AirflowETL-Company")
        try:
            run_company_etl(spark)
        finally:
            spark.stop()

    def _run_relationship_etl():
        from config.spark_config import create_spark_session
        from processing.spark_jobs.relationship_etl import run_relationship_etl
        spark = create_spark_session("AirflowETL-Relationship")
        try:
            run_relationship_etl(spark)
        finally:
            spark.stop()

    etl_company = PythonOperator(task_id="etl_company", python_callable=_run_company_etl)
    etl_relationship = PythonOperator(task_id="etl_relationship", python_callable=_run_relationship_etl)

    # ------------------------------------------------------------------ #
    # Neo4j load
    # ------------------------------------------------------------------ #
    def _load_neo4j():
        from config.spark_config import create_spark_session
        from config.neo4j_config import setup_constraints_and_indexes
        from graph.neo4j_loader import Neo4jLoader
        setup_constraints_and_indexes()
        spark = create_spark_session("AirflowNeo4jLoad")
        try:
            loader = Neo4jLoader()
            c_df = spark.read.format("delta").load("s3a://ena-processed/companies")
            r_df = spark.read.format("delta").load("s3a://ena-processed/relationships")
            loader.load_companies(c_df)
            loader.load_relationships(r_df)
        finally:
            spark.stop()

    load_neo4j = PythonOperator(task_id="load_neo4j", python_callable=_load_neo4j)

    # ------------------------------------------------------------------ #
    # GDS Algorithms
    # ------------------------------------------------------------------ #
    def _run_gds():
        from graph.algorithms.graph_algorithms import GraphAlgorithms
        algo = GraphAlgorithms()
        algo.project_graph("enterprise-graph", ["Company", "Person"], ["RELATIONSHIP"])
        algo.run_pagerank(write=True)
        algo.run_betweenness_centrality(write=True)
        algo.run_community_detection(write=True)

    run_gds = PythonOperator(task_id="run_gds", python_callable=_run_gds)

    # ------------------------------------------------------------------ #
    # Fraud detection
    # ------------------------------------------------------------------ #
    def _run_fraud():
        from analytics.fraud_detection.rule_based import RuleBasedFraudDetector
        detector = RuleBasedFraudDetector()
        alerts = detector.run_all_rules()
        print(f"Fraud alerts generated: {len(alerts)}")

    run_fraud = PythonOperator(task_id="run_fraud_detection", python_callable=_run_fraud)

    # ------------------------------------------------------------------ #
    # Risk scoring
    # ------------------------------------------------------------------ #
    def _run_risk():
        from analytics.risk.risk_scoring import RiskScoringEngine
        engine = RiskScoringEngine()
        profiles = engine.batch_score_all(limit=1000)
        print(f"Risk profiles computed: {len(profiles)}")

    run_risk = PythonOperator(task_id="run_risk_scoring", python_callable=_run_risk)

    # ------------------------------------------------------------------ #
    # Graph embedding update (weekly via branching)
    # ------------------------------------------------------------------ #
    update_embedding = BashOperator(
        task_id="update_graph_embedding",
        bash_command="cd /opt/ena && python -c 'from ai.graph_embedding import GraphEmbedding; GraphEmbedding().train()'",
    )

    # ------------------------------------------------------------------ #
    # Task dependencies
    # ------------------------------------------------------------------ #
    [health_neo4j, health_kafka] >> [etl_company, etl_relationship]
    [etl_company, etl_relationship] >> load_neo4j >> run_gds
    run_gds >> [run_fraud, run_risk]
    run_risk >> update_embedding

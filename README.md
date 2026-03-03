# Enterprise Network Analytics — Phân Tích Mạng Lưới Doanh Nghiệp

> **Stack:** PySpark · Apache Kafka · Neo4j · FastAPI · MLflow · Airflow

---

## Tổng Quan Kiến Trúc

```
Raw Data Sources
      │
      ▼
┌─────────────────────────────────────────┐
│          Ingestion Layer                │
│   Kafka (streaming) + Batch loaders     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│        Processing Layer (PySpark)       │
│   ETL · Cleaning · Feature Engineering │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Graph Layer (Neo4j)             │
│   Nodes: Company, Person, Transaction   │
│   PageRank · Centrality · Community     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Analytics Layer                 │
│  ┌──────────────┐  ┌──────────────────┐ │
│  │ Fraud / Risk │  │  Ownership Graph │ │
│  └──────────────┘  └──────────────────┘ │
│  ┌──────────────┐  ┌──────────────────┐ │
│  │ Supply Chain │  │  AI / LLM Query  │ │
│  └──────────────┘  └──────────────────┘ │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│            API Layer (FastAPI)          │
│   REST endpoints · Graph queries        │
└─────────────────────────────────────────┘
```

## Cấu Trúc Thư Mục

```
enterprise-network-analytics/
├── config/                   # Cấu hình tất cả services
│   ├── settings.py           # Pydantic settings từ .env
│   ├── spark_config.py       # SparkSession factory
│   ├── neo4j_config.py       # Neo4j driver + constraints
│   └── kafka_config.py       # Kafka producer/consumer config
├── data/
│   ├── raw/                  # Dữ liệu thô đầu vào (CSV/JSON)
│   ├── processed/            # Dữ liệu sau ETL
│   └── schemas/              # Pydantic + PySpark schemas
├── ingestion/
│   ├── kafka_producer.py     # Publish events vào Kafka
│   ├── kafka_consumer.py     # Consume và xử lý events
│   └── batch_ingestion.py    # Upload batch files lên MinIO
├── processing/
│   └── spark_jobs/
│       ├── company_etl.py    # ETL cho dữ liệu công ty
│       └── relationship_etl.py
├── graph/
│   ├── neo4j_loader.py       # Load DataFrames vào Neo4j
│   ├── graph_queries.py      # Cypher query wrappers
│   └── algorithms/
│       └── graph_algorithms.py  # PageRank, Centrality, Louvain
├── analytics/
│   ├── fraud_detection/
│   │   └── rule_based.py     # Rule-based fraud detection
│   ├── ownership/
│   │   └── cross_ownership.py   # UBO, sở hữu chéo
│   └── risk/
│       └── risk_scoring.py   # Risk scoring engine
├── ai/
│   ├── llm_integration.py    # LLM Q&A về mạng lưới
│   └── graph_embedding.py    # Node2Vec embeddings
├── pipeline/
│   ├── batch_pipeline.py     # Batch pipeline orchestration
│   ├── streaming_pipeline.py # Kafka streaming pipeline
│   └── orchestration/
│       └── airflow_dags/
│           └── enterprise_network_dag.py
├── api/
│   ├── main.py               # FastAPI app
│   └── routes/
│       ├── companies.py
│       ├── analytics.py
│       ├── graph_api.py
│       └── ai_api.py
├── tests/                    # Unit & integration tests
├── notebooks/                # Jupyter notebooks phân tích
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Khởi Chạy Nhanh

```bash
# 1. Copy và cấu hình env
cp .env.example .env

# 2. Khởi động toàn bộ infrastructure
docker compose up -d

# 3. Cài Python dependencies
pip install -e ".[dev]"

# 4. Chạy batch pipeline
python -m pipeline.batch_pipeline

# 5. Chạy streaming pipeline (Kafka)
python -m pipeline.streaming_pipeline

# 6. Khởi động API
uvicorn api.main:app --reload --port 8000
```

## Services & Ports

| Service | URL | Mô tả |
|---|---|---|
| FastAPI | http://localhost:8000/docs | REST API + Swagger UI |
| Neo4j Browser | http://localhost:7474 | Graph database UI |
| Kafka UI | http://localhost:8080 | Monitor Kafka topics |
| Spark Master | http://localhost:8082 | Spark cluster UI |
| MLflow | http://localhost:5000 | Experiment tracking |
| Airflow | http://localhost:8083 | Pipeline scheduling |
| MinIO | http://localhost:9001 | Object storage UI |

## Các Module Phân Tích

| Module | Mô tả |
|---|---|
| `graph/algorithms/graph_algorithms.py` | PageRank, Betweenness, Louvain |
| `analytics/fraud_detection/rule_based.py` | Shell company, circular ownership, PEP/Sanctions |
| `analytics/ownership/cross_ownership.py` | UBO chain, sở hữu chéo |
| `analytics/risk/risk_scoring.py` | Risk score tổng hợp (0.0–1.0) |
| `ai/llm_integration.py` | Q&A tiếng Việt về mạng lưới |
| `ai/graph_embedding.py` | Node2Vec để tìm công ty tương đồng |

## Yêu Cầu

- Docker & Docker Compose
- Python 3.11+
- Java 11+ (PySpark)


# Khởi động nhanh
```
cd ~/projects/enterprise-network-analytics
bash scripts/start.sh         # tự check dependency + tự chạy backend/UI
```
- API: http://localhost:8000/docs
- Neo4j: http://localhost:7474
- Kafka UI: http://localhost:8080

# lấy API key AI

1. Tạo key từ một trong các nhà cung cấp:
	 - Gemini: https://aistudio.google.com/app/apikey
	 - Groq: https://console.groq.com/keys
	 - OpenAI: https://platform.openai.com/api-keys
	 - OpenRouter (tuỳ chọn): https://openrouter.ai/keys

2. Điền key vào `.env` (ít nhất 1 key):

```
GEMINI_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=
```

3. Nạp lại API backend:

```
docker compose restart api
```

4. Test nhanh AI endpoint:

```
curl -X POST http://localhost:8000/api/v1/ai/ask \
	-H 'Content-Type: application/json' \
	-d '{"question":"Top 3 connected companies"}'
```

Nếu response có `answer` khác rỗng là AI đã hoạt động.

# chạy pipeline thủ công

```
python -c "from pipeline.batch_pipeline import BatchPipeline; print(BatchPipeline().run())"
```

# Tóm tắt cấu trúc

| Layer | Files |
|---|---|
| Infrastructure | `docker-compose.yml`, `Dockerfile`, `pyproject.toml`, `.env.example`, `README.md` |
| Config | `settings.py`, `spark_config.py`, `neo4j_config.py`, `kafka_config.py` |
| Data Schemas | `data/schemas/enterprise_schemas.py` (Pydantic + PySpark StructType) |
| Ingestion | `kafka_producer.py`, `kafka_consumer.py`, `batch_ingestion.py` (MinIO) |
| Processing | `company_etl.py`, `relationship_etl.py` (PySpark + Delta Lake) |
| Graph | `neo4j_loader.py`, `graph_queries.py`, `graph_algorithms.py` (PageRank/Betweenness/Louvain) |
| Analytics | `fraud_detection/rule_based.py`, `ownership/cross_ownership.py`, `risk/risk_scoring.py`, `supply_chain/analysis.py` |
| AI | `llm_integration.py` (OpenAI/Ollama), `graph_embedding.py` (Node2Vec) |
| Pipeline | `batch_pipeline.py`, `streaming_pipeline.py`, `airflow_dags/enterprise_network_dag.py` |
| API | `main.py` (FastAPI), routes: `companies`, `analytics`, `graph_api`, `ai_api` |
| Tests | `test_graph.py`, `test_analytics.py` |


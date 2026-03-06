# Claude Coding Guide

Tài liệu này dành cho agent hoặc lập trình viên dùng Claude để code trong repo `enterprise-network-analytics`.

## Mục tiêu dự án

Xây dựng nền tảng phân tích mạng lưới doanh nghiệp với các lớp chính:

- Ingestion: thu thập dữ liệu từ Kafka, batch files, và các nguồn crawl bên ngoài.
- Processing: ETL bằng PySpark và Delta Lake.
- Graph: nạp dữ liệu vào Neo4j và chạy thuật toán GDS.
- Analytics: fraud detection, ownership, risk scoring, supply chain.
- AI: hỏi đáp và embedding trên graph.
- API: FastAPI để expose dữ liệu và tác vụ.

## Stack chính

- Python 3.11+
- FastAPI
- PySpark 3.5
- Neo4j 5 + Graph Data Science
- Kafka + Confluent stack
- MLflow
- MinIO
- Airflow
- HTTP crawling: `httpx`, `aiohttp`, `beautifulsoup4`, `crawl4ai`, `playwright`

## Cấu trúc repo cần nhớ

- `api/`: entrypoint API và routes.
- `analytics/`: logic phân tích nghiệp vụ.
- `ai/`: tích hợp LLM và graph embedding.
- `config/`: settings và kết nối hạ tầng.
- `graph/`: load/query/algorithms cho Neo4j.
- `ingestion/`: producer/consumer và crawlers.
- `pipeline/`: orchestration batch, streaming, Airflow DAG.
- `processing/`: Spark ETL jobs và transformers.
- `tests/`: test analytics và graph.

## Các entrypoints quan trọng

- API app: `uvicorn api.main:app --reload --port 8000`
- Batch pipeline: `python -m pipeline.batch_pipeline`
- Streaming pipeline: `python -m pipeline.streaming_pipeline`
- Test: `pytest`
- Dev stack: `docker compose up -d`

## Module map theo loại task

### 1. Thêm hoặc sửa API

- Sửa route trong `api/routes/`.
- Đăng ký router trong `api/main.py`.
- Nếu cần schema request/response đơn giản, ưu tiên đặt gần route bằng Pydantic model.
- Giữ API style hiện tại: route rõ ràng, docstring ngắn, lỗi trả về bằng `HTTPException`.

### 2. Thêm analytics mới

- Đặt logic ở `analytics/` theo domain.
- Không nhét business logic nặng vào route FastAPI.
- Nếu analytics cần graph data, tách phần query Neo4j sang `graph/graph_queries.py` hoặc module graph liên quan.
- Nếu analytics là rule-based, ưu tiên output có cấu trúc, có score và evidence.

### 3. Thêm graph algorithms hoặc graph queries

- Query wrappers: `graph/graph_queries.py`.
- GDS algorithms: `graph/algorithms/graph_algorithms.py`.
- Giữ naming nhất quán với Neo4j labels, relationship types, và property names hiện có.
- Không hardcode bừa bãi tên graph projection nếu đã có config hoặc constant dùng lại được.

### 4. Thêm crawler hoặc nguồn dữ liệu mới

- Base abstractions nằm ở `ingestion/crawlers/base_crawler.py`.
- Mỗi nguồn nên có module riêng trong `ingestion/crawlers/`.
- Đăng ký crawler trong `ingestion/crawlers/crawler_pipeline.py`.
- Nếu cần expose qua API, thêm route ở `api/routes/crawl_api.py`.
- Settings liên quan nguồn dữ liệu phải thêm vào `config/settings.py`.
- Kết quả crawler nên chuẩn hóa về các nhóm entity như `companies`, `persons`, `relationships`, `errors`.

### 5. Sửa ETL hoặc data processing

- Spark ETL jobs ở `processing/spark_jobs/`.
- Transform logic chung ở `processing/transformers/`.
- Phân biệt rõ raw data, processed data, và graph-ready data.

### 6. Sửa orchestration

- Batch flow: `pipeline/batch_pipeline.py`.
- Streaming flow: `pipeline/streaming_pipeline.py`.
- Scheduler: `pipeline/orchestration/airflow_dags/enterprise_network_dag.py`.

## Quy ước coding cho repo này

- Ưu tiên sửa đúng gốc vấn đề, không vá tạm ở route nếu lỗi nằm trong service layer.
- Giữ thay đổi nhỏ và tập trung vào task.
- Không đổi public API hoặc cấu trúc dữ liệu nếu không thật cần thiết.
- Dùng type hints đầy đủ cho code mới.
- Giữ style Python hiện tại: rõ ràng, thẳng, ít abstraction thừa.
- Dùng `loguru.logger` cho logging thay vì `print`, trừ khi file đó đã dùng `print` cho operator hoặc batch task.
- Với network calls, phải có timeout, retry hợp lý, và xử lý lỗi rõ ràng.
- Với crawler, tránh giả định HTML/API luôn ổn định; luôn code theo hướng chịu lỗi.
- Với FastAPI, validation nên làm ở Pydantic models hoặc `Query`, `Path`, `Body`.
- Với Neo4j/Cypher, tránh query nối chuỗi thủ công nếu có parameter binding.

## Quy ước khi làm việc với crawlers

- OpenCorporates là nguồn ưu tiên cho dữ liệu doanh nghiệp quốc tế.
- Các nguồn bổ sung hiện có trong repo gồm:
  - OpenSanctions
  - GLEIF
  - OpenOwnership
  - World Bank
  - Vietnam National Business Registry
- Nếu nguồn mới yêu cầu API key hoặc rate limit riêng, phải thêm env vars vào `config/settings.py` và ghi rõ trong README hoặc quick-start nếu task yêu cầu.
- Nếu crawler publish sang Kafka, dùng producer hiện có thay vì tạo client mới trùng chức năng.

## Quy ước test và validate

- Với logic thuần Python: thêm hoặc sửa test trong `tests/`.
- Với thay đổi API nhỏ: ít nhất validate import path, router registration, và schema shape.
- Với thay đổi crawler: kiểm tra code path khi API lỗi, dữ liệu rỗng, và response thiếu field.
- Với thay đổi Spark/Neo4j nặng: nếu không chạy end-to-end được, phải nêu rõ phần chưa verify.

## Lệnh hữu ích

```bash
pip install -e ".[dev]"
pytest
uvicorn api.main:app --reload --port 8000
python -m pipeline.batch_pipeline
python -m pipeline.streaming_pipeline
docker compose up -d
docker compose logs -f api
```

## Nguyên tắc khi Claude tạo code

- Đọc file liên quan trước khi sửa.
- Khi sửa nhiều lớp, giữ luồng dữ liệu nhất quán từ `config` -> `ingestion/processing` -> `graph/analytics` -> `api`.
- Không thêm framework mới nếu stack hiện tại đã đủ.
- Không tạo file tài liệu mới cho mỗi thay đổi nhỏ.
- Nếu repo đã có pattern tương tự, ưu tiên tái sử dụng pattern đó thay vì phát minh cấu trúc mới.

## Checklist trước khi kết thúc một task

- Code mới có đúng module chưa.
- Imports không tạo vòng lặp không cần thiết.
- Settings/env vars mới đã được khai báo đầy đủ.
- Router mới đã được register nếu cần.
- Test hoặc ít nhất validation cơ bản đã được chạy.
- Không vô tình làm lệch kiến trúc hiện có.

## Ghi chú thực tế

- Repo này thiên về backend/data platform, không phải web frontend.
- Chỗ cần cẩn thận nhất là tương thích giữa crawler output, Kafka message shape, Spark ETL, và Neo4j load.
- Khi thêm nguồn dữ liệu mới, ưu tiên chuẩn hóa schema sớm thay vì đẩy dữ liệu không đồng nhất xuống các layer sau.
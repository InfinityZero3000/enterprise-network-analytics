# SUBMISSION CHECKLIST - 1 PAGE

Project: Enterprise Network Analytics
Student: __________________________
Class: ____________________________
Date: _____________________________
Repository branch: feature/nguyenthang

## A. DATA (Must be real and source-clear)

Status: [ ] Pass  [ ] Need fix

- [ ] A1. Data source list is documented (API/web source, free/paid, key needed or not)
  Evidence ref: [api/routes/crawl_api.py](../api/routes/crawl_api.py)
- [ ] A2. Env/source config is documented
  Evidence ref: [.env.example](../.env.example)
- [ ] A3. Real crawled data file exists
  Evidence ref: [crawler_outputs/gleif_data.json](../crawler_outputs/gleif_data.json), [dataset/crawl4ai/latest_summary.json](../dataset/crawl4ai/latest_summary.json)
- [ ] A4. Screenshot attached: Data source + sample records
  Image file: img_01_data_source_and_sample.png
  Insert note: _______________________________________________

## B. PIPELINE (Ingest -> Storage -> Processing -> Result)

Status: [ ] Pass  [ ] Need fix

- [ ] B1. Ingest endpoint exists and is callable
  Evidence ref: [api/routes/crawl_api.py](../api/routes/crawl_api.py)
- [ ] B2. Storage layer exists (MinIO raw/processed)
  Evidence ref: [ingestion/batch_ingestion.py](../ingestion/batch_ingestion.py)
- [ ] B3. Processing layer exists (Spark ETL/streaming)
  Evidence ref: [processing/spark_jobs/company_etl.py](../processing/spark_jobs/company_etl.py), [pipeline/streaming_pipeline.py](../pipeline/streaming_pipeline.py)
- [ ] B4. Infra containers up (Kafka, Spark, Neo4j, MinIO)
  Evidence ref: [docker-compose.yml](../docker-compose.yml)
- [ ] B5. Screenshot attached: pipeline run command + successful response
  Image file: img_02_pipeline_run_sync.png
  Insert note: _______________________________________________

## C. OUTPUT (Table/chart/analysis)

Status: [ ] Pass  [ ] Need fix

- [ ] C1. Crawl KPI/history output is visible
  Evidence ref: [ui/src/components/CrawlManager.tsx](../ui/src/components/CrawlManager.tsx)
- [ ] C2. Graph/analytics visualization is visible
  Evidence ref: [ui/src/components/GraphExplorer.tsx](../ui/src/components/GraphExplorer.tsx), [ui/src/components/ExecutiveDashboard.tsx](../ui/src/components/ExecutiveDashboard.tsx)
- [ ] C3. Screenshot attached: dashboard or graph output
  Image file: img_03_ui_output_kpi_or_graph.png
  Insert note: _______________________________________________

## D. LOG EVIDENCE (Critical for demo section)

Status: [ ] Pass  [ ] Need fix

- [ ] D1. Kafka terminal log screenshot
  Suggested command: docker logs -f --tail 60 ena-kafka
  Image file: img_04_kafka_log_terminal.png
- [ ] D2. Spark processing and flagging terminal screenshot
  Suggested command: SPARK_MASTER_URL=local[*] python scripts/demo_spark_log.py
  Must show keywords: [Processing], [Flagging], Batch table output
  Image file: img_05_spark_processing_flagging.png
- [ ] D3. Cypher query screenshot (live query result)
  Suggested command 1: docker exec -i ena-neo4j cypher-shell -u neo4j -p ena_password "MATCH (c:Company) RETURN count(c) AS total_companies;"
  Suggested command 2: docker exec -i ena-neo4j cypher-shell -u neo4j -p ena_password "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt ORDER BY cnt DESC LIMIT 10;"
  Image file: img_06_cypher_query_results.png
- [ ] D4. Optional extra screenshot for strong evidence (real record query)
  Suggested command: docker exec -i ena-neo4j cypher-shell -u neo4j -p ena_password "MATCH (c:Company) WHERE c.name CONTAINS 'NVIDIA' RETURN c.company_id AS company_id, c.name AS name, c.country AS country LIMIT 5;"
  Image file: img_07_cypher_real_record.png

## E. FINAL 30-SECOND CHECK BEFORE SUBMIT

- [ ] Data is real and source-clear
- [ ] Pipeline flow is complete end-to-end
- [ ] At least 1 concrete output (table/chart/analysis)
- [ ] Terminal logs are attached (Kafka + Spark)
- [ ] Cypher query result screenshot is attached
- [ ] Image file names follow template img_01 ... img_07

Result: [ ] READY TO SUBMIT  [ ] NEED ONE MORE FIX
Reviewer notes: _______________________________________________


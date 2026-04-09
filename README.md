# Enterprise Network Analytics

## System Overview

Enterprise Network Analytics is an advanced analytics and visualization platform dedicated to mapping and analyzing complex relational networks between economic entities, including corporations, individuals, addresses, and assets.

The core objective of the system is to untangle complex corporate structures, cross-ownership networks, and shell entities. By leveraging Graph Data Science and Generative Artificial Intelligence (GenAI), the platform enables the detection of hidden risks, fraudulent behaviors, and compliance violations within large-scale enterprise datasets.

---

## Core Capabilities

### 1. Graph Explorer and Visualization
* **Interactive Rendering:** High-performance mapping of thousands of nodes and edges, offering real-time reflection of data mutations and network topology changes.
* **Layout Physics Interaction:** Dynamic manipulation of physical repulsion forces and edge constraints to expand or contract hyper-connected data clusters, ensuring optimal analytical visibility.
* **Focus & Filtering:** Programmable node pruning based on connection degrees and instantaneous search functionality for investigating localized network hotspots.

### 2. Fraud & Risk Detection
* **Rule Engine:** Continuous network scanning algorithms designed to trace classic violation indicators, including:
  * Mass Registration and Virtual Mailbox detection.
  * Circular Ownership architectures.
  * Super-connected Proxies acting as operational fronts.
* **Risk Prioritization:** Systematic categorization of risk levels (Low, Medium, High, Critical) to streamline and prioritize compliance investigation workflows.

### 3. Ownership Structure Analysis
* Algorithmic computation and retrieval of Ultimate Beneficial Owners (UBO), systematically dissecting multi-layered, cross-border ownership hierarchies.

### 4. Enterprise GenAI Assistant
* Integration of a Natural Language Processing (NLP) interface, allowing users to query and interrogate the data network directly.
* Agnostic support for premier LLM platforms (Gemini, Llama/Groq, OpenAI) configured to translate mathematical graph interactions into comprehensive, actionable business intelligence summaries.

---

## Applied Theories and Algorithms

The system is engineered upon the fundamental academic principles of Network Science and modern Data Analytics:

### 1. Graph Data Science (GDS)
The platform utilizes specialized graph computing engines to execute analytical operations beyond the capabilities of traditional Relational Database Management Systems (RDBMS):
* **Centrality Algorithms (PageRank & Degree Centrality):** Evaluates the concentration of influence or capital flow. High centrality scores indicate "Hubs" orchestrating financial or informational streams across macro networks.
* **Weakly Connected Components (WCC):** Identifies disparate sub-networks within the macro graph—critical for discovering hidden economic conglomerates that appear functionally independent but are structurally linked via shared proxy nodes.
* **Path Finding:** Deploys shortest-path traversal heuristics to uncover sophisticated, concealed topologies between targeted entities.

### 2. GraphRAG (Retrieval-Augmented Generation on Graphs)
Distinguished from standard Vector Similarity RAG architectures, this system implements **GraphRAG**:
* The AI engine utilizes semantic context to generate structural graph queries (e.g., Cypher syntax), dynamically extracting precise topological sub-graphs.
* By analyzing exact nodes and deterministic relationship sequences from the primary database, the AI strictly mitigates data hallucination, yielding definitive intelligence and natural language analysis of deterministic cross-ownership constraints.

### 3. Risk Scoring Model
Standardized against modern Anti-Money Laundering (AML) and Know Your Customer (KYC) risk assessment methodologies:
* **Seed Risk:** Deterministic identification of base entities against international blacklists, Politically Exposed Persons (PEPs) databases, and sanctioned registries.
* **Risk Propagation:** Stochastic risk scores propagate and systematically decay as they traverse child nodes in the graph topology. For instance, a subsidiary definitively tied to a sanctioned parent entity mathematically inherits linked infected risk constraints.

---

## Technology Stack

The platform is built on a modern, highly scalable data engineering and machine learning architecture:

### 1. Data Engineering & Storage
* **Graph Database:** Neo4j (Enterprise Graph Data Science logic)
* **Big Data Processing:** Apache Spark (PySpark) & Delta Lake
* **Streaming & Messaging:** Apache Kafka (Confluent ecosystem)
* **Object Storage:** MinIO (S3-compatible data lake)
* **Orchestration:** Apache Airflow

### 2. Backend & Artificial Intelligence
* **API Framework:** FastAPI (Python 3.11+, Async architectures)
* **Machine Learning Tracking:** MLflow
* **Generative AI Providers:** Native integration with OpenAI, Google Gemini, and Groq LLMs via custom GraphRAG implementations.

### 3. Frontend & Visualization
* **Core Framework:** React 18, TypeScript, Vite
* **Graph Rendering:** D3.js via `react-force-graph-2d` (hardware-accelerated WebGL/Canvas layout engines)
* **Styling:** Modern CSS (Tailwind concepts and raw custom properties)

---

## Getting Started (How to Run)

The application ecosystem is fully dockerized for isolated, reproducible deployments.

### Prerequisites
* Docker Engine & Docker Compose (v2+)
* Node.js + npm (for Web UI development server)
* Minimum OS Requirements: Linux/macOS or Windows (WSL2), 8GB+ RAM recommended.

### Quick Start Deployment

**1. Clone the repository and navigate to the project directory:**
```bash
git clone https://github.com/InfinityZero3000/enterprise-network-analytics.git
cd enterprise-network-analytics
```

**2. Start everything with one command:**
```bash
bash scripts/start.sh
```

The startup script now includes first-run checks to help new users:
* Verifies required commands (`docker`, `npm`)
* Verifies Docker daemon is running
* Auto-creates `.env` from `.env.example` if missing
* Auto-installs UI dependencies in `ui/` when `node_modules` is missing
* Starts Docker services and Web UI dev server automatically

**3. Check service status (optional):**
```bash
docker compose ps
tail -f ui/ui.log
```

**4. Configure AI keys (optional):**
If you want to use the AI Assistant, open `.env` and set keys such as Gemini/Groq/OpenAI.

### AI API Key Setup (Detailed)

Use at least one provider below.

**1. Create your API key**
* Gemini: https://aistudio.google.com/app/apikey
* Groq: https://console.groq.com/keys
* OpenAI: https://platform.openai.com/api-keys
* OpenRouter (optional): https://openrouter.ai/keys

**2. Add keys to `.env`**
```bash
# Fill at least one key
GEMINI_API_KEY=
GROQ_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=

# Optional model overrides
GEMINI_MODEL=gemini-2.5-flash
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_MODEL=gpt-4o
OPENROUTER_MODEL=openai/gpt-4o-mini
```

**3. Reload backend after updating keys**
```bash
docker compose restart api
```

**4. Verify AI endpoint**
```bash
curl -X POST http://localhost:8000/api/v1/ai/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"List top 3 connected companies"}'
```

If the response includes a non-empty `answer`, AI provider integration is working.

### Accessing the Platform
Once initialized, the various graphical interfaces can be accessed at:
* **Web UI (Graph Explorer):** `http://localhost:5173`
* **API Backend (FastAPI Swagger):** `http://localhost:8000/docs`
* **Neo4j Browser:** `http://localhost:7474`
* **Kafka UI:** `http://localhost:8080`

### Stop All Services
```bash
bash scripts/stop.sh
```

## Real Data Pipeline (API + Crawl4AI)

When some API providers are unstable, run a practical hybrid pipeline with:

1. `gleif` (stable public LEI API)
2. `crawl4ai_company_pages` (crawl public aggregate company pages)

### Run synchronous crawl only

```bash
curl -X POST http://localhost:8000/api/v1/crawl/run/sync \
  -H 'Content-Type: application/json' \
  -d '{
    "sources": ["gleif", "crawl4ai_company_pages"],
    "parallel": true,
    "source_options": {
      "gleif": {"countries": ["VN", "SG", "HK"], "max_pages": 3},
      "crawl4ai_company_pages": {"cmc_pages": 2, "max_companies": 80, "fetch_profiles": true}
    }
  }'
```

### Run full ETL (crawl -> quality gate -> Neo4j)

```bash
curl -X POST http://localhost:8000/api/v1/crawl/etl/run/sync \
  -H 'Content-Type: application/json' \
  -d '{
    "sources": ["gleif", "crawl4ai_company_pages"],
    "parallel": true,
    "dry_run": false,
    "source_options": {
      "gleif": {"countries": ["VN", "SG", "HK"], "max_pages": 3},
      "crawl4ai_company_pages": {"cmc_pages": 2, "max_companies": 80, "fetch_profiles": true}
    }
  }'
```

### Storage and visualization outputs

* Raw crawl payloads are uploaded to MinIO bucket `ena-raw/<source>/...`.
* Crawl4AI snapshot is written locally to:
  * `dataset/crawl4ai/latest_companies.ndjson`
  * `dataset/crawl4ai/latest_companies.pretty.json`
  * `dataset/crawl4ai/latest_summary.json`
* Cleaned entities/relationships are loaded to Neo4j via ETL route.
* In UI, open `Crawl Manager` to run sources and inspect pipeline KPIs/history.

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
* Minimum OS Requirements: Linux/macOS or Windows (WSL2), 8GB+ RAM recommended.

### Quick Start Deployment

**1. Clone the repository and navigate to the project directory:**
```bash
git clone https://github.com/InfinityZero3000/enterprise-network-analytics.git
cd enterprise-network-analytics
```

**2. Initialize environmental configurations:**
```bash
cp .env.example .env
# Edit .env with your specific API Keys (Gemini, Groq, OpenAI) if utilizing the AI Assistant.
```

**3. Launch the full data infrastructure and backend API:**
Using the provided multi-container setup via Docker Compose:
```bash
bash scripts/start.sh
# Alternatively: docker compose up -d
```

**4. Start the Frontend Web UI:**
In a separate terminal, navigate to the `ui` directory and start the Vite development server:
```bash
cd ui
npm install
npm run dev
```

### Accessing the Platform
Once initialized, the various graphical interfaces can be accessed at:
* **Web UI (Graph Explorer):** `http://localhost:5173`
* **API Backend (FastAPI Swagger):** `http://localhost:8000/docs`
* **Neo4j Browser:** `http://localhost:7474`
* **Kafka UI:** `http://localhost:8080`

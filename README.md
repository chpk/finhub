# FinHub -- AI-Powered Financial Reporting Compliance Engine

An end-to-end AI compliance validation platform built for the **IndiaAI NFRA (National Financial Reporting Authority) Challenge**. FinHub ingests regulatory PDF documents and financial statements, extracts structured data using advanced OCR and table detection, stores document embeddings in a vector database for semantic retrieval, and validates each document section against Indian regulatory frameworks using a multi-phase, research-assistant-style AI pipeline. The system produces explainable compliance and non-compliance reports with rule citations, evidence excerpts, and actionable recommendations.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Architecture](#solution-architecture)
3. [Key Features](#key-features)
4. [Technology Stack](#technology-stack)
5. [Project Structure](#project-structure)
6. [Compliance Data Corpus](#compliance-data-corpus)
7. [AI and Agent Architecture](#ai-and-agent-architecture)
8. [Application Pages and Features](#application-pages-and-features)
9. [Installation and Setup](#installation-and-setup)
10. [Running the Application](#running-the-application)
11. [Docker Deployment](#docker-deployment)
12. [API Reference](#api-reference)
13. [Configuration Reference](#configuration-reference)
14. [Methodology and Approach](#methodology-and-approach)

---

## Problem Statement

**(Stage 1) -- AI Engine for Compliance Gaps**

Build an AI-powered engine capable of:

- Extracting text, tables, hyperlinks, embedded data, and financial data from multi-format document sources in both scanned and digital versions.
- Segmenting documents into logical, header-based sections with appropriate metadata tagging.
- Validating each section's completeness, integrity, and compliance against pre-defined regulatory frameworks.
- Structuring document metadata to support search, analytics, visualisation, and indexing of source unstructured data for efficient retrieval and referenceability.
- Generating an explainable compliance validation report indicating the dataset's compliance and non-compliance with each provision of the applicable rules and regulations.

The engine is configurable for testing compliance across large volumes of structured or unstructured datasets against a corresponding set of regulations including Indian Accounting Standards (Ind AS), SEBI disclosure requirements, RBI Disclosure Norms, SEBI ESG/BRSR Framework, Schedule III, and Auditing Standards.

---

## Solution Architecture

```
                         +------------------+
                         |   Next.js 14+    |
                         |   Frontend       |
                         |  (Port 3000)     |
                         +--------+---------+
                                  |
                              REST API
                                  |
                         +--------+---------+
                         |   FastAPI        |
                         |   Backend        |
                         |  (Port 8888)     |
                         +---+----+----+----+
                             |    |    |
                +------------+    |    +------------+
                |                 |                  |
        +-------+------+  +------+-------+  +-------+------+
        |  MongoDB     |  |  ChromaDB    |  |  OpenAI API  |
        |  Atlas       |  |  (Vector DB) |  |  GPT-4.1     |
        |              |  |              |  |  Embeddings  |
        +--------------+  +--------------+  +--------------+
```

**Data Flow:**

1. User uploads a financial PDF through the frontend.
2. The backend sends the document to the OCR and table extraction API for high-resolution processing.
3. Extracted elements (text blocks, tables, headers, figures) are classified, enriched with metadata, and stored in MongoDB.
4. A smart chunking engine segments the document into semantically coherent chunks that preserve section boundaries and table integrity.
5. Each chunk is embedded using OpenAI `text-embedding-3-large` and stored in ChromaDB alongside its metadata.
6. During compliance checking, the five-phase AI engine decomposes the document, generates targeted compliance queries, retrieves relevant regulatory rules from the vector database, evaluates each rule with chain-of-thought reasoning, and synthesises a scored report.
7. Reports are available as interactive views in the UI, or as downloadable PDF, JSON, and Excel exports.

---

## Key Features

### Document Processing
- High-resolution OCR processing of scanned and digital PDFs with automatic layout detection.
- HTML-preserving table extraction with column/row header identification and financial statement type detection (Balance Sheet, Profit and Loss, Cash Flow Statement).
- Hierarchical section tree construction from document headers (H1/H2/H3 nesting).
- Financial data annotation: automatic extraction of currency amounts, percentages, date patterns, and XBRL element identifiers.
- Batch processing with progress tracking and status reporting.

### Compliance Validation
- Five-phase deep-research compliance engine (see [AI Architecture](#ai-and-agent-architecture) below).
- Support for seven regulatory frameworks simultaneously: Ind AS (1-116), Schedule III, SEBI LODR, RBI Norms, ESG/BRSR, Auditing Standards, and Disclosure Checklists.
- Chain-of-thought explainability: every compliance verdict includes step-by-step LLM reasoning, evidence citations from the source document, confidence scores, and recommendations.
- Real-time progress visualisation showing each phase as it executes.

### Semantic Search
- Dense vector retrieval across three ChromaDB collections (regulatory frameworks, financial documents, disclosure checklists).
- Hybrid search combining vector similarity with keyword-based document filtering.
- Query expansion and decomposition for complex multi-part questions.
- Framework-specific filtering with metadata-aware retrieval.

### Interactive Analytics Engine
- LangGraph-powered agentic workflow with a planner-executor-synthesiser loop.
- Automatic loading of extracted tables into pandas DataFrames for quantitative analysis.
- Five built-in tools the agent can invoke: `query_dataframe`, `extract_metrics`, `compare_documents`, `generate_chart`, and `search_vectors`.
- Chart generation (bar, line, pie, radar, heatmap) returned as inline images.
- Cross-document comparison, trend analysis, and financial ratio computation.

### NFRA Insight Bot (RAG Chatbot)
- Multi-turn conversational interface with session persistence.
- Query expansion and task decomposition for complex questions.
- Dense retrieval with hybrid search across all indexed collections.
- Document-scoped chat: selecting a specific indexed document restricts answers to that document's context.
- Markdown-rendered responses with bold terms, bullet lists, headings, tables, and standard citations.
- Source citations displayed as collapsible cards with page numbers, sections, and relevance scores.
- Mid-chat document upload for quick on-the-fly analysis.

### Report Generation
- **PDF Reports** (via ReportLab): cover page, executive summary, compliance matrix table, detailed findings, framework-wise breakdown, and appendix.
- **Excel Reports** (via openpyxl): multi-sheet workbook with summary, full rules table, and non-compliant items, with colour-coded status cells.
- **JSON Reports**: complete serialised compliance report including all rule checks with evidence and explanations.

### Frontend
- Apple-inspired design system: clean whitespace, subtle glassmorphism, smooth Framer Motion transitions.
- Responsive layout across desktop, tablet, and mobile.
- Client-side caching layer with configurable TTLs for all API calls.
- Skeleton loading states and toast notifications.
- Drag-and-drop file uploads with progress indicators.
- Animated circular compliance score visualisation.

---

## Technology Stack

| Layer                | Technology                                         |
| -------------------- | -------------------------------------------------- |
| **Frontend**         | Next.js 14.2, TypeScript, Tailwind CSS             |
| **UI Components**    | Radix UI, Framer Motion, Recharts, Lucide Icons    |
| **Backend**          | Python 3.12, FastAPI, Uvicorn                      |
| **Document OCR**     | Cloud Hi-Res Partition API (table extraction, OCR)  |
| **Vector Database**  | ChromaDB (persistent, multi-collection)            |
| **Embeddings**       | OpenAI `text-embedding-3-large` (3072 dimensions)  |
| **LLM**             | OpenAI GPT-4.1 via LangChain                       |
| **Agent Framework**  | LangGraph (state-graph agentic workflows)          |
| **App Database**     | MongoDB Atlas (async via Motor driver)             |
| **PDF Generation**   | ReportLab                                          |
| **Excel Generation** | openpyxl                                           |
| **Containerisation** | Docker, Docker Compose                             |

---

## Project Structure

```
nfra-compliance-engine/
|
+-- backend/
|   +-- Dockerfile
|   +-- .dockerignore
|   +-- requirements.txt
|   +-- .env                           # Environment variables (not committed)
|   +-- app/
|   |   +-- __init__.py
|   |   +-- main.py                    # FastAPI entry point, lifespan, routers
|   |   +-- config.py                  # Pydantic settings loaded from .env
|   |   +-- models/
|   |   |   +-- document.py            # MongoDB document schemas
|   |   |   +-- compliance.py          # ComplianceReport, ComplianceCheckResult
|   |   |   +-- chat.py                # ChatSession, ChatMessage, ChatSource
|   |   +-- routers/
|   |   |   +-- ingest.py              # Document upload, batch ingestion, status
|   |   |   +-- compliance.py          # Compliance check execution and reports
|   |   |   +-- search.py              # Semantic search endpoints
|   |   |   +-- reports.py             # PDF, JSON, Excel report downloads
|   |   |   +-- chat.py                # RAG chatbot endpoints
|   |   |   +-- analytics.py           # Analytics engine endpoints
|   |   |   +-- examination.py         # Preliminary examination endpoints
|   |   +-- services/
|   |   |   +-- document_processor.py  # OCR + table extraction integration
|   |   |   +-- embedding_service.py   # OpenAI embedding generation
|   |   |   +-- vector_store.py        # ChromaDB multi-collection operations
|   |   |   +-- compliance_engine.py   # 5-phase compliance validation engine
|   |   |   +-- llm_service.py         # LLM interaction (assessment, summary, Q&A)
|   |   |   +-- report_generator.py    # PDF, JSON, Excel report generation
|   |   |   +-- mongo_service.py       # Async MongoDB CRUD wrapper
|   |   |   +-- analytics_engine.py    # LangGraph agentic analytics
|   |   |   +-- examination_tool.py    # Preliminary examination service
|   |   +-- pipelines/
|   |   |   +-- ingest_pipeline.py     # End-to-end document ingestion
|   |   |   +-- compliance_pipeline.py # End-to-end compliance check
|   |   +-- utils/
|   |       +-- chunking.py            # Smart compliance-aware chunking
|   |       +-- metadata.py            # Metadata extraction helpers
|   +-- scripts/
|   |   +-- index_compliance_rules.py  # One-time script to ingest regulatory PDFs
|   +-- data/
|   |   +-- compliance_rules/          # Regulatory PDF storage (by framework)
|   +-- uploads/                       # User-uploaded document storage
|   +-- chroma_db/                     # ChromaDB persistent storage
|   +-- tests/
|       +-- test_ingest.py
|       +-- test_compliance.py
|       +-- test_search.py
|
+-- frontend/
|   +-- Dockerfile
|   +-- .dockerignore
|   +-- package.json
|   +-- next.config.js
|   +-- tailwind.config.ts
|   +-- tsconfig.json
|   +-- app/
|   |   +-- layout.tsx                 # Root layout with frosted glass navbar
|   |   +-- page.tsx                   # Dashboard / landing page
|   |   +-- globals.css                # Apple design system CSS variables
|   |   +-- providers.tsx              # React context providers
|   |   +-- ingest/page.tsx            # Document upload and management
|   |   +-- compliance/page.tsx        # Compliance checking interface
|   |   +-- reports/page.tsx           # Report viewer
|   |   +-- search/page.tsx            # Semantic search interface
|   |   +-- chat/page.tsx              # NFRA Insight Bot
|   |   +-- analytics/page.tsx         # Interactive analytics dashboard
|   |   +-- examination/page.tsx       # Preliminary examination tool
|   +-- components/
|   |   +-- chat/
|   |   |   +-- ChatWindow.tsx
|   |   |   +-- MessageBubble.tsx      # Markdown-rendered chat messages
|   |   +-- ingest/
|   |       +-- ProcessingStatus.tsx   # Upload progress visualisation
|   +-- lib/
|       +-- api.ts                     # Typed API client with caching
|       +-- types.ts                   # TypeScript interfaces
|
+-- scripts/
|   +-- ingest_compliance_rules.py     # Batch compliance rule ingestion
|   +-- seed_test_data.py              # Test data seeding
|
+-- docker-compose.yml                 # Multi-container orchestration
+-- .env.example                       # Environment variable template
+-- README.md
```

---

## Compliance Data Corpus

The system is pre-loaded with regulatory documents organised into seven framework categories. These static reference documents form the "rules" against which uploaded financial statements are validated.

### Framework Categories

| Folder                  | Framework ID           | Description                                                         | Documents |
| ----------------------- | ---------------------- | ------------------------------------------------------------------- | --------- |
| `IndAS_Standards/`      | IndAS                  | Indian Accounting Standards 1-116, covering financial presentation, inventories, cash flows, employee benefits, leases, revenue recognition, financial instruments, and more. | 38 PDFs |
| `Schedule_III/`         | Schedule_III           | Companies Act 2013 Schedule III governing the format and presentation of Balance Sheet, Statement of Profit and Loss, and Notes. Includes official text and ICAI guidance for both Ind AS and non-Ind AS entities. | 3 PDFs |
| `SEBI_LODR/`            | SEBI_LODR              | SEBI Listing Obligations and Disclosure Requirements Regulations 2015, including ICSI compendium and SEBI FAQs on LODR. | 2 PDFs |
| `RBI_Norms/`            | RBI_Norms              | RBI Master Directions on financial statement preparation for NBFCs and banks, prudential norms (IRAC), and third-party analysis. | 3 PDFs |
| `ESG_BRSR/`             | ESG_BRSR               | SEBI Business Responsibility and Sustainability Reporting (BRSR) framework, including original format, updated Core format, NSE filing guidelines, and balanced framework guidance. | 6 PDFs |
| `Auditing_Standards/`   | Auditing_Standards     | ICAI checklist covering 38 Standards on Auditing (SA 200-720), including auditor's report requirements and key audit matters. | 1 PDF |
| `Disclosure_Checklists/`| Disclosure_Checklists  | ICAI Ind AS Disclosure Checklist, KPMG Ind AS Disclosure Guide, ICAI Quick Referencer, Conceptual Framework, ICAI FRRB Compliance Study Vol.3, and the full Ind AS book. | 9 PDFs |

**Total: 62 regulatory PDF documents** spanning thousands of pages of Indian financial reporting standards, regulations, and checklists.

### How Compliance Rules are Indexed

1. Each PDF is processed through the OCR and table extraction pipeline to produce structured elements.
2. A compliance-aware chunker segments the content while preserving section boundaries, table integrity, and "shall"/"must" clause completeness.
3. Each chunk inherits metadata: `framework`, `source_file`, `section_path`, `page_number`, `element_type`.
4. Chunks are embedded using `text-embedding-3-large` and stored in the appropriate ChromaDB collection (`regulatory_frameworks` or `disclosure_checklists`).
5. The resulting vector index supports both dense similarity search and metadata-filtered retrieval.

---

## AI and Agent Architecture

### 1. Five-Phase Compliance Engine

The compliance validation pipeline follows a research-assistant paradigm inspired by deep research workflows. Each phase builds on the previous one.

**Phase 1 -- Document Decomposition**

The uploaded financial document is loaded from MongoDB with all its extracted elements, tables, and metadata. The engine reconstructs meaningful sections from the element stream, groups them under their header hierarchy, and identifies the document type (Annual Report, Balance Sheet, Audit Report, etc.) by analysing section names and table headers against known financial statement patterns.

**Phase 2 -- Query Decomposition (LLM-Powered)**

For each selected regulatory framework, the LLM generates specific, testable compliance queries. Rather than checking the entire framework at once, this step breaks broad compliance mandates into concrete questions such as "Does the Balance Sheet present current and non-current classification as required by Ind AS 1 Para 60?" or "Are related party transaction disclosures present as required by Ind AS 24?". This decomposition mirrors how a human auditor would plan their review.

**Phase 3 -- Iterative Retrieval**

Each generated compliance query is embedded and used to search the vector database for the most relevant regulatory rules. The engine performs iterative dense retrieval across the appropriate ChromaDB collection, deduplicates rules across queries using content hashing, and ranks results by relevance. Metadata filters narrow retrieval to the selected framework. The top rules per framework (capped to avoid rate limits) proceed to assessment.

**Phase 4 -- Chain-of-Thought Assessment**

For each rule-document pair, the LLM receives the regulatory requirement text, the relevant document sections, and any extracted tables. The model is instructed to reason step-by-step before producing a structured JSON verdict containing: compliance status (compliant / non-compliant / partially compliant / not applicable / unable to determine), confidence score (0.0-1.0), evidence quoted from the document, an explanation of the reasoning, and recommendations for remediation if applicable. Concurrency is controlled via semaphores to stay within API rate limits.

**Phase 5 -- Synthesis and Report**

All individual rule assessments are aggregated. The engine computes framework-level and overall compliance scores. The LLM generates an executive summary highlighting critical findings and priority recommendations. The complete report is stored in MongoDB and made available through the API.

### 2. LangGraph Analytics Agent

The analytics engine uses a LangGraph state-graph with three nodes arranged in a planner-executor-synthesiser loop:

```
[Planner] --> [Tool Executor] --> [Synthesiser]
    ^                |
    +----------------+  (loop if more tools are needed)
```

**Planner**: The LLM analyses the user's question and selects which tools to invoke. It can select from five tools:

- `query_dataframe` -- Execute a pandas expression on loaded tables (e.g., filtering rows, computing aggregates, pivoting).
- `extract_metrics` -- Pull standard financial ratios and KPIs (Revenue, Net Profit, EBITDA, EPS, ROE, Debt/Equity, Current Ratio).
- `compare_documents` -- Cross-document metric comparison for peer analysis or trend detection.
- `generate_chart` -- Create a Matplotlib chart (bar, line, pie, radar, heatmap) and return it as a base64-encoded PNG.
- `search_vectors` -- Semantic search over ChromaDB collections for supplementary context.

**Tool Executor**: Executes the selected tool with the arguments specified by the planner. Results (DataFrames, metric dictionaries, chart images, search results) are fed back to the agent.

**Synthesiser**: Combines all tool outputs into a coherent, human-readable answer. If the synthesiser determines more analysis is needed, it loops back to the planner.

### 3. RAG Chatbot Pipeline

The NFRA Insight Bot processes each user message through:

1. **Query Expansion**: The original question is augmented with related terms and rephrased variants to improve retrieval recall.
2. **Dense Retrieval**: The expanded query is embedded and searched across all relevant ChromaDB collections. When a specific document is selected, a `source_file` metadata filter restricts results.
3. **Context Assembly**: The top retrieved chunks (up to 15) are assembled into a context window with rich metadata annotations (source file, page number, section path, relevance score). Full chunk text is passed to the LLM.
4. **LLM Generation**: The context and conversation history are sent to GPT-4.1 with a system prompt instructing the model to cite specific standards and paragraphs, format responses in markdown, and distinguish between context-derived and general-knowledge answers.
5. **Response Formatting**: The assistant's response is stored in MongoDB, returned with source citations (text excerpt, source file, page, section, score), and rendered with full markdown support in the frontend.

### 4. Document Processing Pipeline

Each uploaded document passes through:

1. **Upload and Storage**: The file is saved to the server and a MongoDB record is created with initial status.
2. **Hi-Res OCR Partitioning**: The document is sent to the cloud API with `hi_res` strategy, enabling table structure inference, parallel page processing, and page break detection.
3. **Element Classification**: Each returned element is classified (Title, NarrativeText, Table, ListItem, Header, Footer, FigureCaption, PageBreak) and enriched with metadata.
4. **Table Processing**: Table elements receive special treatment -- HTML structure is preserved, plain-text versions are generated, column/row headers are extracted, and the table is classified as a specific financial statement type if applicable.
5. **Financial Data Annotation**: Currency amounts (INR, USD patterns), percentages, dates (DD/MM/YYYY, FY2024-25), and XBRL identifiers are extracted from each element.
6. **Section Tree Construction**: Headers are used to build a hierarchical section tree reflecting the document's logical structure.
7. **Smart Chunking**: The compliance-aware chunker segments elements while preserving section boundaries, keeping tables whole, and ensuring regulatory clauses remain intact. Each chunk inherits its parent section's metadata path.
8. **Embedding and Indexing**: All chunks are embedded using `text-embedding-3-large` and stored in the appropriate ChromaDB collection with full metadata.
9. **MongoDB Persistence**: The complete processed document record (elements, tables, sections, chunks, metadata) is stored in MongoDB for later retrieval by the compliance engine, analytics engine, and chatbot.

---

## Application Pages and Features

### Dashboard (Home Page)

The landing page provides an at-a-glance overview of the system's state:

- **Statistics Cards**: Documents Ingested, Compliance Checks Run, Average Compliance Score, and Active Frameworks, each retrieved via an optimised server-side aggregation query.
- **Recent Compliance Reports**: A table showing the 10 most recent reports with document name, score, frameworks tested, and date.
- **Quick Actions**: One-click buttons to navigate to Upload Document, Run Compliance Check, or Search Standards.

### Document Ingestion

- **Drag-and-Drop Upload**: Supports PDF, DOCX, and image files. Files can be dropped or selected via a styled upload zone.
- **Document Type Selector**: Tag uploads as Financial Statement, Audit Report, Annual Report, or Regulatory Document.
- **Processing Progress**: After upload, a status indicator shows processing stages (Uploading, Extracting Text, Identifying Tables, Generating Embeddings, Done/Failed).
- **Document List**: A sortable table of all ingested documents showing filename, type, page count, elements extracted, tables found, upload date, and processing status.

### Compliance Check

- **Document Selection**: Choose one or more ingested documents from a searchable dropdown.
- **Framework Selection**: Toggle checkboxes for each framework to include in the check:
  - Indian Accounting Standards (Ind AS 1-116)
  - Schedule III (Balance Sheet Format)
  - SEBI LODR Disclosures
  - RBI Disclosure Norms
  - BRSR / ESG Framework
  - Auditing Standards (SA 700-720)
- **Real-Time Progress**: During execution, a progress panel shows each phase as it runs, including query counts, rule retrieval progress, and assessment progress per framework.
- **Results Dashboard**:
  - Overall compliance score displayed as an animated circular progress indicator.
  - Framework-level breakdown bar chart.
  - Filterable, sortable table of all rule checks with columns: Rule, Framework, Status (colour-coded badge), Confidence, Evidence.
  - Expandable rows showing full rule text, document evidence, LLM explanation, and recommendations.
- **Report Download**: Export the full report as PDF, Excel, or JSON.

### Semantic Search

- **Search Bar**: A large, Spotlight-style search input for natural language queries.
- **Framework Filters**: Toggle pills to restrict search to specific frameworks (All, Ind AS, SEBI, RBI, BRSR, Audit Standards).
- **Results**: Cards displaying source document name and page, matched text with relevance score, and framework badge. Expandable to show full context.

### NFRA Insight Bot (Chat)

- **Session Management**: Left sidebar lists past chat sessions with timestamps. Create new sessions or resume existing ones.
- **Document Scoping**: Select a specific indexed document to restrict the bot's answers to that document's content.
- **Chat Interface**: User messages appear as right-aligned blue bubbles; bot responses appear as left-aligned white bubbles with full markdown rendering (bold, lists, headings, tables, code blocks).
- **Source Citations**: Each bot response includes collapsible source cards showing the text excerpt, source file, page number, section, and relevance score.
- **Suggested Questions**: Quick-start prompts displayed above the input field.

### Interactive Analytics

- **Document Selection**: Choose one or more ingested documents to analyse. Only documents with extracted tables are shown.
- **Question Input**: Type a natural language analytics question (e.g., "What is the revenue trend over the last 3 years?" or "Compare debt-to-equity ratios across documents").
- **Results**: The agentic engine returns formatted answers, computed metrics, and generated charts inline.
- **Charts**: Interactive Recharts visualisations (bar, line, pie, radar, heatmap) rendered directly in the browser.

### Reports Viewer

- Browse all generated compliance reports.
- View report details with interactive tables and framework breakdowns.
- Download reports in PDF, Excel, or JSON format.

---

## Installation and Setup

### Prerequisites

- **Python** 3.11 or higher
- **Node.js** 20.x or higher (with npm)
- **MongoDB** (MongoDB Atlas recommended, or a local instance)
- **API Keys**: OpenAI API key and an OCR/Table Extraction API key

### 1. Clone the Repository

```bash
git clone https://github.com/chpk/finhub.git
cd finhub/nfra-compliance-engine
```

### 2. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example and fill in your credentials:

```bash
cp ../.env.example .env
```

Edit `backend/.env` with your actual values:

```env
UNSTRUCTURED_API_KEY=your_ocr_api_key
UNSTRUCTURED_API_URL=https://api.unstructuredapp.io/general/v0/general
OPENAI_API_KEY=your_openai_api_key
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/?appName=YourApp
MONGODB_DB_NAME=nfra_compliance
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION_REGULATIONS=regulatory_frameworks
CHROMA_COLLECTION_DOCUMENTS=financial_documents
EMBEDDING_MODEL=text-embedding-3-large
LLM_MODEL=gpt-4.1
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8888
```

### 4. Compliance Rules Indexing (Automatic on First Run)

The compliance rule PDFs are included in the repository under `backend/data/compliance_rules/`. On first startup, the backend **automatically detects** that the ChromaDB vector database is empty and indexes all 62 regulatory PDFs. This process:

1. Sends each PDF to the OCR extraction API for text and table extraction.
2. Chunks the extracted content using the compliance-aware chunker.
3. Generates embeddings via OpenAI `text-embedding-3-large`.
4. Stores the embeddings in ChromaDB.

**This is fully automatic** -- no manual step is required. The first startup takes several minutes while indexing runs. Subsequent starts detect that data already exists and skip indexing entirely.

The behaviour is controlled by the `AUTO_INDEX_ON_STARTUP` setting in `.env` (default: `true`). If you prefer to index manually:

```bash
cd backend
AUTO_INDEX_ON_STARTUP=false python -m scripts.index_compliance_rules
```

The indexed data persists in `backend/chroma_db/` (or the Docker `chroma_data` volume). Deleting this directory triggers a fresh re-index on next startup.

### 5. Frontend Setup

```bash
cd ../frontend

# Install Node.js dependencies
npm install

# The frontend reads the API URL from the environment
# Default: http://localhost:8888
```

If the backend runs on a different host or port, create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8888
```

---

## Running the Application

### Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

The backend will:

1. Connect to MongoDB Atlas and warm up the connection pool.
2. Initialise ChromaDB with persistent storage.
3. Create database indexes for optimised queries.
4. **Check if compliance rules are indexed** -- if ChromaDB is empty, automatically process and index all 62 regulatory PDFs from `data/compliance_rules/`. This first-run indexing takes several minutes; subsequent starts skip it.
5. Start all service components (document processor, embedding service, LLM service, compliance engine, analytics engine).
6. Serve the API at `http://localhost:8888`.
7. Health check available at `http://localhost:8888/api/health`.

### Start the Frontend

```bash
cd frontend
npm run dev
```

The frontend will start at `http://localhost:3000`.

### Stopping the Application

```bash
# Stop the backend (if running in a terminal)
# Press Ctrl+C in the terminal, or:
pkill -f "uvicorn app.main:app"

# Stop the frontend
# Press Ctrl+C in the terminal, or:
pkill -f "next dev"
```

---

## Docker Deployment

### Building and Running with Docker Compose

The project includes Dockerfiles for both backend and frontend, and a `docker-compose.yml` for orchestrated deployment.

```bash
cd nfra-compliance-engine

# Build and start all services
docker compose up --build -d

# View logs (watch the first-run indexing progress)
docker compose logs -f backend

# Stop all services
docker compose down
```

On **first launch**, the backend container will automatically index all 62 compliance rule PDFs into ChromaDB before starting the API server. Monitor progress with `docker compose logs -f backend`. This one-time process takes several minutes. Subsequent container restarts detect the existing index and start immediately.

To force a re-index (e.g. after updating compliance rules), delete the ChromaDB volume:

```bash
docker compose down -v   # removes named volumes
docker compose up -d     # rebuilds index on next start
```

### docker-compose.yml Services

| Service      | Port | Description                                |
| ------------ | ---- | ------------------------------------------ |
| `backend`    | 8888 | FastAPI backend with all AI services       |
| `frontend`   | 3000 | Next.js production build                   |

### Persistent Volumes

- `./backend/uploads` -- Uploaded document files.
- `chroma_data` (Docker volume) -- ChromaDB vector database. Persists across restarts. Delete to trigger re-indexing.
- `./backend/data` -- Compliance rules PDFs (also baked into the Docker image).

### Backend Docker Image

The backend image includes an entrypoint script (`entrypoint.sh`) that:

1. Checks whether ChromaDB contains indexed data.
2. If empty, runs the compliance rules indexing script as a pre-flight step.
3. Then starts the uvicorn server.

The compliance rule PDFs are baked into the image under `data/compliance_rules/`, so the container is fully self-contained and does not require external file mounts to function.

### Frontend Dockerfile

Multi-stage build for minimal production image:

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## API Reference

### Base URL

```
http://localhost:8888
```

### Health Check

```
GET /api/health
Response: {"status": "healthy", "version": "0.1.0"}
```

### Dashboard

```
GET /api/dashboard/stats
Response: {
  "documents_ingested": 12,
  "compliance_checks": 5,
  "average_score": 72.4,
  "active_frameworks": 3
}
```

### Document Ingestion

| Method | Endpoint                          | Description                            |
| ------ | --------------------------------- | -------------------------------------- |
| POST   | `/api/ingest/upload`              | Upload a PDF for processing            |
| POST   | `/api/ingest/batch`               | Batch process a directory of PDFs      |
| GET    | `/api/ingest/status/{document_id}`| Get processing status for a document   |
| GET    | `/api/ingest/documents`           | List all ingested documents            |
| POST   | `/api/ingest/reindex/{document_id}` | Reprocess an existing document      |

### Compliance

| Method | Endpoint                             | Description                         |
| ------ | ------------------------------------ | ----------------------------------- |
| POST   | `/api/compliance/check`              | Run a compliance check              |
| GET    | `/api/compliance/reports`            | List all compliance reports         |
| GET    | `/api/compliance/reports/{report_id}`| Get a specific report               |
| GET    | `/api/compliance/frameworks`         | List available frameworks           |
| GET    | `/api/compliance/progress/{job_id}`  | Get real-time check progress        |

### Search

| Method | Endpoint              | Description                           |
| ------ | --------------------- | ------------------------------------- |
| POST   | `/api/search/query`   | Semantic search across collections    |
| POST   | `/api/search/similar` | Find similar document sections        |

### Reports

| Method | Endpoint                        | Description                   |
| ------ | ------------------------------- | ----------------------------- |
| GET    | `/api/reports/{report_id}/pdf`  | Download PDF report           |
| GET    | `/api/reports/{report_id}/json` | Download JSON report          |
| GET    | `/api/reports/{report_id}/excel`| Download Excel report         |
| GET    | `/api/reports/{report_id}/summary` | Get executive summary      |

### Chat

| Method | Endpoint                         | Description                        |
| ------ | -------------------------------- | ---------------------------------- |
| POST   | `/api/chat/message`              | Send a message to the chatbot      |
| POST   | `/api/chat/message/analytics`    | Analytics-aware message            |
| GET    | `/api/chat/sessions`             | List all chat sessions             |
| GET    | `/api/chat/sessions/{session_id}`| Get a specific session with history|
| DELETE | `/api/chat/sessions/{session_id}`| Delete a chat session              |

### Analytics

| Method | Endpoint                        | Description                       |
| ------ | ------------------------------- | --------------------------------- |
| GET    | `/api/analytics/documents`      | List documents with extracted data|
| POST   | `/api/analytics/query`          | Run an analytics query            |

---

## Configuration Reference

All configuration is managed through environment variables loaded via Pydantic Settings.

| Variable                       | Default                                                      | Description                                          |
| ------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------- |
| `UNSTRUCTURED_API_KEY`         | (required)                                                   | API key for the document OCR and extraction service   |
| `UNSTRUCTURED_API_URL`         | `https://api.unstructuredapp.io/general/v0/general`          | Endpoint URL for document processing                 |
| `OPENAI_API_KEY`               | (required)                                                   | OpenAI API key for embeddings and LLM                |
| `MONGODB_URL`                  | `mongodb://localhost:27017`                                  | MongoDB connection string                            |
| `MONGODB_DB_NAME`              | `nfra_compliance`                                            | MongoDB database name                                |
| `CHROMA_PERSIST_DIR`           | `./chroma_db`                                                | ChromaDB persistent storage directory                |
| `CHROMA_COLLECTION_REGULATIONS`| `regulatory_frameworks`                                      | ChromaDB collection for regulatory rules             |
| `CHROMA_COLLECTION_DOCUMENTS`  | `financial_documents`                                        | ChromaDB collection for financial documents          |
| `EMBEDDING_MODEL`              | `text-embedding-3-large`                                     | OpenAI embedding model identifier                    |
| `LLM_MODEL`                    | `gpt-4.1`                                                    | OpenAI LLM model for compliance assessment           |
| `BACKEND_HOST`                 | `0.0.0.0`                                                    | Backend server bind address                          |
| `BACKEND_PORT`                 | `8888`                                                       | Backend server port                                  |
| `NEXT_PUBLIC_API_URL`          | `http://localhost:8888`                                      | Frontend API base URL                                |

---

## Methodology and Approach

### Document Extraction and Structuring

Financial documents, particularly annual reports and regulatory filings, contain complex layouts with multi-column text, nested tables, headers at varying levels, footnotes, and embedded charts. The system uses a cloud-based hi-resolution partitioning strategy that combines layout detection with OCR to accurately extract content from both digital and scanned PDFs. Table structure inference preserves row/column relationships and outputs tables in HTML format, enabling downstream parsing and analysis.

After extraction, elements are classified by type and organised into a hierarchical section tree that mirrors the document's logical structure. Financial data annotations (currency amounts, percentages, dates) are applied automatically, and tables are classified by type (Balance Sheet, Profit and Loss, Cash Flow Statement) using pattern matching against known financial statement headers.

### Chunking Strategy

The compliance-aware chunker ensures that:

- **Section boundaries are never broken**: Chunks always belong to a single logical section.
- **Tables remain whole**: No table is ever split across chunks, as partial tables lose semantic meaning.
- **Regulatory clauses stay intact**: Text containing "shall", "must", or "required" is not broken mid-clause.
- **Metadata propagates**: Every chunk inherits its parent section path (e.g., "Ind AS 1 > Presentation of Financial Statements > Para 54"), enabling precise retrieval filtering.
- **Overlap provides context**: A 200-character overlap between consecutive text chunks ensures that boundary sentences are not lost.

### Embedding and Indexing

Chunks are embedded using OpenAI's `text-embedding-3-large` model, which produces 3072-dimensional vectors optimised for semantic similarity. These are stored in ChromaDB across three purpose-specific collections:

- **regulatory_frameworks**: All compliance rules, standards, and regulatory text.
- **financial_documents**: Uploaded financial statements and reports.
- **disclosure_checklists**: Structured disclosure requirements and checklists.

This separation allows the compliance engine to search rules and documents independently, applying appropriate metadata filters (framework, source file, section, page number) during retrieval.

### Performance Optimisations

- **MongoDB Indexes**: Indexes on `status`, `created_at`, `filename`, `report_id`, `document_id`, `session_id`, and `job_id` across relevant collections.
- **Aggregation Queries**: Dashboard statistics use MongoDB `count_documents` and `$group` aggregation instead of fetching full records.
- **Client-Side Caching**: The frontend API client implements a TTL-based cache (30-120 seconds depending on endpoint volatility) to reduce redundant network requests during navigation.
- **Concurrency Control**: LLM API calls during compliance checking are throttled via asyncio semaphores (max 2 concurrent) to stay within rate limits, with exponential backoff retry logic.

### Challenges and Mitigations

| Challenge                                     | Mitigation                                                                                                 |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| OCR accuracy on scanned financial tables       | Hi-resolution strategy with parallel page processing and table structure inference enabled.                  |
| LLM rate limits during large compliance checks | Semaphore-based concurrency control, exponential backoff retries, and capped rules per framework.           |
| Maintaining context in chunked regulatory text | Section path metadata propagation and header prepending to every chunk.                                     |
| 100% false-positive compliance scores          | Scoring excludes "not applicable" and "unable to determine" results; empty rule sets return 0% not 100%.    |
| PDF report generation system dependencies      | Switched from WeasyPrint to ReportLab (pure Python) to eliminate system library requirements.               |
| Slow dashboard loading                         | Server-side aggregation endpoint replacing multiple client-side API calls (62x measured improvement).       |

---

## License

This project was developed for the IndiaAI NFRA Challenge.

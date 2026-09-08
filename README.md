# FactMesh

> An LLM-powered Fact Knowledge Layer that extracts atomic facts from any PDF, grounds each in exact source evidence, and reasons across documents to identify corroborations, contradictions, and contextual differences.

---

## What It Does

FactMesh is a generalizable document intelligence pipeline built for the [Superjoin VIT 2026 Engineering Intern Assignment](https://superjoin.ai). It:

1. **Ingests any PDF** — splits pages into overlapping batches for context-preserving extraction
2. **Extracts atomic facts** via Gemini 2.0 Flash with structured JSON output — entity, metric, value, unit, time period, scope, and a verbatim evidence quote from the source page
3. **Embeds facts locally** using `all-mpnet-base-v2` (768-dim, no API key needed)
4. **Finds candidate pairs** across documents using pgvector HNSW cosine similarity (K=10, threshold=0.65)
5. **Reconciles pairs** via Gemini — classifies as `corroborates`, `contradicts`, `contextual_difference`, or `unrelated`, with detailed reasoning
6. **Exposes everything** via a FastAPI REST API and a Next.js UI

---

## Architecture

```
PDF File
   │
   ▼ PyMuPDF (pdf_parser.py)
   │  Extract text per page, group into 3-5 page batches
   │
   ▼ Gemini 2.0 Flash (fact_extractor.py)
   │  Structured JSON extraction: entity, metric, value, unit, 
   │  time_period, scope, evidence_quote, confidence
   │
   ▼ sentence-transformers (embedder.py)
   │  all-mpnet-base-v2 → 768-dim vectors, stored in pgvector
   │
   ▼ pgvector HNSW (matcher.py)
   │  Find top-K similar facts across documents (cosine similarity)
   │
   ▼ Gemini 2.0 Flash (reconciler.py)
   │  corroborates / contradicts / contextual_difference / unrelated
   │  with verbatim reasoning referencing both evidence quotes
   │
   ▼ FastAPI + Next.js UI
      Browse documents, facts, relationships, extraction issues
```

---

## Quick Start

### Prerequisites
- Docker Desktop (for PostgreSQL + pgvector)
- Python 3.10+
- Node.js 18+
- Google Gemini API key (free at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey))

### 1. Clone and configure
```bash
git clone https://github.com/PrathamMittal07/FACTMESH.git
cd FACTMESH

# Create your .env from the example
cp backend/.env.example backend/.env
# Edit backend/.env and add your GEMINI_API_KEY=AIza...
```

### 2. Start the database
```bash
docker compose up -d
```

### 3. Set up Python environment
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 4. Run the full demo ingestion
```bash
# From repo root — ingests all 6 starter PDFs
python scripts/seed_and_run_demo.py
```

### 5. Start the API
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 6. Start the UI
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## Starter Datasets

| Corpus | Documents | Pages |
|--------|-----------|-------|
| Delhivery | IPO Prospectus 2022, Annual Report FY24, Q4 FY24 Earnings | 227 |
| India Macroeconomy | Economic Survey 2024-25, RBI Annual Report 2024-25, IMF Article IV 2025 | 284 |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Gemini 2.0 Flash for extraction | Native JSON mode (`response_mime_type=application/json`) with `response_schema` guarantees valid structured output. Fast and cost-effective for 500+ pages. |
| `all-mpnet-base-v2` for embeddings | 768-dim, strong semantic understanding of financial/macro language. Runs 100% locally — no API cost, no data leaving the machine. |
| pgvector HNSW index | Sub-linear ANN search at any corpus size. O(log n) lookup vs O(n) brute force. |
| Two-tier confidence | <0.3 → rejected (stored as issue only). 0.3–0.6 → stored but flagged. ≥0.6 → accepted. |
| Incremental reconciliation | SHA-256 dedup prevents re-ingesting the same document. Pair-level dedup skips already-reconciled fact pairs when adding new documents. |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents` | Upload a PDF — returns document ID, starts background ingestion |
| `GET` | `/api/documents` | List all documents with status + counts |
| `GET` | `/api/documents/{id}` | Document detail with fact/issue/relationship counts |
| `GET` | `/api/facts` | List/filter facts (by document, entity, metric, type, confidence) |
| `GET` | `/api/facts/{id}` | Fact detail + all relationships |
| `GET` | `/api/relationships` | Browse relationships, filter by type |
| `GET` | `/api/issues` | Extraction issues log |
| `GET` | `/api/health` | Health check |

---

## Project Structure

```
FACTMESH/
├── backend/
│   ├── app/
│   │   ├── ingestion/        # PDF parsing + pipeline orchestration
│   │   ├── extraction/       # Gemini fact extractor + prompt schemas
│   │   ├── embeddings/       # Local sentence-transformers embedder
│   │   ├── reconciliation/   # pgvector similarity + Gemini reconciler
│   │   ├── db/               # PostgreSQL schema + SQLAlchemy models
│   │   ├── api/              # FastAPI route handlers
│   │   └── schemas/          # Pydantic response models
│   └── requirements.txt
├── frontend/                 # Next.js 14 App Router UI
├── docker-compose.yml        # PostgreSQL 16 + pgvector
├── scripts/
│   ├── seed_and_run_demo.py  # End-to-end demo ingestion
│   └── reset_db.py           # Wipe + reinitialise database
└── sample_data/              # 6 starter PDFs
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | **Required.** Get from aistudio.google.com |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Swap to `gemini-1.5-pro` for higher quality |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Matches docker-compose defaults |
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Local sentence-transformers model |
| `SIMILARITY_THRESHOLD` | `0.65` | Min cosine similarity for candidate pairs |
| `SIMILARITY_K` | `10` | Top-K candidates per fact |
| `CONFIDENCE_FLAG_THRESHOLD` | `0.6` | Below this: fact is stored + flagged |
| `CONFIDENCE_REJECT_THRESHOLD` | `0.3` | Below this: fact rejected, stored as issue |
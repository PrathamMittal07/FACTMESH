# FactMesh

> An LLM-powered Fact Knowledge Layer that extracts atomic facts from any PDF, grounds each in exact source evidence, and reasons across documents to identify corroborations, contradictions, and contextual differences.

---

## What It Does

FactMesh is a generalizable document intelligence pipeline built for the [Superjoin VIT 2026 Engineering Intern Assignment](https://superjoin.ai). It:

1. **Ingests any PDF** — splits pages into context-preserving batches for extraction
2. **Extracts atomic facts** via Gemini (model configurable via `GEMINI_MODEL`, default `gemini-3.6-flash`) with structured JSON output — entity, metric, value, unit, time period, scope, and a verbatim evidence quote from the source page
3. **Embeds facts locally** using `all-mpnet-base-v2` (768-dim, no API key needed)
4. **Finds candidate pairs** across documents using pgvector HNSW cosine similarity (effective local tuning K=1, threshold=0.87; code defaults K=10/0.85)
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
    ▼ Gemini (fact_extractor.py)
   │  Structured JSON extraction: entity, metric, value, unit, 
   │  time_period, scope, evidence_quote, confidence
   │
   ▼ sentence-transformers (embedder.py)
   │  all-mpnet-base-v2 → 768-dim vectors, stored in pgvector
   │
   ▼ pgvector HNSW (matcher.py)
   │  Find top-K similar facts across documents (cosine similarity)
   │
   ▼ Gemini (reconciler.py)
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
# Edit backend/.env and add your GEMINI_API_KEY (AIza... and newer AQ... formats both work)
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

### 4. Run the demo ingestion
```bash
# From repo root — ingests PDFs in sample_data/ (local-only folder;
# see "Setup and Run Instructions" below for details and quota notes)
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
| Gemini (configurable; `gemini-3.6-flash` default) for extraction | Native JSON mode (`response_mime_type=application/json`) with `response_schema` guarantees valid structured output. Fast and cost-effective for 500+ pages. |
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

## Setup and Run Instructions

> This expands the `Quick Start` above with the details you need when something doesn't work first try.

### Prerequisites
- Docker Desktop (PostgreSQL 16 + pgvector via `docker-compose.yml`)
- Python 3.10+ (3.13.2 used here); project venv at `backend/venv`
- Node.js 18+ (24.x used here)
- A Google Gemini API key ([aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)). Both `AIza…` and newer `AQ.…` key formats work.

### 1. Configure
```bash
git clone https://github.com/PrathamMittal07/FACTMESH.git
cd FACTMESH
cp backend/.env.example backend/.env
# Edit backend/.env and set GEMINI_API_KEY (never commit this file)
```

### 2. Start the database
```bash
docker compose up -d
# Postgres on localhost:5432 (user/pass/db: factmesh), pgvector enabled
```

### 3. Python environment
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
> Windows note: `python` is generally not on PATH — invoke `backend\venv\Scripts\python.exe` from the repo root for all scripts below.

### 4. Ingest documents (pick one)
```bash
# Option A — batch ingest the starter set from the repo root:
backend\venv\Scripts\python.exe scripts/seed_and_run_demo.py
# Option B — upload individual PDFs through the UI (see step 6).
```
Ingestion is incremental and idempotent: SHA-256 dedup skips already-ingested files, so re-running the seed script only processes new documents. Each run prints per-document fact/relationship counts plus a final summary. Expect roughly 1–2 minutes per ~30 pages on free-tier quota (the pipeline paces itself with `LLM_BATCH_DELAY_SEC` and aborts fast with a clear error if quota is exhausted — see Limitations). The 6 starter PDFs (~511 pages total) live in `sample_data/` **locally only** — that folder is gitignored, so after a fresh clone, add your own PDFs there or use UI upload.

### 5. Start the API
```bash
# From repo root (--app-dir puts backend/ on the import path):
backend\venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
# Health check: http://localhost:8000/api/health
```

### 6. Start the UI
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Useful commands
```bash
backend\venv\Scripts\python.exe scripts/reset_db.py   # wipe DB and re-run schema (clean slate)
docker compose ps                                     # check factmesh-db health
```

---

## Video Demo

**[VIDEO LINK HERE]** — *to be added after recording (≤3 min).*

Recorded walkthrough script (matches `docs/demo_cases.md` exactly):
1. **Corroboration** — India's forex reserves, Sept 2024: Economic Survey (704.9 USD Bn) vs IMF Article IV ($706Bn) → `corroborates` on rounding.
2. **Contradiction** — Global GDP growth 2023: Economic Survey (3.3%) vs **the RBI Annual Report quoting IMF figures** (3.5%) → `contradicts`, flagged for analyst review. (Note: Fact B's document is the RBI report, not the IMF report itself.)
3. **Contextual difference** — India real GDP FY25: Survey advance estimate (6.4%) vs IMF (6.5%) → `contextual_difference`, different vintage/methodology, not a true conflict.
4. **Graceful failure** — Delhivery Annual Report hit a live 429 quota wall mid-run: fail-fast abort, 1036 extracted facts preserved, clean `extraction_issues` entry.

---

## Approach

1. **Parse** — PyMuPDF extracts text page-by-page; pages are grouped into small sequential batches (3–5 pages) to preserve context within LLM context limits. Image-only pages are logged as issues, not silently dropped.
2. **Extract** — Each batch goes to Gemini in JSON mode (`response_mime_type` + `response_schema`), returning atomic facts: entity, metric, value, unit, time period, scope, a **verbatim** evidence quote, and a self-reported confidence. The prompt is fully generic — no company names, domains, or document types are hardcoded anywhere.
3. **Embed (local)** — `all-mpnet-base-v2` (768-dim, runs on CPU, no API cost) vectors each fact's composite text; vectors live in PostgreSQL via pgvector HNSW.
4. **Match** — For each new fact, pgvector cosine search finds candidates across *other* documents (effective local tuning K=1, threshold 0.87, tightened under free-tier quota pressure; code defaults K=10/0.85). No LLM is spent on obviously-unrelated pairs.
5. **Reconcile** — Each candidate pair goes back to Gemini with both evidence quotes; it returns `corroborates` / `contradicts` / `contextual_difference` / `unrelated` plus reasoning that must cite both sides. Only non-`unrelated` pairs are stored.
6. **Serve** — FastAPI (`/api/documents`, `/api/facts`, `/api/relationships`, `/api/issues`) + Next.js UI with evidence always one click away.
7. **Quality gates** — Two-tier confidence: <0.3 → stored as an issue only; 0.3–0.6 → stored but flagged; ≥0.6 → accepted. Free-tier pacing plus fail-fast retry (no silent multi-hour retry loops) and a second-key fallback (`GEMINI_API_KEY_2`) keep long runs survivable.

---

## Limitations (read before judging the numbers)

- **Doc 2 (Delhivery Annual Report FY24) is only ~4% reconciled.** Extraction finished and 1036 facts were preserved by design (commit-after-extraction), but a Gemini 429 quota abort killed reconciliation early: only 38 of its 1036 facts appear in any relationship (23 contextual, 14 corroborating, 1 contradicting). The remaining ~96% were never compared — absence of a relationship here means "not attempted," not "no relation found."
- **Curated-demo coverage is narrowed by quota, not by design.** The IPO Prospectus (655 facts) was excluded from `docs/demo_cases.md`; the RBI Annual Report appears **only** in Case 2 (and note: Case 2's Fact B is the RBI report *citing* IMF figures — it is not the IMF document itself). Cases 1 and 3 are the Survey↔IMF pair.
- **One mislabeled issue type.** The quota abort on Doc 2 is logged as `issue_type = 'parse_error'` with a 429 detail string. It is not a content parse failure; the label is kept as-is for traceability and narrated honestly (see Case 4).
- **Quota shaped the tuning.** Free-tier limits forced the fallback model (`gemini-3.5-flash-lite` in the local `.env`; `gemini-3.6-flash` remains the configured default) and the tightened matcher (K=1 / 0.87). With billed quota, K=10 and larger batches would raise recall.
- **Scope.** English, text-extractable PDFs; scanned/image-only pages yield issues, not facts. Single-machine Postgres; no auth, no multi-user handling — this is an assignment-grade demo, not a hosted product.

---

## Additional Notes

- **Start here for review:** `docs/demo_cases.md` (the 4 video cases, each DB-verified), `docs/architecture.md` (schema + design decisions), `EXECUTION_LOG.md` (timestamped build history, including every quota incident and fix).
- **Repo hygiene:** `backend/.env`, `sample_data/*.pdf`, `node_modules/`, and `.next/` are gitignored and never committed. `sample_data/` is intentionally local-only (~20 MB of PDFs) — graders supply their own documents.
- **If ingestion stalls:** check `GET /api/issues` first — quota aborts land there with the server's message. Documents stuck in `processing` with no Python process running are stale (this happened twice; fixed by setting status directly — facts are preserved, safe to mark `failed`).
- **Key files:** pipeline orchestration `backend/app/ingestion/pipeline.py`, retry/pacing `backend/app/llm_retry.py`, prompts `backend/app/extraction/prompts.py`, matcher `backend/app/reconciliation/matcher.py`.

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
├── frontend/                 # Next.js 16.3.4 App Router UI
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
| `GEMINI_MODEL` | `gemini-3.6-flash` | Local `.env` may pin `gemini-3.5-flash-lite` as a free-tier fallback |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Matches docker-compose defaults |
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Local sentence-transformers model |
| `SIMILARITY_THRESHOLD` | `0.87` | Min cosine similarity (effective local value; code default 0.85) |
| `SIMILARITY_K` | `1` | Top-K candidates per fact (effective local value; code default 10) |
| `CONFIDENCE_FLAG_THRESHOLD` | `0.6` | Below this: fact is stored + flagged |
| `CONFIDENCE_REJECT_THRESHOLD` | `0.3` | Below this: fact rejected, stored as issue |
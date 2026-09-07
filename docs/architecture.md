# FactMesh — Architecture

## System Architecture

```
                    +----------------------+
   PDF upload  ---> |  Ingestion Service    |
   (API/UI)         |  - PyMuPDF text+layout|
                    |  - page-level chunks  |
                    +----------+-----------+
                               |
                    +----------v-----------+
                    |  Fact Extraction      |
                    |  (Claude claude-sonnet-4-6,  |
                    |   structured tool-use)|
                    |  per chunk/page       |
                    +----------+-----------+
                               |  candidate facts
                    +----------v-----------+
                    |  Embedding Service    |
                    |  (sentence-transformers|
                    |   all-mpnet-base-v2)  |
                    +----------+-----------+
                               |
                    +----------v-----------+
                    |  Postgres + pgvector  |
                    |  facts + embeddings   |
                    +----------+-----------+
                               |  similarity search
                    +----------v-----------+
                    |  Reconciliation Engine|
                    |  (Claude compares     |
                    |   candidate pairs,    |
                    |   classifies relation)|
                    +----------+-----------+
                               |
                    +----------v-----------+
                    |  relationships table  |
                    |  (corroborate /       |
                    |   contradict /        |
                    |   contextual)         |
                    +----------+-----------+
                               |
              +----------------+------------------+
              |  FastAPI (REST)                    |
              +----------------+------------------+
                               |
                    +----------v-----------+
                    |  Next.js UI           |
                    |  upload / browse /    |
                    |  evidence / relations |
                    +-----------------------+
```

## Data Model (PostgreSQL + pgvector)

### documents
One row per uploaded PDF.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| filename | TEXT | Original filename |
| uploaded_at | TIMESTAMP | Upload time |
| page_count | INT | Total pages |
| status | TEXT | 'processing' / 'done' / 'failed' |
| sha256 | TEXT UNIQUE | Dedup: prevents re-ingesting same file |

### facts
One row per extracted atomic fact.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| document_id | UUID FK | -> documents.id |
| page_number | INT | Source page |
| fact_type | TEXT | 'numeric' / 'semantic' / 'status' / ... (LLM-assigned) |
| entity | TEXT | What/who the fact is about |
| metric | TEXT | e.g. "Revenue from Operations" |
| value | TEXT | Raw value as stated |
| normalized_value | NUMERIC | Parsed numeric, NULL if not applicable |
| unit | TEXT | e.g. "INR lakh", "%" |
| time_period | TEXT | e.g. "FY24", "Q4 FY24" |
| scope | TEXT | e.g. "standalone", "consolidated" |
| evidence_quote | TEXT | Short verbatim span from source page |
| confidence | FLOAT | LLM's self-reported confidence 0-1 |
| attributes | JSONB | Open schema for anything else |
| embedding | VECTOR(768) | pgvector column (all-mpnet-base-v2) |
| created_at | TIMESTAMP | |

### relationships
Edges between two facts.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| fact_a_id | UUID FK | -> facts.id |
| fact_b_id | UUID FK | -> facts.id |
| relationship_type | TEXT | 'corroborates' / 'contradicts' / 'contextual_difference' / 'unrelated' |
| reasoning | TEXT | LLM's explanation referencing both evidence quotes |
| confidence | FLOAT | |
| created_at | TIMESTAMP | |

### extraction_issues
Logged failures and low-confidence extractions.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| document_id | UUID FK | -> documents.id |
| page_number | INT | |
| issue_type | TEXT | 'parse_error' / 'low_confidence' / 'ambiguous_unit' / 'llm_refused' / ... |
| raw_text_snippet | TEXT | |
| detail | TEXT | |
| created_at | TIMESTAMP | |

## Key Design Decisions

1. **Open JSONB attributes**: New fact types populate different keys in ttributes — no migration needed. This satisfies "schema evolves dynamically."

2. **Candidate-pair matching via pgvector**: Don't compare every fact to every fact with an LLM call. Use cosine similarity (K=10, threshold=0.65) to shortlist, then only send shortlisted pairs to Claude.

3. **Two-tier confidence**: Facts below 0.6 confidence are flagged; below 0.3 are stored as issues only (not asserted as facts). Both render distinctly in the UI.

4. **Incremental ingestion**: New documents only match against existing facts — no re-processing of old documents.

5. **Idempotency**: SHA-256 dedup prevents re-ingesting the same PDF.

## API Surface

| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/documents | Upload PDF, trigger background ingestion |
| GET | /api/documents | List documents + status |
| GET | /api/documents/{id} | Document detail + counts |
| GET | /api/facts | List/filter facts |
| GET | /api/facts/{id} | Fact detail with evidence |
| GET | /api/facts/{id}/relationships | Relationships for a fact |
| GET | /api/relationships | Browse all relationships |
| GET | /api/issues | List extraction issues |

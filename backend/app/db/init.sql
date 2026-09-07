-- FactMesh Database Schema
-- Executed automatically on first docker compose up via /docker-entrypoint-initdb.d/

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- documents: one row per uploaded PDF
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename TEXT NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    page_count INT,
    status TEXT NOT NULL DEFAULT 'processing',
    sha256 TEXT UNIQUE NOT NULL
);

-- facts: one row per extracted atomic fact
CREATE TABLE facts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT NOT NULL,
    fact_type TEXT NOT NULL,
    entity TEXT,
    metric TEXT,
    value TEXT,
    normalized_value NUMERIC,
    unit TEXT,
    time_period TEXT,
    scope TEXT,
    evidence_quote TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.5,
    attributes JSONB DEFAULT '{}',
    embedding VECTOR(768),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- relationships: edges between two facts
CREATE TABLE relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fact_a_id UUID NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    fact_b_id UUID NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.5,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- extraction_issues: logged failures/low-confidence extractions
CREATE TABLE extraction_issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT,
    issue_type TEXT NOT NULL,
    raw_text_snippet TEXT,
    detail TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_facts_document_id ON facts(document_id);
CREATE INDEX idx_facts_entity ON facts(entity);
CREATE INDEX idx_facts_metric ON facts(metric);
CREATE INDEX idx_facts_fact_type ON facts(fact_type);
CREATE INDEX idx_facts_time_period ON facts(time_period);
CREATE INDEX idx_relationships_fact_a ON relationships(fact_a_id);
CREATE INDEX idx_relationships_fact_b ON relationships(fact_b_id);
CREATE INDEX idx_relationships_type ON relationships(relationship_type);
CREATE INDEX idx_issues_document_id ON extraction_issues(document_id);
CREATE INDEX idx_issues_type ON extraction_issues(issue_type);

-- HNSW index for fast approximate nearest-neighbor search on embeddings
CREATE INDEX idx_facts_embedding ON facts USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

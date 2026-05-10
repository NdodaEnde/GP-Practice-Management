-- ============================================================================
-- Migration 011 — Semantic search infrastructure (pgvector)
-- ============================================================================
-- Implements TRACEABILITY §9. Embedding-based search across digitised
-- documents — the capability the Pricing page already sells via the
-- analytics_semantic_search flag but that has no backend until now.
--
-- Stores per-chunk embeddings keyed by source_document_id, so the indexer
-- can wipe-and-reinsert on doc re-approval (mirrors the promoter's idempotency
-- model). Vector dimension = 1536 (OpenAI text-embedding-3-large with
-- dimensions=1536 truncation — Matryoshka representation; pgvector's
-- ivfflat index caps at 2000 dims, full 3072 would force exact search).
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

-- pgvector extension. Supabase enables this with a GUI button OR the SQL below.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_embeddings (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT         NOT NULL,
    document_id     TEXT         NOT NULL,           -- source digitised_documents.id
    patient_id      TEXT,                            -- denormalised for fast workspace+patient filtering
    chunk_index     INT          NOT NULL,           -- position within the doc
    chunk_text      TEXT         NOT NULL,           -- the content embedded — used as snippet on result
    chunk_section   TEXT,                            -- which section it came from (e.g. 'progress_notes', 'medications', 'patient_demographics')
    embedding       vector(1536),                    -- text-embedding-3-large w/ dimensions=1536
    metadata        JSONB,                           -- room for chunk-level extras
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE document_embeddings IS
    'Per-chunk embeddings for semantic search. One row per chunk per source '
    'document. Chunks are derived at approval time from the validated '
    'gp_validation_sessions.extractions JSONB plus the structured-table '
    'rows the promoter wrote. Wipe-and-reinsert on re-approval keyed on '
    'document_id.';

-- Idempotency lookup
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_doc
    ON document_embeddings (document_id);

-- Workspace + patient filters before vector search
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_workspace
    ON document_embeddings (workspace_id, patient_id);

-- Approximate nearest-neighbour index for fast cosine-similarity search.
-- ivfflat needs `lists` parameter; for <100k rows, lists=100 is a fine default.
-- Cosine distance is `<=>` operator. Only build the index if it doesn't exist
-- (DROP INDEX + CREATE INDEX is safer than CREATE INDEX IF NOT EXISTS for
-- ivfflat — IF NOT EXISTS works in Postgres 12+ which Supabase runs).
CREATE INDEX IF NOT EXISTS idx_doc_embeddings_cosine
    ON document_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ----------------------------------------------------------------------------
-- Search RPC — wraps pgvector's <=> operator so the Supabase Python SDK can
-- call it via .rpc('digitisation_search', {...}). Returns top N chunks ranked
-- by cosine similarity within a workspace, optionally filtered by patient.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION digitisation_search(
    p_workspace_id TEXT,
    p_embedding    vector(1536),
    p_limit        INT  DEFAULT 20,
    p_patient_id   TEXT DEFAULT NULL
)
RETURNS TABLE (
    document_id   TEXT,
    patient_id    TEXT,
    chunk_section TEXT,
    chunk_text    TEXT,
    similarity    REAL
) LANGUAGE sql STABLE AS $$
    SELECT
        document_id,
        patient_id,
        chunk_section,
        chunk_text,
        (1 - (embedding <=> p_embedding))::real AS similarity
      FROM document_embeddings
     WHERE workspace_id = p_workspace_id
       AND (p_patient_id IS NULL OR patient_id = p_patient_id)
     ORDER BY embedding <=> p_embedding
     LIMIT p_limit;
$$;

COMMIT;

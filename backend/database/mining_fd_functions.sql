-- ============================================================
-- Mining Gateway / Financial-Disclosure — Postgres helper functions
-- ============================================================
-- These are stateless functions called from Python via supabase.rpc(...).
-- Keeps trigram / array operations in the DB where they belong (set-based,
-- index-friendly), so the Python resolver is a thin wrapper.
--
-- Idempotent: every function uses CREATE OR REPLACE.
-- ============================================================


-- ------------------------------------------------------------
-- fd_resolve_surface_form
-- ------------------------------------------------------------
-- Maps a verbatim surface form (e.g. "Matla Mine") to its best canonical_id
-- in fd_entity_registry, restricted to a workspace and entity type.
--
-- Returns ONE row: (canonical_id, confidence). confidence is 1.0 for an
-- exact lowercase match on any alias, otherwise the maximum pg_trgm
-- similarity() score across all aliases AND the canonical_name.
--
-- Plan rule (spec §4.2): the caller treats confidence < 0.80 as
-- "needs_review" and MUST NOT auto-merge.
--
-- If the registry has no rows for (workspace_id, entity_type), returns one
-- row with NULL canonical_id and confidence = 0.0 — caller writes to the
-- needs_review bucket.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fd_resolve_surface_form(
    p_workspace_id UUID,
    p_surface_form TEXT,
    p_entity_type  TEXT
)
RETURNS TABLE (canonical_id TEXT, confidence NUMERIC)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_query_norm TEXT := lower(trim(p_surface_form));
BEGIN
    -- Bail early on empty / whitespace input.
    IF v_query_norm = '' OR v_query_norm IS NULL THEN
        RETURN QUERY SELECT NULL::TEXT, 0.0::NUMERIC;
        RETURN;
    END IF;

    -- Try exact match first (over each alias + the canonical name, all lowered).
    RETURN QUERY
    SELECT r.canonical_id::TEXT, 1.0::NUMERIC AS confidence
      FROM fd_entity_registry r
     WHERE r.workspace_id = p_workspace_id
       AND r.entity_type  = p_entity_type
       AND (
            lower(r.canonical_name) = v_query_norm
         OR EXISTS (
              SELECT 1
                FROM unnest(r.surface_forms) AS sf
               WHERE lower(sf) = v_query_norm
            )
       )
     LIMIT 1;
    IF FOUND THEN
        RETURN;
    END IF;

    -- Fall through to trigram similarity. We unnest surface_forms so each
    -- alias is a separate candidate, and also compare against canonical_name.
    -- Returns the single best match (max similarity).
    RETURN QUERY
    SELECT cid, MAX(score)::NUMERIC AS confidence
      FROM (
        SELECT r.canonical_id            AS cid,
               similarity(lower(sf), v_query_norm) AS score
          FROM fd_entity_registry r,
               LATERAL unnest(r.surface_forms || ARRAY[r.canonical_name]) AS sf
         WHERE r.workspace_id = p_workspace_id
           AND r.entity_type  = p_entity_type
      ) candidates
     WHERE score > 0
     GROUP BY cid
     ORDER BY MAX(score) DESC
     LIMIT 1;

    -- If no rows came back, return the explicit "no match" sentinel.
    IF NOT FOUND THEN
        RETURN QUERY SELECT NULL::TEXT, 0.0::NUMERIC;
    END IF;
END
$$;

COMMENT ON FUNCTION fd_resolve_surface_form(UUID, TEXT, TEXT) IS
    'Spec §4.2: maps a verbatim surface form to (canonical_id, surface_form_confidence). Caller treats confidence < 0.80 as needs_review.';


-- ------------------------------------------------------------
-- Edge-idempotency patch: partial UNIQUE index covering NULL valid_from.
-- ------------------------------------------------------------
-- The fd_edges UNIQUE constraint is
--   UNIQUE (workspace_id, src_canonical_id, dst_canonical_id, relation, valid_from)
-- In Postgres, NULL values in a UNIQUE constraint are treated as DISTINCT, so
-- edges with valid_from = NULL (EVIDENCED_BY, SUPERSEDES, undated ALLOCATED_TO
-- / FINANCES) can be inserted multiple times — breaking spec §4.3 idempotency.
-- A partial unique index closes the gap. Idempotent: IF NOT EXISTS.
-- ------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS fd_edges_unique_when_valid_from_null
    ON fd_edges (workspace_id, src_canonical_id, dst_canonical_id, relation)
    WHERE valid_from IS NULL;

COMMENT ON INDEX fd_edges_unique_when_valid_from_null IS
    'Spec §4.3 idempotency: closes the NULL-not-equal-NULL gap in the natural fd_edges UNIQUE constraint for edges without temporal information (EVIDENCED_BY, SUPERSEDES, undated linkages).';


-- ------------------------------------------------------------
-- pgvector index + cosine-search function (spec §7.1 layer-3)
-- ------------------------------------------------------------
-- Deferred from mining_financial_disclosure_migration.sql §2 (was waiting
-- for at least some embedded rows so ivfflat's `lists` parameter has data
-- to cluster). With ~70+ spans embedded, lists=100 fits the rule of thumb
-- (lists ≈ rows / 1000 for small sets, capped at 100).
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS fd_source_spans_embedding_idx
    ON fd_source_spans USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

COMMENT ON INDEX fd_source_spans_embedding_idx IS
    'Spec §7.1 layer-3 grounded retrieval: cosine-similarity index on the OpenAI text-embedding-3-large@1536 embeddings of fd_source_spans.quote.';


CREATE OR REPLACE FUNCTION fd_search_source_spans(
    p_workspace_id UUID,
    p_query_vec    vector(1536),
    p_limit        INT DEFAULT 8
)
RETURNS TABLE (
    id            UUID,
    doc_id        TEXT,
    page          INTEGER,
    quote         TEXT,
    distance      FLOAT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    -- pgvector cosine distance: smaller = more similar. Range [0, 2].
    RETURN QUERY
    SELECT s.id, s.doc_id, s.page, s.quote, (s.embedding <=> p_query_vec) AS distance
      FROM fd_source_spans s
     WHERE s.workspace_id = p_workspace_id
       AND s.embedding IS NOT NULL
     ORDER BY s.embedding <=> p_query_vec
     LIMIT p_limit;
END
$$;

COMMENT ON FUNCTION fd_search_source_spans(UUID, vector, INT) IS
    'Spec §7.1 layer-3: cosine-similarity search over fd_source_spans.embedding. Returns the top-N most-similar spans for a query embedding. Caller embeds the question with text-embedding-3-large@1536.';

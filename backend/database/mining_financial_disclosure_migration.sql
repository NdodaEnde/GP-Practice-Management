-- ============================================================
-- Mining Gateway / Financial-Disclosure module — TBox
-- ============================================================
-- Implements the spec at SurgiScan-Exxaro-Transition-Intelligence-MVP-Spec.md (v0.5).
-- Plan: /Users/luzuko/.claude/plans/lazy-churning-mccarthy.md (step 1).
--
-- Conventions reused from the existing platform:
--   * workspace_id UUID NOT NULL REFERENCES workspaces(id) on every domain table
--     (matches workspaces_migration.sql + gp_migration_to_supabase.sql).
--   * RLS enabled with a permissive "Service role full access" policy. The backend
--     uses the service key (RLS bypassed) and scopes every query at the application
--     layer with `.eq('workspace_id', current_user["workspace_id"])`. This mirrors
--     the GP gateway's pattern; we do NOT introduce auth.uid()-based RLS here.
--   * update_updated_at_column() is defined in gp_migration_to_supabase.sql; we
--     reuse it via CREATE TRIGGER ... EXECUTE FUNCTION update_updated_at_column().
--
-- Honesty backbone (spec §3.3):
--   Every numeric edge MUST carry assertion_type ∈ {disclosed, derived,
--   strategically_attributed}. Enforced at the DB layer via CHECK constraint;
--   the ontology mapper layers additional rules (e.g. coal Asset → CapitalFund
--   linkages MUST be stamped 'strategically_attributed') before insert.
--
-- pgvector (spec §7.1 layer-3 grounded retrieval):
--   The `embedding` column on fd_source_spans uses pgvector(1536). The extension
--   must be enabled in this database before the migration runs:
--     CREATE EXTENSION IF NOT EXISTS vector;   -- run as superuser, idempotent.
--   On Supabase this is enabled from the dashboard's Database → Extensions page.
-- ============================================================

-- ============================================================
-- 0. Pre-flight: extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- fuzzy match for fd_entity_resolver.py

-- ============================================================
-- 1. Reference / lookup tables
-- ============================================================

-- Canonical-ID registry (spec §4.2). Pre-seeded by mining_seed_entity_registry.sql.
-- Surface forms are TEXT[] for cheap GIN-indexable membership checks.
CREATE TABLE IF NOT EXISTS fd_entity_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- 'Asset' | 'CapitalFund' | 'StrategicPillar' | 'Acquisition' | 'Org'
    surface_forms TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    owned_via TEXT,             -- canonical_id of holding company, if applicable (spec §4.2)
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_entity_registry_workspace      ON fd_entity_registry(workspace_id);
CREATE INDEX IF NOT EXISTS idx_fd_entity_registry_type           ON fd_entity_registry(workspace_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_fd_entity_registry_surface_forms  ON fd_entity_registry USING GIN (surface_forms);

DROP TRIGGER IF EXISTS update_fd_entity_registry_updated_at ON fd_entity_registry;
CREATE TRIGGER update_fd_entity_registry_updated_at
    BEFORE UPDATE ON fd_entity_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_entity_registry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_entity_registry" ON fd_entity_registry;
CREATE POLICY "Service role full access to fd_entity_registry"
    ON fd_entity_registry FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 2. Source spans (provenance — spec §5)
-- ============================================================
-- Every fact node / edge is evidenced by ≥1 SourceSpan. Primary node key is
-- (doc_id, page, char_start) per spec §5; content_hash is the v0.3 secondary key
-- so delta logic distinguishes "same fact, moved page" from "genuinely new fact".

CREATE TABLE IF NOT EXISTS fd_source_spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    doc_id TEXT NOT NULL,        -- e.g. 'EXXARO-IR-2024'
    page INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    quote TEXT NOT NULL,
    content_hash TEXT NOT NULL,  -- SHA-256 of the span text (spec §5 v0.3)

    embedding vector(1536),       -- spec §7.1 layer-3 grounded retrieval; populated at step 6

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- spec §5: primary node key
    UNIQUE (workspace_id, doc_id, page, char_start)
);
CREATE INDEX IF NOT EXISTS idx_fd_source_spans_workspace      ON fd_source_spans(workspace_id);
CREATE INDEX IF NOT EXISTS idx_fd_source_spans_doc            ON fd_source_spans(workspace_id, doc_id, page);
CREATE INDEX IF NOT EXISTS idx_fd_source_spans_content_hash   ON fd_source_spans(workspace_id, content_hash);
-- Vector index added at step 6 once embeddings are populated. ivfflat requires
-- at least some rows to build a useful index, so it's deferred.
-- CREATE INDEX IF NOT EXISTS idx_fd_source_spans_embedding ON fd_source_spans USING ivfflat (embedding vector_cosine_ops);

ALTER TABLE fd_source_spans ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_source_spans" ON fd_source_spans;
CREATE POLICY "Service role full access to fd_source_spans"
    ON fd_source_spans FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 3. Node classes (spec §3.1)
-- ============================================================
-- All node tables share: workspace_id + canonical_id (UNIQUE per workspace) +
-- created_at/updated_at + RLS. Class-specific properties per spec §3.1.

CREATE TABLE IF NOT EXISTS fd_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    name TEXT NOT NULL,
    commodity TEXT NOT NULL CHECK (commodity IN ('Coal', 'Manganese', 'Renewable', 'Other')),
    region TEXT,
    lifecycle TEXT CHECK (lifecycle IN ('Producing', 'Acquired', 'Pipeline')),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_assets_workspace   ON fd_assets(workspace_id);
CREATE INDEX IF NOT EXISTS idx_fd_assets_commodity   ON fd_assets(workspace_id, commodity);

DROP TRIGGER IF EXISTS update_fd_assets_updated_at ON fd_assets;
CREATE TRIGGER update_fd_assets_updated_at BEFORE UPDATE ON fd_assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_assets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_assets" ON fd_assets;
CREATE POLICY "Service role full access to fd_assets"
    ON fd_assets FOR ALL USING (true) WITH CHECK (true);


CREATE TABLE IF NOT EXISTS fd_capital_funds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    name TEXT NOT NULL,
    fund_type TEXT NOT NULL CHECK (fund_type IN ('Sustaining', 'Expansion', 'Diversification')),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_capital_funds_workspace ON fd_capital_funds(workspace_id);

DROP TRIGGER IF EXISTS update_fd_capital_funds_updated_at ON fd_capital_funds;
CREATE TRIGGER update_fd_capital_funds_updated_at BEFORE UPDATE ON fd_capital_funds
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_capital_funds ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_capital_funds" ON fd_capital_funds;
CREATE POLICY "Service role full access to fd_capital_funds"
    ON fd_capital_funds FOR ALL USING (true) WITH CHECK (true);


CREATE TABLE IF NOT EXISTS fd_strategic_pillars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    name TEXT NOT NULL,  -- 'Coal Ops' | 'Green Energy' | 'Future Minerals'

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_strategic_pillars_workspace ON fd_strategic_pillars(workspace_id);

DROP TRIGGER IF EXISTS update_fd_strategic_pillars_updated_at ON fd_strategic_pillars;
CREATE TRIGGER update_fd_strategic_pillars_updated_at BEFORE UPDATE ON fd_strategic_pillars
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_strategic_pillars ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_strategic_pillars" ON fd_strategic_pillars;
CREATE POLICY "Service role full access to fd_strategic_pillars"
    ON fd_strategic_pillars FOR ALL USING (true) WITH CHECK (true);


CREATE TABLE IF NOT EXISTS fd_orgs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    name TEXT NOT NULL,
    org_type TEXT,  -- e.g. 'Issuer', 'HoldingCo', 'Subsidiary'

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_orgs_workspace ON fd_orgs(workspace_id);

DROP TRIGGER IF EXISTS update_fd_orgs_updated_at ON fd_orgs;
CREATE TRIGGER update_fd_orgs_updated_at BEFORE UPDATE ON fd_orgs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_orgs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_orgs" ON fd_orgs;
CREATE POLICY "Service role full access to fd_orgs"
    ON fd_orgs FOR ALL USING (true) WITH CHECK (true);


CREATE TABLE IF NOT EXISTS fd_financial_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    metric TEXT NOT NULL,  -- 'EBITDA' | 'FCF' | 'CapEx' | 'RevenueGross' | ...
    value_zar_m NUMERIC(20, 4) NOT NULL,  -- value in ZAR millions, 4-decimal precision
    fiscal_year INTEGER NOT NULL,
    basis TEXT NOT NULL CHECK (basis IN ('reported', 'restated')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'restated', 'withdrawn')),  -- spec §6.1 v0.3

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_financial_facts_workspace  ON fd_financial_facts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_fd_financial_facts_fy_status  ON fd_financial_facts(workspace_id, fiscal_year, status);
CREATE INDEX IF NOT EXISTS idx_fd_financial_facts_metric     ON fd_financial_facts(workspace_id, metric, fiscal_year);

DROP TRIGGER IF EXISTS update_fd_financial_facts_updated_at ON fd_financial_facts;
CREATE TRIGGER update_fd_financial_facts_updated_at BEFORE UPDATE ON fd_financial_facts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_financial_facts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_financial_facts" ON fd_financial_facts;
CREATE POLICY "Service role full access to fd_financial_facts"
    ON fd_financial_facts FOR ALL USING (true) WITH CHECK (true);


CREATE TABLE IF NOT EXISTS fd_esg_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    metric TEXT NOT NULL,  -- 'Scope1' | 'Scope2' | 'Scope3' | 'CarbonIntensity' | ...
    value NUMERIC(20, 4) NOT NULL,
    unit TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    site_ref TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'restated', 'withdrawn')),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_esg_facts_workspace     ON fd_esg_facts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_fd_esg_facts_fy_status     ON fd_esg_facts(workspace_id, fiscal_year, status);
CREATE INDEX IF NOT EXISTS idx_fd_esg_facts_metric        ON fd_esg_facts(workspace_id, metric, fiscal_year);

DROP TRIGGER IF EXISTS update_fd_esg_facts_updated_at ON fd_esg_facts;
CREATE TRIGGER update_fd_esg_facts_updated_at BEFORE UPDATE ON fd_esg_facts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_esg_facts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_esg_facts" ON fd_esg_facts;
CREATE POLICY "Service role full access to fd_esg_facts"
    ON fd_esg_facts FOR ALL USING (true) WITH CHECK (true);


CREATE TABLE IF NOT EXISTS fd_acquisitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    canonical_id TEXT NOT NULL,
    name TEXT NOT NULL,
    value_zar_m NUMERIC(20, 4) NOT NULL,
    announced_date DATE,
    status TEXT NOT NULL CHECK (status IN ('Announced', 'Closed')),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_acquisitions_workspace ON fd_acquisitions(workspace_id);

DROP TRIGGER IF EXISTS update_fd_acquisitions_updated_at ON fd_acquisitions;
CREATE TRIGGER update_fd_acquisitions_updated_at BEFORE UPDATE ON fd_acquisitions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_acquisitions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_acquisitions" ON fd_acquisitions;
CREATE POLICY "Service role full access to fd_acquisitions"
    ON fd_acquisitions FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 4. Edge table (spec §3.2)
-- ============================================================
-- One row per typed relationship between two canonical nodes. Endpoints are
-- (src_canonical_id, src_type) and (dst_canonical_id, dst_type) — we resolve
-- by canonical_id at the app layer rather than enforcing cross-table FKs (the
-- canonical_id is unique per workspace within its own node table, and edges
-- span multiple node types).
--
-- assertion_type is the §3.3 honesty backbone — DB-level CHECK ensures no edge
-- can be persisted without one. The ontology mapper (fd_ontology_mapper.py)
-- adds the rule "Asset(Coal) → CapitalFund linkages MUST be 'strategically_attributed'"
-- before insert (defence in depth — DB-level CHECK alone can't see source vs
-- destination commodity).
--
-- EVIDENCED_BY is modeled as edges too: relation='EVIDENCED_BY', dst pointing
-- at an fd_source_spans row's canonical_id (we use the row's UUID-as-text).
-- This keeps "edges have provenance" representable uniformly.
CREATE TABLE IF NOT EXISTS fd_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    src_canonical_id TEXT NOT NULL,
    src_type TEXT NOT NULL,
    dst_canonical_id TEXT NOT NULL,
    dst_type TEXT NOT NULL,

    relation TEXT NOT NULL CHECK (relation IN (
        'GENERATES',
        'ALLOCATED_TO',
        'FINANCES',
        'PART_OF',
        'GOVERNED_BY',
        'REPORTS',
        'OWNS',
        'EVIDENCED_BY',
        'SUPERSEDES'
    )),

    payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Spec §3.3: every numeric edge tagged. Non-numeric edges (PART_OF, GOVERNED_BY,
    -- EVIDENCED_BY, SUPERSEDES) may omit this — see the partial unique index below.
    assertion_type TEXT
        CHECK (assertion_type IS NULL OR assertion_type IN (
            'disclosed', 'derived', 'strategically_attributed'
        )),

    -- Spec §6: temporal modeling for OWNS / GENERATES / etc.
    valid_from DATE,
    valid_to DATE,
    status TEXT  -- 'active' | 'restated' | 'withdrawn' for restatement-aware edges

    , content_hash TEXT

    , created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    , updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

    -- Numeric edges (those carrying assertion_type) MUST be unique on the tuple
    -- (workspace_id, src_canonical_id, dst_canonical_id, relation, valid_from)
    -- so re-ingestion is idempotent. Non-numeric edges (assertion_type IS NULL)
    -- are also de-duplicated on the same tuple.
    , UNIQUE (workspace_id, src_canonical_id, dst_canonical_id, relation, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_fd_edges_workspace        ON fd_edges(workspace_id);
CREATE INDEX IF NOT EXISTS idx_fd_edges_src              ON fd_edges(workspace_id, src_canonical_id, relation);
CREATE INDEX IF NOT EXISTS idx_fd_edges_dst              ON fd_edges(workspace_id, dst_canonical_id, relation);
CREATE INDEX IF NOT EXISTS idx_fd_edges_assertion_type   ON fd_edges(workspace_id, assertion_type);
CREATE INDEX IF NOT EXISTS idx_fd_edges_status           ON fd_edges(workspace_id, status) WHERE status IS NOT NULL;

DROP TRIGGER IF EXISTS update_fd_edges_updated_at ON fd_edges;
CREATE TRIGGER update_fd_edges_updated_at BEFORE UPDATE ON fd_edges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_edges ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_edges" ON fd_edges;
CREATE POLICY "Service role full access to fd_edges"
    ON fd_edges FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 5. Quarantine bucket (spec §4.2 — needs_review)
-- ============================================================
-- Surface forms whose best registry match scores < 0.80 land here. NEVER
-- auto-merged into a node table. Human resolves via /api/fd/needs_review/:id/merge.
CREATE TABLE IF NOT EXISTS fd_facts_needs_review (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    raw_surface_form TEXT NOT NULL,
    best_match_canonical_id TEXT,
    surface_form_confidence NUMERIC(4, 3) NOT NULL
        CHECK (surface_form_confidence >= 0 AND surface_form_confidence <= 1),
    ade_output JSONB NOT NULL,
    doc_id TEXT,
    page INTEGER,

    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_canonical_id TEXT,
    resolved_by TEXT,            -- user identifier
    resolved_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fd_facts_needs_review_workspace ON fd_facts_needs_review(workspace_id, resolved);

ALTER TABLE fd_facts_needs_review ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_facts_needs_review" ON fd_facts_needs_review;
CREATE POLICY "Service role full access to fd_facts_needs_review"
    ON fd_facts_needs_review FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 6. Gold set + eval runs (spec §8)
-- ============================================================
-- Hard rule (plan, step 5): every gold-set row is captured by a named human
-- reading the actual PDF, with the verbatim quote at the moment of capture.
-- captured_by / captured_at / source_quote are NOT NULL by design — the
-- discipline is enforced by the schema, not by procedure.
CREATE TABLE IF NOT EXISTS fd_gold_set (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    question TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    expected_doc_id TEXT NOT NULL,
    expected_page INTEGER NOT NULL,
    expected_assertion_type TEXT NOT NULL
        CHECK (expected_assertion_type IN ('disclosed', 'derived', 'strategically_attributed', 'refusal')),
        -- 'refusal' = the correct answer is the constrained refusal copy (spec §7.1)

    -- Capture provenance — non-negotiable.
    captured_by TEXT NOT NULL,
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source_quote TEXT NOT NULL,

    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fd_gold_set_workspace_active ON fd_gold_set(workspace_id, is_active);

DROP TRIGGER IF EXISTS update_fd_gold_set_updated_at ON fd_gold_set;
CREATE TRIGGER update_fd_gold_set_updated_at BEFORE UPDATE ON fd_gold_set
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_gold_set ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_gold_set" ON fd_gold_set;
CREATE POLICY "Service role full access to fd_gold_set"
    ON fd_gold_set FOR ALL USING (true) WITH CHECK (true);


CREATE TABLE IF NOT EXISTS fd_eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    run_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    triggered_by TEXT,
    git_sha TEXT,

    -- §8 metrics
    answer_accuracy NUMERIC(5, 4),
    provenance_coverage NUMERIC(5, 4),
    query_validity NUMERIC(5, 4),
    refusal_correctness NUMERIC(5, 4),
    assertion_type_correctness NUMERIC(5, 4),

    gate_passed BOOLEAN NOT NULL DEFAULT FALSE,

    result_blob JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_fd_eval_runs_workspace_run_at ON fd_eval_runs(workspace_id, run_at DESC);

ALTER TABLE fd_eval_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_eval_runs" ON fd_eval_runs;
CREATE POLICY "Service role full access to fd_eval_runs"
    ON fd_eval_runs FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 7. Documents ingested (one row per uploaded PDF)
-- ============================================================
-- Track each annual / sustainability / investor report end-to-end. The actual
-- PDF lives in Supabase Storage; this row records the doc_id used in
-- fd_source_spans + ingest status.
CREATE TABLE IF NOT EXISTS fd_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

    doc_id TEXT NOT NULL,                -- e.g. 'EXXARO-IR-2024'
    doc_type TEXT NOT NULL CHECK (doc_type IN ('integrated', 'sustainability', 'investor')),
    fiscal_year INTEGER NOT NULL,
    title TEXT NOT NULL,
    storage_path TEXT NOT NULL,           -- Supabase Storage path
    sha256 TEXT NOT NULL,

    ingest_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (ingest_status IN ('pending', 'extracting', 'mapping', 'resolving', 'completed', 'failed', 'cached_fallback')),
    extraction_latency_seconds NUMERIC(10, 3),
    entity_resolution_confidence NUMERIC(4, 3),  -- aggregate, for the §7.5 health-check trip-wire
    error_message TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (workspace_id, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_fd_documents_workspace_status ON fd_documents(workspace_id, ingest_status);
CREATE INDEX IF NOT EXISTS idx_fd_documents_sha256           ON fd_documents(workspace_id, sha256);

DROP TRIGGER IF EXISTS update_fd_documents_updated_at ON fd_documents;
CREATE TRIGGER update_fd_documents_updated_at BEFORE UPDATE ON fd_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE fd_documents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Service role full access to fd_documents" ON fd_documents;
CREATE POLICY "Service role full access to fd_documents"
    ON fd_documents FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 8. Comments (documentation in the catalog)
-- ============================================================
COMMENT ON TABLE fd_entity_registry      IS 'Mining/FD: canonical-ID registry (spec §4.2). Pre-seeded; surface_forms must be cross-checked against the 2022–2025 source PDFs before ingest.';
COMMENT ON TABLE fd_source_spans         IS 'Mining/FD: provenance node (spec §5). Every fact node/edge MUST be evidenced by ≥1 row here. embedding populated at step 6.';
COMMENT ON TABLE fd_assets               IS 'Mining/FD: Asset node class (spec §3.1).';
COMMENT ON TABLE fd_capital_funds        IS 'Mining/FD: CapitalFund node class (spec §3.1).';
COMMENT ON TABLE fd_strategic_pillars    IS 'Mining/FD: StrategicPillar node class (spec §3.1).';
COMMENT ON TABLE fd_orgs                 IS 'Mining/FD: Org node class (spec §3.1).';
COMMENT ON TABLE fd_financial_facts      IS 'Mining/FD: FinancialFact node class (spec §3.1). status ∈ {active, restated, withdrawn} per §6.1 v0.3.';
COMMENT ON TABLE fd_esg_facts            IS 'Mining/FD: ESGFact node class (spec §3.1).';
COMMENT ON TABLE fd_acquisitions         IS 'Mining/FD: Acquisition node class (spec §3.1).';
COMMENT ON TABLE fd_edges                IS 'Mining/FD: typed relationship store (spec §3.2). assertion_type ∈ {disclosed, derived, strategically_attributed} for numeric edges.';
COMMENT ON TABLE fd_facts_needs_review   IS 'Mining/FD: surface-form quarantine (spec §4.2). Confidence < 0.80 → here, never auto-merged.';
COMMENT ON TABLE fd_gold_set             IS 'Mining/FD: eval gold set (spec §8). captured_by/captured_at/source_quote NOT NULL — every row read out of the actual PDF by a named human.';
COMMENT ON TABLE fd_eval_runs            IS 'Mining/FD: eval-harness run history. gate_passed = all 5 metrics meet §8 targets.';
COMMENT ON TABLE fd_documents            IS 'Mining/FD: per-PDF ingest tracker (matches doc_id used in fd_source_spans).';

COMMENT ON COLUMN fd_edges.assertion_type IS
    'Spec §3.3 honesty backbone. disclosed = stated directly in source. derived = computed by defined rule. strategically_attributed = company asserts as strategy without traceable cash flow (NEVER disclosed for Coal→Fund linkages).';
COMMENT ON COLUMN fd_financial_facts.status IS
    'Spec §6.1 v0.3. active = current value. restated = superseded (incoming SUPERSEDES edge from a newer row). withdrawn = present in prior report, absent and not restated in current — kept for audit, never deleted.';
COMMENT ON COLUMN fd_gold_set.captured_by IS
    'Named human who captured this gold-set row from the source PDF. Not the spec author. The spec is illustrative — its example numbers MUST NOT be lifted into the gold set verbatim.';

-- ============================================================================
-- Migration 027 — briefing_items (Phase 3 PR D: standing-query materialisation)
-- ============================================================================
--
-- The persistence target for materialised standing queries (morning
-- briefing / pre-consult). Each row is ONE resolved answer row produced
-- by the SAME run_template + resolve_provenance chokepoint /run and /ask
-- use — so every briefing_items row structurally inherits PR A/B's
-- verifiable-provenance + openable/no_source/unresolvable contract.
-- standing.py NEVER reads facts directly; it only writes what the
-- chokepoint resolved. No new data path.
--
-- COLUMNS — grounded in the REAL ResolvedQueryResult.to_dict() /
-- ResolvedRow.to_dict() shape (probed live at PR D, not guessed):
-- row_payload jsonb holds the full per-row {**data, provenance{…},
-- source{status,openable,document_id,signed_url,citation,
-- unresolvable_reason,quality}, additional_sources}; the denormalised
-- top-signal columns (source_status/openable/unresolvable_reason/
-- citation) exist so a UI / probe can read the safety signal cheaply
-- without unpacking jsonb.
--
-- IDEMPOTENCY (PR D §3.3, locked decision #6): the partition key is the
-- triple (workspace_id, kind, as_of_date). materialise_standing_queries
-- DELETEs that exact partition then INSERTs the freshly-resolved rows,
-- one transaction per (workspace_id, kind) — a double-run is row-stable
-- by construction; a mid-run failure's blast radius is exactly the
-- partition being rewritten. The index below backs that DELETE.
--
-- TENANT SCOPE: workspace_id is TEXT and joins workspaces.id (TEXT) with
-- NO ::uuid cast (the heterogeneous-identifier postmortem scar; the
-- materialiser only ever materialises clinical_query-ENTITLED workspaces
-- enumerated from a trusted DB source, never caller input). Added to the
-- PR 5 static tenant-guard TENANT_TABLES (the ratchet only goes down).
--
-- RLS — DENY-ALL, the migration-018 idiom VERBATIM:
--   ENABLE ROW LEVEL SECURITY with NO permissive policy => deny-all to
--   non-bypass roles. The service_role backend (rolbypassrls=TRUE) is
--   unaffected; anon/authenticated get ZERO rows. We deliberately do
--   NOT use FORCE ROW LEVEL SECURITY (018:36 rationale: FORCE would also
--   constrain the bypass-role backend, breaking the app's own writes)
--   and NOT auth.*-keyed policies (the app does not use Supabase Auth;
--   018:43-48). This reproduces exactly the posture migration 018 gave
--   the existing tenant tables.
--
-- POSTGREST SCHEMA-CACHE — `NOTIFY pgrst` is INCLUDED, and that is a
-- consciously-decided call, documented here (locked decision #5; the
-- discipline of 025 omitting it because it added no function and 026
-- including it because it added functions). 027 adds a TABLE and no
-- function. Reasoning for INCLUDING: briefing_items is addressed by the
-- supabase-py REST/table builder (.table("briefing_items")); a stale
-- PostgREST table-schema cache could 404 early .table("briefing_items")
-- calls until the cache happens to reload. NOTIFY is the cheap correct
-- hygiene here even though no function is added — this is a decided
-- inclusion, NOT a cargo-cult of 026's function-driven NOTIFY and NOT a
-- cargo-cult of 025's omission. The test
-- test_standing_queries.py::test_027_migration_ends_with_notify_pgrst_decision_is_explicit
-- enforces only that the decision is EXPLICIT, not its direction.
--
-- ORDERING: strictly after 026. Adds no function, so no
-- template-availability race; standard deploy sequence.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.briefing_items (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- idempotency partition key (PR D §3.3)
    workspace_id        TEXT        NOT NULL,
    kind                TEXT        NOT NULL,
    as_of_date          DATE        NOT NULL,
    -- which template produced this row
    template_id         TEXT        NOT NULL,
    template_version    INT,
    -- the full resolved row (ResolvedRow.to_dict())
    row_payload         JSONB       NOT NULL,
    -- denormalised top safety-signal (cheap reads without unpacking jsonb)
    source_status       TEXT,       -- openable | unresolvable | no_source
    openable            BOOLEAN,
    unresolvable_reason TEXT,
    citation            TEXT,
    materialised_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Backs the idempotency DELETE (workspace_id, kind, as_of_date) AND the
-- GET /api/query/briefing reads (workspace_id [+ kind] [+ as_of_date]).
CREATE INDEX IF NOT EXISTS idx_briefing_items_partition
    ON public.briefing_items (workspace_id, kind, as_of_date);

-- Workspace-scoped reads are index-backed (tenant-guard chains carry
-- .eq("workspace_id", …); this keeps them cheap).
CREATE INDEX IF NOT EXISTS idx_briefing_items_workspace
    ON public.briefing_items (workspace_id);

-- RLS deny-all — migration-018 idiom verbatim. Enable RLS, add NO
-- permissive policy. NOT FORCE. NOT auth.*-keyed.
ALTER TABLE public.briefing_items ENABLE ROW LEVEL SECURITY;

-- Phase-0 finding discipline — consciously INCLUDED for 027 (see header:
-- briefing_items is REST-builder-addressed; a stale table-schema cache
-- could 404 early .table() calls). Decided inclusion, not cargo-cult.
NOTIFY pgrst, 'reload schema';

COMMIT;

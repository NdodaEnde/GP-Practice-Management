-- ============================================================================
-- Migration 028 — open_loops (Phase 4 PR F: the OpenLoop substrate)
-- ============================================================================
--
-- The persistence target for the fourth ontology object, `OpenLoop`
-- (ontology/objects/open_loop.py). A row is one tracked clinical loop:
-- an opening event, an expected closing event, a deadline, an urgency,
-- and a lifecycle state (the closed transition table in
-- ontology/objects/open_loop_state.py: OPEN → AWAITING → (CLOSED |
-- BREACHED), BREACHED → CLOSED, CLOSED terminal).
--
-- SCOPE — F-1 = option B (LOCKED): this is the SUBSTRATE ONLY. PR F adds
-- the table, the object, the state machine, and the audited mutation
-- actions. It does NOT add a detector (F-4: detectors are PR G) and does
-- NOT instantiate any real loop. The substrate ships built and proven
-- non-vacuous on fabricated input, the first real stateful loop deferred
-- to PR G. This migration creates storage; it asserts nothing about a
-- loop existing.
--
-- COLUMNS — grounded in the REAL OpenLoop field set (open_loop.py), not
-- guessed. loop_kind / state / urgency are TEXT, deliberately NOT a DB
-- ENUM type: F-3 (locked) — the taxonomy is PR G's and extensibility
-- must be structural (PR G adds an enum member, NO migration churn). The
-- (state, *_at) consistency invariant is enforced at the ontology layer
-- (OpenLoop.model_validator, the independent second guard) and the
-- audited-action path is the only writer; the table is storage, the
-- ontology is the guard — the base.py "ontology sits above persistence"
-- principle. A DB CHECK is deliberately NOT added (it is not in PR F's
-- locked scope; the guard is the model_validator + the executor path).
--
-- IDEMPOTENCY: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS;
-- a double-run is a clean no-op. No data is seeded (substrate only).
--
-- TENANT SCOPE: workspace_id is TEXT and joins workspaces.id (TEXT) with
-- NO ::uuid cast (the heterogeneous-identifier postmortem scar; the
-- ontology object's `practice_id` is the slug-shaped tenancy ref and
-- maps to this column — the established Patient split). Added to the
-- PR 5 static tenant-guard TENANT_TABLES; under F-1=B the audited Effect
-- primitives use `.table(self.table)` (a variable, not a string
-- literal) so the static scanner finds ZERO `.table("open_loops")`
-- literal chains — adding it to TENANT_TABLES adds ZERO new BASELINE
-- keys (born tenant-scoped; the ratchet only goes down). Proven by
-- running test_no_new_unscoped_tenant_queries, not asserted.
--
-- RLS — DENY-ALL, the migration-018 idiom VERBATIM:
--   ENABLE ROW LEVEL SECURITY with NO permissive policy => deny-all to
--   non-bypass roles. service_role backend (rolbypassrls=TRUE) and the
--   postgres migration role are unaffected; anon/authenticated get ZERO
--   rows. We deliberately do NOT use FORCE ROW LEVEL SECURITY (018:36
--   rationale) and do NOT add auth.*-keyed policies (018:43-48 — the app
--   does not use Supabase Auth). This reproduces exactly the posture
--   migration 018 gave the existing tenant tables and 027 gave
--   briefing_items.
--
-- POSTGREST SCHEMA-CACHE — `NOTIFY pgrst` is INCLUDED, a consciously-
-- decided call (the discipline of 025 omitting it because it added no
-- function, 026 including it because it added functions, 027 including
-- it for a REST-builder-addressed table). 028 adds a TABLE and no
-- function. Reasoning for INCLUDING (same as 027): open_loops is
-- addressed by the supabase-py REST/table builder
-- (.table("open_loops")) via the audited Effect primitives; a stale
-- PostgREST table-schema cache could 404 early .table("open_loops")
-- calls until the cache happens to reload. NOTIFY is the cheap correct
-- hygiene here even though no function is added — a decided inclusion,
-- NOT a cargo-cult of 026's function-driven NOTIFY and NOT a cargo-cult
-- of 025's omission.
--
-- ORDERING: strictly after 027. Adds no function, so no
-- template-availability race; standard deploy sequence.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.open_loops (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- tenancy (DB-level; the object's practice_id maps here)
    workspace_id                TEXT        NOT NULL,
    -- the patient this loop concerns
    patient_id                  UUID        NOT NULL,
    -- taxonomy discriminator (TEXT, not enum — F-3 structural extensibility)
    loop_kind                   TEXT        NOT NULL,
    -- lifecycle state (the closed transition table is the source of truth)
    state                       TEXT        NOT NULL,
    -- what opened it (PR F substrate: 'manual'; PR G detectors set more)
    opening_event_kind          TEXT        NOT NULL,
    opening_event_ref           TEXT,
    -- human-readable description of the event that would close it
    expected_closing_event_kind TEXT        NOT NULL,
    -- urgency (TEXT, not enum — same F-3 rationale as loop_kind)
    urgency                     TEXT        NOT NULL DEFAULT 'routine',
    -- when it breaches if not closed (nullable: a loop may have none)
    deadline_at                 TIMESTAMPTZ,
    -- lifecycle timestamps (consistency enforced by the ontology guard)
    opened_at                   TIMESTAMPTZ NOT NULL,
    closed_at                   TIMESTAMPTZ,
    closed_reason               TEXT,
    breached_at                 TIMESTAMPTZ,
    -- ontology system fields
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                  TIMESTAMPTZ
);

-- Workspace-scoped reads by state (the briefing/PR-G read shape) and by
-- patient (the Patient--has_open_loop-->OpenLoop traversal).
CREATE INDEX IF NOT EXISTS idx_open_loops_workspace_state
    ON public.open_loops (workspace_id, state);
CREATE INDEX IF NOT EXISTS idx_open_loops_workspace_patient
    ON public.open_loops (workspace_id, patient_id);

-- RLS deny-all — migration-018 idiom verbatim. Enable RLS, add NO
-- permissive policy. NOT FORCE. NOT auth.*-keyed.
ALTER TABLE public.open_loops ENABLE ROW LEVEL SECURITY;

-- Phase-0 finding discipline — consciously INCLUDED for 028 (see header:
-- open_loops is REST-builder-addressed via the audited Effect
-- primitives; a stale table-schema cache could 404 early .table()
-- calls). Decided inclusion, not cargo-cult.
NOTIFY pgrst, 'reload schema';

COMMIT;

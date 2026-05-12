-- ============================================================================
-- Migration 014 — Action audit log
-- ============================================================================
--
-- The ActionExecutor writes one row here per mutation it processes (real,
-- dry-run, or reversed). This table is the regulatory-grade audit surface
-- the platform's "audit-ready by default" claim leans on.
--
-- Why a new table and not an extension of validation_edit_log?
--
--   validation_edit_log (migration 005) is document-scoped: its action CHECK
--   constraint enumerates ('edit', 'accept', 'approve', 'reject',
--   'reprocess'), its field_path semantics are field-level, and it has no
--   concept of affected_objects across the graph. The audit-trail UI in
--   Phase 4 will want "show me every action that touched patient X" — a
--   query that table's schema cannot answer without joins it isn't indexed
--   for. The two tables overlap for one PR cycle (PR 1 double-writes,
--   PR 2 removes the legacy write).
--
-- affected_objects is structured JSONB, not TEXT[]
--
--   Each entry is {type, id, op} where op is created|updated|soft_deleted|
--   linked. The Phase 4 UI renders WHAT happened to each object — type-
--   prefixed strings ('patient_<uuid>') can't carry the op dimension; bare
--   UUIDs need joins to recover the type. The slightly more complex GIN
--   (jsonb_path_ops) index pays for the audit log becoming a *story*, not
--   a *list*.
--
--   Containment query example:
--     SELECT * FROM action_audit_log
--      WHERE affected_objects @> '[{"type": "Patient", "id": "<uuid>"}]'
--      ORDER BY started_at DESC;
--
-- Append-only by convention
--
--   The reverses_audit_id / reversed_by_audit_id pointers let us link
--   forward and backward without UPDATEing the original row in normal
--   flow. Reversal of action X writes a new row Y with Y.reverses_audit_id
--   = X.id, AND updates X.reversed_by_audit_id = Y.id (one targeted
--   UPDATE via the executor; not a free-form mutation).
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS action_audit_log (
    id                     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    action_name            TEXT         NOT NULL,
    action_version         INT          NOT NULL DEFAULT 1,
    actor_user_id          TEXT         NOT NULL,
    actor_email            TEXT,
    practice_id            TEXT         NOT NULL,
    workspace_id           TEXT         NOT NULL,
    idempotency_key        TEXT,
    dry_run                BOOLEAN      NOT NULL DEFAULT FALSE,
    parameters             JSONB        NOT NULL,
    preconditions_checked  JSONB        NOT NULL,   -- [{name, passed, detail}]
    effects_applied        JSONB        NOT NULL,   -- [{name, descriptor, result}]
    affected_objects       JSONB        NOT NULL DEFAULT '[]',
                                                    -- [{type, id, op}]
    outcome                TEXT         NOT NULL CHECK (outcome IN (
                                            'success',
                                            'precondition_failed',
                                            'effect_failed',
                                            'reversed',
                                            'dry_run'
                                        )),
    error_detail           JSONB,                   -- ErrorDetail(code, message, context)
    reverses_audit_id      UUID         REFERENCES action_audit_log(id),
    reversed_by_audit_id   UUID         REFERENCES action_audit_log(id),
    started_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finished_at            TIMESTAMPTZ,
    duration_ms            INT
);

-- "every action of type X across all practices, most recent first"
CREATE INDEX IF NOT EXISTS idx_action_audit_log_action_started
    ON action_audit_log (action_name, started_at DESC);

-- "every action in this practice, most recent first" — practice timeline view
CREATE INDEX IF NOT EXISTS idx_action_audit_log_practice_started
    ON action_audit_log (practice_id, started_at DESC);

-- "every action this user ever did" — for individual-actor audit trails
CREATE INDEX IF NOT EXISTS idx_action_audit_log_actor_started
    ON action_audit_log (actor_user_id, started_at DESC);

-- "every action that touched patient/document/consultation X" — Phase 4 UI
CREATE INDEX IF NOT EXISTS idx_action_audit_log_affected_objects
    ON action_audit_log USING gin (affected_objects jsonb_path_ops);

-- Idempotency: same key + same action = same audit row (real writes only).
-- Dry-runs are intentionally outside this constraint so previews are repeatable.
CREATE UNIQUE INDEX IF NOT EXISTS idx_action_audit_log_idempotency
    ON action_audit_log (action_name, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND dry_run = FALSE;

-- Find all reversals of a given action
CREATE INDEX IF NOT EXISTS idx_action_audit_log_reverses
    ON action_audit_log (reverses_audit_id)
    WHERE reverses_audit_id IS NOT NULL;

COMMENT ON TABLE action_audit_log IS
    'One row per ActionExecutor invocation (real or dry-run). Append-only; '
    'reversals add a new row pointing at reverses_audit_id and the executor '
    'updates the original row''s reversed_by_audit_id (one targeted UPDATE).';

-- ----------------------------------------------------------------------------
-- Advisory lock RPC
-- ----------------------------------------------------------------------------
-- Callable from Python via supabase.rpc('action_try_advisory_lock', ...).
-- Uses pg_try_advisory_xact_lock — transaction-scoped. The lock is held only
-- for the duration of the RPC call, then released automatically.
--
-- The plan calls for verifying empirically (Phase 0) whether session-scoped
-- advisory locks (pg_try_advisory_lock + pg_advisory_unlock) are visible
-- across Supabase's HTTP-pooled requests. This RPC supports the verification
-- by acquiring a session-scoped lock and returning whether it succeeded; the
-- companion unlock RPC releases it.
--
-- See backend/tests/test_advisory_lock_semantics.py for the verification.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION action_try_advisory_lock(
    p_action_name  TEXT,
    p_resource_key TEXT
) RETURNS BOOLEAN LANGUAGE sql AS $$
    -- Session-scoped lock. Must be released via action_advisory_unlock.
    SELECT pg_try_advisory_lock(
        hashtextextended(p_action_name || '|' || p_resource_key, 0)
    );
$$;

CREATE OR REPLACE FUNCTION action_advisory_unlock(
    p_action_name  TEXT,
    p_resource_key TEXT
) RETURNS BOOLEAN LANGUAGE sql AS $$
    SELECT pg_advisory_unlock(
        hashtextextended(p_action_name || '|' || p_resource_key, 0)
    );
$$;

COMMIT;

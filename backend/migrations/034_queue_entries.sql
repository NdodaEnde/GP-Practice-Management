-- ============================================================================
-- Migration 034 — queue_entries (reception / workflow queue) onto Supabase
-- ============================================================================
--
-- The reception queue was the last Professional feature still backed by
-- MongoDB (db.queue_entries). It is migrated onto the unified foundation:
-- one Supabase table, tenant-scoped by workspace_id derived from the caller's
-- token (server.py /queue/* handlers), RLS deny-all underneath like every
-- other tenant table (see 033 for the threat model / design).
--
-- One queue entry = one patient check-in for a day, moving through stations
-- (reception -> vitals -> consultation -> dispensary) until completed.
--
-- The Mongo version also wrote bespoke db.audit_events rows per queue action.
-- Those had NO reader and NO Supabase home (action_audit_log is the
-- ActionExecutor's strict ontology-action surface, not a free-form event log),
-- so the rebuild does NOT carry them. A first-class queue audit trail is a
-- separate, deliberate decision if ever needed — named, not silently dropped.
--
-- Idempotent: safe to re-run.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS queue_entries (
    id                 UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       TEXT         NOT NULL,
    tenant_id          TEXT,
    queue_number       INT          NOT NULL,
    patient_id         UUID         NOT NULL,
    patient_name       TEXT,
    reason_for_visit   TEXT,
    priority           TEXT         NOT NULL DEFAULT 'normal',   -- normal | urgent | emergency
    status             TEXT         NOT NULL DEFAULT 'waiting',  -- waiting | in_vitals | in_consultation | in_dispensary | completed | cancelled
    station            TEXT         NOT NULL DEFAULT 'reception',-- reception | vitals | consultation | dispensary
    queue_date         DATE         NOT NULL,
    check_in_time      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    called_at          TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    notes              TEXT,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ
);

-- The hot query: today's active queue for a workspace, ordered by number.
CREATE INDEX IF NOT EXISTS idx_queue_entries_ws_date
    ON queue_entries (workspace_id, queue_date, queue_number);

-- RLS deny-all (service_role / postgres bypass) — identical posture to 033.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'queue_entries' AND c.relrowsecurity = FALSE
    ) THEN
        EXECUTE 'ALTER TABLE public.queue_entries ENABLE ROW LEVEL SECURITY';
    END IF;
END $$;

COMMIT;

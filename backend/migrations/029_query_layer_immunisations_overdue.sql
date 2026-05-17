-- ============================================================================
-- Migration 029 — query_immunisations_overdue (Phase 4 PR G, option B)
-- ============================================================================
--
-- PR G ships ONE real derived cohort (G-1=B locked): patients with an
-- overdue next immunisation dose. STATELESS recomputed cohort (locked
-- Decision 3 / §2.0) — NOT an OpenLoop; no per-row lifecycle. It is a
-- new StandingQuery kind materialising into briefing_items through the
-- SAME run_template+resolve_provenance chokepoint morning_briefing uses
-- — zero new data path, the PR-D "configuration, not a project" payoff.
--
-- THE FUNCTION (mirrors query_patients_not_seen_since, migration 026
-- verbatim idiom):
--   * LANGUAGE sql STABLE. Pure read — never mutates, never audited.
--   * p_workspace_id is the MANDATORY first parameter; the WHERE clause
--     is the structural tenant scope (i.workspace_id = p_workspace_id).
--   * Returns TABLE(... provenance jsonb). PROVENANCE IS HONEST
--     live_entry: the immunizations table has NO source_document_id
--     column (probed 2026-05-17) — immunisations are entered directly in
--     the EHR, there is no source scan. So provenance resolves NO_SOURCE
--     ("entered directly in the EHR"), exactly the honest NULL-sourced
--     case the resolver already handles for demo-gp. This is NOT faked
--     and NOT an error — it is the true provenance of EHR-direct data.
--
-- DATA MATURITY: "thin" (G-3 locked) — 1 overdue of 31 immunisations on
-- the live corpus (probed). Real, but ONE instance. The template
-- declares data_maturity="thin"; a reader must not infer volume.
--
-- NOTIFY pgrst: INCLUDED and REQUIRED — 029 adds a function; without the
-- NOTIFY the new RPC is invisible to PostgREST until the schema cache
-- happens to reload (the Phase-0 finding; the 026 discipline verbatim).
--
-- APPLICATION: this migration is SURFACED for the user's per-migration
-- call. It is NOT auto-applied by the assistant — the
-- assistant-auto-applies-migrations standing rule is REJECTED-tombstoned;
-- migration 028 was the one-time exception, explicitly NOT precedent.
-- The RUN_INTEGRATION materialisation test (read-back of the real
-- overdue row) cannot pass until the user applies this migration.
--
-- ORDERING: strictly after 028. Adds a function; standard deploy.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION query_immunisations_overdue(
    p_workspace_id  TEXT
)
RETURNS TABLE(
    patient_id      TEXT,
    first_name      TEXT,
    last_name       TEXT,
    dob             TEXT,
    vaccine_name    TEXT,
    next_dose_due   TEXT,
    provenance      JSONB
)
LANGUAGE sql STABLE AS $$
    SELECT
        p.id, p.first_name, p.last_name, p.dob,
        i.vaccine_name,
        to_char(i.next_dose_due, 'YYYY-MM-DD'),
        jsonb_build_object(
            -- immunizations has NO source_document_id: EHR-direct ⇒
            -- live_entry ⇒ resolver renders NO_SOURCE (honest, not error)
            'source_kind',        'live_entry',
            'source_document_id', NULL,
            'occurred_on',        to_char(i.next_dose_due, 'YYYY-MM-DD'),
            'snippet',
            COALESCE(i.vaccine_name, 'immunisation')
              || ' next dose overdue since '
              || to_char(i.next_dose_due, 'YYYY-MM-DD'),
            'page', NULL
        )
    FROM immunizations i
    JOIN patients p
      ON p.id = i.patient_id
     AND p.workspace_id = i.workspace_id
     AND p.deleted_at IS NULL
    WHERE i.workspace_id = p_workspace_id            -- structural tenant scope
      AND COALESCE(i.series_complete, FALSE) = FALSE
      AND i.next_dose_due IS NOT NULL
      AND i.next_dose_due < current_date
    ORDER BY i.next_dose_due ASC, p.last_name, p.first_name
    LIMIT 500
$$;

COMMENT ON FUNCTION query_immunisations_overdue(TEXT)
IS 'PR G (option B). Patients with an overdue next immunisation dose '
   '(series not complete, next_dose_due < today). STATELESS derived '
   'cohort, NOT an OpenLoop. Provenance = live_entry (immunisations are '
   'EHR-direct; no source_document_id) ⇒ resolves NO_SOURCE honestly.';

NOTIFY pgrst, 'reload schema';

COMMIT;

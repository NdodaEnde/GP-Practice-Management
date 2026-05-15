-- ============================================================================
-- Migration 020 — Schema additions for PR 3 actions (patients + prescriptions)
-- ============================================================================
--
-- Three new Actions in PR 3 need columns this migration adds:
--
--   SoftDeletePatient (POPIA right-to-erasure, reversible):
--     - patients.deleted_at  TIMESTAMPTZ
--     - patients.deletion_reason TEXT
--
--   MergePatient (consolidate duplicate records into one):
--     - patients.merged_into_patient_id  TEXT REFERENCES patients(id)
--
--   VoidPrescription (soft-cancel an active prescription, reversible):
--     - prescriptions.void_reason TEXT
--
-- Soft-delete is reversible by design — POPIA permits erasure, but a
-- mistakenly-deleted patient must be restorable within a retention
-- window. The `deleted_at` column is the soft-flag; reversal sets it
-- back to NULL.
--
-- Merge re-points every child row (encounters, prescriptions, etc.)
-- from a source patient to a target patient, then soft-deletes the
-- source with `merged_into_patient_id` pointing at the survivor. A
-- regulator asking "where did this patient go?" gets a clean trail.
--
-- IDEMPOTENT — safe to re-run. All ADD COLUMN clauses use IF NOT EXISTS.
--
-- Indexes:
--   idx_patients_active — the canonical hot-path filter; every patient-
--     facing query gets a `WHERE deleted_at IS NULL` clause AFTER PR 3
--     code lands. The partial index keeps the scan cheap.
--   idx_patients_merged_into — for "show me every patient consolidated
--     into this survivor" admin queries.
--
-- ORDERING NOTE: ships FIRST in the PR 3 migration sequence (before 021
-- and 022) because both ReassignDocument and MergePatient rely on these
-- columns. Application code that queries patients without filtering on
-- deleted_at IS NULL keeps working until the per-query sweep lands in
-- the SAME PR — the column defaults to NULL, so existing rows are still
-- visible to queries that don't filter.
-- ============================================================================

BEGIN;

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS deleted_at              TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deletion_reason         TEXT,
    ADD COLUMN IF NOT EXISTS merged_into_patient_id  TEXT REFERENCES patients(id);

-- Partial index for the canonical "active patients" filter — every
-- per-workspace patient-list query will use this once code-side filters
-- are added.
CREATE INDEX IF NOT EXISTS idx_patients_active
    ON patients (workspace_id)
    WHERE deleted_at IS NULL;

-- For admin queries: "show all patients that were consolidated into X"
CREATE INDEX IF NOT EXISTS idx_patients_merged_into
    ON patients (merged_into_patient_id)
    WHERE merged_into_patient_id IS NOT NULL;

COMMENT ON COLUMN patients.deleted_at IS
    'Soft-delete flag for POPIA right-to-erasure. NULL = active. '
    'Set by the SoftDeletePatient or MergePatient action. Reversible '
    'via executor.reverse() within the retention window (no retention '
    'job exists yet — see PR 4 roadmap).';

COMMENT ON COLUMN patients.merged_into_patient_id IS
    'When a patient is merged into another, this points at the survivor. '
    'Set by MergePatient on the source-patient row; the target row is '
    'untouched. Reversed by reverse_action_merge_patient.';


-- ----------------------------------------------------------------------------
-- prescriptions.void_reason — for VoidPrescription action
-- ----------------------------------------------------------------------------
--
-- A reason string captured at void time. Queryable column (rather than
-- stuffing it into notes) so admin dashboards can answer "why did we
-- void this prescription class?" without parsing free text.
--
-- Reversal does NOT clear the column on its own — the audit row's
-- parameters carry previous_status; void_reason is informational, not
-- a load-bearing state-restoration field.
-- ----------------------------------------------------------------------------

ALTER TABLE prescriptions
    ADD COLUMN IF NOT EXISTS void_reason TEXT;

COMMENT ON COLUMN prescriptions.void_reason IS
    'Reason captured when the VoidPrescription action soft-cancels a '
    'prescription. NULL for prescriptions that have never been voided. '
    'Survives reversal (the audit row carries the load-bearing state).';

COMMIT;

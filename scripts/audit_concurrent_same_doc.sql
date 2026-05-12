-- ============================================================================
-- Concurrent same-document promotion detection — operational safety net
-- ============================================================================
--
-- This query is the post-hoc detection mechanism PR 1 relies on, given
-- that Phase 0 verification (test_advisory_lock_semantics.py) revealed
-- that real mutual exclusion is not achievable at the Supabase REST
-- client layer. PR 2's PL/pgSQL port closes the gap by running the
-- entire mutation inside one Postgres transaction; until then, this
-- query is how we detect that the race we couldn't prevent fired.
--
-- WHO RUNS THIS, AND HOW OFTEN
--
--   Recommended: nightly via cron / scheduled GitHub Action / Supabase
--   Edge Function. The query is cheap (single index lookup per row;
--   uses idx_action_audit_log_practice_started). At 10K audit rows it
--   runs in milliseconds.
--
--   Manual: copy-paste into Supabase Dashboard SQL Editor whenever
--   investigating an audit-trail anomaly.
--
-- WHAT EACH RETURNED ROW MEANS
--
--   A returned row indicates that two PromoteDocumentToPatientRecord
--   actions targeted the same source document within 5 seconds of each
--   other. Both audit rows landed; the question is whether both promote
--   operations actually committed (the existing wipe-and-rewrite means
--   the SECOND promotion's wipe deleted the FIRST promotion's writes,
--   then re-inserted — so the FIRST audit row's affected_objects no
--   longer reference live database state).
--
-- PLAYBOOK WHEN ROWS RETURN
--
--   1. For each pair (audit_a, audit_b), determine which finished
--      last by comparing finished_at timestamps.
--   2. The LATER promotion's writes are the live state. The earlier
--      promotion's audit row's affected_objects entries are stale —
--      those object IDs were wiped by the second promotion's wipe phase.
--   3. Decide whether the two promotions agreed on the patient match.
--      Different forced_patient_id values across the pair = a real
--      coordination problem requiring manual review.
--      Same patient_id with same extractions = benign re-promotion;
--      no data corruption (current state IS the second promotion's).
--   4. If the audit timeline is being shown to a regulator, annotate
--      the earlier row with reversed_by_audit_id = audit_b.id so the
--      replaced-by relationship is explicit in the audit trail.
--
-- WHEN THIS QUERY GOES AWAY
--
--   PR 2's PL/pgSQL port acquires FOR UPDATE NOWAIT on the source
--   document row inside the RPC transaction. The second concurrent
--   call fails fast with action_locked; this query will return zero
--   rows from the day PR 2 ships. The query can be retired then.
-- ============================================================================

WITH window AS (
    -- Look-back window. 24 hours for nightly; 7 days for weekly review.
    SELECT now() - INTERVAL '24 hours' AS since
),
ranked AS (
    SELECT
        id,
        practice_id,
        actor_user_id,
        parameters->>'document_id' AS document_id,
        parameters->>'target_patient_id' AS target_patient_id,
        parameters->>'forced_patient_id' AS forced_patient_id,
        outcome,
        started_at,
        finished_at,
        duration_ms,
        LAG(id) OVER w AS prev_audit_id,
        LAG(started_at) OVER w AS prev_started_at,
        LAG(finished_at) OVER w AS prev_finished_at,
        LAG(parameters->>'forced_patient_id') OVER w AS prev_forced_patient_id
      FROM action_audit_log
     WHERE action_name = 'PromoteDocumentToPatientRecord'
       AND dry_run = FALSE
       AND outcome IN ('success', 'effect_failed')
       AND started_at > (SELECT since FROM window)
    WINDOW w AS (
        PARTITION BY parameters->>'document_id'
        ORDER BY started_at ASC
    )
)
SELECT
    document_id,
    practice_id,
    prev_audit_id        AS earlier_audit_id,
    id                   AS later_audit_id,
    prev_started_at      AS earlier_started_at,
    started_at           AS later_started_at,
    (started_at - prev_started_at)              AS gap_between_starts,
    (started_at - prev_finished_at)             AS overlap_or_gap,
    prev_forced_patient_id                       AS earlier_target_patient,
    forced_patient_id                            AS later_target_patient,
    (prev_forced_patient_id IS DISTINCT FROM forced_patient_id) AS targeted_different_patients
FROM ranked
WHERE prev_audit_id IS NOT NULL
  AND (started_at - prev_started_at) < INTERVAL '5 seconds'
ORDER BY started_at DESC;

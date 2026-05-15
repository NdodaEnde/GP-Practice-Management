-- ============================================================================
-- Migration 022 — Merge-patient RPCs (PR 3)
-- ============================================================================
--
-- MergePatient consolidates two patient records into one. Every child
-- row carrying patient_id = source is re-pointed to target. The source
-- patient is then soft-deleted with `merged_into_patient_id = target`
-- so the audit trail makes the consolidation explicit and a future
-- "show me every patient consolidated into X" query is cheap.
--
-- HIGHEST-BLAST-RADIUS ACTION IN THE SYSTEM. Re-points across 10 child
-- tables in one transaction. Mutual exclusion via FOR UPDATE NOWAIT on
-- BOTH patient rows; locking ordered by id to avoid deadlock with a
-- concurrent reverse-direction merge.
--
-- TABLES TOUCHED (10 + patients itself)
--
--   encounters, diagnoses, vitals, allergies, prescriptions,
--   document_refs, digitised_documents, sick_notes, referrals,
--   clinical_notes
--
-- CRITICAL: this list MUST be kept in sync with the schema. If a future
-- migration adds a new table with patient_id, MergePatient leaves rows
-- in that table pointing at the soft-deleted source patient. A CI test
-- (TODO post-PR 3) will introspect pg_constraint for every FK to
-- patients(id) and assert every referenced table appears here.
--
-- REVERSAL
--
--   reverse_action_merge_patient reads affected_objects (each entry
--   carries previous_patient_id), restores each row's patient_id,
--   clears the source patient's deleted_at + merged_into_patient_id,
--   writes the new reversal audit row, updates the original's
--   reversed_by_audit_id. All atomic.
--
-- IDEMPOTENT — safe to re-run.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION execute_action_merge_patient(
    p_source_patient_id  TEXT,
    p_target_patient_id  TEXT,
    p_workspace_id       TEXT,
    p_merge_reason       TEXT,
    p_created_by         TEXT
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_first_lock  TEXT;
    v_second_lock TEXT;
    v_source_row  RECORD;
    v_target_row  RECORD;
    v_affected    JSONB := '[]'::JSONB;
    v_counts      JSONB := '{}'::JSONB;
    v_count_enc          INT := 0;
    v_count_diag         INT := 0;
    v_count_vital        INT := 0;
    v_count_allergy      INT := 0;
    v_count_rx           INT := 0;
    v_count_docref       INT := 0;
    v_count_digidoc      INT := 0;
    v_count_sicknote     INT := 0;
    v_count_referral     INT := 0;
    v_count_clinnote     INT := 0;
    v_row                RECORD;
BEGIN
    SET LOCAL statement_timeout = '30s';

    -- Reject same-row merge.
    IF p_source_patient_id = p_target_patient_id THEN
        RAISE EXCEPTION 'cannot merge patient % into itself', p_source_patient_id
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    -- ------------------------------------------------------------------------
    -- Acquire locks in deterministic order (lower id first). Avoids
    -- deadlock with a reverse-direction concurrent merge (B → A while
    -- this one does A → B).
    -- ------------------------------------------------------------------------
    IF p_source_patient_id < p_target_patient_id THEN
        v_first_lock := p_source_patient_id;
        v_second_lock := p_target_patient_id;
    ELSE
        v_first_lock := p_target_patient_id;
        v_second_lock := p_source_patient_id;
    END IF;

    PERFORM 1 FROM patients
     WHERE id = v_first_lock AND workspace_id = p_workspace_id
     FOR UPDATE NOWAIT;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'patient % not found in workspace %', v_first_lock, p_workspace_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;
    PERFORM 1 FROM patients
     WHERE id = v_second_lock AND workspace_id = p_workspace_id
     FOR UPDATE NOWAIT;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'patient % not found in workspace %', v_second_lock, p_workspace_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;

    -- ------------------------------------------------------------------------
    -- Sanity: source must not already be soft-deleted; target must not
    -- be soft-deleted; neither must already be merged.
    -- ------------------------------------------------------------------------
    SELECT * INTO v_source_row FROM patients
     WHERE id = p_source_patient_id AND workspace_id = p_workspace_id;
    SELECT * INTO v_target_row FROM patients
     WHERE id = p_target_patient_id AND workspace_id = p_workspace_id;

    IF v_source_row.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'source patient % is already soft-deleted', p_source_patient_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;
    IF v_target_row.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'target patient % is soft-deleted', p_target_patient_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;

    -- ------------------------------------------------------------------------
    -- Per-table re-point. Each block: SELECT to capture affected_objects,
    -- then UPDATE. Same pattern for all 10 tables.
    -- ------------------------------------------------------------------------

    -- encounters
    FOR v_row IN SELECT id FROM encounters WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Consultation', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_enc := v_count_enc + 1;
    END LOOP;
    UPDATE encounters SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- diagnoses
    FOR v_row IN SELECT id FROM diagnoses WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Diagnosis', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_diag := v_count_diag + 1;
    END LOOP;
    UPDATE diagnoses SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- vitals
    FOR v_row IN SELECT id FROM vitals WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Vital', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_vital := v_count_vital + 1;
    END LOOP;
    UPDATE vitals SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- allergies
    FOR v_row IN SELECT id FROM allergies WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Allergy', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_allergy := v_count_allergy + 1;
    END LOOP;
    UPDATE allergies SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- prescriptions
    FOR v_row IN SELECT id FROM prescriptions WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Prescription', 'id', v_row.id, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_rx := v_count_rx + 1;
    END LOOP;
    UPDATE prescriptions SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- document_refs
    FOR v_row IN SELECT id FROM document_refs WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'DocumentRef', 'id', v_row.id, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_docref := v_count_docref + 1;
    END LOOP;
    UPDATE document_refs SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- digitised_documents
    FOR v_row IN SELECT id FROM digitised_documents WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Document', 'id', v_row.id, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_digidoc := v_count_digidoc + 1;
    END LOOP;
    UPDATE digitised_documents SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- sick_notes
    FOR v_row IN SELECT id FROM sick_notes WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'SickNote', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_sicknote := v_count_sicknote + 1;
    END LOOP;
    UPDATE sick_notes SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- referrals
    FOR v_row IN SELECT id FROM referrals WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Referral', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_referral := v_count_referral + 1;
    END LOOP;
    UPDATE referrals SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- clinical_notes
    FOR v_row IN SELECT id FROM clinical_notes WHERE patient_id = p_source_patient_id LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'ClinicalNote', 'id', v_row.id::TEXT, 'op', 'updated',
            'previous_patient_id', p_source_patient_id));
        v_count_clinnote := v_count_clinnote + 1;
    END LOOP;
    UPDATE clinical_notes SET patient_id = p_target_patient_id
     WHERE patient_id = p_source_patient_id;

    -- ------------------------------------------------------------------------
    -- Soft-delete the source patient with merge metadata.
    -- ------------------------------------------------------------------------
    UPDATE patients
       SET deleted_at = now(),
           deletion_reason = 'merged',
           merged_into_patient_id = p_target_patient_id
     WHERE id = p_source_patient_id;

    v_affected := v_affected || jsonb_build_array(jsonb_build_object(
        'type', 'Patient',
        'id', p_source_patient_id,
        'op', 'soft_deleted',
        'merged_into_patient_id', p_target_patient_id
    ));

    v_counts := jsonb_build_object(
        'encounters', v_count_enc,
        'diagnoses', v_count_diag,
        'vitals', v_count_vital,
        'allergies', v_count_allergy,
        'prescriptions', v_count_rx,
        'document_refs', v_count_docref,
        'digitised_documents', v_count_digidoc,
        'sick_notes', v_count_sicknote,
        'referrals', v_count_referral,
        'clinical_notes', v_count_clinnote
    );

    RETURN jsonb_build_object(
        'source_patient_id', p_source_patient_id,
        'target_patient_id', p_target_patient_id,
        'merge_reason', p_merge_reason,
        'counts', v_counts,
        'affected_objects', v_affected
    );
END;
$$;

COMMENT ON FUNCTION execute_action_merge_patient(TEXT, TEXT, TEXT, TEXT, TEXT) IS
    'PR 3: consolidate two patients into one. Re-points 10 child tables, '
    'soft-deletes source with merged_into pointer. FOR UPDATE NOWAIT on '
    'both patient rows; deterministic lock order to avoid deadlocks.';


-- ============================================================================
-- reverse_action_merge_patient
-- ============================================================================

CREATE OR REPLACE FUNCTION reverse_action_merge_patient(
    p_audit_id        UUID,
    p_actor_user_id   TEXT,
    p_reason          TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_audit              action_audit_log%ROWTYPE;
    v_affected           JSONB;
    v_entry              JSONB;
    v_new_audit_id       UUID;
    v_reverse_affected   JSONB := '[]'::JSONB;
    v_started_at         TIMESTAMPTZ;
    v_finished_at        TIMESTAMPTZ;
    v_source_patient_id  TEXT;
    v_restored           INT := 0;
BEGIN
    SET LOCAL statement_timeout = '30s';
    v_started_at := now();

    SELECT * INTO v_audit FROM action_audit_log
     WHERE id = p_audit_id FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'action_audit_log row not found: %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;
    IF v_audit.dry_run THEN
        RAISE EXCEPTION 'cannot reverse dry-run row %', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'cannot_reverse_dry_run';
    END IF;
    IF v_audit.reversed_by_audit_id IS NOT NULL THEN
        RAISE EXCEPTION 'audit row % already reversed', p_audit_id
            USING ERRCODE = 'P0001', HINT = 'precondition_failed';
    END IF;
    IF v_audit.action_name <> 'MergePatient' THEN
        RAISE EXCEPTION 'reverse_action_merge_patient called on action %', v_audit.action_name
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    v_affected := COALESCE(v_audit.affected_objects, '[]'::JSONB);
    v_source_patient_id := v_audit.parameters ->> 'source_patient_id';

    -- Restore patient_id on every affected row + un-soft-delete the source.
    FOR v_entry IN SELECT * FROM jsonb_array_elements(v_affected) LOOP
        DECLARE
            v_type TEXT := v_entry ->> 'type';
            v_id   TEXT := v_entry ->> 'id';
            v_prev TEXT := v_entry ->> 'previous_patient_id';
        BEGIN
            IF v_type = 'Consultation' THEN
                UPDATE encounters SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Diagnosis' THEN
                UPDATE diagnoses SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Vital' THEN
                UPDATE vitals SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Allergy' THEN
                UPDATE allergies SET patient_id = v_prev WHERE id = v_id::UUID;
            ELSIF v_type = 'Prescription' THEN
                UPDATE prescriptions SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'DocumentRef' THEN
                UPDATE document_refs SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Document' THEN
                UPDATE digitised_documents SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'SickNote' THEN
                UPDATE sick_notes SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Referral' THEN
                UPDATE referrals SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'ClinicalNote' THEN
                UPDATE clinical_notes SET patient_id = v_prev WHERE id = v_id;
            ELSIF v_type = 'Patient' AND (v_entry ->> 'op') = 'soft_deleted' THEN
                -- Un-soft-delete the source patient.
                UPDATE patients
                   SET deleted_at = NULL,
                       deletion_reason = NULL,
                       merged_into_patient_id = NULL
                 WHERE id = v_id;
            END IF;
            v_restored := v_restored + 1;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type, 'id', v_id, 'op', 'reversed_update'
            ));
        END;
    END LOOP;

    v_new_audit_id := gen_random_uuid();
    v_finished_at := now();

    INSERT INTO action_audit_log (
        id, action_name, action_version, actor_user_id, actor_email,
        practice_id, workspace_id, idempotency_key, dry_run,
        parameters, preconditions_checked, effects_applied,
        affected_objects, outcome, error_detail,
        reverses_audit_id, reversed_by_audit_id,
        started_at, finished_at, duration_ms
    ) VALUES (
        v_new_audit_id, 'ReverseActionMergePatient', 1,
        p_actor_user_id, NULL,
        v_audit.practice_id, v_audit.workspace_id, NULL, FALSE,
        jsonb_build_object('reverses_audit_id', p_audit_id::TEXT, 'reason', p_reason),
        '[]'::JSONB, '[]'::JSONB,
        v_reverse_affected, 'reversed', NULL,
        p_audit_id, NULL,
        v_started_at, v_finished_at,
        EXTRACT(MILLISECONDS FROM (v_finished_at - v_started_at))::INT
    );

    UPDATE action_audit_log SET reversed_by_audit_id = v_new_audit_id
     WHERE id = p_audit_id;

    RETURN jsonb_build_object(
        'audit_id', v_new_audit_id,
        'reverses_audit_id', p_audit_id,
        'outcome', 'reversed',
        'restored_count', v_restored,
        'affected_objects', v_reverse_affected
    );
END;
$$;

COMMENT ON FUNCTION reverse_action_merge_patient(UUID, TEXT, TEXT) IS
    'PR 3: undo a MergePatient. Restores every affected row''s '
    'patient_id and clears the source patient''s soft-delete + merge '
    'metadata.';

COMMIT;

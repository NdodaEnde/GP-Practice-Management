-- ============================================================================
-- Migration 021 — Reassign-document RPCs (PR 3)
-- ============================================================================
--
-- ReassignDocument re-points a single document's structured data from
-- one patient to another. Used when a document was incorrectly linked
-- (e.g. a reviewer approved into the wrong patient and only noticed
-- after promote). The whole sweep runs in one transaction with
-- SELECT...FOR UPDATE NOWAIT on the digitised_documents row, matching
-- the mutual-exclusion semantics PR 2 established.
--
-- TABLES TOUCHED
--
--   digitised_documents:  UPDATE patient_id = new WHERE id = doc_id
--   encounters:           UPDATE patient_id = new WHERE source_document_id = doc_id
--   diagnoses:            same
--   vitals:               same
--   allergies:            same
--   prescriptions:        same
--   prescription_items:   NOT TOUCHED (no patient_id column; reaches the
--                         patient transitively via prescription)
--
-- AFFECTED OBJECTS
--
--   Every re-pointed row appends to affected_objects with op='updated'
--   and a `previous_patient_id` field so reversal can restore.
--   The Document entry carries the document's own previous_patient_id.
--
-- REVERSAL
--
--   reverse_action_reassign_document iterates affected_objects, restores
--   each row's patient_id to its `previous_patient_id`, writes the new
--   reversal audit row, updates the original audit row's
--   reversed_by_audit_id. Same atomicity envelope as migration 015's
--   reverse RPC.
--
-- IDEMPOTENT — safe to re-run.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION execute_action_reassign_document(
    p_document_id        TEXT,
    p_workspace_id       TEXT,
    p_new_patient_id     TEXT,
    p_reason             TEXT,
    p_created_by         TEXT
) RETURNS JSONB
LANGUAGE plpgsql AS $$
DECLARE
    v_locked_id          TEXT;
    v_prev_patient_id    TEXT;
    v_affected           JSONB := '[]'::JSONB;
    v_count_enc          INT := 0;
    v_count_diag         INT := 0;
    v_count_vital        INT := 0;
    v_count_allergy      INT := 0;
    v_count_rx           INT := 0;
    v_row                RECORD;
BEGIN
    SET LOCAL statement_timeout = '15s';

    -- ------------------------------------------------------------------------
    -- 1. Lock the document row. FOR UPDATE NOWAIT raises 55P03 if another
    -- transaction holds it; Python maps to ErrorDetail(code='action_locked').
    -- ------------------------------------------------------------------------
    SELECT id, patient_id
      INTO v_locked_id, v_prev_patient_id
      FROM digitised_documents
     WHERE id = p_document_id
       AND workspace_id = p_workspace_id
     FOR UPDATE NOWAIT;

    IF v_locked_id IS NULL THEN
        RAISE EXCEPTION 'digitised_documents row not found: %', p_document_id
            USING ERRCODE = 'P0001', HINT = 'not_found';
    END IF;

    -- ------------------------------------------------------------------------
    -- 2. Verify the new patient exists in the same workspace + not soft-deleted.
    --    (Python preconditions also check these; this is the
    --    inside-transaction safety net.)
    -- ------------------------------------------------------------------------
    PERFORM 1 FROM patients
     WHERE id = p_new_patient_id
       AND workspace_id = p_workspace_id
       AND deleted_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'target patient % not found / soft-deleted / wrong workspace',
                        p_new_patient_id
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    -- ------------------------------------------------------------------------
    -- 3. Iterate each child table; for each row attached to this document
    --    via source_document_id, capture {id, previous_patient_id} in
    --    affected_objects then re-point patient_id.
    -- ------------------------------------------------------------------------

    -- Encounters
    FOR v_row IN
        SELECT id, patient_id
          FROM encounters
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Consultation',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_enc := v_count_enc + 1;
    END LOOP;
    UPDATE encounters
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Diagnoses
    FOR v_row IN
        SELECT id, patient_id
          FROM diagnoses
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Diagnosis',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_diag := v_count_diag + 1;
    END LOOP;
    UPDATE diagnoses
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Vitals
    FOR v_row IN
        SELECT id, patient_id
          FROM vitals
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Vital',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_vital := v_count_vital + 1;
    END LOOP;
    UPDATE vitals
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Allergies
    FOR v_row IN
        SELECT id, patient_id
          FROM allergies
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Allergy',
            'id', v_row.id::TEXT,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_allergy := v_count_allergy + 1;
    END LOOP;
    UPDATE allergies
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- Prescriptions
    FOR v_row IN
        SELECT id, patient_id
          FROM prescriptions
         WHERE source_document_id = p_document_id
    LOOP
        v_affected := v_affected || jsonb_build_array(jsonb_build_object(
            'type', 'Prescription',
            'id', v_row.id,
            'op', 'updated',
            'previous_patient_id', v_row.patient_id
        ));
        v_count_rx := v_count_rx + 1;
    END LOOP;
    UPDATE prescriptions
       SET patient_id = p_new_patient_id
     WHERE source_document_id = p_document_id;

    -- The document itself
    UPDATE digitised_documents
       SET patient_id = p_new_patient_id,
           updated_at = now()
     WHERE id = p_document_id;

    v_affected := v_affected || jsonb_build_array(jsonb_build_object(
        'type', 'Document',
        'id', p_document_id,
        'op', 'updated',
        'previous_patient_id', v_prev_patient_id
    ));

    RETURN jsonb_build_object(
        'document_id',         p_document_id,
        'new_patient_id',      p_new_patient_id,
        'previous_patient_id', v_prev_patient_id,
        'counts', jsonb_build_object(
            'encounters',    v_count_enc,
            'diagnoses',     v_count_diag,
            'vitals',        v_count_vital,
            'allergies',     v_count_allergy,
            'prescriptions', v_count_rx
        ),
        'affected_objects', v_affected
    );
END;
$$;

COMMENT ON FUNCTION execute_action_reassign_document(TEXT, TEXT, TEXT, TEXT, TEXT) IS
    'PR 3: re-point all rows linked to a document from one patient to '
    'another, in one transaction with FOR UPDATE NOWAIT on the document. '
    'Returns affected_objects with previous_patient_id for reversal.';


-- ============================================================================
-- reverse_action_reassign_document
-- ============================================================================

CREATE OR REPLACE FUNCTION reverse_action_reassign_document(
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
    v_restored           INT := 0;
BEGIN
    SET LOCAL statement_timeout = '15s';
    v_started_at := now();

    -- Load + lock the original audit row.
    SELECT * INTO v_audit
      FROM action_audit_log
     WHERE id = p_audit_id
     FOR UPDATE NOWAIT;

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
    IF v_audit.action_name <> 'ReassignDocument' THEN
        RAISE EXCEPTION 'reverse_action_reassign_document called on action %',
                        v_audit.action_name
            USING ERRCODE = 'P0001', HINT = 'invariant_violated';
    END IF;

    v_affected := COALESCE(v_audit.affected_objects, '[]'::JSONB);

    -- Restore patient_id on every affected row.
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
            ELSIF v_type = 'Document' THEN
                UPDATE digitised_documents
                   SET patient_id = v_prev, updated_at = now()
                 WHERE id = v_id;
            END IF;
            v_restored := v_restored + 1;
            v_reverse_affected := v_reverse_affected || jsonb_build_array(jsonb_build_object(
                'type', v_type,
                'id', v_id,
                'op', 'reversed_update',
                'restored_patient_id', v_prev
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
        v_new_audit_id, 'ReverseActionReassignDocument', 1,
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
        'audit_id',         v_new_audit_id,
        'reverses_audit_id', p_audit_id,
        'outcome',          'reversed',
        'restored_count',   v_restored,
        'affected_objects', v_reverse_affected
    );
END;
$$;

COMMENT ON FUNCTION reverse_action_reassign_document(UUID, TEXT, TEXT) IS
    'PR 3: undo a ReassignDocument by restoring each affected row''s '
    'patient_id from the audit row''s previous_patient_id field.';

COMMIT;

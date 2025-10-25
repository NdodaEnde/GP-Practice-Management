-- =============================================
-- SPRINT 2.1: STRUCTURED CLINICAL NOTES
-- Convert AI Scribe SOAP notes to structured data
-- =============================================

DROP TABLE IF EXISTS clinical_notes CASCADE;

CREATE TABLE clinical_notes (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    encounter_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    
    -- Note type and format
    format TEXT CHECK (format IN ('soap', 'free_text', 'discharge_summary', 'referral_letter', 'procedure_note', 'progress_note')) DEFAULT 'soap',
    
    -- SOAP structure (main fields)
    subjective TEXT,
    objective TEXT,
    assessment TEXT,
    plan TEXT,
    
    -- Free text fallback for non-SOAP notes
    raw_text TEXT,
    
    -- Metadata
    note_datetime TIMESTAMPTZ DEFAULT NOW(),
    author TEXT,
    role TEXT CHECK (role IN ('doctor', 'nurse', 'pharmacist', 'therapist', 'other', 'ai_scribe')) DEFAULT 'doctor',
    
    -- Source tracking
    source TEXT CHECK (source IN ('ai_scribe', 'manual_entry', 'document_extraction', 'imported')) DEFAULT 'ai_scribe',
    source_document_id TEXT,
    
    -- Signature and approval
    signed BOOLEAN DEFAULT false,
    signed_at TIMESTAMPTZ,
    signed_by TEXT,
    
    -- Version control for edits
    version INTEGER DEFAULT 1,
    parent_note_id TEXT REFERENCES clinical_notes(id),
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

CREATE INDEX idx_clinical_notes_encounter ON clinical_notes(encounter_id);
CREATE INDEX idx_clinical_notes_patient ON clinical_notes(patient_id, note_datetime DESC);
CREATE INDEX idx_clinical_notes_workspace ON clinical_notes(workspace_id, tenant_id);
CREATE INDEX idx_clinical_notes_author ON clinical_notes(author, note_datetime DESC);
CREATE INDEX idx_clinical_notes_unsigned ON clinical_notes(workspace_id, signed) WHERE signed = false;

-- Full-text search on all SOAP fields
CREATE INDEX idx_clinical_notes_fulltext ON clinical_notes 
USING gin(to_tsvector('english', 
    COALESCE(subjective, '') || ' ' || 
    COALESCE(objective, '') || ' ' || 
    COALESCE(assessment, '') || ' ' || 
    COALESCE(plan, '') || ' ' || 
    COALESCE(raw_text, '')
));

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE clinical_notes IS 'Structured clinical documentation - SOAP notes, progress notes, discharge summaries';
COMMENT ON COLUMN clinical_notes.format IS 'Type of clinical note (soap, free_text, etc.)';
COMMENT ON COLUMN clinical_notes.subjective IS 'S - Patient symptoms, complaints, history';
COMMENT ON COLUMN clinical_notes.objective IS 'O - Physical findings, vitals, test results';
COMMENT ON COLUMN clinical_notes.assessment IS 'A - Clinical diagnosis and impressions';
COMMENT ON COLUMN clinical_notes.plan IS 'P - Treatment plan, medications, follow-up';
COMMENT ON COLUMN clinical_notes.source IS 'Origin of the note (AI Scribe, manual entry, etc.)';
COMMENT ON COLUMN clinical_notes.version IS 'Version number for edited notes';
COMMENT ON COLUMN clinical_notes.parent_note_id IS 'Links to original note if this is an amendment';

-- =============================================
-- VIEW FOR BACKWARD COMPATIBILITY
-- =============================================

-- This view combines structured SOAP into single text field for compatibility
CREATE OR REPLACE VIEW encounters_with_notes AS
SELECT 
    e.*,
    CASE 
        WHEN cn.id IS NOT NULL THEN 
            '**SUBJECTIVE:**' || E'\n' || COALESCE(cn.subjective, '') || E'\n\n' ||
            '**OBJECTIVE:**' || E'\n' || COALESCE(cn.objective, '') || E'\n\n' ||
            '**ASSESSMENT:**' || E'\n' || COALESCE(cn.assessment, '') || E'\n\n' ||
            '**PLAN:**' || E'\n' || COALESCE(cn.plan, '')
        ELSE e.gp_notes
    END as consolidated_notes,
    cn.id as clinical_note_id,
    cn.format as note_format,
    cn.signed as note_signed,
    cn.author as note_author
FROM encounters e
LEFT JOIN clinical_notes cn ON e.id = cn.encounter_id 
    AND cn.version = (
        SELECT MAX(version) 
        FROM clinical_notes 
        WHERE encounter_id = e.id
    );

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

SELECT 'Clinical notes table created successfully!' as message;
SELECT 'Created indexes for performance' as status;
SELECT 'Created compatibility view: encounters_with_notes' as status;

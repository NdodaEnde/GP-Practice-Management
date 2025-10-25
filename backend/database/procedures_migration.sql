-- =============================================
-- SPRINT 2.3: PROCEDURES TABLE
-- Track surgical and medical procedures
-- =============================================

DROP TABLE IF EXISTS procedures CASCADE;

CREATE TABLE procedures (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    encounter_id TEXT,
    patient_id TEXT NOT NULL,
    
    -- Procedure identification
    procedure_code TEXT,  -- CPT, ICD-10-PCS, or local code
    coding_system TEXT DEFAULT 'local',  -- 'cpt', 'icd10pcs', 'snomed', 'local'
    procedure_name TEXT NOT NULL,
    procedure_category TEXT,  -- Surgery, Diagnostic, Therapeutic, Preventive
    
    -- Procedure details
    procedure_datetime TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER,
    
    -- Clinical context
    indication TEXT,  -- Reason for procedure
    anatomical_site TEXT,  -- Body location/site
    laterality TEXT CHECK (laterality IN ('left', 'right', 'bilateral', 'not_applicable')),
    
    -- Personnel
    primary_surgeon TEXT,
    assistant_surgeon TEXT,
    anesthetist TEXT,
    performing_provider TEXT,
    
    -- Procedure status
    status TEXT CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled', 'postponed')) DEFAULT 'scheduled',
    outcome TEXT CHECK (outcome IN ('successful', 'partial', 'complicated', 'failed', 'aborted')),
    
    -- Clinical notes
    pre_operative_notes TEXT,
    operative_notes TEXT,
    post_operative_notes TEXT,
    complications TEXT,
    
    -- Billing
    billable BOOLEAN DEFAULT true,
    medical_aid_approved BOOLEAN,
    billing_code TEXT,  -- Medical aid billing code
    tariff_amount NUMERIC(10, 2),
    
    -- Follow-up
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_date DATE,
    follow_up_notes TEXT,
    
    -- Source tracking
    source TEXT CHECK (source IN ('manual_entry', 'theatre_system', 'imported')) DEFAULT 'manual_entry',
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

CREATE INDEX idx_procedures_patient ON procedures(patient_id, procedure_datetime DESC);
CREATE INDEX idx_procedures_encounter ON procedures(encounter_id);
CREATE INDEX idx_procedures_workspace ON procedures(workspace_id, tenant_id);
CREATE INDEX idx_procedures_provider ON procedures(performing_provider, procedure_datetime DESC);
CREATE INDEX idx_procedures_category ON procedures(procedure_category, status);
CREATE INDEX idx_procedures_status ON procedures(status, workspace_id);
CREATE INDEX idx_procedures_billable ON procedures(billable, status) WHERE billable = true;
CREATE INDEX idx_procedures_follow_up ON procedures(follow_up_date) WHERE follow_up_required = true;

-- Full-text search on procedure name and notes
CREATE INDEX idx_procedures_fulltext ON procedures 
USING gin(to_tsvector('english', 
    COALESCE(procedure_name, '') || ' ' || 
    COALESCE(indication, '') || ' ' || 
    COALESCE(operative_notes, '')
));

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE procedures IS 'Medical and surgical procedures performed on patients';
COMMENT ON COLUMN procedures.procedure_code IS 'CPT code, ICD-10-PCS, or local procedure code';
COMMENT ON COLUMN procedures.procedure_category IS 'Type of procedure: Surgery, Diagnostic, Therapeutic, Preventive';
COMMENT ON COLUMN procedures.laterality IS 'Body side: left, right, bilateral, or not applicable';
COMMENT ON COLUMN procedures.status IS 'Procedure lifecycle status';
COMMENT ON COLUMN procedures.outcome IS 'Result of the procedure';
COMMENT ON COLUMN procedures.billable IS 'Whether procedure can be billed to medical aid';
COMMENT ON COLUMN procedures.tariff_amount IS 'Standard tariff amount for billing';

-- =============================================
-- HELPER VIEW: PATIENT PROCEDURE SUMMARY
-- =============================================

CREATE OR REPLACE VIEW patient_procedure_summary AS
SELECT 
    p.patient_id,
    p.id as procedure_id,
    p.procedure_name,
    p.procedure_category,
    p.procedure_datetime,
    p.performing_provider,
    p.status,
    p.outcome,
    p.billable,
    e.encounter_date,
    e.chief_complaint
FROM procedures p
LEFT JOIN encounters e ON p.encounter_id = e.id
ORDER BY p.procedure_datetime DESC;

COMMENT ON VIEW patient_procedure_summary IS 'Quick overview of patient procedures';

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

SELECT 'Procedures table created successfully!' as message;
SELECT 'Created 8 performance indexes' as status;
SELECT 'Created patient_procedure_summary view' as status;

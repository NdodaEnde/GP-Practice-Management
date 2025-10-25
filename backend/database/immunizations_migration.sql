-- =============================================
-- SPRINT 2.4: IMMUNIZATIONS TABLE
-- Track vaccinations and immunization schedules
-- =============================================

DROP TABLE IF EXISTS immunizations CASCADE;

CREATE TABLE immunizations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    encounter_id TEXT,
    patient_id TEXT NOT NULL,
    
    -- Vaccine identification
    vaccine_code TEXT,  -- CVX code or local code
    vaccine_name TEXT NOT NULL,
    vaccine_type TEXT,  -- COVID-19, Influenza, Hepatitis B, etc.
    manufacturer TEXT,
    lot_number TEXT,
    
    -- Administration details
    administration_date DATE NOT NULL,
    dose_number INTEGER,  -- Which dose in series (1, 2, 3, etc.)
    dose_quantity NUMERIC(10, 2),
    dose_unit TEXT,  -- mL, units
    
    -- Route and site
    route TEXT,  -- Intramuscular, Subcutaneous, Oral, Intranasal
    anatomical_site TEXT,  -- Left deltoid, Right deltoid, Left thigh, etc.
    
    -- Series information
    series_name TEXT,  -- e.g., "Hepatitis B Series", "COVID-19 Primary Series"
    doses_in_series INTEGER,  -- Total doses in series
    series_complete BOOLEAN DEFAULT false,
    
    -- Next dose scheduling
    next_dose_due DATE,
    next_dose_overdue BOOLEAN DEFAULT false,
    
    -- Administering details
    administered_by TEXT,
    administering_provider TEXT,
    facility_name TEXT,
    
    -- Vaccine status
    status TEXT CHECK (status IN ('completed', 'not_done', 'refused', 'contraindicated')) DEFAULT 'completed',
    refusal_reason TEXT,
    contraindication_reason TEXT,
    
    -- Reactions and adverse events
    adverse_reaction BOOLEAN DEFAULT false,
    reaction_description TEXT,
    reaction_severity TEXT CHECK (reaction_severity IN ('mild', 'moderate', 'severe', 'life_threatening')),
    
    -- Clinical notes
    clinical_notes TEXT,
    consent_obtained BOOLEAN DEFAULT true,
    
    -- Occupational health specific
    occupational_requirement BOOLEAN DEFAULT false,
    employer_mandated BOOLEAN DEFAULT false,
    compliance_status TEXT CHECK (compliance_status IN ('compliant', 'overdue', 'exempt', 'pending')),
    
    -- Certification
    certificate_issued BOOLEAN DEFAULT false,
    certificate_number TEXT,
    certificate_expiry_date DATE,
    
    -- Billing
    billable BOOLEAN DEFAULT true,
    billing_code TEXT,
    vaccine_cost NUMERIC(10, 2),
    administration_fee NUMERIC(10, 2),
    
    -- Source tracking
    source TEXT CHECK (source IN ('manual_entry', 'imported', 'external_system')) DEFAULT 'manual_entry',
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

CREATE INDEX idx_immunizations_patient ON immunizations(patient_id, administration_date DESC);
CREATE INDEX idx_immunizations_encounter ON immunizations(encounter_id);
CREATE INDEX idx_immunizations_workspace ON immunizations(workspace_id, tenant_id);
CREATE INDEX idx_immunizations_vaccine_type ON immunizations(vaccine_type, administration_date DESC);
CREATE INDEX idx_immunizations_next_dose ON immunizations(next_dose_due) WHERE next_dose_due IS NOT NULL;
CREATE INDEX idx_immunizations_overdue ON immunizations(next_dose_overdue) WHERE next_dose_overdue = true;
CREATE INDEX idx_immunizations_occupational ON immunizations(patient_id, occupational_requirement) WHERE occupational_requirement = true;
CREATE INDEX idx_immunizations_status ON immunizations(status, workspace_id);

-- Full-text search
CREATE INDEX idx_immunizations_fulltext ON immunizations 
USING gin(to_tsvector('english', 
    COALESCE(vaccine_name, '') || ' ' || 
    COALESCE(vaccine_type, '') || ' ' || 
    COALESCE(clinical_notes, '')
));

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE immunizations IS 'Patient immunization records and vaccination history';
COMMENT ON COLUMN immunizations.vaccine_code IS 'CVX (vaccine administered) code or local identifier';
COMMENT ON COLUMN immunizations.dose_number IS 'Sequence number in multi-dose series (1, 2, 3, etc.)';
COMMENT ON COLUMN immunizations.series_complete IS 'Whether the vaccination series is complete';
COMMENT ON COLUMN immunizations.occupational_requirement IS 'Required for occupational health compliance';
COMMENT ON COLUMN immunizations.compliance_status IS 'Current compliance state for occupational requirements';

-- =============================================
-- HELPER VIEWS
-- =============================================

-- Patient immunization summary
CREATE OR REPLACE VIEW patient_immunization_summary AS
SELECT 
    i.patient_id,
    i.vaccine_type,
    COUNT(*) as total_doses,
    MAX(i.administration_date) as last_dose_date,
    MAX(i.next_dose_due) as next_due_date,
    BOOL_OR(i.series_complete) as any_series_complete,
    BOOL_OR(i.adverse_reaction) as has_adverse_reaction
FROM immunizations i
WHERE i.status = 'completed'
GROUP BY i.patient_id, i.vaccine_type;

COMMENT ON VIEW patient_immunization_summary IS 'Summary of patient immunizations by vaccine type';

-- Overdue immunizations
CREATE OR REPLACE VIEW overdue_immunizations AS
SELECT 
    i.patient_id,
    i.vaccine_name,
    i.vaccine_type,
    i.next_dose_due,
    CURRENT_DATE - i.next_dose_due as days_overdue,
    i.occupational_requirement,
    i.compliance_status
FROM immunizations i
WHERE i.next_dose_due < CURRENT_DATE
  AND i.status = 'completed'
  AND i.series_complete = false
ORDER BY i.next_dose_due;

COMMENT ON VIEW overdue_immunizations IS 'Patients with overdue vaccine doses';

-- Occupational compliance
CREATE OR REPLACE VIEW occupational_immunization_compliance AS
SELECT 
    i.patient_id,
    i.vaccine_type,
    i.compliance_status,
    i.next_dose_due,
    i.certificate_issued,
    i.certificate_expiry_date,
    CASE 
        WHEN i.certificate_expiry_date < CURRENT_DATE THEN true
        ELSE false
    END as certificate_expired
FROM immunizations i
WHERE i.occupational_requirement = true
  AND i.status = 'completed';

COMMENT ON VIEW occupational_immunization_compliance IS 'Occupational health immunization compliance tracking';

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

SELECT 'Immunizations table created successfully!' as message;
SELECT 'Created 8 performance indexes' as status;
SELECT 'Created 3 helper views' as status;

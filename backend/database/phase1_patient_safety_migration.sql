-- =============================================
-- PHASE 1: PATIENT SAFETY CRITICAL TABLES
-- Migration Script for SurgiScan EHR
-- =============================================

-- =============================================
-- 1. ALLERGIES TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS allergies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    
    -- Allergy details
    substance TEXT NOT NULL,
    reaction TEXT,
    severity TEXT CHECK (severity IN ('mild', 'moderate', 'severe', 'life_threatening', 'unknown')),
    status TEXT CHECK (status IN ('active', 'resolved', 'entered_in_error')) DEFAULT 'active',
    
    -- Metadata
    onset_date DATE,
    notes TEXT,
    source TEXT CHECK (source IN ('document_extraction', 'manual_entry', 'patient_reported', 'imported')),
    source_document_id UUID,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT,
    
    -- Constraints
    CONSTRAINT unique_patient_substance UNIQUE (patient_id, substance, status)
);

-- Indexes for allergies
CREATE INDEX IF NOT EXISTS idx_allergies_patient ON allergies(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_allergies_workspace ON allergies(workspace_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_allergies_severity ON allergies(severity) WHERE status = 'active';

-- =============================================
-- 2. VITALS TABLE (Structured)
-- =============================================
CREATE TABLE IF NOT EXISTS vitals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    encounter_id UUID NOT NULL,
    patient_id UUID NOT NULL,
    
    -- Vital signs
    bp_systolic INTEGER,
    bp_diastolic INTEGER,
    heart_rate INTEGER,
    respiratory_rate INTEGER,
    temperature NUMERIC(4,1),
    spo2 INTEGER CHECK (spo2 BETWEEN 0 AND 100),
    
    -- Anthropometrics
    weight_kg NUMERIC(5,2),
    height_cm NUMERIC(5,2),
    bmi NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN height_cm > 0 THEN weight_kg / POWER(height_cm / 100, 2) END
    ) STORED,
    
    -- Metadata
    measured_datetime TIMESTAMPTZ DEFAULT NOW(),
    measured_by TEXT,
    source TEXT CHECK (source IN ('manual_entry', 'document_extraction', 'device_import')),
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- Indexes for vitals
CREATE INDEX IF NOT EXISTS idx_vitals_patient ON vitals(patient_id, measured_datetime DESC);
CREATE INDEX IF NOT EXISTS idx_vitals_encounter ON vitals(encounter_id);
CREATE INDEX IF NOT EXISTS idx_vitals_workspace ON vitals(workspace_id, tenant_id);

-- =============================================
-- 3. ICD-10 CODES LOOKUP TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS icd10_codes (
    code TEXT PRIMARY KEY,
    chapter_no TEXT,
    chapter_desc TEXT,
    group_code TEXT,
    group_desc TEXT,
    code_3char TEXT,
    code_3char_desc TEXT,
    who_full_desc TEXT NOT NULL,
    
    -- Validation flags
    valid_clinical_use BOOLEAN DEFAULT false,
    valid_primary BOOLEAN DEFAULT false,
    valid_asterisk BOOLEAN DEFAULT false,
    valid_dagger BOOLEAN DEFAULT false,
    
    -- Restrictions
    age_range TEXT,
    gender TEXT,
    status TEXT,
    
    -- Dates
    who_start_date DATE,
    who_end_date DATE,
    sa_start_date DATE,
    sa_end_date DATE,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for ICD-10 codes
CREATE INDEX IF NOT EXISTS idx_icd10_search ON icd10_codes USING gin(to_tsvector('english', who_full_desc));
CREATE INDEX IF NOT EXISTS idx_icd10_chapter ON icd10_codes(chapter_no);
CREATE INDEX IF NOT EXISTS idx_icd10_group ON icd10_codes(group_code);
CREATE INDEX IF NOT EXISTS idx_icd10_valid ON icd10_codes(valid_clinical_use, valid_primary) WHERE valid_clinical_use = true;
CREATE INDEX IF NOT EXISTS idx_icd10_code_3char ON icd10_codes(code_3char);

-- =============================================
-- 4. DIAGNOSES TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS diagnoses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    encounter_id UUID,
    patient_id UUID NOT NULL,
    
    -- Diagnosis coding
    code TEXT,
    coding_system TEXT DEFAULT 'ICD-10' CHECK (coding_system IN ('ICD-10', 'SNOMED', 'local')),
    display TEXT NOT NULL,
    
    -- Clinical details
    diagnosis_type TEXT CHECK (diagnosis_type IN ('primary', 'secondary', 'complication', 'comorbidity')),
    status TEXT CHECK (status IN ('active', 'resolved', 'chronic', 'history')) DEFAULT 'active',
    onset_date DATE,
    resolution_date DATE,
    
    -- Context
    clinical_notes TEXT,
    source TEXT CHECK (source IN ('ai_scribe', 'manual_entry', 'document_extraction', 'imported')),
    source_document_id UUID,
    
    -- Audit
    diagnosed_by TEXT,
    diagnosed_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- Indexes for diagnoses
CREATE INDEX IF NOT EXISTS idx_diagnoses_patient ON diagnoses(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_diagnoses_encounter ON diagnoses(encounter_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_code ON diagnoses(code, coding_system);
CREATE INDEX IF NOT EXISTS idx_diagnoses_workspace ON diagnoses(workspace_id, tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_diagnoses_type ON diagnoses(diagnosis_type, status);

-- =============================================
-- 5. DOCUMENT_REFS TABLE (MongoDB Bridge)
-- =============================================
CREATE TABLE IF NOT EXISTS document_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    
    -- Patient/Encounter linkage
    patient_id UUID,
    encounter_id UUID,
    
    -- MongoDB references
    mongo_scanned_doc_id TEXT,
    mongo_parsed_doc_id TEXT,
    mongo_validation_session_id TEXT,
    
    -- Document metadata
    filename TEXT NOT NULL,
    doc_type TEXT CHECK (doc_type IN (
        'scan', 'parsed', 'lab_report', 'radiology_report', 
        'discharge_summary', 'referral_letter', 'external_letter', 
        'consent_form', 'sick_note', 'other'
    )),
    mime_type TEXT,
    file_size_bytes BIGINT,
    pages_count INTEGER,
    
    -- Storage
    storage_location TEXT CHECK (storage_location IN ('supabase_storage', 'mongodb', 's3', 'local')),
    storage_path TEXT,
    storage_bucket TEXT,
    checksum TEXT,
    
    -- Processing status
    status TEXT CHECK (status IN (
        'uploaded', 'parsing', 'parsed', 'extracting', 'extracted', 
        'validating', 'validated', 'approved', 'archived', 'error'
    )) DEFAULT 'uploaded',
    version INTEGER DEFAULT 1,
    
    -- Validation
    validated_by TEXT,
    validated_at TIMESTAMPTZ,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Audit
    uploaded_by TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for document_refs
CREATE INDEX IF NOT EXISTS idx_document_refs_patient ON document_refs(patient_id);
CREATE INDEX IF NOT EXISTS idx_document_refs_encounter ON document_refs(encounter_id);
CREATE INDEX IF NOT EXISTS idx_document_refs_mongo_scanned ON document_refs(mongo_scanned_doc_id);
CREATE INDEX IF NOT EXISTS idx_document_refs_mongo_parsed ON document_refs(mongo_parsed_doc_id);
CREATE INDEX IF NOT EXISTS idx_document_refs_status ON document_refs(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_document_refs_workspace ON document_refs(workspace_id, tenant_id);

-- =============================================
-- GRANT PERMISSIONS (Adjust based on your setup)
-- =============================================
-- These are examples - adjust for your Supabase RLS policies
-- GRANT ALL ON allergies TO authenticated;
-- GRANT ALL ON vitals TO authenticated;
-- GRANT ALL ON icd10_codes TO authenticated;
-- GRANT ALL ON diagnoses TO authenticated;
-- GRANT ALL ON document_refs TO authenticated;

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

-- =============================================
-- PHASE 1: PATIENT SAFETY CRITICAL TABLES
-- Migration Script v2 - Handles Existing Tables
-- =============================================

-- =============================================
-- OPTION 1: Drop existing document_refs if needed
-- Uncomment the line below if you want to recreate document_refs
-- =============================================
-- DROP TABLE IF EXISTS document_refs CASCADE;

-- =============================================
-- 1. ALLERGIES TABLE
-- =============================================
DROP TABLE IF EXISTS allergies CASCADE;

CREATE TABLE allergies (
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
CREATE INDEX idx_allergies_patient ON allergies(patient_id, status);
CREATE INDEX idx_allergies_workspace ON allergies(workspace_id, tenant_id);
CREATE INDEX idx_allergies_severity ON allergies(severity) WHERE status = 'active';

-- =============================================
-- 2. VITALS TABLE (Structured)
-- =============================================
DROP TABLE IF EXISTS vitals CASCADE;

CREATE TABLE vitals (
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
CREATE INDEX idx_vitals_patient ON vitals(patient_id, measured_datetime DESC);
CREATE INDEX idx_vitals_encounter ON vitals(encounter_id);
CREATE INDEX idx_vitals_workspace ON vitals(workspace_id, tenant_id);

-- =============================================
-- 3. ICD-10 CODES LOOKUP TABLE
-- =============================================
DROP TABLE IF EXISTS icd10_codes CASCADE;

CREATE TABLE icd10_codes (
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
CREATE INDEX idx_icd10_search ON icd10_codes USING gin(to_tsvector('english', who_full_desc));
CREATE INDEX idx_icd10_chapter ON icd10_codes(chapter_no);
CREATE INDEX idx_icd10_group ON icd10_codes(group_code);
CREATE INDEX idx_icd10_valid ON icd10_codes(valid_clinical_use, valid_primary) WHERE valid_clinical_use = true;
CREATE INDEX idx_icd10_code_3char ON icd10_codes(code_3char);

-- =============================================
-- 4. DIAGNOSES TABLE
-- =============================================
DROP TABLE IF EXISTS diagnoses CASCADE;

CREATE TABLE diagnoses (
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
CREATE INDEX idx_diagnoses_patient ON diagnoses(patient_id, status);
CREATE INDEX idx_diagnoses_encounter ON diagnoses(encounter_id);
CREATE INDEX idx_diagnoses_code ON diagnoses(code, coding_system);
CREATE INDEX idx_diagnoses_workspace ON diagnoses(workspace_id, tenant_id, status);
CREATE INDEX idx_diagnoses_type ON diagnoses(diagnosis_type, status);

-- =============================================
-- 5. ALTER EXISTING DIGITISED_DOCUMENTS TABLE
-- (This table exists, we'll keep using it as document_refs equivalent)
-- =============================================

-- Add missing columns to digitised_documents if they don't exist
DO $$ 
BEGIN
    -- Add mongo references if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='digitised_documents' AND column_name='mongo_scanned_doc_id') THEN
        ALTER TABLE digitised_documents ADD COLUMN mongo_scanned_doc_id TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='digitised_documents' AND column_name='mongo_validation_session_id') THEN
        ALTER TABLE digitised_documents ADD COLUMN mongo_validation_session_id TEXT;
    END IF;
    
    -- Add doc_type if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='digitised_documents' AND column_name='doc_type') THEN
        ALTER TABLE digitised_documents ADD COLUMN doc_type TEXT 
            CHECK (doc_type IN ('scan', 'parsed', 'lab_report', 'radiology_report', 
                'discharge_summary', 'referral_letter', 'external_letter', 
                'consent_form', 'sick_note', 'other'));
    END IF;
    
    -- Add mime_type if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='digitised_documents' AND column_name='mime_type') THEN
        ALTER TABLE digitised_documents ADD COLUMN mime_type TEXT;
    END IF;
    
    -- Add retry_count if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='digitised_documents' AND column_name='retry_count') THEN
        ALTER TABLE digitised_documents ADD COLUMN retry_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Create view for backward compatibility (document_refs -> digitised_documents)
CREATE OR REPLACE VIEW document_refs AS
SELECT 
    id,
    workspace_id,
    workspace_id as tenant_id,  -- Map workspace_id to tenant_id for compatibility
    patient_id,
    encounter_id,
    mongo_scanned_doc_id,
    parsed_doc_id as mongo_parsed_doc_id,
    mongo_validation_session_id,
    filename,
    doc_type,
    mime_type,
    file_size as file_size_bytes,
    pages_count,
    'supabase_storage' as storage_location,
    file_path as storage_path,
    s3_bucket as storage_bucket,
    NULL as checksum,
    status,
    1 as version,
    validated_by,
    validated_at,
    uploaded_by as approved_by,
    approved_at,
    error_message,
    retry_count,
    uploaded_by,
    upload_date as uploaded_at,
    created_at,
    updated_at
FROM digitised_documents;

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

-- Summary
SELECT 'Migration completed successfully!' as message;
SELECT 'Created tables: allergies, vitals, icd10_codes, diagnoses' as status;
SELECT 'Updated table: digitised_documents (added columns)' as status;
SELECT 'Created view: document_refs (maps to digitised_documents)' as status;

-- Phase 4.2: Enhanced Prescription Module - Database Schema

-- ==================== PRESCRIPTIONS ====================
CREATE TABLE IF NOT EXISTS prescriptions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    doctor_id TEXT,
    doctor_name TEXT NOT NULL,
    prescription_date DATE NOT NULL,
    status TEXT DEFAULT 'active', -- 'active', 'dispensed', 'cancelled'
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Prescription Items (multiple medications per prescription)
CREATE TABLE IF NOT EXISTS prescription_items (
    id TEXT PRIMARY KEY,
    prescription_id TEXT NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    medication_name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    frequency TEXT NOT NULL,
    duration TEXT NOT NULL,
    quantity TEXT,
    instructions TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== SICK NOTES / MEDICAL CERTIFICATES ====================
CREATE TABLE IF NOT EXISTS sick_notes (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    doctor_id TEXT,
    doctor_name TEXT NOT NULL,
    issue_date DATE NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    diagnosis TEXT NOT NULL,
    fitness_status TEXT NOT NULL, -- 'unfit', 'fit_with_restrictions', 'fit'
    restrictions TEXT,
    additional_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== REFERRAL LETTERS ====================
CREATE TABLE IF NOT EXISTS referrals (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    referring_doctor_id TEXT,
    referring_doctor_name TEXT NOT NULL,
    referral_date DATE NOT NULL,
    specialist_type TEXT NOT NULL, -- 'Cardiologist', 'Orthopedist', etc.
    specialist_name TEXT,
    specialist_practice TEXT,
    reason_for_referral TEXT NOT NULL,
    clinical_findings TEXT NOT NULL,
    investigations_done TEXT,
    current_medications TEXT,
    urgency TEXT DEFAULT 'routine', -- 'urgent', 'routine', 'non-urgent'
    status TEXT DEFAULT 'pending', -- 'pending', 'sent', 'completed', 'cancelled'
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== PRESCRIPTION TEMPLATES ====================
CREATE TABLE IF NOT EXISTS prescription_templates (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    doctor_id TEXT,
    template_name TEXT NOT NULL,
    condition TEXT NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prescription_template_items (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES prescription_templates(id) ON DELETE CASCADE,
    medication_name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    frequency TEXT NOT NULL,
    duration TEXT NOT NULL,
    instructions TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== MEDICATIONS DATABASE ====================
CREATE TABLE IF NOT EXISTS medications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    generic_name TEXT,
    brand_names TEXT[], -- Array of brand names
    category TEXT, -- 'Antibiotic', 'Analgesic', 'Antihypertensive', etc.
    common_dosages TEXT[], -- ['500mg', '1g']
    common_frequencies TEXT[], -- ['Once daily', 'Twice daily', 'Three times daily']
    route TEXT DEFAULT 'Oral', -- 'Oral', 'IV', 'IM', 'Topical'
    contraindications TEXT,
    side_effects TEXT,
    pregnancy_category TEXT,
    interactions TEXT[], -- List of drug IDs that interact
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== DOCUMENT STORAGE REFERENCES ====================
-- Store references to generated PDFs
CREATE TABLE IF NOT EXISTS prescription_documents (
    id TEXT PRIMARY KEY,
    prescription_id TEXT REFERENCES prescriptions(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL, -- 'prescription', 'sick_note', 'referral'
    file_name TEXT NOT NULL,
    file_url TEXT, -- Supabase storage URL or MongoDB reference
    generated_at TIMESTAMP DEFAULT NOW()
);

-- ==================== INDEXES ====================
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_encounter ON prescriptions(encounter_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_date ON prescriptions(prescription_date);

CREATE INDEX IF NOT EXISTS idx_sick_notes_patient ON sick_notes(patient_id);
CREATE INDEX IF NOT EXISTS idx_sick_notes_date ON sick_notes(issue_date);

CREATE INDEX IF NOT EXISTS idx_referrals_patient ON referrals(patient_id);
CREATE INDEX IF NOT EXISTS idx_referrals_specialist ON referrals(specialist_type);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status);

CREATE INDEX IF NOT EXISTS idx_medications_name ON medications(name);
CREATE INDEX IF NOT EXISTS idx_medications_category ON medications(category);

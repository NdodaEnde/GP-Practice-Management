-- Patient Conditions/Diagnoses Table for EHR Integration

CREATE TABLE IF NOT EXISTS patient_conditions (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    condition_name TEXT NOT NULL,
    icd10_code TEXT,
    diagnosed_date DATE,
    status TEXT DEFAULT 'active', -- 'active', 'resolved', 'chronic'
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patient_conditions_patient ON patient_conditions(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_conditions_status ON patient_conditions(status);

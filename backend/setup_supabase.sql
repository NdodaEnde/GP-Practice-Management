-- SurgiScan Database Schema for Supabase

-- Tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workspaces table
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('gp', 'occ_health')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Patients table
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob TEXT NOT NULL,
    id_number TEXT NOT NULL,
    contact_number TEXT,
    email TEXT,
    address TEXT,
    medical_aid TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Encounters table
CREATE TABLE IF NOT EXISTS encounters (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    encounter_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'in_progress',
    chief_complaint TEXT,
    vitals_json JSONB,
    gp_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document references table (links to MongoDB)
CREATE TABLE IF NOT EXISTS document_refs (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT NOT NULL REFERENCES encounters(id),
    mongo_doc_id TEXT NOT NULL,
    mongo_parsed_id TEXT,
    filename TEXT NOT NULL,
    file_size INTEGER,
    status TEXT NOT NULL DEFAULT 'pending_validation',
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- GP Invoices table
CREATE TABLE IF NOT EXISTS gp_invoices (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id),
    payer_type TEXT NOT NULL CHECK (payer_type IN ('cash', 'medical_aid', 'corporate')),
    items_json JSONB NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dispense events table
CREATE TABLE IF NOT EXISTS dispense_events (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id),
    medication TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    dosage TEXT NOT NULL,
    instructions TEXT,
    dispensed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Certificates table (for Occ Health)
CREATE TABLE IF NOT EXISTS certificates (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id),
    certificate_type TEXT NOT NULL,
    content TEXT NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Billing usage tracking
CREATE TABLE IF NOT EXISTS billing_usage (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    usage_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_patients_workspace ON patients(workspace_id);
CREATE INDEX IF NOT EXISTS idx_patients_id_number ON patients(id_number);
CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);
CREATE INDEX IF NOT EXISTS idx_encounters_workspace ON encounters(workspace_id);
CREATE INDEX IF NOT EXISTS idx_encounters_date ON encounters(encounter_date);
CREATE INDEX IF NOT EXISTS idx_document_refs_encounter ON document_refs(encounter_id);
CREATE INDEX IF NOT EXISTS idx_invoices_encounter ON gp_invoices(encounter_id);
CREATE INDEX IF NOT EXISTS idx_dispense_encounter ON dispense_events(encounter_id);

-- Enable Row Level Security (RLS) - For production use
-- ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE encounters ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE document_refs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE gp_invoices ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE dispense_events ENABLE ROW LEVEL SECURITY;

-- Note: For MVP, RLS is disabled. In production, add RLS policies for multi-tenancy.

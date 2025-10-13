# Supabase Table Setup Instructions for SurgiScan

## Step 1: Access Supabase SQL Editor

1. Go to: https://supabase.com/dashboard/project/sizujtbejnnrdqcymgle/sql
2. Or navigate: Supabase Dashboard → Your Project → SQL Editor (left sidebar)

## Step 2: Copy and Execute the SQL Below

```sql
-- SurgiScan Database Schema

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

-- Document references table
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

-- Certificates table
CREATE TABLE IF NOT EXISTS certificates (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id),
    certificate_type TEXT NOT NULL,
    content TEXT NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_patients_workspace ON patients(workspace_id);
CREATE INDEX IF NOT EXISTS idx_patients_id_number ON patients(id_number);
CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);
CREATE INDEX IF NOT EXISTS idx_encounters_workspace ON encounters(workspace_id);
CREATE INDEX IF NOT EXISTS idx_encounters_date ON encounters(encounter_date);
CREATE INDEX IF NOT EXISTS idx_document_refs_encounter ON document_refs(encounter_id);
CREATE INDEX IF NOT EXISTS idx_invoices_encounter ON gp_invoices(encounter_id);
CREATE INDEX IF NOT EXISTS idx_dispense_encounter ON dispense_events(encounter_id);

-- Insert demo tenant and workspace
INSERT INTO tenants (id, name, created_at)
VALUES ('demo-tenant-001', 'Demo GP Practice', NOW())
ON CONFLICT (id) DO NOTHING;

INSERT INTO workspaces (id, tenant_id, name, type, created_at)
VALUES ('demo-gp-workspace-001', 'demo-tenant-001', 'Main GP Practice', 'gp', NOW())
ON CONFLICT (id) DO NOTHING;
```

## Step 3: Verify Tables Created

Run this query to verify:
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```

You should see all the tables listed above.

## Step 4: Restart Backend

After tables are created, restart the backend:
```bash
sudo supervisorctl restart backend
```

The application will now be fully functional!

-- Digitised Documents Table for Phase 1.7
-- Central tracking for all uploaded GP documents

-- Drop the table if it exists (to start fresh)
DROP TABLE IF EXISTS digitised_documents CASCADE;

-- Create the table
CREATE TABLE digitised_documents (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    pages_count INTEGER,
    upload_date TIMESTAMP DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'uploaded',
    patient_id TEXT REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    parsed_doc_id TEXT,
    extracted_data_id TEXT,
    uploaded_by TEXT,
    validated_by TEXT,
    validated_at TIMESTAMP,
    approved_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX idx_digitised_docs_status ON digitised_documents(status);
CREATE INDEX idx_digitised_docs_patient ON digitised_documents(patient_id);
CREATE INDEX idx_digitised_docs_workspace ON digitised_documents(workspace_id);
CREATE INDEX idx_digitised_docs_upload_date ON digitised_documents(upload_date DESC);

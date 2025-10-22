-- Digitised Documents Table for Phase 1.7
-- Central tracking for all uploaded GP documents

CREATE TABLE IF NOT EXISTS digitised_documents (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    pages_count INTEGER,
    upload_date TIMESTAMP DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'uploaded',
    -- Status flow: uploaded → parsing → parsed → extracting → extracted → validated → approved
    patient_id TEXT REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    parsed_doc_id TEXT, -- Reference to MongoDB parsed data
    extracted_data_id TEXT, -- Reference to MongoDB extracted data
    uploaded_by TEXT,
    validated_by TEXT,
    validated_at TIMESTAMP,
    approved_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_digitised_docs_status ON digitised_documents(status);
CREATE INDEX IF NOT EXISTS idx_digitised_docs_patient ON digitised_documents(patient_id);
CREATE INDEX IF NOT EXISTS idx_digitised_docs_workspace ON digitised_documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_digitised_docs_upload_date ON digitised_documents(upload_date DESC);

-- Comments for documentation
COMMENT ON TABLE digitised_documents IS 'Tracks all uploaded GP documents through the digitization workflow';
COMMENT ON COLUMN digitised_documents.status IS 'Workflow status: uploaded, parsing, parsed, extracting, extracted, validated, approved, error';
COMMENT ON COLUMN digitised_documents.parsed_doc_id IS 'MongoDB document ID containing parsed JSON from ADE Parse';
COMMENT ON COLUMN digitised_documents.extracted_data_id IS 'MongoDB document ID containing extracted fields from ADE Extract';

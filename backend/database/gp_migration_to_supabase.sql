-- GP Document Processing Pipeline: MongoDB → Supabase Migration
-- Migrates: gp_parsed_documents, gp_validation_sessions
-- Note: gp_scanned_documents replaced by digitised_documents + Supabase Storage (already done)
-- Note: gp_patients merged into existing patients table (already done)

-- ============================================================
-- 1. GP Parsed Documents - stores LandingAI parsed output
-- ============================================================
CREATE TABLE IF NOT EXISTS gp_parsed_documents (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_id TEXT NOT NULL REFERENCES digitised_documents(id) ON DELETE CASCADE,
    organization_id TEXT,
    workspace_id TEXT REFERENCES workspaces(id),
    filename TEXT NOT NULL,

    -- Parsed content stored as JSONB (chunks, num_pages, total_chunks)
    parsed_data JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Metadata
    parser TEXT DEFAULT 'landingai_dpt2',
    parsed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for gp_parsed_documents
CREATE INDEX IF NOT EXISTS idx_gp_parsed_docs_document_id ON gp_parsed_documents(document_id);
CREATE INDEX IF NOT EXISTS idx_gp_parsed_docs_workspace ON gp_parsed_documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_gp_parsed_docs_created ON gp_parsed_documents(created_at DESC);

-- GIN index for JSONB querying (search within chunks)
CREATE INDEX IF NOT EXISTS idx_gp_parsed_docs_data ON gp_parsed_documents USING GIN (parsed_data);

-- ============================================================
-- 2. GP Validation Sessions - tracks extraction validation
-- ============================================================
CREATE TABLE IF NOT EXISTS gp_validation_sessions (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    session_id TEXT UNIQUE NOT NULL,
    document_id TEXT NOT NULL REFERENCES digitised_documents(id) ON DELETE CASCADE,
    organization_id TEXT,
    workspace_id TEXT REFERENCES workspaces(id),
    patient_id TEXT REFERENCES patients(id),

    -- Validation status
    status TEXT NOT NULL DEFAULT 'pending_validation'
        CHECK (status IN ('pending_validation', 'in_review', 'approved', 'rejected', 'needs_review')),

    -- Extracted data stored as JSONB
    extractions JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_scores JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Validation state per section
    validation_state JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Validated/corrected data (after human review)
    validated_data JSONB DEFAULT NULL,
    validation_statuses JSONB DEFAULT NULL,
    validator_notes TEXT,
    validated_by TEXT,
    validated_at TIMESTAMPTZ,

    -- Processing metadata
    processing_time FLOAT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for gp_validation_sessions
CREATE INDEX IF NOT EXISTS idx_gp_val_sessions_document ON gp_validation_sessions(document_id);
CREATE INDEX IF NOT EXISTS idx_gp_val_sessions_session ON gp_validation_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_gp_val_sessions_status ON gp_validation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_gp_val_sessions_workspace ON gp_validation_sessions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_gp_val_sessions_patient ON gp_validation_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_gp_val_sessions_created ON gp_validation_sessions(created_at DESC);

-- GIN indexes for JSONB querying
CREATE INDEX IF NOT EXISTS idx_gp_val_sessions_extractions ON gp_validation_sessions USING GIN (extractions);

-- ============================================================
-- 3. Add parsed_doc_ref column to digitised_documents if missing
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'digitised_documents' AND column_name = 'gp_parsed_doc_id'
    ) THEN
        ALTER TABLE digitised_documents ADD COLUMN gp_parsed_doc_id TEXT REFERENCES gp_parsed_documents(id);
    END IF;
END $$;

-- ============================================================
-- 4. Row Level Security (RLS)
-- ============================================================
ALTER TABLE gp_parsed_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE gp_validation_sessions ENABLE ROW LEVEL SECURITY;

-- Allow all operations for service role (backend uses service key)
DROP POLICY IF EXISTS "Service role full access to gp_parsed_documents" ON gp_parsed_documents;
CREATE POLICY "Service role full access to gp_parsed_documents"
    ON gp_parsed_documents FOR ALL
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access to gp_validation_sessions" ON gp_validation_sessions;
CREATE POLICY "Service role full access to gp_validation_sessions"
    ON gp_validation_sessions FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================
-- 5. Updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_gp_parsed_documents_updated_at ON gp_parsed_documents;
CREATE TRIGGER update_gp_parsed_documents_updated_at
    BEFORE UPDATE ON gp_parsed_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_gp_validation_sessions_updated_at ON gp_validation_sessions;
CREATE TRIGGER update_gp_validation_sessions_updated_at
    BEFORE UPDATE ON gp_validation_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

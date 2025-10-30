-- Migration to add template-driven extraction columns to digitised_documents table
-- Phase 1.2 Enhanced Extraction Support

-- Add template_id column to track which template was used
ALTER TABLE digitised_documents 
ADD COLUMN IF NOT EXISTS template_id TEXT REFERENCES extraction_templates(id);

-- Add template_used boolean flag
ALTER TABLE digitised_documents 
ADD COLUMN IF NOT EXISTS template_used BOOLEAN DEFAULT FALSE;

-- Add records_created count for auto-population summary
ALTER TABLE digitised_documents 
ADD COLUMN IF NOT EXISTS records_created INTEGER DEFAULT 0;

-- Add tables_populated JSONB for detailed auto-population tracking
ALTER TABLE digitised_documents 
ADD COLUMN IF NOT EXISTS tables_populated JSONB DEFAULT '{}'::jsonb;

-- Create index on template_id for efficient queries
CREATE INDEX IF NOT EXISTS idx_digitised_docs_template ON digitised_documents(template_id);

-- Comments for documentation
COMMENT ON COLUMN digitised_documents.template_id IS 'ID of the extraction template used for processing';
COMMENT ON COLUMN digitised_documents.template_used IS 'Whether template-driven extraction was used';
COMMENT ON COLUMN digitised_documents.records_created IS 'Number of records auto-populated to structured tables';
COMMENT ON COLUMN digitised_documents.tables_populated IS 'JSON object mapping table names to record IDs created';

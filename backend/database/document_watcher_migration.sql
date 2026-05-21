-- Document Watcher Migration
-- Adds source column to digitised_documents for tracking how documents entered the system
-- Run this in Supabase SQL Editor

-- Add source tracking column
ALTER TABLE digitised_documents
ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual_upload';

COMMENT ON COLUMN digitised_documents.source IS 'How the document entered the system: manual_upload, storage_watcher, batch_upload, api';

-- Add index on status for the watcher to efficiently query pending documents
CREATE INDEX IF NOT EXISTS idx_digitised_docs_status_workspace
ON digitised_documents (status, workspace_id)
WHERE status IN ('uploaded', 'parsing', 'extracting');

-- Add index on file_path for deduplication during storage scanning
CREATE INDEX IF NOT EXISTS idx_digitised_docs_file_path
ON digitised_documents (file_path);

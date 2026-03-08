-- =============================================
-- PHASE 1: FLEXIBLE FIELD MAPPING SYSTEM
-- Client-agnostic document extraction and allocation
-- =============================================

DROP TABLE IF EXISTS extraction_field_mappings CASCADE;
DROP TABLE IF EXISTS extraction_templates CASCADE;

-- =============================================
-- EXTRACTION TEMPLATES TABLE
-- Defines document types and their extraction configurations
-- =============================================

CREATE TABLE extraction_templates (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    
    -- Template identification
    template_name TEXT NOT NULL,
    template_description TEXT,
    document_type TEXT,  -- 'medical_record', 'lab_report', 'immunization_card', 'prescription', 'procedure_note'
    
    -- Template configuration
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,  -- Default template for this workspace
    
    -- LandingAI extraction schema
    extraction_schema JSONB,  -- Custom Pydantic schema for this template
    
    -- Processing rules
    auto_populate BOOLEAN DEFAULT true,  -- Automatically populate structured tables
    require_validation BOOLEAN DEFAULT true,  -- Require human validation before committing
    
    -- Usage statistics
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- =============================================
-- EXTRACTION FIELD MAPPINGS TABLE
-- Maps extracted fields to EHR structured tables
-- =============================================

CREATE TABLE extraction_field_mappings (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES extraction_templates(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    
    -- Source field (from extraction)
    source_section TEXT NOT NULL,  -- e.g., 'vaccination_records', 'laboratory_results', 'medication_list'
    source_field TEXT NOT NULL,  -- e.g., 'vaccine_type', 'test_name', 'drug_name'
    source_field_path TEXT,  -- JSON path for nested fields (e.g., 'demographics.contact.cell_number')
    
    -- Target table and field
    target_table TEXT NOT NULL,  -- 'immunizations', 'lab_results', 'procedures', 'prescriptions', 'allergies', 'diagnoses', 'vitals'
    target_field TEXT NOT NULL,  -- Column name in target table
    
    -- Mapping configuration
    field_type TEXT CHECK (field_type IN ('text', 'number', 'date', 'datetime', 'boolean', 'json')) DEFAULT 'text',
    is_required BOOLEAN DEFAULT false,
    default_value TEXT,  -- Default value if field not found
    
    -- Transformation rules
    transformation_type TEXT CHECK (transformation_type IN ('direct', 'lookup', 'calculation', 'concatenation', 'split', 'ai_match')),
    transformation_config JSONB,  -- Configuration for transformation
    -- Examples:
    -- lookup: {"lookup_table": "icd10_codes", "lookup_field": "code", "match_field": "description"}
    -- calculation: {"formula": "weight_kg / (height_m * height_m)"}  -- BMI
    -- concatenation: {"fields": ["first_name", "last_name"], "separator": " "}
    -- split: {"delimiter": "/", "index": 0}  -- For BP: "120/80" -> systolic = 120
    -- ai_match: {"service": "icd10_suggest", "confidence_threshold": 0.7}
    
    -- Data validation
    validation_rules JSONB,  -- {"min": 0, "max": 300, "pattern": "^[0-9]+$", "enum": ["male", "female"]}
    
    -- Processing priority
    processing_order INTEGER DEFAULT 100,  -- Lower number = higher priority
    skip_if_exists BOOLEAN DEFAULT true,  -- Skip if target record already exists
    
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- =============================================
-- EXTRACTION HISTORY TABLE
-- Track all document extractions for audit and learning
-- =============================================

CREATE TABLE extraction_history (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    template_id TEXT REFERENCES extraction_templates(id),
    workspace_id TEXT NOT NULL,
    patient_id TEXT,
    
    -- Extraction details
    extraction_datetime TIMESTAMPTZ DEFAULT NOW(),
    extraction_status TEXT CHECK (extraction_status IN ('success', 'partial', 'failed')) DEFAULT 'success',
    
    -- Data extracted
    raw_extraction JSONB,  -- Raw data from LandingAI
    structured_extraction JSONB,  -- Mapped to fields
    
    -- Population results
    tables_populated JSONB,  -- {"immunizations": [id1, id2], "lab_results": [id1], ...}
    population_errors JSONB,  -- Errors during auto-population
    
    -- Confidence and quality
    confidence_scores JSONB,  -- Per-section confidence scores
    validation_required_sections TEXT[],  -- Sections that need human validation
    
    -- Processing metrics
    processing_time_ms INTEGER,
    fields_extracted INTEGER,
    fields_mapped INTEGER,
    records_created INTEGER,
    
    -- Validation tracking
    validated BOOLEAN DEFAULT false,
    validated_by TEXT,
    validated_at TIMESTAMPTZ,
    validation_changes JSONB,  -- Changes made during validation
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Extraction Templates
CREATE INDEX idx_extraction_templates_workspace ON extraction_templates(workspace_id, tenant_id);
CREATE INDEX idx_extraction_templates_type ON extraction_templates(document_type, is_active);
CREATE INDEX idx_extraction_templates_default ON extraction_templates(workspace_id) WHERE is_default = true;

-- Field Mappings
CREATE INDEX idx_extraction_mappings_template ON extraction_field_mappings(template_id, processing_order);
CREATE INDEX idx_extraction_mappings_workspace ON extraction_field_mappings(workspace_id);
CREATE INDEX idx_extraction_mappings_target ON extraction_field_mappings(target_table, target_field);
CREATE INDEX idx_extraction_mappings_active ON extraction_field_mappings(is_active) WHERE is_active = true;

-- Extraction History
CREATE INDEX idx_extraction_history_document ON extraction_history(document_id);
CREATE INDEX idx_extraction_history_workspace ON extraction_history(workspace_id, extraction_datetime DESC);
CREATE INDEX idx_extraction_history_patient ON extraction_history(patient_id) WHERE patient_id IS NOT NULL;
CREATE INDEX idx_extraction_history_validation ON extraction_history(validated, workspace_id) WHERE validated = false;
CREATE INDEX idx_extraction_history_template ON extraction_history(template_id);

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE extraction_templates IS 'Document extraction templates for different document types and client formats';
COMMENT ON TABLE extraction_field_mappings IS 'Field-level mappings from extracted data to structured EHR tables';
COMMENT ON TABLE extraction_history IS 'Audit trail of all document extractions and auto-population results';

COMMENT ON COLUMN extraction_templates.extraction_schema IS 'Custom Pydantic schema definition for LandingAI extraction';
COMMENT ON COLUMN extraction_templates.auto_populate IS 'Automatically populate structured tables after extraction';

COMMENT ON COLUMN extraction_field_mappings.source_section IS 'Section name in extracted document (e.g., vaccination_records)';
COMMENT ON COLUMN extraction_field_mappings.target_table IS 'Destination table in EHR schema';
COMMENT ON COLUMN extraction_field_mappings.transformation_type IS 'How to transform source data to target format';
COMMENT ON COLUMN extraction_field_mappings.processing_order IS 'Order in which to process mappings (lower = first)';

COMMENT ON COLUMN extraction_history.tables_populated IS 'Record IDs created in each table during auto-population';
COMMENT ON COLUMN extraction_history.confidence_scores IS 'AI confidence scores for each extracted section';

-- =============================================
-- HELPER VIEWS
-- =============================================

-- Active mappings by workspace
CREATE OR REPLACE VIEW active_workspace_mappings AS
SELECT 
    et.workspace_id,
    et.template_name,
    et.document_type,
    efm.source_section,
    efm.source_field,
    efm.target_table,
    efm.target_field,
    efm.transformation_type,
    efm.processing_order
FROM extraction_templates et
JOIN extraction_field_mappings efm ON et.id = efm.template_id
WHERE et.is_active = true 
  AND efm.is_active = true
ORDER BY et.workspace_id, et.template_name, efm.processing_order;

COMMENT ON VIEW active_workspace_mappings IS 'All active field mappings organized by workspace and template';

-- Extraction success rate by template
CREATE OR REPLACE VIEW template_extraction_stats AS
SELECT 
    et.workspace_id,
    et.template_name,
    et.document_type,
    COUNT(eh.id) as total_extractions,
    COUNT(CASE WHEN eh.extraction_status = 'success' THEN 1 END) as successful,
    COUNT(CASE WHEN eh.extraction_status = 'partial' THEN 1 END) as partial,
    COUNT(CASE WHEN eh.extraction_status = 'failed' THEN 1 END) as failed,
    AVG(eh.processing_time_ms) as avg_processing_time_ms,
    AVG(eh.fields_extracted) as avg_fields_extracted,
    AVG(eh.records_created) as avg_records_created
FROM extraction_templates et
LEFT JOIN extraction_history eh ON et.id = eh.template_id
GROUP BY et.workspace_id, et.template_name, et.document_type;

COMMENT ON VIEW template_extraction_stats IS 'Performance statistics for each extraction template';

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

SELECT 'Extraction templates table created successfully!' as message;
SELECT 'Extraction field mappings table created successfully!' as message;
SELECT 'Extraction history table created successfully!' as message;
SELECT 'Created 12 performance indexes' as status;
SELECT 'Created 2 helper views' as status;

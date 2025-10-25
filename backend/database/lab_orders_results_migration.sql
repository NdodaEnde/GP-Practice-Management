-- =============================================
-- SPRINT 2.2: LAB ORDERS & RESULTS
-- Track laboratory tests, orders, and results
-- =============================================

DROP TABLE IF EXISTS lab_results CASCADE;
DROP TABLE IF EXISTS lab_orders CASCADE;

-- =============================================
-- LAB ORDERS TABLE
-- =============================================

CREATE TABLE lab_orders (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    encounter_id TEXT,
    patient_id TEXT NOT NULL,
    
    -- Order identification
    order_number TEXT,
    order_datetime TIMESTAMPTZ DEFAULT NOW(),
    ordering_provider TEXT,
    priority TEXT CHECK (priority IN ('routine', 'urgent', 'stat')) DEFAULT 'routine',
    
    -- Lab information (South African labs)
    lab_name TEXT,  -- PathCare, Lancet, Ampath, Vermaak, etc.
    lab_reference_number TEXT,  -- Lab's internal reference
    collection_date DATE,
    
    -- Status tracking
    status TEXT CHECK (status IN ('ordered', 'collected', 'received', 'in_progress', 'completed', 'cancelled')) DEFAULT 'ordered',
    
    -- Clinical context
    indication TEXT,  -- Reason for test
    clinical_notes TEXT,
    icd10_code TEXT,  -- Diagnosis code for medical aid
    
    -- Results notification
    results_received_datetime TIMESTAMPTZ,
    results_reviewed_by TEXT,
    results_reviewed_datetime TIMESTAMPTZ,
    
    -- Source document
    source_document_id TEXT,  -- Link to uploaded lab report PDF
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- =============================================
-- LAB RESULTS TABLE
-- =============================================

CREATE TABLE lab_results (
    id TEXT PRIMARY KEY,
    lab_order_id TEXT NOT NULL REFERENCES lab_orders(id) ON DELETE CASCADE,
    
    -- Test identification
    test_code TEXT,  -- LOINC code (future) or local code
    test_system TEXT DEFAULT 'local',  -- 'loinc', 'local', 'snomed'
    test_name TEXT NOT NULL,  -- e.g., "HbA1c", "Creatinine", "Total Cholesterol"
    test_category TEXT,  -- e.g., "Hematology", "Chemistry", "Immunology"
    
    -- Result value
    result_value TEXT NOT NULL,  -- Can be numeric or text (e.g., "Positive", "7.5")
    result_numeric NUMERIC,  -- For trending (extracted from result_value)
    units TEXT,  -- mg/dL, mmol/L, g/L, etc.
    
    -- Reference range
    reference_range TEXT,  -- e.g., "3.5-5.5", "<100", "Negative"
    reference_low NUMERIC,  -- For automated flagging
    reference_high NUMERIC,
    
    -- Interpretation
    abnormal_flag TEXT CHECK (abnormal_flag IN ('normal', 'low', 'high', 'critical_low', 'critical_high', 'abnormal', 'unknown')) DEFAULT 'unknown',
    interpretation TEXT,  -- Free text interpretation
    comments TEXT,  -- Lab comments or notes
    
    -- Metadata
    result_datetime TIMESTAMPTZ,
    specimen_type TEXT,  -- Blood, Urine, Serum, Plasma, etc.
    specimen_collection_datetime TIMESTAMPTZ,
    performing_lab TEXT,
    result_status TEXT CHECK (result_status IN ('preliminary', 'final', 'corrected', 'cancelled')) DEFAULT 'final',
    
    -- Source tracking
    source TEXT CHECK (source IN ('manual_entry', 'pdf_extraction', 'hl7_import', 'api_import')) DEFAULT 'manual_entry',
    source_document_id TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Lab Orders
CREATE INDEX idx_lab_orders_patient ON lab_orders(patient_id, order_datetime DESC);
CREATE INDEX idx_lab_orders_encounter ON lab_orders(encounter_id);
CREATE INDEX idx_lab_orders_workspace ON lab_orders(workspace_id, tenant_id);
CREATE INDEX idx_lab_orders_status ON lab_orders(status, workspace_id);
CREATE INDEX idx_lab_orders_lab ON lab_orders(lab_name, status);
CREATE INDEX idx_lab_orders_ordering_provider ON lab_orders(ordering_provider, order_datetime DESC);

-- Lab Results
CREATE INDEX idx_lab_results_order ON lab_results(lab_order_id);
CREATE INDEX idx_lab_results_test_name ON lab_results(test_name);
CREATE INDEX idx_lab_results_abnormal ON lab_results(abnormal_flag) WHERE abnormal_flag IN ('critical_low', 'critical_high', 'abnormal');
CREATE INDEX idx_lab_results_datetime ON lab_results(result_datetime DESC);

-- Composite index for trending queries
CREATE INDEX idx_lab_results_trending ON lab_results(lab_order_id, test_name, result_datetime DESC) WHERE result_numeric IS NOT NULL;

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE lab_orders IS 'Laboratory test orders - tracking from order to completion';
COMMENT ON TABLE lab_results IS 'Individual test results within lab orders';

COMMENT ON COLUMN lab_orders.priority IS 'Test urgency: routine (standard), urgent (expedited), stat (immediate)';
COMMENT ON COLUMN lab_orders.lab_name IS 'South African labs: PathCare, Lancet, Ampath, Vermaak, etc.';
COMMENT ON COLUMN lab_orders.status IS 'Order lifecycle: ordered → collected → received → in_progress → completed';

COMMENT ON COLUMN lab_results.test_name IS 'Human-readable test name (e.g., HbA1c, Full Blood Count)';
COMMENT ON COLUMN lab_results.result_numeric IS 'Numeric value for trending and comparisons';
COMMENT ON COLUMN lab_results.abnormal_flag IS 'Automated flagging: normal, low, high, critical_low, critical_high';
COMMENT ON COLUMN lab_results.reference_range IS 'Lab-provided normal range as text';

-- =============================================
-- HELPER VIEW: PATIENT LAB SUMMARY
-- =============================================

CREATE OR REPLACE VIEW patient_lab_summary AS
SELECT 
    lo.patient_id,
    lo.id as order_id,
    lo.order_number,
    lo.order_datetime,
    lo.lab_name,
    lo.status as order_status,
    lr.test_name,
    lr.result_value,
    lr.units,
    lr.abnormal_flag,
    lr.result_datetime,
    lo.ordering_provider
FROM lab_orders lo
LEFT JOIN lab_results lr ON lo.id = lr.lab_order_id
WHERE lo.status != 'cancelled'
ORDER BY lo.order_datetime DESC, lr.test_name;

COMMENT ON VIEW patient_lab_summary IS 'Quick view of patient lab orders and results';

-- =============================================
-- MIGRATION COMPLETE
-- =============================================

SELECT 'Lab orders table created successfully!' as message;
SELECT 'Lab results table created successfully!' as message;
SELECT 'Created 10 performance indexes' as status;
SELECT 'Created patient_lab_summary view' as status;

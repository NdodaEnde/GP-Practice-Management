-- =============================================
-- PHASE 3: BILLING SYSTEM MIGRATION
-- South African Healthcare Billing with Medical Aid Support
-- =============================================

-- =============================================
-- INVOICES TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    invoice_number TEXT NOT NULL UNIQUE,
    invoice_date DATE NOT NULL,
    due_date DATE,
    
    -- Financial Details
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0,
    vat_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    amount_paid DECIMAL(10,2) NOT NULL DEFAULT 0,
    amount_outstanding DECIMAL(10,2) NOT NULL DEFAULT 0,
    
    -- Payment Details
    payment_status TEXT NOT NULL DEFAULT 'unpaid', -- unpaid, partially_paid, paid, overdue
    payment_method TEXT, -- cash, card, eft, medical_aid, split
    
    -- Medical Aid Details
    medical_aid_name TEXT,
    medical_aid_number TEXT,
    medical_aid_plan TEXT,
    medical_aid_portion DECIMAL(10,2) DEFAULT 0,
    patient_portion DECIMAL(10,2) DEFAULT 0,
    
    -- Status and Notes
    status TEXT NOT NULL DEFAULT 'draft', -- draft, issued, cancelled
    notes TEXT,
    
    -- Audit Fields
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    issued_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    
    CONSTRAINT fk_invoice_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_invoice_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT check_payment_status CHECK (payment_status IN ('unpaid', 'partially_paid', 'paid', 'overdue')),
    CONSTRAINT check_status CHECK (status IN ('draft', 'issued', 'cancelled'))
);

-- =============================================
-- INVOICE ITEMS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS invoice_items (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    
    -- Item Details
    item_type TEXT NOT NULL, -- consultation, medication, procedure, lab_test, immunization
    description TEXT NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    
    -- Medical Coding for Claims
    icd10_code TEXT, -- Diagnosis code for consultation
    nappi_code TEXT, -- Medication code
    procedure_code TEXT, -- Procedure/tariff code
    
    -- Reference IDs
    prescription_item_id TEXT,
    procedure_id TEXT,
    lab_order_id TEXT,
    immunization_id TEXT,
    
    -- VAT
    vat_rate DECIMAL(5,2) DEFAULT 0,
    vat_amount DECIMAL(10,2) DEFAULT 0,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_invoice_item_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    CONSTRAINT check_item_type CHECK (item_type IN ('consultation', 'medication', 'procedure', 'lab_test', 'immunization', 'other'))
);

-- =============================================
-- PAYMENTS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    
    -- Payment Details
    payment_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_method TEXT NOT NULL, -- cash, card, eft, medical_aid
    
    -- Additional Details
    reference_number TEXT, -- Transaction/reference number
    notes TEXT,
    
    -- Medical Aid Payment
    is_medical_aid_payment BOOLEAN DEFAULT FALSE,
    medical_aid_claim_id TEXT,
    
    -- Audit Fields
    recorded_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_payment_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_payment_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT check_payment_method CHECK (payment_method IN ('cash', 'card', 'eft', 'medical_aid'))
);

-- =============================================
-- MEDICAL AID CLAIMS TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS medical_aid_claims (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    
    -- Claim Details
    claim_number TEXT NOT NULL UNIQUE,
    claim_date DATE NOT NULL,
    medical_aid_name TEXT NOT NULL,
    medical_aid_number TEXT NOT NULL,
    medical_aid_plan TEXT,
    
    -- Financial
    claim_amount DECIMAL(10,2) NOT NULL,
    approved_amount DECIMAL(10,2),
    paid_amount DECIMAL(10,2),
    
    -- Status Tracking
    status TEXT NOT NULL DEFAULT 'draft', -- draft, submitted, approved, partially_approved, rejected, paid
    submission_date DATE,
    response_date DATE,
    payment_date DATE,
    
    -- ICD-10 Diagnosis Codes
    primary_diagnosis_code TEXT,
    primary_diagnosis_description TEXT,
    secondary_diagnosis_codes TEXT[], -- Array of additional codes
    
    -- Rejection Details
    rejection_reason TEXT,
    rejection_code TEXT,
    
    -- Notes and Documents
    notes TEXT,
    claim_file_path TEXT, -- Path to exported claim file
    
    -- Audit Fields
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    
    CONSTRAINT fk_claim_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_claim_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT check_claim_status CHECK (status IN ('draft', 'submitted', 'approved', 'partially_approved', 'rejected', 'paid'))
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Invoices Indexes
CREATE INDEX IF NOT EXISTS idx_invoices_patient ON invoices(patient_id);
CREATE INDEX IF NOT EXISTS idx_invoices_encounter ON invoices(encounter_id);
CREATE INDEX IF NOT EXISTS idx_invoices_invoice_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_payment_status ON invoices(payment_status);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_workspace ON invoices(workspace_id);

-- Invoice Items Indexes
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_type ON invoice_items(item_type);
CREATE INDEX IF NOT EXISTS idx_invoice_items_nappi ON invoice_items(nappi_code) WHERE nappi_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_invoice_items_icd10 ON invoice_items(icd10_code) WHERE icd10_code IS NOT NULL;

-- Payments Indexes
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_patient ON payments(patient_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_method ON payments(payment_method);
CREATE INDEX IF NOT EXISTS idx_payments_workspace ON payments(workspace_id);

-- Claims Indexes
CREATE INDEX IF NOT EXISTS idx_claims_invoice ON medical_aid_claims(invoice_id);
CREATE INDEX IF NOT EXISTS idx_claims_patient ON medical_aid_claims(patient_id);
CREATE INDEX IF NOT EXISTS idx_claims_number ON medical_aid_claims(claim_number);
CREATE INDEX IF NOT EXISTS idx_claims_status ON medical_aid_claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_medical_aid ON medical_aid_claims(medical_aid_name);
CREATE INDEX IF NOT EXISTS idx_claims_date ON medical_aid_claims(claim_date);
CREATE INDEX IF NOT EXISTS idx_claims_workspace ON medical_aid_claims(workspace_id);

-- =============================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================

COMMENT ON TABLE invoices IS 'Patient invoices with medical aid support';
COMMENT ON TABLE invoice_items IS 'Line items for invoices with medical coding';
COMMENT ON TABLE payments IS 'Payment records for invoices';
COMMENT ON TABLE medical_aid_claims IS 'Medical aid claim submissions and tracking';

COMMENT ON COLUMN invoices.invoice_number IS 'Unique invoice reference number';
COMMENT ON COLUMN invoices.medical_aid_portion IS 'Amount covered by medical aid';
COMMENT ON COLUMN invoices.patient_portion IS 'Amount patient must pay (co-pay)';

COMMENT ON COLUMN invoice_items.nappi_code IS 'South African medication code for medical aid claims';
COMMENT ON COLUMN invoice_items.icd10_code IS 'ICD-10 diagnosis code for consultation billing';
COMMENT ON COLUMN invoice_items.procedure_code IS 'Procedure/tariff code for medical aid claims';

COMMENT ON COLUMN medical_aid_claims.claim_number IS 'Unique medical aid claim reference';
COMMENT ON COLUMN medical_aid_claims.primary_diagnosis_code IS 'Main ICD-10 diagnosis code for claim';

-- =============================================
-- SUCCESS MESSAGE
-- =============================================

SELECT 'Phase 3 Billing tables created successfully!' as message,
       'Tables: invoices, invoice_items, payments, medical_aid_claims' as tables_created;

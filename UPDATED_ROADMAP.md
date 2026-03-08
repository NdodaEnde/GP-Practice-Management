# 🚀 SurgiScan EHR Roadmap - Updated for Production

## 📊 ICD-10 Database Details

**Dataset:** South African ICD-10 MIT 2021 (41,008 codes)
**Structure:**
- Hierarchical: Chapter → Group → 3-Character Code → Full Code
- Clinically usable codes: `Valid_ICD10_ClinicalUse = 'Y'`
- Primary diagnosis codes: `Valid_ICD10_Primary = 'Y'`
- Includes gender restrictions, age ranges, validity dates

**Key Columns:**
- `ICD10_Code` - Full code (e.g., A00.0, S29.8)
- `WHO_Full_Desc` - Full description
- `Chapter_Desc` - Major category (e.g., "Certain infectious and parasitic diseases")
- `Group_Desc` - Subcategory

---

## 🎯 PHASE 1: PATIENT SAFETY CRITICAL (WEEKS 1-2)
**Status:** 🟡 IN PROGRESS
**Priority:** ⚠️ HIGHEST - Medico-legal & patient safety requirements

### Sprint 1.1: Allergies System (Days 1-3)
**Objective:** Prevent prescribing allergens - patient safety critical

#### Database Schema
```sql
CREATE TABLE allergies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    
    -- Allergy details
    substance TEXT NOT NULL,
    reaction TEXT,
    severity TEXT CHECK (severity IN ('mild', 'moderate', 'severe', 'life_threatening', 'unknown')),
    status TEXT CHECK (status IN ('active', 'resolved', 'entered_in_error')) DEFAULT 'active',
    
    -- Metadata
    onset_date DATE,
    notes TEXT,
    source TEXT CHECK (source IN ('document_extraction', 'manual_entry', 'patient_reported', 'imported')),
    source_document_id UUID REFERENCES document_refs(id),
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT,
    
    -- Indexes
    CONSTRAINT unique_patient_substance UNIQUE (patient_id, substance, status)
);

CREATE INDEX idx_allergies_patient ON allergies(patient_id, status);
CREATE INDEX idx_allergies_workspace ON allergies(workspace_id, tenant_id);
```

#### Implementation Tasks
- [x] **Backend:**
  - [ ] Create allergies table in Supabase
  - [ ] Add allergy endpoints (CRUD)
  - [ ] Document extraction: Parse "Known allergies:", "Allergic to:" sections
  - [ ] Prescription safety check: Block allergen prescriptions with warning
  
- [x] **Frontend:**
  - [ ] Allergy management UI in Patient Registry
  - [ ] **RED ALERT banner** in Patient EHR when allergies exist
  - [ ] Allergy section in GPValidationInterface (for document extraction)
  - [ ] Prescription workflow: Show warning if drug matches allergy
  - [ ] PatientMatchDialog: Display allergies prominently

**Success Metrics:**
- ✅ Allergies extracted from 90%+ documents mentioning them
- ✅ Prescription safety check catches 100% of exact matches
- ✅ Prominent display in all patient views

---

### Sprint 1.2: Structured Vitals Table (Days 4-5)
**Objective:** Queryable vitals for trends, charts, alerts

#### Database Schema
```sql
CREATE TABLE vitals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    encounter_id UUID NOT NULL REFERENCES encounters(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    
    -- Vital signs
    bp_systolic INTEGER,
    bp_diastolic INTEGER,
    heart_rate INTEGER,
    respiratory_rate INTEGER,
    temperature NUMERIC(4,1),
    spo2 INTEGER CHECK (spo2 BETWEEN 0 AND 100),
    
    -- Anthropometrics
    weight_kg NUMERIC(5,2),
    height_cm NUMERIC(5,2),
    bmi NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN height_cm > 0 THEN weight_kg / POWER(height_cm / 100, 2) END
    ) STORED,
    
    -- Metadata
    measured_datetime TIMESTAMPTZ DEFAULT NOW(),
    measured_by TEXT,
    source TEXT CHECK (source IN ('manual_entry', 'document_extraction', 'device_import')),
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT,
    
    -- Indexes
    CONSTRAINT vitals_encounter_unique UNIQUE (encounter_id, measured_datetime)
);

CREATE INDEX idx_vitals_patient ON vitals(patient_id, measured_datetime DESC);
CREATE INDEX idx_vitals_encounter ON vitals(encounter_id);
```

#### Implementation Tasks
- [x] **Backend:**
  - [ ] Create vitals table
  - [ ] Migration script: Parse encounters.vitals_json → vitals rows
  - [ ] Update encounter creation: Save to vitals table
  - [ ] Document extraction: Parse vital_entries → vitals
  - [ ] Vitals API endpoints
  
- [x] **Frontend:**
  - [ ] Update Vitals Station to save to new table
  - [ ] Patient EHR: Query vitals table for trends
  - [ ] Vitals chart: Use real data from vitals table
  - [ ] Keep encounters.vitals_json for backward compatibility (view)

**Success Metrics:**
- ✅ Historical vitals migrated
- ✅ Charts show real data
- ✅ BMI calculated automatically

---

### Sprint 1.3: Diagnoses Table with ICD-10 (Days 6-8)
**Objective:** Structured diagnoses for billing, analytics, care tracking

#### Database Schema
```sql
CREATE TABLE diagnoses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    encounter_id UUID REFERENCES encounters(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    
    -- Diagnosis coding
    code TEXT,  -- ICD-10 code (e.g., A00.0, J45.9)
    coding_system TEXT DEFAULT 'ICD-10' CHECK (coding_system IN ('ICD-10', 'SNOMED', 'local')),
    display TEXT NOT NULL,  -- Human-readable diagnosis
    
    -- Clinical details
    diagnosis_type TEXT CHECK (diagnosis_type IN ('primary', 'secondary', 'complication', 'comorbidity')),
    status TEXT CHECK (status IN ('active', 'resolved', 'chronic', 'history')) DEFAULT 'active',
    onset_date DATE,
    resolution_date DATE,
    
    -- Context
    clinical_notes TEXT,
    source TEXT CHECK (source IN ('ai_scribe', 'manual_entry', 'document_extraction', 'imported')),
    source_document_id UUID REFERENCES document_refs(id),
    
    -- Audit
    diagnosed_by TEXT,
    diagnosed_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

CREATE INDEX idx_diagnoses_patient ON diagnoses(patient_id, status);
CREATE INDEX idx_diagnoses_encounter ON diagnoses(encounter_id);
CREATE INDEX idx_diagnoses_code ON diagnoses(code, coding_system);
CREATE INDEX idx_diagnoses_workspace ON diagnoses(workspace_id, tenant_id, status);

-- ICD-10 lookup table
CREATE TABLE icd10_codes (
    code TEXT PRIMARY KEY,
    chapter_no TEXT,
    chapter_desc TEXT,
    group_code TEXT,
    group_desc TEXT,
    code_3char TEXT,
    code_3char_desc TEXT,
    who_full_desc TEXT NOT NULL,
    valid_clinical_use BOOLEAN DEFAULT false,
    valid_primary BOOLEAN DEFAULT false,
    age_range TEXT,
    gender TEXT,
    status TEXT,
    sa_start_date DATE,
    sa_end_date DATE
);

CREATE INDEX idx_icd10_search ON icd10_codes USING gin(to_tsvector('english', who_full_desc));
CREATE INDEX idx_icd10_chapter ON icd10_codes(chapter_no);
CREATE INDEX idx_icd10_group ON icd10_codes(group_code);
CREATE INDEX idx_icd10_valid ON icd10_codes(valid_clinical_use, valid_primary);
```

#### Implementation Tasks
- [x] **Backend:**
  - [ ] Create diagnoses table
  - [ ] Create icd10_codes table
  - [ ] Load ICD-10 dataset (41,008 codes)
  - [ ] ICD-10 search API (autocomplete, full-text search)
  - [ ] AI-assisted ICD-10 suggestion (GPT-4 from Assessment text)
  - [ ] Diagnoses CRUD endpoints
  - [ ] Migration: patient_conditions → diagnoses (keep both for now)
  
- [x] **Frontend:**
  - [ ] Diagnosis input UI with ICD-10 autocomplete
  - [ ] AI suggestion: "Suggest ICD-10 code" button
  - [ ] Display diagnoses in Patient EHR (separate from conditions)
  - [ ] GPValidationInterface: Extract diagnoses section
  - [ ] Problem list view (active diagnoses)

**Success Metrics:**
- ✅ ICD-10 codes searchable in <200ms
- ✅ AI suggests correct code 80%+ of time
- ✅ All new encounters have coded diagnoses

---

### Sprint 1.4: Document References Bridge (Days 9-10)
**Objective:** Formalize MongoDB ↔ Postgres linkage

#### Database Schema
```sql
CREATE TABLE document_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    
    -- Patient/Encounter linkage (nullable for multi-patient docs)
    patient_id UUID REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    
    -- MongoDB references
    mongo_scanned_doc_id TEXT,
    mongo_parsed_doc_id TEXT,
    mongo_validation_session_id TEXT,
    
    -- Document metadata
    filename TEXT NOT NULL,
    doc_type TEXT CHECK (doc_type IN (
        'scan', 'parsed', 'lab_report', 'radiology_report', 
        'discharge_summary', 'referral_letter', 'external_letter', 
        'consent_form', 'sick_note', 'other'
    )),
    mime_type TEXT,
    file_size_bytes BIGINT,
    pages_count INTEGER,
    
    -- Storage
    storage_location TEXT CHECK (storage_location IN ('supabase_storage', 'mongodb', 's3', 'local')),
    storage_path TEXT,
    storage_bucket TEXT,
    checksum TEXT,
    
    -- Processing status
    status TEXT CHECK (status IN (
        'uploaded', 'parsing', 'parsed', 'extracting', 'extracted', 
        'validating', 'validated', 'approved', 'archived', 'error'
    )) DEFAULT 'uploaded',
    version INTEGER DEFAULT 1,
    
    -- Validation
    validated_by TEXT,
    validated_at TIMESTAMPTZ,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Audit
    uploaded_by TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_document_refs_patient ON document_refs(patient_id);
CREATE INDEX idx_document_refs_encounter ON document_refs(encounter_id);
CREATE INDEX idx_document_refs_mongo_scanned ON document_refs(mongo_scanned_doc_id);
CREATE INDEX idx_document_refs_mongo_parsed ON document_refs(mongo_parsed_doc_id);
CREATE INDEX idx_document_refs_status ON document_refs(workspace_id, status);
```

#### Implementation Tasks
- [x] **Backend:**
  - [ ] Create document_refs table
  - [ ] Update upload flow: Create document_ref entry
  - [ ] Link to digitised_documents table (may consolidate later)
  - [ ] Update validation flow: Update document_ref on approval
  
- [x] **Frontend:**
  - [ ] No UI changes (internal bridge)

**Success Metrics:**
- ✅ All documents have document_refs entry
- ✅ Encounter → documents linkage clear

---

## 🏥 PHASE 2: CLINICAL WORKFLOW ENHANCEMENT (WEEKS 3-6)
**Status:** 🔵 PLANNED
**Priority:** 🔥 HIGH - Core EHR functionality

### Sprint 2.1: Structured Clinical Notes (Week 3)
**Objective:** SOAP notes as structured data, not free text

#### Database Schema
```sql
CREATE TABLE clinical_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    encounter_id UUID NOT NULL REFERENCES encounters(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    
    -- Note type
    format TEXT CHECK (format IN ('soap', 'free_text', 'discharge_summary', 'referral_letter', 'procedure_note', 'progress_note')) DEFAULT 'soap',
    
    -- SOAP structure
    subjective TEXT,
    objective TEXT,
    assessment TEXT,
    plan TEXT,
    
    -- Free text fallback
    raw_text TEXT,
    
    -- Metadata
    note_datetime TIMESTAMPTZ DEFAULT NOW(),
    author TEXT,
    role TEXT CHECK (role IN ('doctor', 'nurse', 'pharmacist', 'therapist', 'other')),
    
    -- Source
    source TEXT CHECK (source IN ('ai_scribe', 'manual_entry', 'document_extraction', 'imported')),
    source_document_id UUID REFERENCES document_refs(id),
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    signed BOOLEAN DEFAULT false,
    signed_at TIMESTAMPTZ,
    signed_by TEXT
);

CREATE INDEX idx_clinical_notes_encounter ON clinical_notes(encounter_id);
CREATE INDEX idx_clinical_notes_patient ON clinical_notes(patient_id, note_datetime DESC);
```

#### Implementation Tasks
- [x] **Backend:**
  - [ ] Create clinical_notes table
  - [ ] AI Scribe: Save to clinical_notes (structured SOAP)
  - [ ] Document extraction: Parse SOAP → clinical_notes
  - [ ] Keep encounters.gp_notes for backward compatibility
  
- [x] **Frontend:**
  - [ ] Display structured SOAP in EHR
  - [ ] Edit/append to existing notes
  - [ ] Multiple notes per encounter support

---

### Sprint 2.2: Lab Orders & Results (Week 4)
**Objective:** Lab result tracking, trending, alerts

#### Database Schema
```sql
CREATE TABLE lab_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    encounter_id UUID REFERENCES encounters(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    
    -- Order details
    order_number TEXT UNIQUE,
    order_datetime TIMESTAMPTZ DEFAULT NOW(),
    ordering_provider TEXT,
    priority TEXT CHECK (priority IN ('routine', 'urgent', 'stat')) DEFAULT 'routine',
    
    -- Lab info
    lab_name TEXT,  -- PathCare, Lancet, Ampath, etc.
    status TEXT CHECK (status IN ('ordered', 'collected', 'received', 'completed', 'cancelled')) DEFAULT 'ordered',
    
    -- Clinical context
    indication TEXT,
    clinical_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE lab_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_order_id UUID NOT NULL REFERENCES lab_orders(id),
    
    -- Test identification
    test_code TEXT,  -- LOINC code (future)
    test_system TEXT DEFAULT 'local',
    test_name TEXT NOT NULL,
    
    -- Results
    result_value TEXT NOT NULL,
    result_numeric NUMERIC,  -- For trending
    units TEXT,
    reference_range TEXT,
    
    -- Interpretation
    abnormal_flag TEXT CHECK (abnormal_flag IN ('low', 'high', 'critical', 'normal', 'unknown')),
    interpretation TEXT,
    
    -- Metadata
    result_datetime TIMESTAMPTZ,
    performing_lab TEXT,
    result_status TEXT CHECK (result_status IN ('preliminary', 'final', 'corrected', 'cancelled')) DEFAULT 'final',
    
    -- Source
    source_document_id UUID REFERENCES document_refs(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_lab_orders_patient ON lab_orders(patient_id, order_datetime DESC);
CREATE INDEX idx_lab_orders_encounter ON lab_orders(encounter_id);
CREATE INDEX idx_lab_results_order ON lab_results(lab_order_id);
CREATE INDEX idx_lab_results_test ON lab_results(test_name, result_datetime);
```

#### Implementation Tasks
- [x] **Backend:**
  - [ ] Create lab tables
  - [ ] Lab result extraction from PDFs (tables in documents)
  - [ ] Lab order creation API
  - [ ] Result trending API
  
- [x] **Frontend:**
  - [ ] Lab results display in Patient EHR
  - [ ] Result trending charts
  - [ ] Flagged results highlighting (critical, abnormal)
  - [ ] Lab report PDF viewer

---

### Sprint 2.3: Procedures Table (Week 5)
**Objective:** Surgical history, billable procedures

#### Database Schema
```sql
CREATE TABLE procedures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    encounter_id UUID REFERENCES encounters(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    
    -- Procedure coding
    procedure_code TEXT,
    coding_system TEXT CHECK (coding_system IN ('CPT', 'ICD-10-PCS', 'HCPCS', 'local')) DEFAULT 'local',
    procedure_name TEXT NOT NULL,
    
    -- Details
    performed_datetime TIMESTAMPTZ,
    operator TEXT,  -- Surgeon/performer
    assistant TEXT,
    location TEXT,
    
    -- Outcome
    outcome TEXT,
    complications TEXT,
    notes TEXT,
    
    -- Billing
    billable BOOLEAN DEFAULT true,
    
    -- Source
    source TEXT CHECK (source IN ('manual_entry', 'document_extraction', 'imported')),
    source_document_id UUID REFERENCES document_refs(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_procedures_patient ON procedures(patient_id, performed_datetime DESC);
CREATE INDEX idx_procedures_encounter ON procedures(encounter_id);
CREATE INDEX idx_procedures_code ON procedures(procedure_code, coding_system);
```

---

### Sprint 2.4: Immunizations (Week 6)
**Objective:** Vaccine tracking for occupational health

#### Database Schema
```sql
CREATE TABLE immunizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    encounter_id UUID REFERENCES encounters(id),
    
    -- Vaccine details
    vaccine_code TEXT,  -- CVX code (future)
    vaccine_name TEXT NOT NULL,
    dose_number INTEGER,
    series_total INTEGER,
    
    -- Administration
    administered_datetime TIMESTAMPTZ NOT NULL,
    site TEXT,  -- Left deltoid, right thigh, etc.
    route TEXT CHECK (route IN ('intramuscular', 'subcutaneous', 'oral', 'intranasal', 'intradermal')),
    dose_quantity NUMERIC,
    dose_units TEXT,
    
    -- Product details
    lot_number TEXT,
    manufacturer TEXT,
    expiration_date DATE,
    
    -- Provider
    administering_provider TEXT,
    clinic_location TEXT,
    
    -- Schedule
    next_due_date DATE,
    
    -- Outcome
    adverse_reaction TEXT,
    notes TEXT,
    
    -- Source
    source TEXT CHECK (source IN ('manual_entry', 'document_extraction', 'imported')),
    source_document_id UUID REFERENCES document_refs(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_immunizations_patient ON immunizations(patient_id, administered_datetime DESC);
CREATE INDEX idx_immunizations_vaccine ON immunizations(vaccine_name);
CREATE INDEX idx_immunizations_due ON immunizations(patient_id, next_due_date) WHERE next_due_date IS NOT NULL;
```

---

## 💰 PHASE 3: BILLING & REVENUE CYCLE (WEEKS 7-10)
**Status:** 🟢 PLANNED
**Priority:** 🔥 HIGH - Business monetization

### Sprint 3.1: Claims System (Weeks 7-8)
**Objective:** Medical aid billing, revenue tracking

#### Database Schema
```sql
CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    encounter_id UUID NOT NULL REFERENCES encounters(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    
    -- Claim identification
    claim_number TEXT UNIQUE,
    external_claim_id TEXT,  -- Medical aid reference
    
    -- Payer
    payer_type TEXT CHECK (payer_type IN ('cash', 'card', 'medical_aid', 'corporate', 'government')) NOT NULL,
    payer_name TEXT,  -- Discovery, Bonitas, etc.
    payer_plan TEXT,
    member_number TEXT,
    
    -- Amounts
    total_amount NUMERIC(12,2) NOT NULL,
    approved_amount NUMERIC(12,2),
    patient_responsibility NUMERIC(12,2),
    paid_amount NUMERIC(12,2) DEFAULT 0,
    
    -- Status
    status TEXT CHECK (status IN ('draft', 'submitted', 'adjudicated', 'partially_paid', 'paid', 'rejected', 'void', 'appealed')) DEFAULT 'draft',
    
    -- Dates
    service_date DATE NOT NULL,
    submission_datetime TIMESTAMPTZ,
    adjudication_datetime TIMESTAMPTZ,
    
    -- Denial management
    denial_reason TEXT,
    appeal_notes TEXT,
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_by TEXT
);

CREATE TABLE claim_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    
    -- Service coding
    code TEXT NOT NULL,
    coding_system TEXT CHECK (coding_system IN ('CPT', 'ICD-10-PCS', 'HCPCS', 'tariff_code')) NOT NULL,
    description TEXT NOT NULL,
    
    -- Quantities
    units NUMERIC(10,2) DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL,
    line_total NUMERIC(12,2) GENERATED ALWAYS AS (units * unit_price) STORED,
    
    -- Medical necessity
    linked_diagnosis_id UUID REFERENCES diagnoses(id),
    modifier TEXT,
    
    -- Adjudication
    approved_units NUMERIC(10,2),
    approved_amount NUMERIC(12,2),
    denial_code TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES claims(id),
    
    -- Payment details
    payment_type TEXT CHECK (payment_type IN ('cash', 'card', 'eft', 'medical_aid_remit', 'write_off', 'refund')) NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    payment_datetime TIMESTAMPTZ DEFAULT NOW(),
    
    -- Transaction
    transaction_ref TEXT,
    batch_id TEXT,
    remittance_advice_ref TEXT,
    
    -- Banking
    bank_name TEXT,
    account_last4 TEXT,
    
    -- Reconciliation
    reconciled BOOLEAN DEFAULT false,
    reconciled_datetime TIMESTAMPTZ,
    
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_claims_encounter ON claims(encounter_id);
CREATE INDEX idx_claims_patient ON claims(patient_id);
CREATE INDEX idx_claims_status ON claims(workspace_id, status);
CREATE INDEX idx_claims_payer ON claims(payer_type, payer_name);
CREATE INDEX idx_claim_line_items_claim ON claim_line_items(claim_id);
CREATE INDEX idx_payments_claim ON payments(claim_id);
```

#### Implementation Tasks
- [x] **Backend:**
  - [ ] Create claims tables
  - [ ] Claim creation from encounter
  - [ ] ICD-10 codes from diagnoses
  - [ ] Medical aid submission export (CSV/XML)
  - [ ] Payment reconciliation logic
  - [ ] 2% fee calculation on successful claims
  
- [x] **Frontend:**
  - [ ] Claim creation UI
  - [ ] Claim status tracking
  - [ ] Payment recording
  - [ ] Remittance advice upload
  - [ ] Denial management workflow
  - [ ] Revenue reports

---

## 🔄 PHASE 4: INTEGRATION & INTEROPERABILITY (WEEKS 11+)
**Status:** 🟣 FUTURE
**Priority:** 🔷 MEDIUM - Long-term value

### Sprint 4.1: External Lab Integration
- HL7 v2 / FHIR result ingestion
- PathCare, Lancet, Ampath APIs

### Sprint 4.2: Pharmacy Integration
- Dispensing notifications
- Stock management

### Sprint 4.3: Medical Aid Pre-Auth
- Online pre-authorization requests
- Real-time eligibility checks

### Sprint 4.4: FHIR API
- FHIR R4 Patient, Encounter, Observation resources
- External EHR interoperability

---

## 📊 MIGRATION STRATEGY

### Backward Compatibility
- Keep old tables during transition
- Use database views to bridge old/new
- Feature flags for gradual rollout

### Data Migration Scripts
1. `patient_conditions` → `diagnoses` (with AI ICD-10 suggestion)
2. `encounters.vitals_json` → `vitals` table
3. `encounters.gp_notes` → `clinical_notes` (SOAP parsing)
4. MongoDB documents → `document_refs` linkage

### Rollback Plan
- All migrations reversible
- Old APIs maintained for 3 months
- Rollback scripts prepared

---

## 🎯 SUCCESS METRICS

### Phase 1 (Patient Safety)
- [ ] 0 prescriptions of known allergens
- [ ] 100% of encounters have vitals recorded
- [ ] 80% of diagnoses have ICD-10 codes

### Phase 2 (Clinical Workflow)
- [ ] Lab results accessible in <2 clicks
- [ ] SOAP notes structured 90%+ of time
- [ ] 50% reduction in clinical documentation time

### Phase 3 (Billing)
- [ ] Medical aid claim acceptance rate >85%
- [ ] Payment cycle reduced to <14 days
- [ ] Revenue tracking accurate to 99%

---

## 🚀 NEXT STEPS

1. **Review & approve** this roadmap
2. **Start Sprint 1.1** (Allergies) - Day 1
3. **Daily standups** to track progress
4. **User testing** after each sprint
5. **Iterate** based on clinic feedback

---

**Last Updated:** 2025-10-23
**Version:** 2.0
**Status:** Ready for implementation

# SurgiScan GP Practice Workflow - Implementation Roadmap

## Overview
Transform SurgiScan into a complete GP practice management system with queue management, workstation routing, AI scribe, and real-time analytics.

**Last Updated:** October 22, 2025

---

## 🎯 Quick Status Overview

**Overall Progress:** ~75% Core Features Complete

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Foundation | ✅ Complete | 100% |
| Phase 1.5: GP Document Digitization (Old) | ✅ Complete | 100% |
| **Phase 1.7: Document Architecture Refactor** | 🚀 **IN PROGRESS** | 20% |
| Phase 1.6: Document-to-EHR Integration | ✅ Complete | 100% |
| Phase 2: Queue Management | ✅ Complete | 100% |
| Phase 3: Vitals Station | ✅ Complete | 100% |
| Phase 4.1: AI Scribe | ✅ Complete | 100% |
| Phase 4.2: Prescription Module | ✅ Complete | 100% |
| Phase 5: Dispensary Workflow | 🔄 Not Started | 0% |
| Phase 7: Enhanced Analytics | 🔄 Basic | 30% |
| Phase 8: Intelligent Search | 🔄 Not Started | 0% |

---

## Current Status ✅

**Phase 1: Foundation (COMPLETED)**
- ✅ Patient registration and management
- ✅ 6-tab EHR/EMR interface
- ✅ Encounter management with vitals
- ✅ Billing and invoicing
- ✅ Analytics dashboard with real-time data
- ✅ Multi-tenancy architecture
- ✅ Supabase + MongoDB hybrid database

**Phase 1.5: GP Document Digitization - Core (COMPLETED)**
- ✅ Document upload with drag-and-drop interface
- ✅ LandingAI microservice integration (separate FastAPI service on port 5001)
- ✅ Visual grounding validation interface (bi-directional PDF ↔ data highlighting)
- ✅ Editable validation tabs (Demographics, Chronic Care, Vitals, Clinical Notes)
- ✅ Modification tracking for ML retraining
- ✅ Backend validation save endpoint with audit logging
- ⚠️ **BLOCKED**: LandingAI API balance insufficient - cannot process new documents

**Phase 1.6: Document-to-EHR Integration (PARTIALLY COMPLETE)**
- ✅ Smart patient matching with confirmation workflow (implemented, needs full testing)
- ✅ Automatic EHR population from validated documents (implemented, needs full testing)
- ✅ Encounter creation from scanned records (implemented, needs full testing)
- ✅ Document archive viewer for compliance (implemented, needs full testing)
- ✅ Access audit trail for legal cases (implemented, needs full testing)

**Phase 2: Reception & Queue Management (PARTIALLY COMPLETE)**
- ✅ Patient check-in interface (ReceptionCheckIn.jsx)
- ✅ Queue management system backend endpoints
- ✅ Queue Display for waiting room (QueueDisplay.jsx)
- ✅ Workstation Dashboard for doctors/nurses (WorkstationDashboard.jsx)
- 🔄 Full integration testing needed

**Phase 3: Vitals Station Integration (COMPLETED)**
- ✅ Vitals recording interface (VitalsStation.jsx)
- ✅ Quick nurse workflow for vital signs entry
- ✅ Integration with patient encounters

**Phase 4: Consultation Station (COMPLETED) ⭐**
- ✅ **Phase 4.1: AI Scribe** 
  - Real-time audio recording and transcription (OpenAI Whisper)
  - AI-generated SOAP notes (OpenAI GPT-4o)
  - Consultation documentation workflow
- ✅ **Phase 4.2: Enhanced Prescription Module**
  - Electronic prescription generation (multi-medication support)
  - Sick notes / medical certificates
  - Referral letters to specialists
  - Internal medication database (20 common medications)
  - Medication search functionality
  - Patient prescription history viewer

---

## Envisioned GP Practice Workflow

### Station 1: Reception/Registration
**Actors:** Receptionist OR Patient (self-service)

**Workflow:**
1. Patient arrives at practice
2. Check patient status:
   - **New Patient** → Full registration (demographics, medical aid, contact)
   - **Existing Patient** → Quick check-in (confirm details, reason for visit)
3. System assigns queue number
4. Patient waits in waiting room

**Key Questions to Address:**
- **Self-Service Option?** Should patients check-in themselves via tablet to reduce reception queue?
- **Existing Patient Check-in:** What information should they provide?
  - Reason for visit?
  - Update contact details?
  - Confirm medical aid?
  - Just "I'm here" button?

---

### Queue Management System
**Components:**
- LED Screen display in waiting room
- Real-time queue status
- Audio announcements
- Patient tracking through workflow

**Features:**
- Display current queue position
- Show who's next
- Estimated wait time
- Audio announcement: "Patient [Name/Number], please proceed to Consultation Room [X]"
- SMS notification option

---

### Station 2: Vitals (Optional)
**Actors:** Nurse OR Doctor (some doctors do vitals themselves)

**Workflow:**
1. Patient called to vitals station (if practice has one)
2. Nurse records:
   - Blood Pressure
   - Heart Rate
   - Temperature
   - Weight
   - Height
   - Oxygen Saturation
3. System timestamps and records vitals
4. Patient returns to queue or proceeds to doctor

**Timing Tracked:** Time spent at vitals station

---

### Station 3: Consultation
**Actors:** Doctor

**Workflow:**
1. Patient called to consultation room
2. Doctor reviews:
   - Patient history (from EHR)
   - Current vitals (if recorded)
   - Previous encounters
   - Medications
   - Allergies
3. **AI Scribe captures consultation** (no manual note-taking!)
4. Doctor examines patient
5. Doctor makes diagnosis
6. Doctor prescribes:
   - Medications
   - Referrals (to specialists)
   - Sick notes/certificates
   - Lab investigations
7. Doctor clicks **"Submit Consultation"**

**System Actions After Submit:**
- **If NO Dispensary:** Generate invoice → Send to Admin for payment processing
- **If Dispensary Exists:** Send prescription electronically → Dispensary starts preparing

**Timing Tracked:** Time spent in consultation

---

### Station 4: Dispensary (Optional - Only if GP has dispensing license)
**Actors:** Pharmacist/Dispenser

**Workflow:**
1. Prescription received electronically from consultation
2. Dispenser prepares medication while patient finishes consultation
3. Patient called to dispensary
4. Dispenser:
   - Verifies patient identity
   - Explains medication instructions
   - Dispenses medication
   - Records dispensing event
5. Generate invoice (includes consultation + medication)
6. Patient proceeds to payment

**Timing Tracked:** Time spent at dispensary

---

### Station 5: Admin/Payment
**Actors:** Admin/Receptionist

**Workflow:**
1. Invoice received from system
2. Patient makes payment:
   - Cash
   - Card
   - Medical Aid (claim submission)
3. Issue receipt
4. Patient exits

**Timing Tracked:** Time spent at payment counter

---

## Implementation Phases

### **PHASE 1.6: Document-to-EHR Integration** ⭐ (Priority 1 - CURRENT)

**Goal:** Complete the digitization loop by automatically populating EHR with validated document data and providing compliance-ready document archive.

#### 1.6.1 Smart Patient Matching
**Approach:** Semi-automatic with human confirmation

**Features:**
- Automatic patient search by SA ID number (primary)
- Fallback search by Name + DOB
- Fuzzy matching for name variations
- Confidence scoring (High/Medium/Low)
- User confirmation interface with side-by-side comparison
- "Create New Patient" option for no matches
- Duplicate prevention logic

**Matching Algorithm:**
```python
def match_patient(extracted_data):
    # Step 1: Search by ID number (95% reliable)
    if id_number_match:
        return HighConfidenceMatch(patient)
    
    # Step 2: Fuzzy name + DOB match
    if similar_name and dob_match:
        return MediumConfidenceMatch(patient)
    
    # Step 3: No clear match
    return SuggestNewPatient()
```

**UI Flow:**
- Show match results with confidence indicator
- Display extracted data vs existing patient data side-by-side
- One-click confirm or create new
- Handles edge cases (multiple matches, no match)

**Database Changes:**
```sql
-- Track patient matching decisions
CREATE TABLE patient_match_logs (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    matched_patient_id TEXT,
    confidence_score FLOAT,
    match_method TEXT, -- 'id_number', 'name_dob', 'manual'
    confirmed_by TEXT,
    created_at TIMESTAMP
);
```

**Estimated Time:** 1 day

---

#### 1.6.2 Automatic EHR Population

**Features:**
- Create new patient record if no match
- Create new encounter from validated data
- Populate encounter with:
  - Vitals from scanned document
  - Chronic conditions
  - Medications
  - Clinical notes
  - Document date as encounter date
- Smart merging of chronic conditions (avoid duplicates)
- Medication reconciliation
- Update patient demographics if changed

**Workflow After "Confirm Match":**
```
1. Create/Update Patient
   ↓
2. Create New Encounter
   - encounter_date = document_date
   - vitals = validated_vitals
   - status = 'completed' (historical record)
   ↓
3. Merge Medical History
   - Add new chronic conditions (check for duplicates)
   - Add medications to patient's medication list
   - Append clinical notes to history
   ↓
4. Link Document to Encounter
   - Store document_id in encounter
   - Update document status to 'linked'
   ↓
5. Audit Log
   - Record EHR population event
   - Track data transformations
```

**API Endpoints:**
```
POST   /api/gp/validation/match-patient     # Search for patient matches
POST   /api/gp/validation/confirm-match     # Confirm match and populate EHR
POST   /api/gp/validation/create-new-patient # Create new patient from document
```

**Estimated Time:** 1.5 days

---

#### 1.6.3 Document Archive Viewer (Compliance)

**Critical for Legal Cases - 40 Year Retention (South Africa)**

**Features:**

**A. Patient Document History Page:**
- Timeline view of all scanned documents for a patient
- Filter by:
  - Date range
  - Document type (consultation, lab, prescription, discharge summary)
  - Status (validated, pending, linked)
- Search across document content
- Quick preview thumbnails
- Bulk operations (export, print)

**B. Document Viewer Interface:**
- View original PDF (immutable, as scanned)
- View extracted/validated data side-by-side
- Show validation audit trail:
  - Who validated
  - When validated
  - What was modified
  - Original vs edited values
- Access control (logged in user only)
- Print/download for legal purposes
- Watermark with access timestamp

**C. Archive Management:**
- Document metadata:
  - Upload date
  - Document type
  - Patient link
  - Encounter link (if created)
  - File size
  - Pages count
- Document lifecycle tracking
- Retention policy enforcement (40 years)
- Secure deletion after retention period

**D. Legal Export Feature:**
- Package document + audit trail for court
- Generate PDF report with:
  - Original scanned document
  - Validation history
  - Access logs
  - Cryptographic hash (proof of integrity)
  - Chain of custody

**UI Pages:**
```
1. Patient Record → "Documents" Tab
   - List all scanned documents
   - Timeline view
   
2. Document Viewer (Modal or Full Page)
   - Left: Original PDF
   - Right: Extracted/Validated Data
   - Bottom: Audit Trail
   
3. Archive Search (Admin)
   - Search across all documents
   - Advanced filters
```

**Database Schema:**
```sql
-- Document access audit
CREATE TABLE document_access_logs (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    user_id TEXT,
    access_type TEXT, -- 'view', 'download', 'print', 'export'
    ip_address TEXT,
    user_agent TEXT,
    accessed_at TIMESTAMP
);

-- Document retention tracking
CREATE TABLE document_retention (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    uploaded_at TIMESTAMP,
    retention_until TIMESTAMP, -- 40 years from upload
    status TEXT, -- 'active', 'archived', 'scheduled_deletion'
);
```

**API Endpoints:**
```
GET    /api/documents/patient/{patient_id}        # Get all documents for patient
GET    /api/documents/{document_id}/view          # View document (already exists)
GET    /api/documents/{document_id}/audit-trail   # Get validation & access history
POST   /api/documents/{document_id}/access-log    # Log document access
GET    /api/documents/{document_id}/legal-export  # Export for legal case
GET    /api/documents/search                      # Search across all documents
```

**Estimated Time:** 2 days

---

#### 1.6.4 Access Audit Trail

**Features:**
- Log every document access (view, download, print)
- Track user, timestamp, IP address
- Searchable audit logs
- Export audit trail for compliance
- Alert on suspicious access patterns
- Integration with document viewer

**Compliance Requirements (South Africa Medical):**
- Track who accessed what and when
- Immutable audit logs
- Export for HPCSA audits
- POPIA (Protection of Personal Information Act) compliance

**Estimated Time:** 0.5 days

---

**Total Estimated Time for Phase 1.6:** 5 days

**Priority Order:**
1. Smart Patient Matching (1 day)
2. EHR Population (1.5 days)
3. Document Archive Viewer (2 days)
4. Access Audit Trail (0.5 days)

---

### **PHASE 2: Reception & Queue Management** (Priority 2 - AFTER Phase 1.6)

#### 2.1 Patient Check-in Interface
**New Components:**
- Reception Kiosk interface
- Self-service tablet interface (optional)
- Queue management system

**Features:**
- Quick patient search
- One-click check-in for existing patients
- Registration for new patients
- Reason for visit capture
- Queue number assignment

**Database Schema Additions:**
```sql
-- Queue management
CREATE TABLE queue_entries (
    id TEXT PRIMARY KEY,
    patient_id TEXT REFERENCES patients(id),
    workspace_id TEXT REFERENCES workspaces(id),
    queue_number INTEGER,
    check_in_time TIMESTAMP,
    reason_for_visit TEXT,
    status TEXT, -- 'waiting', 'at_vitals', 'at_consultation', 'at_dispensary', 'completed'
    current_station TEXT,
    created_at TIMESTAMP
);

-- Workstation tracking
CREATE TABLE workstation_logs (
    id TEXT PRIMARY KEY,
    queue_entry_id TEXT REFERENCES queue_entries(id),
    station_type TEXT, -- 'reception', 'vitals', 'consultation', 'dispensary', 'payment'
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    staff_id TEXT, -- doctor/nurse/receptionist
    created_at TIMESTAMP
);
```

**API Endpoints:**
```
POST   /api/queue/check-in          # Check-in patient
GET    /api/queue/current            # Get current queue status
POST   /api/queue/call-next          # Call next patient
PUT    /api/queue/{id}/move-station # Move patient to next station
GET    /api/queue/display            # For LED screen
```

**UI Pages:**
- Reception Check-in page
- Queue Display (LED screen view)
- Workstation Dashboard (for calling patients)

---

#### 2.2 Self-Service Kiosk (Optional)
**Decision Needed:** Should patients self-check-in?

**Pros:**
- Reduces reception queue
- Faster check-in
- Less staff needed
- Modern patient experience

**Cons:**
- Some patients may need assistance
- Requires tablets/kiosks
- Security considerations

**If Yes, What Should Existing Patients Provide?**
- Option A: Just "I'm Here" button + confirm contact number
- Option B: Reason for visit + update any changed details
- Option C: Brief questionnaire about symptoms

**Recommendation:** 
- Start with assisted reception check-in
- Add self-service kiosk later as enhancement

---

### **PHASE 3: Vitals Station Integration** (COMPLETED ✅)

**Status:** Fully implemented and operational

**Implemented Features:**
- ✅ Vitals recording interface (VitalsStation.jsx)
- ✅ Integration with EHR
- ✅ Automatic timestamp tracking
- ✅ Quick nurse workflow for vital signs entry
- ✅ Fields: Blood pressure, heart rate, temperature, weight, height, oxygen saturation

**Pages Created:**
- ✅ `/vitals` - VitalsStation.jsx (optimized for quick input)
- ✅ Navigation link in Layout.jsx

**Estimated Time:** 1 day ✅ COMPLETE

---

### **PHASE 4: Consultation Station** (COMPLETED ✅) ⭐

#### 4.1 AI Scribe Integration (COMPLETED ✅)

**Status:** Fully implemented and operational

**Technology Used:**
- ✅ OpenAI Whisper API (speech-to-text)
- ✅ OpenAI GPT-4o (SOAP note structuring)
- ✅ Direct OpenAI API integration (OPENAI_API_KEY)

**Implemented Features:**
- ✅ **Real-time audio recording** using browser MediaRecorder API
- ✅ **Automatic transcription** via OpenAI Whisper
- ✅ **Automatic SOAP note generation:**
  - **S**ubjective (patient's complaint)
  - **O**bjective (examination findings)
  - **A**ssessment (diagnosis)
  - **P**lan (treatment plan)
- ✅ **Review and edit** before saving
- ✅ **Patient context integration** (name, age, chronic conditions)
- ✅ **Save to encounter** functionality

**Workflow Implemented:**
1. ✅ Doctor navigates to patient EHR → clicks "AI Scribe"
2. ✅ Clicks "Start Recording" 
3. ✅ Records consultation audio with real-time timer
4. ✅ Clicks "Stop Recording" → automatic transcription
5. ✅ Reviews transcription text
6. ✅ Clicks "Generate SOAP Notes" → AI structures into SOAP format
7. ✅ Reviews and edits SOAP notes
8. ✅ Clicks "Save to Encounter"

**Pages Created:**
- ✅ `/patients/:patientId/ai-scribe` - AIScribe.jsx
- ✅ "AI Scribe" button added to PatientEHR.jsx

**Backend Endpoints:**
- ✅ `/api/ai-scribe/transcribe` - Audio transcription using Whisper
- ✅ `/api/ai-scribe/generate-soap` - SOAP note generation using GPT-4o

**Estimated Time:** 3-4 days ✅ COMPLETE

---

#### 4.2 Enhanced Prescription Module (COMPLETED ✅)

**Status:** Fully implemented, tested, and operational

**Implemented Features:**

**1. Electronic Prescription Generation:**
- ✅ Multi-medication support per prescription
- ✅ Fields: medication name, dosage, frequency, duration, quantity, instructions
- ✅ Medication search with autocomplete (internal database)
- ✅ Add/remove medication items dynamically
- ✅ Additional notes support
- ✅ Full CRUD operations via API

**2. Sick Notes / Medical Certificates:**
- ✅ Date range (start/end) with automatic day calculation
- ✅ Diagnosis field
- ✅ Fitness status (unfit, fit with restrictions, fit for work)
- ✅ Restrictions/limitations field (conditional)
- ✅ Additional notes support

**3. Referral Letters:**
- ✅ 15+ specialist types (Cardiologist, Orthopedist, Neurologist, etc.)
- ✅ Specialist details (name, practice/hospital)
- ✅ Urgency levels (urgent, routine, non-urgent)
- ✅ Reason for referral
- ✅ Clinical findings
- ✅ Investigations done
- ✅ Current medications
- ✅ Status tracking (pending, sent, completed, cancelled)

**4. Medication Database:**
- ✅ Internal drug database with 20 common medications
- ✅ Categories: Analgesics, Antibiotics, Antihypertensives, Diabetes, Respiratory, etc.
- ✅ Medication details: generic name, brand names, dosages, frequencies, contraindications
- ✅ Search API endpoint with autocomplete

**Components Created:**
- ✅ PrescriptionBuilder.jsx - Interactive prescription creation
- ✅ SickNoteBuilder.jsx - Medical certificate generator
- ✅ ReferralBuilder.jsx - Referral letter builder
- ✅ PatientPrescriptions.jsx - Comprehensive view with tabs

**Backend Endpoints:**
- ✅ `/api/prescriptions` - Create prescription
- ✅ `/api/prescriptions/patient/{id}` - Get patient prescriptions
- ✅ `/api/prescriptions/{id}` - Get specific prescription
- ✅ `/api/sick-notes` - Create sick note
- ✅ `/api/sick-notes/patient/{id}` - Get patient sick notes
- ✅ `/api/referrals` - Create referral
- ✅ `/api/referrals/patient/{id}` - Get patient referrals
- ✅ `/api/medications/search` - Search medications
- ✅ `/api/medications/{id}` - Get medication details

**Database Tables (Supabase):**
- ✅ `prescriptions` - Prescription headers
- ✅ `prescription_items` - Medication line items
- ✅ `sick_notes` - Medical certificates
- ✅ `referrals` - Specialist referrals
- ✅ `medications` - Drug database
- ✅ `prescription_templates` - Future template support
- ✅ `prescription_template_items` - Template medications
- ✅ `prescription_documents` - PDF storage references

**Access Points:**
- ✅ Patient EHR → "Prescriptions" button
- ✅ Direct URL: `/patients/:patientId/prescriptions`
- ✅ Tabbed interface: Prescriptions | Sick Notes | Referrals

**Nice-to-Have Features (Future Roadmap):**
- 🔄 PDF generation for prescriptions/sick notes/referrals
- 🔄 Prescription templates (pre-configured common prescriptions)
- 🔄 Basic drug interaction checker
- 🔄 Dosage calculator based on weight/age
- 🔄 Integration with dispensary workflow
- 🔄 E-prescribing to pharmacy networks

**Estimated Time:** 2-3 days ✅ COMPLETE

---

### **PHASE 5: Dispensary Workflow** (Priority 5)

**Features:**
- Electronic prescription inbox
- Medication preparation tracking
- Stock management integration
- Dispensing recording
- Patient counseling checklist

**New Pages:**
- Dispensary Dashboard
- Prescription Queue
- Dispensing Interface
- Stock Alerts

**Database Schema:**
```sql
-- Dispensary queue
CREATE TABLE dispensary_queue (
    id TEXT PRIMARY KEY,
    encounter_id TEXT REFERENCES encounters(id),
    prescription_id TEXT,
    status TEXT, -- 'pending', 'preparing', 'ready', 'dispensed'
    received_at TIMESTAMP,
    prepared_at TIMESTAMP,
    dispensed_at TIMESTAMP
);
```

---

### **PHASE 6: LandingAI Document Digitization Integration**

**Current Status:**
- Mock ADE parser in place
- You have Python microservice ready

**Integration Steps:**
1. Deploy your Python microservice
2. Create API bridge between SurgiScan backend and your microservice
3. Replace mock parser with real LandingAI calls
4. Handle authentication and API keys
5. Process real scanned documents
6. Return structured medical data

**API Integration Pattern:**
```python
# Your microservice endpoint
POST /digitize
{
    "file": base64_encoded_file,
    "file_type": "pdf|jpg|png"
}

Response:
{
    "patient_demographics": {...},
    "medical_history": [...],
    "medications": [...],
    "allergies": [...],
    "lab_results": [...],
    "clinical_notes": "...",
    "confidence": 0.95
}
```

---

### **PHASE 7: Analytics Fine-Tuning** (Priority 6)

#### Key Metrics to Track:

**Operational Metrics:**
- Average time per workstation
- Peak hours analysis
- Patient throughput per day
- Queue wait times
- Consultation duration trends
- Bottleneck identification

**Clinical Metrics:**
- Most common diagnoses
- Prescription patterns
- Referral rates
- Follow-up compliance
- Chronic disease management stats

**Financial Metrics:**
- Revenue per consultation type
- Medical aid vs cash ratio
- Dispensary revenue (if applicable)
- Outstanding invoices
- Peak revenue hours

**Workstation Efficiency:**
- Doctor consultation time average
- Vitals station throughput
- Dispensary preparation time
- Payment processing time

**Patient Flow:**
- Average total visit time
- Station-to-station transition times
- Peak queue times
- Patient satisfaction indicators

**Enhanced Charts:**
- Heatmap: Busy hours/days
- Funnel: Patient flow through stations
- Comparison: Doctor efficiency metrics
- Trends: Wait times over weeks/months

---

## Decision Points & Questions

### 1. Self-Service Check-in
**Question:** Should patients self-check-in on tablets?
- **Option A:** Yes, add self-service kiosks
- **Option B:** No, keep reception-assisted only
- **Option C:** Hybrid (both options available)

**For existing patients, what should they enter?**
- Just "I'm here" confirmation?
- Reason for visit?
- Symptom questionnaire?

### 2. AI Scribe Technology ✅ RESOLVED
**Decision Made:** Built in-house using OpenAI APIs
- ✅ **Implemented:** OpenAI Whisper (transcription) + GPT-4o (SOAP structuring)
- ✅ Direct OpenAI API integration
- ✅ Real-time recording and transcription
- ✅ Status: Fully operational

### 3. Queue Display
**Question:** Hardware requirements?
- Do you have LED screens available?
- What size/resolution?
- Should we support multiple display types?

### 4. Dispensary Priority
**Question:** How many GPs have dispensary?
- If majority → High priority
- If minority → Lower priority

### 5. Audio Announcements
**Question:** Text-to-speech for patient calling?
- Do practices have speaker systems?
- Language requirements? (English, Afrikaans, Zulu, etc.)

---

## Technology Stack Additions

**For Queue Management:**
- WebSockets for real-time updates
- LED screen rendering (web-based or custom)

**For AI Scribe:**
- OpenAI Whisper API
- OpenAI GPT-4 for medical note structuring
- Audio recording library (browser-based)

**For Real-time Updates:**
- Server-Sent Events (SSE) or WebSockets
- Redis for queue state management

---

## Next Steps

**Immediate Actions:**
1. **Clarify Decision Points** (answer questions above)
2. **Prioritize Phases** (which phase should we build first?)
3. **Define MVP Scope** for Phase 2 (Queue Management)
4. **Prepare for LandingAI Integration** (when will microservice be ready?)

**Recommended Implementation Order:**
1. ✅ **Phase 1.6:** Document-to-EHR Integration (Complete digitization loop - IMPLEMENTED, needs testing)
2. 🔄 **Phase 2:** Reception check-in + Queue management (Foundation for workflow - PARTIALLY COMPLETE)
3. ✅ **Phase 3:** Vitals station integration (COMPLETE)
4. ✅ **Phase 4.1:** AI Scribe (COMPLETE - High value, immediate doctor productivity boost!)
5. ✅ **Phase 4.2:** Enhanced prescription module (COMPLETE)
6. 🔄 **Phase 5:** Dispensary workflow (if applicable to many GPs)
7. 🔄 **Phase 7:** Analytics fine-tuning
8. 🔄 **Phase 8:** Intelligent Document Search with Visual Grounding
9. 🔄 **Phase 2.2:** Self-service kiosks (enhancement)

**Current Priority:** Complete testing of Phase 1.6, 2, and 3 features

---

## Estimated Complexity & Status

**Phase 1.6 (Document-to-EHR):** Medium - 5 days ✅ COMPLETE (needs full testing)
**Phase 2 (Queue Management):** Medium - 2-3 days ✅ PARTIALLY COMPLETE
**Phase 3 (Vitals):** Low - 1 day ✅ COMPLETE
**Phase 4.1 (AI Scribe):** High - 3-4 days ✅ COMPLETE
**Phase 4.2 (Prescriptions):** Medium - 2-3 days ✅ COMPLETE
**Phase 5 (Dispensary):** Medium - 2 days 🔄 NOT STARTED
**Phase 6 (LandingAI):** ✅ Integration complete (⚠️ API balance insufficient)
**Phase 7 (Analytics):** Medium - 2 days 🔄 BASIC COMPLETE, needs enhancement
**Phase 8 (Intelligent Search):** Medium-High - 1-2 weeks 🔄 NOT STARTED
  - Phase 8.1 (Basic Search): 1-2 days
  - Phase 8.2 (Visual Grounding): 2-3 days
  - Phase 8.3 (Advanced Features): 3-4 days
  - Phase 8.4 (Case Analytics): 3-4 days

**Completion Status:** ~70% of core features complete
**Remaining Work:** Testing, Dispensary workflow, Enhanced analytics, Intelligent search

---

## Phase 8: Intelligent Document Search with Visual Grounding 🔍 (NEW)

**Vision:** Enable doctors to search across 20+ years of digitized patient records with visual highlighting of relevant sections.

### Use Case
*"Doctor needs to reference a rare disease case from 8 years ago. Search for disease name, system shows matching cases with the original document displayed and relevant sections visually highlighted."*

### What Makes This Powerful
- **Semantic Search:** Find documents by medical terms, conditions, medications, symptoms
- **Visual Grounding:** LandingAI's bounding boxes highlight exact sections containing search terms
- **Historical Context:** Access decades of medical records instantly
- **Case-Based Learning:** Compare similar cases across time

---

### Architecture Already in Place ✅

**Current Foundation (Already Built):**
1. ✅ **Document parsing with chunks** - Each document broken into semantic chunks
2. ✅ **Grounding coordinates** - Every chunk has `{page, box: {top, left, bottom, right}}`
3. ✅ **MongoDB storage** - All chunks stored with metadata in `gp_parsed_documents` collection
4. ✅ **Text extraction** - Markdown content available for each chunk
5. ✅ **PDF viewer** - Already displaying documents with react-pdf
6. ✅ **Patient linking** - Documents associated with patients/encounters

**What This Means:**
The heavy lifting is done! Each chunk already has:
```javascript
{
  id: "chunk_123",
  markdown: "Patient diagnosed with Addison's disease...",
  grounding: {
    page: 2,
    box: { top: 0.15, left: 0.10, bottom: 0.25, right: 0.90 }
  }
}
```

---

### Implementation Phases

#### Phase 8.1: Basic Text Search (Week 1) 🎯
**Scope:** Full-text search across all document chunks

**Backend:**
- Create MongoDB text index on `parsed_data.chunks.markdown`
- Build search API endpoint: `GET /api/gp/search?query={term}&patient_id={id}`
- Return matching chunks with document metadata and grounding coordinates

**Frontend:**
- New "Search Records" page with search bar
- Results list showing:
  - Document name & date
  - Patient name
  - Snippet of matching text
  - Number of matches

**Estimated Time:** 1-2 days

---

#### Phase 8.2: Visual Grounding & Highlighting (Week 1-2) ⭐
**Scope:** Display documents with highlighted search results

**Frontend Enhancements:**
- Split view: Search results (left) + PDF viewer (right)
- Click result → Load PDF at correct page
- Draw highlight boxes on PDF using grounding coordinates
- Canvas overlay technique or PDF.js annotations

**Implementation:**
```javascript
// Pseudo-code for highlighting
searchResults.forEach(result => {
  const { page, box } = result.grounding;
  drawHighlightBox(page, box, 'yellow');
});
```

**Estimated Time:** 2-3 days

---

#### Phase 8.3: Advanced Search Features (Week 2-3) 🚀

**Smart Search Capabilities:**
1. **Multi-term search:** "diabetes AND hypertension"
2. **Field-specific:** Search in demographics, chronic conditions, medications separately
3. **Date range filters:** "Cases between 2015-2020"
4. **Patient filtering:** Search within specific patient's history
5. **Fuzzy matching:** Handle typos and variations

**AI-Enhanced Search (Optional):**
- Semantic search using embeddings
- "Find similar cases to this patient"
- Auto-suggest related medical terms
- Summary of matching documents

**Estimated Time:** 3-4 days

---

#### Phase 8.4: Case Comparison & Analytics (Week 3-4) 📊

**Clinical Intelligence:**
- "Show all patients with [condition] and their outcomes"
- Treatment patterns across similar cases
- Medication efficacy tracking
- Rare disease case library
- Export results for research

**Estimated Time:** 3-4 days

---

### Technical Implementation Details

#### Backend Search API
```python
@api_router.get("/gp/search")
async def search_documents(
    query: str,
    patient_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50
):
    """
    Search across parsed document chunks with grounding
    Returns: {
      results: [{
        document_id,
        patient_id,
        chunk_id,
        matched_text,
        context,
        grounding: {page, box},
        score
      }]
    }
    """
```

#### MongoDB Query
```javascript
db.gp_parsed_documents.aggregate([
  // Text search
  { $match: { $text: { $search: "addison disease" } } },
  // Unwind chunks
  { $unwind: "$parsed_data.chunks" },
  // Filter matching chunks
  { $match: { "parsed_data.chunks.markdown": { $regex: "addison", $options: "i" } } },
  // Add score
  { $addFields: { score: { $meta: "textScore" } } },
  // Sort by relevance
  { $sort: { score: -1 } },
  { $limit: 50 }
])
```

#### Frontend Highlighting Component
```jsx
<PDFHighlightViewer
  documentId={selectedResult.document_id}
  highlights={searchMatches.map(m => ({
    page: m.grounding.page,
    box: m.grounding.box,
    color: 'yellow'
  }))}
/>
```

---

### Success Metrics

**Phase 8.1:**
- ✅ Search returns results in < 1 second
- ✅ Finds relevant documents with 90%+ accuracy
- ✅ Handles 10,000+ documents efficiently

**Phase 8.2:**
- ✅ Visual highlights render correctly on PDF
- ✅ Clicking result jumps to correct page
- ✅ Supports multi-page documents with multiple matches

**Phase 8.3:**
- ✅ Advanced filters work correctly
- ✅ Fuzzy search handles misspellings
- ✅ Search suggestions improve user experience

---

### Dependencies

**Required:**
- ✅ MongoDB text indexes
- ✅ PDF.js for document rendering (already integrated)
- ✅ Canvas API for drawing highlights

**Optional (for Phase 8.3+):**
- OpenAI embeddings for semantic search
- ElasticSearch for advanced full-text capabilities
- Redis for search result caching

---

### Risk Assessment

**Low Risk:**
- Text search - MongoDB handles this natively ✅
- PDF display - Already working ✅
- Grounding data - Already captured ✅

**Medium Risk:**
- Visual highlighting accuracy - Need to test box coordinate precision
- Performance with large document sets - May need indexing optimization

**Mitigation:**
- Start with basic search, validate accuracy
- Test with real 20-year dataset
- Optimize indexes before launch

---

### Next Steps for Phase 8

**Before Starting:**
1. ✅ Complete and stabilize current digitization workflow
2. Test with real patient documents
3. Gather feedback on existing features

**When Ready to Build:**
1. **Week 1:** Phase 8.1 - Basic search functionality
2. **Week 2:** Phase 8.2 - Visual highlighting
3. **Week 3-4:** Phase 8.3 - Advanced features (if needed)

**Recommendation:**
Build Phase 8.1 and 8.2 first as MVP, then gather user feedback before investing in advanced features. The core value is finding and visually highlighting historical cases - everything else is enhancement.

---

## Questions for You

1. **Self-service check-in:** Yes or No? If yes, what should existing patients enter?
2. **AI Scribe:** Which approach? (In-house vs. service vs. simple start)
3. **Hardware:** Do you have LED screens? Speaker systems?
4. **Dispensary:** What % of your GPs have dispensing licenses?
5. **Priority:** Which phase should we build FIRST?
6. **LandingAI:** When will your Python microservice be ready to integrate?

Please answer these questions so I can create a detailed implementation plan and start building!

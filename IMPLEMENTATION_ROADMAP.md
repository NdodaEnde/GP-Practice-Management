# SurgiScan GP Practice Workflow - Implementation Roadmap

## Overview
Transform SurgiScan into a complete GP practice management system with queue management, workstation routing, AI scribe, and real-time analytics.

---

## Current Status ✅

**Phase 1: Foundation (COMPLETED)**
- ✅ Patient registration and management
- ✅ Document digitization with smart patient matching
- ✅ 6-tab EHR/EMR interface
- ✅ Encounter management with vitals
- ✅ Billing and invoicing
- ✅ Basic analytics dashboard
- ✅ Multi-tenancy architecture
- ✅ Supabase + MongoDB hybrid database

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

### **PHASE 2: Reception & Queue Management** (Priority 1)

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

### **PHASE 3: Vitals Station Integration** (Priority 2)

**Features:**
- Vitals recording interface
- Integration with EHR
- Automatic timestamp tracking
- Nurse/Doctor workflow differentiation

**New Pages:**
- Vitals Entry page (optimized for quick input)
- Vitals device integration (if available)

---

### **PHASE 4: AI Scribe for Consultation** (Priority 1 - High Value!)

#### 4.1 AI Scribe Integration
**Technology Options:**
- OpenAI Whisper (speech-to-text) + GPT for structuring
- Microsoft Azure Speech + Medical NLP
- Specialized medical scribe services

**Features:**
- **Real-time transcription** during consultation
- **Automatic SOAP note generation:**
  - **S**ubjective (patient's complaint)
  - **O**bjective (examination findings)
  - **A**ssessment (diagnosis)
  - **P**lan (treatment plan)
- **ICD-10 code suggestions** from diagnosis
- **Medication suggestions** based on diagnosis
- **Review and edit** before saving
- **Voice commands** for doctor

**Workflow:**
1. Doctor starts consultation
2. Clicks "Start Recording"
3. AI listens and transcribes in real-time
4. Doctor speaks naturally during exam
5. AI structures conversation into SOAP format
6. Doctor reviews and edits
7. Clicks "Submit" to save

**Database Schema:**
```sql
-- Consultation recordings
CREATE TABLE consultation_transcripts (
    id TEXT PRIMARY KEY,
    encounter_id TEXT REFERENCES encounters(id),
    raw_transcript TEXT,
    soap_notes JSONB, -- {subjective, objective, assessment, plan}
    icd10_codes JSONB,
    recording_duration INTEGER,
    confidence_score FLOAT,
    reviewed BOOLEAN,
    created_at TIMESTAMP
);
```

**Integration Question:**
- Where will AI Scribe processing happen?
  - Backend API with AI model?
  - Separate microservice?
  - Third-party service?

---

#### 4.2 Prescription Module Enhancement

**Features:**
- Electronic prescription generation
- Drug interaction checker
- Dosage calculator
- Prescription templates
- Referral letter generation
- Sick note generation

**New Components:**
- Prescription builder interface
- Drug database integration
- Template library

---

### **PHASE 5: Dispensary Workflow** (Priority 2)

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

### **PHASE 7: Analytics Fine-Tuning** (Priority 3)

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

### 2. AI Scribe Technology
**Question:** Which AI scribe approach?
- **Option A:** Build in-house (OpenAI Whisper + GPT)
- **Option B:** Use specialized medical scribe service (e.g., Suki, Nuance)
- **Option C:** Start simple (just recording + manual transcription)

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
1. **Phase 2.1:** Reception check-in + Queue management (Foundation)
2. **Phase 4.1:** AI Scribe (High value, immediate doctor productivity boost!)
3. **Phase 3:** Vitals station integration
4. **Phase 6:** LandingAI real integration
5. **Phase 4.2:** Enhanced prescription module
6. **Phase 5:** Dispensary workflow (if applicable to many GPs)
7. **Phase 7:** Analytics fine-tuning
8. **Phase 2.2:** Self-service kiosks (enhancement)

---

## Estimated Complexity

**Phase 2 (Queue Management):** Medium - 2-3 days
**Phase 3 (Vitals):** Low - 1 day
**Phase 4.1 (AI Scribe):** High - 3-4 days (core feature!)
**Phase 4.2 (Prescriptions):** Medium - 2 days
**Phase 5 (Dispensary):** Medium - 2 days
**Phase 6 (LandingAI):** Low - 1 day (just integration)
**Phase 7 (Analytics):** Medium - 2 days

**Total:** ~2-3 weeks for complete system

---

## Questions for You

1. **Self-service check-in:** Yes or No? If yes, what should existing patients enter?
2. **AI Scribe:** Which approach? (In-house vs. service vs. simple start)
3. **Hardware:** Do you have LED screens? Speaker systems?
4. **Dispensary:** What % of your GPs have dispensing licenses?
5. **Priority:** Which phase should we build FIRST?
6. **LandingAI:** When will your Python microservice be ready to integrate?

Please answer these questions so I can create a detailed implementation plan and start building!

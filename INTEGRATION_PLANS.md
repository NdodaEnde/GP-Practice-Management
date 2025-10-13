# Integration Plans - LandingAI & AI Scribe

## ✅ Phase 1: Enhanced Analytics - COMPLETED

New API endpoints created:
- `GET /api/analytics/operational` - Patient volume, peak hours, throughput
- `GET /api/analytics/clinical` - Diagnoses, medications, allergies, age distribution
- `GET /api/analytics/financial` - Revenue trends, payer breakdown, outstanding invoices

Analytics page now displays real data from the system.

---

## 🔌 Phase 2: LandingAI Microservice Integration

### Your Microservice Details (from logs):

**Endpoint:** `POST /api/v1/gp/upload-patient-file`
**Additional:** `GET /api/v1/gp/document/{document_id}/file`

**Process Flow (from your logs):**
1. Upload file → Saves to storage
2. Parse with LandingAI (takes ~3 minutes)
3. Extract structured data:
   - Demographics
   - Chronic summary
   - Vitals
4. Creates validation session
5. Returns 39 chunks with grounding data

### Recommended Architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment Strategy                       │
└─────────────────────────────────────────────────────────────┘

Option A: Same Container (Recommended for Start)
├─ /app/backend/server.py (Port 8001)
├─ /app/backend/microservices/landingai_service/ (Port 8002)
│   ├─ main.py (your microservice)
│   ├─ requirements.txt
│   ├─ .env (with LANDING_AI_API_KEY)
│   └─ storage/
└─ Supervisor manages both services

Option B: Separate Container (Later for Production)
├─ Main App Container (Port 8001)
└─ LandingAI Service Container (Port 8002)
    └─ Kubernetes/Docker orchestration
```

### Integration Steps:

**Step 1: Deploy Your Microservice**
```bash
# Copy your microservice folder
cp -r /path/to/your/microservice /app/backend/microservices/landingai_service

# Install dependencies
cd /app/backend/microservices/landingai_service
pip install -r requirements.txt

# Create .env file
echo "LANDING_AI_API_KEY=your_key_here" > .env
echo "MONGO_URL=mongodb://localhost:27017" >> .env
```

**Step 2: Add Supervisor Configuration**
```ini
# /etc/supervisor/conf.d/landingai.conf
[program:landingai]
directory=/app/backend/microservices/landingai_service
command=uvicorn main:app --host 0.0.0.0 --port 8002
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/landingai.out.log
stderr_logfile=/var/log/supervisor/landingai.err.log
```

**Step 3: Create API Bridge in Main Backend**
```python
# In /app/backend/server.py

import httpx

LANDING_AI_SERVICE_URL = "http://localhost:8002"

async def call_landing_ai_parser(file_content: bytes, filename: str):
    """
    Call your LandingAI microservice to parse document
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        files = {'file': (filename, file_content, 'application/pdf')}
        
        response = await client.post(
            f"{LANDING_AI_SERVICE_URL}/api/v1/gp/upload-patient-file",
            files=files
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="LandingAI parsing failed")
        
        return response.json()

# Replace mock_ade_parser with real call
def landing_ai_ade_parser(filename: str, file_content: bytes) -> Dict[str, Any]:
    """
    Real LandingAI ADE parser - replaces mock
    """
    try:
        # Call your microservice
        result = await call_landing_ai_parser(file_content, filename)
        
        # Transform your microservice response to our expected format
        return {
            'patient_demographics': result.get('demographics', {}),
            'medical_history': result.get('chronic_summary', {}).get('conditions', []),
            'current_medications': result.get('medications', []),
            'allergies': result.get('allergies', []),
            'lab_results': result.get('vitals', []),
            'clinical_notes': result.get('notes', ''),
            'diagnoses': result.get('diagnoses', []),
            'extraction_metadata': {
                'confidence': result.get('confidence', 0),
                'extracted_at': datetime.now(timezone.utc).isoformat(),
                'source_filename': filename,
                'chunks_count': len(result.get('chunks', []))
            }
        }
    except Exception as e:
        logger.error(f"LandingAI parsing error: {e}")
        # Fall back to mock if service unavailable
        return mock_ade_parser(filename, file_content)
```

**Step 4: Update Document Upload Endpoint**
```python
@api_router.post("/documents/upload-standalone")
async def upload_standalone_document(
    file: UploadFile = File(...),
    document_type: str = Form("medical_record")
):
    # ... existing code ...
    
    # Replace this line:
    # parsed_data = mock_ade_parser(file.filename, file_content)
    
    # With:
    parsed_data = await landing_ai_ade_parser(file.filename, file_content)
    
    # ... rest of existing code ...
```

### What Data Format Do You Return?

Based on your logs, please clarify:
1. What is the exact structure of the response from `/api/v1/gp/upload-patient-file`?
2. How are chunks organized?
3. Where is demographics, vitals, chronic_summary in your response?

**Please send me:**
- Sample JSON response from your microservice
- Your microservice folder (or key files)
- Any specific requirements file

---

## 🎤 Phase 3: AI Scribe with Smart Validation

### The Challenge:
- Doctors shouldn't do "admin work"
- BUT validation is crucial for accuracy
- Need to balance automation with safety

### 🎯 Solution: Contextual In-Flow Validation

**Principle:** Validation happens AS PART of the consultation, not as extra work.

### Workflow Design:

```
┌─────────────────────────────────────────────────────────────┐
│           AI Scribe with Smart Validation                    │
└─────────────────────────────────────────────────────────────┘

DURING Consultation:
1. Doctor clicks "Start Recording" 🎙️
2. AI listens and transcribes in real-time
3. Live transcript appears on screen
4. Doctor speaks naturally during examination
5. Patient leaves room

IMMEDIATE POST-CONSULTATION (30 seconds):
6. AI generates structured SOAP notes (happens while doctor walks patient out)
7. Doctor sits back down - notes are ready
8. Quick Review Screen appears:

   ┌───────────────────────────────────────────────────┐
   │  ✓ AI Generated Notes - Quick Review              │
   ├───────────────────────────────────────────────────┤
   │                                                    │
   │  Subjective: [Patient complains of headaches...] │
   │              ✏️ Edit if needed                    │
   │                                                    │
   │  Objective: [BP: 135/85, HR: 78, Temp: 36.8°C]  │
   │             ✏️ Edit if needed                     │
   │                                                    │
   │  Assessment: [Hypertension, probable migraine]    │
   │              ✏️ Edit if needed                    │
   │                                                    │
   │  Plan: [Prescribe: Lisinopril 10mg OD]          │
   │        ✏️ Edit if needed                          │
   │                                                    │
   │  ⚠️ CRITICAL ITEMS TO VERIFY:                     │
   │  □ Diagnosis correct?                             │
   │  □ Medication names correct?                      │
   │  □ Dosages correct?                               │
   │  □ Patient allergies considered?                  │
   │                                                    │
   │  [Edit Notes] [✓ Approve & Continue]             │
   └───────────────────────────────────────────────────┘

9. Doctor spends 30-60 seconds:
   - Scans notes (AI did 95% of work)
   - Clicks checkboxes for critical items
   - Edits anything incorrect
   - Clicks "Approve & Continue"

10. System proceeds to prescription generation
```

### Key Design Principles:

**✅ What Makes This NOT "Admin Work":**
1. **Timing:** Happens immediately, while fresh in mind (not end of day)
2. **Pre-filled:** 95% already done by AI
3. **Quick:** Takes 30-60 seconds (vs 5-10 minutes manual)
4. **Focused:** Only critical items need attention
5. **Smart:** AI flags low-confidence items for review
6. **Visual:** Clear highlights of what needs verification

**❌ What We Avoid:**
1. ❌ No typing lengthy notes
2. ❌ No "review later" pile-up
3. ❌ No separate validation session
4. ❌ No context switching
5. ❌ No interruption of workflow

### Smart Confidence-Based Validation:

```python
AI Confidence System:

High Confidence (>95%): ✓ Auto-approve, just show
Medium Confidence (85-95%): ⚠️ Highlight in yellow
Low Confidence (<85%): 🚨 Require explicit verification

Example:
┌─────────────────────────────────────────────────┐
│ Assessment:                                      │
│ ✓ Hypertension (98% confident)                 │
│ ⚠️ Type 2 Diabetes (87% confident) - Verify?   │
│ 🚨 [Unclear diagnosis] (45% confident)          │
│    Please specify: ___________                   │
└─────────────────────────────────────────────────┘
```

### Implementation Architecture:

```
Doctor speaks → OpenAI Whisper (speech-to-text)
                        ↓
                Raw transcript
                        ↓
        OpenAI GPT-4 with Medical Prompt
                        ↓
            Structured SOAP Notes + Confidence Scores
                        ↓
        Smart Review UI (only flagged items highlighted)
                        ↓
            Doctor approves (30 seconds)
                        ↓
                Save to EHR
```

### Technical Specs:

**OpenAI Whisper:**
- Real-time streaming transcription
- Medical terminology support
- Multi-accent handling (South African English)
- Cost: R0.06 per 10-minute consultation

**OpenAI GPT-4:**
- Structured output (SOAP format)
- ICD-10 code suggestion
- Medication name validation
- Confidence scoring per field
- Cost: R0.15 per consultation

**Total Cost: ~R0.21 per consultation** (Very affordable!)

### Safety Mechanisms:

1. **Critical Items Checklist:**
   - Diagnosis ✓
   - Medications ✓
   - Dosages ✓
   - Allergies considered ✓
   - Patient identity verified ✓

2. **Auto-Save Drafts:**
   - Every 30 seconds during transcription
   - Prevents data loss
   - Can resume if interrupted

3. **Audit Trail:**
   - Original transcript stored
   - AI-generated notes stored
   - Doctor edits tracked
   - Final approved version stored
   - Timestamps for everything

4. **Fallback:**
   - If AI fails → Manual notes interface
   - If confidence too low → Flag for doctor
   - If service down → Traditional EHR entry

### UI Mockup - Quick Review:

```
┌─────────────────────────────────────────────────────────────┐
│  📋 Consultation Summary for Sarah Johnson                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                              │
│  Duration: 12 minutes  |  Confidence: 94%  |  ⚠️ 2 items    │
│                                                              │
│  S - SUBJECTIVE                                   ✏️ Edit    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  Patient reports frequent headaches for past 2 weeks.        │
│  Worse in mornings. Denies vision changes or nausea.        │
│  Family history of hypertension.                             │
│                                                              │
│  O - OBJECTIVE                                    ✏️ Edit    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  Vitals: BP 135/85, HR 78, Temp 36.8°C, Weight 68.5kg      │
│  Physical exam: Alert and oriented. No focal deficits.      │
│  Cardiovascular: Regular rhythm, no murmurs.                 │
│                                                              │
│  A - ASSESSMENT                                   ✏️ Edit    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  1. Hypertension, Stage 1 (ICD-10: I10) ✓ 98%              │
│  2. ⚠️ Tension headache (ICD-10: G44.2) 87% - Verify?       │
│     □ Confirm diagnosis                                      │
│                                                              │
│  P - PLAN                                         ✏️ Edit    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  Medications:                                                │
│  • Lisinopril 10mg PO once daily ✓                          │
│  • Ibuprofen 400mg PRN for headaches ✓                      │
│                                                              │
│  Follow-up: 4 weeks for BP check                            │
│  Patient education: Low sodium diet, stress management       │
│                                                              │
│  ⚠️ VERIFICATION REQUIRED:                                   │
│  □ Diagnosis codes accurate?                                 │
│  □ No drug interactions with Lisinopril?                     │
│  □ Patient allergies checked? (⚠️ Penicillin allergy noted) │
│  □ Dosages appropriate for patient weight?                   │
│                                                              │
│  [✏️ Edit Full Notes]  [✓ Approve & Generate Prescription]  │
└─────────────────────────────────────────────────────────────┘

Time to review: ~45 seconds
Doctor action: Check boxes, click Approve
Result: Clean notes in EHR + Prescription ready
```

### ROI for Doctor:

**Traditional Manual Notes:**
- Time: 5-10 minutes per patient
- Typing while thinking
- Often incomplete
- Done after hours

**AI Scribe with Smart Validation:**
- Time: 30-60 seconds per patient
- Just verification
- Complete and structured
- Done immediately

**Time Saved:** 8-9 minutes per patient
**For 20 patients/day:** 2.5-3 hours saved!
**For 100 patients/week:** 12-15 hours saved!

---

## Next Steps:

### For LandingAI Integration:
Please provide:
1. Your microservice folder or key files
2. Sample JSON response structure
3. requirements.txt
4. Current port it runs on
5. Any environment variables needed

### For AI Scribe:
1. Should I proceed with OpenAI Whisper + GPT-4 approach?
2. Any specific medical terminology requirements?
3. Should we support multiple languages? (English, Afrikaans, Zulu?)
4. Do doctors have microphones on their tablets/computers?

### Timeline:
- **Analytics:** ✅ Done
- **LandingAI Integration:** 1-2 days (once I have your files)
- **AI Scribe:** 3-4 days (includes UI + validation flow)

Ready to proceed when you share the microservice files!

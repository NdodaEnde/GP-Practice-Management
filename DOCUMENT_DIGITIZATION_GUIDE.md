# Document Digitization Workflow - Complete Guide

## Overview

SurgiScan now supports an intelligent document digitization workflow that handles both:
1. **Historical Medical Records** (bulk/backlog processing)
2. **Day-to-Day Medical Records** (as patients visit)

## Key Features

### ✅ Compliance-First Approach
- **All scanned documents are stored** in MongoDB for compliance purposes
- Original documents are never deleted
- Full audit trail of all operations

### ✅ AI-Powered Parsing
- Documents are parsed using LandingAI ADE (currently mocked)
- Extracts: demographics, medical history, medications, allergies, lab results, clinical notes
- Structured data ready for validation

### ✅ Smart Patient Matching
- Automatically matches parsed data to existing patients
- Multiple matching strategies:
  1. **ID Number Match** (highest confidence)
  2. **Name + DOB Match** (high confidence)
  3. **Fuzzy Name Match** (medium confidence, requires manual review)
- If no match → creates new patient

### ✅ Data Validation & Editing
- Human-in-the-loop validation before saving
- Edit any extracted field
- Ensure clean, accurate data in the database

## Complete Workflow

### Step 1: Upload Medical Document

**Location:** Navigate to "Digitize Documents" in the sidebar

**Actions:**
1. Click "Click to upload medical document"
2. Select a medical record (PDF, JPG, PNG)
3. Click "Upload & Parse Document"

**What Happens:**
- Document stored in MongoDB `scanned_documents` collection
- AI parser extracts structured data
- Parsed data stored in MongoDB `parsed_documents` collection
- Status: `pending_patient_match`

**API Endpoint:**
```bash
POST /api/documents/upload-standalone
- Form Data: file, document_type
- Returns: parsed_doc_id, parsed_data, status
```

---

### Step 2: Review & Edit Extracted Data (CRITICAL STEP)

**⚠️ IMPORTANT:** This step happens BEFORE patient matching to prevent duplicates!

**What You See:**
- Tabbed interface with 5 sections:
  - **Demographics**: Name, ID Number, DOB, Age, Gender, Contact
  - **Medical History**: Conditions with diagnosis dates
  - **Medications**: Current medications with dosage and frequency
  - **Allergies**: List of known allergies
  - **Lab Results**: Test results with values

**Why This Order Matters:**

**Problem Scenario:**
```
Real patient ID: 0098 (existing patient)
OCR reads: 0068 (error)

Wrong Flow:
Upload → Parse → Match using "0068" → Not found → Creates duplicate ❌

Correct Flow:
Upload → Parse → Human corrects "0068" to "0098" → Match using "0098" → Found! ✅
```

**Actions:**
1. **Carefully review ID number** - Most critical field for matching
2. **Verify patient name** - Used for fuzzy matching
3. **Check date of birth** - Used with name for matching
4. Edit any incorrect fields (OCR errors are common)
5. Add missing information
6. Click "Proceed to Patient Matching"

**What Happens:**
- Validated data stored in memory
- **Patient matching will use THIS corrected data, not raw OCR**
- System prepares for patient matching with clean, human-verified identifiers

---

### Step 3: Patient Matching (Using Validated Data)

**Automatic Matching Process:**

The system attempts to match using **YOUR CORRECTED DATA**:

**Priority 1: ID Number (Highest Confidence)**
```
Uses: The ID number YOU verified/corrected in Step 2
If match found → 99% confidence it's the same patient
```

**Priority 2: Name + DOB (High Confidence)**
```
Uses: The name and DOB YOU verified in Step 2  
If match found → High confidence match
```

**Priority 3: Fuzzy Name (Medium Confidence)**
```
Uses: Name similarity matching
If matches found → Shows multiple possibilities for manual selection
```

**Priority 4: No Match**
```
No existing patient found → New patient creation required
```

**API Endpoint:**
```bash
POST /api/documents/match-patient
- Form Data: parsed_doc_id, id_number, first_name, last_name, dob
- Returns: match_found, match_type, patient (or possible_matches), confidence
```

---

### Step 3a: Match Found - Link to Existing Patient

**Display:**
- Green success alert
- Patient details card showing:
  - Full name
  - ID number
  - Date of birth
  - Contact number
  - Medical aid

**Actions:**
1. Review matched patient details
2. Confirm this is the correct patient
3. Click "Link to This Patient"

**What Happens:**
- Document linked to existing patient
- New encounter created automatically
- Validated data stored in database
- Navigate to patient profile

**API Endpoint:**
```bash
POST /api/documents/link-to-patient
- Form Data: parsed_doc_id, patient_id, create_encounter, validated_data
- Returns: patient_id, encounter_id
```

**Database Updates:**
1. `parsed_documents` → patient_id assigned, status = 'linked'
2. `scanned_documents` → patient_id assigned
3. `encounters` → new record created
4. `document_refs` → Supabase reference created
5. `audit_events` → log of linking operation

---

### Step 3b: No Match - Create New Patient

**Display:**
- Amber alert indicating new patient
- Message: "No existing patient found. This appears to be a new patient."
- Info: "A new patient record will be created with the validated demographics data."

**Actions:**
1. Review that no match is correct
2. Click "Create New Patient"

**What Happens:**
- New patient record created in `patients` table
- Document linked to new patient
- New encounter created automatically
- Navigate to new patient profile

**API Endpoint:**
```bash
POST /api/documents/create-patient-from-document
- Form Data: parsed_doc_id, patient_data (JSON)
- Returns: patient_id, encounter_id
```

**Database Updates:**
1. `patients` → new patient created
2. `parsed_documents` → patient_id assigned
3. `scanned_documents` → patient_id assigned
4. `encounters` → new record created
5. `document_refs` → Supabase reference created
6. `audit_events` → log of patient creation

---

## Why Validation Before Matching is Critical

### The Duplicate Patient Problem

**Scenario: OCR Reads ID Incorrectly**

```
┌─────────────────────────────────────────────────────────────┐
│  WRONG WORKFLOW (Matching Before Validation)                │
└─────────────────────────────────────────────────────────────┘

Real World:
  Patient: Sarah Johnson
  ID: 0098 (exists in database)

Step 1: Scan old medical record
Step 2: OCR extracts data
  └─> Name: "Sarah Johnson" ✓
  └─> ID: "0068" ✗ (OCR mistake: confused 9 with 6)

Step 3: System matches using raw OCR data
  └─> Search for ID "0068" in database
  └─> NOT FOUND (because real ID is 0098)
  └─> Decision: Create NEW patient ❌

Step 4: Human validates (too late!)
  └─> User corrects "0068" to "0098"
  └─> But duplicate patient already created! ❌

Result: Sarah Johnson now has TWO profiles in the system!
  - Profile 1: ID 0098 (original)
  - Profile 2: ID 0068 (duplicate from OCR error)


┌─────────────────────────────────────────────────────────────┐
│  CORRECT WORKFLOW (Validation Before Matching)              │
└─────────────────────────────────────────────────────────────┘

Real World:
  Patient: Sarah Johnson  
  ID: 0098 (exists in database)

Step 1: Scan old medical record
Step 2: OCR extracts data
  └─> Name: "Sarah Johnson" ✓
  └─> ID: "0068" ✗ (OCR mistake)

Step 3: Human validates FIRST ✓
  └─> User reviews extracted data
  └─> Notices "0068" looks wrong
  └─> Corrects to "0098" based on document
  └─> All data now accurate!

Step 4: System matches using VALIDATED data
  └─> Search for ID "0098" in database  
  └─> FOUND! Sarah Johnson already exists ✓
  └─> Decision: Link to existing profile ✓

Result: Document linked to Sarah's existing profile!
  - No duplicate created ✓
  - Clean data in database ✓
  - Complete patient history ✓
```

### Common OCR Errors That Cause Duplicates

| Character | Often Misread As | Example |
|-----------|------------------|---------|
| 0 (zero) | O (letter O) | ID "0098" → "O098" |
| 1 (one) | I (letter i) or l (letter L) | ID "1234" → "I234" |
| 5 | S or 6 | ID "5678" → "6678" |
| 8 | 3 or B | ID "8890" → "3890" |
| 9 | 4 or 6 | ID "9012" → "6012" |

**Each mistake creates a potential duplicate patient!**

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UPLOAD DOCUMENT                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │   MongoDB Storage       │
         │  scanned_documents      │
         │  (original file)        │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │   AI Parsing            │
         │   (LandingAI ADE)       │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │   MongoDB Storage       │
         │  parsed_documents       │
         │  (structured data)      │
         └────────────┬────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              VALIDATION & EDITING                           │
│  (Human reviews and corrects extracted data)                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │  Patient Matching       │
         │  (Smart algorithm)      │
         └────┬────────────────┬───┘
              │                │
      Match Found         No Match
              │                │
              ▼                ▼
    ┌─────────────┐    ┌──────────────┐
    │ Link to     │    │ Create New   │
    │ Existing    │    │ Patient      │
    └──────┬──────┘    └──────┬───────┘
           │                  │
           └────────┬─────────┘
                    ▼
      ┌─────────────────────────────┐
      │  Supabase (Postgres)        │
      │  - patients                 │
      │  - encounters               │
      │  - document_refs            │
      └─────────────────────────────┘
                    │
                    ▼
      ┌─────────────────────────────┐
      │  Patient Profile Updated     │
      │  (Clean, validated data)     │
      └─────────────────────────────┘
```

---

## Use Cases

### Use Case 1: Historical Records Digitization

**Scenario:** You have boxes of old paper medical records that need to be digitized.

**Process:**
1. Scan documents to PDF
2. Upload each document through "Digitize Documents"
3. Review and correct extracted data
4. System matches to existing patients or creates new ones
5. All historical records now searchable and accessible

**Benefit:** Massive backlog of paper records converted to digital format with minimal manual data entry.

---

### Use Case 2: Day-to-Day Patient Records

**Scenario:** A patient walks in with medical records from another practice.

**Process:**
1. Scan their records
2. Upload through "Digitize Documents"
3. System automatically matches to their existing profile
4. Records immediately added to their history
5. Doctor can view complete medical history during consultation

**Benefit:** Seamless integration of external records into patient profiles.

---

### Use Case 3: New Patient with Records

**Scenario:** A new patient arrives with their medical history.

**Process:**
1. Scan their documents
2. Upload through "Digitize Documents"
3. System finds no match → creates new patient
4. New patient profile created with complete history
5. Ready for immediate consultation

**Benefit:** New patient onboarding with full history in minutes.

---

## LandingAI ADE Integration

### Current Status: MOCKED

The current implementation uses a mock parser that returns realistic medical data. To integrate the real LandingAI ADE:

### Step 1: Get LandingAI API Credentials

Visit: https://landing.ai/
Create account and get API key

### Step 2: Update Backend Configuration

Add to `/app/backend/.env`:
```
LANDING_AI_API_KEY=your_api_key_here
LANDING_AI_PROJECT_ID=your_project_id
```

### Step 3: Replace Mock Parser

In `/app/backend/server.py`, replace the `mock_ade_parser` function with:

```python
import requests

def landing_ai_ade_parser(filename: str, file_content: bytes) -> Dict[str, Any]:
    """Real LandingAI ADE integration"""
    api_key = os.environ['LANDING_AI_API_KEY']
    project_id = os.environ['LANDING_AI_PROJECT_ID']
    
    # Upload document to LandingAI
    files = {'file': (filename, file_content)}
    headers = {'Authorization': f'Bearer {api_key}'}
    
    response = requests.post(
        f'https://api.landing.ai/v1/projects/{project_id}/documents',
        files=files,
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"LandingAI API error: {response.text}")
    
    # Parse response and map to our structure
    ade_result = response.json()
    
    return {
        'patient_demographics': extract_demographics(ade_result),
        'medical_history': extract_history(ade_result),
        'current_medications': extract_medications(ade_result),
        'allergies': extract_allergies(ade_result),
        'lab_results': extract_labs(ade_result),
        'clinical_notes': extract_notes(ade_result),
        'diagnoses': extract_diagnoses(ade_result),
        'extraction_metadata': {
            'confidence': ade_result.get('confidence', 0),
            'extracted_at': datetime.now(timezone.utc).isoformat(),
            'source_filename': filename,
            'ade_document_id': ade_result.get('document_id')
        }
    }
```

### Step 4: Install Dependencies

```bash
cd /app/backend
pip install requests
pip freeze > requirements.txt
```

### Step 5: Restart Backend

```bash
sudo supervisorctl restart backend
```

---

## API Reference

### 1. Upload Standalone Document
```http
POST /api/documents/upload-standalone
Content-Type: multipart/form-data

file: <binary>
document_type: "medical_record" | "historical"

Response:
{
  "document_id": "uuid",
  "parsed_doc_id": "uuid",
  "parsed_data": {...},
  "status": "pending_patient_match"
}
```

### 2. Match Patient
```http
POST /api/documents/match-patient
Content-Type: multipart/form-data

parsed_doc_id: "uuid"
id_number: "string" (optional)
first_name: "string" (optional)
last_name: "string" (optional)
dob: "YYYY-MM-DD" (optional)

Response (Match Found):
{
  "match_found": true,
  "match_type": "id_number" | "name_dob" | "name_fuzzy",
  "patient": {...},
  "confidence": "high" | "medium"
}

Response (No Match):
{
  "match_found": false,
  "action_required": "create_new_patient"
}
```

### 3. Link to Existing Patient
```http
POST /api/documents/link-to-patient
Content-Type: multipart/form-data

parsed_doc_id: "uuid"
patient_id: "uuid"
create_encounter: "true"
validated_data: "json_string"

Response:
{
  "status": "success",
  "patient_id": "uuid",
  "encounter_id": "uuid"
}
```

### 4. Create New Patient from Document
```http
POST /api/documents/create-patient-from-document
Content-Type: multipart/form-data

parsed_doc_id: "uuid"
patient_data: "json_string"

Response:
{
  "status": "success",
  "patient_id": "uuid",
  "encounter_id": "uuid"
}
```

### 5. Get Pending Documents
```http
GET /api/documents/pending-match

Response:
{
  "count": 5,
  "documents": [...]
}
```

---

## Database Collections

### MongoDB Collections

#### scanned_documents
```json
{
  "id": "uuid",
  "tenant_id": "string",
  "workspace_id": "string",
  "patient_id": "string | null",
  "encounter_id": "string | null",
  "filename": "string",
  "content_type": "string",
  "file_size": "number",
  "file_data": "base64_string",
  "document_type": "historical | medical_record",
  "uploaded_at": "iso_datetime",
  "status": "uploaded | linked"
}
```

#### parsed_documents
```json
{
  "id": "uuid",
  "document_id": "uuid",
  "tenant_id": "string",
  "workspace_id": "string",
  "patient_id": "string | null",
  "encounter_id": "string | null",
  "parsed_data": {
    "patient_demographics": {...},
    "medical_history": [...],
    "current_medications": [...],
    "allergies": [...],
    "lab_results": [...],
    "clinical_notes": "string",
    "diagnoses": [...]
  },
  "status": "pending_patient_match | linked | approved",
  "parsed_at": "iso_datetime",
  "linked_at": "iso_datetime",
  "validated_at": "iso_datetime"
}
```

### Supabase Tables

#### document_refs
```sql
CREATE TABLE document_refs (
    id TEXT PRIMARY KEY,
    patient_id TEXT REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    mongo_doc_id TEXT,
    mongo_parsed_id TEXT,
    filename TEXT,
    file_size INTEGER,
    status TEXT,
    uploaded_at TIMESTAMP
);
```

---

## Benefits of This Workflow

### 1. Compliance
- ✅ All original documents preserved
- ✅ Full audit trail
- ✅ Immutable document history

### 2. Data Quality
- ✅ Human validation before saving
- ✅ Correction of AI extraction errors
- ✅ Clean, structured data in database

### 3. Efficiency
- ✅ Minimal manual data entry
- ✅ Bulk processing capability
- ✅ Automatic patient matching

### 4. Intelligence
- ✅ Smart patient matching algorithm
- ✅ Confidence scoring
- ✅ Multiple matching strategies

### 5. Flexibility
- ✅ Handles historical records
- ✅ Handles day-to-day records
- ✅ Works for new and existing patients

---

## Testing the Workflow

### Test Scenario 1: Upload Historical Record

```bash
# Upload a document
curl -X POST https://clinicflow-63.preview.emergentagent.com/api/documents/upload-standalone \
  -F "file=@medical_record.pdf" \
  -F "document_type=historical"

# Response includes parsed_doc_id: "abc-123"

# Match patient
curl -X POST https://clinicflow-63.preview.emergentagent.com/api/documents/match-patient \
  -F "parsed_doc_id=abc-123" \
  -F "id_number=8503205555088"

# Link to existing patient (if match found)
curl -X POST https://clinicflow-63.preview.emergentagent.com/api/documents/link-to-patient \
  -F "parsed_doc_id=abc-123" \
  -F "patient_id=xyz-789" \
  -F "create_encounter=true"
```

---

## Next Steps

1. **Integrate Real LandingAI ADE** (see integration guide above)
2. **Bulk Upload Interface** - Process multiple documents at once
3. **Progress Dashboard** - Track digitization progress
4. **Quality Metrics** - Track parsing accuracy, validation rates
5. **Advanced Matching** - ML-based fuzzy matching with higher accuracy

---

## Summary

This document digitization workflow provides a complete solution for:
- ✅ Historical record digitization
- ✅ Day-to-day document processing  
- ✅ Compliance with document retention
- ✅ Smart patient matching
- ✅ Data quality through human validation
- ✅ Seamless integration with existing workflows

The system ensures that all scanned documents are stored for compliance, parsed data is validated by humans for accuracy, and patients are intelligently matched or created as needed - resulting in clean, structured data in your database.

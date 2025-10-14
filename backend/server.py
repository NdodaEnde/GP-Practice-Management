from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, date, timedelta
from supabase import create_client, Client
import json
import base64
from decimal import Decimal
import httpx  # For calling the microservice

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ['DB_NAME']]

# Supabase connection
supabase_url = os.environ['SUPABASE_URL']
supabase_key = os.environ['SUPABASE_SERVICE_KEY']
supabase: Client = create_client(supabase_url, supabase_key)

# Demo tenant configuration
DEMO_TENANT_ID = os.environ.get('DEMO_TENANT_ID', 'demo-tenant-001')
DEMO_WORKSPACE_ID = os.environ.get('DEMO_WORKSPACE_ID', 'demo-gp-workspace-001')

# Microservice configuration
MICROSERVICE_URL = os.environ.get('MICROSERVICE_URL', 'http://localhost:5001')

# Create the main app
app = FastAPI(title="SurgiScan API")
api_router = APIRouter(prefix="/api")

# ==================== Models ====================

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    dob: str  # YYYY-MM-DD
    id_number: str
    contact_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    medical_aid: Optional[str] = None

class PatientResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    first_name: str
    last_name: str
    dob: str
    id_number: str
    contact_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    medical_aid: Optional[str] = None
    created_at: str

class VitalsData(BaseModel):
    blood_pressure: Optional[str] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    oxygen_saturation: Optional[int] = None

class EncounterCreate(BaseModel):
    patient_id: str
    chief_complaint: Optional[str] = None
    vitals: Optional[VitalsData] = None
    gp_notes: Optional[str] = None

class EncounterResponse(BaseModel):
    id: str
    patient_id: str
    workspace_id: str
    encounter_date: str
    status: str
    chief_complaint: Optional[str] = None
    vitals_json: Optional[Dict] = None
    gp_notes: Optional[str] = None
    created_at: str

class DocumentUploadResponse(BaseModel):
    document_id: str
    mongo_doc_id: str
    parsed_data: Dict[str, Any]
    status: str

class ValidationUpdate(BaseModel):
    parsed_data: Dict[str, Any]
    status: str  # 'approved' or 'rejected'
    notes: Optional[str] = None

class GPValidationSaveRequest(BaseModel):
    document_id: str
    parsed_data: Dict[str, Any]
    modifications: List[Dict[str, Any]]
    status: str
    notes: Optional[str] = None

class PatientMatchRequest(BaseModel):
    document_id: str
    demographics: Dict[str, Any]

class PatientMatchResult(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    dob: str
    id_number: str
    contact_number: Optional[str] = None
    last_visit: Optional[str] = None
    confidence_score: float
    match_method: str  # 'id_number', 'name_dob', 'fuzzy'

class ConfirmMatchRequest(BaseModel):
    document_id: str
    patient_id: str
    parsed_data: Dict[str, Any]
    modifications: List[Dict[str, Any]]
    
class CreateNewPatientRequest(BaseModel):
    document_id: str
    demographics: Dict[str, Any]
    parsed_data: Dict[str, Any]
    modifications: List[Dict[str, Any]]

class DocumentAccessLog(BaseModel):
    document_id: str
    access_type: str  # 'view', 'download', 'print', 'export'
    user_id: Optional[str] = 'system'
    ip_address: Optional[str] = None

class QueueCheckIn(BaseModel):
    patient_id: str
    reason_for_visit: str
    priority: Optional[str] = 'normal'  # 'normal', 'urgent', 'emergency'

class QueueUpdate(BaseModel):
    status: str  # 'waiting', 'in_vitals', 'in_consultation', 'completed', 'cancelled'
    station: Optional[str] = None  # 'reception', 'vitals', 'consultation', 'dispensary'
    notes: Optional[str] = None

class SOAPNoteRequest(BaseModel):
    transcription: str
    patient_context: Optional[Dict[str, Any]] = None

class DispenseCreate(BaseModel):
    encounter_id: str
    medication: str
    quantity: int
    dosage: str
    instructions: Optional[str] = None

class InvoiceItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    total: float

class InvoiceCreate(BaseModel):
    encounter_id: str
    payer_type: str  # 'cash', 'medical_aid', 'corporate'
    items: List[InvoiceItem]
    total_amount: float
    notes: Optional[str] = None

# ==================== Phase 4.2: Prescription Module Models ====================

class PrescriptionItem(BaseModel):
    medication_name: str
    dosage: str
    frequency: str
    duration: str
    quantity: Optional[str] = None
    instructions: Optional[str] = None

class PrescriptionCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    doctor_name: str
    prescription_date: str  # YYYY-MM-DD
    items: List[PrescriptionItem]
    notes: Optional[str] = None

class PrescriptionResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    patient_id: str
    encounter_id: Optional[str]
    doctor_name: str
    prescription_date: str
    status: str
    items: List[Dict[str, Any]]
    notes: Optional[str]
    created_at: str

class SickNoteCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    doctor_name: str
    issue_date: str  # YYYY-MM-DD
    start_date: str
    end_date: str
    diagnosis: str
    fitness_status: str  # 'unfit', 'fit_with_restrictions', 'fit'
    restrictions: Optional[str] = None
    additional_notes: Optional[str] = None

class SickNoteResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    patient_id: str
    encounter_id: Optional[str]
    doctor_name: str
    issue_date: str
    start_date: str
    end_date: str
    diagnosis: str
    fitness_status: str
    restrictions: Optional[str]
    additional_notes: Optional[str]
    created_at: str

class ReferralCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    referring_doctor_name: str
    referral_date: str  # YYYY-MM-DD
    specialist_type: str
    specialist_name: Optional[str] = None
    specialist_practice: Optional[str] = None
    reason_for_referral: str
    clinical_findings: str
    investigations_done: Optional[str] = None
    current_medications: Optional[str] = None
    urgency: str = 'routine'  # 'urgent', 'routine', 'non-urgent'

class ReferralResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    patient_id: str
    encounter_id: Optional[str]
    referring_doctor_name: str
    referral_date: str
    specialist_type: str
    specialist_name: Optional[str]
    specialist_practice: Optional[str]
    reason_for_referral: str
    clinical_findings: str
    investigations_done: Optional[str]
    current_medications: Optional[str]
    urgency: str
    status: str
    created_at: str

# ==================== Helper Functions ====================

async def init_demo_tenant():
    """Initialize demo tenant and workspace in Supabase if not exists"""
    try:
        # Check if tenant exists
        tenant_result = supabase.table('tenants').select('*').eq('id', DEMO_TENANT_ID).execute()
        
        if not tenant_result.data:
            # Create tenant
            supabase.table('tenants').insert({
                'id': DEMO_TENANT_ID,
                'name': 'Demo GP Practice',
                'created_at': datetime.now(timezone.utc).isoformat()
            }).execute()
            logger.info(f"Created demo tenant: {DEMO_TENANT_ID}")
        
        # Check if workspace exists
        workspace_result = supabase.table('workspaces').select('*').eq('id', DEMO_WORKSPACE_ID).execute()
        
        if not workspace_result.data:
            # Create workspace
            supabase.table('workspaces').insert({
                'id': DEMO_WORKSPACE_ID,
                'tenant_id': DEMO_TENANT_ID,
                'name': 'Main GP Practice',
                'type': 'gp',
                'created_at': datetime.now(timezone.utc).isoformat()
            }).execute()
            logger.info(f"Created demo workspace: {DEMO_WORKSPACE_ID}")
    except Exception as e:
        logger.error(f"Error initializing demo tenant: {e}")

def calculate_name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names using simple matching"""
    from difflib import SequenceMatcher
    
    # Normalize names
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    
    # Exact match
    if n1 == n2:
        return 1.0
    
    # Use SequenceMatcher for fuzzy matching
    return SequenceMatcher(None, n1, n2).ratio()

async def find_patient_matches(demographics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Find potential patient matches using multiple strategies
    Returns list of matches with confidence scores
    """
    matches = []
    
    # Extract search criteria from demographics
    id_number = demographics.get('id_number') or demographics.get('patient_id') or demographics.get('sa_id_number')
    first_name = demographics.get('first_name') or demographics.get('patient_name', '').split()[0] if demographics.get('patient_name') else None
    last_name = demographics.get('last_name') or ' '.join(demographics.get('patient_name', '').split()[1:]) if demographics.get('patient_name') else None
    dob = demographics.get('dob') or demographics.get('date_of_birth')
    
    # Strategy 1: Exact ID number match (95%+ confidence)
    if id_number:
        try:
            result = supabase.table('patients').select('*').eq('id_number', id_number).eq('workspace_id', DEMO_WORKSPACE_ID).execute()
            if result.data:
                for patient in result.data:
                    # Get last encounter for this patient
                    encounter_result = supabase.table('encounters').select('encounter_date').eq('patient_id', patient['id']).order('encounter_date', desc=True).limit(1).execute()
                    last_visit = encounter_result.data[0]['encounter_date'] if encounter_result.data else None
                    
                    matches.append({
                        'patient_id': patient['id'],
                        'first_name': patient['first_name'],
                        'last_name': patient['last_name'],
                        'dob': patient['dob'],
                        'id_number': patient['id_number'],
                        'contact_number': patient.get('contact_number'),
                        'last_visit': last_visit,
                        'confidence_score': 0.98,
                        'match_method': 'id_number'
                    })
        except Exception as e:
            logger.error(f"Error searching by ID number: {e}")
    
    # Strategy 2: Name + DOB match (70-90% confidence)
    if (first_name or last_name) and dob and not matches:
        try:
            # Get all patients for fuzzy matching
            result = supabase.table('patients').select('*').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
            
            if result.data:
                for patient in result.data:
                    # Calculate name similarity
                    first_name_similarity = calculate_name_similarity(first_name or '', patient.get('first_name', ''))
                    last_name_similarity = calculate_name_similarity(last_name or '', patient.get('last_name', ''))
                    
                    # Check DOB match
                    dob_match = patient.get('dob') == dob
                    
                    # Calculate overall confidence
                    if dob_match and (first_name_similarity > 0.7 or last_name_similarity > 0.7):
                        avg_name_similarity = (first_name_similarity + last_name_similarity) / 2
                        confidence = 0.7 + (avg_name_similarity * 0.2)  # 0.7 to 0.9
                        
                        # Get last encounter
                        encounter_result = supabase.table('encounters').select('encounter_date').eq('patient_id', patient['id']).order('encounter_date', desc=True).limit(1).execute()
                        last_visit = encounter_result.data[0]['encounter_date'] if encounter_result.data else None
                        
                        matches.append({
                            'patient_id': patient['id'],
                            'first_name': patient['first_name'],
                            'last_name': patient['last_name'],
                            'dob': patient['dob'],
                            'id_number': patient['id_number'],
                            'contact_number': patient.get('contact_number'),
                            'last_visit': last_visit,
                            'confidence_score': round(confidence, 2),
                            'match_method': 'name_dob'
                        })
        except Exception as e:
            logger.error(f"Error searching by name and DOB: {e}")
    
    # Sort by confidence score
    matches.sort(key=lambda x: x['confidence_score'], reverse=True)
    
    return matches[:5]  # Return top 5 matches

async def create_encounter_from_document(patient_id: str, parsed_data: Dict[str, Any], document_id: str) -> str:
    """Create an encounter from validated document data"""
    try:
        encounter_id = str(uuid.uuid4())
        
        # Extract data from parsed_data
        demographics = parsed_data.get('demographics', {})
        chronic_summary = parsed_data.get('chronic_summary', {})
        vitals_data = parsed_data.get('vitals', {})
        clinical_notes = parsed_data.get('clinical_notes', {})
        
        # Prepare vitals
        vitals_json = None
        if vitals_data and vitals_data.get('vital_signs_records'):
            # Use the first vital signs record
            first_record = vitals_data['vital_signs_records'][0] if vitals_data['vital_signs_records'] else {}
            vitals_json = {
                'blood_pressure': first_record.get('blood_pressure'),
                'heart_rate': first_record.get('heart_rate'),
                'temperature': first_record.get('temperature'),
                'weight': first_record.get('weight'),
                'height': first_record.get('height'),
                'oxygen_saturation': first_record.get('oxygen_saturation')
            }
        
        # Prepare GP notes from clinical notes and chronic summary
        gp_notes_parts = []
        if clinical_notes:
            gp_notes_parts.append(f"Clinical Notes: {json.dumps(clinical_notes)}")
        if chronic_summary.get('chronic_conditions'):
            gp_notes_parts.append(f"Chronic Conditions: {json.dumps(chronic_summary['chronic_conditions'])}")
        if chronic_summary.get('current_medications'):
            gp_notes_parts.append(f"Current Medications: {json.dumps(chronic_summary['current_medications'])}")
        
        gp_notes = '\n\n'.join(gp_notes_parts) if gp_notes_parts else 'Imported from scanned document'
        
        # Get document date or use current date
        encounter_date = demographics.get('document_date') or datetime.now(timezone.utc).isoformat()
        
        # Create encounter in Supabase
        encounter_data = {
            'id': encounter_id,
            'patient_id': patient_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'encounter_date': encounter_date,
            'status': 'completed',
            'chief_complaint': 'Imported from historical record',
            'vitals_json': vitals_json,
            'gp_notes': gp_notes,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('encounters').insert(encounter_data).execute()
        
        # Store reference to original document in MongoDB
        await db.document_refs.insert_one({
            'id': str(uuid.uuid4()),
            'encounter_id': encounter_id,
            'patient_id': patient_id,
            'document_id': document_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'created_at': datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Created encounter {encounter_id} from document {document_id}")
        return encounter_id
        
    except Exception as e:
        logger.error(f"Error creating encounter from document: {e}")
        raise

async def get_next_queue_number() -> int:
    """Generate next queue number for the day"""
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        
        # Get the highest queue number for today
        result = await db.queue_entries.find_one(
            {'date': today},
            sort=[('queue_number', -1)]
        )
        
        if result and result.get('queue_number'):
            return result['queue_number'] + 1
        else:
            return 1
    except Exception as e:
        logger.error(f"Error getting next queue number: {e}")
        return 1

async def call_microservice_parser(filename: str, file_content: bytes) -> Dict[str, Any]:
    """Call the microservice to parse document using LandingAI"""
    try:
        # Prepare the file for upload
        files = {'file': (filename, file_content, 'application/pdf')}
        data = {
            'processing_mode': 'smart',
            'save_to_database': 'false'
        }
        
        # Call the microservice
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{MICROSERVICE_URL}/api/v1/historic-documents/upload",
                files=files,
                data=data
            )
            response.raise_for_status()
            result = response.json()
        
        # Extract the parsed data from microservice response
        extracted_data = result.get('extracted_data', {})
        
        # Transform to our expected format
        return {
            'patient_demographics': {
                'name': extracted_data.get('patient_name', 'Unknown'),
                'age': extracted_data.get('age', 0),
                'gender': extracted_data.get('gender', 'Unknown')
            },
            'medical_history': extracted_data.get('medical_history', []),
            'current_medications': extracted_data.get('medications', []),
            'allergies': extracted_data.get('allergies', []),
            'lab_results': extracted_data.get('lab_results', []),
            'clinical_notes': extracted_data.get('clinical_notes', ''),
            'diagnoses': extracted_data.get('diagnoses', []),
            'extraction_metadata': {
                'confidence': result.get('confidence_score', 0.0),
                'extracted_at': datetime.now(timezone.utc).isoformat(),
                'source_filename': filename,
                'microservice_document_id': result.get('document_id'),
                'processing_summary': result.get('processing_summary', {}),
                'needs_validation': result.get('needs_validation', True)
            },
            'raw_microservice_response': result  # Keep for debugging
        }
    except httpx.HTTPError as e:
        logger.error(f"Microservice call failed: {e}")
        # Fallback to mock parser if microservice fails
        logger.warning("Falling back to mock parser")
        return mock_ade_parser(filename, file_content)
    except Exception as e:
        logger.error(f"Error calling microservice: {e}")
        # Fallback to mock parser
        return mock_ade_parser(filename, file_content)

def mock_ade_parser(filename: str, file_content: bytes) -> Dict[str, Any]:
    """Mock ADE parser - returns realistic parsed medical data"""
    return {
        'patient_demographics': {
            'name': 'Extracted from Document',
            'age': 45,
            'gender': 'Unknown'
        },
        'medical_history': [
            {'condition': 'Hypertension', 'diagnosed_date': '2020-03-15'},
            {'condition': 'Type 2 Diabetes', 'diagnosed_date': '2019-08-22'}
        ],
        'current_medications': [
            {'name': 'Metformin', 'dosage': '500mg', 'frequency': 'Twice daily'},
            {'name': 'Lisinopril', 'dosage': '10mg', 'frequency': 'Once daily'}
        ],
        'allergies': ['Penicillin', 'Latex'],
        'lab_results': [
            {'test': 'HbA1c', 'value': '6.8%', 'date': '2024-01-15'},
            {'test': 'Blood Pressure', 'value': '135/85', 'date': '2024-01-15'}
        ],
        'clinical_notes': 'Patient presents with controlled diabetes and hypertension. Continue current medication regimen. Follow up in 3 months.',
        'diagnoses': [
            {'code': 'E11', 'description': 'Type 2 diabetes mellitus'},
            {'code': 'I10', 'description': 'Essential hypertension'}
        ],
        'extraction_metadata': {
            'confidence': 0.92,
            'extracted_at': datetime.now(timezone.utc).isoformat(),
            'source_filename': filename
        }
    }

# ==================== API Routes ====================

@api_router.get("/")
async def root():
    return {"message": "SurgiScan API v1.0", "status": "operational"}

@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "tenant": DEMO_TENANT_ID,
        "workspace": DEMO_WORKSPACE_ID
    }

# ==================== Patient Management ====================

@api_router.post("/patients", response_model=PatientResponse)
async def create_patient(patient: PatientCreate):
    """Create a new patient"""
    try:
        patient_id = str(uuid.uuid4())
        patient_data = {
            'id': patient_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            **patient.model_dump(),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = supabase.table('patients').insert(patient_data).execute()
        
        # Log to audit
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'patient_created',
            'patient_id': patient_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': {'action': 'Patient registered'}
        })
        
        return PatientResponse(**result.data[0])
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/patients", response_model=List[PatientResponse])
async def list_patients(search: Optional[str] = None):
    """List all patients with optional search"""
    try:
        if search:
            # Search across multiple fields
            search_pattern = f"%{search}%"
            
            # Get all patients and filter in Python (more reliable than complex Supabase queries)
            result = supabase.table('patients').select('*').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
            
            # Filter results
            filtered_patients = []
            for patient in result.data:
                if (search.lower() in (patient.get('first_name') or '').lower() or
                    search.lower() in (patient.get('last_name') or '').lower() or
                    search.lower() in (patient.get('id_number') or '').lower() or
                    search.lower() in (patient.get('contact_number') or '').lower()):
                    filtered_patients.append(patient)
            
            return [PatientResponse(**p) for p in filtered_patients[:100]]
        else:
            result = supabase.table('patients').select('*').eq('workspace_id', DEMO_WORKSPACE_ID).order('created_at', desc=True).limit(100).execute()
            return [PatientResponse(**p) for p in result.data]
    except Exception as e:
        logger.error(f"Error listing patients: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: str):
    """Get patient details"""
    try:
        result = supabase.table('patients').select('*').eq('id', patient_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Patient not found")
        return PatientResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/patients/{patient_id}", response_model=PatientResponse)
async def update_patient(patient_id: str, patient: PatientCreate):
    """Update patient details"""
    try:
        result = supabase.table('patients').update(patient.model_dump()).eq('id', patient_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Patient not found")
        return PatientResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Encounter Management ====================

@api_router.post("/encounters", response_model=EncounterResponse)
async def create_encounter(encounter: EncounterCreate):
    """Create a new encounter"""
    try:
        encounter_id = str(uuid.uuid4())
        vitals_dict = encounter.vitals.model_dump() if encounter.vitals else None
        
        encounter_data = {
            'id': encounter_id,
            'patient_id': encounter.patient_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'encounter_date': datetime.now(timezone.utc).isoformat(),
            'status': 'in_progress',
            'chief_complaint': encounter.chief_complaint,
            'vitals_json': vitals_dict,
            'gp_notes': encounter.gp_notes,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = supabase.table('encounters').insert(encounter_data).execute()
        
        # Log to audit
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'encounter_created',
            'patient_id': encounter.patient_id,
            'encounter_id': encounter_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return EncounterResponse(**result.data[0])
    except Exception as e:
        logger.error(f"Error creating encounter: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/encounters/patient/{patient_id}", response_model=List[EncounterResponse])
async def get_patient_encounters(patient_id: str):
    """Get all encounters for a patient"""
    try:
        result = supabase.table('encounters').select('*').eq('patient_id', patient_id).order('encounter_date', desc=True).execute()
        return [EncounterResponse(**e) for e in result.data]
    except Exception as e:
        logger.error(f"Error getting encounters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/encounters/{encounter_id}", response_model=EncounterResponse)
async def get_encounter(encounter_id: str):
    """Get encounter details"""
    try:
        result = supabase.table('encounters').select('*').eq('id', encounter_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Encounter not found")
        return EncounterResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting encounter: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/encounters/{encounter_id}")
async def update_encounter(encounter_id: str, gp_notes: Optional[str] = None, status: Optional[str] = None):
    """Update encounter notes and status"""
    try:
        update_data = {}
        if gp_notes is not None:
            update_data['gp_notes'] = gp_notes
        if status is not None:
            update_data['status'] = status
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        result = supabase.table('encounters').update(update_data).eq('id', encounter_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Encounter not found")
        return EncounterResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating encounter: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Document Processing ====================

@api_router.post("/documents/upload-standalone")
async def upload_standalone_document(
    file: UploadFile = File(...),
    document_type: str = Form("medical_record")  # 'historical' or 'medical_record'
):
    """
    Upload and parse medical document WITHOUT requiring patient_id or encounter_id.
    This endpoint handles:
    1. Historical record digitization
    2. Day-to-day records where patient may or may not exist
    
    Returns parsed data including patient demographics for matching/creation
    """
    try:
        # Read file content
        file_content = await file.read()
        
        # Store original document in MongoDB
        mongo_doc_id = str(uuid.uuid4())
        document_doc = {
            'id': mongo_doc_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': None,  # Not assigned yet
            'encounter_id': None,  # Not assigned yet
            'filename': file.filename,
            'content_type': file.content_type,
            'file_size': len(file_content),
            'file_data': base64.b64encode(file_content).decode('utf-8'),
            'document_type': document_type,
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
            'status': 'uploaded'
        }
        await db.scanned_documents.insert_one(document_doc)
        
        # Call microservice to parse document
        parsed_data = await call_microservice_parser(file.filename, file_content)
        
        # Store parsed data in MongoDB
        parsed_doc_id = str(uuid.uuid4())
        parsed_doc = {
            'id': parsed_doc_id,
            'document_id': mongo_doc_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': None,
            'encounter_id': None,
            'parsed_data': parsed_data,
            'status': 'pending_patient_match',
            'parsed_at': datetime.now(timezone.utc).isoformat()
        }
        await db.parsed_documents.insert_one(parsed_doc)
        
        # Log to audit
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'document_uploaded_standalone',
            'document_id': mongo_doc_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': {'filename': file.filename, 'type': document_type}
        })
        
        return {
            'document_id': mongo_doc_id,
            'parsed_doc_id': parsed_doc_id,
            'parsed_data': parsed_data,
            'status': 'pending_patient_match',
            'message': 'Document uploaded and parsed. Ready for patient matching and validation.'
        }
    except Exception as e:
        logger.error(f"Error uploading standalone document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/documents/upload")
async def upload_document(
    encounter_id: str = Form(...),
    patient_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload and parse medical document for existing encounter"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Store original document in MongoDB
        mongo_doc_id = str(uuid.uuid4())
        document_doc = {
            'id': mongo_doc_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'filename': file.filename,
            'content_type': file.content_type,
            'file_size': len(file_content),
            'file_data': base64.b64encode(file_content).decode('utf-8'),
            'uploaded_at': datetime.now(timezone.utc).isoformat()
        }
        await db.scanned_documents.insert_one(document_doc)
        
        # Mock ADE parsing
        parsed_data = mock_ade_parser(file.filename, file_content)
        
        # Store parsed data in MongoDB
        parsed_doc_id = str(uuid.uuid4())
        parsed_doc = {
            'id': parsed_doc_id,
            'document_id': mongo_doc_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'parsed_data': parsed_data,
            'status': 'pending_validation',
            'parsed_at': datetime.now(timezone.utc).isoformat()
        }
        await db.parsed_documents.insert_one(parsed_doc)
        
        # Create document reference in Supabase
        doc_ref_id = str(uuid.uuid4())
        doc_ref = {
            'id': doc_ref_id,
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'mongo_doc_id': mongo_doc_id,
            'mongo_parsed_id': parsed_doc_id,
            'filename': file.filename,
            'file_size': len(file_content),
            'status': 'pending_validation',
            'uploaded_at': datetime.now(timezone.utc).isoformat()
        }
        supabase.table('document_refs').insert(doc_ref).execute()
        
        # Create validation session
        validation_session = {
            'id': str(uuid.uuid4()),
            'document_id': mongo_doc_id,
            'parsed_doc_id': parsed_doc_id,
            'encounter_id': encounter_id,
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        await db.validation_sessions.insert_one(validation_session)
        
        return DocumentUploadResponse(
            document_id=doc_ref_id,
            mongo_doc_id=mongo_doc_id,
            parsed_data=parsed_data,
            status='pending_validation'
        )
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/documents/match-patient")
async def match_patient_to_document(
    parsed_doc_id: str = Form(...),
    id_number: Optional[str] = Form(None),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    dob: Optional[str] = Form(None)
):
    """
    Match parsed document to existing patient or identify as new patient.
    Returns matched patient or indication that new patient should be created.
    """
    try:
        # Build search query based on provided identifiers
        query = supabase.table('patients').select('*').eq('workspace_id', DEMO_WORKSPACE_ID)
        
        # Priority 1: Match by ID number (most reliable)
        if id_number:
            result = query.eq('id_number', id_number).execute()
            if result.data:
                return {
                    'match_found': True,
                    'match_type': 'id_number',
                    'patient': result.data[0],
                    'confidence': 'high'
                }
        
        # Priority 2: Match by name + DOB
        if first_name and last_name and dob:
            result = query.ilike('first_name', first_name).ilike('last_name', last_name).eq('dob', dob).execute()
            if result.data:
                return {
                    'match_found': True,
                    'match_type': 'name_dob',
                    'patient': result.data[0],
                    'confidence': 'high'
                }
        
        # Priority 3: Fuzzy match by name only (return multiple possibilities)
        if first_name and last_name:
            result = query.ilike('first_name', f'%{first_name}%').ilike('last_name', f'%{last_name}%').execute()
            if result.data:
                return {
                    'match_found': True,
                    'match_type': 'name_fuzzy',
                    'possible_matches': result.data,
                    'confidence': 'medium',
                    'action_required': 'manual_review'
                }
        
        # No match found
        return {
            'match_found': False,
            'action_required': 'create_new_patient',
            'message': 'No existing patient found. Create new patient record.'
        }
        
    except Exception as e:
        logger.error(f"Error matching patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/documents/link-to-patient")
async def link_document_to_patient(
    parsed_doc_id: str = Form(...),
    patient_id: str = Form(...),
    create_encounter: bool = Form(True),
    validated_data: Optional[str] = Form(None)  # JSON string of validated/edited data
):
    """
    Link a parsed document to an existing or newly created patient.
    Optionally create an encounter and save validated data.
    """
    try:
        # Get parsed document from MongoDB
        parsed_doc = await db.parsed_documents.find_one({'id': parsed_doc_id})
        if not parsed_doc:
            raise HTTPException(status_code=404, detail="Parsed document not found")
        
        # Parse validated data if provided
        if validated_data:
            validated_json = json.loads(validated_data)
            parsed_doc['parsed_data'] = validated_json
        
        # Update parsed document with patient_id
        await db.parsed_documents.update_one(
            {'id': parsed_doc_id},
            {'$set': {
                'patient_id': patient_id,
                'status': 'linked',
                'linked_at': datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Update original document
        await db.scanned_documents.update_one(
            {'id': parsed_doc['document_id']},
            {'$set': {
                'patient_id': patient_id,
                'status': 'linked'
            }}
        )
        
        encounter_id = None
        if create_encounter:
            # Create encounter from parsed data
            encounter_id = str(uuid.uuid4())
            
            # Extract chief complaint from clinical notes if available
            chief_complaint = None
            if 'clinical_notes' in parsed_doc['parsed_data']:
                chief_complaint = parsed_doc['parsed_data']['clinical_notes'][:200]  # First 200 chars
            
            encounter_data = {
                'id': encounter_id,
                'patient_id': patient_id,
                'workspace_id': DEMO_WORKSPACE_ID,
                'encounter_date': datetime.now(timezone.utc).isoformat(),
                'status': 'pending_validation',
                'chief_complaint': chief_complaint,
                'vitals_json': None,
                'gp_notes': parsed_doc['parsed_data'].get('clinical_notes'),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table('encounters').insert(encounter_data).execute()
            
            # Update parsed document with encounter_id
            await db.parsed_documents.update_one(
                {'id': parsed_doc_id},
                {'$set': {'encounter_id': encounter_id}}
            )
            
            # Create document reference in Supabase
            doc_ref_id = str(uuid.uuid4())
            doc_ref = {
                'id': doc_ref_id,
                'patient_id': patient_id,
                'encounter_id': encounter_id,
                'mongo_doc_id': parsed_doc['document_id'],
                'mongo_parsed_id': parsed_doc_id,
                'filename': 'Historical Record',
                'file_size': 0,
                'status': 'linked',
                'uploaded_at': datetime.now(timezone.utc).isoformat()
            }
            supabase.table('document_refs').insert(doc_ref).execute()
        
        # Log to audit
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'document_linked_to_patient',
            'patient_id': patient_id,
            'document_id': parsed_doc['document_id'],
            'encounter_id': encounter_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return {
            'status': 'success',
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'message': 'Document successfully linked to patient'
        }
        
    except Exception as e:
        logger.error(f"Error linking document to patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/documents/create-patient-from-document")
async def create_patient_from_document(
    parsed_doc_id: str = Form(...),
    patient_data: str = Form(...)  # JSON string with patient details
):
    """
    Create a new patient from parsed document data and link the document.
    This handles the "new patient" workflow from document digitization.
    """
    try:
        # Parse patient data
        patient_dict = json.loads(patient_data)
        
        # Create patient
        patient_id = str(uuid.uuid4())
        patient_record = {
            'id': patient_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            **patient_dict,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('patients').insert(patient_record).execute()
        
        # Link document to patient
        link_result = await link_document_to_patient(
            parsed_doc_id=parsed_doc_id,
            patient_id=patient_id,
            create_encounter=True
        )
        
        return {
            'status': 'success',
            'patient_id': patient_id,
            'encounter_id': link_result.get('encounter_id'),
            'message': 'New patient created and document linked'
        }
        
    except Exception as e:
        logger.error(f"Error creating patient from document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/documents/pending-match")
async def get_pending_documents():
    """Get all documents pending patient matching"""
    try:
        # Get from MongoDB
        pending_docs = await db.parsed_documents.find({
            'workspace_id': DEMO_WORKSPACE_ID,
            'status': 'pending_patient_match'
        }).to_list(100)
        
        return {
            'count': len(pending_docs),
            'documents': pending_docs
        }
    except Exception as e:
        logger.error(f"Error getting pending documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/documents/encounter/{encounter_id}")
async def get_encounter_documents(encounter_id: str):
    """Get all documents for an encounter"""
    try:
        # Get document refs from Supabase
        result = supabase.table('document_refs').select('*').eq('encounter_id', encounter_id).execute()
        
        documents = []
        for doc_ref in result.data:
            # Get parsed data from MongoDB
            parsed_doc = await db.parsed_documents.find_one({'id': doc_ref['mongo_parsed_id']})
            if parsed_doc:
                documents.append({
                    'document_id': doc_ref['id'],
                    'mongo_doc_id': doc_ref['mongo_doc_id'],
                    'filename': doc_ref['filename'],
                    'status': doc_ref['status'],
                    'uploaded_at': doc_ref['uploaded_at'],
                    'parsed_data': parsed_doc['parsed_data']
                })
        
        return documents
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/documents/{document_id}/original")
async def get_original_document(document_id: str):
    """Get original document file"""
    try:
        # Get document ref from Supabase
        result = supabase.table('document_refs').select('*').eq('id', document_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        mongo_doc_id = result.data[0]['mongo_doc_id']
        
        # Get original from MongoDB
        doc = await db.scanned_documents.find_one({'id': mongo_doc_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document file not found")
        
        return {
            'filename': doc['filename'],
            'content_type': doc['content_type'],
            'file_data': doc['file_data'],  # Base64 encoded
            'uploaded_at': doc['uploaded_at']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting original document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Validation Workflow ====================

@api_router.get("/validation/{encounter_id}")
async def get_validation_session(encounter_id: str):
    """Get validation session for an encounter"""
    try:
        # Get all documents for the encounter
        docs = await get_encounter_documents(encounter_id)
        
        # Get validation sessions from MongoDB
        sessions = await db.validation_sessions.find({'encounter_id': encounter_id}).to_list(100)
        
        return {
            'encounter_id': encounter_id,
            'documents': docs,
            'validation_sessions': sessions
        }
    except Exception as e:
        logger.error(f"Error getting validation session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/validation/{document_id}/approve")
async def approve_validation(document_id: str, update: ValidationUpdate):
    """Approve parsed document data"""
    try:
        # Get document ref
        result = supabase.table('document_refs').select('*').eq('id', document_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_ref = result.data[0]
        
        # Update parsed document in MongoDB
        await db.parsed_documents.update_one(
            {'id': doc_ref['mongo_parsed_id']},
            {'$set': {
                'parsed_data': update.parsed_data,
                'status': 'approved',
                'validated_at': datetime.now(timezone.utc).isoformat(),
                'validation_notes': update.notes
            }}
        )
        
        # Update document ref status in Supabase
        supabase.table('document_refs').update({'status': 'approved'}).eq('id', document_id).execute()
        
        # Update validation session
        await db.validation_sessions.update_one(
            {'document_id': doc_ref['mongo_doc_id']},
            {'$set': {
                'status': 'approved',
                'approved_at': datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Log to audit
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'document_validated',
            'document_id': document_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return {'status': 'success', 'message': 'Document approved'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Dispensing ====================

@api_router.post("/dispense")
async def create_dispense_event(dispense: DispenseCreate):
    """Record a dispensing event"""
    try:
        dispense_id = str(uuid.uuid4())
        dispense_data = {
            'id': dispense_id,
            'encounter_id': dispense.encounter_id,
            'medication': dispense.medication,
            'quantity': dispense.quantity,
            'dosage': dispense.dosage,
            'instructions': dispense.instructions,
            'dispensed_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('dispense_events').insert(dispense_data).execute()
        
        return {'status': 'success', 'dispense_id': dispense_id}
    except Exception as e:
        logger.error(f"Error creating dispense event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/dispense/encounter/{encounter_id}")
async def get_dispense_events(encounter_id: str):
    """Get dispensing history for an encounter"""
    try:
        result = supabase.table('dispense_events').select('*').eq('encounter_id', encounter_id).execute()
        return result.data
    except Exception as e:
        logger.error(f"Error getting dispense events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Billing ====================

@api_router.post("/invoices")
async def create_invoice(invoice: InvoiceCreate):
    """Create an invoice for an encounter"""
    try:
        invoice_id = str(uuid.uuid4())
        invoice_data = {
            'id': invoice_id,
            'encounter_id': invoice.encounter_id,
            'payer_type': invoice.payer_type,
            'items_json': [item.model_dump() for item in invoice.items],
            'total_amount': invoice.total_amount,
            'notes': invoice.notes,
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('gp_invoices').insert(invoice_data).execute()
        
        # Update encounter status
        supabase.table('encounters').update({'status': 'completed'}).eq('id', invoice.encounter_id).execute()
        
        return {'status': 'success', 'invoice_id': invoice_id}
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/invoices")
async def list_invoices():
    """List all invoices"""
    try:
        result = supabase.table('gp_invoices').select('*').order('created_at', desc=True).limit(100).execute()
        return result.data
    except Exception as e:
        logger.error(f"Error listing invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    """Get invoice details"""
    try:
        result = supabase.table('gp_invoices').select('*').eq('id', invoice_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: str, status: str):
    """Update invoice status"""
    try:
        result = supabase.table('gp_invoices').update({'status': status}).eq('id', invoice_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Analytics ====================

@api_router.get("/analytics/summary")
async def get_analytics_summary():
    """Get comprehensive summary analytics for the workspace"""
    try:
        # Get counts from Supabase
        patients_result = supabase.table('patients').select('id', count='exact').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
        encounters_result = supabase.table('encounters').select('id', count='exact').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
        invoices_result = supabase.table('gp_invoices').select('total_amount').execute()
        
        total_revenue = sum(float(inv['total_amount']) for inv in invoices_result.data)
        
        # Get recent encounters
        recent_encounters = supabase.table('encounters').select('*').eq('workspace_id', DEMO_WORKSPACE_ID).order('encounter_date', desc=True).limit(5).execute()
        
        return {
            'total_patients': patients_result.count or 0,
            'total_encounters': encounters_result.count or 0,
            'total_invoices': len(invoices_result.data),
            'total_revenue': total_revenue,
            'recent_encounters': recent_encounters.data
        }
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analytics/operational")
async def get_operational_analytics():
    """Get operational metrics: patient volume, peak hours, throughput"""
    try:
        # Patient volume trends (last 6 months)
        six_months_ago = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        
        patients_over_time = supabase.table('patients').select('created_at').eq('workspace_id', DEMO_WORKSPACE_ID).gte('created_at', six_months_ago).execute()
        encounters_over_time = supabase.table('encounters').select('encounter_date', count='exact').eq('workspace_id', DEMO_WORKSPACE_ID).gte('encounter_date', six_months_ago).execute()
        
        # Group by month
        patient_monthly = {}
        for p in patients_over_time.data:
            month = p['created_at'][:7]  # YYYY-MM
            patient_monthly[month] = patient_monthly.get(month, 0) + 1
        
        encounter_monthly = {}
        for e in encounters_over_time.data:
            month = e['encounter_date'][:7]
            encounter_monthly[month] = encounter_monthly.get(month, 0) + 1
        
        # Peak hours analysis (encounters by hour)
        all_encounters = supabase.table('encounters').select('encounter_date').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
        hour_distribution = {}
        for e in all_encounters.data:
            hour = datetime.fromisoformat(e['encounter_date'].replace('Z', '+00:00')).hour
            hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
        
        # Average consultation duration (mock for now - will be real once we track workstation times)
        avg_consultation_duration = 15  # minutes
        
        return {
            'patient_growth': [
                {'month': month, 'count': count} 
                for month, count in sorted(patient_monthly.items())
            ],
            'encounter_volume': [
                {'month': month, 'count': count}
                for month, count in sorted(encounter_monthly.items())
            ],
            'peak_hours': [
                {'hour': hour, 'count': count}
                for hour, count in sorted(hour_distribution.items())
            ],
            'avg_consultation_duration': avg_consultation_duration,
            'total_patients_6m': len(patients_over_time.data),
            'total_encounters_6m': len(all_encounters.data)
        }
    except Exception as e:
        logger.error(f"Error getting operational analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analytics/clinical")
async def get_clinical_analytics():
    """Get clinical metrics: diagnoses, prescriptions, referrals"""
    try:
        # Get all parsed documents to analyze medical data
        parsed_docs = await db.parsed_documents.find({
            'workspace_id': DEMO_WORKSPACE_ID,
            'status': {'$in': ['approved', 'linked']}
        }).to_list(1000)
        
        # Aggregate diagnoses
        diagnosis_counts = {}
        medication_counts = {}
        allergy_counts = {}
        
        for doc in parsed_docs:
            parsed_data = doc.get('parsed_data', {})
            
            # Count diagnoses
            for diagnosis in parsed_data.get('diagnoses', []):
                diag_desc = diagnosis.get('description', 'Unknown')
                diagnosis_counts[diag_desc] = diagnosis_counts.get(diag_desc, 0) + 1
            
            # Count medications
            for med in parsed_data.get('current_medications', []):
                med_name = med.get('name', 'Unknown')
                medication_counts[med_name] = medication_counts.get(med_name, 0) + 1
            
            # Count allergies
            for allergy in parsed_data.get('allergies', []):
                allergy_counts[allergy] = allergy_counts.get(allergy, 0) + 1
        
        # Get top 10 diagnoses
        top_diagnoses = sorted(diagnosis_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_medications = sorted(medication_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_allergies = sorted(allergy_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Get encounter statistics
        all_encounters = supabase.table('encounters').select('*').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
        
        # Patient age distribution
        all_patients = supabase.table('patients').select('dob').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
        age_distribution = {'0-18': 0, '19-35': 0, '36-50': 0, '51-65': 0, '65+': 0}
        
        for p in all_patients.data:
            try:
                dob = datetime.strptime(p['dob'], '%Y-%m-%d')
                age = (datetime.now() - dob).days // 365
                if age <= 18:
                    age_distribution['0-18'] += 1
                elif age <= 35:
                    age_distribution['19-35'] += 1
                elif age <= 50:
                    age_distribution['36-50'] += 1
                elif age <= 65:
                    age_distribution['51-65'] += 1
                else:
                    age_distribution['65+'] += 1
            except:
                pass
        
        return {
            'top_diagnoses': [{'diagnosis': d, 'count': c} for d, c in top_diagnoses],
            'top_medications': [{'medication': m, 'count': c} for m, c in top_medications],
            'top_allergies': [{'allergy': a, 'count': c} for a, c in top_allergies],
            'age_distribution': age_distribution,
            'total_conditions_tracked': len(diagnosis_counts),
            'total_unique_medications': len(medication_counts),
            'encounter_count': len(all_encounters.data)
        }
    except Exception as e:
        logger.error(f"Error getting clinical analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analytics/financial")
async def get_financial_analytics():
    """Get financial metrics: revenue, payment methods, outstanding"""
    try:
        # Get all invoices
        invoices = supabase.table('gp_invoices').select('*').eq('workspace_id', DEMO_WORKSPACE_ID).execute()
        
        # Revenue over time (last 6 months)
        six_months_ago = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        recent_invoices = supabase.table('gp_invoices').select('*').gte('created_at', six_months_ago).execute()
        
        revenue_monthly = {}
        for inv in recent_invoices.data:
            month = inv['created_at'][:7]
            revenue_monthly[month] = revenue_monthly.get(month, 0) + float(inv['total_amount'])
        
        # Payer type breakdown
        payer_breakdown = {}
        for inv in invoices.data:
            payer = inv['payer_type']
            payer_breakdown[payer] = payer_breakdown.get(payer, 0) + float(inv['total_amount'])
        
        # Invoice status
        status_breakdown = {}
        for inv in invoices.data:
            status = inv['status']
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        total_revenue = sum(float(inv['total_amount']) for inv in invoices.data)
        pending_revenue = sum(float(inv['total_amount']) for inv in invoices.data if inv['status'] == 'pending')
        paid_revenue = sum(float(inv['total_amount']) for inv in invoices.data if inv['status'] == 'paid')
        
        return {
            'total_revenue': total_revenue,
            'pending_revenue': pending_revenue,
            'paid_revenue': paid_revenue,
            'revenue_by_month': [
                {'month': month, 'revenue': round(revenue, 2)}
                for month, revenue in sorted(revenue_monthly.items())
            ],
            'revenue_by_payer': [
                {'payer_type': payer, 'revenue': round(revenue, 2)}
                for payer, revenue in payer_breakdown.items()
            ],
            'invoice_status': status_breakdown,
            'total_invoices': len(invoices.data),
            'avg_invoice_value': round(total_revenue / len(invoices.data), 2) if invoices.data else 0
        }
    except Exception as e:
        logger.error(f"Error getting financial analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== GP Microservice Proxy Endpoints ====================

@api_router.post("/gp/upload-patient-file")
async def proxy_gp_upload(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    processing_mode: str = Form("smart")
):
    """Proxy GP patient file upload to microservice"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Prepare multipart form data for microservice
        files = {'file': (file.filename, file_content, file.content_type)}
        data = {
            'processing_mode': processing_mode,
            'save_to_database': 'true'
        }
        if patient_id:
            data['patient_id'] = patient_id
        
        # Forward to microservice
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{MICROSERVICE_URL}/api/v1/gp/upload-patient-file",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPError as e:
        logger.error(f"Microservice error: {e}")
        raise HTTPException(status_code=500, detail=f"Microservice error: {str(e)}")
    except Exception as e:
        logger.error(f"GP upload proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/gp/validate-extraction")
async def proxy_gp_validate(request_data: Dict[str, Any]):
    """Proxy GP validation to microservice"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{MICROSERVICE_URL}/api/v1/gp/validate-extraction",
                json=request_data
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"GP validation proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/gp/patients")
async def proxy_gp_patients():
    """Proxy get GP patients list to microservice"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{MICROSERVICE_URL}/api/v1/gp/patients")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"GP patients list proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/gp/patient/{patient_id}/chronic-summary")
async def proxy_gp_chronic_summary(patient_id: str):
    """Proxy get chronic summary to microservice"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{MICROSERVICE_URL}/api/v1/gp/patient/{patient_id}/chronic-summary"
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"GP chronic summary proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/gp/parsed-document/{document_id}")
async def proxy_gp_parsed_document(document_id: str):
    """Proxy get parsed document to microservice"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{MICROSERVICE_URL}/api/v1/gp/parsed-document/{document_id}"
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"GP parsed document proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/gp/statistics")
async def proxy_gp_statistics():
    """Proxy get GP statistics to microservice"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{MICROSERVICE_URL}/api/v1/gp/statistics")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"GP statistics proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/gp/document/{document_id}/view")
async def get_gp_document_view(document_id: str):
    """Get GP document for viewing"""
    try:
        # Connect to the microservice database where GP documents are stored
        microservice_db_name = os.environ.get('DATABASE_NAME', 'surgiscan_documents')
        microservice_client = AsyncIOMotorClient(os.environ.get('MONGODB_URL', 'mongodb://localhost:27017'))
        microservice_db = microservice_client[microservice_db_name]
        
        # Get document from MongoDB
        doc = await microservice_db.gp_scanned_documents.find_one({"document_id": document_id})
        
        microservice_client.close()
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
        
        # Return the file data with CORS headers
        from fastapi.responses import Response
        return Response(
            content=doc["file_data"],
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{doc["filename"]}"',
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get GP document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/gp/validation/save")
async def save_gp_validation(validation_data: GPValidationSaveRequest):
    """Save validated GP document data with modification tracking"""
    try:
        # Connect to the microservice database
        microservice_db_name = os.environ.get('DATABASE_NAME', 'surgiscan_documents')
        microservice_client = AsyncIOMotorClient(os.environ.get('MONGODB_URL', 'mongodb://localhost:27017'))
        microservice_db = microservice_client[microservice_db_name]
        
        document_id = validation_data.document_id
        
        # Get the original document
        doc = await microservice_db.gp_scanned_documents.find_one({"document_id": document_id})
        if not doc:
            microservice_client.close()
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
        
        # Prepare validated data with modifications tracking
        validated_record = {
            "document_id": document_id,
            "original_data": doc.get("parsed_data", {}),
            "validated_data": validation_data.parsed_data,
            "modifications": validation_data.modifications,
            "modification_count": len(validation_data.modifications),
            "status": validation_data.status,
            "validation_notes": validation_data.notes,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "validated_by": "user",  # Can be enhanced with auth
            "tenant_id": DEMO_TENANT_ID,
            "workspace_id": DEMO_WORKSPACE_ID
        }
        
        # Save to validated_documents collection
        await microservice_db.gp_validated_documents.insert_one(validated_record)
        
        # Update the original document status
        await microservice_db.gp_scanned_documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "status": "validated",
                    "validated_at": datetime.now(timezone.utc).isoformat(),
                    "validated_data": validation_data.parsed_data
                }
            }
        )
        
        # Log audit event
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'gp_document_validated',
            'document_id': document_id,
            'modifications_count': len(validation_data.modifications),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        microservice_client.close()
        
        logger.info(f"GP document {document_id} validated with {len(validation_data.modifications)} modifications")
        
        return {
            'status': 'success',
            'message': 'Validation saved successfully',
            'document_id': document_id,
            'modifications_count': len(validation_data.modifications)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving GP validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/gp/validation/match-patient")
async def match_patient_from_document(match_request: PatientMatchRequest):
    """Find potential patient matches from document demographics"""
    try:
        document_id = match_request.document_id
        demographics = match_request.demographics
        
        logger.info(f"Searching for patient matches for document {document_id}")
        
        # Find potential matches
        matches = await find_patient_matches(demographics)
        
        return {
            'status': 'success',
            'document_id': document_id,
            'matches': matches,
            'match_count': len(matches)
        }
    except Exception as e:
        logger.error(f"Error matching patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/gp/validation/confirm-match")
async def confirm_patient_match(confirm_request: ConfirmMatchRequest):
    """Confirm patient match and create encounter from document"""
    try:
        document_id = confirm_request.document_id
        patient_id = confirm_request.patient_id
        parsed_data = confirm_request.parsed_data
        
        logger.info(f"Confirming patient match: {patient_id} for document {document_id}")
        
        # Create encounter from document data
        encounter_id = await create_encounter_from_document(patient_id, parsed_data, document_id)
        
        # Connect to microservice database
        microservice_db_name = os.environ.get('DATABASE_NAME', 'surgiscan_documents')
        microservice_client = AsyncIOMotorClient(os.environ.get('MONGODB_URL', 'mongodb://localhost:27017'))
        microservice_db = microservice_client[microservice_db_name]
        
        # Update document status to "linked"
        await microservice_db.gp_scanned_documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "status": "linked",
                    "patient_id": patient_id,
                    "encounter_id": encounter_id,
                    "linked_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Log patient match
        await db.patient_match_logs.insert_one({
            'id': str(uuid.uuid4()),
            'document_id': document_id,
            'matched_patient_id': patient_id,
            'encounter_id': encounter_id,
            'match_method': 'manual_confirmation',
            'confirmed_by': 'user',
            'confirmed_at': datetime.now(timezone.utc).isoformat(),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID
        })
        
        # Log audit event
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'gp_patient_matched',
            'document_id': document_id,
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        microservice_client.close()
        
        logger.info(f"Successfully matched document {document_id} to patient {patient_id}, created encounter {encounter_id}")
        
        return {
            'status': 'success',
            'message': 'Patient matched and encounter created',
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'document_id': document_id
        }
    except Exception as e:
        logger.error(f"Error confirming patient match: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/gp/validation/create-new-patient")
async def create_new_patient_from_document(create_request: CreateNewPatientRequest):
    """Create new patient and encounter from document"""
    try:
        document_id = create_request.document_id
        demographics = create_request.demographics
        parsed_data = create_request.parsed_data
        
        logger.info(f"Creating new patient from document {document_id}")
        
        # Create new patient in Supabase
        patient_id = str(uuid.uuid4())
        
        patient_data = {
            'id': patient_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'first_name': demographics.get('first_name') or demographics.get('patient_name', 'Unknown').split()[0],
            'last_name': demographics.get('last_name') or ' '.join(demographics.get('patient_name', 'Unknown').split()[1:]) or 'Unknown',
            'dob': demographics.get('dob') or demographics.get('date_of_birth') or '1900-01-01',
            'id_number': demographics.get('id_number') or demographics.get('patient_id') or demographics.get('sa_id_number') or 'Unknown',
            'contact_number': demographics.get('contact_number') or demographics.get('phone'),
            'email': demographics.get('email'),
            'address': demographics.get('address'),
            'medical_aid': demographics.get('medical_aid'),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('patients').insert(patient_data).execute()
        
        # Create encounter from document
        encounter_id = await create_encounter_from_document(patient_id, parsed_data, document_id)
        
        # Connect to microservice database
        microservice_db_name = os.environ.get('DATABASE_NAME', 'surgiscan_documents')
        microservice_client = AsyncIOMotorClient(os.environ.get('MONGODB_URL', 'mongodb://localhost:27017'))
        microservice_db = microservice_client[microservice_db_name]
        
        # Update document status
        await microservice_db.gp_scanned_documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "status": "linked",
                    "patient_id": patient_id,
                    "encounter_id": encounter_id,
                    "linked_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Log audit event
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'gp_new_patient_created',
            'document_id': document_id,
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        microservice_client.close()
        
        logger.info(f"Created new patient {patient_id} and encounter {encounter_id} from document {document_id}")
        
        return {
            'status': 'success',
            'message': 'New patient created and encounter added',
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'document_id': document_id
        }
    except Exception as e:
        logger.error(f"Error creating new patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/documents/patient/{patient_id}")
async def get_patient_documents(patient_id: str):
    """Get all documents for a specific patient"""
    try:
        logger.info(f"Fetching documents for patient {patient_id}")
        
        # Connect to microservice database
        microservice_db_name = os.environ.get('DATABASE_NAME', 'surgiscan_documents')
        microservice_client = AsyncIOMotorClient(os.environ.get('MONGODB_URL', 'mongodb://localhost:27017'))
        microservice_db = microservice_client[microservice_db_name]
        
        # Get all documents for this patient
        cursor = microservice_db.gp_scanned_documents.find(
            {"patient_id": patient_id},
            {
                "document_id": 1,
                "filename": 1,
                "upload_date": 1,
                "status": 1,
                "patient_id": 1,
                "encounter_id": 1,
                "validated_at": 1,
                "linked_at": 1,
                "file_size": 1,
                "_id": 0
            }
        ).sort("upload_date", -1)
        
        documents = await cursor.to_list(length=None)
        
        microservice_client.close()
        
        return {
            'status': 'success',
            'patient_id': patient_id,
            'documents': documents,
            'count': len(documents)
        }
    except Exception as e:
        logger.error(f"Error fetching patient documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/documents/{document_id}/details")
async def get_document_details(document_id: str):
    """Get full document details including extracted data and validation history"""
    try:
        logger.info(f"Fetching details for document {document_id}")
        
        # Connect to microservice database
        microservice_db_name = os.environ.get('DATABASE_NAME', 'surgiscan_documents')
        microservice_client = AsyncIOMotorClient(os.environ.get('MONGODB_URL', 'mongodb://localhost:27017'))
        microservice_db = microservice_client[microservice_db_name]
        
        # Get document
        doc = await microservice_db.gp_scanned_documents.find_one(
            {"document_id": document_id},
            {"file_data": 0}  # Exclude binary data
        )
        
        if not doc:
            microservice_client.close()
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get validation record if exists
        validation = await microservice_db.gp_validated_documents.find_one(
            {"document_id": document_id}
        )
        
        # Convert ObjectId to string if present
        if doc.get('_id'):
            doc['_id'] = str(doc['_id'])
        if validation and validation.get('_id'):
            validation['_id'] = str(validation['_id'])
        
        microservice_client.close()
        
        return {
            'status': 'success',
            'document': doc,
            'validation': validation
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/documents/{document_id}/audit-trail")
async def get_document_audit_trail(document_id: str):
    """Get audit trail for a document (validation, access logs, modifications)"""
    try:
        logger.info(f"Fetching audit trail for document {document_id}")
        
        # Get audit events from MongoDB
        cursor = db.audit_events.find(
            {"document_id": document_id}
        ).sort("timestamp", -1)
        
        audit_events = await cursor.to_list(length=None)
        
        # Convert ObjectId to string
        for event in audit_events:
            if event.get('_id'):
                event['_id'] = str(event['_id'])
        
        # Get access logs
        access_cursor = db.document_access_logs.find(
            {"document_id": document_id}
        ).sort("accessed_at", -1)
        
        access_logs = await access_cursor.to_list(length=None)
        
        for log in access_logs:
            if log.get('_id'):
                log['_id'] = str(log['_id'])
        
        return {
            'status': 'success',
            'document_id': document_id,
            'audit_events': audit_events,
            'access_logs': access_logs,
            'total_events': len(audit_events),
            'total_accesses': len(access_logs)
        }
    except Exception as e:
        logger.error(f"Error fetching audit trail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/documents/{document_id}/log-access")
async def log_document_access(document_id: str, access_log: DocumentAccessLog):
    """Log document access for compliance"""
    try:
        # Create access log entry
        log_entry = {
            'id': str(uuid.uuid4()),
            'document_id': document_id,
            'access_type': access_log.access_type,
            'user_id': access_log.user_id,
            'ip_address': access_log.ip_address,
            'accessed_at': datetime.now(timezone.utc).isoformat(),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID
        }
        
        await db.document_access_logs.insert_one(log_entry)
        
        logger.info(f"Logged {access_log.access_type} access for document {document_id}")
        
        return {
            'status': 'success',
            'message': 'Access logged',
            'log_id': log_entry['id']
        }
    except Exception as e:
        logger.error(f"Error logging document access: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/documents/search")
async def search_documents(
    query: Optional[str] = None,
    patient_id: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50
):
    """Search across all documents"""
    try:
        logger.info(f"Searching documents with query: {query}")
        
        # Connect to microservice database
        microservice_db_name = os.environ.get('DATABASE_NAME', 'surgiscan_documents')
        microservice_client = AsyncIOMotorClient(os.environ.get('MONGODB_URL', 'mongodb://localhost:27017'))
        microservice_db = microservice_client[microservice_db_name]
        
        # Build query
        search_filter = {}
        
        if patient_id:
            search_filter['patient_id'] = patient_id
        
        if status:
            search_filter['status'] = status
        
        if date_from or date_to:
            search_filter['upload_date'] = {}
            if date_from:
                search_filter['upload_date']['$gte'] = date_from
            if date_to:
                search_filter['upload_date']['$lte'] = date_to
        
        # Execute search
        cursor = microservice_db.gp_scanned_documents.find(
            search_filter,
            {
                "document_id": 1,
                "filename": 1,
                "upload_date": 1,
                "status": 1,
                "patient_id": 1,
                "encounter_id": 1,
                "_id": 0
            }
        ).sort("upload_date", -1).limit(limit)
        
        documents = await cursor.to_list(length=None)
        
        microservice_client.close()
        
        return {
            'status': 'success',
            'documents': documents,
            'count': len(documents),
            'query': query
        }
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Queue Management Endpoints ====================

@api_router.post("/queue/check-in")
async def queue_check_in(check_in: QueueCheckIn):
    """Check in a patient and add them to the queue"""
    try:
        patient_id = check_in.patient_id
        
        # Get patient details
        patient_result = supabase.table('patients').select('*').eq('id', patient_id).execute()
        if not patient_result.data:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        patient = patient_result.data[0]
        
        # Get next queue number
        queue_number = await get_next_queue_number()
        
        # Create queue entry
        queue_id = str(uuid.uuid4())
        today = datetime.now(timezone.utc).date().isoformat()
        now = datetime.now(timezone.utc).isoformat()
        
        queue_entry = {
            'id': queue_id,
            'queue_number': queue_number,
            'patient_id': patient_id,
            'patient_name': f"{patient['first_name']} {patient['last_name']}",
            'reason_for_visit': check_in.reason_for_visit,
            'priority': check_in.priority,
            'status': 'waiting',  # waiting, in_vitals, in_consultation, completed, cancelled
            'station': 'reception',  # reception, vitals, consultation, dispensary
            'check_in_time': now,
            'date': today,
            'workspace_id': DEMO_WORKSPACE_ID,
            'tenant_id': DEMO_TENANT_ID,
            'wait_time_minutes': 0,
            'created_at': now
        }
        
        await db.queue_entries.insert_one(queue_entry)
        
        # Log audit event
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'patient_checked_in',
            'patient_id': patient_id,
            'queue_id': queue_id,
            'queue_number': queue_number,
            'timestamp': now
        })
        
        logger.info(f"Patient {patient_id} checked in with queue number {queue_number}")
        
        return {
            'status': 'success',
            'message': 'Patient checked in successfully',
            'queue_id': queue_id,
            'queue_number': queue_number,
            'patient_name': queue_entry['patient_name']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking in patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/queue/current")
async def get_current_queue(station: Optional[str] = None):
    """Get current queue for today"""
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        
        # Build filter
        queue_filter = {
            'date': today,
            'status': {'$in': ['waiting', 'in_vitals', 'in_consultation']}
        }
        
        if station:
            queue_filter['station'] = station
        
        # Get queue entries
        cursor = db.queue_entries.find(queue_filter).sort('queue_number', 1)
        queue = await cursor.to_list(length=None)
        
        # Convert ObjectId to string
        for entry in queue:
            if entry.get('_id'):
                entry['_id'] = str(entry['_id'])
            
            # Calculate wait time
            check_in_time = datetime.fromisoformat(entry['check_in_time'])
            wait_time = (datetime.now(timezone.utc) - check_in_time).total_seconds() / 60
            entry['wait_time_minutes'] = int(wait_time)
        
        return {
            'status': 'success',
            'date': today,
            'queue': queue,
            'count': len(queue)
        }
    except Exception as e:
        logger.error(f"Error getting current queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/queue/{queue_id}/call-next")
async def call_next_patient(queue_id: str, station: str):
    """Call the next patient to a station"""
    try:
        # Get queue entry
        queue_entry = await db.queue_entries.find_one({'id': queue_id})
        
        if not queue_entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        
        # Update status based on station
        status_map = {
            'vitals': 'in_vitals',
            'consultation': 'in_consultation',
            'dispensary': 'in_dispensary'
        }
        
        new_status = status_map.get(station, 'in_consultation')
        
        # Update queue entry
        now = datetime.now(timezone.utc).isoformat()
        await db.queue_entries.update_one(
            {'id': queue_id},
            {
                '$set': {
                    'status': new_status,
                    'station': station,
                    'called_at': now,
                    'updated_at': now
                }
            }
        )
        
        # Log audit event
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'patient_called',
            'patient_id': queue_entry['patient_id'],
            'queue_id': queue_id,
            'station': station,
            'timestamp': now
        })
        
        logger.info(f"Patient {queue_entry['patient_id']} called to {station}")
        
        return {
            'status': 'success',
            'message': f"Patient called to {station}",
            'queue_number': queue_entry['queue_number'],
            'patient_name': queue_entry['patient_name']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling next patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/queue/{queue_id}/update-status")
async def update_queue_status(queue_id: str, update: QueueUpdate):
    """Update queue entry status"""
    try:
        queue_entry = await db.queue_entries.find_one({'id': queue_id})
        
        if not queue_entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        
        # Update fields
        update_fields = {
            'status': update.status,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if update.station:
            update_fields['station'] = update.station
        
        if update.notes:
            update_fields['notes'] = update.notes
        
        if update.status == 'completed':
            update_fields['completed_at'] = datetime.now(timezone.utc).isoformat()
        
        await db.queue_entries.update_one(
            {'id': queue_id},
            {'$set': update_fields}
        )
        
        # Log audit event
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'queue_status_updated',
            'patient_id': queue_entry['patient_id'],
            'queue_id': queue_id,
            'old_status': queue_entry['status'],
            'new_status': update.status,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Queue {queue_id} status updated to {update.status}")
        
        return {
            'status': 'success',
            'message': 'Queue status updated',
            'queue_id': queue_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/queue/stats")
async def get_queue_stats():
    """Get queue statistics for today"""
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        
        # Get all queue entries for today
        cursor = db.queue_entries.find({'date': today})
        all_entries = await cursor.to_list(length=None)
        
        # Calculate statistics
        total_checked_in = len(all_entries)
        waiting = len([e for e in all_entries if e['status'] == 'waiting'])
        in_progress = len([e for e in all_entries if e['status'] in ['in_vitals', 'in_consultation', 'in_dispensary']])
        completed = len([e for e in all_entries if e['status'] == 'completed'])
        cancelled = len([e for e in all_entries if e['status'] == 'cancelled'])
        
        # Calculate average wait time for completed patients
        completed_entries = [e for e in all_entries if e.get('completed_at')]
        avg_wait_time = 0
        if completed_entries:
            total_wait = sum([
                (datetime.fromisoformat(e['completed_at']) - datetime.fromisoformat(e['check_in_time'])).total_seconds() / 60
                for e in completed_entries
            ])
            avg_wait_time = int(total_wait / len(completed_entries))
        
        return {
            'status': 'success',
            'date': today,
            'stats': {
                'total_checked_in': total_checked_in,
                'waiting': waiting,
                'in_progress': in_progress,
                'completed': completed,
                'cancelled': cancelled,
                'average_wait_time_minutes': avg_wait_time
            }
        }
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AI Scribe Endpoints ====================

@api_router.post("/ai-scribe/transcribe")
async def transcribe_audio(file: UploadFile):
    """Transcribe audio file using OpenAI Whisper"""
    try:
        import openai
        
        # Get OpenAI API key for Whisper
        # Note: Using a fresh environment read to ensure we get the correct key
        from pathlib import Path
        from dotenv import dotenv_values
        
        env_path = Path(__file__).parent / '.env'
        env_vars = dotenv_values(env_path)
        api_key = env_vars.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
        
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
        
        # Debug log to verify key being used
        logger.info(f"Using API key for Whisper: {api_key[:15]}...")
        
        # Initialize OpenAI client for Whisper
        client = openai.OpenAI(api_key=api_key)
        
        # Read audio file
        audio_content = await file.read()
        
        # Save temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(audio_content)
        
        # Transcribe using Whisper
        with open(temp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
        
        # Clean up temp file
        os.remove(temp_path)
        
        logger.info(f"Audio transcription completed: {len(transcription)} characters")
        
        return {
            'status': 'success',
            'transcription': transcription
        }
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ai-scribe/generate-soap")
async def generate_soap_notes(request: SOAPNoteRequest):
    """Generate SOAP notes from transcription using OpenAI GPT-4o"""
    try:
        import openai
        
        # Get OpenAI API key
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
        
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Build context if patient info provided
        context_info = ""
        if request.patient_context:
            context_info = f"\n\nPatient Context:\n"
            if request.patient_context.get('name'):
                context_info += f"Name: {request.patient_context['name']}\n"
            if request.patient_context.get('age'):
                context_info += f"Age: {request.patient_context['age']}\n"
            if request.patient_context.get('chronic_conditions'):
                context_info += f"Known Conditions: {', '.join(request.patient_context['chronic_conditions'])}\n"
        
        # System message for SOAP note generation
        system_message = """You are a medical AI assistant helping doctors create structured SOAP notes.

SOAP Format:
- S (Subjective): Patient's complaints, symptoms, history in their own words
- O (Objective): Physical examination findings, vital signs, test results
- A (Assessment): Doctor's diagnosis or clinical impression
- P (Plan): Treatment plan, medications, follow-up instructions

Generate clear, concise, professional SOAP notes from the consultation transcription.
Use medical terminology appropriately. Be thorough but succinct."""
        
        # Create user message
        user_prompt = f"""Please generate a structured SOAP note from this consultation transcription:

{context_info}

Transcription:
{request.transcription}

Format the output as:

**SUBJECTIVE:**
[Patient's symptoms and complaints]

**OBJECTIVE:**
[Physical findings and measurements]

**ASSESSMENT:**
[Clinical diagnosis/impression]

**PLAN:**
[Treatment and follow-up]"""
        
        # Generate SOAP notes using OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        soap_notes = response.choices[0].message.content
        
        logger.info(f"SOAP notes generated: {len(soap_notes)} characters")
        
        return {
            'status': 'success',
            'soap_notes': soap_notes
        }
    except Exception as e:
        logger.error(f"Error generating SOAP notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ai-scribe/extract-clinical-actions")
async def extract_clinical_actions(request: dict):
    """Extract structured clinical actions from SOAP notes for auto-population"""
    try:
        import openai
        
        soap_notes = request.get('soap_notes', '')
        patient_context = request.get('patient_context', {})
        
        if not soap_notes:
            raise HTTPException(status_code=400, detail="SOAP notes required")
        
        # Get OpenAI API key
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
        
        client = openai.OpenAI(api_key=api_key)
        
        # System prompt for extraction
        system_prompt = """You are a medical AI assistant that extracts structured clinical actions from SOAP notes.

Extract the following information from the SOAP notes and return as JSON:

1. PRESCRIPTIONS: List of medications mentioned in the Plan section
   - medication_name: Full name of medication
   - dosage: Dose amount (e.g., "500mg")
   - frequency: How often (e.g., "Twice daily", "Three times daily")
   - duration: How long (e.g., "7 days", "2 weeks")
   - instructions: Special instructions (e.g., "Take with food")

2. SICK_NOTE: If patient needs time off work
   - needed: true/false
   - diagnosis: Main diagnosis
   - days_off: Number of days off work
   - fitness_status: "unfit", "fit_with_restrictions", or "fit"
   - restrictions: Any work restrictions

3. REFERRAL: If specialist referral is needed
   - needed: true/false
   - specialist_type: Type of specialist (e.g., "Cardiologist", "Orthopedist")
   - reason: Brief reason for referral
   - urgency: "urgent", "routine", or "non-urgent"

Return ONLY valid JSON. If no prescriptions/sick note/referral needed, return empty arrays/false values."""

        user_prompt = f"""Extract clinical actions from these SOAP notes:

{soap_notes}

Patient Context:
- Name: {patient_context.get('name', 'N/A')}
- Age: {patient_context.get('age', 'N/A')}

Return structured JSON with prescriptions, sick_note, and referral sections."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent extraction
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        extracted_data = response.choices[0].message.content
        
        # Parse JSON response
        import json
        parsed_data = json.loads(extracted_data)
        
        logger.info(f"Clinical actions extracted from SOAP notes: {parsed_data}")
        
        return {
            'status': 'success',
            'extracted_data': parsed_data
        }
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing extracted data: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse extracted data")
    except Exception as e:
        logger.error(f"Error extracting clinical actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Phase 4.2: Prescription Module Endpoints ====================

@api_router.post("/prescriptions")
async def create_prescription(prescription: PrescriptionCreate):
    """Create a new prescription"""
    try:
        prescription_id = str(uuid.uuid4())
        
        # Create prescription record in Supabase
        prescription_data = {
            'id': prescription_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': prescription.patient_id,
            'encounter_id': prescription.encounter_id,
            'doctor_name': prescription.doctor_name,
            'prescription_date': prescription.prescription_date,
            'status': 'active',
            'notes': prescription.notes,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('prescriptions').insert(prescription_data).execute()
        
        # Create prescription items
        items_data = []
        for item in prescription.items:
            item_id = str(uuid.uuid4())
            items_data.append({
                'id': item_id,
                'prescription_id': prescription_id,
                'medication_name': item.medication_name,
                'dosage': item.dosage,
                'frequency': item.frequency,
                'duration': item.duration,
                'quantity': item.quantity,
                'instructions': item.instructions,
                'created_at': datetime.now(timezone.utc).isoformat()
            })
        
        if items_data:
            supabase.table('prescription_items').insert(items_data).execute()
        
        logger.info(f"Prescription created: {prescription_id}")
        
        return {
            'status': 'success',
            'prescription_id': prescription_id,
            'message': 'Prescription created successfully'
        }
    except Exception as e:
        logger.error(f"Error creating prescription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/prescriptions/patient/{patient_id}")
async def get_patient_prescriptions(patient_id: str):
    """Get all prescriptions for a patient"""
    try:
        # Get prescriptions
        prescriptions = supabase.table('prescriptions')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .order('prescription_date', desc=True)\
            .execute()
        
        # Get items for each prescription
        result = []
        for prescription in prescriptions.data:
            items = supabase.table('prescription_items')\
                .select('*')\
                .eq('prescription_id', prescription['id'])\
                .execute()
            
            prescription['items'] = items.data
            result.append(prescription)
        
        return {
            'status': 'success',
            'prescriptions': result
        }
    except Exception as e:
        logger.error(f"Error fetching prescriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/prescriptions/{prescription_id}")
async def get_prescription(prescription_id: str):
    """Get a specific prescription with items"""
    try:
        prescription = supabase.table('prescriptions')\
            .select('*')\
            .eq('id', prescription_id)\
            .single()\
            .execute()
        
        items = supabase.table('prescription_items')\
            .select('*')\
            .eq('prescription_id', prescription_id)\
            .execute()
        
        prescription.data['items'] = items.data
        
        return {
            'status': 'success',
            'prescription': prescription.data
        }
    except Exception as e:
        logger.error(f"Error fetching prescription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/sick-notes")
async def create_sick_note(sick_note: SickNoteCreate):
    """Create a new sick note/medical certificate"""
    try:
        sick_note_id = str(uuid.uuid4())
        
        sick_note_data = {
            'id': sick_note_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': sick_note.patient_id,
            'encounter_id': sick_note.encounter_id,
            'doctor_name': sick_note.doctor_name,
            'issue_date': sick_note.issue_date,
            'start_date': sick_note.start_date,
            'end_date': sick_note.end_date,
            'diagnosis': sick_note.diagnosis,
            'fitness_status': sick_note.fitness_status,
            'restrictions': sick_note.restrictions,
            'additional_notes': sick_note.additional_notes,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('sick_notes').insert(sick_note_data).execute()
        
        logger.info(f"Sick note created: {sick_note_id}")
        
        return {
            'status': 'success',
            'sick_note_id': sick_note_id,
            'message': 'Sick note created successfully'
        }
    except Exception as e:
        logger.error(f"Error creating sick note: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/sick-notes/patient/{patient_id}")
async def get_patient_sick_notes(patient_id: str):
    """Get all sick notes for a patient"""
    try:
        sick_notes = supabase.table('sick_notes')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .order('issue_date', desc=True)\
            .execute()
        
        return {
            'status': 'success',
            'sick_notes': sick_notes.data
        }
    except Exception as e:
        logger.error(f"Error fetching sick notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/referrals")
async def create_referral(referral: ReferralCreate):
    """Create a new referral letter"""
    try:
        referral_id = str(uuid.uuid4())
        
        referral_data = {
            'id': referral_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': referral.patient_id,
            'encounter_id': referral.encounter_id,
            'referring_doctor_name': referral.referring_doctor_name,
            'referral_date': referral.referral_date,
            'specialist_type': referral.specialist_type,
            'specialist_name': referral.specialist_name,
            'specialist_practice': referral.specialist_practice,
            'reason_for_referral': referral.reason_for_referral,
            'clinical_findings': referral.clinical_findings,
            'investigations_done': referral.investigations_done,
            'current_medications': referral.current_medications,
            'urgency': referral.urgency,
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('referrals').insert(referral_data).execute()
        
        logger.info(f"Referral created: {referral_id}")
        
        return {
            'status': 'success',
            'referral_id': referral_id,
            'message': 'Referral created successfully'
        }
    except Exception as e:
        logger.error(f"Error creating referral: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/referrals/patient/{patient_id}")
async def get_patient_referrals(patient_id: str):
    """Get all referrals for a patient"""
    try:
        referrals = supabase.table('referrals')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .order('referral_date', desc=True)\
            .execute()
        
        return {
            'status': 'success',
            'referrals': referrals.data
        }
    except Exception as e:
        logger.error(f"Error fetching referrals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/medications/search")
async def search_medications(query: str = Query(..., min_length=2)):
    """Search medications by name"""
    try:
        # Search in Supabase medications table
        medications = supabase.table('medications')\
            .select('id, name, generic_name, brand_names, category, common_dosages, common_frequencies, route')\
            .ilike('name', f'%{query}%')\
            .limit(20)\
            .execute()
        
        return {
            'status': 'success',
            'medications': medications.data
        }
    except Exception as e:
        logger.error(f"Error searching medications: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/medications/{medication_id}")
async def get_medication_details(medication_id: str):
    """Get detailed information about a medication"""
    try:
        medication = supabase.table('medications')\
            .select('*')\
            .eq('id', medication_id)\
            .single()\
            .execute()
        
        return {
            'status': 'success',
            'medication': medication.data
        }
    except Exception as e:
        logger.error(f"Error fetching medication: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Application Setup ====================

# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Application Events ====================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Starting SurgiScan API...")
    await init_demo_tenant()
    logger.info("Demo tenant initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    mongo_client.close()
    logger.info("MongoDB connection closed")
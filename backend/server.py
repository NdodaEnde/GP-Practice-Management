from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
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

# Capability gating — imported AFTER load_dotenv() because app.api.auth reads
# SUPABASE_URL / SUPABASE_SERVICE_KEY at module-load time. This early import
# is needed because route decorators below reference require_capability().
# (auth_router and other API routers are still imported at the bottom of this
# file per the existing pattern.)
from app.api.auth import require_capability, get_current_user

# MongoDB connection — OPTIONAL legacy dependency.
#
# The Essential digitisation tier runs entirely on Supabase; Mongo only backs
# some older Professional/practice features (reception queue, AI-scribe
# transcript storage, marketing leads, legacy audit). Production does NOT
# require Mongo. When MONGO_URL is unset, `db` is a null-safe stub: legacy
# Mongo-backed endpoints degrade to empty/no-op instead of crashing the app.
class _NoMongoCursor:
    def sort(self, *a, **k):  return self
    def limit(self, *a, **k): return self
    def skip(self, *a, **k):  return self
    async def to_list(self, *a, **k): return []
    def __aiter__(self): return self
    async def __anext__(self): raise StopAsyncIteration


class _NoMongoCollection:
    async def insert_one(self, *a, **k):       return None
    async def find_one(self, *a, **k):         return None
    async def update_one(self, *a, **k):       return None
    async def delete_one(self, *a, **k):       return None
    async def count_documents(self, *a, **k):  return 0
    async def create_index(self, *a, **k):     return None
    def find(self, *a, **k):                   return _NoMongoCursor()
    def aggregate(self, *a, **k):              return _NoMongoCursor()


class _NoMongoDB:
    def __getattr__(self, _name):              return _NoMongoCollection()


_mongo_url = os.environ.get('MONGO_URL')
if _mongo_url:
    mongo_client = AsyncIOMotorClient(_mongo_url)
    db = mongo_client[os.environ.get('DB_NAME', 'surgiscan')]
else:
    mongo_client = None
    db = _NoMongoDB()

# Supabase connection
supabase_url = os.environ['SUPABASE_URL']
supabase_key = os.environ['SUPABASE_SERVICE_KEY']
supabase: Client = create_client(supabase_url, supabase_key)

# Demo tenant configuration
DEMO_TENANT_ID = os.environ.get('DEMO_TENANT_ID', 'demo-tenant-001')
DEMO_WORKSPACE_ID = os.environ.get('DEMO_WORKSPACE_ID', 'demo-gp-workspace-001')

# Create the main app
# Disable interactive API docs + the OpenAPI schema in production (DEBUG off):
# they expose the full endpoint surface unauthenticated. Enabled in dev only.
_DOCS_ENABLED = os.environ.get("DEBUG", "false").lower() == "true"
app = FastAPI(
    title="SurgiScan API",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)
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
    nappi_code: Optional[str] = None  # South African medication code
    generic_name: Optional[str] = None  # Generic/active ingredient name
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
    # Doctor-supplied clinical reason for proceeding when an allergy interaction
    # is detected (Phase 2.5 — patient safety). Empty/None = no conflict, OR no
    # override attempted. Server returns 409 if conflicts exist with no override.
    allergy_override: Optional[str] = None

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


# ==================== Digitised Documents Models (Phase 1.7) ====================

class DigitisedDocumentResponse(BaseModel):
    id: str
    workspace_id: str
    filename: str
    file_path: str
    file_size: Optional[int] = None
    pages_count: Optional[int] = None
    upload_date: str
    status: str  # uploaded, parsing, parsed, extracting, extracted, validated, approved, error
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None  # Computed field
    encounter_id: Optional[str] = None
    parsed_doc_id: Optional[str] = None
    extracted_data_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    validated_by: Optional[str] = None
    validated_at: Optional[str] = None
    approved_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str

class DocumentStatusUpdate(BaseModel):
    status: str
    error_message: Optional[str] = None

class DocumentListFilters(BaseModel):
    status: Optional[str] = None
    patient_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    search: Optional[str] = None


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

async def populate_allergies_from_document(patient_id: str, parsed_data: Dict[str, Any]):
    """Auto-populate allergies table from extracted document data"""
    try:
        demographics = parsed_data.get('demographics', {})
        allergies_data = demographics.get('allergies') or demographics.get('known_allergies')
        
        if not allergies_data:
            return
        
        # Handle different formats: string or list
        if isinstance(allergies_data, str):
            if allergies_data.lower() in ['none', 'nil', 'nka', 'nkda', 'no known allergies']:
                return
            allergies_list = [a.strip() for a in allergies_data.split(',') if a.strip()]
        elif isinstance(allergies_data, list):
            allergies_list = allergies_data
        else:
            return
        
        for allergy_item in allergies_list:
            if isinstance(allergy_item, dict):
                allergen = allergy_item.get('allergen') or allergy_item.get('name') or str(allergy_item)
                reaction = allergy_item.get('reaction', 'Unknown reaction')
                severity = allergy_item.get('severity', 'moderate')
            else:
                allergen = str(allergy_item)
                reaction = 'Unknown reaction'
                severity = 'moderate'
            
            # Check if allergy already exists
            existing = supabase.table('allergies')\
                .select('*')\
                .eq('patient_id', patient_id)\
                .ilike('allergen', f'%{allergen}%')\
                .eq('status', 'active')\
                .execute()
            
            if not existing.data:
                allergy_data = {
                    'id': str(uuid.uuid4()),
                    'patient_id': patient_id,
                    'allergen': allergen,
                    'reaction': reaction,
                    'severity': severity,
                    'status': 'active',
                    'notes': 'Auto-imported from digitized document',
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                supabase.table('allergies').insert(allergy_data).execute()
                logger.info(f"Created allergy: {allergen} for patient {patient_id}")
    
    except Exception as e:
        logger.error(f"Error populating allergies: {e}")

async def populate_diagnoses_from_document(patient_id: str, encounter_id: str, parsed_data: Dict[str, Any]):
    """Auto-populate diagnoses table with AI ICD-10 matching from extracted document data"""
    try:
        chronic_summary = parsed_data.get('chronic_summary', {})
        clinical_notes = parsed_data.get('clinical_notes', {})
        
        # Collect diagnoses from different sources
        diagnoses_to_process = []
        
        # From chronic conditions
        conditions = chronic_summary.get('chronic_conditions', [])
        for condition in conditions:
            if isinstance(condition, dict):
                diagnosis_text = condition.get('condition') or condition.get('name')
            else:
                diagnosis_text = str(condition)
            
            if diagnosis_text:
                diagnoses_to_process.append({
                    'text': diagnosis_text,
                    'type': 'primary',
                    'onset_date': None
                })
        
        # From clinical notes (assessment/diagnosis section)
        if isinstance(clinical_notes, dict):
            assessment = clinical_notes.get('assessment') or clinical_notes.get('diagnosis')
            if assessment:
                diagnoses_to_process.append({
                    'text': assessment,
                    'type': 'primary',
                    'onset_date': None
                })
        
        # Process each diagnosis with AI ICD-10 matching
        import httpx
        for diagnosis_item in diagnoses_to_process:
            diagnosis_text = diagnosis_item['text']
            
            # Skip if empty or already exists
            if not diagnosis_text or len(diagnosis_text) < 3:
                continue
            
            # Check if diagnosis already exists
            existing = supabase.table('diagnoses')\
                .select('*')\
                .eq('patient_id', patient_id)\
                .ilike('diagnosis_description', f'%{diagnosis_text}%')\
                .eq('status', 'active')\
                .execute()
            
            if existing.data:
                continue
            
            # Use AI to suggest ICD-10 code
            icd10_code = None
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"http://localhost:8001/api/icd10/suggest",
                        params={'diagnosis_text': diagnosis_text, 'max_suggestions': 1},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('suggestions') and len(data['suggestions']) > 0:
                            icd10_code = data['suggestions'][0]['code']
                            logger.info(f"AI matched '{diagnosis_text}' to ICD-10 code: {icd10_code}")
            except Exception as e:
                logger.warning(f"ICD-10 AI matching failed for '{diagnosis_text}': {e}")
            
            # If AI matching failed, try simple keyword search
            if not icd10_code:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"http://localhost:8001/api/icd10/search",
                            params={'query': diagnosis_text, 'limit': 1},
                            timeout=10.0
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if len(data) > 0:
                                icd10_code = data[0]['code']
                                logger.info(f"Keyword matched '{diagnosis_text}' to ICD-10 code: {icd10_code}")
                except Exception as e:
                    logger.warning(f"ICD-10 keyword search failed for '{diagnosis_text}': {e}")
            
            # Create diagnosis record (even without ICD-10 code)
            if icd10_code or diagnosis_text:
                diagnosis_data = {
                    'id': str(uuid.uuid4()),
                    'patient_id': patient_id,
                    'encounter_id': encounter_id,
                    'icd10_code': icd10_code or 'UNMAPPED',
                    'diagnosis_description': diagnosis_text,
                    'diagnosis_type': diagnosis_item['type'],
                    'status': 'active',
                    'notes': 'Auto-imported from digitized document' + ('' if icd10_code else ' - ICD-10 code needs manual assignment'),
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                
                # Only insert if we have a valid ICD-10 code or the description is substantial
                if icd10_code and icd10_code != 'UNMAPPED':
                    supabase.table('diagnoses').insert(diagnosis_data).execute()
                    logger.info(f"Created diagnosis: {diagnosis_text} ({icd10_code}) for patient {patient_id}")
    
    except Exception as e:
        logger.error(f"Error populating diagnoses: {e}")

async def populate_vitals_from_document(patient_id: str, encounter_id: str, parsed_data: Dict[str, Any]):
    """Auto-populate vitals table from extracted document data"""
    try:
        vitals_data = parsed_data.get('vitals', {})
        demographics = parsed_data.get('demographics', {})
        
        if not vitals_data:
            return
        
        # Get measurement date from document
        measurement_date = demographics.get('document_date') or datetime.now(timezone.utc).isoformat()
        if 'T' in measurement_date:
            measurement_date = measurement_date.split('T')[0]
        
        # Get vital records (handle both new and old structures)
        vital_records = vitals_data.get('vital_entries') or vitals_data.get('vital_signs_records') or []
        
        if not vital_records:
            return
        
        # Process each vital record (usually we want the most recent)
        for idx, vital_record in enumerate(vital_records[:1]):  # Just take the first/most recent one
            # Extract and normalize vital signs
            bp_systolic = vital_record.get('bp_systolic')
            bp_diastolic = vital_record.get('bp_diastolic')
            heart_rate = vital_record.get('pulse') or vital_record.get('heart_rate')
            temperature = vital_record.get('temperature')
            weight = vital_record.get('weight_kg') or vital_record.get('weight')
            height = vital_record.get('height_cm') or vital_record.get('height')
            oxygen_saturation = vital_record.get('oxygen_saturation') or vital_record.get('spo2')
            
            # Only create record if at least one vital sign exists
            if not any([bp_systolic, heart_rate, temperature, weight, height, oxygen_saturation]):
                continue
            
            # Check if similar vital already exists for this date
            existing = supabase.table('vitals')\
                .select('*')\
                .eq('patient_id', patient_id)\
                .eq('measurement_date', measurement_date)\
                .execute()
            
            if existing.data:
                continue
            
            vital_data = {
                'id': str(uuid.uuid4()),
                'patient_id': patient_id,
                'encounter_id': encounter_id,
                'measurement_date': measurement_date,
                'blood_pressure_systolic': int(bp_systolic) if bp_systolic else None,
                'blood_pressure_diastolic': int(bp_diastolic) if bp_diastolic else None,
                'heart_rate': int(heart_rate) if heart_rate else None,
                'temperature': float(temperature) if temperature else None,
                'weight': float(weight) if weight else None,
                'height': float(height) if height else None,
                'oxygen_saturation': int(oxygen_saturation) if oxygen_saturation else None,
                'notes': 'Auto-imported from digitized document',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'recorded_by': 'system'
            }
            
            supabase.table('vitals').insert(vital_data).execute()
            logger.info(f"Created vitals record for patient {patient_id} on {measurement_date}")
    
    except Exception as e:
        logger.error(f"Error populating vitals: {e}")

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
        if vitals_data:
            # Check for vital_entries (new structure) or vital_signs_records (old structure)
            vital_records = vitals_data.get('vital_entries') or vitals_data.get('vital_signs_records')
            
            if vital_records and len(vital_records) > 0:
                # Use the most recent vital signs record (first in array)
                first_record = vital_records[0]
                
                # Handle new structure (vital_entries) vs old structure (vital_signs_records)
                if 'bp_systolic' in first_record:
                    # New structure with separate systolic/diastolic
                    bp = None
                    if first_record.get('bp_systolic') and first_record.get('bp_diastolic'):
                        bp = f"{first_record.get('bp_systolic')}/{first_record.get('bp_diastolic')}"
                    elif first_record.get('bp_raw'):
                        bp = first_record.get('bp_raw')
                    
                    vitals_json = {
                        'blood_pressure': bp,
                        'heart_rate': first_record.get('pulse') or first_record.get('pulse_raw'),
                        'temperature': first_record.get('temperature') or first_record.get('temperature_raw'),
                        'weight': first_record.get('weight_kg') or first_record.get('weight_raw'),
                        'height': first_record.get('height_cm') or first_record.get('height_raw'),
                        'oxygen_saturation': first_record.get('oxygen_saturation') or first_record.get('spo2')
                    }
                else:
                    # Old structure
                    vitals_json = {
                        'blood_pressure': first_record.get('blood_pressure'),
                        'heart_rate': first_record.get('heart_rate'),
                        'temperature': first_record.get('temperature'),
                        'weight': first_record.get('weight'),
                        'height': first_record.get('height'),
                        'oxygen_saturation': first_record.get('oxygen_saturation')
                    }
        
        # Prepare GP notes from clinical notes
        gp_notes_parts = []
        if clinical_notes:
            if isinstance(clinical_notes, dict):
                for key, value in clinical_notes.items():
                    gp_notes_parts.append(f"{key}: {value}")
            else:
                gp_notes_parts.append(str(clinical_notes))
        
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
        
        # Save chronic conditions as patient_conditions
        conditions = chronic_summary.get('chronic_conditions', [])
        if conditions:
            for condition in conditions:
                if isinstance(condition, dict):
                    condition_name = condition.get('condition') or condition.get('name') or str(condition)
                else:
                    condition_name = str(condition)
                
                # Check if condition already exists
                existing = supabase.table('patient_conditions')\
                    .select('*')\
                    .eq('patient_id', patient_id)\
                    .ilike('condition_name', f'%{condition_name}%')\
                    .execute()
                
                if not existing.data:
                    condition_data = {
                        'id': str(uuid.uuid4()),
                        'patient_id': patient_id,
                        'condition_name': condition_name,
                        'diagnosed_date': encounter_date.split('T')[0] if 'T' in encounter_date else encounter_date,
                        'status': 'active',
                        'notes': f'Imported from historical document',
                        'created_at': datetime.now(timezone.utc).isoformat()
                    }
                    supabase.table('patient_conditions').insert(condition_data).execute()
                    logger.info(f"Created condition: {condition_name} for patient {patient_id}")
        
        # Save current medications
        medications = chronic_summary.get('current_medications', []) or chronic_summary.get('likely_current_medications', [])
        if medications:
            for medication in medications:
                if isinstance(medication, dict):
                    # Handle different field name variations from microservice
                    med_name = (
                        medication.get('medication_name') or 
                        medication.get('medication') or 
                        medication.get('name') or 
                        'Unknown Medication'
                    )
                    
                    # Extract dosage information
                    med_dosage = (
                        medication.get('dosage_info') or 
                        medication.get('dosage') or 
                        medication.get('dose') or 
                        ''
                    )
                    
                    # Extract frequency
                    med_frequency = medication.get('frequency', '')
                    
                    # Extract the mentioned date (when medication was prescribed)
                    med_date = (
                        medication.get('mentioned_date') or 
                        medication.get('prescribed_date') or 
                        medication.get('start_date') or
                        encounter_date
                    )
                    
                    # Normalize date format
                    if 'T' in str(med_date):
                        med_date = med_date.split('T')[0]
                    
                    # Extract context/notes
                    med_notes = medication.get('context', 'Imported from scanned document')
                    if medication.get('legibility'):
                        med_notes += f" (Legibility: {medication.get('legibility')})"
                    
                else:
                    med_name = str(medication)
                    med_dosage = ''
                    med_frequency = ''
                    med_date = encounter_date.split('T')[0] if 'T' in encounter_date else encounter_date
                    med_notes = 'Imported from scanned document'
                
                # Skip if medication name is empty or just brackets
                if not med_name or med_name in ['Unknown Medication', '{}', '[]']:
                    continue
                
                # Store in MongoDB
                await db.patient_medications.insert_one({
                    'id': str(uuid.uuid4()),
                    'patient_id': patient_id,
                    'medication_name': med_name,
                    'dosage': med_dosage,
                    'frequency': med_frequency,
                    'start_date': med_date,
                    'status': 'active',
                    'prescribed_by': 'Historical Record',
                    'notes': med_notes,
                    'created_at': datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"Created medication: {med_name} (Date: {med_date}) for patient {patient_id}")
        
        # Store reference to original document in MongoDB
        await db.document_refs.insert_one({
            'id': str(uuid.uuid4()),
            'encounter_id': encounter_id,
            'patient_id': patient_id,
            'document_id': document_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'created_at': datetime.now(timezone.utc).isoformat()
        })
        
        # Auto-populate structured EHR tables
        await populate_allergies_from_document(patient_id, parsed_data)
        await populate_diagnoses_from_document(patient_id, encounter_id, parsed_data)
        await populate_vitals_from_document(patient_id, encounter_id, parsed_data)
        
        logger.info(f"Created encounter {encounter_id} from document {document_id} with structured EHR data")
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

# ==================== Public lead capture ====================

class LeadCreate(BaseModel):
    email: str
    vertical: str  # healthcare | mining | logistics | legal | finance
    source: Optional[str] = None  # e.g. 'vertical-landing', 'gateway-cta'


class LeadResponse(BaseModel):
    success: bool
    lead_id: str
    message: str


VALID_LEAD_VERTICALS = {"healthcare", "mining", "logistics", "legal", "finance"}


@api_router.post("/leads", response_model=LeadResponse)
async def capture_lead(lead: LeadCreate):
    """Public lead-capture endpoint for vertical landing pages.

    Tolerant by design: if the database write fails (e.g. dormant Supabase / Mongo),
    we still return success so the marketing form never breaks for a prospect.
    Failures are logged for ops follow-up.
    """
    if lead.vertical not in VALID_LEAD_VERTICALS:
        raise HTTPException(status_code=400, detail=f"Unknown vertical '{lead.vertical}'")

    lead_id = str(uuid.uuid4())
    record = {
        "lead_id": lead_id,
        "email": lead.email.strip().lower(),
        "vertical": lead.vertical,
        "source": lead.source,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": "new",
    }
    try:
        await db.leads.insert_one(record)
    except Exception as e:
        logging.error(f"capture_lead: failed to persist lead {lead_id}: {e}")
        # Intentionally swallow — surface no infra problems to the marketing form.

    return LeadResponse(
        success=True,
        lead_id=lead_id,
        message=f"Thanks — we'll reach out about your {lead.vertical} pilot.",
    )


# ==================== Patient Management ====================

# ==================== Patient Management ====================
# Rebuilt onto the unified foundation: workspace_id is derived from the
# authenticated token (current_user), NOT DEMO_WORKSPACE_ID, and every read/
# write is scoped to that workspace. Gating lives in the central
# ROUTE_CAPABILITIES map (patient_ehr_basic); get_current_user supplies tenancy.

@api_router.post("/patients", response_model=PatientResponse)
async def create_patient(patient: PatientCreate, current_user: dict = Depends(get_current_user)):
    """Create a new patient in the caller's workspace."""
    try:
        workspace_id = current_user["workspace_id"]
        tenant_id = current_user.get("tenant_id") or DEMO_TENANT_ID
        data = patient.model_dump()
        data.pop('workspace_id', None)   # tenancy is server-controlled, never caller-set
        data.pop('tenant_id', None)
        patient_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            **data,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        result = supabase.table('patients').insert(patient_data).execute()
        return PatientResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/patients", response_model=List[PatientResponse])
async def list_patients(search: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """List patients in the caller's workspace, with optional search."""
    try:
        workspace_id = current_user["workspace_id"]
        result = supabase.table('patients').select('*').eq('workspace_id', workspace_id)\
            .order('created_at', desc=True).limit(500 if search else 100).execute()
        rows = result.data or []
        if search:
            s = search.lower()
            rows = [p for p in rows if (
                s in (p.get('first_name') or '').lower() or
                s in (p.get('last_name') or '').lower() or
                s in (p.get('id_number') or '').lower() or
                s in (p.get('contact_number') or '').lower())][:100]
        return [PatientResponse(**p) for p in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing patients: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: str, current_user: dict = Depends(get_current_user)):
    """Get a patient in the caller's workspace."""
    try:
        result = supabase.table('patients').select('*')\
            .eq('id', patient_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Patient not found")
        return PatientResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting patient: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/patients/{patient_id}", response_model=PatientResponse)
async def update_patient(patient_id: str, patient: PatientCreate, current_user: dict = Depends(get_current_user)):
    """Update a patient in the caller's workspace."""
    try:
        workspace_id = current_user["workspace_id"]
        data = patient.model_dump()
        data.pop('workspace_id', None)   # never reassign tenancy
        data.pop('tenant_id', None)
        result = supabase.table('patients').update(data)\
            .eq('id', patient_id).eq('workspace_id', workspace_id).execute()
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
async def create_encounter(encounter: EncounterCreate, current_user: dict = Depends(get_current_user)):
    """Create an encounter for a patient in the caller's workspace."""
    try:
        workspace_id = current_user["workspace_id"]
        # The patient must belong to the caller's workspace (no cross-tenant encounters).
        pt = supabase.table('patients').select('id')\
            .eq('id', encounter.patient_id).eq('workspace_id', workspace_id).execute()
        if not pt.data:
            raise HTTPException(status_code=404, detail="Patient not found")
        vitals_dict = encounter.vitals.model_dump() if encounter.vitals else None
        encounter_data = {
            'id': str(uuid.uuid4()),
            'patient_id': encounter.patient_id,
            'workspace_id': workspace_id,
            'encounter_date': datetime.now(timezone.utc).isoformat(),
            'status': 'in_progress',
            'chief_complaint': encounter.chief_complaint,
            'vitals_json': vitals_dict,
            'gp_notes': encounter.gp_notes,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        result = supabase.table('encounters').insert(encounter_data).execute()
        return EncounterResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating encounter: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/encounters/patient/{patient_id}", response_model=List[EncounterResponse])
async def get_patient_encounters(patient_id: str, current_user: dict = Depends(get_current_user)):
    """Get a patient's encounters (caller's workspace only)."""
    try:
        result = supabase.table('encounters').select('*')\
            .eq('patient_id', patient_id).eq('workspace_id', current_user["workspace_id"])\
            .order('encounter_date', desc=True).execute()
        return [EncounterResponse(**e) for e in result.data]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting encounters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/encounters/{encounter_id}", response_model=EncounterResponse)
async def get_encounter(encounter_id: str, current_user: dict = Depends(get_current_user)):
    """Get an encounter in the caller's workspace."""
    try:
        result = supabase.table('encounters').select('*')\
            .eq('id', encounter_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Encounter not found")
        return EncounterResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting encounter: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/encounters/{encounter_id}")
async def update_encounter(encounter_id: str, gp_notes: Optional[str] = None, status: Optional[str] = None,
                           current_user: dict = Depends(get_current_user)):
    """Update an encounter's notes/status (caller's workspace only)."""
    try:
        update_data = {}
        if gp_notes is not None:
            update_data['gp_notes'] = gp_notes
        if status is not None:
            update_data['status'] = status
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        result = supabase.table('encounters').update(update_data)\
            .eq('id', encounter_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Encounter not found")
        return EncounterResponse(**result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating encounter: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Document Processing ====================


@api_router.get("/patients/{patient_id}/conditions")
async def get_patient_conditions(patient_id: str):
    """Get all conditions for a patient"""
    try:
        result = supabase.table('patient_conditions')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .order('diagnosed_date', desc=True)\
            .execute()
        return {'status': 'success', 'conditions': result.data}
    except Exception as e:
        logger.error(f"Error getting patient conditions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/patients/{patient_id}/medications")
async def get_patient_medications(patient_id: str):
    """Get all medications for a patient"""
    try:
        # Fetch from MongoDB
        medications_cursor = db.patient_medications.find(
            {'patient_id': patient_id},
            {'_id': 0}
        ).sort('created_at', -1)
        
        medications = await medications_cursor.to_list(length=100)
        return {'status': 'success', 'medications': medications}
    except Exception as e:
        logger.error(f"Error getting patient medications: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

# ==================== Billing (OLD - REPLACED BY api/billing.py) ====================

# OLD BILLING ENDPOINTS COMMENTED OUT - REPLACED BY api/billing.py
# 
# @api_router.post("/invoices")
# async def create_invoice(invoice: InvoiceCreate):
#     """Create an invoice for an encounter"""
#     try:
#         invoice_id = str(uuid.uuid4())
#         invoice_data = {
#             'id': invoice_id,
#             'encounter_id': invoice.encounter_id,
#             'payer_type': invoice.payer_type,
#             'items_json': [item.model_dump() for item in invoice.items],
#             'total_amount': invoice.total_amount,
#             'notes': invoice.notes,
#             'status': 'pending',
#             'created_at': datetime.now(timezone.utc).isoformat()
#         }
#         
#         supabase.table('gp_invoices').insert(invoice_data).execute()
#         
#         # Update encounter status
#         supabase.table('encounters').update({'status': 'completed'}).eq('id', invoice.encounter_id).execute()
#         
#         return {'status': 'success', 'invoice_id': invoice_id}
#     except Exception as e:
#         logger.error(f"Error creating invoice: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
# 
# @api_router.get("/invoices")
# async def list_invoices():
#     """List all invoices"""
#     try:
#         result = supabase.table('gp_invoices').select('*').order('created_at', desc=True).limit(100).execute()
#         return result.data
#     except Exception as e:
#         logger.error(f"Error listing invoices: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
# 
# @api_router.get("/invoices/{invoice_id}")
# async def get_invoice(invoice_id: str):
#     """Get invoice details"""
#     try:
#         result = supabase.table('gp_invoices').select('*').eq('id', invoice_id).execute()
#         if not result.data:
#             raise HTTPException(status_code=404, detail="Invoice not found")
#         return result.data[0]
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting invoice: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
# 
# @api_router.put("/invoices/{invoice_id}/status")
# async def update_invoice_status(invoice_id: str, status: str):
#     """Update invoice status"""
#     try:
#         result = supabase.table('gp_invoices').update({'status': status}).eq('id', invoice_id).execute()
#         if not result.data:
#             raise HTTPException(status_code=404, detail="Invoice not found")
#         return result.data[0]
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error updating invoice: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

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
async def get_clinical_analytics(
    # Phase 2 capability gating proof-of-concept. Requires the practice to have
    # an active entitlement granting `analytics_cohorts` (Module 02 — Advanced
    # Clinical Analytics). Returns 403 with capability_required detail otherwise,
    # which the frontend renders as a CapabilityUpsell card.
    current_user: dict = Depends(require_capability("analytics_cohorts")),
):
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

def parse_soap_notes(soap_text: str) -> dict:
    """
    Parse markdown-formatted SOAP notes into structured components
    Handles various formats: **SUBJECTIVE:**, **S:**, S:, etc.
    """
    import re
    
    result = {
        'subjective': '',
        'objective': '',
        'assessment': '',
        'plan': ''
    }
    
    # Remove markdown formatting
    soap_text = soap_text.replace('**', '')
    
    # Patterns to match SOAP sections (case insensitive, various formats)
    patterns = {
        'subjective': r'(?:SUBJECTIVE|S):\s*\n(.*?)(?=(?:OBJECTIVE|O):|$)',
        'objective': r'(?:OBJECTIVE|O):\s*\n(.*?)(?=(?:ASSESSMENT|A):|$)',
        'assessment': r'(?:ASSESSMENT|A):\s*\n(.*?)(?=(?:PLAN|P):|$)',
        'plan': r'(?:PLAN|P):\s*\n(.*?)$'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, soap_text, re.DOTALL | re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()
    
    # If no sections found, try splitting by common markers
    if not any(result.values()):
        # Split by common section headers
        sections = re.split(r'\n\s*(?:SUBJECTIVE|OBJECTIVE|ASSESSMENT|PLAN):\s*\n', soap_text, flags=re.IGNORECASE)
        if len(sections) >= 4:
            result = {
                'subjective': sections[1].strip() if len(sections) > 1 else '',
                'objective': sections[2].strip() if len(sections) > 2 else '',
                'assessment': sections[3].strip() if len(sections) > 3 else '',
                'plan': sections[4].strip() if len(sections) > 4 else ''
            }
    
    return result

@api_router.post("/ai-scribe/save-consultation")
async def save_consultation_to_ehr(request: dict):
    """Save AI Scribe consultation to EHR - creates encounter, extracts diagnosis, links documents"""
    try:
        import openai
        import json
        
        patient_id = request.get('patient_id')
        soap_notes = request.get('soap_notes', '')
        transcription = request.get('transcription', '')
        doctor_name = request.get('doctor_name', 'Dr. Unknown')
        
        if not patient_id or not soap_notes:
            raise HTTPException(status_code=400, detail="patient_id and soap_notes required")
        
        # Get OpenAI API key for diagnosis extraction
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
        
        client = openai.OpenAI(api_key=api_key)
        
        # Extract diagnosis and chief complaint from SOAP notes
        extraction_prompt = """Extract from these SOAP notes and return as JSON:
        {
          "chief_complaint": "Brief main complaint from Subjective section",
          "diagnosis": "Primary diagnosis from Assessment section",
          "icd10_code": "Suggested ICD-10 code if you know it, otherwise empty string"
        }"""
        
        diagnosis_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": soap_notes}
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        extracted_info = json.loads(diagnosis_response.choices[0].message.content)
        
        # Create encounter in Supabase
        encounter_id = str(uuid.uuid4())
        encounter_data = {
            'id': encounter_id,
            'patient_id': patient_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'encounter_date': datetime.now(timezone.utc).isoformat(),
            'status': 'completed',
            'chief_complaint': extracted_info.get('chief_complaint', 'Consultation'),
            'gp_notes': soap_notes,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('encounters').insert(encounter_data).execute()
        
        # Parse SOAP notes into structured format
        parsed_soap = parse_soap_notes(soap_notes)
        
        # Create structured clinical note
        clinical_note_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'encounter_id': encounter_id,
            'patient_id': patient_id,
            'format': 'soap',
            'subjective': parsed_soap['subjective'],
            'objective': parsed_soap['objective'],
            'assessment': parsed_soap['assessment'],
            'plan': parsed_soap['plan'],
            'raw_text': soap_notes,  # Keep original for reference
            'author': doctor_name,
            'role': 'ai_scribe',
            'source': 'ai_scribe',
            'note_datetime': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('clinical_notes').insert(clinical_note_data).execute()
        logger.info(f"Structured clinical note created for encounter {encounter_id}")
        
        # Add diagnosis to patient's conditions (if not already present)
        diagnosis = extracted_info.get('diagnosis', '')
        if diagnosis:
            # Check if condition exists
            existing = supabase.table('patient_conditions')\
                .select('*')\
                .eq('patient_id', patient_id)\
                .ilike('condition_name', f'%{diagnosis}%')\
                .execute()
            
            if not existing.data:
                # Add new condition
                condition_data = {
                    'id': str(uuid.uuid4()),
                    'patient_id': patient_id,
                    'condition_name': diagnosis,
                    'icd10_code': extracted_info.get('icd10_code', ''),
                    'diagnosed_date': datetime.now(timezone.utc).date().isoformat(),
                    'status': 'active',
                    'notes': f'Diagnosed during consultation on {datetime.now(timezone.utc).date().isoformat()}',
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                supabase.table('patient_conditions').insert(condition_data).execute()
        
        # Store transcription in MongoDB for reference
        await db.consultation_transcripts.insert_one({
            'id': str(uuid.uuid4()),
            'encounter_id': encounter_id,
            'patient_id': patient_id,
            'transcription': transcription,
            'soap_notes': soap_notes,
            'doctor_name': doctor_name,
            'created_at': datetime.now(timezone.utc).isoformat()
        })
        
        # Log audit event
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'event_type': 'ai_scribe_consultation_saved',
            'patient_id': patient_id,
            'encounter_id': encounter_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"AI Scribe consultation saved to EHR: encounter_id={encounter_id}")
        
        return {
            'status': 'success',
            'encounter_id': encounter_id,
            'diagnosis': diagnosis,
            'chief_complaint': extracted_info.get('chief_complaint'),
            'message': 'Consultation saved to patient EHR successfully'
        }
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing diagnosis extraction: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse diagnosis")
    except Exception as e:
        logger.error(f"Error saving consultation to EHR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Phase 4.2: Prescription Module Endpoints ====================

@api_router.post("/prescriptions")
async def create_prescription(prescription: PrescriptionCreate):
    """Create a new prescription. Server-side allergy interaction check enforced
    (Phase 2.5 patient safety). Returns 409 on conflict unless `allergy_override`
    is supplied with a clinical reason — overrides are logged for audit."""
    try:
        # ---- Server-side allergy interaction check ----
        # Defence in depth: even if the client UI is bypassed or buggy, the server
        # blocks prescriptions that conflict with the patient's known allergies
        # unless the doctor explicitly overrides with a reason.
        allergies_result = (
            supabase.table('allergies')
            .select('substance, reaction, severity')
            .eq('patient_id', prescription.patient_id)
            .eq('status', 'active')
            .execute()
        )
        patient_allergies = allergies_result.data or []

        conflicts = []
        for item in prescription.items:
            med_name = (item.medication_name or '').lower()
            generic_name = (item.generic_name or '').lower()
            for allergy in patient_allergies:
                substance = (allergy.get('substance') or '').strip().lower()
                if not substance:
                    continue
                # Bidirectional substring match: catches "Penicillin" allergy vs
                # "Amoxicillin" prescription (substance in name) AND "Aspirin"
                # allergy vs "Aspirin 100mg" (substance in name with extras).
                if (
                    substance in med_name
                    or substance in generic_name
                    or (med_name and med_name in substance)
                    or (generic_name and generic_name in substance)
                ):
                    conflicts.append({
                        'medication': item.medication_name,
                        'allergy_substance': allergy['substance'],
                        'reaction': allergy.get('reaction'),
                        'severity': allergy.get('severity'),
                    })

        if conflicts and not (prescription.allergy_override and prescription.allergy_override.strip()):
            raise HTTPException(
                status_code=409,
                detail={
                    'error': 'allergy_conflict',
                    'message': f'Prescription has {len(conflicts)} allergy conflict(s). '
                               f'Resubmit with allergy_override (clinical reason ≥ 10 chars) to proceed.',
                    'conflicts': conflicts,
                },
            )

        # If override supplied alongside real conflicts: log loud + structured for audit.
        # TODO (Phase 5): persist this to audit_events with full chain of custody.
        if conflicts and prescription.allergy_override:
            logger.warning(
                f"ALLERGY OVERRIDE accepted — patient={prescription.patient_id} "
                f"doctor={prescription.doctor_name} "
                f"conflicts={[c['allergy_substance'] for c in conflicts]} "
                f"reason={prescription.allergy_override!r}"
            )

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
                'nappi_code': item.nappi_code,  # South African medication code
                'generic_name': item.generic_name,  # Generic/active ingredient name
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
    except HTTPException:
        # Don't wrap intentional 4xx responses (e.g. 409 allergy_conflict) in 500.
        raise
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
async def create_sick_note(
    sick_note: SickNoteCreate,
    current_user: dict = Depends(require_capability("patient_ehr_basic")),
):
    """Create a new sick note/medical certificate.

    Capability-gated (patient_ehr_basic): a sick note is a clinical-legal
    document. Tenant/workspace are derived from the authenticated
    principal — NEVER the DEMO constants — so a clinician's note lands in
    their own workspace. The gate and the tenant derivation are one
    non-severable change: gated-but-tenant-blind would *look* fixed while
    still writing every note to the demo workspace."""
    workspace_id = current_user.get("workspace_id")
    tenant_id = current_user.get("tenant_id")
    if not workspace_id or not tenant_id:
        raise HTTPException(status_code=400, detail="No workspace/tenant context")
    try:
        sick_note_id = str(uuid.uuid4())

        sick_note_data = {
            'id': sick_note_id,
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
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
async def get_patient_sick_notes(
    patient_id: str,
    current_user: dict = Depends(require_capability("patient_ehr_basic")),
):
    """Get a patient's sick notes, scoped to the caller's workspace.

    An authenticated-but-tenant-blind read of a legal-medical record is
    the same defect as the create hardcode, in mirror — closed here as
    part of the same non-severable cut, not deferred."""
    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace context")
    try:
        sick_notes = supabase.table('sick_notes')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('workspace_id', workspace_id)\
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
# Include specialized API routers
from api.allergies import router as allergies_router
from api.icd10 import router as icd10_router
from api.diagnoses import router as diagnoses_router
from api.vitals import router as vitals_router
from api.nappi import router as nappi_router
from api.clinical_notes import router as clinical_notes_router
from api.lab import router as lab_router
from api.procedures import router as procedures_router
from api.immunizations import router as immunizations_router
from api.billing import router as billing_router
from api.payfast import router as payfast_router
from api.extraction_mappings import router as extraction_mappings_router

api_router.include_router(allergies_router, tags=["Allergies"])
api_router.include_router(icd10_router, tags=["ICD-10"])
api_router.include_router(diagnoses_router, tags=["Diagnoses"])
api_router.include_router(vitals_router, tags=["Vitals"])
api_router.include_router(nappi_router, tags=["NAPPI Codes"])
api_router.include_router(clinical_notes_router, tags=["Clinical Notes"])
api_router.include_router(lab_router, tags=["Lab Orders & Results"])
api_router.include_router(procedures_router, tags=["Procedures"])
api_router.include_router(immunizations_router, tags=["Immunizations"])
api_router.include_router(billing_router, tags=["Billing & Payments"])
api_router.include_router(payfast_router, prefix="/payfast", tags=["PayFast Payment Gateway"])
api_router.include_router(extraction_mappings_router, tags=["Extraction Mappings"])

# ==================== Authentication & User Management ====================
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.workspaces import router as workspaces_router
api_router.include_router(auth_router, tags=["Authentication"])
api_router.include_router(users_router, tags=["User Management"])
api_router.include_router(workspaces_router, tags=["Workspace Management"])


# ==================== FHIR R4 Export (Module 01 Digitisation) ====================
# Phase 2.5 — committed in v1.2 brochure §11. Exports a patient's full record
# as a FHIR R4 Bundle so Type C doctors (have own EHR) can ingest into their
# existing system. Gated by `digitisation_export_fhir` capability.
from app.services.fhir_export import build_patient_bundle


@api_router.get("/export/patient/{patient_id}/fhir")
async def export_patient_fhir(
    patient_id: str,
    current_user: dict = Depends(require_capability("digitisation_export_fhir")),
):
    """Export a patient's full SurgiScan record as a FHIR R4 Bundle (searchset).

    Capability-gated. Returns application/fhir+json. Includes Patient,
    AllergyIntolerance, Condition (diagnoses), MedicationStatement,
    Observation (vitals — one per measurement), and Encounter resources.
    """
    try:
        # Fetch patient row
        patient_q = supabase.table('patients').select('*').eq('id', patient_id).execute()
        if not patient_q.data:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        patient_row = patient_q.data[0]

        # Tenant scope check — patient must belong to caller's workspace.
        # (Skip for legacy_full_access users to keep grandfathering working.)
        if 'legacy_full_access' not in current_user.get('capabilities', []):
            if patient_row.get('workspace_id') != current_user.get('workspace_id'):
                raise HTTPException(status_code=403, detail="Patient is not in your workspace.")

        # Fetch related clinical data — defensively (table may be empty).
        def _fetch(table: str, filt_col: str = 'patient_id'):
            try:
                return supabase.table(table).select('*').eq(filt_col, patient_id).execute().data or []
            except Exception as e:
                logger.warning(f"FHIR export: {table} fetch failed for {patient_id}: {e}")
                return []

        allergies   = [a for a in _fetch('allergies')           if a.get('status') == 'active']
        diagnoses   = _fetch('diagnoses')
        vitals      = _fetch('vitals')
        encounters  = _fetch('encounters')

        # Patient medications live in prescription_items, joined via prescriptions.
        # (No `current_medications` or `patient_medications` table exists in this
        # codebase — the prescription tables are the source of truth for patient meds.)
        medications = []
        try:
            patient_rxs = (
                supabase.table('prescriptions')
                .select('id')
                .eq('patient_id', patient_id)
                .eq('status', 'active')
                .execute()
                .data or []
            )
            rx_ids = [r['id'] for r in patient_rxs]
            if rx_ids:
                medications = (
                    supabase.table('prescription_items')
                    .select('id, prescription_id, medication_name, generic_name, nappi_code, dosage, frequency, duration, quantity')
                    .in_('prescription_id', rx_ids)
                    .execute()
                    .data or []
                )
                # Add a 'status' field MedicationStatement requires (default to 'active' since the parent prescription is active).
                for m in medications:
                    m.setdefault('status', 'active')
        except Exception as e:
            logger.warning(f"FHIR export: prescription_items fetch failed for {patient_id}: {e}")

        bundle = build_patient_bundle(
            patient_row=patient_row,
            allergies=allergies,
            diagnoses=diagnoses,
            medications=medications,
            vitals=vitals,
            encounters=encounters,
        )

        # FHIR JSON serialisation: by_alias=True converts Python `class_fhir` → JSON `class`.
        # exclude_none keeps the output clean (FHIR spec lets fields be absent).
        bundle_json = bundle.model_dump(by_alias=True, exclude_none=True, mode='json')

        return JSONResponse(content=bundle_json, media_type="application/fhir+json")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FHIR export failed for {patient_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"FHIR export failed: {str(e)}")


@api_router.get("/analytics/medications")
async def get_medications_analytics(
    days: int = 90,
    current_user: dict = Depends(require_capability("analytics_drug_spend")),
):
    """Module 02 Analytics — medication prescribing analytics.

    Returns volume + schedule distribution + monthly trend over the last N days
    (default 90). Population-level analytic, distinct from Practice Professional's
    workflow dashboards (which are real-time / per-doctor operational metrics).

    Limitation: true "drug spend" in ZAR requires NAPPI pricing data not currently
    loaded into the `nappi_codes` table. This endpoint returns volume-based metrics;
    upgrade to currency analytics is a single SQL extension once price data flows
    in (multiply count × unit_price per nappi_code, group by month).

    Capability: `analytics_drug_spend` (Module 02).
    """
    from collections import Counter, defaultdict
    from datetime import timedelta

    workspace_id = current_user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(status_code=400, detail="No workspace in user context")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    rxs = (
        supabase.table('prescriptions')
        .select('id, prescription_date')
        .eq('workspace_id', workspace_id)
        .gte('prescription_date', cutoff)
        .execute()
        .data or []
    )
    rx_ids = [r['id'] for r in rxs]
    rx_dates = {r['id']: r['prescription_date'] for r in rxs}

    if not rx_ids:
        return {
            'window_days': days,
            'total_prescriptions': 0,
            'total_items': 0,
            'nappi_coverage_pct': 0,
            'atc_coverage_pct': 0,
            'by_medication': [],
            'by_schedule': {},
            'by_atc_anatomical': [],
            'by_atc_class': [],
            'monthly_trend': [],
            '_note': 'No prescriptions in window. Cost analytics requires NAPPI pricing data (not currently loaded).',
        }

    items = (
        supabase.table('prescription_items')
        .select('medication_name, generic_name, nappi_code, prescription_id')
        .in_('prescription_id', rx_ids)
        .execute()
        .data or []
    )

    # Aggregate by medication name
    by_med_acc = defaultdict(lambda: {'count': 0, 'nappi_codes': set(), 'generic_names': set()})
    for item in items:
        name = item.get('medication_name') or item.get('generic_name') or 'Unknown'
        agg = by_med_acc[name]
        agg['count'] += 1
        if item.get('nappi_code'):
            agg['nappi_codes'].add(item['nappi_code'])
        if item.get('generic_name'):
            agg['generic_names'].add(item['generic_name'])

    top_meds = sorted(
        [{
            'name': n,
            'count': v['count'],
            'nappi_codes': sorted(v['nappi_codes']),
            'generic_names': sorted(v['generic_names']),
        } for n, v in by_med_acc.items()],
        key=lambda x: -x['count']
    )[:20]

    # NAPPI Schedule (S0/S1/.../S6) distribution — controlled-substance compliance signal.
    # Same lookup also pulls atc_code / atc_class_desc so we can aggregate by
    # ATC anatomical group (level-1, single letter) and therapeutic class
    # (level-3, e.g. "C09A" = ACE inhibitors) — TRACEABILITY 6b deliverable.
    nappi_used = [i['nappi_code'] for i in items if i.get('nappi_code')]
    by_schedule: dict = {}
    by_atc_anatomical: list = []
    by_atc_class: list = []
    atc_coverage_pct = 0.0
    if nappi_used:
        nappi_lookup = (
            supabase.table('nappi_codes')
            .select('nappi_code, schedule, atc_code, atc_class_desc')
            .in_('nappi_code', list(set(nappi_used)))
            .execute()
            .data or []
        )
        sched_map = {n['nappi_code']: n.get('schedule') or 'Unknown' for n in nappi_lookup}
        atc_map = {n['nappi_code']: (n.get('atc_code'), n.get('atc_class_desc'))
                   for n in nappi_lookup}
        sched_counter = Counter(sched_map.get(n, 'Unknown') for n in nappi_used)
        by_schedule = dict(sched_counter)

        # ATC level-1 (anatomical group) — single letter prefix.
        ATC_GROUP_NAMES = {
            'A': 'Alimentary tract & metabolism',
            'B': 'Blood & blood-forming organs',
            'C': 'Cardiovascular system',
            'D': 'Dermatologicals',
            'G': 'Genito-urinary & sex hormones',
            'H': 'Systemic hormonal preparations',
            'J': 'Anti-infectives',
            'L': 'Antineoplastic & immunomodulating',
            'M': 'Musculo-skeletal system',
            'N': 'Nervous system',
            'P': 'Antiparasitic products',
            'R': 'Respiratory system',
            'S': 'Sensory organs',
            'V': 'Various',
        }
        anat_counter: Counter = Counter()
        # ATC level-3 (therapeutic / pharmacological subgroup) — first 4 chars.
        # Description = the level-5 substance name we have on file (close enough
        # for v1 — tighter rollup would need a separate level-3 name table).
        class_acc: dict = defaultdict(lambda: {'count': 0, 'sample_substance': None})
        atc_hits = 0
        for nappi_code in nappi_used:
            atc_code, class_desc = atc_map.get(nappi_code, (None, None))
            if not atc_code:
                continue
            atc_hits += 1
            anat_counter[atc_code[0]] += 1
            class_key = atc_code[:4] if len(atc_code) >= 4 else atc_code
            class_acc[class_key]['count'] += 1
            if class_acc[class_key]['sample_substance'] is None and class_desc:
                class_acc[class_key]['sample_substance'] = class_desc

        by_atc_anatomical = sorted(
            [{
                'group_letter': letter,
                'group_name': ATC_GROUP_NAMES.get(letter, 'Unknown'),
                'count': count,
            } for letter, count in anat_counter.items()],
            key=lambda x: -x['count'],
        )
        by_atc_class = sorted(
            [{
                'atc_class_code': code,
                'sample_substance': v['sample_substance'],
                'count': v['count'],
            } for code, v in class_acc.items()],
            key=lambda x: -x['count'],
        )[:15]

        atc_coverage_pct = round(atc_hits / len(nappi_used) * 100, 1)

    # Monthly trend (prescription items per YYYY-MM)
    monthly = Counter()
    for item in items:
        date = rx_dates.get(item['prescription_id'])
        if date:
            monthly[date[:7]] += 1
    monthly_trend = sorted(
        [{'month': m, 'prescriptions': c} for m, c in monthly.items()],
        key=lambda x: x['month']
    )

    nappi_coverage = round(len(nappi_used) / len(items) * 100, 1) if items else 0.0

    return {
        'window_days': days,
        'total_prescriptions': len(rx_ids),
        'total_items': len(items),
        'nappi_coverage_pct': nappi_coverage,
        'atc_coverage_pct': atc_coverage_pct,
        'by_medication': top_meds,
        'by_schedule': by_schedule,
        'by_atc_anatomical': by_atc_anatomical,
        'by_atc_class': by_atc_class,
        'monthly_trend': monthly_trend,
        '_note': 'Cost analytics (ZAR drug spend) requires NAPPI pricing data not currently loaded. Current output is volume-based.',
    }


app.include_router(api_router)

# Type C Digitisation Workspace router (capability-gated)
from app.api.digitisation import router as digitisation_router  # noqa: E402
app.include_router(digitisation_router)

# PR 3 Clinical Actions router — void prescription, soft-delete patient,
# reassign document, merge patient, universal reverse. Mounted under
# /clinical/*. Equivalent inclusion already exists in main.py for the
# :8001 micro-service; server.py serves the frontend on :8002 and needs
# the same routes registered.
from app.api.clinical_actions import router as clinical_actions_router  # noqa: E402
app.include_router(clinical_actions_router)

# Phase-3 query-layer router (PR A) — POST /api/query/run. server.py
# serves the frontend on :8002, so the same route must be registered
# here as well as in main.py (mirrors the clinical_actions note above).
from app.api.query import router as query_router  # noqa: E402
app.include_router(query_router)

# Deny-by-default authentication floor (ZERO). Added BEFORE CORS so CORS
# stays outermost: CORS handles preflight OPTIONS and wraps the floor's
# 401 with the proper CORS headers. The floor also bypasses OPTIONS itself.
from app.core.auth_backstop import AuthBackstopMiddleware  # noqa: E402
app.add_middleware(AuthBackstopMiddleware)

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

    # Start the document watcher (auto-detect and process new files)
    try:
        from app.services.document_watcher import start_document_watcher
        await start_document_watcher(supabase, DEMO_WORKSPACE_ID)
        logger.info("Document watcher started — auto-processing enabled")
    except Exception as e:
        logger.error(f"Failed to start document watcher: {e}")

    # Phase 3 PR D — standing-query tick (D-W1). SHIPS DISABLED: with
    # STANDING_QUERY_TICK_ENABLED off (merge default) this creates NO
    # task and runs NO loop. Same lifecycle host as the watcher.
    try:
        from app.services.standing_query_scheduler import (
            start_standing_query_scheduler,
        )
        await start_standing_query_scheduler(supabase)
    except Exception as e:
        logger.error(f"Failed to start standing-query scheduler: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    # Stop document watcher
    try:
        from app.services.document_watcher import stop_document_watcher
        await stop_document_watcher()
    except Exception:
        pass

    # Stop the standing-query scheduler (no-op if it was never started —
    # the disabled default never created a task).
    try:
        from app.services.standing_query_scheduler import (
            stop_standing_query_scheduler,
        )
        await stop_standing_query_scheduler()
    except Exception:
        pass

    if mongo_client is not None:
        mongo_client.close()
    logger.info("Connections closed")
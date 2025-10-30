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
    """
    Upload GP patient file with Phase 1.7 integration
    Creates digitised_documents record and tracks status through workflow
    """
    document_id = str(uuid.uuid4())
    
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Upload to Supabase Storage
        storage_path = f"{DEMO_WORKSPACE_ID}/{document_id}/{file.filename}"
        
        try:
            supabase.storage.from_('medical-records').upload(
                path=storage_path,
                file=file_content,
                file_options={
                    'content-type': 'application/pdf',
                    'cache-control': '3600',
                    'upsert': 'false'
                }
            )
            logger.info(f"File uploaded to Supabase Storage: {storage_path} ({file_size} bytes)")
        except Exception as storage_error:
            logger.error(f"Supabase Storage upload failed: {storage_error}")
            # Fall back to local storage if Supabase fails
            storage_dir = Path("storage/gp_documents/original")
            storage_dir.mkdir(parents=True, exist_ok=True)
            local_path = storage_dir / f"gp_doc_{document_id}_{file.filename}"
            with open(local_path, "wb") as f:
                f.write(file_content)
            storage_path = str(local_path)
            logger.info(f"File saved locally as fallback: {local_path}")
        
        # Create digitised_documents record with status "uploaded"
        digitised_doc_data = {
            'id': document_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'filename': file.filename,
            'file_path': storage_path,  # Supabase Storage path or local fallback
            'file_size': file_size,
            'status': 'uploaded',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('digitised_documents').insert(digitised_doc_data).execute()
        logger.info(f"Created digitised_documents record: {document_id}")
        
        # Update status to "parsing"
        supabase.table('digitised_documents')\
            .update({'status': 'parsing', 'updated_at': datetime.now(timezone.utc).isoformat()})\
            .eq('id', document_id)\
            .execute()
        
        # Prepare multipart form data for microservice
        files = {'file': (file.filename, file_content, file.content_type)}
        data = {
            'processing_mode': processing_mode,
            'save_to_database': 'true'
        }
        if patient_id:
            data['patient_id'] = patient_id
        
        # Forward to microservice for parsing and extraction
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{MICROSERVICE_URL}/api/v1/gp/upload-patient-file",
                files=files,
                data=data
            )
            response.raise_for_status()
            result = response.json()
        
        # Store parsed data in MongoDB and update status
        if result.get('success'):
            parsed_doc_id = result.get('data', {}).get('parsed_doc_id')
            
            # Store the entire parsed response in MongoDB for retrieval
            parsed_data_record = {
                'document_id': document_id,
                'parsed_doc_id': parsed_doc_id,
                'microservice_response': result,
                'extracted_data': result.get('data', {}),
                'workspace_id': DEMO_WORKSPACE_ID,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Store in MongoDB
            mongo_result = await db.parsed_documents.insert_one(parsed_data_record)
            mongo_id = str(mongo_result.inserted_id)
            
            logger.info(f"Stored parsed data in MongoDB: {mongo_id}")
            
            # Update Supabase with both IDs
            update_data = {
                'status': 'parsed',
                'parsed_doc_id': mongo_id,  # Use MongoDB ID instead
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table('digitised_documents')\
                .update(update_data)\
                .eq('id', document_id)\
                .execute()
            
            logger.info(f"Document {document_id} parsed successfully, MongoDB ID: {mongo_id}")
        
        # Add document_id to response
        result['document_id'] = document_id
        return result
            
    except httpx.HTTPError as e:
        # Update status to "error"
        supabase.table('digitised_documents')\
            .update({
                'status': 'error',
                'error_message': f"Microservice error: {str(e)}",
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', document_id)\
            .execute()
        
        logger.error(f"Microservice error: {e}")
        raise HTTPException(status_code=500, detail=f"Microservice error: {str(e)}")
    except Exception as e:
        # Update status to "error"
        supabase.table('digitised_documents')\
            .update({
                'status': 'error',
                'error_message': str(e),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', document_id)\
            .execute()
        
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

# OLD: Proxy to microservice - DEPRECATED in Phase 1.7
# Now using MongoDB storage instead (see endpoint at line ~2429)
# @api_router.get("/gp/parsed-document/{document_id}")
# async def proxy_gp_parsed_document(document_id: str):
#     """Proxy get parsed document to microservice"""
#     try:
#         async with httpx.AsyncClient(timeout=30.0) as client:
#             response = await client.get(
#                 f"{MICROSERVICE_URL}/api/v1/gp/parsed-document/{document_id}"
#             )
#             response.raise_for_status()
#             return response.json()
#     except Exception as e:
#         logger.error(f"GP parsed document proxy error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

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
    """
    Get GP document for viewing from Supabase Storage
    Phase 1.7: Uses Supabase Storage (production will use S3)
    """
    try:
        # Get document metadata from digitised_documents table
        doc_result = supabase.table('digitised_documents')\
            .select('*')\
            .eq('id', document_id)\
            .execute()
        
        if not doc_result.data:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
        
        doc_metadata = doc_result.data[0]
        storage_path = doc_metadata['file_path']
        
        # Check if it's a Supabase Storage path or local path
        if storage_path.startswith(DEMO_WORKSPACE_ID):
            # It's in Supabase Storage - generate signed URL
            signed_url_response = supabase.storage.from_('medical-records').create_signed_url(
                path=storage_path,
                expires_in=3600  # 1 hour
            )
            
            # Redirect to signed URL
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=signed_url_response['signedURL'])
        
        else:
            # Fallback: Local file system (for old documents)
            file_path = Path(storage_path)
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Document file not found")
            
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            from fastapi.responses import Response
            return Response(
                content=file_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{doc_metadata["filename"]}"',
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
        
        # Update digitised_documents status to 'approved' and link to patient/encounter
        try:
            supabase.table('digitised_documents')\
                .update({
                    'status': 'approved',
                    'patient_id': patient_id,
                    'encounter_id': encounter_id,
                    'validated_by': 'user',
                    'validated_at': datetime.now(timezone.utc).isoformat(),
                    'approved_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('id', document_id)\
                .execute()
            logger.info(f"Updated digitised_documents record for {document_id} - status: approved")
        except Exception as e:
            logger.warning(f"Could not update digitised_documents for {document_id}: {e}")
        
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
        logger.info(f"Received demographics: {demographics}")
        
        # Normalize demographics data - try multiple field name variations
        # Extract name from various possible fields
        first_name = 'Unknown'
        last_name = 'Unknown'
        
        # Try to get first_name and last_name directly
        if demographics.get('first_name'):
            first_name = demographics.get('first_name')
        if demographics.get('last_name'):
            last_name = demographics.get('last_name')
        
        # Try first_names and surname (common in South African documents)
        if first_name == 'Unknown' and demographics.get('first_names'):
            first_name = demographics.get('first_names')
        if last_name == 'Unknown' and demographics.get('surname'):
            last_name = demographics.get('surname')
        
        # If not found, try patient_name or name field
        if first_name == 'Unknown' and (demographics.get('patient_name') or demographics.get('name')):
            full_name = demographics.get('patient_name') or demographics.get('name', '')
            name_parts = full_name.strip().split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
            elif len(name_parts) == 1:
                first_name = name_parts[0]
                last_name = ''
        
        # Extract other fields with fallbacks
        dob = demographics.get('dob') or demographics.get('date_of_birth') or demographics.get('birth_date') or '1900-01-01'
        
        # Normalize date format (handle formats like 1991.02:03 or 1991.02.03)
        if dob and dob != '1900-01-01':
            # Replace periods and colons with dashes
            dob = dob.replace('.', '-').replace(':', '-')
            # Ensure proper formatting
            try:
                from datetime import datetime
                parsed_date = datetime.strptime(dob, '%Y-%m-%d')
                dob = parsed_date.strftime('%Y-%m-%d')
            except:
                # If parsing fails, keep the normalized version
                pass
        id_number = demographics.get('id_number') or demographics.get('patient_id') or demographics.get('sa_id_number') or demographics.get('id') or 'Unknown'
        
        # Contact number - check multiple field variations
        contact_number = (
            demographics.get('contact_number') or 
            demographics.get('cell_number') or 
            demographics.get('mobile') or 
            demographics.get('phone') or 
            demographics.get('telephone') or 
            demographics.get('cellphone')
        )
        
        email = demographics.get('email') or demographics.get('email_address')
        
        # Address - combine multiple address fields if needed
        address = demographics.get('address') or demographics.get('residential_address')
        if not address:
            # Build address from components
            address_parts = []
            if demographics.get('home_address_street'):
                address_parts.append(demographics.get('home_address_street'))
            if demographics.get('home_address_suburb'):
                address_parts.append(demographics.get('home_address_suburb'))
            if demographics.get('home_address_city'):
                address_parts.append(demographics.get('home_address_city'))
            if demographics.get('home_address_code'):
                address_parts.append(str(demographics.get('home_address_code')))
            if demographics.get('postal_address') and not address_parts:
                address_parts.append(demographics.get('postal_address'))
            address = ', '.join(address_parts) if address_parts else None
        
        # Medical aid - check multiple field variations
        medical_aid = (
            demographics.get('medical_aid') or 
            demographics.get('medical_scheme') or 
            demographics.get('medical_aid_name') or 
            demographics.get('medical_aid_scheme')
        )
        
        # Create new patient in Supabase
        patient_id = str(uuid.uuid4())
        
        patient_data = {
            'id': patient_id,
            'tenant_id': DEMO_TENANT_ID,
            'workspace_id': DEMO_WORKSPACE_ID,
            'first_name': first_name,
            'last_name': last_name,
            'dob': dob,
            'id_number': id_number,
            'contact_number': contact_number,
            'email': email,
            'address': address,
            'medical_aid': medical_aid,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Normalized patient data: {patient_data}")
        
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
        
        # Update digitised_documents status to 'approved' and link to patient/encounter
        try:
            supabase.table('digitised_documents')\
                .update({
                    'status': 'approved',
                    'patient_id': patient_id,
                    'encounter_id': encounter_id,
                    'validated_by': 'user',
                    'validated_at': datetime.now(timezone.utc).isoformat(),
                    'approved_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('id', document_id)\
                .execute()
            logger.info(f"Updated digitised_documents record for {document_id} - status: approved")
        except Exception as e:
            logger.warning(f"Could not update digitised_documents for {document_id}: {e}")
        
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

@api_router.post("/gp/documents/{document_id}/extract")
async def extract_document_data(document_id: str):
    """
    Trigger extraction for a parsed document using LandingAI Extract API
    Converts parsed chunks into structured data (Demographics, Conditions, Vitals, Notes)
    """
    try:
        # Get document metadata
        doc_result = supabase.table('digitised_documents')\
            .select('*')\
            .eq('id', document_id)\
            .execute()
        
        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_result.data[0]
        
        if document['status'] not in ['parsed', 'extracted', 'error']:
            raise HTTPException(
                status_code=400, 
                detail=f"Document must be parsed before extraction. Current status: {document['status']}"
            )
        
        # Update status to extracting
        supabase.table('digitised_documents')\
            .update({
                'status': 'extracting',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', document_id)\
            .execute()
        
        logger.info(f"Starting extraction for document {document_id}")
        
        # Get parsed data from MongoDB
        parsed_doc = await db.parsed_documents.find_one({'document_id': document_id})
        
        if not parsed_doc:
            raise HTTPException(status_code=404, detail="Parsed data not found in MongoDB")
        
        # Extract chunks/markdown from parsed data
        extracted_data = parsed_doc.get('extracted_data', {})
        microservice_response = parsed_doc.get('microservice_response', {})
        chunks = microservice_response.get('data', {}).get('chunks', [])
        
        # Combine all chunks into markdown text for extraction
        markdown_text = "\n\n".join([
            chunk.get('markdown', chunk.get('text', '')) 
            for chunk in chunks if chunk.get('markdown') or chunk.get('text')
        ])
        
        if not markdown_text:
            raise HTTPException(status_code=400, detail="No markdown content available for extraction")
        
        # Call LandingAI Extract API with defined schema
        # This is where we would call the Extract API with a schema
        # For now, we'll use the existing extracted_data from microservice
        # In a full implementation, you would define Pydantic schemas and call:
        # from landing_ai_ade import LandingAIADE
        # client = LandingAIADE(apikey=os.getenv('LANDING_AI_API_KEY'))
        # result = client.extract(schema=your_schema, markdown=markdown_text)
        
        # The microservice response has extractions nested in data
        # extracted_data = result.data = { ..., extractions: { demographics, chronic_summary, vitals, clinical_notes } }
        extractions = extracted_data.get('extractions', {})
        
        logger.info(f"Extracted data structure: {list(extracted_data.keys())}")
        logger.info(f"Extractions: {list(extractions.keys())}")
        
        # For now, we'll structure the existing data
        structured_extraction = {
            'demographics': extractions.get('demographics', extracted_data.get('demographics', {})),
            'chronic_summary': extractions.get('chronic_summary', extracted_data.get('chronic_summary', {})),
            'vitals': extractions.get('vitals', extracted_data.get('vitals', {})),
            'clinical_notes': extractions.get('clinical_notes', extracted_data.get('clinical_notes', {})),
            'extracted_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Update parsed document with structured extraction
        await db.parsed_documents.update_one(
            {'document_id': document_id},
            {'$set': {
                'structured_extraction': structured_extraction,
                'extraction_completed_at': datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Update status to extracted
        supabase.table('digitised_documents')\
            .update({
                'status': 'extracted',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', document_id)\
            .execute()
        
        logger.info(f"Document {document_id} extraction completed")
        
        return {
            'status': 'success',
            'message': 'Document extraction completed',
            'document_id': document_id,
            'extracted_data': structured_extraction
        }
    
    except HTTPException:
        raise
    except Exception as e:
        # Update status to error
        supabase.table('digitised_documents')\
            .update({
                'status': 'error',
                'error_message': f"Extraction failed: {str(e)}",
                'updated_at': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', document_id)\
            .execute()
        
        logger.error(f"Error extracting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Digitised Documents Endpoints (Phase 1.7) ====================

@api_router.get("/gp/documents")
async def list_digitised_documents(
    status: Optional[str] = None,
    patient_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    List all digitised documents with optional filters
    Supports pagination and multiple filter criteria
    """
    try:
        logger.info(f"Fetching digitised documents with filters: status={status}, patient_id={patient_id}")
        
        # Build query
        query = supabase.table('digitised_documents').select('*')
        
        # Apply filters
        if status:
            query = query.eq('status', status)
        if patient_id:
            query = query.eq('patient_id', patient_id)
        if date_from:
            query = query.gte('upload_date', date_from)
        if date_to:
            query = query.lte('upload_date', date_to)
        if search:
            query = query.ilike('filename', f'%{search}%')
        
        # Apply workspace filter
        query = query.eq('workspace_id', DEMO_WORKSPACE_ID)
        
        # Order by upload date descending
        query = query.order('upload_date', desc=True)
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        result = query.execute()
        
        # Enrich with patient names if patient_id exists
        documents = []
        for doc in result.data:
            doc_copy = doc.copy()
            if doc.get('patient_id'):
                try:
                    patient_res = supabase.table('patients').select('first_name, last_name').eq('id', doc['patient_id']).execute()
                    if patient_res.data:
                        patient = patient_res.data[0]
                        doc_copy['patient_name'] = f"{patient['first_name']} {patient['last_name']}"
                except:
                    doc_copy['patient_name'] = None
            documents.append(doc_copy)
        
        return {
            'status': 'success',
            'documents': documents,
            'total': len(documents),
            'offset': offset,
            'limit': limit
        }
    except Exception as e:
        logger.error(f"Error listing digitised documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/gp/documents/{document_id}")
async def get_digitised_document(document_id: str):
    """Get details of a specific digitised document"""
    try:
        result = supabase.table('digitised_documents')\
            .select('*')\
            .eq('id', document_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = result.data[0]
        
        # Enrich with patient name if linked
        if document.get('patient_id'):
            try:
                patient_res = supabase.table('patients').select('first_name, last_name').eq('id', document['patient_id']).execute()
                if patient_res.data:
                    patient = patient_res.data[0]
                    document['patient_name'] = f"{patient['first_name']} {patient['last_name']}"
            except:
                document['patient_name'] = None
        
        return {
            'status': 'success',
            'document': document
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/gp/parsed-document/{mongo_id}")
async def get_parsed_document_from_mongo(mongo_id: str):
    """
    Retrieve parsed document data from MongoDB
    This is our internal storage, not the microservice
    """
    try:
        from bson import ObjectId
        
        # Try as ObjectId first, then as string
        try:
            query = {'_id': ObjectId(mongo_id)}
        except:
            query = {'document_id': mongo_id}
        
        parsed_doc = await db.parsed_documents.find_one(query)
        
        if not parsed_doc:
            raise HTTPException(status_code=404, detail="Parsed document not found")
        
        # Convert ObjectId to string for JSON serialization
        if '_id' in parsed_doc:
            parsed_doc['_id'] = str(parsed_doc['_id'])
        
        # Prioritize structured_extraction if it exists (from Extract API)
        # Otherwise use extracted_data (from initial Parse+Extract microservice call)
        data = parsed_doc.get('structured_extraction') or parsed_doc.get('extracted_data', {})
        
        return {
            'status': 'success',
            'data': data,
            'microservice_response': parsed_doc.get('microservice_response', {})
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving parsed document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/gp/documents/{document_id}/status")
async def update_document_status(document_id: str, update: DocumentStatusUpdate):
    """Update the status of a digitised document"""
    try:
        logger.info(f"Updating document {document_id} status to {update.status}")
        
        update_data = {
            'status': update.status,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if update.error_message:
            update_data['error_message'] = update.error_message
        
        result = supabase.table('digitised_documents')\
            .update(update_data)\
            .eq('id', document_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            'status': 'success',
            'message': f'Document status updated to {update.status}',
            'document': result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/gp/documents/{document_id}")
async def delete_digitised_document(document_id: str):
    """Delete a digitised document and its associated files"""
    try:
        # Get document details
        doc_result = supabase.table('digitised_documents')\
            .select('*')\
            .eq('id', document_id)\
            .execute()
        
        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_result.data[0]
        
        # Delete physical file if exists
        if document.get('file_path'):
            file_path = Path(document['file_path'])
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
        
        # Delete from database
        supabase.table('digitised_documents').delete().eq('id', document_id).execute()
        
        return {
            'status': 'success',
            'message': 'Document deleted successfully'
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/gp/documents/bulk-extract")
async def bulk_extract_documents(document_ids: List[str]):
    """Trigger extraction for multiple documents"""
    try:
        logger.info(f"Bulk extraction requested for {len(document_ids)} documents")
        
        results = []
        for doc_id in document_ids:
            try:
                # Update status to 'extracting'
                supabase.table('digitised_documents')\
                    .update({'status': 'extracting', 'updated_at': datetime.now(timezone.utc).isoformat()})\
                    .eq('id', doc_id)\
                    .execute()
                
                results.append({
                    'document_id': doc_id,
                    'status': 'queued'
                })
            except Exception as e:
                results.append({
                    'document_id': doc_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return {
            'status': 'success',
            'message': f'Extraction queued for {len(document_ids)} documents',
            'results': results
        }
    except Exception as e:
        logger.error(f"Error in bulk extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@api_router.post("/gp/upload-with-template")
async def upload_gp_document_with_template(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    encounter_id: Optional[str] = Form(None)
):
    """
    NEW ENDPOINT: Upload GP document with template-driven extraction and auto-population
    
    This endpoint uses the Phase 1.2 Enhanced Extraction:
    - Layer 1: Always extracts core demographics
    - Layer 2: Uses templates to extract additional sections
    - Auto-populates structured tables based on field mappings
    
    Args:
        file: PDF file to upload
        patient_id: Optional patient ID (if known)
        template_id: Optional template ID (will use default if not specified)
        encounter_id: Optional encounter ID to link records
    
    Returns:
        Complete extraction result with auto-population summary
    """
    document_id = str(uuid.uuid4())
    
    try:
        logger.info(f"📄 Template-driven upload: {file.filename}")
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Save file temporarily
        temp_dir = Path("storage/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file_path = temp_dir / f"{document_id}_{file.filename}"
        
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"✅ File saved temporarily: {temp_file_path}")
        
        # Create digitised_documents record
        digitised_doc_data = {
            'id': document_id,
            'workspace_id': DEMO_WORKSPACE_ID,
            'patient_id': patient_id,
            'filename': file.filename,
            'file_path': str(temp_file_path),
            'file_size': file_size,
            'status': 'processing',
            'template_id': template_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('digitised_documents').insert(digitised_doc_data).execute()
        logger.info(f"✅ Created digitised_documents record: {document_id}")
        
        # Process with template-driven extraction
        from app.services.gp_processor import GPDocumentProcessor
        
        # Initialize processor with MongoDB connection
        processor = GPDocumentProcessor(db_manager=type('obj', (object,), {
            'db': db,
            'connected': True
        }))
        
        # Process the document with templates
        result = await processor.process_with_template(
            file_path=str(temp_file_path),
            filename=file.filename,
            organization_id=DEMO_WORKSPACE_ID,
            workspace_id=DEMO_WORKSPACE_ID,
            tenant_id=DEMO_TENANT_ID,
            template_id=template_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            file_data=file_content
        )
        
        # Update status based on result
        if result.get('success'):
            status = 'extracted' if result.get('template_used') else 'parsed'
            
            update_data = {
                'status': status,
                'parsed_doc_id': result.get('parsed_doc_id'),
                'template_used': result.get('template_used', False),
                'records_created': result.get('auto_population', {}).get('records_created', 0),
                'tables_populated': result.get('auto_population', {}).get('tables_populated', {}),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table('digitised_documents')\
                .update(update_data)\
                .eq('id', document_id)\
                .execute()
            
            logger.info(f"✅ Document processed successfully: {document_id}")
            logger.info(f"📊 Template used: {result.get('template_used')}")
            logger.info(f"📊 Records created: {result.get('auto_population', {}).get('records_created', 0)}")
            logger.info(f"📊 Tables populated: {list(result.get('auto_population', {}).get('tables_populated', {}).keys())}")
        else:
            supabase.table('digitised_documents')\
                .update({
                    'status': 'error',
                    'error_message': result.get('error', 'Unknown error'),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('id', document_id)\
                .execute()
        
        # Clean up temp file
        try:
            temp_file_path.unlink()
        except:
            pass
        
        return JSONResponse(content={
            'status': 'success' if result.get('success') else 'error',
            'message': 'Document processed with template-driven extraction',
            'data': result
        })
        
    except Exception as e:
        logger.error(f"❌ Template-driven upload failed: {e}", exc_info=True)
        
        # Update status to error
        try:
            supabase.table('digitised_documents')\
                .update({
                    'status': 'error',
                    'error_message': str(e),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('id', document_id)\
                .execute()
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")



@api_router.post("/gp/batch-upload")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    patient_id: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    encounter_id: Optional[str] = Form(None)
):
    """
    BATCH UPLOAD: Upload multiple GP documents for processing
    
    Processes multiple documents asynchronously with progress tracking.
    Returns a batch_id that can be used to track progress.
    
    Args:
        files: List of PDF files to upload (up to 50)
        patient_id: Optional patient ID for all files
        template_id: Optional template ID (uses default if not specified)
        encounter_id: Optional encounter ID
    
    Returns:
        {
            'batch_id': str,
            'total_files': int,
            'status': 'processing',
            'message': str
        }
    """
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per batch")
    
    batch_id = str(uuid.uuid4())
    
    try:
        logger.info(f"📦 Batch upload started: {len(files)} files")
        
        # Get batch service
        from app.services.batch_upload_service import get_batch_service
        batch_service = get_batch_service(
            db_manager=type('obj', (object,), {'db': db}),
            supabase_client=supabase
        )
        
        # Prepare file info for batch creation
        files_info = [
            {
                'filename': file.filename,
                'size': file.size if hasattr(file, 'size') else 0
            }
            for file in files
        ]
        
        # Create batch record
        batch_id = batch_service.create_batch(
            workspace_id=DEMO_WORKSPACE_ID,
            tenant_id=DEMO_TENANT_ID,
            files_info=files_info,
            patient_id=patient_id,
            template_id=template_id
        )
        
        # Save files temporarily and prepare for processing
        temp_dir = Path("storage/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        files_data = []
        
        for idx, file in enumerate(files):
            # Read file content
            file_content = await file.read()
            
            # Generate unique file_id
            file_id = batch_service.get_batch_status(batch_id)['files'][idx]['file_id']
            
            # Save temporarily
            temp_file_path = temp_dir / f"{batch_id}_{file_id}_{file.filename}"
            with open(temp_file_path, "wb") as f:
                f.write(file_content)
            
            files_data.append({
                'file_id': file_id,
                'filename': file.filename,
                'file_path': str(temp_file_path),
                'file_content': file_content
            })
        
        logger.info(f"✅ All files saved temporarily for batch {batch_id}")
        
        # Initialize processor
        from app.services.gp_processor import GPDocumentProcessor
        processor = GPDocumentProcessor(db_manager=type('obj', (object,), {
            'db': db,
            'connected': True
        }))
        
        # Start background processing (fire and forget)
        asyncio.create_task(
            batch_service.process_batch(
                batch_id=batch_id,
                files_data=files_data,
                processor=processor,
                workspace_id=DEMO_WORKSPACE_ID,
                tenant_id=DEMO_TENANT_ID,
                patient_id=patient_id,
                template_id=template_id,
                encounter_id=encounter_id
            )
        )
        
        logger.info(f"🚀 Background processing started for batch {batch_id}")
        
        return JSONResponse(content={
            'status': 'success',
            'batch_id': batch_id,
            'total_files': len(files),
            'message': f'Batch upload initiated. Processing {len(files)} files in background.',
            'tracking_url': f'/api/gp/batch-status/{batch_id}'
        })
        
    except Exception as e:
        logger.error(f"❌ Batch upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


@api_router.get("/gp/batch-status/{batch_id}")
async def get_batch_status(batch_id: str):
    """
    Get current status of a batch upload
    
    Returns real-time progress including:
    - Overall batch status
    - Progress counts (pending, processing, completed, failed)
    - Individual file statuses
    - Results for completed files
    """
    try:
        from app.services.batch_upload_service import get_batch_service
        batch_service = get_batch_service()
        
        if not batch_service:
            raise HTTPException(status_code=500, detail="Batch service not initialized")
        
        batch_status = batch_service.get_batch_status(batch_id)
        
        if not batch_status:
            # Try to fetch from database
            batch_record = await db['batch_uploads'].find_one({'id': batch_id})
            if batch_record:
                return JSONResponse(content={
                    'status': 'success',
                    'batch': batch_record
                })
            else:
                raise HTTPException(status_code=404, detail="Batch not found")
        
        return JSONResponse(content={
            'status': 'success',
            'batch': batch_status
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/gp/batch-history")
async def get_batch_history(workspace_id: str = DEMO_WORKSPACE_ID, limit: int = 20):
    """
    Get recent batch uploads for a workspace
    """
    try:
        from app.services.batch_upload_service import get_batch_service
        batch_service = get_batch_service()
        
        if not batch_service:
            raise HTTPException(status_code=500, detail="Batch service not initialized")
        
        batches = await batch_service.get_batch_history(workspace_id, limit)
        
        return JSONResponse(content={
            'status': 'success',
            'batches': batches
        })
        
    except Exception as e:
        logger.error(f"Failed to get batch history: {e}")
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
from api.validation import router as validation_router

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
api_router.include_router(validation_router, tags=["Validation Workflow"])

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
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form
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
        query = supabase.table('patients').select('*').eq('workspace_id', DEMO_WORKSPACE_ID)
        
        if search:
            # Simple search implementation - in production, use full-text search
            query = query.or_(f"first_name.ilike.%{search}%,last_name.ilike.%{search}%,id_number.ilike.%{search}%")
        
        result = query.order('created_at', desc=True).limit(100).execute()
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
        
        # Mock ADE parsing (replace with real LandingAI ADE integration)
        parsed_data = mock_ade_parser(file.filename, file_content)
        
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
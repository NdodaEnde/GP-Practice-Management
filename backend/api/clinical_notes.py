"""
Clinical Notes API endpoints
Structured SOAP notes and clinical documentation
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
from supabase import create_client
import uuid

router = APIRouter()

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# Request/Response Models
class ClinicalNoteCreate(BaseModel):
    encounter_id: str
    patient_id: str
    format: str = 'soap'  # soap, free_text, discharge_summary, etc.
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    raw_text: Optional[str] = None
    author: Optional[str] = None
    role: str = 'doctor'
    source: str = 'manual_entry'  # ai_scribe, manual_entry, document_extraction


class ClinicalNoteUpdate(BaseModel):
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    raw_text: Optional[str] = None
    author: Optional[str] = None


class ClinicalNote(BaseModel):
    id: str
    encounter_id: str
    patient_id: str
    format: str
    subjective: Optional[str]
    objective: Optional[str]
    assessment: Optional[str]
    plan: Optional[str]
    raw_text: Optional[str]
    note_datetime: str
    author: Optional[str]
    role: str
    source: str
    signed: bool
    signed_at: Optional[str]
    signed_by: Optional[str]
    version: int
    created_at: str


@router.post("/clinical-notes", response_model=ClinicalNote)
async def create_clinical_note(note: ClinicalNoteCreate):
    """Create a new clinical note"""
    try:
        # Get workspace/tenant from environment (or from request in production)
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        tenant_id = os.getenv('DEMO_TENANT_ID')
        
        note_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            'encounter_id': note.encounter_id,
            'patient_id': note.patient_id,
            'format': note.format,
            'subjective': note.subjective,
            'objective': note.objective,
            'assessment': note.assessment,
            'plan': note.plan,
            'raw_text': note.raw_text,
            'author': note.author,
            'role': note.role,
            'source': note.source,
            'note_datetime': datetime.utcnow().isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('clinical_notes').insert(note_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create clinical note")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating clinical note: {str(e)}")


@router.get("/clinical-notes/encounter/{encounter_id}", response_model=List[ClinicalNote])
async def get_notes_by_encounter(encounter_id: str):
    """Get all clinical notes for an encounter"""
    try:
        result = supabase.table('clinical_notes')\
            .select('*')\
            .eq('encounter_id', encounter_id)\
            .order('note_datetime', desc=True)\
            .execute()
        
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clinical notes: {str(e)}")


@router.get("/clinical-notes/patient/{patient_id}", response_model=List[ClinicalNote])
async def get_notes_by_patient(
    patient_id: str,
    limit: int = Query(50, le=200),
    signed_only: bool = Query(False)
):
    """Get all clinical notes for a patient"""
    try:
        query = supabase.table('clinical_notes')\
            .select('*')\
            .eq('patient_id', patient_id)
        
        if signed_only:
            query = query.eq('signed', True)
        
        result = query.order('note_datetime', desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching patient clinical notes: {str(e)}")


@router.get("/clinical-notes/{note_id}", response_model=ClinicalNote)
async def get_clinical_note(note_id: str):
    """Get a specific clinical note by ID"""
    try:
        result = supabase.table('clinical_notes')\
            .select('*')\
            .eq('id', note_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Clinical note not found")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clinical note: {str(e)}")


@router.put("/clinical-notes/{note_id}", response_model=ClinicalNote)
async def update_clinical_note(note_id: str, note_update: ClinicalNoteUpdate):
    """Update a clinical note (creates new version)"""
    try:
        # Get existing note
        existing = supabase.table('clinical_notes')\
            .select('*')\
            .eq('id', note_id)\
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Clinical note not found")
        
        old_note = existing.data[0]
        
        # Check if signed (can't edit signed notes directly)
        if old_note.get('signed'):
            raise HTTPException(status_code=403, detail="Cannot edit signed note. Create amendment instead.")
        
        # Prepare update data (only update provided fields)
        update_data = {
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if note_update.subjective is not None:
            update_data['subjective'] = note_update.subjective
        if note_update.objective is not None:
            update_data['objective'] = note_update.objective
        if note_update.assessment is not None:
            update_data['assessment'] = note_update.assessment
        if note_update.plan is not None:
            update_data['plan'] = note_update.plan
        if note_update.raw_text is not None:
            update_data['raw_text'] = note_update.raw_text
        if note_update.author is not None:
            update_data['author'] = note_update.author
        
        # Update the note
        result = supabase.table('clinical_notes')\
            .update(update_data)\
            .eq('id', note_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update clinical note")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating clinical note: {str(e)}")


@router.post("/clinical-notes/{note_id}/sign")
async def sign_clinical_note(note_id: str, signed_by: str):
    """Sign (finalize) a clinical note"""
    try:
        update_data = {
            'signed': True,
            'signed_at': datetime.utcnow().isoformat(),
            'signed_by': signed_by,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('clinical_notes')\
            .update(update_data)\
            .eq('id', note_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Clinical note not found")
        
        return {
            'status': 'success',
            'message': 'Clinical note signed successfully',
            'note': result.data[0]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error signing clinical note: {str(e)}")


@router.post("/clinical-notes/{note_id}/amend", response_model=ClinicalNote)
async def create_amendment(note_id: str, amendment: ClinicalNoteUpdate):
    """Create an amendment to a signed note (new version)"""
    try:
        # Get original note
        original = supabase.table('clinical_notes')\
            .select('*')\
            .eq('id', note_id)\
            .execute()
        
        if not original.data:
            raise HTTPException(status_code=404, detail="Original note not found")
        
        old_note = original.data[0]
        
        # Create amended version
        amended_note = {
            'id': str(uuid.uuid4()),
            'tenant_id': old_note['tenant_id'],
            'workspace_id': old_note['workspace_id'],
            'encounter_id': old_note['encounter_id'],
            'patient_id': old_note['patient_id'],
            'format': old_note['format'],
            'subjective': amendment.subjective if amendment.subjective else old_note.get('subjective'),
            'objective': amendment.objective if amendment.objective else old_note.get('objective'),
            'assessment': amendment.assessment if amendment.assessment else old_note.get('assessment'),
            'plan': amendment.plan if amendment.plan else old_note.get('plan'),
            'raw_text': amendment.raw_text if amendment.raw_text else old_note.get('raw_text'),
            'author': amendment.author if amendment.author else old_note.get('author'),
            'role': old_note['role'],
            'source': old_note['source'],
            'parent_note_id': note_id,
            'version': old_note['version'] + 1,
            'note_datetime': datetime.utcnow().isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('clinical_notes').insert(amended_note).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create amendment")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating amendment: {str(e)}")


@router.delete("/clinical-notes/{note_id}")
async def delete_clinical_note(note_id: str):
    """Delete a clinical note (soft delete - mark as deleted)"""
    try:
        # Check if note is signed
        existing = supabase.table('clinical_notes')\
            .select('signed')\
            .eq('id', note_id)\
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Clinical note not found")
        
        if existing.data[0].get('signed'):
            raise HTTPException(status_code=403, detail="Cannot delete signed note")
        
        # Delete the note
        result = supabase.table('clinical_notes')\
            .delete()\
            .eq('id', note_id)\
            .execute()
        
        return {
            'status': 'success',
            'message': 'Clinical note deleted successfully'
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting clinical note: {str(e)}")

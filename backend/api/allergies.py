"""
Allergy Management API Endpoints
Sprint 1.1: Patient Safety Critical

Rebuilt onto the unified foundation: workspace_id comes from the authenticated
TOKEN (current_user), never from the caller-supplied patient_id (the old IDOR),
and every read/write is scoped to that workspace. Gating lives in the central
ROUTE_CAPABILITIES map (patient_ehr_basic); get_current_user supplies tenancy.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timezone
import uuid

from app.api.auth import get_current_user

router = APIRouter()


class AllergyCreate(BaseModel):
    patient_id: str
    substance: str
    reaction: Optional[str] = None
    severity: Optional[str] = None  # mild, moderate, severe, life_threatening, unknown
    status: str = 'active'
    onset_date: Optional[date] = None
    notes: Optional[str] = None
    source: str = 'manual_entry'
    source_document_id: Optional[str] = None


class AllergyUpdate(BaseModel):
    substance: Optional[str] = None
    reaction: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    onset_date: Optional[date] = None
    notes: Optional[str] = None


class AllergyResponse(BaseModel):
    id: str
    patient_id: str
    substance: str
    reaction: Optional[str]
    severity: Optional[str]
    status: str
    onset_date: Optional[date]
    notes: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime


def _require_patient(supabase, patient_id: str, workspace_id: str):
    """The patient must belong to the caller's workspace, else 404."""
    res = supabase.table('patients').select('id').eq('id', patient_id).eq('workspace_id', workspace_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Patient not found")


@router.post("/allergies", response_model=AllergyResponse)
async def create_allergy(allergy: AllergyCreate, current_user: dict = Depends(get_current_user)):
    """Create an allergy for a patient in the caller's workspace."""
    from server import supabase
    try:
        workspace_id = current_user["workspace_id"]
        _require_patient(supabase, allergy.patient_id, workspace_id)
        allergy_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': current_user.get("tenant_id") or workspace_id,
            'workspace_id': workspace_id,
            'patient_id': allergy.patient_id,
            'substance': allergy.substance,
            'reaction': allergy.reaction,
            'severity': allergy.severity,
            'status': allergy.status,
            'onset_date': allergy.onset_date.isoformat() if allergy.onset_date else None,
            'notes': allergy.notes,
            'source': allergy.source,
            'source_document_id': allergy.source_document_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        result = supabase.table('allergies').insert(allergy_data).execute()
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create allergy: {str(e)}")


@router.get("/allergies/patient/{patient_id}", response_model=List[AllergyResponse])
async def get_patient_allergies(patient_id: str, status: Optional[str] = 'active',
                                current_user: dict = Depends(get_current_user)):
    """Get a patient's allergies (caller's workspace only)."""
    from server import supabase
    try:
        query = supabase.table('allergies').select('*')\
            .eq('workspace_id', current_user["workspace_id"]).eq('patient_id', patient_id)
        if status:
            query = query.eq('status', status)
        return query.order('created_at', desc=True).execute().data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch allergies: {str(e)}")


@router.get("/allergies/{allergy_id}", response_model=AllergyResponse)
async def get_allergy(allergy_id: str, current_user: dict = Depends(get_current_user)):
    """Get an allergy in the caller's workspace."""
    from server import supabase
    try:
        result = supabase.table('allergies').select('*')\
            .eq('id', allergy_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Allergy not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch allergy: {str(e)}")


@router.put("/allergies/{allergy_id}", response_model=AllergyResponse)
async def update_allergy(allergy_id: str, allergy: AllergyUpdate, current_user: dict = Depends(get_current_user)):
    """Update an allergy in the caller's workspace."""
    from server import supabase
    try:
        update_data = {'updated_at': datetime.now(timezone.utc).isoformat()}
        if allergy.substance is not None:  update_data['substance'] = allergy.substance
        if allergy.reaction is not None:   update_data['reaction'] = allergy.reaction
        if allergy.severity is not None:   update_data['severity'] = allergy.severity
        if allergy.status is not None:     update_data['status'] = allergy.status
        if allergy.onset_date is not None: update_data['onset_date'] = allergy.onset_date.isoformat()
        if allergy.notes is not None:      update_data['notes'] = allergy.notes
        result = supabase.table('allergies').update(update_data)\
            .eq('id', allergy_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Allergy not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update allergy: {str(e)}")


@router.delete("/allergies/{allergy_id}")
async def delete_allergy(allergy_id: str, current_user: dict = Depends(get_current_user)):
    """Soft-delete (mark entered_in_error) an allergy in the caller's workspace."""
    from server import supabase
    try:
        result = supabase.table('allergies').update({
            'status': 'entered_in_error',
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', allergy_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Allergy not found")
        return {'status': 'success', 'message': 'Allergy marked as entered_in_error'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete allergy: {str(e)}")


@router.post("/allergies/check-prescription")
async def check_prescription_safety(patient_id: str, medication_name: str,
                                    current_user: dict = Depends(get_current_user)):
    """Check a medication against the patient's active allergies (caller's workspace only)."""
    from server import supabase
    try:
        result = supabase.table('allergies').select('*')\
            .eq('workspace_id', current_user["workspace_id"])\
            .eq('patient_id', patient_id).eq('status', 'active').execute()
        allergies = result.data
        if not allergies:
            return {'safe': True, 'message': 'No known allergies', 'allergies': []}
        medication_lower = medication_name.lower()
        warnings = []
        for allergy in allergies:
            substance_lower = (allergy['substance'] or '').lower()
            if substance_lower and (substance_lower in medication_lower or medication_lower in substance_lower):
                warnings.append({'substance': allergy['substance'], 'reaction': allergy['reaction'],
                                 'severity': allergy['severity']})
        if warnings:
            return {'safe': False,
                    'message': f'⚠️ ALLERGY ALERT: Patient has {len(warnings)} potential allergy conflict(s)',
                    'allergies': warnings, 'recommendation': 'Review allergies before prescribing'}
        return {'safe': True, 'message': 'No known conflicts', 'allergies': allergies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check prescription safety: {str(e)}")

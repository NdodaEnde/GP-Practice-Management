"""
Diagnoses Management API
Sprint 1.3: Structured Diagnoses with ICD-10

Rebuilt onto the unified foundation: workspace_id from the authenticated TOKEN
(current_user), set on every write and scoped on every read. Gating lives in
the central ROUTE_CAPABILITIES map (patient_ehr_basic).

The API contract (icd10_code / diagnosis_description / notes) is preserved for
the frontend; internally it maps to the real table columns (code / display /
clinical_notes) — the Mar-8 router had drifted from the unified schema.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from app.api.auth import get_current_user

router = APIRouter()


class DiagnosisCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    icd10_code: str
    diagnosis_description: str
    diagnosis_type: str = 'primary'
    status: str = 'active'
    onset_date: Optional[str] = None
    notes: Optional[str] = None


class DiagnosisResponse(BaseModel):
    id: str
    patient_id: str
    encounter_id: Optional[str]
    icd10_code: str
    diagnosis_description: str
    diagnosis_type: Optional[str]
    status: str
    onset_date: Optional[str]
    notes: Optional[str]
    created_at: str
    updated_at: Optional[str]
    created_by: Optional[str]


class DiagnosisUpdate(BaseModel):
    diagnosis_description: Optional[str] = None
    diagnosis_type: Optional[str] = None
    status: Optional[str] = None
    onset_date: Optional[str] = None
    notes: Optional[str] = None


def _to_response(row: dict) -> dict:
    """Map real DB columns -> the API contract field names."""
    return {
        'id': row['id'],
        'patient_id': row.get('patient_id'),
        'encounter_id': row.get('encounter_id'),
        'icd10_code': row.get('code'),
        'diagnosis_description': row.get('display'),
        'diagnosis_type': row.get('diagnosis_type'),
        'status': row.get('status'),
        'onset_date': row.get('onset_date'),
        'notes': row.get('clinical_notes'),
        'created_at': row.get('created_at'),
        'updated_at': row.get('updated_at'),
        'created_by': row.get('created_by'),
    }


def _require_patient(supabase, patient_id: str, workspace_id: str):
    res = supabase.table('patients').select('id').eq('id', patient_id).eq('workspace_id', workspace_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Patient not found")


@router.post("/diagnoses", response_model=DiagnosisResponse)
async def create_diagnosis(diagnosis: DiagnosisCreate, current_user: dict = Depends(get_current_user)):
    """Create a diagnosis for a patient in the caller's workspace."""
    from server import supabase
    try:
        workspace_id = current_user["workspace_id"]
        _require_patient(supabase, diagnosis.patient_id, workspace_id)
        if not supabase.table('icd10_codes').select('code').eq('code', diagnosis.icd10_code).execute().data:
            raise HTTPException(status_code=404, detail=f"ICD-10 code '{diagnosis.icd10_code}' not found")
        row = {
            'id': str(uuid.uuid4()),
            'workspace_id': workspace_id,
            'tenant_id': current_user.get("tenant_id") or workspace_id,
            'patient_id': diagnosis.patient_id,
            'encounter_id': diagnosis.encounter_id,
            'code': diagnosis.icd10_code,
            'coding_system': 'ICD-10',
            'display': diagnosis.diagnosis_description,
            'diagnosis_type': diagnosis.diagnosis_type,
            'status': diagnosis.status,
            'onset_date': diagnosis.onset_date,
            'clinical_notes': diagnosis.notes,
            'source': 'manual_entry',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': current_user.get("email") or "system",
        }
        result = supabase.table('diagnoses').insert(row).execute()
        return _to_response(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create diagnosis: {str(e)}")


@router.get("/diagnoses/patient/{patient_id}", response_model=List[DiagnosisResponse])
async def get_patient_diagnoses(
    patient_id: str,
    status: Optional[str] = Query(None),
    diagnosis_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Get a patient's diagnoses (caller's workspace only)."""
    from server import supabase
    try:
        query = supabase.table('diagnoses').select('*')\
            .eq('workspace_id', current_user["workspace_id"]).eq('patient_id', patient_id)
        if status:
            query = query.eq('status', status)
        if diagnosis_type:
            query = query.eq('diagnosis_type', diagnosis_type)
        return [_to_response(r) for r in query.order('created_at', desc=True).execute().data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch diagnoses: {str(e)}")


@router.get("/diagnoses/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(diagnosis_id: str, current_user: dict = Depends(get_current_user)):
    """Get a diagnosis in the caller's workspace."""
    from server import supabase
    try:
        result = supabase.table('diagnoses').select('*')\
            .eq('id', diagnosis_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Diagnosis with ID '{diagnosis_id}' not found")
        return _to_response(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch diagnosis: {str(e)}")


@router.patch("/diagnoses/{diagnosis_id}", response_model=DiagnosisResponse)
async def update_diagnosis(diagnosis_id: str, diagnosis_update: DiagnosisUpdate,
                           current_user: dict = Depends(get_current_user)):
    """Update a diagnosis in the caller's workspace."""
    from server import supabase
    try:
        u = diagnosis_update.dict(exclude_unset=True)
        # map API field names -> real DB columns
        col_map = {'diagnosis_description': 'display', 'notes': 'clinical_notes'}
        update_data = {col_map.get(k, k): v for k, v in u.items()}
        update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        result = supabase.table('diagnoses').update(update_data)\
            .eq('id', diagnosis_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Diagnosis with ID '{diagnosis_id}' not found")
        return _to_response(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update diagnosis: {str(e)}")


@router.delete("/diagnoses/{diagnosis_id}")
async def delete_diagnosis(diagnosis_id: str, current_user: dict = Depends(get_current_user)):
    """Soft-delete a diagnosis in the caller's workspace."""
    from server import supabase
    try:
        result = supabase.table('diagnoses').update({
            'status': 'deleted',
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', diagnosis_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Diagnosis with ID '{diagnosis_id}' not found")
        return {"status": "success", "message": f"Diagnosis {diagnosis_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete diagnosis: {str(e)}")


@router.get("/diagnoses/encounter/{encounter_id}", response_model=List[DiagnosisResponse])
async def get_encounter_diagnoses(encounter_id: str, current_user: dict = Depends(get_current_user)):
    """Get an encounter's diagnoses (caller's workspace only)."""
    from server import supabase
    try:
        result = supabase.table('diagnoses').select('*')\
            .eq('encounter_id', encounter_id).eq('workspace_id', current_user["workspace_id"])\
            .order('created_at', desc=True).execute()
        return [_to_response(r) for r in result.data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch encounter diagnoses: {str(e)}")

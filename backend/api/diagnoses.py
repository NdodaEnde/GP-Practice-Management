"""
Diagnoses Management API
Sprint 1.3: Structured Diagnoses with ICD-10
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()

# Pydantic models
class DiagnosisCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    icd10_code: str
    diagnosis_description: str
    diagnosis_type: str = 'primary'  # primary, secondary, differential
    status: str = 'active'  # active, resolved, ruled_out
    onset_date: Optional[str] = None
    notes: Optional[str] = None

class DiagnosisResponse(BaseModel):
    id: str
    patient_id: str
    encounter_id: Optional[str]
    icd10_code: str
    diagnosis_description: str
    diagnosis_type: str
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

@router.post("/diagnoses", response_model=DiagnosisResponse)
async def create_diagnosis(diagnosis: DiagnosisCreate):
    """Create a new diagnosis for a patient"""
    from server import supabase
    import uuid
    
    try:
        # Verify ICD-10 code exists
        icd_result = supabase.table('icd10_codes').select('*').eq('code', diagnosis.icd10_code).execute()
        if not icd_result.data:
            raise HTTPException(status_code=404, detail=f"ICD-10 code '{diagnosis.icd10_code}' not found")
        
        # Create diagnosis record
        diagnosis_data = {
            'id': str(uuid.uuid4()),
            'patient_id': diagnosis.patient_id,
            'encounter_id': diagnosis.encounter_id,
            'icd10_code': diagnosis.icd10_code,
            'diagnosis_description': diagnosis.diagnosis_description,
            'diagnosis_type': diagnosis.diagnosis_type,
            'status': diagnosis.status,
            'onset_date': diagnosis.onset_date,
            'notes': diagnosis.notes,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': 'system'  # TODO: Get from auth context
        }
        
        result = supabase.table('diagnoses').insert(diagnosis_data).execute()
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create diagnosis: {str(e)}")

@router.get("/diagnoses/patient/{patient_id}", response_model=List[DiagnosisResponse])
async def get_patient_diagnoses(
    patient_id: str,
    status: Optional[str] = Query(None, description="Filter by status (active, resolved, ruled_out)"),
    diagnosis_type: Optional[str] = Query(None, description="Filter by type (primary, secondary, differential)")
):
    """Get all diagnoses for a patient"""
    from server import supabase
    
    try:
        query = supabase.table('diagnoses').select('*').eq('patient_id', patient_id)
        
        if status:
            query = query.eq('status', status)
        
        if diagnosis_type:
            query = query.eq('diagnosis_type', diagnosis_type)
        
        result = query.order('created_at', desc=True).execute()
        
        return result.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch diagnoses: {str(e)}")

@router.get("/diagnoses/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(diagnosis_id: str):
    """Get a specific diagnosis by ID"""
    from server import supabase
    
    try:
        result = supabase.table('diagnoses').select('*').eq('id', diagnosis_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Diagnosis with ID '{diagnosis_id}' not found")
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch diagnosis: {str(e)}")

@router.patch("/diagnoses/{diagnosis_id}", response_model=DiagnosisResponse)
async def update_diagnosis(diagnosis_id: str, diagnosis_update: DiagnosisUpdate):
    """Update a diagnosis"""
    from server import supabase
    
    try:
        # Check if diagnosis exists
        check_result = supabase.table('diagnoses').select('*').eq('id', diagnosis_id).execute()
        if not check_result.data:
            raise HTTPException(status_code=404, detail=f"Diagnosis with ID '{diagnosis_id}' not found")
        
        # Prepare update data
        update_data = diagnosis_update.dict(exclude_unset=True)
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Update diagnosis
        result = supabase.table('diagnoses').update(update_data).eq('id', diagnosis_id).execute()
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update diagnosis: {str(e)}")

@router.delete("/diagnoses/{diagnosis_id}")
async def delete_diagnosis(diagnosis_id: str):
    """Delete a diagnosis (soft delete by setting status to 'deleted')"""
    from server import supabase
    
    try:
        # Check if diagnosis exists
        check_result = supabase.table('diagnoses').select('*').eq('id', diagnosis_id).execute()
        if not check_result.data:
            raise HTTPException(status_code=404, detail=f"Diagnosis with ID '{diagnosis_id}' not found")
        
        # Soft delete by updating status
        result = supabase.table('diagnoses').update({
            'status': 'deleted',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', diagnosis_id).execute()
        
        return {
            "status": "success",
            "message": f"Diagnosis {diagnosis_id} deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete diagnosis: {str(e)}")

@router.get("/diagnoses/encounter/{encounter_id}", response_model=List[DiagnosisResponse])
async def get_encounter_diagnoses(encounter_id: str):
    """Get all diagnoses for a specific encounter"""
    from server import supabase
    
    try:
        result = supabase.table('diagnoses')\
            .select('*')\
            .eq('encounter_id', encounter_id)\
            .order('created_at', desc=True)\
            .execute()
        
        return result.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch encounter diagnoses: {str(e)}")

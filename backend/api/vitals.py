"""
Vitals Management API
Sprint 1.3: Structured Vitals Table
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()

# Pydantic models
class VitalCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    measurement_date: str
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    bmi: Optional[float] = None
    notes: Optional[str] = None

class VitalResponse(BaseModel):
    id: str
    patient_id: str
    encounter_id: Optional[str]
    measurement_date: str
    blood_pressure_systolic: Optional[int]
    blood_pressure_diastolic: Optional[int]
    heart_rate: Optional[int]
    temperature: Optional[float]
    respiratory_rate: Optional[int]
    oxygen_saturation: Optional[int]
    weight: Optional[float]
    height: Optional[float]
    bmi: Optional[float]
    notes: Optional[str]
    created_at: str
    updated_at: Optional[str]
    recorded_by: Optional[str]

class VitalUpdate(BaseModel):
    measurement_date: Optional[str] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    bmi: Optional[float] = None
    notes: Optional[str] = None

@router.post("/vitals", response_model=VitalResponse)
async def create_vital(vital: VitalCreate):
    """Create a new vital signs record"""
    from server import supabase
    import uuid
    
    try:
        # Auto-calculate BMI if weight and height are provided
        bmi = vital.bmi
        if vital.weight and vital.height and not bmi:
            height_m = vital.height / 100  # Convert cm to meters
            bmi = round(vital.weight / (height_m ** 2), 1)
        
        # Create vital record
        vital_data = {
            'id': str(uuid.uuid4()),
            'patient_id': vital.patient_id,
            'encounter_id': vital.encounter_id,
            'measurement_date': vital.measurement_date,
            'blood_pressure_systolic': vital.blood_pressure_systolic,
            'blood_pressure_diastolic': vital.blood_pressure_diastolic,
            'heart_rate': vital.heart_rate,
            'temperature': vital.temperature,
            'respiratory_rate': vital.respiratory_rate,
            'oxygen_saturation': vital.oxygen_saturation,
            'weight': vital.weight,
            'height': vital.height,
            'bmi': bmi,
            'notes': vital.notes,
            'created_at': datetime.utcnow().isoformat(),
            'recorded_by': 'system'  # TODO: Get from auth context
        }
        
        result = supabase.table('vitals').insert(vital_data).execute()
        
        return result.data[0]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create vital: {str(e)}")

@router.get("/vitals/patient/{patient_id}", response_model=List[VitalResponse])
async def get_patient_vitals(
    patient_id: str,
    limit: int = Query(10, le=100, description="Maximum number of records to return")
):
    """Get all vital signs for a patient"""
    from server import supabase
    
    try:
        result = supabase.table('vitals')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .order('measurement_date', desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vitals: {str(e)}")

@router.get("/vitals/{vital_id}", response_model=VitalResponse)
async def get_vital(vital_id: str):
    """Get a specific vital signs record by ID"""
    from server import supabase
    
    try:
        result = supabase.table('vitals').select('*').eq('id', vital_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Vital with ID '{vital_id}' not found")
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vital: {str(e)}")

@router.patch("/vitals/{vital_id}", response_model=VitalResponse)
async def update_vital(vital_id: str, vital_update: VitalUpdate):
    """Update a vital signs record"""
    from server import supabase
    
    try:
        # Check if vital exists
        check_result = supabase.table('vitals').select('*').eq('id', vital_id).execute()
        if not check_result.data:
            raise HTTPException(status_code=404, detail=f"Vital with ID '{vital_id}' not found")
        
        # Prepare update data
        update_data = vital_update.dict(exclude_unset=True)
        
        # Recalculate BMI if weight or height changed
        if 'weight' in update_data or 'height' in update_data:
            current_data = check_result.data[0]
            weight = update_data.get('weight', current_data.get('weight'))
            height = update_data.get('height', current_data.get('height'))
            
            if weight and height:
                height_m = height / 100
                update_data['bmi'] = round(weight / (height_m ** 2), 1)
        
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Update vital
        result = supabase.table('vitals').update(update_data).eq('id', vital_id).execute()
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update vital: {str(e)}")

@router.delete("/vitals/{vital_id}")
async def delete_vital(vital_id: str):
    """Delete a vital signs record"""
    from server import supabase
    
    try:
        # Check if vital exists
        check_result = supabase.table('vitals').select('*').eq('id', vital_id).execute()
        if not check_result.data:
            raise HTTPException(status_code=404, detail=f"Vital with ID '{vital_id}' not found")
        
        # Delete vital
        supabase.table('vitals').delete().eq('id', vital_id).execute()
        
        return {
            "status": "success",
            "message": f"Vital {vital_id} deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete vital: {str(e)}")

@router.get("/vitals/encounter/{encounter_id}", response_model=List[VitalResponse])
async def get_encounter_vitals(encounter_id: str):
    """Get all vital signs for a specific encounter"""
    from server import supabase
    
    try:
        result = supabase.table('vitals')\
            .select('*')\
            .eq('encounter_id', encounter_id)\
            .order('measurement_date', desc=True)\
            .execute()
        
        return result.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch encounter vitals: {str(e)}")

@router.get("/vitals/patient/{patient_id}/latest", response_model=VitalResponse)
async def get_latest_vital(patient_id: str):
    """Get the most recent vital signs for a patient"""
    from server import supabase
    
    try:
        result = supabase.table('vitals')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .order('measurement_date', desc=True)\
            .limit(1)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail=f"No vitals found for patient {patient_id}")
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch latest vital: {str(e)}")

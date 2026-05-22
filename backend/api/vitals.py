"""
Vitals Management API

Rebuilt onto the unified foundation (2026-05-22). The original Sprint-1.3
router was removed as dead because it had drifted from the schema: it wrote
API field names (blood_pressure_systolic / weight / measurement_date /
oxygen_saturation / height) that DON'T exist on the real `vitals` table
(bp_systolic / weight_kg / measured_datetime / spo2 / height_cm), so every
insert it attempted was a dead write. It also had no tenancy.

VitalsManagement.jsx (the Professional EHR vitals tab) is a live consumer,
so the router is rebuilt — not re-deleted:
  * workspace_id from the authenticated TOKEN (current_user), scoped on every
    read, set on every write; _require_patient on writes (404 if foreign).
  * the frontend's API contract (blood_pressure_systolic / weight / ... ) is
    preserved; internally it maps to the real columns (bp_systolic / weight_kg
    / ...), exactly like the diagnoses rebuild.
  * gating lives in the central ROUTE_CAPABILITIES map (vitals_station).

Manual vitals recorded from the EHR are not necessarily tied to a formal
encounter, so encounter_id is nullable (migration 035); digitisation-promoted
vitals still carry their encounter.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from app.api.auth import get_current_user

router = APIRouter()


class VitalCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    measurement_date: Optional[str] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    notes: Optional[str] = None


class VitalResponse(BaseModel):
    id: str
    patient_id: str
    encounter_id: Optional[str]
    measurement_date: Optional[str]
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
    created_at: Optional[str]


def _to_response(row: dict) -> dict:
    """Map real DB columns -> the API contract field names."""
    return {
        'id': row['id'],
        'patient_id': row.get('patient_id'),
        'encounter_id': row.get('encounter_id'),
        'measurement_date': row.get('measured_datetime'),
        'blood_pressure_systolic': row.get('bp_systolic'),
        'blood_pressure_diastolic': row.get('bp_diastolic'),
        'heart_rate': row.get('heart_rate'),
        'temperature': float(row['temperature']) if row.get('temperature') is not None else None,
        'respiratory_rate': row.get('respiratory_rate'),
        'oxygen_saturation': row.get('spo2'),
        'weight': float(row['weight_kg']) if row.get('weight_kg') is not None else None,
        'height': float(row['height_cm']) if row.get('height_cm') is not None else None,
        'bmi': float(row['bmi']) if row.get('bmi') is not None else None,
        'notes': row.get('notes'),
        'created_at': row.get('created_at'),
    }


def _require_patient(supabase, patient_id: str, workspace_id: str):
    res = supabase.table('patients').select('id').eq('id', patient_id).eq('workspace_id', workspace_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Patient not found")


@router.post("/vitals", response_model=VitalResponse)
async def create_vital(vital: VitalCreate, current_user: dict = Depends(get_current_user)):
    """Record vital signs for a patient in the caller's workspace."""
    from server import supabase
    try:
        workspace_id = current_user["workspace_id"]
        _require_patient(supabase, vital.patient_id, workspace_id)

        # If tied to an encounter, that encounter must be in the workspace too.
        if vital.encounter_id:
            enc = supabase.table('encounters').select('id')\
                .eq('id', vital.encounter_id).eq('workspace_id', workspace_id).execute()
            if not enc.data:
                raise HTTPException(status_code=404, detail="Encounter not found")

        measured = vital.measurement_date or datetime.now(timezone.utc).isoformat()
        row = {
            'id': str(uuid.uuid4()),
            'workspace_id': workspace_id,
            'tenant_id': current_user.get("tenant_id") or workspace_id,
            'patient_id': vital.patient_id,
            'encounter_id': vital.encounter_id,
            'measured_datetime': measured,
            'bp_systolic': vital.blood_pressure_systolic,
            'bp_diastolic': vital.blood_pressure_diastolic,
            'heart_rate': vital.heart_rate,
            'temperature': vital.temperature,
            'respiratory_rate': vital.respiratory_rate,
            'spo2': vital.oxygen_saturation,
            'weight_kg': vital.weight,
            'height_cm': vital.height,   # bmi is a GENERATED column — never inserted
            'notes': vital.notes,
            'source': 'manual_entry',
            'measured_by': current_user.get("email") or "system",
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': current_user.get("email") or "system",
        }
        result = supabase.table('vitals').insert(row).execute()
        return _to_response(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create vital: {str(e)}")


@router.get("/vitals/patient/{patient_id}", response_model=List[VitalResponse])
async def get_patient_vitals(
    patient_id: str,
    limit: int = Query(20, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Get a patient's vitals (caller's workspace only), newest first."""
    from server import supabase
    try:
        result = supabase.table('vitals').select('*')\
            .eq('workspace_id', current_user["workspace_id"])\
            .eq('patient_id', patient_id)\
            .order('measured_datetime', desc=True)\
            .limit(limit)\
            .execute()
        return [_to_response(r) for r in (result.data or [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vitals: {str(e)}")


@router.delete("/vitals/{vital_id}")
async def delete_vital(vital_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a vitals record in the caller's workspace."""
    from server import supabase
    try:
        result = supabase.table('vitals').delete()\
            .eq('id', vital_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Vital signs record not found")
        return {"status": "success", "message": f"Vital {vital_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete vital: {str(e)}")

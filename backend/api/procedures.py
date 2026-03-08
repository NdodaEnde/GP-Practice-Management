"""
Procedures API endpoints
Track surgical and medical procedures
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import os
from supabase import create_client
import uuid

router = APIRouter()

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# =============================================
# REQUEST/RESPONSE MODELS
# =============================================

class ProcedureCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    procedure_code: Optional[str] = None
    procedure_name: str
    procedure_category: Optional[str] = None  # Surgery, Diagnostic, Therapeutic, Preventive
    procedure_datetime: str
    duration_minutes: Optional[int] = None
    indication: Optional[str] = None
    anatomical_site: Optional[str] = None
    laterality: Optional[str] = None  # left, right, bilateral, not_applicable
    performing_provider: Optional[str] = None
    primary_surgeon: Optional[str] = None
    status: str = 'completed'  # scheduled, in_progress, completed, cancelled
    outcome: Optional[str] = None  # successful, partial, complicated, failed
    operative_notes: Optional[str] = None
    complications: Optional[str] = None
    billable: bool = True
    billing_code: Optional[str] = None
    tariff_amount: Optional[float] = None
    follow_up_required: bool = False
    follow_up_date: Optional[str] = None


class ProcedureUpdate(BaseModel):
    procedure_name: Optional[str] = None
    status: Optional[str] = None
    outcome: Optional[str] = None
    operative_notes: Optional[str] = None
    post_operative_notes: Optional[str] = None
    complications: Optional[str] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[str] = None


class Procedure(BaseModel):
    id: str
    patient_id: str
    encounter_id: Optional[str]
    procedure_name: str
    procedure_code: Optional[str]
    procedure_category: Optional[str]
    procedure_datetime: str
    performing_provider: Optional[str]
    status: str
    outcome: Optional[str]
    billable: bool
    created_at: str


# =============================================
# PROCEDURES ENDPOINTS
# =============================================

@router.post("/procedures", response_model=Procedure)
async def create_procedure(procedure: ProcedureCreate):
    """Create a new procedure record"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        tenant_id = os.getenv('DEMO_TENANT_ID')
        
        procedure_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            'patient_id': procedure.patient_id,
            'encounter_id': procedure.encounter_id,
            'procedure_code': procedure.procedure_code,
            'procedure_name': procedure.procedure_name,
            'procedure_category': procedure.procedure_category,
            'procedure_datetime': procedure.procedure_datetime,
            'duration_minutes': procedure.duration_minutes,
            'indication': procedure.indication,
            'anatomical_site': procedure.anatomical_site,
            'laterality': procedure.laterality,
            'performing_provider': procedure.performing_provider,
            'primary_surgeon': procedure.primary_surgeon,
            'status': procedure.status,
            'outcome': procedure.outcome,
            'operative_notes': procedure.operative_notes,
            'complications': procedure.complications,
            'billable': procedure.billable,
            'billing_code': procedure.billing_code,
            'tariff_amount': procedure.tariff_amount,
            'follow_up_required': procedure.follow_up_required,
            'follow_up_date': procedure.follow_up_date,
            'source': 'manual_entry',
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('procedures').insert(procedure_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create procedure")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating procedure: {str(e)}")


@router.get("/procedures/patient/{patient_id}", response_model=List[Procedure])
async def get_patient_procedures(
    patient_id: str,
    limit: int = Query(50, le=200),
    category: Optional[str] = None,
    status: Optional[str] = None
):
    """Get all procedures for a patient"""
    try:
        query = supabase.table('procedures')\
            .select('*')\
            .eq('patient_id', patient_id)
        
        if category:
            query = query.eq('procedure_category', category)
        
        if status:
            query = query.eq('status', status)
        
        result = query.order('procedure_datetime', desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching procedures: {str(e)}")


@router.get("/procedures/encounter/{encounter_id}", response_model=List[Procedure])
async def get_encounter_procedures(encounter_id: str):
    """Get all procedures for an encounter"""
    try:
        result = supabase.table('procedures')\
            .select('*')\
            .eq('encounter_id', encounter_id)\
            .order('procedure_datetime', desc=True)\
            .execute()
        
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching encounter procedures: {str(e)}")


@router.get("/procedures/{procedure_id}", response_model=Procedure)
async def get_procedure(procedure_id: str):
    """Get specific procedure details"""
    try:
        result = supabase.table('procedures')\
            .select('*')\
            .eq('id', procedure_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Procedure not found")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching procedure: {str(e)}")


@router.put("/procedures/{procedure_id}", response_model=Procedure)
async def update_procedure(procedure_id: str, procedure_update: ProcedureUpdate):
    """Update procedure details"""
    try:
        update_data = {'updated_at': datetime.utcnow().isoformat()}
        
        if procedure_update.procedure_name is not None:
            update_data['procedure_name'] = procedure_update.procedure_name
        if procedure_update.status is not None:
            update_data['status'] = procedure_update.status
        if procedure_update.outcome is not None:
            update_data['outcome'] = procedure_update.outcome
        if procedure_update.operative_notes is not None:
            update_data['operative_notes'] = procedure_update.operative_notes
        if procedure_update.post_operative_notes is not None:
            update_data['post_operative_notes'] = procedure_update.post_operative_notes
        if procedure_update.complications is not None:
            update_data['complications'] = procedure_update.complications
        if procedure_update.follow_up_required is not None:
            update_data['follow_up_required'] = procedure_update.follow_up_required
        if procedure_update.follow_up_date is not None:
            update_data['follow_up_date'] = procedure_update.follow_up_date
        
        result = supabase.table('procedures')\
            .update(update_data)\
            .eq('id', procedure_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Procedure not found")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating procedure: {str(e)}")


@router.get("/procedures/patient/{patient_id}/category/{category}")
async def get_procedures_by_category(patient_id: str, category: str):
    """Get patient procedures filtered by category"""
    try:
        result = supabase.table('procedures')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('procedure_category', category)\
            .order('procedure_datetime', desc=True)\
            .execute()
        
        return {
            'patient_id': patient_id,
            'category': category,
            'count': len(result.data or []),
            'procedures': result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching procedures by category: {str(e)}")


@router.get("/procedures/patient/{patient_id}/surgical-history")
async def get_surgical_history(patient_id: str):
    """Get complete surgical history for a patient"""
    try:
        result = supabase.table('procedures')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('procedure_category', 'Surgery')\
            .order('procedure_datetime', desc=True)\
            .execute()
        
        return {
            'patient_id': patient_id,
            'total_surgeries': len(result.data or []),
            'procedures': result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching surgical history: {str(e)}")


@router.get("/procedures/patient/{patient_id}/billable")
async def get_billable_procedures(patient_id: str):
    """Get all billable procedures for a patient"""
    try:
        result = supabase.table('procedures')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('billable', True)\
            .eq('status', 'completed')\
            .order('procedure_datetime', desc=True)\
            .execute()
        
        total_tariff = sum(float(p.get('tariff_amount', 0) or 0) for p in result.data or [])
        
        return {
            'patient_id': patient_id,
            'billable_count': len(result.data or []),
            'total_tariff': total_tariff,
            'procedures': result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching billable procedures: {str(e)}")


@router.get("/procedures/follow-up/due")
async def get_due_follow_ups():
    """Get all procedures with follow-up due"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        today = date.today().isoformat()
        
        result = supabase.table('procedures')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .eq('follow_up_required', True)\
            .lte('follow_up_date', today)\
            .order('follow_up_date')\
            .execute()
        
        return {
            'due_count': len(result.data or []),
            'procedures': result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching due follow-ups: {str(e)}")


@router.delete("/procedures/{procedure_id}")
async def delete_procedure(procedure_id: str):
    """Delete a procedure record"""
    try:
        result = supabase.table('procedures')\
            .delete()\
            .eq('id', procedure_id)\
            .execute()
        
        return {
            'status': 'success',
            'message': 'Procedure deleted successfully'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting procedure: {str(e)}")

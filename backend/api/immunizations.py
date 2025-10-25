"""
Immunizations API endpoints
Track vaccinations and immunization schedules
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

class ImmunizationCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    vaccine_code: Optional[str] = None
    vaccine_name: str
    vaccine_type: Optional[str] = None  # COVID-19, Influenza, Hepatitis B, etc.
    manufacturer: Optional[str] = None
    lot_number: Optional[str] = None
    administration_date: str
    dose_number: Optional[int] = None
    dose_quantity: Optional[float] = None
    dose_unit: Optional[str] = None
    route: Optional[str] = None  # Intramuscular, Subcutaneous, Oral
    anatomical_site: Optional[str] = None
    series_name: Optional[str] = None
    doses_in_series: Optional[int] = None
    series_complete: bool = False
    next_dose_due: Optional[str] = None
    administered_by: Optional[str] = None
    status: str = 'completed'
    clinical_notes: Optional[str] = None
    occupational_requirement: bool = False
    billable: bool = True
    vaccine_cost: Optional[float] = None
    administration_fee: Optional[float] = None


class ImmunizationUpdate(BaseModel):
    vaccine_name: Optional[str] = None
    series_complete: Optional[bool] = None
    next_dose_due: Optional[str] = None
    adverse_reaction: Optional[bool] = None
    reaction_description: Optional[str] = None
    clinical_notes: Optional[str] = None


class Immunization(BaseModel):
    id: str
    patient_id: str
    vaccine_name: str
    vaccine_type: Optional[str]
    administration_date: str
    dose_number: Optional[int]
    route: Optional[str]
    anatomical_site: Optional[str]
    series_name: Optional[str]
    doses_in_series: Optional[int]
    status: str
    series_complete: bool
    next_dose_due: Optional[str]
    administered_by: Optional[str]
    occupational_requirement: bool
    created_at: str


# =============================================
# IMMUNIZATIONS ENDPOINTS
# =============================================

@router.post("/immunizations", response_model=Immunization)
async def create_immunization(immunization: ImmunizationCreate):
    """Create a new immunization record"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        tenant_id = os.getenv('DEMO_TENANT_ID')
        
        immunization_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            'patient_id': immunization.patient_id,
            'encounter_id': immunization.encounter_id,
            'vaccine_code': immunization.vaccine_code,
            'vaccine_name': immunization.vaccine_name,
            'vaccine_type': immunization.vaccine_type,
            'manufacturer': immunization.manufacturer,
            'lot_number': immunization.lot_number,
            'administration_date': immunization.administration_date,
            'dose_number': immunization.dose_number,
            'dose_quantity': immunization.dose_quantity,
            'dose_unit': immunization.dose_unit,
            'route': immunization.route,
            'anatomical_site': immunization.anatomical_site,
            'series_name': immunization.series_name,
            'doses_in_series': immunization.doses_in_series,
            'series_complete': immunization.series_complete,
            'next_dose_due': immunization.next_dose_due,
            'administered_by': immunization.administered_by,
            'status': immunization.status,
            'clinical_notes': immunization.clinical_notes,
            'occupational_requirement': immunization.occupational_requirement,
            'billable': immunization.billable,
            'vaccine_cost': immunization.vaccine_cost,
            'administration_fee': immunization.administration_fee,
            'source': 'manual_entry',
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('immunizations').insert(immunization_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create immunization")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating immunization: {str(e)}")


@router.get("/immunizations/patient/{patient_id}", response_model=List[Immunization])
async def get_patient_immunizations(
    patient_id: str,
    limit: int = Query(100, le=500),
    vaccine_type: Optional[str] = None
):
    """Get all immunizations for a patient"""
    try:
        query = supabase.table('immunizations')\
            .select('*')\
            .eq('patient_id', patient_id)
        
        if vaccine_type:
            query = query.eq('vaccine_type', vaccine_type)
        
        result = query.order('administration_date', desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching immunizations: {str(e)}")


@router.get("/immunizations/{immunization_id}", response_model=Immunization)
async def get_immunization(immunization_id: str):
    """Get specific immunization details"""
    try:
        result = supabase.table('immunizations')\
            .select('*')\
            .eq('id', immunization_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Immunization not found")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching immunization: {str(e)}")


@router.put("/immunizations/{immunization_id}", response_model=Immunization)
async def update_immunization(immunization_id: str, immunization_update: ImmunizationUpdate):
    """Update immunization details"""
    try:
        update_data = {'updated_at': datetime.utcnow().isoformat()}
        
        if immunization_update.vaccine_name is not None:
            update_data['vaccine_name'] = immunization_update.vaccine_name
        if immunization_update.series_complete is not None:
            update_data['series_complete'] = immunization_update.series_complete
        if immunization_update.next_dose_due is not None:
            update_data['next_dose_due'] = immunization_update.next_dose_due
        if immunization_update.adverse_reaction is not None:
            update_data['adverse_reaction'] = immunization_update.adverse_reaction
        if immunization_update.reaction_description is not None:
            update_data['reaction_description'] = immunization_update.reaction_description
        if immunization_update.clinical_notes is not None:
            update_data['clinical_notes'] = immunization_update.clinical_notes
        
        result = supabase.table('immunizations')\
            .update(update_data)\
            .eq('id', immunization_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Immunization not found")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating immunization: {str(e)}")


@router.get("/immunizations/patient/{patient_id}/summary")
async def get_immunization_summary(patient_id: str):
    """Get immunization summary by vaccine type"""
    try:
        # Get all immunizations
        immunizations = supabase.table('immunizations')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('status', 'completed')\
            .execute()
        
        # Group by vaccine type
        summary = {}
        for imm in immunizations.data or []:
            vaccine_type = imm.get('vaccine_type', 'Unknown')
            if vaccine_type not in summary:
                summary[vaccine_type] = {
                    'total_doses': 0,
                    'doses_in_series': None,
                    'last_dose_date': None,
                    'next_due_date': None,
                    'series_complete': False
                }
            
            summary[vaccine_type]['total_doses'] += 1
            
            # Track doses in series (use the most recent or highest value)
            doses_in_series = imm.get('doses_in_series')
            if doses_in_series:
                if not summary[vaccine_type]['doses_in_series'] or doses_in_series > summary[vaccine_type]['doses_in_series']:
                    summary[vaccine_type]['doses_in_series'] = doses_in_series
            
            # Track most recent dose
            admin_date = imm.get('administration_date')
            if not summary[vaccine_type]['last_dose_date'] or admin_date > summary[vaccine_type]['last_dose_date']:
                summary[vaccine_type]['last_dose_date'] = admin_date
            
            # Track next due date
            next_due = imm.get('next_dose_due')
            if next_due:
                if not summary[vaccine_type]['next_due_date'] or next_due < summary[vaccine_type]['next_due_date']:
                    summary[vaccine_type]['next_due_date'] = next_due
            
            # Check if any series is complete
            if imm.get('series_complete'):
                summary[vaccine_type]['series_complete'] = True
        
        return {
            'patient_id': patient_id,
            'summary': summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching immunization summary: {str(e)}")


@router.get("/immunizations/patient/{patient_id}/occupational")
async def get_occupational_immunizations(patient_id: str):
    """Get occupational health immunizations"""
    try:
        result = supabase.table('immunizations')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('occupational_requirement', True)\
            .order('administration_date', desc=True)\
            .execute()
        
        return {
            'patient_id': patient_id,
            'count': len(result.data or []),
            'immunizations': result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching occupational immunizations: {str(e)}")


@router.get("/immunizations/overdue")
async def get_overdue_immunizations():
    """Get all overdue immunizations in workspace"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        today = date.today().isoformat()
        
        result = supabase.table('immunizations')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .eq('status', 'completed')\
            .eq('series_complete', False)\
            .lt('next_dose_due', today)\
            .order('next_dose_due')\
            .execute()
        
        return {
            'overdue_count': len(result.data or []),
            'immunizations': result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching overdue immunizations: {str(e)}")


@router.get("/immunizations/patient/{patient_id}/series/{series_name}")
async def get_series_progress(patient_id: str, series_name: str):
    """Get progress of a vaccination series"""
    try:
        result = supabase.table('immunizations')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .ilike('series_name', f'%{series_name}%')\
            .order('dose_number')\
            .execute()
        
        doses = result.data or []
        total_in_series = doses[0].get('doses_in_series') if doses else None
        completed_doses = len([d for d in doses if d.get('status') == 'completed'])
        series_complete = any(d.get('series_complete') for d in doses)
        
        return {
            'patient_id': patient_id,
            'series_name': series_name,
            'total_doses_in_series': total_in_series,
            'completed_doses': completed_doses,
            'series_complete': series_complete,
            'doses': doses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching series progress: {str(e)}")


@router.get("/immunizations/patient/{patient_id}/certificate")
async def get_immunization_certificates(patient_id: str):
    """Get all immunization certificates for a patient"""
    try:
        result = supabase.table('immunizations')\
            .select('*')\
            .eq('patient_id', patient_id)\
            .eq('certificate_issued', True)\
            .order('administration_date', desc=True)\
            .execute()
        
        return {
            'patient_id': patient_id,
            'certificates_count': len(result.data or []),
            'certificates': result.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching certificates: {str(e)}")


@router.delete("/immunizations/{immunization_id}")
async def delete_immunization(immunization_id: str):
    """Delete an immunization record"""
    try:
        supabase.table('immunizations')\
            .delete()\
            .eq('id', immunization_id)\
            .execute()
        
        return {
            'status': 'success',
            'message': 'Immunization deleted successfully'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting immunization: {str(e)}")

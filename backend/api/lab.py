"""
Lab Orders & Results API endpoints
Track laboratory tests, orders, and results.

Rebuilt onto the unified foundation: lab_orders carry workspace_id from the
authenticated TOKEN (not DEMO_WORKSPACE_ID) and are scoped on every read/write;
lab_results have no workspace_id column, so they are scoped via their parent
order's ownership. Gating lives in the central ROUTE_CAPABILITIES map
(patient_ehr_basic).
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import os
import uuid
from supabase import create_client

from app.api.auth import get_current_user

router = APIRouter()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# =============================================
# REQUEST/RESPONSE MODELS
# =============================================

class LabOrderCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    order_number: Optional[str] = None
    ordering_provider: Optional[str] = None
    priority: str = 'routine'
    lab_name: Optional[str] = None
    indication: Optional[str] = None
    clinical_notes: Optional[str] = None
    icd10_code: Optional[str] = None


class LabResultCreate(BaseModel):
    lab_order_id: str
    test_name: str
    result_value: str
    result_numeric: Optional[float] = None
    units: Optional[str] = None
    reference_range: Optional[str] = None
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    abnormal_flag: str = 'unknown'
    test_category: Optional[str] = None
    specimen_type: Optional[str] = None
    interpretation: Optional[str] = None
    comments: Optional[str] = None


class LabOrder(BaseModel):
    id: str
    patient_id: str
    encounter_id: Optional[str]
    order_number: Optional[str]
    order_datetime: str
    ordering_provider: Optional[str]
    priority: str
    lab_name: Optional[str]
    status: str
    indication: Optional[str]
    clinical_notes: Optional[str]
    created_at: str


class LabResult(BaseModel):
    id: str
    lab_order_id: str
    test_name: str
    result_value: str
    result_numeric: Optional[float]
    units: Optional[str]
    reference_range: Optional[str]
    abnormal_flag: str
    test_category: Optional[str]
    result_datetime: Optional[str]
    created_at: str


def _require_patient(patient_id: str, workspace_id: str):
    if not supabase.table('patients').select('id').eq('id', patient_id).eq('workspace_id', workspace_id).execute().data:
        raise HTTPException(status_code=404, detail="Patient not found")


def _require_order(order_id: str, workspace_id: str):
    """The lab order must belong to the caller's workspace, else 404."""
    res = supabase.table('lab_orders').select('id').eq('id', order_id).eq('workspace_id', workspace_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Lab order not found")


# =============================================
# LAB ORDERS
# =============================================

@router.post("/lab-orders", response_model=LabOrder)
async def create_lab_order(order: LabOrderCreate, current_user: dict = Depends(get_current_user)):
    """Create a lab order for a patient in the caller's workspace."""
    try:
        workspace_id = current_user["workspace_id"]
        _require_patient(order.patient_id, workspace_id)
        order_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': current_user.get("tenant_id") or workspace_id,
            'workspace_id': workspace_id,
            'patient_id': order.patient_id,
            'encounter_id': order.encounter_id,
            'order_number': order.order_number,
            'ordering_provider': order.ordering_provider or current_user.get("email"),
            'priority': order.priority,
            'lab_name': order.lab_name,
            'indication': order.indication,
            'clinical_notes': order.clinical_notes,
            'icd10_code': order.icd10_code,
            'status': 'ordered',
            'order_datetime': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        result = supabase.table('lab_orders').insert(order_data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create lab order")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lab order: {str(e)}")


@router.get("/lab-orders/patient/{patient_id}", response_model=List[LabOrder])
async def get_patient_lab_orders(patient_id: str, limit: int = Query(50, le=200),
                                 status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Get a patient's lab orders (caller's workspace only)."""
    try:
        query = supabase.table('lab_orders').select('*')\
            .eq('workspace_id', current_user["workspace_id"]).eq('patient_id', patient_id)
        if status:
            query = query.eq('status', status)
        return query.order('order_datetime', desc=True).limit(limit).execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching lab orders: {str(e)}")


@router.get("/lab-orders/{order_id}", response_model=LabOrder)
async def get_lab_order(order_id: str, current_user: dict = Depends(get_current_user)):
    """Get a lab order in the caller's workspace."""
    try:
        result = supabase.table('lab_orders').select('*')\
            .eq('id', order_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Lab order not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching lab order: {str(e)}")


@router.put("/lab-orders/{order_id}/status")
async def update_order_status(order_id: str, status: str, current_user: dict = Depends(get_current_user)):
    """Update a lab order's status (caller's workspace only)."""
    try:
        valid = ['ordered', 'collected', 'received', 'in_progress', 'completed', 'cancelled']
        if status not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
        update_data = {'status': status, 'updated_at': datetime.now(timezone.utc).isoformat()}
        if status == 'completed':
            update_data['results_received_datetime'] = datetime.now(timezone.utc).isoformat()
        result = supabase.table('lab_orders').update(update_data)\
            .eq('id', order_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Lab order not found")
        return {'status': 'success', 'message': f'Order status updated to {status}', 'order': result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating order status: {str(e)}")


@router.delete("/lab-orders/{order_id}")
async def cancel_lab_order(order_id: str, current_user: dict = Depends(get_current_user)):
    """Cancel a lab order in the caller's workspace."""
    try:
        result = supabase.table('lab_orders')\
            .update({'status': 'cancelled', 'updated_at': datetime.now(timezone.utc).isoformat()})\
            .eq('id', order_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Lab order not found")
        return {'status': 'success', 'message': 'Lab order cancelled'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling order: {str(e)}")


# =============================================
# LAB RESULTS (scoped via their parent order's ownership)
# =============================================

@router.post("/lab-results", response_model=LabResult)
async def create_lab_result(result_data: LabResultCreate, current_user: dict = Depends(get_current_user)):
    """Add a result to a lab order in the caller's workspace."""
    try:
        _require_order(result_data.lab_order_id, current_user["workspace_id"])
        abnormal_flag = result_data.abnormal_flag
        if result_data.result_numeric is not None and result_data.reference_low is not None and result_data.reference_high is not None:
            if result_data.result_numeric < result_data.reference_low:
                abnormal_flag = 'low'
            elif result_data.result_numeric > result_data.reference_high:
                abnormal_flag = 'high'
            else:
                abnormal_flag = 'normal'
        result_entry = {
            'id': str(uuid.uuid4()),
            'lab_order_id': result_data.lab_order_id,
            'test_name': result_data.test_name,
            'result_value': result_data.result_value,
            'result_numeric': result_data.result_numeric,
            'units': result_data.units,
            'reference_range': result_data.reference_range,
            'reference_low': result_data.reference_low,
            'reference_high': result_data.reference_high,
            'abnormal_flag': abnormal_flag,
            'test_category': result_data.test_category,
            'specimen_type': result_data.specimen_type,
            'interpretation': result_data.interpretation,
            'comments': result_data.comments,
            'source': 'manual_entry',
            'result_datetime': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        result = supabase.table('lab_results').insert(result_entry).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create lab result")
        # Advance the order to completed (scoped).
        order = supabase.table('lab_orders').select('status')\
            .eq('id', result_data.lab_order_id).eq('workspace_id', current_user["workspace_id"]).execute()
        if order.data and order.data[0]['status'] not in ['completed', 'cancelled']:
            supabase.table('lab_orders').update(
                {'status': 'completed', 'results_received_datetime': datetime.now(timezone.utc).isoformat()}
            ).eq('id', result_data.lab_order_id).eq('workspace_id', current_user["workspace_id"]).execute()
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lab result: {str(e)}")


@router.get("/lab-results/order/{order_id}", response_model=List[LabResult])
async def get_results_by_order(order_id: str, current_user: dict = Depends(get_current_user)):
    """Get results for a lab order in the caller's workspace."""
    try:
        _require_order(order_id, current_user["workspace_id"])
        return supabase.table('lab_results').select('*').eq('lab_order_id', order_id)\
            .order('test_name').execute().data or []
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching lab results: {str(e)}")


@router.get("/lab-results/patient/{patient_id}/test/{test_name}")
async def get_patient_test_history(patient_id: str, test_name: str, limit: int = Query(20, le=100),
                                   current_user: dict = Depends(get_current_user)):
    """Historical results for a test (trending) — caller's workspace only."""
    try:
        orders = supabase.table('lab_orders').select('id')\
            .eq('workspace_id', current_user["workspace_id"]).eq('patient_id', patient_id).execute()
        if not orders.data:
            return {'test_name': test_name, 'patient_id': patient_id, 'results_count': 0, 'results': []}
        order_ids = [o['id'] for o in orders.data]
        results = supabase.table('lab_results').select('*').in_('lab_order_id', order_ids)\
            .ilike('test_name', f'%{test_name}%').order('result_datetime', desc=True).limit(limit).execute()
        return {'test_name': test_name, 'patient_id': patient_id,
                'results_count': len(results.data or []), 'results': results.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching test history: {str(e)}")


@router.get("/lab-results/patient/{patient_id}/abnormal")
async def get_patient_abnormal_results(patient_id: str, current_user: dict = Depends(get_current_user)):
    """All abnormal/critical results for a patient — caller's workspace only."""
    try:
        orders = supabase.table('lab_orders').select('id')\
            .eq('workspace_id', current_user["workspace_id"]).eq('patient_id', patient_id).execute()
        if not orders.data:
            return {'patient_id': patient_id, 'abnormal_count': 0, 'results': []}
        order_ids = [o['id'] for o in orders.data]
        results = supabase.table('lab_results').select('*').in_('lab_order_id', order_ids)\
            .in_('abnormal_flag', ['low', 'high', 'critical_low', 'critical_high', 'abnormal'])\
            .order('result_datetime', desc=True).execute()
        return {'patient_id': patient_id, 'abnormal_count': len(results.data or []), 'results': results.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching abnormal results: {str(e)}")

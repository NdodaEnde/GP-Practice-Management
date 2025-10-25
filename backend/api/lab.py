"""
Lab Orders & Results API endpoints
Track laboratory tests, orders, and results
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


# =============================================
# REQUEST/RESPONSE MODELS
# =============================================

class LabOrderCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    order_number: Optional[str] = None
    ordering_provider: Optional[str] = None
    priority: str = 'routine'  # routine, urgent, stat
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
    abnormal_flag: str = 'unknown'  # normal, low, high, critical_low, critical_high
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


# =============================================
# LAB ORDERS ENDPOINTS
# =============================================

@router.post("/lab-orders", response_model=LabOrder)
async def create_lab_order(order: LabOrderCreate):
    """Create a new lab order"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        tenant_id = os.getenv('DEMO_TENANT_ID')
        
        order_data = {
            'id': str(uuid.uuid4()),
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            'patient_id': order.patient_id,
            'encounter_id': order.encounter_id,
            'order_number': order.order_number,
            'ordering_provider': order.ordering_provider,
            'priority': order.priority,
            'lab_name': order.lab_name,
            'indication': order.indication,
            'clinical_notes': order.clinical_notes,
            'icd10_code': order.icd10_code,
            'status': 'ordered',
            'order_datetime': datetime.utcnow().isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('lab_orders').insert(order_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create lab order")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lab order: {str(e)}")


@router.get("/lab-orders/patient/{patient_id}", response_model=List[LabOrder])
async def get_patient_lab_orders(
    patient_id: str,
    limit: int = Query(50, le=200),
    status: Optional[str] = None
):
    """Get all lab orders for a patient"""
    try:
        query = supabase.table('lab_orders')\
            .select('*')\
            .eq('patient_id', patient_id)
        
        if status:
            query = query.eq('status', status)
        
        result = query.order('order_datetime', desc=True)\
            .limit(limit)\
            .execute()
        
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching lab orders: {str(e)}")


@router.get("/lab-orders/{order_id}", response_model=LabOrder)
async def get_lab_order(order_id: str):
    """Get specific lab order"""
    try:
        result = supabase.table('lab_orders')\
            .select('*')\
            .eq('id', order_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Lab order not found")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching lab order: {str(e)}")


@router.put("/lab-orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    """Update lab order status"""
    try:
        valid_statuses = ['ordered', 'collected', 'received', 'in_progress', 'completed', 'cancelled']
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        update_data = {
            'status': status,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # If completing, set results received datetime
        if status == 'completed':
            update_data['results_received_datetime'] = datetime.utcnow().isoformat()
        
        result = supabase.table('lab_orders')\
            .update(update_data)\
            .eq('id', order_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Lab order not found")
        
        return {
            'status': 'success',
            'message': f'Order status updated to {status}',
            'order': result.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating order status: {str(e)}")


# =============================================
# LAB RESULTS ENDPOINTS
# =============================================

@router.post("/lab-results", response_model=LabResult)
async def create_lab_result(result_data: LabResultCreate):
    """Create a new lab result (manual entry)"""
    try:
        # Auto-determine abnormal flag if numeric values provided
        abnormal_flag = result_data.abnormal_flag
        if result_data.result_numeric and result_data.reference_low and result_data.reference_high:
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
            'result_datetime': datetime.utcnow().isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('lab_results').insert(result_entry).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create lab result")
        
        # Update order status if not already completed
        order = supabase.table('lab_orders').select('status').eq('id', result_data.lab_order_id).execute()
        if order.data and order.data[0]['status'] not in ['completed', 'cancelled']:
            supabase.table('lab_orders')\
                .update({'status': 'completed', 'results_received_datetime': datetime.utcnow().isoformat()})\
                .eq('id', result_data.lab_order_id)\
                .execute()
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating lab result: {str(e)}")


@router.get("/lab-results/order/{order_id}", response_model=List[LabResult])
async def get_results_by_order(order_id: str):
    """Get all results for a specific lab order"""
    try:
        result = supabase.table('lab_results')\
            .select('*')\
            .eq('lab_order_id', order_id)\
            .order('test_name')\
            .execute()
        
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching lab results: {str(e)}")


@router.get("/lab-results/patient/{patient_id}/test/{test_name}")
async def get_patient_test_history(
    patient_id: str,
    test_name: str,
    limit: int = Query(20, le=100)
):
    """Get historical results for a specific test (for trending)"""
    try:
        # Get all orders for patient
        orders = supabase.table('lab_orders')\
            .select('id')\
            .eq('patient_id', patient_id)\
            .execute()
        
        if not orders.data:
            return []
        
        order_ids = [order['id'] for order in orders.data]
        
        # Get results matching test name
        results = supabase.table('lab_results')\
            .select('*')\
            .in_('lab_order_id', order_ids)\
            .ilike('test_name', f'%{test_name}%')\
            .order('result_datetime', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            'test_name': test_name,
            'patient_id': patient_id,
            'results_count': len(results.data or []),
            'results': results.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching test history: {str(e)}")


@router.get("/lab-results/patient/{patient_id}/abnormal")
async def get_patient_abnormal_results(patient_id: str):
    """Get all abnormal/critical results for a patient"""
    try:
        # Get all orders for patient
        orders = supabase.table('lab_orders')\
            .select('id, order_datetime, lab_name')\
            .eq('patient_id', patient_id)\
            .execute()
        
        if not orders.data:
            return []
        
        order_ids = [order['id'] for order in orders.data]
        
        # Get abnormal results
        results = supabase.table('lab_results')\
            .select('*')\
            .in_('lab_order_id', order_ids)\
            .in_('abnormal_flag', ['low', 'high', 'critical_low', 'critical_high', 'abnormal'])\
            .order('result_datetime', desc=True)\
            .execute()
        
        return {
            'patient_id': patient_id,
            'abnormal_count': len(results.data or []),
            'results': results.data or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching abnormal results: {str(e)}")


@router.delete("/lab-orders/{order_id}")
async def cancel_lab_order(order_id: str):
    """Cancel a lab order"""
    try:
        result = supabase.table('lab_orders')\
            .update({'status': 'cancelled', 'updated_at': datetime.utcnow().isoformat()})\
            .eq('id', order_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Lab order not found")
        
        return {
            'status': 'success',
            'message': 'Lab order cancelled'
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling order: {str(e)}")

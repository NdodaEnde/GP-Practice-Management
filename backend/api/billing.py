"""
Billing API endpoints
Invoice generation, payments, and medical aid claims
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
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

class InvoiceItemCreate(BaseModel):
    item_type: str  # consultation, medication, procedure, lab_test, immunization
    description: str
    quantity: float = 1
    unit_price: float
    icd10_code: Optional[str] = None
    nappi_code: Optional[str] = None
    procedure_code: Optional[str] = None
    prescription_item_id: Optional[str] = None
    procedure_id: Optional[str] = None
    lab_order_id: Optional[str] = None
    immunization_id: Optional[str] = None


class InvoiceCreate(BaseModel):
    patient_id: str
    encounter_id: Optional[str] = None
    invoice_date: str  # YYYY-MM-DD
    items: List[InvoiceItemCreate]
    medical_aid_name: Optional[str] = None
    medical_aid_number: Optional[str] = None
    medical_aid_plan: Optional[str] = None
    medical_aid_portion: Optional[float] = None
    patient_portion: Optional[float] = None
    notes: Optional[str] = None


class PaymentCreate(BaseModel):
    invoice_id: str
    payment_date: str  # YYYY-MM-DD
    amount: float
    payment_method: str  # cash, card, eft, medical_aid
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class ClaimCreate(BaseModel):
    invoice_id: str
    medical_aid_name: str
    medical_aid_number: str
    medical_aid_plan: Optional[str] = None
    claim_amount: float
    primary_diagnosis_code: str
    primary_diagnosis_description: str
    secondary_diagnosis_codes: Optional[List[str]] = None
    notes: Optional[str] = None


# =============================================
# INVOICE ENDPOINTS
# =============================================

@router.post("/invoices")
async def create_invoice(invoice: InvoiceCreate):
    """Create a new invoice from encounter or manual entry"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        tenant_id = os.getenv('DEMO_TENANT_ID')
        
        # Generate invoice number (format: INV-YYYYMMDD-XXXX)
        today = datetime.now().strftime('%Y%m%d')
        count_result = supabase.table('invoices')\
            .select('id', count='exact')\
            .execute()
        invoice_number = f"INV-{today}-{(count_result.count + 1):04d}"
        
        # Calculate totals
        subtotal = sum(item.quantity * item.unit_price for item in invoice.items)
        vat_amount = subtotal * 0.15  # 15% VAT in South Africa
        total_amount = subtotal + vat_amount
        
        # Determine payment portions
        if invoice.medical_aid_portion is not None:
            medical_aid_portion = invoice.medical_aid_portion
            patient_portion = total_amount - medical_aid_portion
        else:
            medical_aid_portion = 0
            patient_portion = total_amount
        
        # Create invoice
        invoice_id = str(uuid.uuid4())
        invoice_data = {
            'id': invoice_id,
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            'patient_id': invoice.patient_id,
            'encounter_id': invoice.encounter_id,
            'invoice_number': invoice_number,
            'invoice_date': invoice.invoice_date,
            'due_date': (datetime.strptime(invoice.invoice_date, '%Y-%m-%d') + timedelta(days=30)).strftime('%Y-%m-%d'),
            'subtotal': float(subtotal),
            'vat_amount': float(vat_amount),
            'total_amount': float(total_amount),
            'amount_paid': 0,
            'amount_outstanding': float(total_amount),
            'payment_status': 'unpaid',
            'medical_aid_name': invoice.medical_aid_name,
            'medical_aid_number': invoice.medical_aid_number,
            'medical_aid_plan': invoice.medical_aid_plan,
            'medical_aid_portion': float(medical_aid_portion),
            'patient_portion': float(patient_portion),
            'status': 'issued',
            'notes': invoice.notes,
            'created_at': datetime.utcnow().isoformat(),
            'issued_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('invoices').insert(invoice_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create invoice")
        
        # Create invoice items
        for item in invoice.items:
            item_total = item.quantity * item.unit_price
            item_vat = item_total * 0.15
            
            item_data = {
                'id': str(uuid.uuid4()),
                'invoice_id': invoice_id,
                'item_type': item.item_type,
                'description': item.description,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'total_price': item_total,
                'vat_rate': 15.0,
                'vat_amount': item_vat,
                'icd10_code': item.icd10_code,
                'nappi_code': item.nappi_code,
                'procedure_code': item.procedure_code,
                'prescription_item_id': item.prescription_item_id,
                'procedure_id': item.procedure_id,
                'lab_order_id': item.lab_order_id,
                'immunization_id': item.immunization_id,
                'created_at': datetime.utcnow().isoformat()
            }
            
            supabase.table('invoice_items').insert(item_data).execute()
        
        return {
            'status': 'success',
            'invoice_id': invoice_id,
            'invoice_number': invoice_number,
            'total_amount': total_amount,
            'message': 'Invoice created successfully'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating invoice: {str(e)}")


@router.get("/invoices/patient/{patient_id}")
async def get_patient_invoices(
    patient_id: str,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """Get all invoices for a patient"""
    try:
        query = supabase.table('invoices')\
            .select('*')\
            .eq('patient_id', patient_id)
        
        if status:
            query = query.eq('status', status)
        if payment_status:
            query = query.eq('payment_status', payment_status)
        
        result = query.order('invoice_date', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            'patient_id': patient_id,
            'count': len(result.data or []),
            'invoices': result.data or []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching invoices: {str(e)}")


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    """Get invoice details with items"""
    try:
        # Get invoice
        invoice_result = supabase.table('invoices')\
            .select('*')\
            .eq('id', invoice_id)\
            .execute()
        
        if not invoice_result.data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        invoice = invoice_result.data[0]
        
        # Get invoice items
        items_result = supabase.table('invoice_items')\
            .select('*')\
            .eq('invoice_id', invoice_id)\
            .execute()
        
        invoice['items'] = items_result.data or []
        
        # Get payments
        payments_result = supabase.table('payments')\
            .select('*')\
            .eq('invoice_id', invoice_id)\
            .execute()
        
        invoice['payments'] = payments_result.data or []
        
        return invoice
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching invoice: {str(e)}")


@router.get("/invoices")
async def get_all_invoices(
    payment_status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(100, le=500)
):
    """Get all invoices with filters"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        
        query = supabase.table('invoices')\
            .select('*')\
            .eq('workspace_id', workspace_id)
        
        if payment_status:
            query = query.eq('payment_status', payment_status)
        if from_date:
            query = query.gte('invoice_date', from_date)
        if to_date:
            query = query.lte('invoice_date', to_date)
        
        result = query.order('invoice_date', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            'count': len(result.data or []),
            'invoices': result.data or []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching invoices: {str(e)}")


# =============================================
# PAYMENT ENDPOINTS
# =============================================

@router.post("/payments")
async def record_payment(payment: PaymentCreate):
    """Record a payment for an invoice"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        tenant_id = os.getenv('DEMO_TENANT_ID')
        
        # Get invoice
        invoice_result = supabase.table('invoices')\
            .select('*')\
            .eq('id', payment.invoice_id)\
            .execute()
        
        if not invoice_result.data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        invoice = invoice_result.data[0]
        
        # Create payment record
        payment_id = str(uuid.uuid4())
        payment_data = {
            'id': payment_id,
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            'invoice_id': payment.invoice_id,
            'patient_id': invoice['patient_id'],
            'payment_date': payment.payment_date,
            'amount': payment.amount,
            'payment_method': payment.payment_method,
            'reference_number': payment.reference_number,
            'notes': payment.notes,
            'is_medical_aid_payment': payment.payment_method == 'medical_aid',
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('payments').insert(payment_data).execute()
        
        # Update invoice payment status
        new_amount_paid = float(invoice['amount_paid']) + payment.amount
        new_outstanding = float(invoice['total_amount']) - new_amount_paid
        
        if new_outstanding <= 0:
            new_payment_status = 'paid'
            paid_at = datetime.utcnow().isoformat()
        elif new_amount_paid > 0:
            new_payment_status = 'partially_paid'
            paid_at = None
        else:
            new_payment_status = 'unpaid'
            paid_at = None
        
        supabase.table('invoices')\
            .update({
                'amount_paid': new_amount_paid,
                'amount_outstanding': new_outstanding,
                'payment_status': new_payment_status,
                'paid_at': paid_at,
                'payment_method': payment.payment_method,
                'updated_at': datetime.utcnow().isoformat()
            })\
            .eq('id', payment.invoice_id)\
            .execute()
        
        return {
            'status': 'success',
            'payment_id': payment_id,
            'new_outstanding': new_outstanding,
            'payment_status': new_payment_status,
            'message': 'Payment recorded successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording payment: {str(e)}")


@router.get("/payments/invoice/{invoice_id}")
async def get_invoice_payments(invoice_id: str):
    """Get all payments for an invoice"""
    try:
        result = supabase.table('payments')\
            .select('*')\
            .eq('invoice_id', invoice_id)\
            .order('payment_date', desc=True)\
            .execute()
        
        return {
            'invoice_id': invoice_id,
            'count': len(result.data or []),
            'payments': result.data or []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching payments: {str(e)}")


# =============================================
# MEDICAL AID CLAIMS ENDPOINTS
# =============================================

@router.post("/claims")
async def create_claim(claim: ClaimCreate):
    """Create a medical aid claim from an invoice"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        tenant_id = os.getenv('DEMO_TENANT_ID')
        
        # Get invoice
        invoice_result = supabase.table('invoices')\
            .select('*')\
            .eq('id', claim.invoice_id)\
            .execute()
        
        if not invoice_result.data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        invoice = invoice_result.data[0]
        
        # Generate claim number
        today = datetime.now().strftime('%Y%m%d')
        count_result = supabase.table('medical_aid_claims')\
            .select('id', count='exact')\
            .execute()
        claim_number = f"CLM-{today}-{(count_result.count + 1):04d}"
        
        # Create claim
        claim_id = str(uuid.uuid4())
        claim_data = {
            'id': claim_id,
            'tenant_id': tenant_id,
            'workspace_id': workspace_id,
            'invoice_id': claim.invoice_id,
            'patient_id': invoice['patient_id'],
            'claim_number': claim_number,
            'claim_date': datetime.now().strftime('%Y-%m-%d'),
            'medical_aid_name': claim.medical_aid_name,
            'medical_aid_number': claim.medical_aid_number,
            'medical_aid_plan': claim.medical_aid_plan,
            'claim_amount': claim.claim_amount,
            'status': 'draft',
            'primary_diagnosis_code': claim.primary_diagnosis_code,
            'primary_diagnosis_description': claim.primary_diagnosis_description,
            'secondary_diagnosis_codes': claim.secondary_diagnosis_codes,
            'notes': claim.notes,
            'created_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('medical_aid_claims').insert(claim_data).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create claim")
        
        return {
            'status': 'success',
            'claim_id': claim_id,
            'claim_number': claim_number,
            'message': 'Claim created successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating claim: {str(e)}")


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: str):
    """Get claim details"""
    try:
        result = supabase.table('medical_aid_claims')\
            .select('*')\
            .eq('id', claim_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        return result.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching claim: {str(e)}")


@router.patch("/claims/{claim_id}/status")
async def update_claim_status(
    claim_id: str,
    status: str,
    approved_amount: Optional[float] = None,
    paid_amount: Optional[float] = None,
    rejection_reason: Optional[str] = None,
    rejection_code: Optional[str] = None
):
    """Update claim status"""
    try:
        update_data = {
            'status': status,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if status == 'submitted':
            update_data['submission_date'] = datetime.now().strftime('%Y-%m-%d')
            update_data['submitted_at'] = datetime.utcnow().isoformat()
        elif status in ['approved', 'partially_approved']:
            update_data['response_date'] = datetime.now().strftime('%Y-%m-%d')
            update_data['approved_amount'] = approved_amount
        elif status == 'rejected':
            update_data['response_date'] = datetime.now().strftime('%Y-%m-%d')
            update_data['rejection_reason'] = rejection_reason
            update_data['rejection_code'] = rejection_code
        elif status == 'paid':
            update_data['payment_date'] = datetime.now().strftime('%Y-%m-%d')
            update_data['paid_amount'] = paid_amount
        
        result = supabase.table('medical_aid_claims')\
            .update(update_data)\
            .eq('id', claim_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        return {
            'status': 'success',
            'message': f'Claim status updated to {status}'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating claim: {str(e)}")


@router.get("/claims")
async def get_all_claims(
    status: Optional[str] = None,
    medical_aid: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = Query(100, le=500)
):
    """Get all claims with filters"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        
        query = supabase.table('medical_aid_claims')\
            .select('*')\
            .eq('workspace_id', workspace_id)
        
        if status:
            query = query.eq('status', status)
        if medical_aid:
            query = query.eq('medical_aid_name', medical_aid)
        if from_date:
            query = query.gte('claim_date', from_date)
        if to_date:
            query = query.lte('claim_date', to_date)
        
        result = query.order('claim_date', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            'count': len(result.data or []),
            'claims': result.data or []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching claims: {str(e)}")


# =============================================
# FINANCIAL REPORTS ENDPOINTS
# =============================================

@router.get("/reports/revenue")
async def get_revenue_report(
    from_date: str,
    to_date: str
):
    """Get revenue report for a date range"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        
        # Get all invoices in date range
        invoices_result = supabase.table('invoices')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .gte('invoice_date', from_date)\
            .lte('invoice_date', to_date)\
            .execute()
        
        invoices = invoices_result.data or []
        
        # Calculate totals
        total_invoiced = sum(float(inv.get('total_amount', 0)) for inv in invoices)
        total_paid = sum(float(inv.get('amount_paid', 0)) for inv in invoices)
        total_outstanding = sum(float(inv.get('amount_outstanding', 0)) for inv in invoices)
        
        # Get payments in date range
        payments_result = supabase.table('payments')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .gte('payment_date', from_date)\
            .lte('payment_date', to_date)\
            .execute()
        
        payments = payments_result.data or []
        
        # Payment method breakdown
        payment_methods = {}
        for payment in payments:
            method = payment.get('payment_method', 'unknown')
            payment_methods[method] = payment_methods.get(method, 0) + float(payment.get('amount', 0))
        
        return {
            'from_date': from_date,
            'to_date': to_date,
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'total_outstanding': total_outstanding,
            'invoice_count': len(invoices),
            'payment_count': len(payments),
            'payment_methods': payment_methods
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/reports/outstanding")
async def get_outstanding_report():
    """Get all outstanding invoices"""
    try:
        workspace_id = os.getenv('DEMO_WORKSPACE_ID')
        
        result = supabase.table('invoices')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .in_('payment_status', ['unpaid', 'partially_paid'])\
            .order('invoice_date')\
            .execute()
        
        invoices = result.data or []
        total_outstanding = sum(float(inv.get('amount_outstanding', 0)) for inv in invoices)
        
        return {
            'count': len(invoices),
            'total_outstanding': total_outstanding,
            'invoices': invoices
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

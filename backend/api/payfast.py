"""
PayFast Payment Gateway Integration
Handles online payment processing for medical billing invoices
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
import os
import uuid
import urllib.parse
from hashlib import md5
from datetime import datetime
import logging

router = APIRouter()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PayFast Configuration
PAYFAST_MERCHANT_ID = os.getenv('PAYFAST_MERCHANT_ID')
PAYFAST_MERCHANT_KEY = os.getenv('PAYFAST_MERCHANT_KEY')
PAYFAST_PASSPHRASE = os.getenv('PAYFAST_PASSPHRASE')
PAYFAST_SANDBOX = os.getenv('PAYFAST_SANDBOX', 'True').lower() == 'true'

# PayFast URLs
PAYFAST_URL = "https://sandbox.payfast.co.za/eng/process" if PAYFAST_SANDBOX else "https://www.payfast.co.za/eng/process"

# PayFast valid IPs
PAYFAST_IPS = [
    "197.97.145.144",
    "197.97.145.145",
    "197.97.145.146",
    "197.97.145.147",
    "197.97.145.148"
]

# Signature field order (critical for PayFast)
SIGNATURE_FIELD_ORDER = [
    "merchant_id", "merchant_key", "return_url", "cancel_url", "notify_url",
    "name_first", "name_last", "email_address", "cell_number",
    "m_payment_id", "amount", "item_name", "item_description",
    "custom_int1", "custom_int2", "custom_int3", "custom_int4", "custom_int5",
    "custom_str1", "custom_str2", "custom_str3", "custom_str4", "custom_str5",
    "email_confirmation", "confirmation_address", "payment_method"
]


# =============================================
# REQUEST/RESPONSE MODELS
# =============================================

class PaymentInitiationRequest(BaseModel):
    invoice_id: str
    amount: float
    customer_email: EmailStr
    customer_phone: str
    invoice_number: str
    
    @validator('amount')
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than zero')
        return round(v, 2)


# =============================================
# UTILITY FUNCTIONS
# =============================================

def generate_payfast_signature(data_dict: dict, passphrase: str = None) -> str:
    """
    Generate MD5 signature for PayFast transactions.
    PayFast is very strict about signature generation:
    1. Remove signature field if present
    2. Remove empty values
    3. Sort by keys alphabetically
    4. URL encode values
    5. Create parameter string
    6. Add passphrase at the end ONLY if one is set (NOT URL encoded!)
    7. Generate MD5 hash
    """
    # Remove signature if present
    filtered_data = {k: v for k, v in data_dict.items() if k != 'signature'}
    
    # Remove empty values
    filtered_data = {k: v for k, v in filtered_data.items() if v is not None and str(v).strip() != ''}
    
    # Sort by keys alphabetically (PayFast requirement)
    sorted_keys = sorted(filtered_data.keys())
    
    # Build parameter string with URL encoding
    param_string = ""
    for key in sorted_keys:
        value = str(filtered_data[key]).strip()
        # URL encode the value
        encoded_value = urllib.parse.quote_plus(value)
        param_string += f"{key}={encoded_value}&"
    
    # Remove trailing '&'
    param_string = param_string.rstrip('&')
    
    # Add passphrase ONLY if provided and not empty (CRITICAL: NOT URL encoded!)
    if passphrase and passphrase.strip():
        param_string += f"&passphrase={passphrase}"
        logger.info(f"Signature string WITH passphrase")
    else:
        logger.info(f"Signature string WITHOUT passphrase")
    
    logger.info(f"Signature string: {param_string}")
    
    # Generate MD5 hash
    signature = md5(param_string.encode()).hexdigest()
    logger.info(f"Generated signature: {signature}")
    
    return signature


def verify_payfast_signature(data_dict: dict, passphrase: str, received_signature: str) -> bool:
    """
    Verify PayFast ITN signature.
    """
    generated_signature = generate_payfast_signature(data_dict, passphrase)
    
    logger.info(f"Generated signature: {generated_signature}")
    logger.info(f"Received signature: {received_signature}")
    
    return generated_signature == received_signature


# =============================================
# PAYMENT ENDPOINTS
# =============================================

@router.post("/initiate")
async def initiate_payment(request: PaymentInitiationRequest):
    """
    Initiate PayFast payment for a medical invoice.
    Returns payment URL and data needed for frontend redirect.
    """
    try:
        # Get frontend and backend URLs from environment
        frontend_url = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:3000').replace('/api', '')
        backend_url = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')
        
        # Generate unique payment ID
        payment_id = str(uuid.uuid4())
        
        # Build payment data - only include non-empty values
        payment_data = {
            "merchant_id": PAYFAST_MERCHANT_ID,
            "merchant_key": PAYFAST_MERCHANT_KEY,
            "return_url": f"{frontend_url}/payment/success",
            "cancel_url": f"{frontend_url}/payment/cancelled",
            "notify_url": f"{backend_url}/api/payfast/webhook",
            "name_first": "Medical",
            "name_last": "Patient",
            "email_address": request.customer_email,
            "m_payment_id": payment_id,
            "amount": f"{request.amount:.2f}",
            "item_name": f"Medical Invoice {request.invoice_number}",
            "item_description": "Medical Services Payment",
        }
        
        # Add optional fields only if they have values
        if request.customer_phone and request.customer_phone.strip():
            payment_data["cell_number"] = request.customer_phone
        
        # Add custom fields for tracking
        payment_data["custom_str1"] = request.invoice_id
        payment_data["custom_str2"] = request.invoice_number
        
        # Generate signature (passphrase will be added inside the function)
        signature = generate_payfast_signature(payment_data, PAYFAST_PASSPHRASE)
        payment_data["signature"] = signature
        
        logger.info(f"Payment initiated for invoice {request.invoice_number}, payment_id: {payment_id}")
        logger.info(f"Payment data: {payment_data}")
        
        return {
            "success": True,
            "payment_url": PAYFAST_URL,
            "payment_data": payment_data,
            "payment_id": payment_id
        }
        
    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error initiating payment: {str(e)}")


@router.post("/webhook")
async def handle_payfast_webhook(request: Request):
    """
    Handle PayFast Instant Transaction Notification (ITN) webhook.
    Verifies signature and processes payment confirmation.
    """
    try:
        # Get form data from PayFast
        form_data = await request.form()
        itn_data = dict(form_data)
        
        logger.info(f"ITN received: {itn_data}")
        
        # Extract signature
        received_signature = itn_data.get("signature", "")
        
        # Create copy without signature for verification
        itn_copy = itn_data.copy()
        itn_copy.pop("signature", None)
        
        # Verify signature
        if not verify_payfast_signature(itn_copy, PAYFAST_PASSPHRASE, received_signature):
            logger.error("Signature verification failed")
            return Response(status_code=400, content="Signature verification failed")
        
        # Verify source IP (optional in sandbox)
        source_ip = request.client.host
        if not PAYFAST_SANDBOX and source_ip not in PAYFAST_IPS:
            logger.warning(f"Request from unauthorized IP: {source_ip}")
            return Response(status_code=400, content="Invalid source IP")
        
        # Extract payment details
        payment_status = itn_data.get("payment_status")
        pf_payment_id = itn_data.get("pf_payment_id")
        m_payment_id = itn_data.get("m_payment_id")
        amount_gross = itn_data.get("amount_gross")
        invoice_id = itn_data.get("custom_str1")
        invoice_number = itn_data.get("custom_str2")
        
        logger.info(f"Payment {pf_payment_id} status: {payment_status}, invoice: {invoice_number}")
        
        # Here you would update your database with payment information
        # For now, we'll log it
        
        if payment_status == "COMPLETE":
            logger.info(f"Payment successful for invoice {invoice_number}")
            # TODO: Update invoice status to paid in database
            # TODO: Generate receipt
            # TODO: Send confirmation email
        else:
            logger.warning(f"Payment not complete. Status: {payment_status}")
        
        # Return 200 OK to acknowledge receipt
        return Response(status_code=200, content="OK")
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return Response(status_code=500, content="Internal server error")


@router.get("/payment-status/{payment_id}")
async def get_payment_status(payment_id: str):
    """
    Get payment status by payment ID.
    """
    try:
        # TODO: Query database for payment status
        # For now, return mock data
        
        return {
            "payment_id": payment_id,
            "status": "pending",
            "message": "Payment status check endpoint"
        }
        
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting payment status: {str(e)}")

# Phase 3 Billing System - Backend Testing Guide

## Prerequisites
- Backend is running on port 8001
- Get the REACT_APP_BACKEND_URL from `/app/frontend/.env`
- You'll need a patient ID (get from `/api/patients`)

## Test Sequence

### 1. Get Patient ID for Testing
```bash
curl -X GET "https://docwise-health.preview.emergentagent.com/api/patients"
```
**Expected:** List of patients
**Pick a patient_id** from the response for the following tests.

---

### 2. Create an Invoice
**Test Case:** Create invoice with consultation + medication

```bash
curl -X POST "https://docwise-health.preview.emergentagent.com/api/invoices" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "YOUR_PATIENT_ID_HERE",
    "encounter_id": null,
    "invoice_date": "2025-10-25",
    "items": [
      {
        "item_type": "consultation",
        "description": "General Consultation",
        "quantity": 1,
        "unit_price": 500,
        "icd10_code": "Z00.0"
      },
      {
        "item_type": "medication",
        "description": "Panado 500mg Tablets x20",
        "quantity": 1,
        "unit_price": 50,
        "nappi_code": "111111"
      }
    ],
    "medical_aid_name": "Discovery Health",
    "medical_aid_number": "12345678",
    "medical_aid_plan": "Executive Plan",
    "notes": "Test invoice with medical aid"
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "invoice_id": "uuid-here",
  "invoice_number": "INV-20251025-0001",
  "total_amount": 632.50,
  "message": "Invoice created successfully"
}
```

**Verify:**
- ✅ Invoice number format: INV-YYYYMMDD-XXXX
- ✅ Subtotal: R550.00 (500 + 50)
- ✅ VAT: R82.50 (15% of 550)
- ✅ Total: R632.50

**Save the invoice_id** for next tests.

---

### 3. Retrieve Invoice Details
```bash
curl -X GET "https://docwise-health.preview.emergentagent.com/api/invoices/YOUR_INVOICE_ID_HERE"
```

**Expected Response:**
```json
{
  "id": "invoice_id",
  "invoice_number": "INV-20251025-0001",
  "patient_id": "...",
  "subtotal": 550.00,
  "vat_amount": 82.50,
  "total_amount": 632.50,
  "amount_paid": 0,
  "amount_outstanding": 632.50,
  "payment_status": "unpaid",
  "medical_aid_name": "Discovery Health",
  "items": [
    {
      "item_type": "consultation",
      "description": "General Consultation",
      "unit_price": 500,
      "icd10_code": "Z00.0",
      "nappi_code": null
    },
    {
      "item_type": "medication",
      "description": "Panado 500mg Tablets x20",
      "unit_price": 50,
      "icd10_code": null,
      "nappi_code": "111111"
    }
  ],
  "payments": []
}
```

**Verify:**
- ✅ Items array contains 2 items
- ✅ ICD-10 code on consultation item
- ✅ NAPPI code on medication item
- ✅ Payments array is empty
- ✅ Payment status is "unpaid"

---

### 4. Record Partial Payment (Cash)
```bash
curl -X POST "https://docwise-health.preview.emergentagent.com/api/payments" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "YOUR_INVOICE_ID_HERE",
    "payment_date": "2025-10-25",
    "amount": 300,
    "payment_method": "cash",
    "reference_number": "CASH001",
    "notes": "Partial payment - cash"
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "payment_id": "payment_uuid",
  "new_outstanding": 332.50,
  "payment_status": "partially_paid",
  "message": "Payment recorded successfully"
}
```

**Verify:**
- ✅ Outstanding reduced: 632.50 - 300 = 332.50
- ✅ Payment status changed to "partially_paid"

---

### 5. Verify Payment Recorded
```bash
curl -X GET "https://docwise-health.preview.emergentagent.com/api/invoices/YOUR_INVOICE_ID_HERE"
```

**Verify:**
- ✅ `amount_paid`: 300.00
- ✅ `amount_outstanding`: 332.50
- ✅ `payment_status`: "partially_paid"
- ✅ `payments` array contains 1 payment

---

### 6. Record Second Payment (Complete Payment)
```bash
curl -X POST "https://docwise-health.preview.emergentagent.com/api/payments" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "YOUR_INVOICE_ID_HERE",
    "payment_date": "2025-10-25",
    "amount": 332.50,
    "payment_method": "card",
    "reference_number": "CARD002",
    "notes": "Final payment - card"
  }'
```

**Expected:**
- ✅ `new_outstanding`: 0.00
- ✅ `payment_status`: "paid"

---

### 7. Get Patient Invoices
```bash
curl -X GET "https://docwise-health.preview.emergentagent.com/api/invoices/patient/YOUR_PATIENT_ID_HERE"
```

**Verify:**
- ✅ Returns array of all patient invoices
- ✅ Shows invoice count
- ✅ Most recent invoices first

---

### 8. Get All Invoices (with filters)
```bash
# Get unpaid invoices
curl -X GET "https://docwise-health.preview.emergentagent.com/api/invoices?payment_status=unpaid"

# Get invoices for date range
curl -X GET "https://docwise-health.preview.emergentagent.com/api/invoices?from_date=2025-10-01&to_date=2025-10-31"
```

**Verify:**
- ✅ Filtering by payment_status works
- ✅ Date range filtering works

---

### 9. Create Medical Aid Claim
```bash
curl -X POST "https://docwise-health.preview.emergentagent.com/api/claims" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "YOUR_INVOICE_ID_HERE",
    "medical_aid_name": "Discovery Health",
    "medical_aid_number": "12345678",
    "medical_aid_plan": "Executive Plan",
    "claim_amount": 632.50,
    "primary_diagnosis_code": "Z00.0",
    "primary_diagnosis_description": "General medical examination",
    "secondary_diagnosis_codes": ["I10"],
    "notes": "Routine checkup with medication"
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "claim_id": "claim_uuid",
  "claim_number": "CLM-20251025-0001",
  "message": "Claim created successfully"
}
```

**Verify:**
- ✅ Claim number format: CLM-YYYYMMDD-XXXX
- ✅ Linked to invoice

**Save the claim_id** for next tests.

---

### 10. Retrieve Claim Details
```bash
curl -X GET "https://docwise-health.preview.emergentagent.com/api/claims/YOUR_CLAIM_ID_HERE"
```

**Verify:**
- ✅ Contains claim_number, status ("draft"), medical_aid_name
- ✅ Contains primary_diagnosis_code and description
- ✅ Linked to invoice_id

---

### 11. Update Claim Status to Submitted
```bash
curl -X PATCH "https://docwise-health.preview.emergentagent.com/api/claims/YOUR_CLAIM_ID_HERE/status?status=submitted"
```

**Expected:**
```json
{
  "status": "success",
  "message": "Claim status updated to submitted"
}
```

**Verify:**
- ✅ Status changed to "submitted"
- ✅ `submission_date` set to today
- ✅ `submitted_at` timestamp recorded

---

### 12. Update Claim Status to Approved
```bash
curl -X PATCH "https://docwise-health.preview.emergentagent.com/api/claims/YOUR_CLAIM_ID_HERE/status?status=approved&approved_amount=632.50"
```

**Verify:**
- ✅ Status changed to "approved"
- ✅ `approved_amount` set to 632.50
- ✅ `response_date` recorded

---

### 13. Get All Claims
```bash
# All claims
curl -X GET "https://docwise-health.preview.emergentagent.com/api/claims"

# Filter by status
curl -X GET "https://docwise-health.preview.emergentagent.com/api/claims?status=submitted"

# Filter by medical aid
curl -X GET "https://docwise-health.preview.emergentagent.com/api/claims?medical_aid=Discovery%20Health"
```

**Verify:**
- ✅ Returns claims array
- ✅ Filtering works correctly

---

### 14. Get Revenue Report
```bash
curl -X GET "https://docwise-health.preview.emergentagent.com/api/reports/revenue?from_date=2025-10-01&to_date=2025-10-31"
```

**Expected Response:**
```json
{
  "from_date": "2025-10-01",
  "to_date": "2025-10-31",
  "total_invoiced": 632.50,
  "total_paid": 632.50,
  "total_outstanding": 0.00,
  "invoice_count": 1,
  "payment_count": 2,
  "payment_methods": {
    "cash": 300.00,
    "card": 332.50
  }
}
```

**Verify:**
- ✅ Totals match your test data
- ✅ Payment methods breakdown correct
- ✅ Counts accurate

---

### 15. Get Outstanding Invoices Report
```bash
curl -X GET "https://docwise-health.preview.emergentagent.com/api/reports/outstanding"
```

**Expected:**
- ✅ Shows all unpaid and partially_paid invoices
- ✅ Calculates total outstanding amount

---

## Test Scenarios to Cover

### Scenario A: Medical Aid Split Billing
Create invoice with medical aid covering 80%, patient 20%:
```bash
curl -X POST "https://docwise-health.preview.emergentagent.com/api/invoices" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "YOUR_PATIENT_ID",
    "invoice_date": "2025-10-25",
    "items": [
      {"item_type": "consultation", "description": "Consultation", "quantity": 1, "unit_price": 1000}
    ],
    "medical_aid_name": "Bonitas",
    "medical_aid_number": "987654",
    "medical_aid_portion": 920,
    "patient_portion": 230
  }'
```

**Verify:**
- ✅ Total: R1150 (R1000 + 15% VAT)
- ✅ Medical aid portion: R920
- ✅ Patient portion: R230

### Scenario B: Multiple Medications with NAPPI Codes
Create invoice with multiple medications:
```bash
{
  "items": [
    {"item_type": "medication", "description": "Panado 500mg", "quantity": 20, "unit_price": 2.50, "nappi_code": "111111"},
    {"item_type": "medication", "description": "Ibuprofen 400mg", "quantity": 30, "unit_price": 1.50, "nappi_code": "222222"},
    {"item_type": "medication", "description": "Amoxicillin 500mg", "quantity": 15, "unit_price": 3.00, "nappi_code": "333333"}
  ]
}
```

**Verify:**
- ✅ All NAPPI codes saved correctly
- ✅ Totals calculated correctly

### Scenario C: Claim Rejection
```bash
curl -X PATCH "https://docwise-health.preview.emergentagent.com/api/claims/YOUR_CLAIM_ID/status?status=rejected&rejection_reason=Invalid%20ICD10%20code&rejection_code=ERR001"
```

**Verify:**
- ✅ Status: "rejected"
- ✅ Rejection reason and code saved

---

## Success Criteria Checklist

### Invoice Management
- [ ] Invoice created with auto-generated number (INV-YYYYMMDD-XXXX)
- [ ] VAT calculated correctly (15%)
- [ ] Multiple line items supported
- [ ] ICD-10 codes on consultation items
- [ ] NAPPI codes on medication items
- [ ] Medical aid information saved

### Payment Processing
- [ ] Cash payments recorded
- [ ] Card payments recorded
- [ ] Partial payments update status to "partially_paid"
- [ ] Full payments update status to "paid"
- [ ] Outstanding amount calculated correctly
- [ ] Multiple payments per invoice supported

### Medical Aid Claims
- [ ] Claims created with auto-generated number (CLM-YYYYMMDD-XXXX)
- [ ] Claims linked to invoices
- [ ] Status workflow: draft → submitted → approved/rejected → paid
- [ ] Diagnosis codes (ICD-10) included
- [ ] Approved amounts tracked

### Financial Reports
- [ ] Revenue report shows correct totals
- [ ] Payment methods breakdown accurate
- [ ] Outstanding invoices report working
- [ ] Date range filtering works

---

## Common Issues to Watch For

1. **Invoice Number Uniqueness**: Each invoice should have unique number
2. **VAT Calculation**: Should always be 15% of subtotal
3. **Payment Status Logic**: 
   - amount_paid = 0 → "unpaid"
   - 0 < amount_paid < total → "partially_paid"
   - amount_paid >= total → "paid"
4. **Medical Aid Portions**: medical_aid_portion + patient_portion should equal total_amount
5. **NAPPI/ICD-10 Codes**: Should be optional (can be null)

---

## Notes
- Replace `YOUR_PATIENT_ID_HERE`, `YOUR_INVOICE_ID_HERE`, `YOUR_CLAIM_ID_HERE` with actual IDs from responses
- All amounts in South African Rands (R)
- Dates in YYYY-MM-DD format
- Save IDs from responses to use in subsequent tests

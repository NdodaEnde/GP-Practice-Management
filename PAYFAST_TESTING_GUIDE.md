# PayFast Payment Gateway - Complete Testing Guide

## 🎯 Testing Overview

You'll test 3 main flows:
1. **Payment Initiation** - Does the payment button work?
2. **PayFast Payment Page** - Can you complete a test payment?
3. **Payment Confirmation** - Does the success page show?

---

## ✅ PRE-TEST CHECKLIST

Before testing, verify these are ready:

- [ ] Backend is running: `sudo supervisorctl status backend` (should show RUNNING)
- [ ] Frontend is running: Navigate to http://localhost:3000
- [ ] You have at least one unpaid invoice in the system
- [ ] PayFast sandbox credentials are in backend/.env

---

## 📋 TEST SUITE

### **TEST 1: Payment Button Visibility**

**Where:** `/billing` page

**Steps:**
1. Open browser and navigate to: `http://localhost:3000/billing`
2. You should see a list of invoices
3. Click on any invoice with status "unpaid" or "partially_paid"

**Expected Result:**
✅ Invoice opens in a modal/dialog
✅ You see a blue section at the bottom labeled "💳 Pay Online with PayFast"
✅ There's a green button saying "Pay R XXX.XX Online"
✅ Below that, you see "OR" divider
✅ Below that, manual payment options ("Record Manual Payment")

**Screenshot Checkpoint:** You should see something like this:
```
┌─────────────────────────────────────┐
│  Invoice Details                     │
│  ...                                 │
│  ┌───────────────────────────────┐  │
│  │ 💳 Pay Online with PayFast    │  │
│  │ Secure online payment via...   │  │
│  │ [Pay R 632.50 Online]         │  │
│  └───────────────────────────────┘  │
│           OR                         │
│  [Record Manual Payment] [Split]    │
└─────────────────────────────────────┘
```

**If you don't see this:**
- Check browser console for errors (F12)
- Verify invoice has `amount_outstanding > 0`
- Refresh the page

---

### **TEST 2: Payment Initiation (Backend)**

**Where:** Invoice modal with PayFast button

**Steps:**
1. With invoice open, click the green "Pay R XXX.XX Online" button
2. Watch what happens (should take 1-2 seconds)

**Expected Result:**
✅ A toast notification appears: "Payment Initiated - Redirecting to PayFast..."
✅ A new browser tab/window opens
✅ The new tab shows PayFast sandbox payment page (orange/red PayFast branding)
✅ Payment amount matches your invoice amount

**What the PayFast page should look like:**
```
┌─────────────────────────────────────┐
│  [PayFast Logo]        SANDBOX      │
│                                      │
│  Medical Invoice INV-20251026-XXXX  │
│  Amount: R 632.50                   │
│                                      │
│  Payment Method:                    │
│  ( ) Credit Card                    │
│  ( ) Instant EFT                    │
│                                      │
└─────────────────────────────────────┘
```

**If new tab doesn't open:**
- Check if popup blocker blocked it
- Check browser console for errors (F12)
- Try again with popup blocker disabled

**Debug Steps:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Click payment button again
4. Look for POST request to `/api/payfast/initiate`
5. Check response - should have `"success": true` and `payment_url`

---

### **TEST 3: Complete Test Payment (Success)**

**Where:** PayFast sandbox payment page (new tab)

**Steps:**
1. On PayFast sandbox page, select "Credit Card" payment method
2. Enter test card details:
   - **Card Number:** `4000000000000002` (success card)
   - **Cardholder Name:** `Test User`
   - **Expiry Date:** Any future date (e.g., `12/2025`)
   - **CVV:** Any 3 digits (e.g., `123`)
3. Click "Pay Now" or "Complete Payment"
4. Wait for processing (5-10 seconds)

**Expected Result:**
✅ PayFast shows "Payment Successful" message
✅ You're automatically redirected back to your app
✅ You land on: `http://localhost:3000/payment/success`
✅ Success page shows:
   - Green checkmark icon ✓
   - "Payment Successful!" heading
   - "Your payment has been processed successfully"
   - "Payment Reference" box with payment ID
   - "View Invoices" button
   - "View Financial Dashboard" button

**Screenshot of Success Page:**
```
┌─────────────────────────────────────┐
│     ✓  Payment Successful!          │
│                                      │
│  Your payment has been processed    │
│  successfully.                       │
│                                      │
│  ┌─────────────────────────────┐   │
│  │ Payment Reference:           │   │
│  │ pf_12345678abcd             │   │
│  └─────────────────────────────┘   │
│                                      │
│  [View Invoices]                    │
│  [View Financial Dashboard]         │
└─────────────────────────────────────┘
```

**If you see an error:**
- Note the error message
- Check card number is exactly: `4000000000000002`
- Try again with different test card

---

### **TEST 4: Check Backend Webhook (ITN) Processing**

**Where:** Backend logs

**Steps:**
1. After completing payment, check backend logs immediately
2. Run: `tail -f /var/log/supervisor/backend.out.log` (or check latest logs)

**Expected Result:**
✅ You should see log entries like:
```
INFO: ITN received: {'merchant_id': '10043091', 'merchant_key': '...', ...}
INFO: Payment pf_XXXXXXX status: COMPLETE, invoice: INV-YYYYMMDD-XXXX
INFO: Payment successful for invoice INV-YYYYMMDD-XXXX
```

**What each log means:**
- `ITN received` - Webhook was called by PayFast ✓
- `Payment status: COMPLETE` - Payment was successful ✓
- `Payment successful for invoice` - Your invoice was identified ✓

**If you see:**
- `Signature verification failed` - There's a configuration issue
- No logs at all - Webhook wasn't called (see Webhook Setup below)
- `Payment status: PENDING` - Payment is processing

---

### **TEST 5: Payment Cancellation Flow**

**Where:** PayFast sandbox payment page

**Steps:**
1. Start a new payment (click "Pay Online" button again)
2. On PayFast page, click "Cancel" or close the tab
3. OR click the "Cancel Payment" button if available

**Expected Result:**
✅ You're redirected to: `http://localhost:3000/payment/cancelled`
✅ Cancelled page shows:
   - Orange X icon
   - "Payment Cancelled" heading
   - "Your payment was cancelled..."
   - "No charges have been made to your account"
   - "Return to Invoices" button
   - "Go Back" button

---

### **TEST 6: Declined Card Test**

**Where:** PayFast sandbox payment page

**Steps:**
1. Start a new payment
2. On PayFast page, use DECLINED test card:
   - **Card Number:** `4000000000000010` (decline card)
   - **Other details:** Same as before
3. Click "Pay Now"

**Expected Result:**
✅ Payment is declined
✅ Error message appears on PayFast page
✅ You remain on PayFast page (no redirect)
✅ You can try again or cancel

---

### **TEST 7: Check Payment in Database (Optional)**

**Where:** Supabase Dashboard or backend API

**Steps:**
1. Go to Supabase dashboard
2. Navigate to `payments` table
3. Look for recent payment records

**OR use API:**
```bash
curl -X GET "http://localhost:8001/api/payments/invoice/YOUR_INVOICE_ID"
```

**Expected Result:**
✅ Payment record exists
✅ `payment_method`: Should show payment type
✅ `amount`: Should match invoice amount
✅ Invoice `amount_paid` updated
✅ Invoice `payment_status` changed to "paid" or "partially_paid"

**Note:** Currently, the webhook only logs payments but doesn't automatically update the database. This is the next enhancement step.

---

## 🔧 TROUBLESHOOTING

### Problem: PayFast Button Not Visible

**Check:**
1. Is invoice `amount_outstanding > 0`?
   - Go to Billing page
   - Check if invoice shows as "unpaid"
2. Check browser console for errors (F12)
3. Verify `PayFastPaymentButton` component imported correctly

**Fix:**
- Create a new unpaid invoice first
- Refresh browser (Ctrl+Shift+R)

---

### Problem: Payment Page Doesn't Open

**Check:**
1. Browser console for errors (F12)
2. Network tab - look for `/api/payfast/initiate` request
3. Response should be `success: true`

**Common Issues:**
- **Popup blocked:** Allow popups for localhost
- **CORS error:** Check backend CORS settings
- **Backend not running:** Check `sudo supervisorctl status backend`

**Fix:**
```bash
# Restart backend
sudo supervisorctl restart backend

# Check logs
tail -f /var/log/supervisor/backend.err.log
```

---

### Problem: No Webhook Logs

**This is EXPECTED in local development!**

PayFast sandbox cannot reach `localhost` URLs. To fix:

**Option A: Use ngrok (Recommended for full testing)**

1. Install ngrok: https://ngrok.com/download
2. Start tunnel:
   ```bash
   ngrok http 8001
   ```
3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
4. Go to PayFast sandbox dashboard
5. Update ITN URL to: `https://abc123.ngrok.io/api/payfast/webhook`

**Option B: Skip webhook testing for now**
- Manually record payments in the system
- Webhook will work in production with public URL

---

### Problem: Signature Verification Failed

**Check:**
1. PayFast credentials in `/app/backend/.env`
2. Ensure no extra spaces in credentials
3. Check passphrase is correct

**Fix:**
```bash
# View current .env
cat /app/backend/.env | grep PAYFAST

# Should show:
# PAYFAST_MERCHANT_ID=10043091
# PAYFAST_MERCHANT_KEY=0kkuh46yyasfr
# PAYFAST_PASSPHRASE=jt#yj!nA68jMd52j
# PAYFAST_SANDBOX=True

# If wrong, edit and restart:
nano /app/backend/.env
sudo supervisorctl restart backend
```

---

## ✅ SUCCESS CRITERIA

You've successfully tested PayFast if:

- [x] Payment button appears on unpaid invoices
- [x] Clicking button opens PayFast sandbox page
- [x] Test card payment completes successfully
- [x] Success page displays after payment
- [x] Backend logs show ITN received (if using ngrok)
- [x] Cancel flow works correctly
- [x] Declined card shows error

---

## 📊 TESTING CHECKLIST

Copy this and check off as you test:

```
□ Backend running
□ Frontend accessible at localhost:3000
□ Created unpaid invoice
□ Invoice opens and shows PayFast button
□ Payment button clickable
□ PayFast page opens in new tab
□ Test card payment succeeds
□ Redirected to success page
□ Success page displays correctly
□ Payment cancelled flow works
□ Declined card test works
□ Backend webhook logs visible (optional)
```

---

## 🎯 NEXT STEPS AFTER TESTING

Once all tests pass:

**Option 1: Enhance Webhook Processing**
- Auto-update invoice payment status
- Auto-record payment in database
- Generate receipt automatically

**Option 2: Production Deployment**
- Get production PayFast credentials
- Update .env with production keys
- Deploy to server with public URL

**Option 3: Add Email Notifications**
- Send payment confirmation emails
- Send receipt PDFs
- Notify practice of payments

---

## 📞 NEED HELP?

If you encounter issues:

1. **Check backend logs:**
   ```bash
   tail -n 100 /var/log/supervisor/backend.err.log
   ```

2. **Check browser console:** Press F12, go to Console tab

3. **Test backend API directly:**
   ```bash
   curl -X POST "http://localhost:8001/api/payfast/initiate" \
     -H "Content-Type: application/json" \
     -d '{
       "invoice_id": "test-123",
       "amount": 100.00,
       "customer_email": "test@example.com",
       "customer_phone": "0123456789",
       "invoice_number": "INV-TEST-001"
     }'
   ```

Let me know what happens and I can help debug!

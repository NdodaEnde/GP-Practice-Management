# Phase 2: Queue Management System - Summary & Workflow

**Last Updated:** October 2025  
**Status:** Core features implemented, needs completion & testing

---

## What's Currently Implemented ✅

### 1. Reception Check-In Interface
**Component:** `ReceptionCheckIn.jsx`  
**Route:** `/reception`

**Features:**
- ✅ Patient search (by name, ID number, or phone)
- ✅ New patient registration form
- ✅ Reason for visit / Chief complaint input
- ✅ Priority selection (Normal, Urgent)
- ✅ Queue number generation
- ✅ Check-in confirmation

### 2. Queue Display (Waiting Room)
**Component:** `QueueDisplay.jsx`  
**Route:** `/queue/display`

**Features:**
- ✅ Large screen display for waiting room
- ✅ Shows current queue numbers
- ✅ Patient status indicators
- ✅ Real-time queue updates

### 3. Workstation Dashboard
**Component:** `WorkstationDashboard.jsx`  
**Route:** `/queue/workstation`

**Features:**
- ✅ Doctor/nurse view of their queue
- ✅ "Call Next Patient" functionality
- ✅ Patient details display
- ✅ Status management

### 4. Backend Endpoints
**Implemented:**
- ✅ `/api/queue/check-in` - Patient check-in
- ✅ `/api/queue/current` - Get current queue
- ✅ `/api/queue/{queue_id}/call-next` - Call next patient
- ✅ `/api/queue/{queue_id}/status` - Update status

**Database:**
- ✅ MongoDB `queue_entries` collection
- ✅ Audit logging for all queue actions

---

## Designed Workflow (Your Practice Flow)

### Step 1: Patient Arrival at Reception

#### **Scenario A: Existing Patient**
```
1. Patient walks in: "I'm here to see the doctor"
2. Receptionist searches: Name / ID / Phone
3. Patient found ✓
4. Receptionist asks: "What's the reason for your visit today?"
   Patient responds: "I have a running tummy" / "I have a fever"
5. Receptionist enters:
   - Reason for visit: "Running tummy / Diarrhea"
   - Priority: Normal (or Urgent if severe)
6. Click "Check In"
7. System assigns queue number: "You are number 5"
8. Patient receives ticket/number and waits
```

#### **Scenario B: New Patient**
```
1. Patient walks in: "First time here"
2. Receptionist clicks "New Patient"
3. Completes registration form:
   - Personal details (name, DOB, ID, contact)
   - Medical aid information (if applicable)
   - Emergency contact
   - Allergies (if known)
   - Current medications (if any)
4. Asks: "What brings you in today?"
   Patient: "I have a fever for 3 days"
5. Enters reason for visit: "Fever - 3 days"
6. Priority: Normal
7. Saves patient → Auto check-in
8. Queue number assigned: "You are number 6"
```

### Step 2: Patient in Waiting Room

```
┌─────────────────────────────────┐
│   WAITING ROOM DISPLAY          │
├─────────────────────────────────┤
│                                 │
│   NOW SERVING:                  │
│        #3                       │
│                                 │
│   PLEASE WAIT:                  │
│   #4  #5  #6  #7  #8            │
│                                 │
└─────────────────────────────────┘
```

### Step 3: Vitals Station (Optional - Already Built)

```
When called:
- Patient goes to Vitals Station
- Nurse records: BP, temp, weight, height, oxygen sat
- Status: "In Vitals" → "Waiting for Consultation"
- Returns to waiting area
```

### Step 4: Doctor's Workstation

**What Doctor Sees:**
```
┌───────────────────────────────────────────┐
│  MY QUEUE                                 │
├───────────────────────────────────────────┤
│  Queue #5 - Mary Smith                    │
│  Chief Complaint: Running tummy/Diarrhea  │ ← YES, DOCTOR SEES THIS
│  Age: 45 | Priority: Normal               │
│  Vitals: BP 120/80, Temp 37.2°C          │
│  [Call Next Patient]                      │
├───────────────────────────────────────────┤
│  WAITING:                                 │
│  #6 - John Doe (Fever - 3 days)          │
│  #7 - Sarah Lee (Follow-up checkup)      │
│  #8 - Peter Jones (Back pain)            │
└───────────────────────────────────────────┘
```

### Step 5: Consultation (AI Scribe Integration)

```
1. Doctor clicks "Call Next Patient"
2. Patient enters consultation room
3. Doctor clicks "AI Scribe" (or opens from dashboard)
4. Records consultation - patient explains symptoms
5. AI generates SOAP notes (includes chief complaint)
6. Doctor reviews, prescribes, issues sick note, etc.
7. Marks consultation complete
8. Patient moves to next station (e.g., dispensary)
```

---

## Key Questions & Answers

### Q1: Do patients tell their complaint at reception?
**Yes! ✅** 
- Chief complaint is captured during check-in
- Field: "Reason for visit"
- Examples: "Running tummy", "Fever for 3 days", "Follow-up for diabetes"

### Q2: Does this complaint go into the SOAP?
**Yes! ✅**
- Complaint becomes part of encounter's `chief_complaint` field
- Appears at top of patient record when doctor opens it
- AI Scribe can reference it when generating SOAP Subjective section
- Doctor can see complaint before calling patient

### Q3: Does doctor see complaint before calling patient?
**Yes! Should be implemented ✅**
- Workstation dashboard shows chief complaint for each patient
- Helps doctor prepare and prioritize
- Example: "Chest pain" = high priority, prepare for ECG

### Q4: Queue number display?
**Yes! ✅**
- Waiting room screen shows current number and upcoming
- Helps patients know their turn
- Audio announcements (future enhancement)

---

## What's Missing / Needs Completion

### Critical (Must Complete):

1. **Chief Complaint Integration with AI Scribe** ⚠️
   - When doctor opens AI Scribe from queue, pre-fill patient context
   - Include chief complaint in consultation context
   - Show chief complaint prominently in AI Scribe interface

2. **Workstation Dashboard Enhancement** ⚠️
   - Show chief complaint for each patient in queue
   - Display vitals if already recorded
   - Show patient medical history summary

3. **Real-time Updates** ⚠️
   - Queue Display auto-refreshes when new patients check in
   - Workstation updates when patient called/status changes
   - WebSockets or polling implementation

4. **Integration with AI Scribe** ⚠️
   - "Call Next Patient" → Opens AI Scribe automatically
   - Pre-fills patient info and chief complaint
   - Saves consultation → Updates queue status to "completed"

### Nice-to-Have (Future):

5. **Audio Announcements**
   - "Number 5, please proceed to consultation room 2"
   - Text-to-speech integration

6. **SMS/WhatsApp Notifications**
   - "You are next in line, please be ready"
   - "Doctor is ready to see you"

7. **Wait Time Estimation**
   - "Estimated wait: 15 minutes"
   - Based on average consultation time

8. **Multi-Doctor Support**
   - Separate queues for different doctors
   - Route patients to specific doctors

---

## Technical Architecture

### Database Structure (MongoDB)

```javascript
queue_entries: {
  id: "uuid",
  queue_number: 5,
  patient_id: "patient_uuid",
  patient_name: "Mary Smith",
  reason_for_visit: "Running tummy/Diarrhea",  // ← Chief complaint
  priority: "normal",  // "normal", "urgent"
  status: "waiting",   // "waiting", "in_vitals", "in_consultation", "completed"
  station: "reception",
  check_in_time: "2025-10-14T10:30:00Z",
  vitals_recorded_at: null,
  consultation_started_at: null,
  consultation_completed_at: null,
  date: "2025-10-14",
  workspace_id: "workspace_id",
  wait_time_minutes: 0
}
```

### Status Flow

```
Check-in → waiting → in_vitals → waiting → in_consultation → completed
   ↓          ↓          ↓            ↓           ↓               ↓
Reception   Queue    Vitals Stn   Queue     Consultation    Dispensary
```

---

## Implementation Priority

### Phase 2.1: Core Queue (Already Built) ✅
- Patient check-in
- Queue display
- Basic workstation dashboard

### Phase 2.2: Enhanced Integration (Needs Completion) ⚠️
**Priority Order:**
1. Show chief complaint in Workstation Dashboard
2. Integrate "Call Next Patient" with AI Scribe
3. Pass chief complaint to AI Scribe consultation
4. Real-time queue updates (polling for MVP)

### Phase 2.3: Advanced Features (Future)
- WebSockets for real-time updates
- Audio announcements
- SMS notifications
- Multi-doctor queues

---

## Testing Checklist

### Reception Flow:
- [ ] Search existing patient by name
- [ ] Search existing patient by ID number
- [ ] Register new patient
- [ ] Enter chief complaint for both new/existing
- [ ] Check-in and verify queue number assigned
- [ ] Verify patient appears in queue display

### Queue Display:
- [ ] Shows current number being served
- [ ] Shows upcoming patients
- [ ] Updates when new patients check in

### Workstation Dashboard:
- [ ] Shows next patient with chief complaint
- [ ] "Call Next Patient" changes status
- [ ] Shows vitals if recorded
- [ ] Updates queue in real-time

### Integration with AI Scribe:
- [ ] Can open AI Scribe from workstation
- [ ] Chief complaint visible in AI Scribe
- [ ] Consultation saves to encounter
- [ ] Queue status updates to "completed"

---

## Recommendation: Next Steps

**To complete Phase 2, we should:**

1. **Enhance Workstation Dashboard** (30 min)
   - Add chief complaint display for each patient
   - Show vitals if available
   - Add "View Patient EHR" button

2. **Integrate with AI Scribe** (45 min)
   - Add navigation from "Call Next Patient" to AI Scribe
   - Pass patient context including chief complaint
   - Auto-update queue status when consultation saved

3. **Add Real-time Updates** (45 min)
   - Implement polling (every 5 seconds) for queue updates
   - Auto-refresh queue display and workstation

4. **Testing** (30 min)
   - End-to-end workflow testing
   - Multiple patients in queue
   - Different scenarios (urgent vs normal)

**Total Estimated Time:** 2.5 hours

---

## Summary

**What Works:**
- ✅ Patient check-in (new & existing)
- ✅ Chief complaint capture
- ✅ Queue number generation
- ✅ Queue display
- ✅ Basic workstation dashboard

**What Needs Completion:**
- ⚠️ Chief complaint visibility in workstation
- ⚠️ Integration between queue → AI Scribe
- ⚠️ Real-time updates
- ⚠️ Status management through workflow

**Your Workflow is Correct! ✓**
Patient walks in → Check-in with complaint → Queue → Vitals (optional) → Doctor sees complaint → Consultation with AI Scribe → Complete

The design is solid. We just need to complete the connections between the modules.

Ready to proceed with completing Phase 2? 🚀

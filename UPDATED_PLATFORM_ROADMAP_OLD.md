# SurgiScan Platform - Updated Roadmap & Status
**Last Updated:** October 26, 2024
**Project Status:** MVP Complete with Phase 3 Billing

---

## 🎯 EXECUTIVE SUMMARY

**Platform Vision:** Multi-tenant healthcare SaaS for Occupational Health & GP Practices

**Current State:**
- ✅ Core patient management complete
- ✅ Document digitization functional (needs enhancements)
- ✅ Clinical workflow Phase 2 complete
- ✅ Billing & payment system complete
- ⏳ Digitization module needs productization for standalone sale
- ⏳ Medical aid switching integration pending

---

## 📊 OVERALL COMPLETION STATUS

| Module | Status | Completion | Production Ready |
|--------|--------|------------|------------------|
| Core Patient Management | ✅ Complete | 100% | Yes |
| Document Digitization | ⚠️ Functional | 70% | **No - Needs work** |
| Queue Management | ✅ Complete | 100% | Yes |
| Vitals Station | ✅ Complete | 100% | Yes |
| AI Scribe (SOAP Notes) | ✅ Complete | 100% | Yes |
| Clinical Notes | ✅ Complete | 100% | Yes |
| Lab Orders & Results | ✅ Complete | 100% | Yes |
| Procedures | ✅ Complete | 100% | Yes |
| Immunizations | ✅ Complete | 100% | Yes |
| Prescriptions with NAPPI | ✅ Complete | 100% | Yes |
| Billing & Invoicing | ✅ Complete | 100% | Yes |
| Payment Gateway (PayFast) | ✅ Complete | 100% | Yes (Sandbox) |
| Claims Management | ✅ Complete | 100% | Yes |
| Financial Dashboard | ✅ Complete | 100% | Yes |
| Medical Aid Switching | ❌ Not Started | 0% | No |
| Audit Trail | ❌ Not Started | 0% | No |
| Workstation Dashboard | ⏳ Partial | 40% | No |

---

## 🔍 DIGITIZATION MODULE - DETAILED STATUS

### ✅ WHAT'S COMPLETE (Current Features)

**1. Document Upload & Processing**
- ✅ Single PDF upload
- ✅ AI extraction with LandingAI
- ✅ 6-tab validation interface (Demographics, Medications, Allergies, Diagnoses, Vitals, History)
- ✅ MongoDB storage of extracted data
- ✅ Supabase tracking of document metadata

**2. Patient Matching**
- ✅ Fuzzy matching by ID number, name, DOB
- ✅ Manual patient selection
- ✅ New patient creation from document
- ✅ Confidence scoring

**3. Auto-Population (Partial)**
- ✅ Allergies → structured table
- ✅ Diagnoses → structured table with ICD-10
- ✅ Vitals → structured table
- ✅ Chronic conditions → patient_conditions table
- ✅ Medications → MongoDB (semi-structured)

**4. User Interface**
- ✅ Upload interface
- ✅ Validation interface (6 tabs)
- ✅ Document archive/list view
- ✅ Document status tracking (pending, validated, archived)

---

### ❌ WHAT'S MISSING (Must Build for Standalone Product)

**CRITICAL (Blocks standalone sale):**

**1. Batch Upload System** ⚠️ **CRITICAL**
- ❌ Upload multiple documents at once
- ❌ Queue processing (background jobs)
- ❌ Progress tracking for batch operations
- ❌ Error handling for failed extractions
- ❌ Bulk patient matching
- **Why Critical:** GPs have hundreds/thousands of historical records
- **Effort:** 1-2 days

**2. Complete Auto-Population** ⚠️ **CRITICAL**
- ❌ Immunizations → immunizations table
- ❌ Lab results → lab_orders_results tables
- ❌ Procedures → procedures table
- ❌ Prescriptions → prescriptions table with NAPPI
- **Why Critical:** Incomplete patient history = unusable EHR
- **Effort:** 1-2 days

**3. Flexible Data Extraction (Client-Agnostic)** ⚠️ **CRITICAL**
- ❌ Dynamic field mapping system
- ❌ Custom extraction templates per client
- ❌ User-configurable field mappings
- ❌ Support for non-standard GP formats
- **Why Critical:** Each GP practice has different formats
- **Effort:** 3-4 days (see detailed design below)

**IMPORTANT (Improves usability):**

**4. Document Quality Control**
- ❌ Pre-processing for poor quality scans
- ❌ Rotation detection/correction
- ❌ Multi-page document handling
- ❌ Page splitting/merging tools
- **Effort:** 1-2 days

**5. Extraction Confidence & Review**
- ❌ Confidence scores per field
- ❌ Flag low-confidence extractions
- ❌ Bulk correction interface
- ❌ Learning from corrections
- **Effort:** 1-2 days

**6. Document Types Support**
- ⏳ Currently: Medical records only
- ❌ Lab reports (structured format)
- ❌ Radiology reports
- ❌ Specialist referral letters
- ❌ Discharge summaries
- **Effort:** 2-3 days (per document type)

**NICE-TO-HAVE (Future enhancements):**

**7. Advanced Features**
- ❌ OCR quality metrics
- ❌ Document classification (auto-detect type)
- ❌ Duplicate detection
- ❌ Version control for corrections
- ❌ Audit trail of changes
- **Effort:** 2-3 days

---

## 🎯 SOLUTION: CLIENT-AGNOSTIC DIGITIZATION SYSTEM

### The Problem You Described:
> "GP medical records differ in terms of what they capture... I need an agnostic way so I don't have to customize the EHR each time I meet a new client"

### The Solution: **Flexible Field Mapping Architecture**

**Concept:**
Instead of hardcoding what fields to extract, create a **configurable extraction system** where:
1. AI extracts ALL data it finds (not just predefined fields)
2. System stores raw extraction as JSON
3. Admin configures which extracted fields map to which EHR tables
4. Mappings saved per client/workspace
5. Future documents use saved mappings automatically

**Example Scenario:**

**Client A (Dr. Smith's Practice):**
- Their records have: "Immunisation History" section
- Admin maps: `immunisation_history` → `immunizations` table
- Field mapping: `vaccine` → `vaccine_name`, `date_given` → `administration_date`

**Client B (Dr. Jones's Practice):**
- Their records have: "Vaccination Records" section
- Admin maps: `vaccination_records` → `immunizations` table
- Field mapping: `vaccine_type` → `vaccine_name`, `administered` → `administration_date`

**Client C (No Immunization Records):**
- Their records don't track immunizations
- Admin marks: `immunizations` → Skip
- System doesn't try to populate immunizations table

---

### Implementation Design:

**1. Enhanced AI Extraction (Smart Mode)**
```python
# Current: Fixed structure
parsed_data = {
    'demographics': {...},
    'medications': [...],
    'allergies': [...],
    'diagnoses': [...],
    'vitals': {...},
    'clinical_notes': {...}
}

# New: Flexible structure
parsed_data = {
    'structured': {
        'demographics': {...},
        'medications': [...],
        # ... existing fields
    },
    'unstructured': {
        # AI finds additional sections
        'immunisation_history': [...],
        'vaccination_records': [...],
        'laboratory_results': [...],
        'specialist_referrals': [...],
        'any_other_section': {...}
    },
    'raw_text': "Full OCR text...",
    'confidence_scores': {...}
}
```

**2. Field Mapping Configuration (New Table)**
```sql
CREATE TABLE extraction_mappings (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,
    source_field TEXT,          -- e.g., 'vaccination_records'
    target_table TEXT,           -- e.g., 'immunizations'
    field_mappings JSONB,        -- {"vaccine_type": "vaccine_name", ...}
    transformation_rules JSONB,  -- Optional: date formats, unit conversions
    is_active BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

**3. Mapping UI (Admin Interface)**
```
┌─────────────────────────────────────────────┐
│  Field Mapping Configuration                │
├─────────────────────────────────────────────┤
│                                              │
│  Extracted Section: "Vaccination Records"   │
│  ┌─────────────────────────────────────┐   │
│  │ Map to: [immunizations table ▼]     │   │
│  └─────────────────────────────────────┘   │
│                                              │
│  Field Mappings:                            │
│  vaccine_type    → vaccine_name             │
│  administered    → administration_date      │
│  dose           → dose_number                │
│  next_due       → next_dose_due             │
│                                              │
│  [+ Add Mapping]  [Save]  [Test]           │
└─────────────────────────────────────────────┘
```

**4. Auto-Population Logic (Enhanced)**
```python
async def populate_from_document(patient_id, encounter_id, parsed_data, workspace_id):
    """
    Universal population function using workspace-specific mappings
    """
    # Get workspace mappings
    mappings = get_workspace_mappings(workspace_id)
    
    # Process each mapped section
    for mapping in mappings:
        source_data = parsed_data.get('unstructured', {}).get(mapping.source_field)
        
        if source_data:
            if mapping.target_table == 'immunizations':
                await populate_immunizations(patient_id, encounter_id, source_data, mapping)
            elif mapping.target_table == 'lab_orders_results':
                await populate_lab_results(patient_id, encounter_id, source_data, mapping)
            # ... etc for each table
```

---

### Benefits of This Approach:

**For SurgiScan (You):**
- ✅ **Zero custom code per client** - all configuration
- ✅ **Faster onboarding** - just configure mappings
- ✅ **Scalable** - add new clients without engineering time
- ✅ **Revenue model** - charge for setup/mapping as a service

**For Clients:**
- ✅ **Works with their existing formats** - no need to change records
- ✅ **Complete data capture** - nothing lost in digitization
- ✅ **Flexible** - can add new fields as needs evolve
- ✅ **Quality** - data validated before structured storage

---

### Implementation Phases:

**Phase 1: Core Flexibility (3-4 days)**
- ✅ Enhance AI extraction to capture "unknown" sections
- ✅ Create extraction_mappings table
- ✅ Build mapping configuration UI
- ✅ Update auto-population to use mappings

**Phase 2: Batch Processing (1-2 days)**
- ✅ Multiple file upload
- ✅ Background job queue
- ✅ Progress tracking
- ✅ Error handling

**Phase 3: Complete Auto-Population (1-2 days)**
- ✅ Immunizations population
- ✅ Lab results population
- ✅ Procedures population
- ✅ Prescriptions population

**Total Effort:** 5-8 days to productize digitization module

---

## 🚀 FULL PLATFORM - OUTSTANDING WORK

### HIGH PRIORITY (Production Blockers)

**1. Medical Aid Switch Integration** (2-3 weeks)
- ❌ Register with Healthbridge/MediSwitch
- ❌ Real-time eligibility checks
- ❌ Electronic claim submission
- ❌ Automated status updates
- ❌ ERA (Electronic Remittance Advice) parsing
- **Business Impact:** Manual claims = slow cash flow

**2. Comprehensive Testing** (1 week)
- ⏳ End-to-end patient workflow
- ⏳ All integrations (PayFast, NAPPI, ICD-10)
- ⏳ Edge cases and error handling
- ⏳ Performance testing
- ⏳ Security audit
- **Business Impact:** Production bugs = reputation risk

**3. Access & Audit Trail** (1 week)
- ❌ Track all user actions
- ❌ HIPAA/POPIA compliance logs
- ❌ User permissions system
- ❌ Data access logging
- **Business Impact:** Legal/compliance requirement

### MEDIUM PRIORITY (Competitive Features)

**4. Workstation Dashboard** (3-4 days)
- ⏳ Real-time patient queue
- ⏳ Today's appointments
- ⏳ Pending tasks
- ⏳ Quick actions
- **Business Impact:** UX improvement

**5. Reporting & Analytics** (1 week)
- ⏳ Custom report builder
- ⏳ Practice performance metrics
- ⏳ Clinical quality indicators
- ⏳ Export to Excel/PDF
- **Business Impact:** Practice management insights

**6. Background Job System** (3-4 days)
- ❌ Async processing queue
- ❌ Scheduled tasks
- ❌ Retry mechanisms
- ❌ Job monitoring
- **Business Impact:** Scalability & performance

### LOW PRIORITY (Nice-to-Have)

**7. Automated Notifications** (3-4 days)
- ❌ Email/SMS for appointments
- ❌ Payment reminders
- ❌ Lab result alerts
- ❌ Prescription renewals

**8. Mobile App** (4-6 weeks)
- ❌ Patient-facing mobile app
- ❌ View test results
- ❌ Book appointments
- ❌ Make payments

**9. Telemedicine Integration** (2-3 weeks)
- ❌ Video consultation
- ❌ Virtual waiting room
- ❌ Remote prescribing

---

## 📅 RECOMMENDED ROADMAP (Next 3 Months)

### Month 1: **Productize Digitization Module** (Standalone Sale)
**Week 1-2:**
- Build flexible field mapping system
- Enhance AI extraction for unknown fields
- Create mapping configuration UI

**Week 3:**
- Implement batch upload system
- Background processing queue
- Progress tracking

**Week 4:**
- Complete auto-population for all tables
- Testing with various GP formats
- Documentation for clients

**Deliverable:** Standalone digitization product ready for sale

---

### Month 2: **Production Readiness**
**Week 1-2:**
- Comprehensive end-to-end testing
- Performance optimization
- Bug fixes

**Week 3:**
- Security audit
- Compliance checks (POPIA/HIPAA)
- Access & audit trail implementation

**Week 4:**
- Production deployment prep
- Monitoring setup
- Client onboarding documentation

**Deliverable:** Production-ready platform

---

### Month 3: **Medical Aid Integration & Scale**
**Week 1-2:**
- Register with medical aid switch
- Implement eligibility checks
- Electronic claim submission

**Week 3-4:**
- Claims automation testing
- ERA integration
- Client training materials

**Deliverable:** Automated claims = faster cash flow

---

## 💰 BUSINESS MODEL IMPLICATIONS

### Standalone Digitization Module Pricing:
- **Setup Fee:** R20,000 - R50,000 (includes mapping configuration)
- **Per Document:** R5 - R10 per page
- **Monthly License:** R2,000 - R5,000 for ongoing access
- **Bulk Pricing:** Discounts for 1000+ documents

### Full Platform Pricing:
- **Setup:** R50,000 - R100,000
- **Monthly SaaS:** R5,000 - R15,000 per practice
- **Per Transaction:** Small % of payment processing
- **Medical Aid Integration:** Premium tier (+R5,000/month)

---

## 🎯 CRITICAL DECISIONS NEEDED

**Decision 1: Digitization Module Priority**
- Option A: Prioritize standalone digitization (revenue now)
- Option B: Focus on full platform (bigger long-term value)
- **Recommendation:** Option A - quick revenue, proves concept

**Decision 2: Medical Aid Integration**
- Option A: Build now (2-3 weeks investment)
- Option B: Defer until first paying client needs it
- **Recommendation:** Option B - don't build until validated demand

**Decision 3: Testing Approach**
- Option A: Comprehensive testing now (1 week)
- Option B: Test incrementally with pilot clients
- **Recommendation:** Option A - production bugs expensive to fix

---

## 📊 EFFORT SUMMARY

| Workstream | Effort | Priority | ROI |
|------------|--------|----------|-----|
| Digitization Productization | 5-8 days | **CRITICAL** | HIGH (Standalone sale) |
| Batch Upload System | 1-2 days | **CRITICAL** | HIGH (Usability) |
| Flexible Field Mapping | 3-4 days | **CRITICAL** | HIGH (Scalability) |
| Complete Auto-Population | 1-2 days | **CRITICAL** | HIGH (Data completeness) |
| Comprehensive Testing | 1 week | HIGH | HIGH (Quality) |
| Medical Aid Switching | 2-3 weeks | MEDIUM | MEDIUM (Complex) |
| Audit Trail | 1 week | MEDIUM | MEDIUM (Compliance) |
| Workstation Dashboard | 3-4 days | LOW | LOW (Polish) |

---

## ✅ WHAT YOU CAN SELL TODAY

**Full Platform (With Caveats):**
- ✅ Core EHR with NAPPI/ICD-10
- ✅ Billing & payment processing
- ✅ Claims management (manual submission)
- ⚠️ Digitization (single documents only, manual mapping)
- ❌ Medical aid integration (manual process)

**Standalone Digitization (NOT YET):**
- ⚠️ Needs 1-2 weeks more work
- Missing: Batch upload, flexible mapping, complete auto-population

---

## 🚀 NEXT STEPS

**Immediate (This Week):**
1. Decide on priority: Digitization vs Full Platform testing
2. Review flexible mapping design (feedback needed)
3. Test current system with real GP documents (identify gaps)

**Next 2 Weeks:**
1. Implement flexible field mapping system
2. Build batch upload functionality
3. Complete auto-population for all tables

**Month 1 Goal:**
Have a productized, sellable standalone digitization module

---

**Questions for You:**
1. Do you want to prioritize standalone digitization module first?
2. Should I proceed with flexible field mapping implementation?
3. Do you have sample GP documents from different practices to test with?
4. What's your target launch date for standalone digitization?

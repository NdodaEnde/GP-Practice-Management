# SurgiScan - Multi-Tenant Healthcare SaaS Platform

## 🏥 Project Overview

SurgiScan is a comprehensive multi-tenant healthcare SaaS platform designed to support GP Practice workflows with:
- Patient registration and management
- Encounter documentation with vitals
- Medical document upload and parsing (mocked ADE integration)
- Side-by-side validation interface for parsed documents
- Dispensing tracking
- Billing and invoice management
- Analytics dashboard

## 🏗️ Architecture

### Technology Stack
- **Frontend**: React 19 + TailwindCSS + Shadcn UI
- **Backend**: FastAPI (Python 3.11)
- **Databases**: 
  - Supabase (PostgreSQL) - for structured relational data
  - MongoDB - for document storage and unstructured data

### Database Architecture (Hybrid Approach)

**Supabase (Postgres):**
- Structured, relational data
- Tables: tenants, workspaces, patients, encounters, document_refs, gp_invoices, dispense_events, certificates
- Enforces referential integrity
- Analytics-ready data

**MongoDB:**
- Operational document storage
- Collections: scanned_documents, parsed_documents, validation_sessions, audit_events
- Stores unstructured clinical artifacts and ADE parse results

**Bridge:** `document_refs` table in Postgres maps to MongoDB documents via `mongo_doc_id`

## 🚀 Current Status

### ✅ Completed
1. **Backend API** - Fully implemented with all endpoints
2. **Frontend UI** - Complete GP workflow interface
3. **MongoDB Integration** - Working and tested
4. **Multi-tenancy Structure** - Architecture in place
5. **Mock Document Parser** - Generates realistic parsed medical data
6. **All GP Workflow Pages:**
   - Dashboard with analytics
   - Patient Registry with search
   - Patient Details with encounter history
   - New Encounter form with vitals
   - Validation Interface (side-by-side view)
   - Billing and Invoice Management

### ⚠️ Pending Setup
**Supabase Tables Need to be Created Manually**

The Supabase tables must be created via the Supabase Dashboard SQL Editor because the Python SDK doesn't support raw SQL execution.

**📋 Follow these steps:**

1. **Go to Supabase SQL Editor:**
   - URL: https://supabase.com/dashboard/project/sizujtbejnnrdqcymgle/sql
   - Or navigate: Dashboard → Your Project → SQL Editor

2. **Copy and execute the SQL** from `/app/backend/SUPABASE_SETUP_INSTRUCTIONS.md`

3. **Restart backend:**
   ```bash
   sudo supervisorctl restart backend
   ```

4. **Verify:** The dashboard should show data without errors

## 📁 Project Structure

```
/app/
├── backend/
│   ├── server.py                          # Main FastAPI application
│   ├── .env                               # Environment variables (Supabase + MongoDB)
│   ├── requirements.txt                   # Python dependencies
│   ├── setup_supabase.sql                # SQL schema file
│   └── SUPABASE_SETUP_INSTRUCTIONS.md    # Setup guide
│
├── frontend/
│   ├── src/
│   │   ├── App.js                        # Main app with routing
│   │   ├── App.css                       # Global styles
│   │   ├── components/
│   │   │   ├── Layout.jsx                # Main layout with sidebar
│   │   │   └── ui/                       # Shadcn UI components
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx             # Analytics dashboard
│   │   │   ├── PatientRegistry.jsx       # Patient list & registration
│   │   │   ├── PatientDetails.jsx        # Patient profile & encounters
│   │   │   ├── NewEncounter.jsx          # Create new encounter
│   │   │   ├── ValidationInterface.jsx   # Document validation UI
│   │   │   └── Billing.jsx               # Invoice management
│   │   └── services/
│   │       └── api.js                    # API client wrapper
│   ├── package.json
│   └── .env                              # Frontend environment variables
│
└── README_SURGISCAN.md                   # This file
```

## 🔧 Configuration

### Backend Environment Variables (`.env`)
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="surgiscan_db"
CORS_ORIGINS="*"

# Supabase Configuration
SUPABASE_URL="https://sizujtbejnnrdqcymgle.supabase.co"
SUPABASE_ANON_KEY="your-anon-key"
SUPABASE_SERVICE_KEY="your-service-key"

# Demo Tenant
DEMO_TENANT_ID="demo-tenant-001"
DEMO_WORKSPACE_ID="demo-gp-workspace-001"
```

### Frontend Environment Variables (`.env`)
```
REACT_APP_BACKEND_URL=https://docucare-health.preview.emergentagent.com
```

## 🎯 GP Workflow

### 1. Patient Registration
- Navigate to "Patients" → "Register New Patient"
- Enter patient demographics (name, DOB, ID, contact, medical aid)
- Patient stored in Supabase `patients` table

### 2. Create Encounter
- From patient details page → "New Encounter"
- Record:
  - Chief complaint
  - Vital signs (BP, HR, temp, weight, height, O2 saturation)
  - GP notes
  - Upload medical document (PDF/image)
- Document automatically parsed by mock ADE parser
- Encounter stored in Supabase, documents in MongoDB

### 3. Validation
- View parsed document data side-by-side with original
- Structured data displayed by category:
  - Patient demographics
  - Medical history
  - Current medications
  - Allergies
  - Lab results
  - Clinical notes
- Add validation notes
- Approve document → status changes to "approved"

### 4. Billing
- Create invoice for encounter
- Add line items (description, quantity, unit price)
- Select payer type (cash/medical aid/corporate)
- Invoice stored in Supabase

## 📊 API Endpoints

### Health Check
```bash
GET /api/health
```

### Patients
```bash
GET    /api/patients              # List patients (with optional search)
POST   /api/patients              # Create patient
GET    /api/patients/{id}         # Get patient details
PUT    /api/patients/{id}         # Update patient
```

### Encounters
```bash
POST   /api/encounters                    # Create encounter
GET    /api/encounters/{id}               # Get encounter
GET    /api/encounters/patient/{id}       # List patient encounters
PUT    /api/encounters/{id}               # Update encounter
```

### Documents
```bash
POST   /api/documents/upload                  # Upload & parse document
GET    /api/documents/encounter/{id}         # List encounter documents
GET    /api/documents/{id}/original          # Get original file
```

### Validation
```bash
GET    /api/validation/{encounter_id}        # Get validation session
POST   /api/validation/{doc_id}/approve     # Approve document
```

### Invoices
```bash
POST   /api/invoices                # Create invoice
GET    /api/invoices                # List invoices
GET    /api/invoices/{id}           # Get invoice
PUT    /api/invoices/{id}/status    # Update status
```

### Analytics
```bash
GET    /api/analytics/summary       # Dashboard summary stats
```

## 🧪 Testing

### Backend API Test
```bash
# Health check
curl https://docucare-health.preview.emergentagent.com/api/health

# After Supabase setup, test patient creation:
curl -X POST https://docucare-health.preview.emergentagent.com/api/patients \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1980-01-15",
    "id_number": "8001155555083",
    "contact_number": "0821234567",
    "email": "john.doe@example.com",
    "medical_aid": "Discovery Health"
  }'
```

### Frontend
Visit: https://docucare-health.preview.emergentagent.com

## 🎨 UI/UX Features

- **Modern Healthcare Design**: Clean, professional medical UI
- **Teal/Cyan Color Palette**: Professional and trust-inspiring
- **Responsive Layout**: Works on all screen sizes
- **Smooth Animations**: Fade-in and slide-in effects
- **Shadcn UI Components**: Accessible, customizable components
- **Inter Font**: Clean, readable typography
- **Real-time Form Validation**: Instant feedback
- **Loading States**: User-friendly loading indicators

## 🔐 Security & Compliance

### Current Implementation
- Multi-tenant data isolation via tenant_id and workspace_id
- All operations stamped with tenant context
- Audit trail in MongoDB (audit_events collection)

### Production Requirements (Not Yet Implemented)
- Enable Supabase Row Level Security (RLS)
- Add JWT-based authentication
- Implement role-based access control
- Add encryption for sensitive PHI data
- HIPAA compliance measures

## 📈 Analytics

Dashboard provides:
- Total patients count
- Total encounters
- Total revenue (from invoices)
- Pending invoices count
- Recent encounters timeline

## 🚧 Future Enhancements

1. **Authentication System**
   - JWT-based auth
   - Role management (GP doctor, receptionist, admin)

2. **Real ADE Integration**
   - Replace mock parser with actual LandingAI ADE API
   - Confidence scoring
   - Manual correction workflows

3. **Occupational Health Workflow**
   - Questionnaires
   - Nurse examinations
   - Medical reviews
   - Certificate generation

4. **Advanced Features**
   - Appointment scheduling
   - SMS/Email notifications
   - Prescription management
   - Medical aid claim submissions
   - Data export/reporting

5. **Analytics Dashboard**
   - Charts and graphs
   - Financial reports
   - Patient outcome tracking
   - Provider performance metrics

## 🐛 Known Issues

1. **Supabase Tables**: Must be manually created (see instructions above)
2. **No Authentication**: Currently working in demo mode with fixed tenant
3. **Mock Document Parser**: Returns simulated data instead of real OCR

## 📞 Support

For issues or questions:
1. Check `/app/backend/SUPABASE_SETUP_INSTRUCTIONS.md`
2. Review logs: `tail -f /var/log/supervisor/backend.*.log`
3. Test API health: `curl https://docucare-health.preview.emergentagent.com/api/health`

## 🎉 Quick Start Summary

1. **Create Supabase tables** (see SUPABASE_SETUP_INSTRUCTIONS.md)
2. **Restart backend**: `sudo supervisorctl restart backend`
3. **Open app**: https://docucare-health.preview.emergentagent.com
4. **Register first patient**: Click "Register New Patient"
5. **Create encounter**: Select patient → "New Encounter"
6. **Upload document**: Add medical document for parsing
7. **Validate data**: Review and approve parsed information
8. **Create invoice**: Generate billing for the encounter

## 📝 License

Proprietary - SurgiScan Healthcare Platform

---

**Built with ❤️ for modern healthcare practices**

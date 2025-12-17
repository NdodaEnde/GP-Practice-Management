# SurgiScan Platform - Technical Architecture Document

**Version:** 1.0  
**Date:** October 2025  
**Document Type:** Technical Architecture Overview  
**Audience:** Software Architects, Technical Decision Makers

---

## Executive Summary

SurgiScan is a **comprehensive multi-tenant healthcare SaaS platform** designed for GP practices, occupational health clinics, hospitals, and medical facilities. It provides a complete Electronic Health Record (EHR) system, practice management tools, clinical workflows, billing integration, and AI-powered document digitization.

**Core Value Proposition:**
- **Complete EHR System:** Patient management, clinical notes, prescriptions, lab results
- **Clinical Workflow:** Reception, queue management, vitals capture, AI scribe
- **Billing & Payments:** Invoice generation, online payments (PayFast), claims management
- **Document Digitization:** AI-powered extraction with human validation (DaaS offering)
- **Multi-Tenant Architecture:** Support multiple healthcare organizations with data isolation
- **Role-Based Access:** Admin, clinician, validator, uploader, reception roles

---

## 1. Platform Overview

### 1.1 What Does SurgiScan Do?

**Primary Function:** Medical Document Digitization as a Service

The platform accepts scanned medical documents (PDF, images) and:
1. **Parses** documents using AI (LandingAI ADE DPT-2)
2. **Extracts** structured data using configurable templates
3. **Validates** extractions through human review
4. **Stores** validated data in relational databases
5. **Exports** data in multiple formats (JSON, CSV, FHIR-ready)

### 1.2 Target Users

**Healthcare Organizations:**
- GP Practices
- Occupational Health Clinics
- Hospitals
- Medical Records Departments

**User Roles:**
- **Administrators:** Manage workspaces, users, and system configuration
- **Validators:** Review and approve AI extractions
- **Uploaders:** Upload documents for processing
- **Clinicians:** Access validated patient records (future)

### 1.3 Use Cases

**Use Case 1: Historical Records Digitization**
- Client has 10,000 paper patient files
- Scans documents → uploads to platform
- AI extracts demographics, diagnoses, medications
- Validators review and approve
- Export structured data to existing EHR

**Use Case 2: Ongoing Document Processing**
- Daily intake of referral letters, lab results, prescriptions
- Real-time processing and validation
- Integration with practice management systems

**Use Case 3: Compliance & Audit**
- Centralized document archive
- Searchable medical record repository
- Audit trail for data access and modifications

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                            │
│  Web Browser (React SPA) - Role-Based Dashboards            │
└─────────────────────────────────────────────────────────────┘
                            ▼ HTTPS/REST
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  FastAPI     │  │  FastAPI     │  │  FastAPI     │      │
│  │  Auth Service│  │  Digitization│  │  User/       │      │
│  │              │  │  Service     │  │  Workspace   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   INTEGRATION LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  LandingAI   │  │  Supabase    │  │  MongoDB     │      │
│  │  (Document   │  │  (Relational)│  │  (Documents) │      │
│  │   Parsing)   │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  ┌────────────────┐         ┌───────────────────┐           │
│  │  PostgreSQL    │         │  MongoDB Atlas    │           │
│  │  (Supabase)    │         │  (Document Store) │           │
│  │  - Users       │         │  - Parsed Docs    │           │
│  │  - Workspaces  │         │  - Extractions    │           │
│  │  - EHR Tables  │         │  - Validation     │           │
│  └────────────────┘         └───────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

**Frontend:**
- React 18 (Single Page Application)
- React Router DOM (Client-side routing)
- Axios (HTTP client)
- Shadcn UI (Component library)
- TailwindCSS (Styling)
- PDF.js (Document preview)

**Backend:**
- FastAPI (Python 3.9+)
- Pydantic (Data validation)
- Python-Jose (JWT tokens)
- Passlib (Password hashing)
- HTTPX (Async HTTP client)

**Databases:**
- PostgreSQL (via Supabase) - Structured data
- MongoDB Atlas - Document storage

**Third-Party Services:**
- LandingAI ADE DPT-2 - AI document parsing
- Supabase - Backend-as-a-Service (Auth, Storage, Database)

**Infrastructure:**
- Kubernetes (Container orchestration)
- Supervisor (Process management)
- Nginx (Reverse proxy)

---

## 3. Core Features & Capabilities

### 3.1 Authentication & Authorization

**JWT-Based Authentication:**
- Access tokens: 24-hour validity
- Refresh tokens: 7-day validity
- Bcrypt password hashing
- Automatic token refresh on expiry

**Role-Based Access Control (RBAC):**
```
admin:
  - Full platform access
  - Create/manage workspaces
  - Create/manage users
  - View all data

validator:
  - Access validation queue
  - Review document extractions
  - Approve/reject data
  - View assigned documents

uploader:
  - Upload documents (single/batch)
  - View upload history
  - Track document status
```

**Security Features:**
- HTTP-only cookies (future)
- CORS protection
- SQL injection prevention (parameterized queries)
- XSS protection (React escaping)
- Rate limiting (future)

### 3.2 Multi-Tenant Architecture

**Workspace Isolation:**
```sql
-- Every query filters by workspace_id
SELECT * FROM documents 
WHERE workspace_id = 'client-abc-123';

-- Users belong to workspaces
SELECT * FROM users 
WHERE workspace_id = 'client-abc-123';
```

**Data Separation:**
- **Logical Isolation:** Shared database, filtered queries
- **Tenant ID:** Every record tagged with workspace_id
- **User-Workspace Relationship:** Many-to-many via junction table

**Workspace Features:**
- Custom branding (future)
- Usage quotas (max users, documents, storage)
- Subscription tiers (free, basic, professional, enterprise)
- Independent configuration per workspace

### 3.3 Document Processing Workflow

**Two-Phase Processing:**

```
Phase 1: PARSE
User uploads PDF → LandingAI parses → Extract text & structure → Save to MongoDB
Status: uploaded → parsing → parsed

Phase 2: EXTRACT
Validator reviews → Triggers extraction → Template maps data → Save to PostgreSQL
Status: parsed → extracting → extracted → pending_validation → approved
```

**Document Lifecycle:**
```
uploaded ──→ parsing ──→ parsed ──→ pending_validation
                            │
                            ├──→ extracting ──→ extracted ──→ approved ──→ EHR tables
                            │
                            └──→ rejected (with reason)
```

**Template-Driven Extraction:**
```json
{
  "template_name": "GP Patient Demographics",
  "fields": [
    {
      "field_name": "patient_name",
      "database_table": "patients",
      "database_column": "full_name",
      "data_type": "string",
      "required": true,
      "validation_rules": "^[A-Za-z\\s]+$"
    },
    {
      "field_name": "date_of_birth",
      "database_table": "patients",
      "database_column": "dob",
      "data_type": "date",
      "required": true
    }
  ]
}
```

### 3.4 Validation Queue

**Human-in-the-Loop Validation:**
- AI extracts data with confidence scores
- Human validators review side-by-side (PDF + extracted data)
- Edit incorrect extractions
- Approve or reject with reasons
- Track validator performance metrics

**Queue Management:**
- Priority sorting (urgent documents first)
- Auto-assignment to validators
- Workload balancing
- SLA tracking (time to validation)

### 3.5 Data Export

**Export Formats:**
- **JSON:** Complete document structure
- **CSV:** Tabular data (demographics, vitals, etc.)
- **Bulk Export:** All documents in single file
- **PDF:** Original scanned document

**Future Formats:**
- HL7 FHIR (healthcare interoperability standard)
- HL7 v2 messages
- CDA (Clinical Document Architecture)

### 3.6 Document Archive

**Features:**
- Full-text search across documents
- Filter by: status, patient, date range, document type
- Preview PDF alongside extracted data
- Export individual or bulk documents
- Statistics dashboard (total docs, by status)

---

## 4. Database Schema

### 4.1 PostgreSQL (Supabase) - Relational Data

**Core Tables:**

```sql
-- User Management
users (
  id UUID PRIMARY KEY,
  email VARCHAR UNIQUE,
  password_hash VARCHAR,
  first_name VARCHAR,
  last_name VARCHAR,
  role VARCHAR, -- admin, validator, uploader
  workspace_id VARCHAR,
  tenant_id VARCHAR,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  last_login TIMESTAMP
)

-- Workspace Management
workspaces (
  id UUID PRIMARY KEY,
  name VARCHAR,
  slug VARCHAR UNIQUE,
  organization_name VARCHAR,
  organization_type VARCHAR, -- gp_practice, hospital, etc.
  subscription_tier VARCHAR, -- free, basic, professional, enterprise
  max_users INTEGER,
  max_documents INTEGER,
  storage_quota_gb INTEGER,
  is_active BOOLEAN,
  tenant_id VARCHAR,
  created_at TIMESTAMP
)

-- Workspace-User Relationships
workspace_users (
  id UUID PRIMARY KEY,
  workspace_id UUID REFERENCES workspaces,
  user_id UUID REFERENCES users,
  role VARCHAR, -- owner, admin, member
  joined_at TIMESTAMP
)

-- Document Metadata
digitised_documents (
  id UUID PRIMARY KEY,
  filename VARCHAR,
  status VARCHAR, -- parsed, extracted, approved, rejected
  patient_id UUID,
  workspace_id VARCHAR,
  tenant_id VARCHAR,
  upload_date TIMESTAMP,
  parsed_doc_id VARCHAR, -- MongoDB reference
  pages_count INTEGER,
  file_size_bytes BIGINT,
  template_id UUID
)

-- EHR Tables (examples)
patients (...)
diagnoses (...)
medications (...)
vitals (...)
lab_results (...)
```

**Indexes:**
- `users.workspace_id` (workspace filtering)
- `users.email` (login lookup)
- `workspaces.slug` (URL routing)
- `digitised_documents.workspace_id` (tenant isolation)
- `digitised_documents.status` (queue queries)

### 4.2 MongoDB - Document Storage

**Collections:**

```javascript
// Parsed Documents
gp_parsed_documents {
  _id: ObjectId,
  document_id: "uuid",
  workspace_id: "client-abc-123",
  raw_text: "Full OCR text...",
  structured_data: {
    pages: [...],
    tables: [...],
    forms: [...]
  },
  ai_confidence: 0.95,
  parsed_at: ISODate,
  parser_version: "ade-dpt-2"
}

// Validation Sessions
gp_validation_sessions {
  _id: ObjectId,
  document_id: "uuid",
  validator_id: "uuid",
  extracted_data: {
    demographics: {...},
    diagnoses: [...],
    medications: [...]
  },
  validation_status: "pending_validation",
  started_at: ISODate,
  completed_at: ISODate
}
```

---

## 5. API Architecture

### 5.1 REST API Endpoints

**Authentication:**
```
POST   /api/auth/login           - User login (returns JWT)
POST   /api/auth/logout          - User logout
POST   /api/auth/refresh         - Refresh access token
GET    /api/auth/me              - Get current user
POST   /api/auth/register        - Create user (admin only)
```

**User Management:**
```
GET    /api/users/               - List users (admin only)
GET    /api/users/{id}           - Get user details
POST   /api/users/               - Create user (admin only)
PUT    /api/users/{id}           - Update user (admin only)
DELETE /api/users/{id}           - Deactivate user (admin only)
```

**Workspace Management:**
```
GET    /api/workspaces/          - List workspaces (admin only)
GET    /api/workspaces/{id}      - Get workspace details
POST   /api/workspaces/          - Create workspace (admin only)
PUT    /api/workspaces/{id}      - Update workspace (admin only)
DELETE /api/workspaces/{id}      - Deactivate workspace (admin only)
GET    /api/workspaces/stats     - Get statistics (admin only)
```

**Document Processing:**
```
POST   /api/gp/upload            - Upload document
GET    /api/gp/documents         - List documents (filtered by workspace)
GET    /api/gp/document/{id}/view - Get PDF for preview
POST   /api/gp/documents/{id}/extract - Trigger extraction
GET    /api/gp/parsed-document/{id} - Get parsed data from MongoDB
```

**Validation Workflow:**
```
GET    /api/validation/queue/list - Get validation queue
POST   /api/validation/approve   - Approve extraction
POST   /api/validation/reject    - Reject extraction
```

**Data Export:**
```
GET    /api/gp/documents/{id}/export?format=json - Export document
```

### 5.2 API Security

**Authentication:**
```python
from fastapi.security import HTTPBearer
from jose import jwt

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload
```

**Authorization:**
```python
async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user
```

**Workspace Filtering:**
```python
@router.get("/documents")
async def get_documents(current_user: dict = Depends(get_current_user)):
    workspace_id = current_user.get("workspace_id")
    documents = db.query(Document).filter(Document.workspace_id == workspace_id)
    return documents
```

---

## 6. Data Flow Diagrams

### 6.1 Document Upload & Processing

```
┌──────────┐
│  Client  │
│ (Upload) │
└────┬─────┘
     │ 1. POST /api/gp/upload (PDF file)
     ▼
┌──────────────────┐
│  FastAPI Server  │
│  - Save to temp  │
│  - Create record │
└────┬─────────────┘
     │ 2. Send to LandingAI
     ▼
┌──────────────────┐
│   LandingAI API  │
│  - OCR text      │
│  - Extract tables│
│  - Detect forms  │
└────┬─────────────┘
     │ 3. Return parsed data
     ▼
┌──────────────────┐
│  MongoDB Store   │
│  - Save parsed   │
│  - Link doc_id   │
└────┬─────────────┘
     │ 4. Update status
     ▼
┌──────────────────┐
│  PostgreSQL      │
│  - status:parsed │
│  - parsed_doc_id │
└──────────────────┘
```

### 6.2 Validation Workflow

```
┌───────────┐
│ Validator │
│   User    │
└─────┬─────┘
      │ 1. GET /api/validation/queue
      ▼
┌──────────────────┐
│  FastAPI Server  │
│  - Fetch pending │
│  - Filter by WS  │
└────┬─────────────┘
      │ 2. Query MongoDB
      ▼
┌──────────────────┐
│  MongoDB         │
│  - Get parsed    │
│  - Get extracted │
└────┬─────────────┘
      │ 3. Return data
      ▼
┌───────────────────┐
│  Validator UI     │
│  - Show PDF       │
│  - Show extracted │
│  - Edit fields    │
└────┬──────────────┘
      │ 4. POST /api/validation/approve
      ▼
┌──────────────────┐
│  FastAPI Server  │
│  - Validate data │
│  - Insert to EHR │
└────┬─────────────┘
      │ 5. Save to EHR tables
      ▼
┌──────────────────┐
│  PostgreSQL      │
│  - patients      │
│  - diagnoses     │
│  - medications   │
└──────────────────┘
```

---

## 7. Deployment Architecture

### 7.1 Current Deployment (Kubernetes)

```
┌─────────────────────────────────────────────────────────┐
│              Kubernetes Cluster (Emergent)              │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Nginx Ingress Controller                          │  │
│  │  - Route /api/* → Backend Pod (8001)              │  │
│  │  - Route /* → Frontend Pod (3000)                 │  │
│  └────────────────┬──────────────────────────────────┘  │
│                   │                                      │
│  ┌────────────────┴────────────┐                        │
│  │                              │                        │
│  ▼                              ▼                        │
│  ┌──────────────┐    ┌──────────────────┐              │
│  │  Frontend    │    │  Backend         │              │
│  │  React SPA   │    │  FastAPI         │              │
│  │  Port: 3000  │    │  Port: 8001      │              │
│  │              │    │  - Supervisor    │              │
│  └──────────────┘    │  - Hot reload    │              │
│                      └──────────────────┘              │
└─────────────────────────────────────────────────────────┘
          │                        │
          │                        │
          ▼                        ▼
┌──────────────────┐    ┌──────────────────┐
│  Supabase Cloud  │    │  MongoDB Atlas   │
│  (PostgreSQL)    │    │  (Document Store)│
└──────────────────┘    └──────────────────┘
```

### 7.2 Process Management (Supervisor)

```ini
[program:backend]
command=uvicorn server:app --host 0.0.0.0 --port 8001 --reload
directory=/app/backend
autostart=true
autorestart=true

[program:frontend]
command=yarn start
directory=/app/frontend
autostart=true
autorestart=true
```

### 7.3 Environment Variables

**Backend (.env):**
```bash
# Database
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=xxx
MONGO_URL=mongodb+srv://xxx

# Authentication
JWT_SECRET_KEY=xxx

# External Services
LANDINGAI_API_KEY=xxx
LANDINGAI_ENDPOINT=xxx
```

**Frontend (.env):**
```bash
REACT_APP_BACKEND_URL=https://xxx/api
```

---

## 8. Security & Compliance

### 8.1 Data Security

**At Rest:**
- PostgreSQL: Encrypted at rest (Supabase default)
- MongoDB: Encrypted at rest (Atlas default)
- Passwords: Bcrypt hashed with salt

**In Transit:**
- HTTPS/TLS 1.2+ for all connections
- JWT tokens for API authentication
- Secure WebSocket connections (future)

**Access Control:**
- Row-level security (workspace filtering)
- Role-based permissions
- Audit logging (future)

### 8.2 Healthcare Compliance (Roadmap)

**POPIA (South Africa):**
- Consent management
- Data subject rights (access, deletion)
- Data breach notification

**HIPAA (USA):**
- PHI encryption
- Access logs
- Minimum necessary access

**GDPR (Europe):**
- Right to erasure
- Data portability
- Privacy by design

### 8.3 Audit Trail (Future)

```sql
audit_logs (
  id UUID PRIMARY KEY,
  user_id UUID,
  action VARCHAR, -- login, upload, approve, export
  resource_type VARCHAR, -- document, user, workspace
  resource_id UUID,
  ip_address VARCHAR,
  user_agent VARCHAR,
  timestamp TIMESTAMP
)
```

---

## 9. Performance & Scalability

### 9.1 Current Performance

**API Response Times:**
- Authentication: < 200ms
- Document list: < 500ms
- Document upload: 2-5s (depends on file size)
- Parsing (LandingAI): 5-15s per document
- Extraction: 1-3s

**Database Queries:**
- Indexed queries: < 50ms
- Workspace filtering: < 100ms
- Document search: < 200ms

### 9.2 Scalability Considerations

**Horizontal Scaling:**
- Stateless backend (can add more pods)
- Load balancing via Kubernetes
- Database connection pooling

**Vertical Scaling:**
- Increase pod resources (CPU, memory)
- Database read replicas (Supabase/MongoDB)

**Bottlenecks:**
- LandingAI API rate limits (async queue needed)
- File storage (implement CDN/S3)
- Large PDF processing (chunk processing)

### 9.3 Optimization Roadmap

**Phase 1: Caching**
- Redis for session storage
- CDN for static assets
- Browser caching headers

**Phase 2: Async Processing**
- Celery/RQ for background jobs
- Queue for document processing
- Webhook notifications

**Phase 3: Database Optimization**
- Query optimization
- Materialized views for analytics
- Partitioning large tables

---

## 10. Monitoring & Observability (Future)

### 10.1 Logging

**Application Logs:**
```python
import logging

logger = logging.getLogger(__name__)
logger.info(f"User {user_id} uploaded document {doc_id}")
logger.error(f"Parsing failed for {doc_id}: {error}")
```

**Log Aggregation:**
- Centralized logging (ELK stack or equivalent)
- Structured JSON logs
- Log retention policies

### 10.2 Metrics

**Key Performance Indicators:**
- Documents processed per hour
- Validation queue length
- Average validation time
- Error rates by endpoint
- User activity metrics

**Health Checks:**
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": check_db_connection(),
        "external_api": check_landingai_status()
    }
```

### 10.3 Alerts

**Critical Alerts:**
- Database connection failures
- External API downtime
- High error rates (> 5%)
- Queue backlog (> 100 documents)
- Security incidents

---

## 11. Integration Capabilities

### 11.1 Current Integrations

**LandingAI (Document Parsing):**
```python
response = httpx.post(
    "https://api.landing.ai/v1/parse",
    headers={"Authorization": f"Bearer {API_KEY}"},
    files={"file": pdf_bytes}
)
parsed_data = response.json()
```

**Supabase (Backend Services):**
```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
result = supabase.table('users').select('*').execute()
```

**MongoDB (Document Storage):**
```python
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(MONGO_URL)
db = client['surgiscan_documents']
collection = db['gp_parsed_documents']
```

### 11.2 Future Integrations

**EHR Systems:**
- HL7 FHIR API export
- HL7 v2 message generation
- Direct database connections

**Practice Management Systems:**
- Medisoft, Meditrac, eQuality
- Real-time patient matching
- Appointment integration

**Payment Systems:**
- PayFast (partially implemented)
- Medical aid billing
- Invoice generation

**Notification Services:**
- Email (SendGrid, SMTP)
- SMS (Twilio, Clickatell)
- Push notifications

---

## 12. Development Practices

### 12.1 Code Organization

**Backend Structure:**
```
/app/backend/
├── server.py              # Main FastAPI app
├── app/
│   ├── api/               # API endpoints
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── workspaces.py
│   │   ├── gp_endpoints.py
│   │   └── validation.py
│   ├── services/          # Business logic
│   │   ├── gp_processor.py
│   │   ├── extraction_engine.py
│   │   └── batch_upload_service.py
│   └── core/              # Configuration
│       └── config.py
├── database/              # SQL migrations
└── requirements.txt       # Python dependencies
```

**Frontend Structure:**
```
/app/frontend/
├── src/
│   ├── App.js             # Main routing
│   ├── contexts/          # React contexts
│   │   └── AuthContext.jsx
│   ├── components/        # Reusable components
│   │   ├── Layout.jsx
│   │   ├── ui/            # Shadcn components
│   │   └── ProtectedRoute.jsx
│   ├── pages/             # Page components
│   │   ├── Login.jsx
│   │   ├── UserManagement.jsx
│   │   ├── WorkspaceManagement.jsx
│   │   ├── DigitizationModule.jsx
│   │   └── ValidationReview.jsx
│   └── services/          # API clients
│       └── gp.js
└── package.json           # Node dependencies
```

### 12.2 Testing Strategy (Roadmap)

**Backend Tests:**
```python
# Unit tests
def test_password_hashing():
    hash = get_password_hash("password123")
    assert verify_password("password123", hash)

# Integration tests
async def test_user_creation():
    response = await client.post("/api/users/", json={...})
    assert response.status_code == 201

# End-to-end tests
async def test_document_workflow():
    # Upload → Parse → Extract → Validate → Approve
    pass
```

**Frontend Tests:**
```javascript
// Component tests (Jest + React Testing Library)
test('login form submits correctly', () => {
  render(<Login />);
  // Test assertions
});

// E2E tests (Playwright)
test('complete document upload workflow', async ({ page }) => {
  // Full user journey
});
```

### 12.3 CI/CD Pipeline (Future)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    - Run backend tests
    - Run frontend tests
    - Lint code
  
  build:
    - Build Docker images
    - Push to registry
  
  deploy:
    - Deploy to Kubernetes
    - Run smoke tests
    - Notify team
```

---

## 13. Roadmap & Future Enhancements

### 13.1 Short-Term (Q1 2026)

**Phase 1: Production Hardening**
- Usage limit enforcement
- Comprehensive error handling
- Performance optimization
- Security audit

**Phase 2: Enhanced Validation**
- Confidence score display
- Bulk validation actions
- Validator performance metrics
- Quality assurance dashboard

**Phase 3: Analytics**
- Workspace usage dashboard
- Document processing metrics
- User activity tracking
- Custom reports

### 13.2 Medium-Term (Q2-Q3 2026)

**Phase 4: Email & Notifications**
- Welcome emails
- Password reset
- User invitations
- Real-time notifications

**Phase 5: API Access**
- REST API keys for clients
- Webhook support
- Rate limiting
- API documentation portal

**Phase 6: Advanced Features**
- Batch operations UI
- Document versioning
- Approval workflows
- Custom extraction templates UI

### 13.3 Long-Term (Q4 2026+)

**Phase 7: EHR Integration**
- FHIR API compliance
- HL7 v2 messaging
- Direct EHR connections
- Patient matching algorithms

**Phase 8: AI Enhancements**
- Custom model training
- Handwriting recognition
- Multi-language support
- Confidence improvement

**Phase 9: Compliance**
- HIPAA compliance certification
- POPIA compliance
- ISO 27001 certification
- SOC 2 Type II

---

## 14. Known Limitations & Risks

### 14.1 Current Limitations

**Technical:**
- No real-time collaboration (multiple validators on same document)
- Limited file format support (PDF only currently)
- No offline mode
- Manual patient matching required

**Scalability:**
- LandingAI API rate limits (need queuing)
- File storage not optimized (local storage vs CDN)
- No horizontal scaling for parsing jobs

**Security:**
- No 2FA/MFA
- No IP whitelisting
- Limited audit logging
- No data encryption at application level

### 14.2 Risk Mitigation

**Data Loss:**
- Daily automated backups (Supabase/MongoDB)
- Point-in-time recovery
- Disaster recovery plan (future)

**External API Failure:**
- Queue system for retry logic
- Alternative parsing service (future)
- Graceful degradation

**Security Breach:**
- Regular security audits
- Penetration testing (future)
- Incident response plan
- Bug bounty program (future)

---

## 15. Support & Maintenance

### 15.1 Support Tiers

**Standard Support (Included):**
- Email support (24-hour response)
- Bug fixes
- Security patches
- Quarterly feature updates

**Premium Support (Professional+):**
- Priority support (4-hour response)
- Dedicated account manager
- Custom feature development
- Training sessions

**Enterprise Support:**
- 24/7 phone support
- SLA guarantees (99.9% uptime)
- On-site training
- Custom integrations

### 15.2 Maintenance Windows

**Scheduled Maintenance:**
- Every Sunday 2:00-4:00 AM SAST
- Notification 48 hours in advance
- Zero-downtime deployments (future)

**Emergency Maintenance:**
- Critical security patches
- Data corruption fixes
- Immediate notification

---

## 16. Cost Structure (Infrastructure)

### 16.1 Current Costs (Estimates)

**Hosting:**
- Kubernetes cluster: Included (Emergent platform)
- Compute: $0-200/month (depending on usage)

**Databases:**
- Supabase (PostgreSQL): $25-100/month
- MongoDB Atlas: $50-200/month

**External Services:**
- LandingAI: Pay-per-document (~$0.10/document)
- Storage (future CDN): $10-50/month

**Total Estimated:** $100-550/month base + variable per document

### 16.2 Pricing Model (DaaS)

**Subscription Tiers:**
- Free: 1,000 docs/month, $0
- Basic: 5,000 docs/month, $500/month
- Professional: 10,000 docs/month, $1,500/month
- Enterprise: Unlimited, custom pricing

**Additional Charges:**
- Extra documents: $0.15/document
- Storage overage: $0.10/GB
- API access: $100/month
- Premium support: $300/month

---

## 17. Conclusion

SurgiScan is a production-ready, multi-tenant digitization platform designed for healthcare organizations. The architecture emphasizes:

✅ **Scalability:** Multi-tenant design supports multiple clients
✅ **Security:** Role-based access, JWT authentication, workspace isolation
✅ **Flexibility:** Template-driven extraction adapts to new document types
✅ **Reliability:** Human validation ensures accuracy
✅ **Extensibility:** Modular architecture supports future enhancements

**Current Status:** Beta launch ready (95% complete)

**Primary Use Case:** Medical document digitization as a service for South African healthcare providers

**Differentiator:** No-code template configuration eliminates custom development for new document types

---

## 18. Technical Specifications Summary

| **Aspect** | **Details** |
|------------|-------------|
| **Frontend** | React 18, SPA, TailwindCSS |
| **Backend** | FastAPI (Python 3.9+), REST API |
| **Databases** | PostgreSQL (Supabase), MongoDB Atlas |
| **Authentication** | JWT tokens, bcrypt, RBAC |
| **Deployment** | Kubernetes, Supervisor, Nginx |
| **AI Parsing** | LandingAI ADE DPT-2 |
| **Multi-Tenancy** | Workspace isolation, logical separation |
| **Performance** | < 500ms API, 5-15s parsing |
| **Security** | HTTPS, encrypted at rest, role-based |
| **Scalability** | Horizontal (pods), vertical (resources) |

---

## Appendix A: API Examples

### A.1 Authentication Flow

**Login:**
```bash
curl -X POST https://surgiscan.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "validator@clinic.com",
    "password": "password123"
  }'

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "validator@clinic.com",
    "role": "validator",
    "workspace_id": "clinic-abc-123"
  }
}
```

**Authenticated Request:**
```bash
curl -X GET https://surgiscan.app/api/gp/documents \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### A.2 Document Upload

```bash
curl -X POST https://surgiscan.app/api/gp/upload \
  -H "Authorization: Bearer {token}" \
  -F "file=@patient_record.pdf" \
  -F "patient_id=patient-123" \
  -F "document_type=patient_demographics"

# Response:
{
  "document_id": "doc-uuid",
  "status": "parsing",
  "filename": "patient_record.pdf",
  "pages_count": 3,
  "upload_date": "2025-10-31T12:00:00Z"
}
```

### A.3 Validation Queue

```bash
curl -X GET https://surgiscan.app/api/validation/queue/list \
  -H "Authorization: Bearer {token}"

# Response:
{
  "total": 15,
  "documents": [
    {
      "id": "doc-uuid",
      "filename": "patient_record.pdf",
      "status": "pending_validation",
      "upload_date": "2025-10-31T12:00:00Z",
      "urgency": "high"
    },
    ...
  ]
}
```

---

## Appendix B: Database ERD

```
┌──────────────┐         ┌──────────────────┐
│   users      │◄───────►│  workspace_users │
│              │         │                  │
│ • id (PK)    │         │ • workspace_id   │
│ • email      │         │ • user_id        │
│ • role       │         │ • role           │
│ • workspace_id        └──────────────────┘
└──────┬───────┘                 │
       │                         │
       │                         ▼
       │              ┌──────────────────┐
       │              │   workspaces     │
       │              │                  │
       │              │ • id (PK)        │
       │              │ • name           │
       │              │ • subscription   │
       │              └──────────────────┘
       │
       ▼
┌──────────────────────┐
│ digitised_documents  │
│                      │
│ • id (PK)            │
│ • workspace_id (FK)  │
│ • patient_id (FK)    │
│ • status             │
│ • parsed_doc_id      │ ──► MongoDB
└──────────────────────┘
```

---

## Document Control

**Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Oct 2025 | SurgiScan Team | Initial technical architecture document |

**Approval:**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Technical Lead | [Name] | [Date] | [Signature] |
| Product Owner | [Name] | [Date] | [Signature] |

---

**End of Document**

*For questions or clarifications, contact: tech@surgiscan.com*

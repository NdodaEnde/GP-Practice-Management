# SurgiScan Document Processing Microservice

A production-ready AI-powered microservice for processing historic medical documents, extracting structured data, and integrating with the SurgiScan platform.

## 🏥 Features

- **AI Document Processing**: Extract data from 6+ medical document types
- **Smart Document Detection**: Automatic document type identification
- **Validation Workflow**: Human validation for critical data
- **Cloud-Ready**: Deploy to Render, AWS, GCP, or local infrastructure
- **Scalable Architecture**: Async processing with proper error handling
- **Security**: API key authentication, input validation, rate limiting
- **Monitoring**: Structured logging, health checks, error tracking

## 📄 Supported Document Types

1. **Certificate of Fitness** - Medical fitness certifications
2. **Vision Test Reports** - Eye examination results
3. **Audiometric Tests** - Hearing assessment results
4. **Spirometry Reports** - Lung function test results
5. **Consent Forms** - Drug test consent documentation
6. **Medical Questionnaires** - Comprehensive health questionnaires

## 🚀 Quick Start

### Local Development

1. **Clone and setup**:
   ```bash
   cd document-processor-microservice
   cp .env.example .env  # Configure your environment
   ```

2. **Start with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

3. **Access the service**:
   - API: http://localhost:8000
   - Health Check: http://localhost:8000/health
   - API Docs: http://localhost:8000/docs (development only)
   - MongoDB Express: http://localhost:8081 (admin profile)

### Production Deployment on Render

1. **Connect GitHub repository** to Render
2. **Configure environment variables** in Render dashboard
3. **Deploy using render.yaml** configuration
4. **Set up MongoDB database** (included in render.yaml)

## 🔧 Configuration

### Required Environment Variables

```bash
# AI Processing
LANDING_AI_API_KEY=your-landing-ai-api-key
OPENAI_API_KEY=your-openai-api-key  # Optional

# Database
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=surgiscan_documents

# Security
SECRET_KEY=your-secret-key
API_KEY=your-api-key  # Optional but recommended

# CORS (for web integration)
CORS_ORIGINS=https://your-frontend.com,https://surgiscan.com
```

### Optional Environment Variables

```bash
# Processing
MAX_FILE_SIZE_MB=50
DEFAULT_PROCESSING_MODE=smart
MAX_CONCURRENT_PROCESSING=10

# Storage
STORAGE_TYPE=local  # or s3, gcs
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_BUCKET_NAME=your-bucket

# Monitoring
SENTRY_DSN=your-sentry-dsn
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

## 📡 API Endpoints

### Core Processing

- `POST /api/v1/historic-documents/upload` - Process single document
- `POST /api/v1/historic-documents/batch-upload` - Process multiple documents
- `GET /api/v1/historic-documents/{id}` - Get document data
- `GET /api/v1/historic-documents/{id}/status` - Get processing status

### Validation & Integration

- `PUT /api/v1/historic-documents/{id}/validate` - Validate extracted data
- `GET /api/v1/statistics` - Get processing statistics

### System

- `GET /health` - Health check
- `GET /docs` - API documentation (development only)

## 🔗 Integration with SurgiScan

### Upload Document

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('processing_mode', 'smart');
formData.append('save_to_database', 'true');

const response = await fetch('/api/v1/historic-documents/upload', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your-api-key'
  },
  body: formData
});

const result = await response.json();
console.log('Processing result:', result);
```

### Check Status

```javascript
const response = await fetch(`/api/v1/historic-documents/${documentId}/status`, {
  headers: {
    'Authorization': 'Bearer your-api-key'
  }
});

const status = await response.json();
console.log('Document status:', status);
```

### Validate Data

```javascript
const validatedData = {
  extracted_data: {
    // Your validated/corrected data
    patient_name: "John Doe",
    id_number: "1234567890123",
    // ... other fields
  },
  validation_notes: "Corrected patient name spelling"
};

const response = await fetch(`/api/v1/historic-documents/${documentId}/validate`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your-api-key'
  },
  body: JSON.stringify(validatedData)
});
```

## 🔍 Processing Modes

- **`smart`** (default): AI detection + fallback to common types
- **`fast`**: Process only common document types (fastest)
- **`extract_all`**: Try all document types (most comprehensive)
- **`detect_only`**: Use only AI detection (fail if detection fails)

## 📊 Response Format

### Successful Processing

```json
{
  "success": true,
  "document_id": "uuid-here",
  "filename": "certificate.pdf",
  "status": "completed",
  "document_types_found": ["certificate_of_fitness"],
  "extracted_data": {
    "certificate_of_fitness": {
      "initials_and_surname": "J. Doe",
      "id_number": "1234567890123",
      "company_name": "Acme Mining Corp",
      // ... more fields
    }
  },
  "confidence_score": 0.95,
  "needs_validation": false,
  "processing_summary": {
    "processing_time": 2.5,
    "total_fields_extracted": 15
  }
}
```

## 🛠 Development

### Project Structure

```
document-processor-microservice/
├── app/
│   ├── api/            # API models and validation
│   ├── core/           # Configuration and logging
│   ├── services/       # Business logic
│   ├── schemas/        # Document schemas
│   └── main.py         # FastAPI application
├── Dockerfile          # Container configuration
├── docker-compose.yml  # Local development
├── render.yaml         # Render deployment
└── requirements.txt    # Python dependencies
```

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

### Code Quality

```bash
# Format code
black app/
isort app/

# Lint
flake8 app/
```

## 📈 Monitoring & Logging

### Health Checks

The service provides comprehensive health checks:
- Database connectivity
- AI service availability
- File storage accessibility
- Processing capacity

### Logging

Structured JSON logging in production:
- Request/response logging
- Processing metrics
- Error tracking with Sentry integration
- Performance monitoring

### Metrics

Key metrics tracked:
- Documents processed per hour
- Average processing time
- Success/failure rates
- Validation accuracy
- Storage utilization

## 🔐 Security

- **Authentication**: API key based authentication
- **Input Validation**: File type, size, and content validation
- **Rate Limiting**: Configurable request limits
- **CORS**: Configurable cross-origin resource sharing
- **Secure Headers**: Security headers for production
- **Non-root Container**: Runs as non-privileged user

## 🚀 Deployment Guide

### Render Deployment

1. **Fork/Clone** this repository to your GitHub account
2. **Connect to Render** and create a new service
3. **Use render.yaml** for automatic configuration
4. **Set environment variables** in Render dashboard
5. **Deploy** - Render will build and deploy automatically

### Manual Deployment

```bash
# Build Docker image
docker build -t surgiscan-processor .

# Run container
docker run -p 8000:8000 \
  -e MONGODB_URL=your-mongo-url \
  -e LANDING_AI_API_KEY=your-api-key \
  surgiscan-processor
```

## 📞 Support & Integration

For integration with your SurgiScan platform:

1. **API Compatibility**: All endpoints match Historic Documents component expectations
2. **Webhook Support**: Configure `SURGISCAN_WEBHOOK_URL` for status updates
3. **Database Integration**: Extracted data can be automatically integrated with patient records
4. **Custom Validation**: Implement custom validation rules per your requirements

## 📄 License

This microservice is part of the SurgiScan platform and subject to the same licensing terms.
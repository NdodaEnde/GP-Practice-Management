"""
API models for request/response validation and documentation.
Compatible with the SurgiScan Historic Documents component.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator

from app.core.config import ProcessingMode, ProcessingStatus


# Enums for API
class DocumentTypeEnum(str, Enum):
    """Supported document types"""
    CERTIFICATE_OF_FITNESS = "certificate_of_fitness"
    VISION_TEST = "vision_test"
    AUDIOMETRIC_TEST = "audiometric_test"
    SPIROMETRY_REPORT = "spirometry_report"
    CONSENT_FORM = "consent_form"
    MEDICAL_QUESTIONNAIRE = "medical_questionnaire"


class ProcessingModeEnum(str, Enum):
    """Processing modes"""
    SMART = "smart"
    FAST = "fast"
    EXTRACT_ALL = "extract_all"
    DETECT_ONLY = "detect_only"


class ProcessingStatusEnum(str, Enum):
    """Processing status values"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"
    INTEGRATION_PENDING = "integration_pending"
    INTEGRATED = "integrated"


# Request Models
class DocumentUploadRequest(BaseModel):
    """Request for single document upload"""
    processing_mode: ProcessingModeEnum = ProcessingModeEnum.SMART
    save_to_database: bool = True
    patient_context: Optional[Dict[str, Any]] = Field(
        None, 
        description="Additional patient context for processing"
    )


class BatchUploadRequest(BaseModel):
    """Request for batch document upload"""
    processing_mode: ProcessingModeEnum = ProcessingModeEnum.SMART
    save_to_database: bool = True
    batch_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Metadata for the batch"
    )


class ValidationRequest(BaseModel):
    """Request to validate extracted data"""
    extracted_data: Dict[str, Any] = Field(
        ...,
        description="Validated/corrected extracted data"
    )
    validation_notes: Optional[str] = Field(
        None,
        description="Notes from the validator"
    )


# Response Models
class PatientInfo(BaseModel):
    """Patient information extracted from documents"""
    name: Optional[str] = None
    id_number: Optional[str] = None
    company_name: Optional[str] = None
    last_examination_date: Optional[str] = None


class ProcessingSummary(BaseModel):
    """Summary of document processing operation"""
    mode: ProcessingModeEnum
    document_types_attempted: int
    successful_extractions: int
    total_fields_extracted: int
    processing_time: float
    api_calls_made: int
    confidence_score: Optional[float] = None


class DatabaseInfo(BaseModel):
    """Database operation information"""
    status: str
    document_id: Optional[str] = None
    batch_id: Optional[str] = None
    saved_at: Optional[datetime] = None


class DocumentProcessingResult(BaseModel):
    """Result of document processing operation"""
    success: bool
    document_id: str
    filename: str
    status: ProcessingStatusEnum
    document_types_found: List[DocumentTypeEnum] = []
    extracted_data: Dict[str, Any] = {}
    processing_summary: ProcessingSummary
    patient_info: Optional[PatientInfo] = None
    database: DatabaseInfo
    created_at: datetime
    needs_validation: bool = False
    confidence_score: Optional[float] = None
    # NEW: Add grounding data fields
    chunks: List[Dict[str, Any]] = []
    pdf_metadata: Dict[str, Any] = {}


class BatchProcessingResult(BaseModel):
    """Result of batch processing operation"""
    success: bool
    batch_id: str
    total_files: int
    successful_extractions: int
    failed_extractions: int
    processing_mode: ProcessingModeEnum
    saved_to_database: bool
    results: List[DocumentProcessingResult] = []
    created_at: datetime


class DocumentStatus(BaseModel):
    """Status information for a processed document"""
    document_id: str
    filename: str
    status: ProcessingStatusEnum
    upload_date: datetime
    processing_complete_at: Optional[datetime] = None
    confidence_score: Optional[float] = None
    needs_validation: bool = False
    is_validated: bool = False
    document_types: List[DocumentTypeEnum] = []
    patient_info: Optional[PatientInfo] = None


class ValidationResponse(BaseModel):
    """Response after document validation"""
    success: bool
    document_id: str
    validation_status: str
    integration: Optional[Dict[str, Any]] = None
    patient_record: Optional[Dict[str, Any]] = None
    message: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    service: str = "SurgiScan Document Processor"
    version: str
    timestamp: datetime
    uptime_seconds: float
    mongodb_connected: bool
    supported_document_types: List[str]
    processing_modes: List[str]
    features: Dict[str, bool] = {}


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatisticsResponse(BaseModel):
    """Processing statistics response"""
    total_documents: int = 0
    unique_patients: int = 0
    companies_processed: int = 0
    document_types_found: List[str] = []
    processing_stats: Dict[str, int] = {}
    last_updated: datetime


# Integration Models (for SurgiScan compatibility)
class SurgiScanPatientData(BaseModel):
    """Patient data for SurgiScan integration"""
    initials: str
    firstName: str
    surname: str
    idNumber: str
    dateOfBirth: Optional[datetime] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    employerName: str
    position: Optional[str] = None
    department: Optional[str] = None
    examinationType: str


class SurgiScanExaminationData(BaseModel):
    """Examination data for SurgiScan integration"""
    patientId: str
    examinationType: str
    examinationDate: datetime
    fitnessStatus: str
    restrictions: List[str] = []
    medicalTests: Dict[str, Any] = {}
    certificates: List[Dict[str, Any]] = []


class IntegrationResult(BaseModel):
    """Result of SurgiScan integration"""
    success: bool
    patient: Optional[Dict[str, Any]] = None
    examination: Optional[Dict[str, Any]] = None
    is_new_patient: bool = False
    error: Optional[str] = None


# Utility models for internal use
class ProcessingJob(BaseModel):
    """Internal model for processing jobs"""
    job_id: str
    document_id: str
    filename: str
    file_path: str
    processing_mode: ProcessingModeEnum
    status: ProcessingStatusEnum
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# Webhook models
class WebhookPayload(BaseModel):
    """Payload for webhook notifications"""
    event: str
    document_id: str
    status: ProcessingStatusEnum
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Validators
class FileUploadValidator:
    """Validation utilities for file uploads"""
    
    @staticmethod
    def validate_file_size(file_size: int, max_size_mb: int = 50) -> bool:
        """Validate file size"""
        max_size_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_size_bytes
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """Validate file extension"""
        if '.' not in filename:
            return False
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in allowed_extensions
    
    @staticmethod
    def validate_content_type(content_type: str) -> bool:
        """Validate content type"""
        allowed_types = [
            'application/pdf',
            'image/png',
            'image/jpeg',
            'image/jpg',
            'image/tiff',
            'image/tif'
        ]
        return content_type in allowed_types
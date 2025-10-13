"""
Configuration settings for the document processing microservice.
Handles environment variables and deployment-specific settings.
"""

import os
import secrets
from typing import Optional, List, Union
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application Settings
    PROJECT_NAME: str = "SurgiScan Document Processor"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    API_KEY: Optional[str] = os.getenv("API_KEY")
    CORS_ORIGINS: Union[str, List[AnyHttpUrl]] = []
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # AI Processing Settings
    LANDING_AI_API_KEY: Optional[str] = os.getenv("LANDING_AI_API_KEY")
    VISION_AGENT_API_KEY: Optional[str] = os.getenv("VISION_AGENT_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    
    # Processing Configuration
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "png", "jpg", "jpeg", "tiff", "tif"]
    DEFAULT_PROCESSING_MODE: str = os.getenv("DEFAULT_PROCESSING_MODE", "smart")
    
    # Database Settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "surgiscan_documents")
    
    # Redis Settings (for async processing)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    CELERY_BROKER_URL: Optional[str] = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: Optional[str] = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    
    # File Storage
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")  # local, s3, gcs
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: Optional[str] = os.getenv("AWS_REGION", "us-east-1")
    AWS_BUCKET_NAME: Optional[str] = os.getenv("AWS_BUCKET_NAME")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    RATE_LIMIT_PER_HOUR: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
    
    # Integration Settings
    SURGISCAN_WEBHOOK_URL: Optional[str] = os.getenv("SURGISCAN_WEBHOOK_URL")
    SURGISCAN_API_KEY: Optional[str] = os.getenv("SURGISCAN_API_KEY")
    
    # Processing Timeouts
    PROCESSING_TIMEOUT_SECONDS: int = int(os.getenv("PROCESSING_TIMEOUT_SECONDS", "300"))
    MAX_CONCURRENT_PROCESSING: int = int(os.getenv("MAX_CONCURRENT_PROCESSING", "10"))
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"


# Global settings instance
settings = Settings()


# Processing modes configuration
class ProcessingMode:
    SMART = "smart"          # Detection + fallback
    FAST = "fast"            # Common types only
    EXTRACT_ALL = "extract_all"  # All document types
    DETECT_ONLY = "detect_only"  # Detection only


# Document type mappings
DOCUMENT_TYPES = {
    "certificate_of_fitness": "Certificate of Fitness",
    "vision_test": "Vision Test Report", 
    "audiometric_test": "Audiometric Test Results",
    "spirometry_report": "Spirometry Report",
    "consent_form": "Drug Test Consent Form",
    "medical_questionnaire": "Medical Questionnaire"
}

# Status codes for processing
class ProcessingStatus:
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"
    INTEGRATION_PENDING = "integration_pending"
    INTEGRATED = "integrated"


# Error codes
class ErrorCodes:
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTEGRATION_FAILED = "INTEGRATION_FAILED"

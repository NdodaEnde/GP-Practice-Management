"""
File storage service for document management.
Handles temporary and permanent file storage with support for local and cloud storage.
"""

import os
import uuid
import tempfile
import shutil
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime
from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class StorageManager:
    """File storage manager with support for different storage backends"""
    
    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE
        self.temp_dir = tempfile.gettempdir()
        self.local_storage_dir = os.path.join(os.getcwd(), "storage", "documents")
        
        # Ensure local storage directory exists
        os.makedirs(self.local_storage_dir, exist_ok=True)
        
        # Initialize cloud storage if configured
        self.cloud_client = None
        if self.storage_type in ["s3", "gcs"]:
            self._init_cloud_storage()
    
    def _init_cloud_storage(self):
        """Initialize cloud storage client"""
        
        if self.storage_type == "s3":
            try:
                import boto3
                self.cloud_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION
                )
                logger.info("AWS S3 client initialized")
            except ImportError:
                logger.error("boto3 not installed, falling back to local storage")
                self.storage_type = "local"
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}, falling back to local storage")
                self.storage_type = "local"
        
        elif self.storage_type == "gcs":
            try:
                from google.cloud import storage
                self.cloud_client = storage.Client()
                logger.info("Google Cloud Storage client initialized")
            except ImportError:
                logger.error("google-cloud-storage not installed, falling back to local storage")
                self.storage_type = "local"
            except Exception as e:
                logger.error(f"Failed to initialize GCS client: {e}, falling back to local storage")
                self.storage_type = "local"
    
    async def save_temp_file(self, file: UploadFile) -> str:
        """Save uploaded file to temporary location"""
        
        try:
            # Generate unique filename
            file_extension = ""
            if file.filename and '.' in file.filename:
                file_extension = '.' + file.filename.rsplit('.', 1)[1].lower()
            
            temp_filename = f"{uuid.uuid4()}{file_extension}"
            temp_path = os.path.join(self.temp_dir, temp_filename)
            
            # Save file
            with open(temp_path, "wb") as temp_file:
                content = await file.read()
                temp_file.write(content)
            
            logger.info(f"Temporary file saved: {temp_filename}", 
                       extra={"temp_path": temp_path, "file_size": len(content)})
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to save temporary file: {e}", 
                        extra={"filename": file.filename})
            raise
    
    async def store_file(
        self, 
        temp_path: str, 
        original_filename: str, 
        document_id: str
    ) -> Optional[str]:
        """Store file permanently using configured storage backend"""
        
        try:
            if self.storage_type == "local":
                return await self._store_file_local(temp_path, original_filename, document_id)
            elif self.storage_type == "s3":
                return await self._store_file_s3(temp_path, original_filename, document_id)
            elif self.storage_type == "gcs":
                return await self._store_file_gcs(temp_path, original_filename, document_id)
            else:
                logger.error(f"Unsupported storage type: {self.storage_type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to store file permanently: {e}", 
                        extra={
                            "temp_path": temp_path,
                            "filename": original_filename,
                            "document_id": document_id,
                            "storage_type": self.storage_type
                        })
            return None
    
    async def _store_file_local(
        self, 
        temp_path: str, 
        original_filename: str, 
        document_id: str
    ) -> str:
        """Store file in local filesystem"""
        
        # Create directory structure: storage/documents/YYYY/MM/
        now = datetime.utcnow()
        year_month_dir = os.path.join(
            self.local_storage_dir, 
            str(now.year), 
            f"{now.month:02d}"
        )
        os.makedirs(year_month_dir, exist_ok=True)
        
        # Generate stored filename
        file_extension = ""
        if '.' in original_filename:
            file_extension = '.' + original_filename.rsplit('.', 1)[1].lower()
        
        stored_filename = f"{document_id}{file_extension}"
        stored_path = os.path.join(year_month_dir, stored_filename)
        
        # Copy file to permanent location
        shutil.copy2(temp_path, stored_path)
        
        # Generate file URL (relative path for local storage)
        relative_path = os.path.relpath(stored_path, self.local_storage_dir)
        file_url = f"/storage/documents/{relative_path.replace(os.sep, '/')}"
        
        logger.info(f"File stored locally: {stored_filename}", 
                   extra={
                       "document_id": document_id,
                       "stored_path": stored_path,
                       "file_url": file_url
                   })
        
        return file_url
    
    async def _store_file_s3(
        self, 
        temp_path: str, 
        original_filename: str, 
        document_id: str
    ) -> str:
        """Store file in AWS S3"""
        
        if not self.cloud_client or not settings.AWS_BUCKET_NAME:
            raise ValueError("S3 not properly configured")
        
        # Generate S3 key
        now = datetime.utcnow()
        file_extension = ""
        if '.' in original_filename:
            file_extension = '.' + original_filename.rsplit('.', 1)[1].lower()
        
        s3_key = f"documents/{now.year}/{now.month:02d}/{document_id}{file_extension}"
        
        # Upload to S3
        with open(temp_path, 'rb') as file_data:
            self.cloud_client.upload_fileobj(
                file_data,
                settings.AWS_BUCKET_NAME,
                s3_key,
                ExtraArgs={
                    'ContentType': self._get_content_type(original_filename),
                    'Metadata': {
                        'document_id': document_id,
                        'original_filename': original_filename,
                        'upload_date': now.isoformat()
                    }
                }
            )
        
        # Generate file URL
        file_url = f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
        
        logger.info(f"File stored in S3: {s3_key}", 
                   extra={
                       "document_id": document_id,
                       "bucket": settings.AWS_BUCKET_NAME,
                       "file_url": file_url
                   })
        
        return file_url
    
    async def _store_file_gcs(
        self, 
        temp_path: str, 
        original_filename: str, 
        document_id: str
    ) -> str:
        """Store file in Google Cloud Storage"""
        
        if not self.cloud_client or not settings.GCS_BUCKET_NAME:
            raise ValueError("GCS not properly configured")
        
        # Generate GCS blob name
        now = datetime.utcnow()
        file_extension = ""
        if '.' in original_filename:
            file_extension = '.' + original_filename.rsplit('.', 1)[1].lower()
        
        blob_name = f"documents/{now.year}/{now.month:02d}/{document_id}{file_extension}"
        
        # Upload to GCS
        bucket = self.cloud_client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        with open(temp_path, 'rb') as file_data:
            blob.upload_from_file(
                file_data,
                content_type=self._get_content_type(original_filename)
            )
        
        # Set metadata
        blob.metadata = {
            'document_id': document_id,
            'original_filename': original_filename,
            'upload_date': now.isoformat()
        }
        blob.patch()
        
        # Generate file URL
        file_url = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{blob_name}"
        
        logger.info(f"File stored in GCS: {blob_name}", 
                   extra={
                       "document_id": document_id,
                       "bucket": settings.GCS_BUCKET_NAME,
                       "file_url": file_url
                   })
        
        return file_url
    
    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension"""
        
        if not filename or '.' not in filename:
            return 'application/octet-stream'
        
        extension = filename.rsplit('.', 1)[1].lower()
        
        content_types = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'tiff': 'image/tiff',
            'tif': 'image/tiff'
        }
        
        return content_types.get(extension, 'application/octet-stream')
    
    async def get_file(self, file_url: str) -> Optional[bytes]:
        """Retrieve file content by URL"""
        
        try:
            if self.storage_type == "local":
                return await self._get_file_local(file_url)
            elif self.storage_type == "s3":
                return await self._get_file_s3(file_url)
            elif self.storage_type == "gcs":
                return await self._get_file_gcs(file_url)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve file: {e}", 
                        extra={"file_url": file_url})
            return None
    
    async def _get_file_local(self, file_url: str) -> Optional[bytes]:
        """Get file from local storage"""
        
        # Convert URL to local path
        if file_url.startswith("/storage/documents/"):
            relative_path = file_url[len("/storage/documents/"):]
            file_path = os.path.join(self.local_storage_dir, relative_path.replace('/', os.sep))
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    return f.read()
        
        return None
    
    async def _get_file_s3(self, file_url: str) -> Optional[bytes]:
        """Get file from S3"""
        
        if not self.cloud_client:
            return None
        
        try:
            # Extract bucket and key from URL
            # URL format: https://bucket.s3.region.amazonaws.com/key
            parts = file_url.replace('https://', '').split('/')
            bucket = parts[0].split('.')[0]
            key = '/'.join(parts[1:])
            
            response = self.cloud_client.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
            
        except Exception as e:
            logger.error(f"Failed to get file from S3: {e}")
            return None
    
    async def _get_file_gcs(self, file_url: str) -> Optional[bytes]:
        """Get file from GCS"""
        
        if not self.cloud_client:
            return None
        
        try:
            # Extract bucket and blob name from URL
            # URL format: https://storage.googleapis.com/bucket/blob
            parts = file_url.replace('https://storage.googleapis.com/', '').split('/', 1)
            bucket_name = parts[0]
            blob_name = parts[1] if len(parts) > 1 else ''
            
            bucket = self.cloud_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            return blob.download_as_bytes()
            
        except Exception as e:
            logger.error(f"Failed to get file from GCS: {e}")
            return None
    
    async def delete_file(self, file_url: str) -> bool:
        """Delete file by URL"""
        
        try:
            if self.storage_type == "local":
                return await self._delete_file_local(file_url)
            elif self.storage_type == "s3":
                return await self._delete_file_s3(file_url)
            elif self.storage_type == "gcs":
                return await self._delete_file_gcs(file_url)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete file: {e}", 
                        extra={"file_url": file_url})
            return False
    
    async def _delete_file_local(self, file_url: str) -> bool:
        """Delete file from local storage"""
        
        if file_url.startswith("/storage/documents/"):
            relative_path = file_url[len("/storage/documents/"):]
            file_path = os.path.join(self.local_storage_dir, relative_path.replace('/', os.sep))
            
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        
        return False
    
    async def _delete_file_s3(self, file_url: str) -> bool:
        """Delete file from S3"""
        
        if not self.cloud_client:
            return False
        
        try:
            parts = file_url.replace('https://', '').split('/')
            bucket = parts[0].split('.')[0]
            key = '/'.join(parts[1:])
            
            self.cloud_client.delete_object(Bucket=bucket, Key=key)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    async def _delete_file_gcs(self, file_url: str) -> bool:
        """Delete file from GCS"""
        
        if not self.cloud_client:
            return False
        
        try:
            parts = file_url.replace('https://storage.googleapis.com/', '').split('/', 1)
            bucket_name = parts[0]
            blob_name = parts[1] if len(parts) > 1 else ''
            
            bucket = self.cloud_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file from GCS: {e}")
            return False
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up old temporary files"""
        
        try:
            current_time = datetime.utcnow().timestamp()
            max_age_seconds = max_age_hours * 3600
            cleaned_count = 0
            
            for temp_file in os.listdir(self.temp_dir):
                temp_path = os.path.join(self.temp_dir, temp_file)
                
                if os.path.isfile(temp_path):
                    file_age = current_time - os.path.getmtime(temp_path)
                    
                    if file_age > max_age_seconds:
                        try:
                            os.remove(temp_path)
                            cleaned_count += 1
                        except OSError:
                            pass  # File might be in use
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} temporary files")
                
        except Exception as e:
            logger.error(f"Failed to cleanup temporary files: {e}")
    
    def get_storage_info(self) -> dict:
        """Get storage configuration information"""
        
        return {
            "storage_type": self.storage_type,
            "local_storage_dir": self.local_storage_dir if self.storage_type == "local" else None,
            "cloud_configured": self.cloud_client is not None,
            "temp_dir": self.temp_dir
        }
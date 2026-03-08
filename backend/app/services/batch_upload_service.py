"""
Batch Upload Service
Handles multiple document uploads with queue management and progress tracking
"""

import asyncio
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class FileStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchUploadService:
    """
    Service for processing multiple documents in batches
    """
    
    def __init__(self, db_manager, supabase_client):
        self.db = db_manager.db
        self.supabase = supabase_client
        # In-memory queue for simplicity (can be replaced with Redis/MongoDB queue)
        self.processing_batches: Dict[str, Dict] = {}
        
    def create_batch(
        self,
        workspace_id: str,
        tenant_id: str,
        files_info: List[Dict],
        patient_id: Optional[str] = None,
        template_id: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> str:
        """
        Create a new batch upload record
        
        Args:
            workspace_id: Workspace identifier
            tenant_id: Tenant identifier
            files_info: List of file information dictionaries
            patient_id: Optional patient ID for all files
            template_id: Optional template ID to use
            created_by: User who initiated the batch
            
        Returns:
            batch_id: Unique identifier for the batch
        """
        batch_id = str(uuid.uuid4())
        
        batch_record = {
            'id': batch_id,
            'workspace_id': workspace_id,
            'tenant_id': tenant_id,
            'patient_id': patient_id,
            'template_id': template_id,
            'total_files': len(files_info),
            'status': 'pending',
            'files': [
                {
                    'file_id': str(uuid.uuid4()),
                    'filename': f['filename'],
                    'file_size': f['size'],
                    'status': FileStatus.PENDING,
                    'document_id': None,
                    'error': None
                }
                for f in files_info
            ],
            'progress': {
                'pending': len(files_info),
                'processing': 0,
                'completed': 0,
                'failed': 0
            },
            'created_by': created_by,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'started_at': None,
            'completed_at': None
        }
        
        # Store in memory
        self.processing_batches[batch_id] = batch_record
        
        logger.info(f"📦 Created batch {batch_id} with {len(files_info)} files")
        
        return batch_id
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get current status of a batch"""
        return self.processing_batches.get(batch_id)
    
    def update_file_status(
        self,
        batch_id: str,
        file_id: str,
        status: FileStatus,
        document_id: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict] = None
    ):
        """Update the status of a specific file in the batch"""
        if batch_id not in self.processing_batches:
            logger.error(f"Batch {batch_id} not found")
            return
        
        batch = self.processing_batches[batch_id]
        
        # Find and update the file
        for file_info in batch['files']:
            if file_info['file_id'] == file_id:
                old_status = file_info['status']
                file_info['status'] = status
                file_info['document_id'] = document_id
                file_info['error'] = error
                
                if result:
                    file_info['result'] = result
                
                # Update progress counts
                if old_status != status:
                    batch['progress'][old_status] -= 1
                    batch['progress'][status] += 1
                
                logger.info(f"📄 File {file_info['filename']}: {old_status} → {status}")
                break
        
        # Check if batch is complete
        if batch['progress']['pending'] == 0 and batch['progress']['processing'] == 0:
            batch['status'] = 'completed'
            batch['completed_at'] = datetime.now(timezone.utc).isoformat()
            logger.info(f"✅ Batch {batch_id} completed: {batch['progress']['completed']} succeeded, {batch['progress']['failed']} failed")
    
    async def process_batch(
        self,
        batch_id: str,
        files_data: List[Dict],  # [{file_id, file_content, file_path}]
        processor,  # GPDocumentProcessor instance
        workspace_id: str,
        tenant_id: str,
        patient_id: Optional[str] = None,
        template_id: Optional[str] = None,
        encounter_id: Optional[str] = None
    ):
        """
        Process all files in a batch
        
        Args:
            batch_id: Batch identifier
            files_data: List of file data with file_id, content, and path
            processor: GPDocumentProcessor instance
            workspace_id: Workspace ID
            tenant_id: Tenant ID
            patient_id: Optional patient ID
            template_id: Optional template ID
            encounter_id: Optional encounter ID
        """
        if batch_id not in self.processing_batches:
            logger.error(f"Batch {batch_id} not found")
            return
        
        batch = self.processing_batches[batch_id]
        batch['status'] = 'processing'
        batch['started_at'] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"🚀 Starting batch processing: {batch_id} ({len(files_data)} files)")
        
        # Process files sequentially (can be parallelized with asyncio.gather if needed)
        for file_data in files_data:
            file_id = file_data['file_id']
            file_path = file_data['file_path']
            filename = file_data['filename']
            file_content = file_data.get('file_content')
            
            try:
                # Update status to processing
                self.update_file_status(batch_id, file_id, FileStatus.PROCESSING)
                
                logger.info(f"📄 Processing file: {filename}")
                
                # Process with template-driven extraction
                result = await processor.process_with_template(
                    file_path=file_path,
                    filename=filename,
                    organization_id=workspace_id,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    template_id=template_id,
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    file_data=file_content
                )
                
                if result.get('success'):
                    # Success!
                    self.update_file_status(
                        batch_id,
                        file_id,
                        FileStatus.COMPLETED,
                        document_id=result.get('document_id'),
                        result=result
                    )
                else:
                    # Failed
                    self.update_file_status(
                        batch_id,
                        file_id,
                        FileStatus.FAILED,
                        error=result.get('error', 'Unknown error')
                    )
                
            except Exception as e:
                logger.error(f"❌ Failed to process {filename}: {e}", exc_info=True)
                self.update_file_status(
                    batch_id,
                    file_id,
                    FileStatus.FAILED,
                    error=str(e)
                )
            
            # Small delay to prevent overwhelming the system
            await asyncio.sleep(0.5)
        
        logger.info(f"✅ Batch processing complete: {batch_id}")
        
        # Save final batch record to database
        await self._save_batch_record(batch_id)
    
    async def _save_batch_record(self, batch_id: str):
        """Save batch record to MongoDB for persistence"""
        if batch_id not in self.processing_batches:
            return
        
        batch = self.processing_batches[batch_id]
        
        try:
            # Save to MongoDB
            await self.db['batch_uploads'].update_one(
                {'id': batch_id},
                {'$set': batch},
                upsert=True
            )
            logger.info(f"💾 Saved batch record: {batch_id}")
        except Exception as e:
            logger.error(f"Failed to save batch record: {e}")
    
    async def get_batch_history(
        self,
        workspace_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """Get recent batch uploads for a workspace"""
        try:
            cursor = self.db['batch_uploads'].find(
                {'workspace_id': workspace_id}
            ).sort('created_at', -1).limit(limit)
            
            batches = await cursor.to_list(length=limit)
            return batches
        except Exception as e:
            logger.error(f"Failed to get batch history: {e}")
            return []
    
    def cleanup_completed_batches(self, older_than_hours: int = 24):
        """
        Clean up completed batches from memory that are older than specified hours
        Keeps them in database but removes from active memory
        """
        cutoff_time = datetime.now(timezone.utc).timestamp() - (older_than_hours * 3600)
        
        batches_to_remove = []
        for batch_id, batch in self.processing_batches.items():
            if batch['status'] == 'completed':
                completed_at = datetime.fromisoformat(batch['completed_at'].replace('Z', '+00:00'))
                if completed_at.timestamp() < cutoff_time:
                    batches_to_remove.append(batch_id)
        
        for batch_id in batches_to_remove:
            del self.processing_batches[batch_id]
            logger.info(f"🧹 Cleaned up old batch: {batch_id}")
        
        if batches_to_remove:
            logger.info(f"🧹 Cleaned up {len(batches_to_remove)} old batches")


# Singleton instance
_batch_service_instance = None


def get_batch_service(db_manager=None, supabase_client=None):
    """Get or create batch service instance"""
    global _batch_service_instance
    
    if _batch_service_instance is None and db_manager and supabase_client:
        _batch_service_instance = BatchUploadService(db_manager, supabase_client)
    
    return _batch_service_instance

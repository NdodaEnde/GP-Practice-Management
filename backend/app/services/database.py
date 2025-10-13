"""
Database service for MongoDB operations.
Handles document storage, retrieval, and management.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from app.core.config import settings, ProcessingStatus
from app.core.logging import get_logger, log_database_operation


logger = get_logger(__name__)


class DatabaseManager:
    """MongoDB database manager for document processing"""
    
    def __init__(self, connection_string: str, db_name: str):
        self.connection_string = connection_string
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.connected = False
        
    async def connect(self) -> bool:
        """Connect to MongoDB"""
        
        try:
            logger.info(f"Attempting MongoDB connection...")
            logger.info(f"Connection string format: {self.connection_string[:50]}...{self.connection_string[-20:]}")
            self.client = AsyncIOMotorClient(self.connection_string)
            # Test connection
            await self.client.admin.command('ping')
            
            self.db = self.client[self.db_name]
            await self._create_indexes()
            
            self.connected = True
            logger.info("Successfully connected to MongoDB", 
                       extra={"database": self.db_name})
            return True
            
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}", 
                        extra={"connection_string": self.connection_string})
            return False
    
    async def _create_indexes(self):
        """Create database indexes for optimal performance"""
        
        indexes = [
            # Document indexes
            [("document_id", ASCENDING)],
            [("filename", ASCENDING)],
            [("status", ASCENDING)], 
            [("created_at", DESCENDING)],
            [("batch_id", ASCENDING)],
            
            # Patient info indexes
            [("patient_info.id_number", ASCENDING)],
            [("patient_info.name", ASCENDING)],
            [("patient_info.company_name", ASCENDING)],
            
            # Processing indexes
            [("document_types", ASCENDING)],
            [("processing_summary.mode", ASCENDING)],
            [("needs_validation", ASCENDING)],
            [("is_validated", ASCENDING)],
            
            # Compound indexes
            [("status", ASCENDING), ("created_at", DESCENDING)],
            [("patient_info.id_number", ASCENDING), ("created_at", DESCENDING)]
        ]
        
        for index in indexes:
            try:
                await self.db.historic_documents.create_index(index)
                log_database_operation(logger, "create_index", "historic_documents", 
                                     index=index)
            except Exception as e:
                # Index might already exist, which is fine
                logger.debug(f"Index creation skipped: {e}")
    
    async def save_processing_result(
        self, 
        document_id: str, 
        filename: str, 
        processing_result: Dict[str, Any]
    ) -> str:
        """Save processing result to database"""
        
        try:
            # Extract patient info from processing result
            patient_info = processing_result.get('patient_info', {})
            
            # Create document record
            document_record = {
                "_id": document_id,
                "document_id": document_id,
                "document_filename": filename,
                "status": processing_result.get('status', ProcessingStatus.COMPLETED),
                "document_types": list(processing_result.get('extracted_data', {}).keys()),
                "extracted_data": processing_result.get('extracted_data', {}),
                "processing_summary": processing_result.get('processing_summary', {}),
                "patient_info": patient_info,
                "confidence_score": processing_result.get('confidence_score'),
                "needs_validation": processing_result.get('needs_validation', False),
                "is_validated": False,
                "validation_notes": None,
                "created_at": datetime.utcnow(),
                "processed_at": datetime.utcnow() if processing_result.get('status') == ProcessingStatus.COMPLETED else None,
                "validated_at": None,
                "integration_status": "pending",
                "integration_attempts": 0,
                "file_url": processing_result.get('file_url'),
                "metadata": {
                    "file_size": processing_result.get('file_size'),
                    "content_type": processing_result.get('content_type'),
                    "processing_mode": processing_result.get('processing_summary', {}).get('mode')
                }
            }
            
            # Insert document
            await self.db.historic_documents.insert_one(document_record)
            
            log_database_operation(
                logger, "insert", "historic_documents",
                document_id=document_id,
                document_filename=filename,
                document_types=len(document_record["document_types"]),
                patient_id=patient_info.get('id_number')
            )
            
            return document_id
            
        except Exception as e:
            logger.error(f"Failed to save processing result: {e}", 
                        extra={"document_id": document_id, "document_filename": filename})
            raise
    
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        
        try:
            document = await self.db.historic_documents.find_one({"document_id": document_id})
            
            if document:
                log_database_operation(logger, "find_one", "historic_documents", 
                                     document_id=document_id, found=True)
            else:
                log_database_operation(logger, "find_one", "historic_documents", 
                                     document_id=document_id, found=False)
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to get document: {e}", 
                        extra={"document_id": document_id})
            raise
    
    async def update_document_validation(
        self, 
        document_id: str, 
        validated_data: Dict[str, Any],
        validation_notes: Optional[str] = None
    ) -> bool:
        """Update document with validated data"""
        
        try:
            update_data = {
                "$set": {
                    "extracted_data": validated_data,
                    "is_validated": True,
                    "validation_notes": validation_notes,
                    "validated_at": datetime.utcnow(),
                    "needs_validation": False,
                    "status": ProcessingStatus.VALIDATED
                }
            }
            
            result = await self.db.historic_documents.update_one(
                {"document_id": document_id},
                update_data
            )
            
            success = result.modified_count > 0
            
            log_database_operation(
                logger, "update_validation", "historic_documents",
                document_id=document_id,
                success=success,
                modified_count=result.modified_count
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update document validation: {e}", 
                        extra={"document_id": document_id})
            raise
    
    async def get_documents_by_patient(
        self, 
        patient_id: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get documents for a specific patient"""
        
        try:
            cursor = self.db.historic_documents.find(
                {"patient_info.id_number": patient_id}
            ).sort("created_at", DESCENDING).limit(limit)
            
            documents = await cursor.to_list(length=limit)
            
            log_database_operation(
                logger, "find_by_patient", "historic_documents",
                patient_id=patient_id,
                count=len(documents)
            )
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get patient documents: {e}", 
                        extra={"patient_id": patient_id})
            raise
    
    async def get_documents_by_company(
        self, 
        company: str, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get documents for a specific company"""
        
        try:
            cursor = self.db.historic_documents.find(
                {"patient_info.company_name": {"$regex": company, "$options": "i"}}
            ).sort("created_at", DESCENDING).limit(limit)
            
            documents = await cursor.to_list(length=limit)
            
            log_database_operation(
                logger, "find_by_company", "historic_documents",
                company=company,
                count=len(documents)
            )
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get company documents: {e}", 
                        extra={"company": company})
            raise
    
    async def get_documents_needing_validation(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get documents that need validation"""
        
        try:
            cursor = self.db.historic_documents.find(
                {"needs_validation": True, "is_validated": False}
            ).sort("created_at", ASCENDING).limit(limit)
            
            documents = await cursor.to_list(length=limit)
            
            log_database_operation(
                logger, "find_validation_needed", "historic_documents",
                count=len(documents)
            )
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get documents needing validation: {e}")
            raise
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        
        try:
            # Aggregation pipeline for comprehensive stats
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total_documents": {"$sum": 1},
                        "unique_patients": {"$addToSet": "$patient_info.id_number"},
                        "companies": {"$addToSet": "$patient_info.company_name"},
                        "document_types": {"$push": "$document_types"},
                        "statuses": {"$push": "$status"},
                        "validation_needed": {
                            "$sum": {"$cond": [{"$eq": ["$needs_validation", True]}, 1, 0]}
                        },
                        "validated": {
                            "$sum": {"$cond": [{"$eq": ["$is_validated", True]}, 1, 0]}
                        },
                        "avg_confidence": {"$avg": "$confidence_score"},
                        "processing_modes": {"$push": "$processing_summary.mode"}
                    }
                }
            ]
            
            result = await self.db.historic_documents.aggregate(pipeline).to_list(length=1)
            
            if result:
                stats = result[0]
                
                # Process document types
                all_types = set()
                for type_list in stats.get('document_types', []):
                    if isinstance(type_list, list):
                        all_types.update(type_list)
                
                # Process statuses
                status_counts = {}
                for status in stats.get('statuses', []):
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                # Process processing modes
                mode_counts = {}
                for mode in stats.get('processing_modes', []):
                    if mode:
                        mode_counts[mode] = mode_counts.get(mode, 0) + 1
                
                processed_stats = {
                    "total_documents": stats.get('total_documents', 0),
                    "unique_patients": len([p for p in stats.get('unique_patients', []) if p]),
                    "companies_processed": len([c for c in stats.get('companies', []) if c]),
                    "document_types_found": sorted(list(all_types)),
                    "validation_needed": stats.get('validation_needed', 0),
                    "validated": stats.get('validated', 0),
                    "average_confidence": round(stats.get('avg_confidence', 0) or 0, 2),
                    "status_breakdown": status_counts,
                    "processing_mode_breakdown": mode_counts,
                    "last_updated": datetime.utcnow()
                }
                
                log_database_operation(logger, "get_statistics", "historic_documents", 
                                     total_documents=processed_stats["total_documents"])
                
                return processed_stats
            
            return {
                "total_documents": 0,
                "last_updated": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            raise
    
    async def update_integration_status(
        self, 
        document_id: str, 
        status: str, 
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update integration status for a document"""
        
        try:
            update_data = {
                "$set": {
                    "integration_status": status,
                    "integration_result": result,
                    "integration_updated_at": datetime.utcnow()
                },
                "$inc": {
                    "integration_attempts": 1
                }
            }
            
            result = await self.db.historic_documents.update_one(
                {"document_id": document_id},
                update_data
            )
            
            success = result.modified_count > 0
            
            log_database_operation(
                logger, "update_integration", "historic_documents",
                document_id=document_id,
                status=status,
                success=success
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update integration status: {e}", 
                        extra={"document_id": document_id})
            raise
    
    async def cleanup_old_documents(self, days_old: int = 90) -> int:
        """Clean up old processed documents"""
        
        try:
            cutoff_date = datetime.utcnow().replace(day=datetime.utcnow().day - days_old)
            
            result = await self.db.historic_documents.delete_many({
                "created_at": {"$lt": cutoff_date},
                "status": {"$in": [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]},
                "is_validated": True
            })
            
            deleted_count = result.deleted_count
            
            log_database_operation(
                logger, "cleanup_old", "historic_documents",
                days_old=days_old,
                deleted_count=deleted_count
            )
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old documents: {e}")
            raise
    
    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("MongoDB connection closed")
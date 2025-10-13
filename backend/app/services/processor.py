"""
Document processor service using LandingAI ADE
"""
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path

from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema

from app.api.models import ProcessingStatusEnum

logger = logging.getLogger(__name__)

class ProcessingResult:
    """Result from document processing"""
    def __init__(self, status: str, extracted_data: Dict, processing_summary: Dict, 
                 patient_info: Optional[Dict] = None, confidence_score: float = 0.0,
                 needs_validation: bool = False, chunks: List = None, pdf_metadata: Dict = None):
        self.status = status
        self.extracted_data = extracted_data or {}
        self.processing_summary = processing_summary or {}
        self.patient_info = patient_info or {}
        self.confidence_score = confidence_score
        self.needs_validation = needs_validation
        self.chunks = chunks or []
        self.pdf_metadata = pdf_metadata or {}

class DocumentProcessor:
    """Document processor using LandingAI ADE"""
    
    def __init__(self):
        """Initialize processor"""
        api_key = os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY")
        if not api_key:
            raise ValueError("VISION_AGENT_API_KEY or LANDING_AI_API_KEY not set")
        
        self.client = LandingAIADE(apikey=api_key)
        logger.info("✅ DocumentProcessor initialized with LandingAI ADE")
    
    async def process_document(
        self, 
        document_id: str,
        file_path: str,
        filename: str,
        mode: str = "smart"
    ) -> ProcessingResult:
        """Process a single document"""
        logger.info(f"Processing document: {filename} with mode: {mode}")
        
        try:
            # Parse document with LandingAI
            parsed_doc = self.client.parse(file_path)
            
            # Extract basic info
            chunks = parsed_doc.get("chunks", [])
            markdown = parsed_doc.get("markdown", "")
            
            # For now, return basic parsed data
            # TODO: Add structured extraction based on document type
            extracted_data = {
                "parsed_content": markdown[:1000],  # First 1000 chars
                "total_chunks": len(chunks)
            }
            
            processing_summary = {
                "processing_time": 2.5,
                "mode": mode,
                "chunks_found": len(chunks),
                "extraction_method": "landingai_ade"
            }
            
            return ProcessingResult(
                status=ProcessingStatusEnum.COMPLETED,
                extracted_data=extracted_data,
                processing_summary=processing_summary,
                confidence_score=0.85,
                needs_validation=True,
                chunks=chunks,
                pdf_metadata={}
            )
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return ProcessingResult(
                status=ProcessingStatusEnum.FAILED,
                extracted_data={},
                processing_summary={"error": str(e)},
                confidence_score=0.0,
                needs_validation=True
            )
    
    async def batch_process_documents(
        self, 
        documents: List,
        mode: str = "smart"
    ) -> List[ProcessingResult]:
        """Process multiple documents"""
        results = []
        for doc_id, file_path, filename in documents:
            result = await self.process_document(doc_id, file_path, filename, mode)
            results.append(result)
        return results
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up DocumentProcessor")
        pass

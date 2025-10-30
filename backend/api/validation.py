"""
Validation API Endpoints
Manage extraction validation workflow
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import os
from supabase import create_client

router = APIRouter()

# Supabase client
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


class ValidationApproval(BaseModel):
    extraction_id: str
    corrections: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    validated_by: str


class ValidationRejection(BaseModel):
    extraction_id: str
    rejection_reason: str
    validated_by: str


@router.get("/validation/queue")
async def get_validation_queue(
    workspace_id: str,
    limit: int = 50,
    status: str = "pending"  # pending, all
):
    """
    Get queue of extractions awaiting validation
    
    Returns extractions that need human review before committing to tables
    """
    try:
        query = supabase.table('extraction_history')\
            .select('*')\
            .eq('workspace_id', workspace_id)
        
        if status == "pending":
            query = query.eq('validated', False)
        
        response = query\
            .order('extraction_datetime', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            "status": "success",
            "total": len(response.data),
            "extractions": response.data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch validation queue: {str(e)}")


@router.get("/validation/extraction/{extraction_id}")
async def get_extraction_for_validation(extraction_id: str):
    """
    Get detailed extraction data for validation review
    
    Returns:
        - Extracted data
        - Confidence scores
        - Document metadata
        - Template used
    """
    try:
        # Get extraction record
        response = supabase.table('extraction_history')\
            .select('*')\
            .eq('id', extraction_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Extraction not found")
        
        extraction = response.data[0]
        
        # Get document metadata if available
        document_id = extraction.get('document_id')
        document_data = None
        
        if document_id:
            doc_response = supabase.table('digitised_documents')\
                .select('*')\
                .eq('id', document_id)\
                .execute()
            
            if doc_response.data:
                document_data = doc_response.data[0]
        
        # Get template info if used
        template_data = None
        template_id = extraction.get('template_id')
        
        if template_id:
            template_response = supabase.table('extraction_templates')\
                .select('*')\
                .eq('id', template_id)\
                .execute()
            
            if template_response.data:
                template_data = template_response.data[0]
        
        return {
            "status": "success",
            "extraction": extraction,
            "document": document_data,
            "template": template_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch extraction: {str(e)}")


@router.post("/validation/approve")
async def approve_extraction(approval: ValidationApproval):
    """
    Approve an extraction (with optional corrections)
    
    If corrections provided, updates the extracted data before marking as validated
    """
    try:
        # Get extraction record
        response = supabase.table('extraction_history')\
            .select('*')\
            .eq('id', approval.extraction_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Extraction not found")
        
        extraction = response.data[0]
        
        # Apply corrections if provided
        if approval.corrections:
            # Merge corrections into structured_extraction
            structured_extraction = extraction.get('structured_extraction', {})
            structured_extraction.update(approval.corrections)
            
            # TODO: Re-run auto-population with corrected data
            # This would update the target tables with corrected values
        
        # Mark as validated
        update_data = {
            'validated': True,
            'validated_by': approval.validated_by,
            'validated_at': datetime.now(timezone.utc).isoformat(),
            'validation_changes': approval.corrections or {},
            'validation_notes': approval.notes
        }
        
        if approval.corrections:
            update_data['structured_extraction'] = structured_extraction
        
        supabase.table('extraction_history')\
            .update(update_data)\
            .eq('id', approval.extraction_id)\
            .execute()
        
        return {
            "status": "success",
            "message": "Extraction approved and validated",
            "extraction_id": approval.extraction_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve extraction: {str(e)}")


@router.post("/validation/reject")
async def reject_extraction(rejection: ValidationRejection):
    """
    Reject an extraction
    
    Marks extraction as rejected and prevents data from being committed to tables
    """
    try:
        # Get extraction record
        response = supabase.table('extraction_history')\
            .select('*')\
            .eq('id', rejection.extraction_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Extraction not found")
        
        # Mark as validated but with rejection
        update_data = {
            'validated': True,  # Still mark as reviewed
            'validated_by': rejection.validated_by,
            'validated_at': datetime.now(timezone.utc).isoformat(),
            'extraction_status': 'rejected',  # Change status to rejected
            'validation_notes': rejection.rejection_reason
        }
        
        supabase.table('extraction_history')\
            .update(update_data)\
            .eq('id', rejection.extraction_id)\
            .execute()
        
        # TODO: If records were already created in target tables, mark them as rejected
        # or delete them based on business rules
        
        return {
            "status": "success",
            "message": "Extraction rejected",
            "extraction_id": rejection.extraction_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject extraction: {str(e)}")


@router.get("/validation/stats")
async def get_validation_stats(workspace_id: str):
    """
    Get validation statistics for a workspace
    
    Returns:
        - Total extractions
        - Pending validations
        - Approved count
        - Rejected count
        - Average confidence scores
    """
    try:
        # Get all extractions
        all_response = supabase.table('extraction_history')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .execute()
        
        extractions = all_response.data
        
        total = len(extractions)
        pending = len([e for e in extractions if not e.get('validated')])
        approved = len([e for e in extractions if e.get('validated') and e.get('extraction_status') != 'rejected'])
        rejected = len([e for e in extractions if e.get('extraction_status') == 'rejected'])
        
        # Calculate average confidence scores
        confidence_scores = [e.get('confidence_scores', {}) for e in extractions if e.get('confidence_scores')]
        avg_confidence = {}
        
        if confidence_scores:
            # Aggregate confidence scores
            for scores in confidence_scores:
                for section, score in scores.items():
                    if section not in avg_confidence:
                        avg_confidence[section] = []
                    avg_confidence[section].append(score)
            
            # Calculate averages
            avg_confidence = {
                section: sum(scores) / len(scores)
                for section, scores in avg_confidence.items()
            }
        
        return {
            "status": "success",
            "stats": {
                "total_extractions": total,
                "pending_validation": pending,
                "approved": approved,
                "rejected": rejected,
                "approval_rate": approved / total if total > 0 else 0,
                "average_confidence_scores": avg_confidence
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.get("/validation/history")
async def get_validation_history(
    workspace_id: str,
    limit: int = 50,
    validated_only: bool = True
):
    """
    Get validation history (completed validations)
    """
    try:
        query = supabase.table('extraction_history')\
            .select('*')\
            .eq('workspace_id', workspace_id)
        
        if validated_only:
            query = query.eq('validated', True)
        
        response = query\
            .order('validated_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            "status": "success",
            "total": len(response.data),
            "history": response.data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch validation history: {str(e)}")

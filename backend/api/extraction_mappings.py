"""
Extraction Mappings API
Manage extraction templates and field mappings for client-agnostic document processing
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
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

# =============================================
# PYDANTIC MODELS
# =============================================

class ExtractionTemplate(BaseModel):
    id: Optional[str] = None
    tenant_id: str
    workspace_id: str
    template_name: str
    template_description: Optional[str] = None
    document_type: str  # 'medical_record', 'lab_report', 'immunization_card', etc.
    is_active: bool = True
    is_default: bool = False
    extraction_schema: Optional[Dict[str, Any]] = None
    auto_populate: bool = True
    require_validation: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ExtractionFieldMapping(BaseModel):
    id: Optional[str] = None
    template_id: str
    workspace_id: str
    source_section: str  # e.g., 'vaccination_records'
    source_field: str  # e.g., 'vaccine_type'
    source_field_path: Optional[str] = None  # JSON path for nested fields
    target_table: str  # 'immunizations', 'lab_results', etc.
    target_field: str  # Column name in target table
    field_type: str = 'text'  # 'text', 'number', 'date', 'datetime', 'boolean', 'json'
    is_required: bool = False
    default_value: Optional[str] = None
    transformation_type: str = 'direct'  # 'direct', 'lookup', 'calculation', 'concatenation', 'split', 'ai_match'
    transformation_config: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    processing_order: int = 100
    skip_if_exists: bool = True
    is_active: bool = True
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ExtractionHistory(BaseModel):
    id: Optional[str] = None
    document_id: str
    template_id: Optional[str] = None
    workspace_id: str
    patient_id: Optional[str] = None
    extraction_datetime: Optional[str] = None
    extraction_status: str = 'success'  # 'success', 'partial', 'failed'
    raw_extraction: Optional[Dict[str, Any]] = None
    structured_extraction: Optional[Dict[str, Any]] = None
    tables_populated: Optional[Dict[str, Any]] = None
    population_errors: Optional[Dict[str, Any]] = None
    confidence_scores: Optional[Dict[str, Any]] = None
    validation_required_sections: Optional[List[str]] = None
    processing_time_ms: Optional[int] = None
    fields_extracted: Optional[int] = None
    fields_mapped: Optional[int] = None
    records_created: Optional[int] = None
    validated: bool = False
    created_at: Optional[str] = None

# =============================================
# EXTRACTION TEMPLATES ENDPOINTS
# =============================================

@router.get("/extraction/templates", response_model=List[ExtractionTemplate])
async def get_templates(workspace_id: str, document_type: Optional[str] = None):
    """Get all extraction templates for a workspace"""
    try:
        query = supabase.table('extraction_templates').select('*').eq('workspace_id', workspace_id)
        
        if document_type:
            query = query.eq('document_type', document_type)
        
        response = query.order('template_name').execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch templates: {str(e)}")

@router.get("/extraction/templates/{template_id}", response_model=ExtractionTemplate)
async def get_template(template_id: str):
    """Get a specific extraction template"""
    try:
        response = supabase.table('extraction_templates').select('*').eq('id', template_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Template not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch template: {str(e)}")

@router.post("/extraction/templates", response_model=ExtractionTemplate)
async def create_template(template: ExtractionTemplate):
    """Create a new extraction template"""
    try:
        template_data = template.dict(exclude={'id', 'created_at', 'updated_at'})
        template_data['id'] = str(uuid.uuid4())
        template_data['created_at'] = datetime.now(timezone.utc).isoformat()
        template_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        response = supabase.table('extraction_templates').insert(template_data).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")

@router.patch("/extraction/templates/{template_id}", response_model=ExtractionTemplate)
async def update_template(template_id: str, updates: Dict[str, Any]):
    """Update an extraction template"""
    try:
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        response = supabase.table('extraction_templates').update(updates).eq('id', template_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Template not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")

@router.delete("/extraction/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete an extraction template"""
    try:
        response = supabase.table('extraction_templates').delete().eq('id', template_id).execute()
        return {"status": "success", "message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")

# =============================================
# FIELD MAPPINGS ENDPOINTS
# =============================================

@router.get("/extraction/templates/{template_id}/mappings", response_model=List[ExtractionFieldMapping])
async def get_template_mappings(template_id: str):
    """Get all field mappings for a template"""
    try:
        response = supabase.table('extraction_field_mappings')\
            .select('*')\
            .eq('template_id', template_id)\
            .order('processing_order')\
            .execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch mappings: {str(e)}")

@router.get("/extraction/mappings/{mapping_id}", response_model=ExtractionFieldMapping)
async def get_mapping(mapping_id: str):
    """Get a specific field mapping"""
    try:
        response = supabase.table('extraction_field_mappings').select('*').eq('id', mapping_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Mapping not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch mapping: {str(e)}")

@router.post("/extraction/mappings", response_model=ExtractionFieldMapping)
async def create_mapping(mapping: ExtractionFieldMapping):
    """Create a new field mapping"""
    try:
        mapping_data = mapping.dict(exclude={'id', 'created_at', 'updated_at'})
        mapping_data['id'] = str(uuid.uuid4())
        mapping_data['created_at'] = datetime.now(timezone.utc).isoformat()
        mapping_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        response = supabase.table('extraction_field_mappings').insert(mapping_data).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create mapping: {str(e)}")

@router.patch("/extraction/mappings/{mapping_id}", response_model=ExtractionFieldMapping)
async def update_mapping(mapping_id: str, updates: Dict[str, Any]):
    """Update a field mapping"""
    try:
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        response = supabase.table('extraction_field_mappings').update(updates).eq('id', mapping_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Mapping not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mapping: {str(e)}")

@router.delete("/extraction/mappings/{mapping_id}")
async def delete_mapping(mapping_id: str):
    """Delete a field mapping"""
    try:
        response = supabase.table('extraction_field_mappings').delete().eq('id', mapping_id).execute()
        return {"status": "success", "message": "Mapping deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete mapping: {str(e)}")

# =============================================
# BATCH OPERATIONS
# =============================================

@router.post("/extraction/templates/{template_id}/mappings/batch")
async def create_mappings_batch(template_id: str, mappings: List[ExtractionFieldMapping]):
    """Create multiple field mappings at once"""
    try:
        mappings_data = []
        for mapping in mappings:
            mapping_data = mapping.dict(exclude={'id', 'created_at', 'updated_at'})
            mapping_data['id'] = str(uuid.uuid4())
            mapping_data['template_id'] = template_id
            mapping_data['created_at'] = datetime.now(timezone.utc).isoformat()
            mapping_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            mappings_data.append(mapping_data)
        
        response = supabase.table('extraction_field_mappings').insert(mappings_data).execute()
        return {
            "status": "success",
            "message": f"Created {len(response.data)} mappings",
            "mappings": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create mappings: {str(e)}")

# =============================================
# EXTRACTION HISTORY ENDPOINTS
# =============================================

@router.get("/extraction/history", response_model=List[ExtractionHistory])
async def get_extraction_history(workspace_id: str, limit: int = 50):
    """Get extraction history for a workspace"""
    try:
        response = supabase.table('extraction_history')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .order('extraction_datetime', desc=True)\
            .limit(limit)\
            .execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")

@router.get("/extraction/history/{history_id}", response_model=ExtractionHistory)
async def get_extraction_record(history_id: str):
    """Get a specific extraction history record"""
    try:
        response = supabase.table('extraction_history').select('*').eq('id', history_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Extraction record not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch extraction record: {str(e)}")

@router.post("/extraction/history", response_model=ExtractionHistory)
async def create_extraction_record(history: ExtractionHistory):
    """Create an extraction history record"""
    try:
        history_data = history.dict(exclude={'id', 'created_at'})
        history_data['id'] = str(uuid.uuid4())
        history_data['created_at'] = datetime.now(timezone.utc).isoformat()
        
        if not history_data.get('extraction_datetime'):
            history_data['extraction_datetime'] = datetime.now(timezone.utc).isoformat()
        
        response = supabase.table('extraction_history').insert(history_data).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create extraction record: {str(e)}")

# =============================================
# TEMPLATE STATISTICS
# =============================================

@router.get("/extraction/templates/{template_id}/stats")
async def get_template_stats(template_id: str):
    """Get usage statistics for a template"""
    try:
        # Get extraction history for this template
        history_response = supabase.table('extraction_history')\
            .select('*')\
            .eq('template_id', template_id)\
            .execute()
        
        history = history_response.data
        
        if not history:
            return {
                "template_id": template_id,
                "total_extractions": 0,
                "successful": 0,
                "partial": 0,
                "failed": 0,
                "avg_processing_time_ms": 0,
                "avg_fields_extracted": 0,
                "avg_records_created": 0
            }
        
        total = len(history)
        successful = len([h for h in history if h.get('extraction_status') == 'success'])
        partial = len([h for h in history if h.get('extraction_status') == 'partial'])
        failed = len([h for h in history if h.get('extraction_status') == 'failed'])
        
        processing_times = [h.get('processing_time_ms', 0) for h in history if h.get('processing_time_ms')]
        fields_extracted = [h.get('fields_extracted', 0) for h in history if h.get('fields_extracted')]
        records_created = [h.get('records_created', 0) for h in history if h.get('records_created')]
        
        return {
            "template_id": template_id,
            "total_extractions": total,
            "successful": successful,
            "partial": partial,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "avg_processing_time_ms": sum(processing_times) / len(processing_times) if processing_times else 0,
            "avg_fields_extracted": sum(fields_extracted) / len(fields_extracted) if fields_extracted else 0,
            "avg_records_created": sum(records_created) / len(records_created) if records_created else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch template stats: {str(e)}")

# =============================================
# WORKSPACE CONFIGURATION
# =============================================

@router.get("/extraction/workspace/{workspace_id}/config")
async def get_workspace_config(workspace_id: str):
    """Get complete extraction configuration for a workspace"""
    try:
        # Get all templates
        templates_response = supabase.table('extraction_templates')\
            .select('*')\
            .eq('workspace_id', workspace_id)\
            .eq('is_active', True)\
            .execute()
        
        templates = templates_response.data
        
        # Get mappings for each template
        config = []
        for template in templates:
            mappings_response = supabase.table('extraction_field_mappings')\
                .select('*')\
                .eq('template_id', template['id'])\
                .eq('is_active', True)\
                .order('processing_order')\
                .execute()
            
            config.append({
                "template": template,
                "mappings": mappings_response.data
            })
        
        return {
            "workspace_id": workspace_id,
            "total_templates": len(templates),
            "configurations": config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch workspace config: {str(e)}")

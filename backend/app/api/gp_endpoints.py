# app/api/gp_endpoints.py
"""
GP Chronic Patient Digitization Endpoints (Supabase)
Migrated from MongoDB to Supabase PostgreSQL
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, Query, Body
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import os
import tempfile

from app.core.logging import get_logger
from app.api.models import ErrorResponse

logger = get_logger(__name__)

# Security
security = HTTPBearer(auto_error=False)

# Create router
gp_router = APIRouter(prefix="/api/v1/gp", tags=["GP Chronic Patients"])


def _get_supabase():
    """Get the Supabase client from server module"""
    try:
        import server
        return getattr(server, 'supabase', None)
    except ImportError:
        return None


# =============================================================================
# GP HEALTH CHECK
# =============================================================================

@gp_router.get("/health")
async def gp_health_check():
    """GP module health check endpoint"""
    try:
        processor_status = "available"
        try:
            from app.services.gp_processor import GPDocumentProcessor
            test_processor = GPDocumentProcessor()
            processor_status = "initialized"
        except Exception as e:
            processor_status = f"error: {str(e)}"

        db_status = "not_checked"
        sb = _get_supabase()
        if sb:
            try:
                sb.table('gp_parsed_documents').select('id', count='exact').limit(0).execute()
                db_status = "connected"
            except Exception as e:
                db_status = f"error: {str(e)}"

        return {
            "status": "healthy",
            "module": "GP Chronic Patient Digitization",
            "processor_status": processor_status,
            "database_status": db_status,
            "database_type": "supabase",
            "features": {
                "document_parsing": "available",
                "multi_schema_extraction": "available",
                "parse_once_extract_many": "available",
                "validation_workflow": "available",
                "confidence_scoring": "available"
            },
            "supported_schemas": [
                "demographics",
                "chronic_summary",
                "vitals",
                "clinical_notes"
            ],
            "model": "dpt-2-latest",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        return {
            "status": "error",
            "module": "GP Chronic Patient Digitization",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# =============================================================================
# ENDPOINT 1: UPLOAD & PROCESS GP PATIENT FILE
# =============================================================================

@gp_router.post("/upload-patient-file")
async def upload_gp_patient_file(
    file: UploadFile = File(..., description="Patient file (PDF or Image)"),
    patient_id: Optional[str] = Form(None, description="Existing patient ID (optional)"),
    patient_name: Optional[str] = Form(None, description="Patient name for new records"),
    process_mode: str = Form("full", description="full, parse_only, or extract_only"),
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Upload and process a GP chronic patient file."""

    request_id = str(uuid.uuid4())
    logger.info(f"GP Upload Request {request_id}: {file.filename}")

    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    file_content = await file.read()
    if len(file_content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB")

    temp_path = None
    permanent_path = None
    try:
        storage_dir = os.path.join(os.getcwd(), "storage", "gp_documents")
        os.makedirs(storage_dir, exist_ok=True)

        actual_patient_id = patient_id or f"gp_patient_{request_id[:8]}"
        permanent_path = os.path.join(storage_dir, f"{actual_patient_id}_{file.filename}")

        temp_path = os.path.join(tempfile.gettempdir(), f"gp_{request_id}_{file.filename}")

        with open(permanent_path, "wb") as f:
            f.write(file_content)
        with open(temp_path, "wb") as f:
            f.write(file_content)

        from app.services.gp_processor import GPDocumentProcessor

        sb = _get_supabase()
        gp_processor = GPDocumentProcessor(supabase_client=sb)

        result = await gp_processor.process_and_save_patient_file(
            file_path=temp_path,
            filename=file.filename,
            organization_id=patient_id or "default_org",
            file_data=file_content
        )

        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Processing failed'))

        result['patient_id'] = actual_patient_id
        result['file_path'] = permanent_path

        logger.info(f"Processing complete: {request_id}")

        return {
            "success": True,
            "message": "Patient file processed successfully",
            "request_id": request_id,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass


# =============================================================================
# ENDPOINT 2: GET PATIENT CHRONIC SUMMARY
# =============================================================================

@gp_router.get("/patient/{patient_id}/chronic-summary")
async def get_patient_chronic_summary(
    patient_id: str,
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get validated chronic patient summary for quick doctor access."""
    try:
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=503, detail="Database not available")

        result = sb.table('patients').select('*').eq('id', patient_id).execute()

        if not result.data:
            # Try by id_number as fallback
            result = sb.table('patients').select('*').eq('id_number', patient_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

        patient = result.data[0]

        return {
            "success": True,
            "patient_id": patient.get('id'),
            "patient_name": f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip(),
            "demographics": {
                "first_names": patient.get('first_name'),
                "surname": patient.get('last_name'),
                "id_number": patient.get('id_number'),
                "date_of_birth": patient.get('dob'),
                "contact_number": patient.get('contact_number'),
                "email": patient.get('email'),
                "address": patient.get('address'),
                "medical_aid_name": patient.get('medical_aid')
            },
            "chronic_conditions": patient.get('chronic_conditions', []),
            "current_medications": patient.get('current_medications', []),
            "allergies": patient.get('allergies', []),
            "latest_vitals": patient.get('latest_vitals', {}),
            "last_updated": patient.get('updated_at'),
            "validation_status": patient.get('validation_status', 'pending')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 3: VALIDATE & APPROVE EXTRACTION
# =============================================================================

@gp_router.post("/validate-extraction")
async def validate_gp_extraction(
    patient_id: str = Body(...),
    validated_data: dict = Body(...),
    validation_statuses: dict = Body(...),
    validator_notes: str = Body(default="")
):
    """Save human-validated extraction data"""

    logger.info(f"Saving validated data for patient: {patient_id}")

    try:
        sb = _get_supabase()
        if not sb:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Validation recorded (database unavailable)",
                    "patient_id": patient_id
                }
            )

        # Update the validation session
        session_result = sb.table('gp_validation_sessions')\
            .select('id')\
            .or_(f"patient_id.eq.{patient_id},document_id.eq.{patient_id}")\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if session_result.data:
            session_id = session_result.data[0]['id']
            sb.table('gp_validation_sessions').update({
                "validated_data": validated_data,
                "validation_statuses": validation_statuses,
                "validator_notes": validator_notes,
                "status": "approved",
                "validated_at": datetime.now(timezone.utc).isoformat()
            }).eq('id', session_id).execute()

        # Also update patient record if it exists
        patient_result = sb.table('patients').select('id').eq('id', patient_id).execute()
        if patient_result.data:
            sb.table('patients').update({
                "is_validated": True,
                "validation_status": "completed",
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq('id', patient_id).execute()

            logger.info(f"Validated data saved for patient: {patient_id}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Validation saved successfully",
                    "patient_id": patient_id
                }
            )
        else:
            logger.warning(f"No patient record found for: {patient_id}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Validation session updated (no patient record)",
                    "patient_id": patient_id
                }
            )

    except Exception as e:
        logger.error(f"Failed to save validation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 4: LIST ALL CHRONIC PATIENTS
# =============================================================================

@gp_router.get("/patients")
async def list_chronic_patients(
    search: Optional[str] = Query(None, description="Search by name or ID"),
    validation_status: Optional[str] = Query(None, description="Filter by validation status"),
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """List all chronic patients with search and filtering."""
    try:
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=503, detail="Database not available")

        query = sb.table('patients').select('*', count='exact')

        if search:
            query = query.or_(
                f"first_name.ilike.%{search}%,"
                f"last_name.ilike.%{search}%,"
                f"id_number.ilike.%{search}%"
            )

        if validation_status:
            query = query.eq('validation_status', validation_status)

        result = query.range(skip, skip + limit - 1)\
            .order('created_at', desc=True)\
            .execute()

        total = result.count if result.count is not None else len(result.data)

        results = []
        for patient in result.data:
            chronic_conditions = patient.get('chronic_conditions', []) or []
            current_medications = patient.get('current_medications', []) or []

            results.append({
                "patient_id": patient.get('id'),
                "name": f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip(),
                "id_number": patient.get('id_number'),
                "date_of_birth": patient.get('dob'),
                "chronic_conditions_count": len(chronic_conditions) if isinstance(chronic_conditions, list) else 0,
                "medications_count": len(current_medications) if isinstance(current_medications, list) else 0,
                "validation_status": patient.get('validation_status', 'pending'),
                "last_updated": patient.get('updated_at')
            })

        return {
            "success": True,
            "total": total,
            "count": len(results),
            "skip": skip,
            "limit": limit,
            "patients": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing patients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 5: GET PARSED DOCUMENT WITH CHUNKS
# =============================================================================

@gp_router.get("/parsed-document/{document_id}")
async def get_parsed_document(
    document_id: str,
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get parsed document with semantic chunks for validation UI."""
    try:
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=503, detail="Database not available")

        # Try by document_id first, then by id
        parsed_doc = sb.table('gp_parsed_documents')\
            .select('*')\
            .eq('document_id', document_id)\
            .execute()

        if not parsed_doc.data:
            parsed_doc = sb.table('gp_parsed_documents')\
                .select('*')\
                .eq('id', document_id)\
                .execute()

        if not parsed_doc.data:
            raise HTTPException(status_code=404, detail=f"Parsed document not found: {document_id}")

        doc = parsed_doc.data[0]

        return {
            "success": True,
            "document_id": document_id,
            "patient_id": doc.get('patient_id'),
            "filename": doc.get('filename'),
            "parsed_data": doc.get('parsed_data', {}),
            "parsed_at": doc.get('parsed_at')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving parsed document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 6: SEARCH MEDICATIONS
# =============================================================================

@gp_router.get("/medications/search")
async def search_medications(
    query: str = Query(..., min_length=2, description="Medication name to search"),
    limit: int = Query(20, ge=1, le=100),
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Search for medications across all chronic patients."""
    try:
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=503, detail="Database not available")

        # Search patients with medications containing the query
        # Using JSONB containment via textSearch or ilike on cast
        result = sb.table('patients')\
            .select('id, first_name, last_name, current_medications')\
            .not_.is_('current_medications', 'null')\
            .limit(limit)\
            .execute()

        # Filter in application layer for JSONB array search
        matched = []
        for patient in (result.data or []):
            medications = patient.get('current_medications', []) or []
            matching_meds = [
                m for m in medications
                if isinstance(m, dict) and query.lower() in (m.get('medication_name', '') or '').lower()
            ]
            if matching_meds:
                matched.append({
                    "patient_id": patient['id'],
                    "patient_name": f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip(),
                    "medications": matching_meds
                })

        return {
            "success": True,
            "query": query,
            "count": len(matched),
            "results": matched
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching medications: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 7: STATISTICS
# =============================================================================

@gp_router.get("/statistics")
async def get_gp_statistics(
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get overall GP chronic patient statistics."""
    try:
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=503, detail="Database not available")

        # Total patients
        total_result = sb.table('patients').select('id', count='exact').execute()
        total_patients = total_result.count or 0

        # Validation breakdown
        approved_result = sb.table('patients').select('id', count='exact').eq('validation_status', 'approved').execute()
        pending_result = sb.table('patients').select('id', count='exact').eq('validation_status', 'pending').execute()
        review_result = sb.table('patients').select('id', count='exact').eq('validation_status', 'needs_review').execute()

        # Get common conditions from patient_conditions table
        common_conditions = []
        try:
            conditions_result = sb.table('patient_conditions')\
                .select('condition_name')\
                .limit(500)\
                .execute()

            if conditions_result.data:
                from collections import Counter
                condition_counts = Counter(
                    c.get('condition_name') for c in conditions_result.data if c.get('condition_name')
                )
                common_conditions = [
                    {"condition": name, "patient_count": count}
                    for name, count in condition_counts.most_common(10)
                ]
        except Exception:
            pass

        return {
            "success": True,
            "total_patients": total_patients,
            "validation_status": {
                "approved": approved_result.count or 0,
                "pending": pending_result.count or 0,
                "needs_review": review_result.count or 0
            },
            "common_conditions": common_conditions,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 8: GET VALIDATION SESSION DATA
# =============================================================================

@gp_router.get("/validation-session/{document_id}")
async def get_validation_session_data(
    document_id: str,
    request: Optional[str] = Query(None, description="Original request ID"),
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Fetch complete validation session payload for the frontend validation UI."""
    try:
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=503, detail="Database not available")

        # Get parsed document
        parsed_result = sb.table('gp_parsed_documents')\
            .select('*')\
            .eq('document_id', document_id)\
            .execute()

        if not parsed_result.data:
            raise HTTPException(status_code=404, detail=f"Parsed document not found: {document_id}")

        parsed_doc = parsed_result.data[0]

        # Get validation session
        session_result = sb.table('gp_validation_sessions')\
            .select('*')\
            .eq('document_id', document_id)\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if not session_result.data:
            raise HTTPException(status_code=404, detail=f"Validation session not found for document: {document_id}")

        validation_session = session_result.data[0]

        response_data = {
            "success": True,
            "data": {
                "document_id": document_id,
                "patient_id": validation_session.get("patient_id") or parsed_doc.get("patient_id"),
                "request_id": request,
                "chunks": parsed_doc.get("parsed_data", {}).get("chunks", []),
                "pages_processed": parsed_doc.get("parsed_data", {}).get("num_pages", 1),
                "extractions": validation_session.get("extractions", {}),
                "confidence_scores": validation_session.get("confidence_scores", {}),
                "model_used": parsed_doc.get("parser", "dpt-2-latest"),
                "processing_time": validation_session.get("processing_time", 0),
                "parsed_at": parsed_doc.get("parsed_at"),
                "validation_status": validation_session.get("status", "pending_validation"),
                "filename": parsed_doc.get("filename"),
                "organization_id": parsed_doc.get("organization_id")
            }
        }

        logger.info(
            "Served validation data for document %s (chunks: %s)",
            document_id,
            len(response_data["data"]["chunks"])
        )

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving validation session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 9: FILE SERVING
# =============================================================================

@gp_router.get("/document/{patient_id}/file")
async def get_patient_document_file(
    patient_id: str,
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Serve the original document file for a patient."""
    try:
        storage_dir = os.path.join(os.getcwd(), "storage", "gp_documents")
        file_path = None
        filename = 'document.pdf'

        if os.path.exists(storage_dir):
            for f in os.listdir(storage_dir):
                if patient_id in f:
                    file_path = os.path.join(storage_dir, f)
                    filename = f.split('_', 1)[1] if '_' in f else f
                    break

        if not file_path or not os.path.exists(file_path):
            # Try Supabase digitised_documents as fallback
            sb = _get_supabase()
            if sb:
                doc_result = sb.table('digitised_documents')\
                    .select('file_path, filename')\
                    .eq('patient_id', patient_id)\
                    .limit(1)\
                    .execute()
                if doc_result.data:
                    file_path = doc_result.data[0].get('file_path')
                    filename = doc_result.data[0].get('filename', 'document.pdf')

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Original document file not found")

        return FileResponse(path=file_path, filename=filename, media_type='application/pdf')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving document file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 10: SAVE VALIDATED PATIENT
# =============================================================================

@gp_router.post("/save-validated-patient")
async def save_validated_patient(
    organization_id: str = Body(...),
    document_id: str = Body(...),
    validated_data: dict = Body(...)
):
    """Save validated patient data after human review"""

    logger.info(f"Saving validated patient data for document: {document_id}")

    try:
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=503, detail="Database not available")

        from app.services.gp_processor import GPDocumentProcessor
        processor = GPDocumentProcessor(supabase_client=sb)

        patient_id = await processor.save_validated_patient(
            organization_id=organization_id,
            document_id=document_id,
            validated_data=validated_data
        )

        return {
            "success": True,
            "message": "Patient data saved successfully",
            "patient_id": patient_id
        }

    except Exception as e:
        logger.error(f"Save failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

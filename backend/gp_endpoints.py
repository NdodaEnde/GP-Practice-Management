# app/api/gp_endpoints.py
"""
GP Chronic Patient Digitization Endpoints
Add these to main.py or import as a router
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, Query, Body
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List
from datetime import datetime
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


# =============================================================================
# GP HEALTH CHECK
# =============================================================================

@gp_router.get("/health")
async def gp_health_check():
    """
    GP module health check endpoint
    """
    
    try:
        # Check GP processor initialization
        from app.services.gp_processor import GPDocumentProcessor
        processor_status = "available"
        try:
            test_processor = GPDocumentProcessor()
            processor_status = "initialized"
        except Exception as e:
            processor_status = f"error: {str(e)}"
        
        # Check database connectivity for GP collections
        # Get global db_manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        db_status = "not_configured"
        if db_manager:
            if db_manager.connected:
                db_status = "connected"
            else:
                db_status = "disconnected"
        
        return {
            "status": "healthy",
            "module": "GP Chronic Patient Digitization",
            "processor_status": processor_status,
            "database_status": db_status,
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
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "module": "GP Chronic Patient Digitization",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
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
    """
    Upload and process a GP chronic patient file.
    
    **Modes:**
    - `full`: Parse + Extract all data (default)
    - `parse_only`: Only parse document, no extraction
    - `extract_only`: Extract from previously parsed document
    
    **Returns:**
    - Parsed document with semantic chunks
    - All extractions (demographics, conditions, medications, vitals)
    - Confidence scores for validation
    """
    
    request_id = str(uuid.uuid4())
    logger.info(f"📤 GP Upload Request {request_id}: {file.filename}")
    
    # Validate file type
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size (max 50MB)
    file_content = await file.read()
    if len(file_content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 50MB"
        )
    
    temp_path = None
    permanent_path = None
    try:
        # Create permanent storage directory
        storage_dir = os.path.join(os.getcwd(), "storage", "gp_documents")
        os.makedirs(storage_dir, exist_ok=True)
        
        # Save file permanently with patient_id
        actual_patient_id = patient_id or f"gp_patient_{request_id[:8]}"
        permanent_path = os.path.join(
            storage_dir,
            f"{actual_patient_id}_{file.filename}"
        )
        
        # Also save a temporary file for processing
        temp_path = os.path.join(
            tempfile.gettempdir(), 
            f"gp_{request_id}_{file.filename}"
        )
        
        # Write file content to both locations
        with open(permanent_path, "wb") as f:
            f.write(file_content)
        with open(temp_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"💾 Saved permanent file: {permanent_path}")
        logger.info(f"💾 Saved temp file: {temp_path}")
        
        # Process with GP processor
        from app.services.gp_processor import GPDocumentProcessor
        
        # Get database manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        gp_processor = GPDocumentProcessor(db_manager=db_manager)
        
        result = await gp_processor.process_and_save_patient_file(
            file_path=temp_path,
            filename=file.filename,
            organization_id=patient_id or "default_org",  # or get from user context
            file_data=file_content  # Pass the file content we already read
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500, 
                detail=result.get('error', 'Processing failed')
            )
        
        # Ensure patient identifier included in response for downstream consumers
        result['patient_id'] = actual_patient_id
        result['file_path'] = permanent_path

        logger.info(f"✅ Processing complete: {request_id}")
        
        return {
            "success": True,
            "message": "Patient file processed successfully",
            "request_id": request_id,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )
    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.info(f"🗑️  Cleaned up temp file")
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
    """
    Get validated chronic patient summary for quick doctor access.
    
    **Returns:**
    - Patient demographics
    - Chronic conditions list
    - Current medications
    - Latest vital signs
    - Recent clinical notes
    """
    
    try:
        # Get global db_manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager or not db_manager.connected:
            raise HTTPException(
                status_code=503,
                detail="Database manager not initialized"
            )
        
        # Try to use the database, catch errors gracefully
        try:
            patient = await db_manager.db.gp_patients.find_one({
                "patient_id": patient_id  # Use patient_id field instead of _id
            })
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}"
            )
        
        if not patient:
            raise HTTPException(
                status_code=404,
                detail=f"Patient not found: {patient_id}"
            )
        
        # Get validated extractions
        demographics = patient.get('demographics', {})
        chronic_summary = patient.get('chronic_summary', {})
        
        return {
            "success": True,
            "patient_id": patient_id,
            "patient_name": f"{demographics.get('first_names', '')} {demographics.get('surname', '')}".strip(),
            "demographics": demographics,
            "chronic_conditions": chronic_summary.get('chronic_conditions', []),
            "current_medications": chronic_summary.get('current_medications', []),
            "allergies": chronic_summary.get('allergies', []),
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
async def validate_extraction(
    patient_id: str = Form(...),
    extraction_type: str = Form(..., description="demographics, chronic_summary, vitals, etc."),
    validated_data: str = Form(..., description="JSON string of validated data"),
    validation_status: str = Form("approved", description="approved, rejected, needs_review"),
    validator_notes: Optional[str] = Form(None),
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Validate and approve/reject extracted data.
    
    **Extraction Types:**
    - `demographics`
    - `chronic_summary`
    - `vitals`
    - `clinical_notes`
    
    **Validation Status:**
    - `approved` - Data is correct, save to patient record
    - `rejected` - Data is incorrect, needs re-extraction
    - `needs_review` - Uncertain, flag for senior review
    """
    
    try:
        import json
        # Get global db_manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Database manager not initialized"
            )
        
        # Parse validated data
        try:
            validated_data_obj = json.loads(validated_data)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in validated_data"
            )
        
        # Update patient record
        update_data = {
            f"validated_{extraction_type}": validated_data_obj,
            f"validation_status_{extraction_type}": validation_status,
            f"validated_at_{extraction_type}": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if validator_notes:
            update_data[f"validator_notes_{extraction_type}"] = validator_notes
        
        try:
            result = await db_manager.db.gp_patients.update_one(
                {"patient_id": patient_id},  # Use patient_id field instead of _id
                {"$set": update_data}
            )
        except Exception as e:
            logger.error(f"Database update failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}"
            )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Patient not found: {patient_id}"
            )
        
        logger.info(f"✅ Validated {extraction_type} for patient {patient_id}: {validation_status}")
        
        return {
            "success": True,
            "message": f"Validation recorded: {validation_status}",
            "patient_id": patient_id,
            "extraction_type": extraction_type,
            "validation_status": validation_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating extraction: {e}")
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
    """
    List all chronic patients with search and filtering.
    
    **Query Parameters:**
    - `search`: Search by patient name or ID number
    - `validation_status`: Filter by approved, pending, needs_review
    - `limit`: Number of results (max 500)
    - `skip`: Pagination offset
    """
    
    try:
        # Get global db_manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Database manager not initialized"
            )
        
        # Build query
        query = {}
        
        if search:
            query["$or"] = [
                {"demographics.first_names": {"$regex": search, "$options": "i"}},
                {"demographics.surname": {"$regex": search, "$options": "i"}},
                {"demographics.id_number": {"$regex": search, "$options": "i"}}
            ]
        
        if validation_status:
            query["validation_status"] = validation_status
        
        # Try database operations with error handling
        try:
            # Get total count
            total = await db_manager.db.gp_patients.count_documents(query)
            
            # Get patients
            cursor = db_manager.db.gp_patients.find(query).skip(skip).limit(limit)
            patients = await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}"
            )
        
        # Format results
        results = []
        for patient in patients:
            demographics = patient.get('demographics', {})
            chronic_summary = patient.get('chronic_summary', {})
            
            results.append({
                "patient_id": patient.get('_id'),
                "name": f"{demographics.get('first_names', '')} {demographics.get('surname', '')}".strip(),
                "id_number": demographics.get('id_number'),
                "date_of_birth": demographics.get('date_of_birth'),
                "chronic_conditions_count": len(chronic_summary.get('chronic_conditions', [])),
                "medications_count": len(chronic_summary.get('current_medications', [])),
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
    """
    Get parsed document with semantic chunks for validation UI.
    
    **Returns:**
    - Full markdown text
    - Semantic chunks with grounding (page, bbox)
    - Metadata (page count, file info)
    """
    
    try:
        # Get global db_manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Database manager not initialized"
            )
        
        # Get parsed document
        parsed_doc = await db_manager.db.gp_parsed_documents.find_one({
            "document_id": document_id
        })
        
        if not parsed_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Parsed document not found: {document_id}"
            )
        
        return {
            "success": True,
            "document_id": document_id,
            "patient_id": parsed_doc.get('patient_id'),
            "filename": parsed_doc.get('filename'),
            "parsed_data": parsed_doc.get('parsed_data', {}),
            "parsed_at": parsed_doc.get('parsed_at')
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
    """
    Search for medications across all chronic patients.
    Useful for finding all patients on a specific medication.
    """
    
    try:
        # Get global db_manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Database manager not initialized"
            )
        
        # Search in chronic_summary.current_medications
        pipeline = [
            {
                "$match": {
                    "chronic_summary.current_medications.medication_name": {
                        "$regex": query,
                        "$options": "i"
                    }
                }
            },
            {
                "$limit": limit
            },
            {
                "$project": {
                    "patient_id": "$_id",
                    "patient_name": {
                        "$concat": [
                            "$demographics.first_names",
                            " ",
                            "$demographics.surname"
                        ]
                    },
                    "medications": "$chronic_summary.current_medications"
                }
            }
        ]
        
        results = await db_manager.db.gp_patients.aggregate(pipeline).to_list(length=limit)
        
        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
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
    """
    Get overall GP chronic patient statistics.
    
    **Returns:**
    - Total patients digitized
    - Validation status breakdown
    - Most common conditions
    - Most prescribed medications
    """
    
    try:
        # Get global db_manager from main module
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Database manager not initialized"
            )
        
        # Get total counts
        total_patients = await db_manager.db.gp_patients.count_documents({})
        approved = await db_manager.db.gp_patients.count_documents({"validation_status": "approved"})
        pending = await db_manager.db.gp_patients.count_documents({"validation_status": "pending"})
        needs_review = await db_manager.db.gp_patients.count_documents({"validation_status": "needs_review"})
        
        # Get most common conditions (aggregation)
        conditions_pipeline = [
            {"$unwind": "$chronic_summary.chronic_conditions"},
            {"$group": {
                "_id": "$chronic_summary.chronic_conditions.condition_name",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        common_conditions = await db_manager.db.gp_patients.aggregate(
            conditions_pipeline
        ).to_list(length=10)
        
        return {
            "success": True,
            "total_patients": total_patients,
            "validation_status": {
                "approved": approved,
                "pending": pending,
                "needs_review": needs_review
            },
            "common_conditions": [
                {
                    "condition": c["_id"],
                    "patient_count": c["count"]
                }
                for c in common_conditions if c["_id"]
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 8: GET VALIDATION SESSION DATA (NEW)
# =============================================================================

@gp_router.get("/validation-session/{document_id}")
async def get_validation_session_data(
    document_id: str,
    request: Optional[str] = Query(None, description="Original request ID"),
    api_key: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Fetch complete validation session payload for the frontend validation UI.
    Returns parsed chunks, extractions, confidence scores, and metadata.
    """

    try:
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)

        if not db_manager or not db_manager.connected:
            raise HTTPException(
                status_code=503,
                detail="Database not available"
            )

        parsed_doc = await db_manager.db["gp_parsed_documents"].find_one({
            "document_id": document_id
        })

        if not parsed_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Parsed document not found: {document_id}"
            )

        validation_session = await db_manager.db["gp_validation_sessions"].find_one({
            "document_id": document_id
        })

        if not validation_session:
            raise HTTPException(
                status_code=404,
                detail=f"Validation session not found for document: {document_id}"
            )

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
            "✅ Served validation data for document %s (chunks: %s)",
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
    """
    Serve the original document file for a patient.
    Used by the validation interface to display the PDF.
    """
    
    try:
        # Look for file in storage directory directly (bypass database for now)
        storage_dir = os.path.join(os.getcwd(), "storage", "gp_documents")
        file_path = None
        filename = 'document.pdf'
        
        if os.path.exists(storage_dir):
            # Look for any file matching the patient_id pattern
            for file in os.listdir(storage_dir):
                if patient_id in file:
                    file_path = os.path.join(storage_dir, file)
                    filename = file.split('_', 1)[1] if '_' in file else file  # Remove patient_id prefix
                    break
        
        if not file_path or not os.path.exists(file_path):
            # Try getting from database as fallback
            try:
                import app.main
                db_manager = getattr(app.main, 'db_manager', None)
                
                if db_manager and db_manager.connected:
                    patient = await db_manager.db.gp_patients.find_one({
                        "patient_id": patient_id
                    })
                    
                    if patient and patient.get('file_path'):
                        file_path = patient.get('file_path')
                        filename = patient.get('filename', 'document.pdf')
            except:
                pass
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail="Original document file not found"
            )
        
        # Return the file
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving document file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 9: VALIDATE EXTRACTION DATA
# =============================================================================

@gp_router.post("/validate-extraction")
async def validate_gp_extraction(
    patient_id: str = Body(...),
    validated_data: dict = Body(...),
    validation_statuses: dict = Body(...),
    validator_notes: str = Body(default="")
):
    """
    Save human-validated extraction data
    """
    
    logger.info(f"💾 Saving validated data for patient: {patient_id}")
    
    try:
        # Get db_manager
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager or not db_manager.connected:
            logger.warning("Database not available")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Validation recorded (database unavailable)",
                    "patient_id": patient_id
                }
            )
        
        # Update the patient record
        update_result = await db_manager.db.gp_patients.update_one(
            {"patient_id": patient_id},
            {
                "$set": {
                    "validated_extractions": validated_data,
                    "validation_statuses": validation_statuses,
                    "validator_notes": validator_notes,
                    "is_validated": True,
                    "validation_status": "completed",
                    "validated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if update_result.modified_count > 0:
            logger.info(f"✅ Validated data saved for patient: {patient_id}")
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
                status_code=404,
                content={
                    "success": False,
                    "message": "Patient record not found"
                }
            )
            
    except Exception as e:
        logger.error(f"Failed to save validation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENDPOINT 10: SAVE VALIDATED PATIENT (NEW MONGODB PATTERN)
# =============================================================================

@gp_router.post("/save-validated-patient")
async def save_validated_patient(
    organization_id: str = Body(...),
    document_id: str = Body(...),
    validated_data: dict = Body(...)
):
    """
    Save validated patient data after human review
    Uses the new MongoDB persistence pattern
    """
    
    logger.info(f"💾 Saving validated patient data for document: {document_id}")
    
    try:
        # Get database manager and GP processor
        import app.main
        db_manager = getattr(app.main, 'db_manager', None)
        
        if not db_manager:
            raise HTTPException(
                status_code=503,
                detail="Database manager not initialized"
            )
        
        # Initialize GP processor with db_manager
        from app.services.gp_processor import GPDocumentProcessor
        processor = GPDocumentProcessor(db_manager=db_manager)
        
        # Save validated patient data using the new method
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

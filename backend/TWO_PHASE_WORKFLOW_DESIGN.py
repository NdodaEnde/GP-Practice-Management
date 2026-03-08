"""
Two-Phase Document Processing Implementation
Phase 1: Parse-only upload (fast, cheap)
Phase 2: Extract on-demand (can be done multiple times)
"""

PHASE_1_PARSE_ONLY_UPLOAD = """
@api_router.post("/gp/documents/upload")
async def upload_document_parse_only(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    workspace_id: str = Form(DEMO_WORKSPACE_ID)
):
    '''
    Phase 1: Upload and Parse Only
    - Uploads file to storage
    - Calls LandingAI ADE Parse API
    - Saves parsed document to MongoDB  
    - Creates digitised_documents record with status="parsed"
    - Returns document_id for later extraction
    '''
    document_id = str(uuid.uuid4())
    
    try:
        logger.info(f"📤 Phase 1: Uploading {file.filename}")
        
        # Read file
        file_content = await file.read()
        file_size = len(file_content)
        
        # Save to storage
        storage_dir = Path("storage/gp_documents")
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = storage_dir / f"{document_id}_{file.filename}"
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Create digitised_documents record
        digitised_doc_data = {
            'id': document_id,
            'workspace_id': workspace_id,
            'patient_id': patient_id,
            'filename': file.filename,
            'file_path': str(file_path),
            'file_size': file_size,
            'status': 'parsing',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table('digitised_documents').insert(digitised_doc_data).execute()
        logger.info(f"✅ Created record: {document_id}")
        
        # Parse with LandingAI (ADE Parse API)
        from app.services.gp_processor import GPDocumentProcessor
        processor = GPDocumentProcessor(db_manager=type('obj', (object,), {
            'db': db,
            'connected': True
        }))
        
        # Parse only - no extraction yet
        parse_result = await processor.parse_document_only(
            file_path=str(file_path),
            filename=file.filename,
            workspace_id=workspace_id,
            file_data=file_content
        )
        
        if parse_result.get('success'):
            # Update status to parsed
            supabase.table('digitised_documents').update({
                'status': 'parsed',
                'parsed_doc_id': parse_result.get('parsed_doc_id'),
                'pages_count': parse_result.get('pages_count'),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', document_id).execute()
            
            logger.info(f"✅ Document parsed: {document_id}")
            
            return JSONResponse(content={
                'status': 'success',
                'message': 'Document uploaded and parsed successfully',
                'data': {
                    'document_id': document_id,
                    'parsed_doc_id': parse_result.get('parsed_doc_id'),
                    'pages_count': parse_result.get('pages_count'),
                    'ready_for_extraction': True
                }
            })
        else:
            # Update to error
            supabase.table('digitised_documents').update({
                'status': 'error',
                'error_message': parse_result.get('error'),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', document_id).execute()
            
            raise HTTPException(status_code=500, detail=parse_result.get('error'))
            
    except Exception as e:
        logger.error(f"❌ Parse-only upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
"""

PHASE_2_EXTRACT_ON_DEMAND = """
@api_router.post("/gp/documents/{document_id}/extract")
async def extract_from_parsed_document(
    document_id: str,
    template_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    encounter_id: Optional[str] = None
):
    '''
    Phase 2: Extract on Demand
    - Reads parsed document from MongoDB
    - Applies template-driven extraction
    - Auto-populates structured tables (ICD-10, NAPPI, etc.)
    - Can be run multiple times with different templates
    '''
    try:
        logger.info(f"🔍 Phase 2: Extracting from {document_id}")
        
        # Get document record
        doc_result = supabase.table('digitised_documents').select('*').eq('id', document_id).execute()
        
        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = doc_result.data[0]
        
        if doc['status'] != 'parsed':
            raise HTTPException(
                status_code=400, 
                detail=f"Document must be in 'parsed' status. Current status: {doc['status']}"
            )
        
        parsed_doc_id = doc.get('parsed_doc_id')
        if not parsed_doc_id:
            raise HTTPException(status_code=400, detail="No parsed document ID found")
        
        # Update status
        supabase.table('digitised_documents').update({
            'status': 'extracting',
            'updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', document_id).execute()
        
        # Extract with templates
        from app.services.extraction_engine import ExtractionEngine
        engine = ExtractionEngine(db)
        
        extraction_result = await engine.extract_from_parsed_document(
            parsed_doc_id=parsed_doc_id,
            template_id=template_id,
            patient_id=patient_id or doc.get('patient_id'),
            encounter_id=encounter_id,
            workspace_id=doc['workspace_id']
        )
        
        if extraction_result.get('success'):
            # Update with extraction results
            supabase.table('digitised_documents').update({
                'status': 'extracted',
                'template_id': template_id,
                'template_used': True,
                'records_created': extraction_result.get('records_created', 0),
                'tables_populated': extraction_result.get('tables_populated', {}),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', document_id).execute()
            
            logger.info(f"✅ Extraction complete: {document_id}")
            logger.info(f"📊 Records created: {extraction_result.get('records_created')}")
            
            return JSONResponse(content={
                'status': 'success',
                'message': 'Extraction completed successfully',
                'data': extraction_result
            })
        else:
            supabase.table('digitised_documents').update({
                'status': 'extraction_failed',
                'error_message': extraction_result.get('error'),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', document_id).execute()
            
            raise HTTPException(status_code=500, detail=extraction_result.get('error'))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
"""

# Document the workflow
WORKFLOW_DOCUMENTATION = """
## Two-Phase Document Processing Workflow

### Phase 1: Upload & Parse (Fast & Cheap)
1. User uploads document via /gp/documents/upload
2. System saves file to storage
3. Calls LandingAI ADE Parse API (fast operation)
4. Stores parsed document in MongoDB
5. Updates digitised_documents with status="parsed"
6. Returns document_id

### Phase 2: Extract & Populate (On-Demand)
1. User clicks "Extract" button in UI
2. Calls /gp/documents/{document_id}/extract
3. Reads parsed document from MongoDB (no API call needed)
4. Applies template-driven extraction
5. Auto-populates structured tables with ICD-10/NAPPI lookups
6. Updates digitised_documents with status="extracted"
7. Returns extraction summary

### Benefits:
- ✅ Batch uploads don't timeout (parsing is faster than extraction)
- ✅ Cost-effective (parse once, extract multiple times)
- ✅ Can test different templates without re-parsing
- ✅ Production-ready for heavy duty processing
"""

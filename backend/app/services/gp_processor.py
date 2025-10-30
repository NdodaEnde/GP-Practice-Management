"""
GP Document Processor with MongoDB Persistence
Parses once, extracts multiple times, saves to MongoDB
"""

import os
import io
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import uuid

from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema

# Import your schemas
from app.schemas.gp_demographics import PatientDemographics
from app.schemas.gp_chronic_summary import ChronicPatientSummary
from app.schemas.gp_vitals import VitalSignsExtraction
from app.services.extraction_engine import ExtractionEngine
import logging
logger = logging.getLogger(__name__)

# --- Convert Pydantic Models to ADE-compatible JSON Schemas ---
demographics_schema = pydantic_to_json_schema(PatientDemographics)
chronic_schema = pydantic_to_json_schema(ChronicPatientSummary)
vitals_schema = pydantic_to_json_schema(VitalSignsExtraction)

class GPDocumentProcessor:
    """
    GP Patient File Processor with MongoDB persistence
    Implements: Parse once, extract many, save to database
    """
    
    def __init__(self, db_manager=None):
        """
        Initialize processor
        
        Args:
            db_manager: MongoDB database manager instance
        """
        api_key = os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY")
        if not api_key:
            raise ValueError("VISION_AGENT_API_KEY or LANDING_AI_API_KEY not set")
        
        self.client = LandingAIADE(apikey=api_key)
        self.db_manager = db_manager
        logger.info("✅ GPDocumentProcessor initialized")
    
    async def process_and_save_patient_file(
        self, 
        file_path: str,
        filename: str,
        organization_id: str,
        file_data: bytes = None
    ) -> Dict:
        """Complete processing workflow with MongoDB persistence"""
        
        logger.info(f"📄 Processing patient file: {filename}")
        start_time = datetime.utcnow()
        
        try:
            # Generate unique IDs
            document_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            
            # STEP 1: Save original scanned document
            scanned_doc_id = await self._save_scanned_document(
                document_id=document_id,
                organization_id=organization_id,
                filename=filename,
                file_path=file_path,
                file_data=file_data
            )
            logger.info(f"✅ Saved scanned document: {scanned_doc_id}")
            
            # STEP 2: Parse document
            logger.info("🔍 Parsing document with LandingAI...")
            parsed_doc = self._parse_document(file_path)
            
            # STEP 3: Save parsed document to MongoDB
            parsed_doc_id = await self._save_parsed_document(
                document_id=document_id,
                organization_id=organization_id,
                parsed_data=parsed_doc,
                filename=filename
            )
            logger.info(f"✅ Saved parsed document: {parsed_doc_id}")
            
            # 🔑 STEP 3.5: RETRIEVE CHUNKS FROM MONGODB (THIS WAS MISSING!)
            parsed_doc_from_db = await self.db_manager.db["gp_parsed_documents"].find_one({
                "document_id": document_id
            })
            
            if not parsed_doc_from_db:
                raise Exception("Failed to retrieve saved parsed document")
            
            chunks_list = parsed_doc_from_db["parsed_data"]["chunks"]
            pages_processed = parsed_doc_from_db["parsed_data"]["num_pages"]
            
            logger.info(f"📦 Retrieved {len(chunks_list)} chunks from MongoDB")
            
            # STEP 4: Extract schemas
            logger.info("🎯 Extracting structured data...")
            extractions = await self._extract_all_schemas(parsed_doc, file_path)
            
            # STEP 5: Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(extractions)
            
            # STEP 6: Create validation session
            validation_session_id = await self._create_validation_session(
                session_id=session_id,
                document_id=document_id,
                organization_id=organization_id,
                extractions=extractions,
                confidence_scores=confidence_scores
            )
            logger.info(f"✅ Created validation session: {validation_session_id}")
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # 🎯 RETURN COMPLETE STRUCTURE WITH CHUNKS
            result = {
                'success': True,
                'document_id': document_id,
                'scanned_doc_id': scanned_doc_id,
                'parsed_doc_id': parsed_doc_id,
                'validation_session_id': validation_session_id,
                'organization_id': organization_id,
                'filename': filename,
                'patient_id': document_id,
                'chunks': chunks_list,  # ✅ CRITICAL: Include chunks here!
                'pages_processed': pages_processed,
                'model_used': 'dpt-2-latest',
                'extractions': extractions,
                'confidence_scores': confidence_scores,
                'processing_time': processing_time,
                'processed_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"✅ Processing complete in {processing_time:.2f}s")
            logger.info(f"📊 Returning {len(chunks_list)} chunks to frontend")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Processing failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'document_id': document_id if 'document_id' in locals() else None
            }
    
    def _parse_document(self, file_path: str):
        """Parse document using LandingAI with debug logging"""
        parse_response = self.client.parse(
            document=Path(file_path),
            model="dpt-2-latest"
        )
        
        logger.info(f"🧩 Parse response type: {type(parse_response)}")
        logger.info(f"🧩 Has chunks: {hasattr(parse_response, 'chunks')}")
        
        if hasattr(parse_response, 'chunks') and parse_response.chunks:
            sample_chunk = parse_response.chunks[0]
            logger.info(f"🧩 Sample chunk type: {type(sample_chunk)}")
            
            # Convert to dict to see structure
            if hasattr(sample_chunk, 'to_dict'):
                chunk_dict = sample_chunk.to_dict()
                logger.info(f"🧩 Sample chunk keys: {chunk_dict.keys()}")
                if 'grounding' in chunk_dict:
                    logger.info(f"🧩 Grounding structure: {chunk_dict['grounding']}")
            
        return parse_response
    

    async def _extract_all_schemas(self, parsed_doc, file_path: str):
        """
        Extract demographics, chronic summary, and vitals schemas
        from the parsed document markdown using LandingAI ADE.
        Compatible with both dict and Pydantic response formats.
        """
        logger.info("🎯 Extracting structured data...")

        # --- Convert markdown to BytesIO ---
        markdown_bytes = io.BytesIO(parsed_doc.markdown.encode("utf-8"))
        markdown_bytes.seek(0)
        logger.info(f"   Extracted markdown: {len(parsed_doc.markdown)} characters")

        # --- Helper function to safely convert extractions ---
        def safe_model_dump(result):
            """Safely convert LandingAI extract() result to dict"""
            if not result or not hasattr(result, "extraction"):
                return None

            extraction_obj = result.extraction
            if extraction_obj is None:
                return None

            # Case 1: already a dict
            if isinstance(extraction_obj, dict):
                return extraction_obj

            # Case 2: has .to_dict() (LandingAI Pydantic v1)
            if hasattr(extraction_obj, "to_dict"):
                try:
                    return extraction_obj.to_dict()
                except Exception:
                    pass

            # Case 3: has .model_dump() (Pydantic v2)
            if hasattr(extraction_obj, "model_dump"):
                try:
                    return extraction_obj.model_dump()
                except Exception:
                    pass

            # Case 4: has .dict() (legacy)
            if hasattr(extraction_obj, "dict"):
                try:
                    return extraction_obj.dict()
                except Exception:
                    pass

            # Case 5: fallback
            try:
                return dict(extraction_obj)
            except Exception:
                logger.warning("⚠️ Could not convert extraction to dict")
                return None

        # --- Perform schema extractions ---
        extractions = {}

        try:
            demographics_result = self.client.extract(
                schema=demographics_schema,
                markdown=markdown_bytes
            )
            extractions["demographics"] = safe_model_dump(demographics_result)
            logger.info("   ✅ Demographics extracted")
        except Exception as e:
            logger.warning(f"Demographics extraction failed: {e}")
            extractions["demographics"] = None

        try:
            chronic_result = self.client.extract(
                schema=chronic_schema,
                markdown=markdown_bytes
            )
            extractions["chronic_summary"] = safe_model_dump(chronic_result)
            logger.info("   ✅ Chronic summary extracted")
        except Exception as e:
            logger.warning(f"Chronic summary extraction failed: {e}")
            extractions["chronic_summary"] = None

        try:
            vitals_result = self.client.extract(
                schema=vitals_schema,
                markdown=markdown_bytes
            )
            extractions["vitals"] = safe_model_dump(vitals_result)
            logger.info("   ✅ Vitals extracted")
        except Exception as e:
            logger.warning(f"Vitals extraction failed: {e}")
            extractions["vitals"] = None

        logger.info("✅ Completed schema extractions for parsed document")
        return extractions

    
    def _calculate_confidence_scores(self, extractions: Dict) -> Dict:
        """Calculate confidence scores for extractions"""
        
        scores = {}
        
        # Demographics confidence
        if extractions.get('demographics'):
            demo = extractions['demographics']
            required_fields = ['surname', 'first_names', 'id_number']
            present = sum(1 for f in required_fields if demo.get(f))
            scores['demographics'] = present / len(required_fields)
        else:
            scores['demographics'] = 0.0
        
        # Chronic summary confidence
        if extractions.get('chronic_summary'):
            chronic = extractions['chronic_summary']
            has_conditions = len(chronic.get('chronic_conditions', [])) > 0
            has_medications = len(chronic.get('current_medications', [])) > 0
            scores['chronic_summary'] = (has_conditions + has_medications) / 2
        else:
            scores['chronic_summary'] = 0.0
        
        # Vitals confidence
        if extractions.get('vitals'):
            vitals = extractions['vitals']
            has_records = len(vitals.get('vital_signs_records', [])) > 0
            scores['vitals'] = 1.0 if has_records else 0.0
        else:
            scores['vitals'] = 0.0
        
        return scores
    
    # =========================================================================
    # MONGODB SAVE METHODS
    # =========================================================================
    
    async def _save_scanned_document(
        self,
        document_id: str,
        organization_id: str,
        filename: str,
        file_path: str,
        file_data: bytes = None
    ) -> str:
        """Save original scanned document to MongoDB"""
        
        if not self.db_manager or not self.db_manager.connected:
            raise Exception("MongoDB not connected")
        
        # Read file if not provided
        if not file_data:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        
        file_size = len(file_data)
        
        doc = {
            "document_id": document_id,
            "organization_id": organization_id,
            "filename": filename,
            "file_size": file_size,
            "file_type": Path(filename).suffix.lower(),
            "file_data": file_data,  # Binary data
            "uploaded_at": datetime.utcnow(),
            "status": "uploaded"
        }
        
        collection = self.db_manager.db["gp_scanned_documents"]
        result = await collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def _save_parsed_document(
        self,
        document_id: str,
        organization_id: str,
        parsed_data,
        filename: str
    ) -> str:
        """Save LandingAI parsed document to MongoDB in frontend-compatible format"""
        
        if not self.db_manager or not self.db_manager.connected:
            raise Exception("MongoDB not connected")
        
        chunks = []
        pages = set()
        
        # 🔑 CRITICAL FIX: Use .to_dict() to convert Pydantic chunks
        for idx, chunk in enumerate(getattr(parsed_data, "chunks", [])):
            # Convert Pydantic model to dict
            chunk_dict = chunk.to_dict() if hasattr(chunk, 'to_dict') else chunk
            
            # Extract text content
            text_content = chunk_dict.get('text') or chunk_dict.get('content') or chunk_dict.get('markdown', '')
            
            # Extract chunk type
            chunk_type = chunk_dict.get('chunk_type') or chunk_dict.get('type', 'text')
            
            # Extract grounding (LandingAI provides this in the correct format!)
            grounding_data = chunk_dict.get('grounding')
            
            # Build the chunk in frontend format
            chunk_output = {
                "id": chunk_dict.get('id') or f"chunk-{idx}",
                "content": text_content,
                "markdown": chunk_dict.get('markdown', text_content),
                "type": chunk_type,
                "grounding": None  # Default to None
            }
            
            # Process grounding if it exists
            if grounding_data:
                if isinstance(grounding_data, dict):
                    # Single grounding dict
                    page_num = grounding_data.get('page', 0)
                    box = grounding_data.get('box', {})
                    
                    chunk_output["grounding"] = {
                        "page": page_num,
                        "box": {
                            "left": box.get('left') or box.get('l', 0),
                            "top": box.get('top') or box.get('t', 0),
                            "right": box.get('right') or box.get('r', 1),
                            "bottom": box.get('bottom') or box.get('b', 1)
                        }
                    }
                    pages.add(page_num)
                    
                elif isinstance(grounding_data, list) and len(grounding_data) > 0:
                    # Array of grounding dicts - use the first one
                    first_grounding = grounding_data[0]
                    page_num = first_grounding.get('page', 0)
                    box = first_grounding.get('box', {})
                    
                    chunk_output["grounding"] = {
                        "page": page_num,
                        "box": {
                            "left": box.get('left') or box.get('l', 0),
                            "top": box.get('top') or box.get('t', 0),
                            "right": box.get('right') or box.get('r', 1),
                            "bottom": box.get('bottom') or box.get('b', 1)
                        }
                    }
                    pages.add(page_num)
            
            chunks.append(chunk_output)
        
        logger.info(f"✅ Processed {len(chunks)} chunks, {len([c for c in chunks if c['grounding']])} with grounding")
        
        parsed_dict = {
            "chunks": chunks,
            "num_pages": len(pages) if pages else 1,
            "total_chunks": len(chunks)
        }
        
        doc = {
            "document_id": document_id,
            "organization_id": organization_id,
            "filename": filename,
            "parsed_data": parsed_dict,
            "parsed_at": datetime.utcnow(),
            "parser": "landingai_dpt2"
        }
        
        collection = self.db_manager.db["gp_parsed_documents"]
        result = await collection.insert_one(doc)
        logger.info(f"✅ Saved {len(chunks)} chunks with grounding data")
        return str(result.inserted_id)
    
    async def _create_validation_session(
        self,
        session_id: str,
        document_id: str,
        organization_id: str,
        extractions: Dict,
        confidence_scores: Dict
    ) -> str:
        """Create validation session in MongoDB"""
        
        if not self.db_manager or not self.db_manager.connected:
            raise Exception("MongoDB not connected")
        
        doc = {
            "session_id": session_id,
            "document_id": document_id,
            "organization_id": organization_id,
            "status": "pending_validation",
            "extractions": extractions,
            "confidence_scores": confidence_scores,
            "validation_state": {
                "demographics": {"validated": False},
                "chronic_summary": {"validated": False},
                "vitals": {"validated": False}
            },
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        collection = self.db_manager.db["gp_validation_sessions"]
        result = await collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def save_validated_patient(
        self,
        organization_id: str,
        document_id: str,
        validated_data: Dict
    ) -> str:
        """
        Save final validated GP patient data to MongoDB
        Called after human validation is complete
        """
        
        if not self.db_manager or not self.db_manager.connected:
            logger.warning("⚠️ MongoDB not connected - skipping patient save")
            demographics = validated_data.get('demographics', {})
            patient_id = demographics.get('id_number', 'unknown')
            return patient_id
        
        # Extract patient ID from demographics
        demographics = validated_data.get('demographics', {})
        patient_id = demographics.get('id_number')
        
        if not patient_id:
            raise ValueError("Patient ID (id_number) required")
        
        doc = {
            "patient_id": patient_id,
            "document_id": document_id,
            "organization_id": organization_id,
            "demographics": validated_data.get('demographics'),
            "chronic_conditions": validated_data.get('chronic_conditions', []),
            "current_medications": validated_data.get('current_medications', []),
            "vitals_history": validated_data.get('vitals', []),
            "allergies": validated_data.get('allergies', []),
            "validated_at": datetime.utcnow(),
            "status": "validated",
            "created_at": datetime.utcnow()
        }
        
        # Upsert - update if exists, insert if new
        collection = self.db_manager.db["gp_patients"]
        result = await collection.update_one(
            {"patient_id": patient_id, "organization_id": organization_id},
            {"$set": doc},
            upsert=True
        )
        
        logger.info(f"✅ Saved validated patient: {patient_id}")
        return patient_id

    
    async def process_with_template(
        self,
        file_path: str,
        filename: str,
        organization_id: str,
        workspace_id: str,
        tenant_id: str,
        template_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        encounter_id: Optional[str] = None,
        file_data: bytes = None
    ) -> Dict:
        """
        Enhanced processing with template-driven extraction and auto-population
        
        This is the NEW WORKFLOW that combines:
        - Layer 1: Core demographics extraction (always)
        - Layer 2: Template-driven flexible extraction (based on mappings)
        - Auto-population to structured tables
        """
        
        logger.info(f"📄 Processing patient file with templates: {filename}")
        start_time = datetime.utcnow()
        
        try:
            # Generate unique IDs
            document_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            
            # STEP 1: Save original scanned document
            scanned_doc_id = await self._save_scanned_document(
                document_id=document_id,
                organization_id=organization_id,
                filename=filename,
                file_path=file_path,
                file_data=file_data
            )
            logger.info(f"✅ Saved scanned document: {scanned_doc_id}")
            
            # STEP 2: Parse document with LandingAI
            logger.info("🔍 Parsing document with LandingAI...")
            parsed_doc = self._parse_document(file_path)
            
            # STEP 3: Save parsed document to MongoDB
            parsed_doc_id = await self._save_parsed_document(
                document_id=document_id,
                organization_id=organization_id,
                parsed_data=parsed_doc,
                filename=filename
            )
            logger.info(f"✅ Saved parsed document: {parsed_doc_id}")
            
            # STEP 4: LAYER 1 - Extract core demographics (always)
            logger.info("🎯 LAYER 1: Extracting core demographics...")
            core_extractions = await self._extract_all_schemas(parsed_doc, file_path)
            
            # STEP 5: LAYER 2 - Template-driven extraction
            logger.info("🎯 LAYER 2: Template-driven extraction...")
            
            # Initialize extraction engine
            extraction_engine = ExtractionEngine(workspace_id, tenant_id)
            
            # Get active template (if not specified, get default)
            if not template_id:
                templates = await extraction_engine.get_workspace_templates(document_type='medical_record')
                if templates:
                    # Use first active template or default template
                    template = next((t for t in templates if t.get('is_default')), templates[0])
                    template_id = template['id']
                    logger.info(f"📝 Using template: {template.get('template_name')}")
                else:
                    logger.warning("⚠️ No templates configured for this workspace")
                    template_id = None
            
            # Combine core extractions with any additional data from document
            all_extracted_data = {
                **core_extractions,
                # Add raw markdown for template-based extraction
                '_raw_markdown': parsed_doc.markdown if hasattr(parsed_doc, 'markdown') else None
            }
            
            # STEP 6: Apply template mappings and auto-populate
            population_result = {'success': True, 'tables_populated': {}, 'records_created': 0}
            
            if template_id and patient_id:
                logger.info("🔄 Applying template mappings and auto-populating tables...")
                population_result = await extraction_engine.process_extraction(
                    extracted_data=all_extracted_data,
                    template_id=template_id,
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    document_id=document_id
                )
                
                logger.info(f"✅ Auto-population complete: {population_result['records_created']} records created")
                logger.info(f"📊 Tables populated: {list(population_result['tables_populated'].keys())}")
            else:
                logger.info("ℹ️ Skipping auto-population (no template or patient_id)")
            
            # STEP 7: Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(core_extractions)
            
            # STEP 8: Create validation session
            validation_session_id = await self._create_validation_session(
                session_id=session_id,
                document_id=document_id,
                organization_id=organization_id,
                extractions=core_extractions,
                confidence_scores=confidence_scores
            )
            logger.info(f"✅ Created validation session: {validation_session_id}")
            
            # STEP 9: Retrieve chunks for frontend
            parsed_doc_from_db = await self.db_manager.db["gp_parsed_documents"].find_one({
                "document_id": document_id
            })
            
            chunks_list = parsed_doc_from_db["parsed_data"]["chunks"] if parsed_doc_from_db else []
            pages_processed = parsed_doc_from_db["parsed_data"]["num_pages"] if parsed_doc_from_db else 1
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # 🎯 RETURN COMPLETE RESULT
            result = {
                'success': True,
                'document_id': document_id,
                'scanned_doc_id': scanned_doc_id,
                'parsed_doc_id': parsed_doc_id,
                'validation_session_id': validation_session_id,
                'organization_id': organization_id,
                'workspace_id': workspace_id,
                'filename': filename,
                'patient_id': patient_id or document_id,
                'chunks': chunks_list,
                'pages_processed': pages_processed,
                'model_used': 'dpt-2-latest',
                
                # Layer 1: Core extractions
                'extractions': core_extractions,
                'confidence_scores': confidence_scores,
                
                # Layer 2: Template results
                'template_id': template_id,
                'template_used': template_id is not None,
                'auto_population': population_result,
                
                'processing_time': processing_time,
                'processed_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"✅ Processing complete in {processing_time:.2f}s")
            logger.info(f"📊 Core extractions: {len(core_extractions)} sections")
            logger.info(f"📊 Auto-populated: {population_result['records_created']} records across {len(population_result['tables_populated'])} tables")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Processing failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'document_id': document_id if 'document_id' in locals() else None
            }


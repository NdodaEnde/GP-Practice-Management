"""
GP Document Processor with Supabase Persistence
Parses once, extracts multiple times, saves to Supabase PostgreSQL
"""

import os
import io
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
import uuid

from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema

# Import your schemas — the legacy 3-schema split (still used as fallback)
from app.schemas.gp_demographics import PatientDemographics
from app.schemas.gp_chronic_summary import ChronicPatientSummary
from app.schemas.gp_vitals import VitalSignsExtraction
# The rich 9-section schema ported from groundtruth — single extract call,
# fills Demographics / Hx / Vitals / Diagnoses / Medications / Progress Notes /
# Labs / Referrals tabs in one shot.
from app.schemas.digitisation.gp_patient import GPPatientRecordExtraction
from app.services.extraction_engine import ExtractionEngine
import logging
logger = logging.getLogger(__name__)

# --- Convert Pydantic Models to ADE-compatible JSON Schemas ---
demographics_schema = pydantic_to_json_schema(PatientDemographics)
chronic_schema      = pydantic_to_json_schema(ChronicPatientSummary)
vitals_schema       = pydantic_to_json_schema(VitalSignsExtraction)
gp_record_schema    = pydantic_to_json_schema(GPPatientRecordExtraction)

class GPDocumentProcessor:
    """
    GP Patient File Processor with Supabase persistence
    Implements: Parse once, extract many, save to database
    """

    def __init__(self, supabase_client=None, db_manager=None):
        """
        Initialize processor

        Args:
            supabase_client: Supabase client instance
            db_manager: Legacy MongoDB database manager (deprecated, kept for compatibility)
        """
        api_key = os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY")
        if not api_key:
            raise ValueError("VISION_AGENT_API_KEY or LANDING_AI_API_KEY not set")

        self.client = LandingAIADE(apikey=api_key)
        self.supabase = supabase_client
        self.db_manager = db_manager  # Legacy fallback
        logger.info("GPDocumentProcessor initialized")

    async def process_and_save_patient_file(
        self,
        file_path: str,
        filename: str,
        organization_id: str,
        document_id: str = None,
        workspace_id: str = None,
        file_data: bytes = None
    ) -> Dict:
        """Complete processing workflow with Supabase persistence"""

        logger.info(f"Processing patient file: {filename}")
        start_time = datetime.now(timezone.utc)

        try:
            # Generate unique IDs
            if not document_id:
                document_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())

            # STEP 1: Parse document
            logger.info("Parsing document with LandingAI...")
            parsed_doc = self._parse_document(file_path)

            # STEP 2: Process chunks and save parsed document to Supabase
            chunks_list, pages_processed = self._process_chunks(parsed_doc)

            parsed_doc_id = await self._save_parsed_document(
                document_id=document_id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                parsed_data={"chunks": chunks_list, "num_pages": pages_processed, "total_chunks": len(chunks_list)},
                filename=filename
            )
            logger.info(f"Saved parsed document: {parsed_doc_id}")
            logger.info(f"Processed {len(chunks_list)} chunks")

            # STEP 3: Extract schemas + capture LandingAI's per-field grounding metadata.
            #   _extract_all_schemas returns (extractions, extraction_metadata).
            #   extraction_metadata is LandingAI's native per-field {value, references}
            #   shape — references is a list of chunk IDs the value was grounded in.
            #   Empty references = LLM-inferred (lower confidence).
            #   Non-empty references = grounded in source text (high confidence).
            logger.info("Extracting structured data...")
            extractions, extraction_metadata = await self._extract_all_schemas(parsed_doc, file_path)

            # STEP 4: Confidence is now derived from the metadata (not heuristic).
            #   The frontend reads extraction_metadata directly to render per-field
            #   badges + click-to-source. We still produce a coarse summary here
            #   for backward compatibility with anything reading confidence_scores.
            confidence_scores = self._summarise_grounding(extraction_metadata)

            # STEP 5: Create validation session — extraction_metadata included.
            validation_session_id = await self._create_validation_session(
                session_id=session_id,
                document_id=document_id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                extractions=extractions,
                confidence_scores=confidence_scores,
                extraction_metadata=extraction_metadata,
            )
            logger.info(f"Created validation session: {validation_session_id}")

            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            result = {
                'success': True,
                'document_id': document_id,
                'parsed_doc_id': parsed_doc_id,
                'validation_session_id': validation_session_id,
                'organization_id': organization_id,
                'filename': filename,
                'patient_id': document_id,
                'chunks': chunks_list,
                'pages_processed': pages_processed,
                'model_used': 'dpt-2-latest',
                'extractions': extractions,
                'confidence_scores': confidence_scores,
                'processing_time': processing_time,
                'processed_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Processing complete in {processing_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
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

        logger.info(f"Parse response type: {type(parse_response)}")
        logger.info(f"Has chunks: {hasattr(parse_response, 'chunks')}")

        if hasattr(parse_response, 'chunks') and parse_response.chunks:
            sample_chunk = parse_response.chunks[0]
            logger.info(f"Sample chunk type: {type(sample_chunk)}")

        return parse_response

    def _process_chunks(self, parsed_data):
        """Process LandingAI chunks into frontend-compatible format"""
        chunks = []
        pages = set()

        for idx, chunk in enumerate(getattr(parsed_data, "chunks", [])):
            chunk_dict = chunk.to_dict() if hasattr(chunk, 'to_dict') else chunk

            text_content = chunk_dict.get('text') or chunk_dict.get('content') or chunk_dict.get('markdown', '')
            chunk_type = chunk_dict.get('chunk_type') or chunk_dict.get('type', 'text')
            grounding_data = chunk_dict.get('grounding')

            chunk_output = {
                "id": chunk_dict.get('id') or f"chunk-{idx}",
                "content": text_content,
                "markdown": chunk_dict.get('markdown', text_content),
                "type": chunk_type,
                "grounding": None
            }

            if grounding_data:
                if isinstance(grounding_data, dict):
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

        num_pages = len(pages) if pages else 1
        logger.info(f"Processed {len(chunks)} chunks, {len([c for c in chunks if c['grounding']])} with grounding")
        return chunks, num_pages

    async def _extract_all_schemas(self, parsed_doc, file_path: str):
        """
        Extract demographics, chronic summary, and vitals schemas
        from the parsed document markdown using LandingAI ADE.
        """
        logger.info("Extracting structured data...")

        markdown_bytes = io.BytesIO(parsed_doc.markdown.encode("utf-8"))
        markdown_bytes.seek(0)
        logger.info(f"   Extracted markdown: {len(parsed_doc.markdown)} characters")

        def safe_model_dump(result):
            """Safely convert LandingAI extract() result to dict"""
            if not result or not hasattr(result, "extraction"):
                return None
            extraction_obj = result.extraction
            if extraction_obj is None:
                return None
            if isinstance(extraction_obj, dict):
                return extraction_obj
            if hasattr(extraction_obj, "to_dict"):
                try:
                    return extraction_obj.to_dict()
                except Exception:
                    pass
            if hasattr(extraction_obj, "model_dump"):
                try:
                    return extraction_obj.model_dump()
                except Exception:
                    pass
            if hasattr(extraction_obj, "dict"):
                try:
                    return extraction_obj.dict()
                except Exception:
                    pass
            try:
                return dict(extraction_obj)
            except Exception:
                logger.warning("Could not convert extraction to dict")
                return None

        # Helper: coerce a LandingAI extraction_metadata payload (Pydantic OR
        # dict OR None) to a plain dict for JSON storage.
        def safe_meta_dump(result):
            if not result or not hasattr(result, "extraction_metadata"):
                return None
            em = result.extraction_metadata
            if em is None:                     return None
            if isinstance(em, dict):           return em
            if hasattr(em, "model_dump"):
                try: return em.model_dump()
                except Exception: pass
            if hasattr(em, "to_dict"):
                try: return em.to_dict()
                except Exception: pass
            try: return dict(em)
            except Exception:
                logger.warning("Could not convert extraction_metadata to dict")
                return None

        extractions = {}
        extraction_metadata = None

        # Primary path: ONE LandingAI extract call against the full
        # GPPatientRecordExtraction schema. Output keys mirror the 9-section
        # EHR panel directly (patient_demographics, vitals_history,
        # clinical_history, diagnoses, medications, progress_notes,
        # investigations, referrals, etc).
        try:
            logger.info("   Extracting with rich GPPatientRecordExtraction schema (one call)...")
            rich_result = self.client.extract(
                schema=gp_record_schema,
                markdown=markdown_bytes,
            )
            rich = safe_model_dump(rich_result)
            extraction_metadata = safe_meta_dump(rich_result)
            if rich and isinstance(rich, dict):
                # Strip None values so the panel doesn't render empty sub-objects
                extractions = {k: v for k, v in rich.items() if v is not None}
                logger.info(f"   Rich extract produced {len(extractions)} top-level sections: {list(extractions.keys())}")
                # Log how much grounding we got — important quality signal
                if extraction_metadata:
                    grounded = self._count_grounded_fields(extraction_metadata)
                    logger.info(f"   Grounding: {grounded['with_refs']}/{grounded['total']} leaf fields ({grounded['pct']}%) reference source chunks")
                return extractions, extraction_metadata
            logger.warning("   Rich extract returned empty/None — falling back to legacy 3-schema split.")
        except Exception as e:
            logger.warning(f"   Rich extract failed ({e}); falling back to legacy 3-schema split.")

        # Reset the markdown stream pointer for the fallback calls.
        markdown_bytes.seek(0)

        # Fallback: legacy 3-schema split (demographics + chronic_summary + vitals).
        # The frontend normaliser maps this shape to the rich shape so the panel
        # still renders, just with fewer sections populated.
        try:
            demographics_result = self.client.extract(schema=demographics_schema, markdown=markdown_bytes)
            extractions["demographics"] = safe_model_dump(demographics_result)
            logger.info("   Demographics extracted (fallback)")
        except Exception as e:
            logger.warning(f"Demographics extraction failed: {e}")
            extractions["demographics"] = None

        markdown_bytes.seek(0)
        try:
            chronic_result = self.client.extract(schema=chronic_schema, markdown=markdown_bytes)
            extractions["chronic_summary"] = safe_model_dump(chronic_result)
            logger.info("   Chronic summary extracted (fallback)")
        except Exception as e:
            logger.warning(f"Chronic summary extraction failed: {e}")
            extractions["chronic_summary"] = None

        markdown_bytes.seek(0)
        try:
            vitals_result = self.client.extract(schema=vitals_schema, markdown=markdown_bytes)
            extractions["vitals"] = safe_model_dump(vitals_result)
            logger.info("   Vitals extracted (fallback)")
        except Exception as e:
            logger.warning(f"Vitals extraction failed: {e}")
            extractions["vitals"] = None

        logger.info("Completed schema extractions for parsed document (legacy 3-schema fallback — no extraction_metadata)")
        return extractions, None


    # ----------------------------------------------------------------------
    # Grounding helpers — derive per-field provenance from
    # LandingAI's extraction_metadata (each leaf field has {value, references}
    # where references is a list of chunk-ID strings).
    # ----------------------------------------------------------------------

    def _walk_metadata(self, obj, path="", out=None):
        """Yield (field_path, leaf_dict) for every {value, references} leaf."""
        if out is None:
            out = []
        if isinstance(obj, dict):
            if "value" in obj and "references" in obj:
                out.append((path, obj))
                return out
            for k, v in obj.items():
                self._walk_metadata(v, f"{path}.{k}" if path else k, out)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._walk_metadata(item, f"{path}[{i}]", out)
        return out

    def _count_grounded_fields(self, extraction_metadata: Dict) -> Dict:
        """Coverage stats — used for logging + the summary on the dashboard."""
        if not extraction_metadata:
            return {"total": 0, "with_refs": 0, "pct": 0}
        leaves = self._walk_metadata(extraction_metadata)
        total = len(leaves)
        with_refs = sum(1 for _, leaf in leaves if leaf.get("references"))
        return {
            "total":     total,
            "with_refs": with_refs,
            "pct":       round(100 * with_refs / total) if total else 0,
        }

    def _summarise_grounding(self, extraction_metadata: Dict) -> Dict:
        """
        Section-level rollup of grounding for backward compat with anything
        reading confidence_scores. The frontend now reads extraction_metadata
        directly for per-field detail; this is just a coarse roll-up.
        """
        scores = {}
        if not extraction_metadata or not isinstance(extraction_metadata, dict):
            return scores
        for section_key, section in extraction_metadata.items():
            leaves = self._walk_metadata(section)
            with_value = [l for _, l in leaves if l.get("value") not in (None, "", [])]
            if not with_value:
                scores[section_key] = 0.0
                continue
            grounded = sum(1 for l in with_value if l.get("references"))
            scores[section_key] = round(grounded / len(with_value), 3)
        return scores

    def _calculate_confidence_scores(self, extractions: Dict) -> Dict:
        """Calculate confidence scores for extractions"""

        scores = {}

        if extractions.get('demographics'):
            demo = extractions['demographics']
            required_fields = ['surname', 'first_names', 'id_number']
            present = sum(1 for f in required_fields if demo.get(f))
            scores['demographics'] = present / len(required_fields)
        else:
            scores['demographics'] = 0.0

        if extractions.get('chronic_summary'):
            chronic = extractions['chronic_summary']
            has_conditions = len(chronic.get('chronic_conditions', [])) > 0
            has_medications = len(chronic.get('current_medications', [])) > 0
            scores['chronic_summary'] = (has_conditions + has_medications) / 2
        else:
            scores['chronic_summary'] = 0.0

        if extractions.get('vitals'):
            vitals = extractions['vitals']
            has_records = len(vitals.get('vital_signs_records', [])) > 0
            scores['vitals'] = 1.0 if has_records else 0.0
        else:
            scores['vitals'] = 0.0

        return scores

    # =========================================================================
    # SUPABASE SAVE METHODS
    # =========================================================================

    async def _save_parsed_document(
        self,
        document_id: str,
        organization_id: str,
        workspace_id: str,
        parsed_data: dict,
        filename: str
    ) -> str:
        """Save LandingAI parsed document to Supabase"""

        if not self.supabase:
            raise Exception("Supabase client not initialized")

        doc_id = str(uuid.uuid4())

        doc = {
            "id": doc_id,
            "document_id": document_id,
            "organization_id": organization_id,
            "workspace_id": workspace_id,
            "filename": filename,
            "parsed_data": parsed_data,
            "parser": "landingai_dpt2",
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        result = self.supabase.table("gp_parsed_documents").insert(doc).execute()

        if result.data:
            logger.info(f"Saved {len(parsed_data.get('chunks', []))} chunks to gp_parsed_documents")
            return doc_id
        else:
            raise Exception("Failed to save parsed document to Supabase")

    async def _create_validation_session(
        self,
        session_id: str,
        document_id: str,
        organization_id: str,
        extractions: Dict,
        confidence_scores: Dict,
        workspace_id: str = None,
        patient_id: str = None,
        extraction_metadata: Optional[Dict] = None,
    ) -> str:
        """
        Create validation session in Supabase.

        extraction_metadata holds LandingAI's per-field {value, references} grounding.
        We try the new dedicated column first; if it doesn't exist on the database
        (migration 004 not yet run), we fall back to nesting it inside
        confidence_scores._extraction_metadata so the data still persists and the
        API can surface it without a schema change.
        """

        if not self.supabase:
            raise Exception("Supabase client not initialized")

        doc_id = str(uuid.uuid4())

        # Build payload with extraction_metadata in its own column.
        # extractions_original snapshots the AI's first output and is NEVER
        # modified afterwards — the audit trail's "what did the AI say" anchor.
        base_doc = {
            "id":                  doc_id,
            "session_id":          session_id,
            "document_id":         document_id,
            "organization_id":     organization_id,
            "workspace_id":        workspace_id,
            "patient_id":          patient_id,
            "status":              "pending_validation",
            "extractions":         extractions,
            "extractions_original": extractions,         # frozen AI baseline (migration 005)
            "confidence_scores":   confidence_scores,
            "validation_state": {
                "demographics":     {"validated": False},
                "chronic_summary":  {"validated": False},
                "vitals":           {"validated": False},
            },
            "created_at":          datetime.now(timezone.utc).isoformat(),
        }

        try:
            doc_with_metadata = {**base_doc, "extraction_metadata": extraction_metadata}
            result = self.supabase.table("gp_validation_sessions").insert(doc_with_metadata).execute()
        except Exception as e:
            # Column probably doesn't exist yet — fall back to nesting under confidence_scores.
            msg = str(e).lower()
            if "extraction_metadata" in msg or "extractions_original" in msg:
                # Drop whichever column doesn't exist; loop until insert succeeds.
                fallback = dict(base_doc)
                if "extraction_metadata" in msg:
                    logger.warning("extraction_metadata column missing; nesting under confidence_scores._extraction_metadata. Run migration 004 to fix.")
                    fallback["confidence_scores"] = {
                        **(confidence_scores or {}),
                        "_extraction_metadata": extraction_metadata,
                    }
                else:
                    fallback = {**fallback, "extraction_metadata": extraction_metadata}
                if "extractions_original" in msg:
                    logger.warning("extractions_original column missing; skipping AI baseline snapshot. Run migration 005 to fix.")
                    fallback.pop("extractions_original", None)
                result = self.supabase.table("gp_validation_sessions").insert(fallback).execute()
            else:
                raise

        if result.data:
            return doc_id
        raise Exception("Failed to create validation session in Supabase")

    async def save_validated_patient(
        self,
        organization_id: str,
        document_id: str,
        validated_data: Dict,
        workspace_id: str = None
    ) -> str:
        """
        Save final validated GP patient data to Supabase patients table.
        Called after human validation is complete.
        """

        if not self.supabase:
            logger.warning("Supabase not connected - skipping patient save")
            demographics = validated_data.get('demographics', {})
            return demographics.get('id_number', 'unknown')

        demographics = validated_data.get('demographics', {})
        id_number = demographics.get('id_number')

        if not id_number:
            raise ValueError("Patient ID (id_number) required")

        # Check if patient already exists
        existing = self.supabase.table("patients")\
            .select("id")\
            .eq("id_number", id_number)\
            .execute()

        if existing.data:
            # Update existing patient
            patient_id = existing.data[0]['id']
            update_data = {
                "first_name": demographics.get('first_names', ''),
                "last_name": demographics.get('surname', ''),
                "dob": demographics.get('date_of_birth'),
                "contact_number": demographics.get('contact_number'),
                "email": demographics.get('email'),
                "address": demographics.get('address'),
                "medical_aid": demographics.get('medical_aid_name'),
                "chronic_conditions": validated_data.get('chronic_conditions', []),
                "current_medications": validated_data.get('current_medications', []),
                "allergies": validated_data.get('allergies', []),
                "is_validated": True,
                "validation_status": "validated",
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            self.supabase.table("patients").update(update_data).eq("id", patient_id).execute()
            logger.info(f"Updated validated patient: {patient_id}")
        else:
            # Create new patient
            patient_id = str(uuid.uuid4())
            patient_data = {
                "id": patient_id,
                "tenant_id": organization_id,
                "workspace_id": workspace_id or organization_id,
                "first_name": demographics.get('first_names', ''),
                "last_name": demographics.get('surname', ''),
                "dob": demographics.get('date_of_birth'),
                "id_number": id_number,
                "contact_number": demographics.get('contact_number'),
                "email": demographics.get('email'),
                "address": demographics.get('address'),
                "medical_aid": demographics.get('medical_aid_name'),
                "chronic_conditions": validated_data.get('chronic_conditions', []),
                "current_medications": validated_data.get('current_medications', []),
                "allergies": validated_data.get('allergies', []),
                "is_validated": True,
                "validation_status": "validated",
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            self.supabase.table("patients").insert(patient_data).execute()
            logger.info(f"Created validated patient: {patient_id}")

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
        document_id: str = None,
        file_data: bytes = None
    ) -> Dict:
        """
        Enhanced processing with template-driven extraction and auto-population

        This is the NEW WORKFLOW that combines:
        - Layer 1: Core demographics extraction (always)
        - Layer 2: Template-driven flexible extraction (based on mappings)
        - Auto-population to structured tables
        """

        logger.info(f"Processing patient file with templates: {filename}")
        start_time = datetime.now(timezone.utc)

        try:
            # Generate unique IDs
            if not document_id:
                document_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())

            # STEP 1: Parse document with LandingAI
            logger.info("Parsing document with LandingAI...")
            parsed_doc = self._parse_document(file_path)

            # STEP 2: Process chunks and save parsed document to Supabase
            chunks_list, pages_processed = self._process_chunks(parsed_doc)

            parsed_doc_id = await self._save_parsed_document(
                document_id=document_id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                parsed_data={"chunks": chunks_list, "num_pages": pages_processed, "total_chunks": len(chunks_list)},
                filename=filename
            )
            logger.info(f"Saved parsed document: {parsed_doc_id}")

            # STEP 3: LAYER 1 - Extract core demographics (always)
            logger.info("LAYER 1: Extracting core demographics...")
            core_extractions = await self._extract_all_schemas(parsed_doc, file_path)

            # STEP 4: LAYER 2 - Template-driven extraction
            logger.info("LAYER 2: Template-driven extraction...")

            extraction_engine = ExtractionEngine(workspace_id, tenant_id)

            if not template_id:
                templates = await extraction_engine.get_workspace_templates(document_type='medical_record')
                if templates:
                    template = next((t for t in templates if t.get('is_default')), templates[0])
                    template_id = template['id']
                    logger.info(f"Using template: {template.get('template_name')}")
                else:
                    logger.warning("No templates configured for this workspace")
                    template_id = None

            all_extracted_data = {
                **core_extractions,
                '_raw_markdown': parsed_doc.markdown if hasattr(parsed_doc, 'markdown') else None
            }

            # STEP 5: Apply template mappings and auto-populate
            population_result = {'success': True, 'tables_populated': {}, 'records_created': 0}

            if template_id and patient_id:
                logger.info("Applying template mappings and auto-populating tables...")
                population_result = await extraction_engine.process_extraction(
                    extracted_data=all_extracted_data,
                    template_id=template_id,
                    patient_id=patient_id,
                    encounter_id=encounter_id,
                    document_id=document_id
                )
                logger.info(f"Auto-population complete: {population_result['records_created']} records created")
            else:
                logger.info("Skipping auto-population (no template or patient_id)")

            # STEP 6: Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(core_extractions)

            # STEP 7: Create validation session in Supabase
            validation_session_id = await self._create_validation_session(
                session_id=session_id,
                document_id=document_id,
                organization_id=organization_id,
                workspace_id=workspace_id,
                patient_id=patient_id,
                extractions=core_extractions,
                confidence_scores=confidence_scores
            )
            logger.info(f"Created validation session: {validation_session_id}")

            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            result = {
                'success': True,
                'document_id': document_id,
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
                'processed_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Processing complete in {processing_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'document_id': document_id if 'document_id' in locals() else None
            }

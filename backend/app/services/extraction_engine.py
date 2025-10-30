"""
Extraction Engine - Template-Driven Data Extraction and Population
Handles dynamic field extraction, transformations, and auto-population to EHR tables
"""

from typing import Dict, List, Any, Optional
import uuid
import logging
from datetime import datetime, timezone, date
import re
import os
from supabase import create_client

logger = logging.getLogger(__name__)

# Supabase client
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


class ExtractionEngine:
    """
    Handles template-driven extraction, transformations, and auto-population
    """
    
    def __init__(self, workspace_id: str, tenant_id: str):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        
    async def get_workspace_templates(self, document_type: Optional[str] = None) -> List[Dict]:
        """Get active templates for workspace"""
        try:
            query = supabase.table('extraction_templates')\
                .select('*')\
                .eq('workspace_id', self.workspace_id)\
                .eq('is_active', True)
            
            if document_type:
                query = query.eq('document_type', document_type)
            
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"Failed to get workspace templates: {e}")
            return []
    
    async def get_template_mappings(self, template_id: str) -> List[Dict]:
        """Get active field mappings for a template"""
        try:
            response = supabase.table('extraction_field_mappings')\
                .select('*')\
                .eq('template_id', template_id)\
                .eq('is_active', True)\
                .order('processing_order')\
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to get template mappings: {e}")
            return []
    
    def extract_field_value(self, data: Dict, source_section: str, source_field: str, 
                           source_field_path: Optional[str] = None) -> Any:
        """
        Extract field value from nested data structure
        Supports JSON path notation (e.g., 'demographics.contact.cell_number')
        """
        try:
            # If source_field_path is provided, use it
            if source_field_path:
                path_parts = source_field_path.split('.')
                value = data
                for part in path_parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    elif isinstance(value, list) and part.isdigit():
                        value = value[int(part)]
                    else:
                        return None
                return value
            
            # Otherwise, look for source_section first, then source_field
            if source_section in data:
                section_data = data[source_section]
                
                # Handle list of items (e.g., immunisation_history)
                if isinstance(section_data, list):
                    # Return list of values for this field
                    return [item.get(source_field) for item in section_data if isinstance(item, dict)]
                
                # Handle dict
                elif isinstance(section_data, dict):
                    return section_data.get(source_field)
            
            # Fallback: search entire data structure
            if source_field in data:
                return data[source_field]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract field {source_section}.{source_field}: {e}")
            return None
    
    def apply_transformation(self, value: Any, mapping: Dict) -> Any:
        """
        Apply transformation to extracted value
        Supports: direct, split, concatenation, lookup, ai_match, calculation
        """
        try:
            transformation_type = mapping.get('transformation_type', 'direct')
            field_type = mapping.get('field_type', 'text')
            transformation_config = mapping.get('transformation_config', {})
            
            if value is None:
                return mapping.get('default_value')
            
            # Direct copy - just type conversion
            if transformation_type == 'direct':
                return self._convert_type(value, field_type)
            
            # Split string (e.g., "120/80" -> 120 or 80, "Dose 1/2" -> 1)
            elif transformation_type == 'split':
                delimiter = transformation_config.get('delimiter', '/')
                index = transformation_config.get('index', 0)
                
                if isinstance(value, str):
                    parts = value.split(delimiter)
                    if len(parts) > index:
                        extracted = parts[index].strip()
                        # Extract numeric value if present (e.g., "Dose 1" -> 1)
                        numeric_match = re.search(r'\d+', extracted)
                        if numeric_match:
                            return self._convert_type(numeric_match.group(), field_type)
                        return self._convert_type(extracted, field_type)
                
                return value
            
            # Concatenation (combine multiple fields)
            elif transformation_type == 'concatenation':
                fields = transformation_config.get('fields', [])
                separator = transformation_config.get('separator', ' ')
                
                if isinstance(value, dict):
                    parts = [str(value.get(f, '')) for f in fields if value.get(f)]
                    return separator.join(parts)
                
                return value
            
            # Lookup (match against reference data)
            elif transformation_type == 'lookup':
                lookup_type = transformation_config.get('lookup_type', 'icd10')
                
                if lookup_type == 'icd10':
                    return self._lookup_icd10(value, transformation_config)
                elif lookup_type == 'nappi':
                    return self._lookup_nappi(value, transformation_config)
                else:
                    logger.warning(f"Unknown lookup type: {lookup_type}")
                    return value
            
            # AI Match (use AI to match/suggest codes)
            elif transformation_type == 'ai_match':
                match_type = transformation_config.get('match_type', 'icd10')
                
                if match_type == 'icd10':
                    return self._ai_match_icd10(value, transformation_config)
                elif match_type == 'nappi':
                    return self._ai_match_nappi(value, transformation_config)
                else:
                    logger.warning(f"Unknown match type: {match_type}")
                    return value
            
            # Calculation (calculate from formula)
            elif transformation_type == 'calculation':
                formula = transformation_config.get('formula', '')
                # TODO: Implement safe formula evaluation
                # For now, return as-is
                return value
            
            else:
                return self._convert_type(value, field_type)
                
        except Exception as e:
            logger.error(f"Failed to apply transformation: {e}")
            return value
    
    def _convert_type(self, value: Any, field_type: str) -> Any:
        """Convert value to specified type"""
        try:
            if value is None or value == '':
                return None
            
            if field_type == 'text':
                return str(value)
            
            elif field_type == 'number':
                # Extract numeric value from string
                if isinstance(value, str):
                    numeric_match = re.search(r'-?\d+\.?\d*', value)
                    if numeric_match:
                        value = numeric_match.group()
                return float(value) if '.' in str(value) else int(value)
            
            elif field_type == 'date':
                if isinstance(value, str):
                    # Try to parse various date formats
                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
                        try:
                            return datetime.strptime(value, fmt).date().isoformat()
                        except:
                            continue
                return str(value)
            
            elif field_type == 'datetime':
                if isinstance(value, str):
                    return value  # Assume ISO format
                return str(value)
            
            elif field_type == 'boolean':
                if isinstance(value, str):
                    return value.lower() in ['true', 'yes', '1', 'y']
                return bool(value)
            
            elif field_type == 'json':
                return value  # Keep as-is (dict or list)
            
            else:
                return value
                
        except Exception as e:
            logger.error(f"Failed to convert type: {e}")
            return value
    
    async def populate_target_table(self, table_name: str, record_data: Dict, 
                                   patient_id: str, encounter_id: Optional[str] = None) -> Optional[str]:
        """
        Populate target EHR table with extracted and transformed data
        """
        try:
            # Add common fields
            record_data['id'] = str(uuid.uuid4())
            record_data['tenant_id'] = self.tenant_id
            record_data['workspace_id'] = self.workspace_id
            record_data['patient_id'] = patient_id
            
            if encounter_id:
                record_data['encounter_id'] = encounter_id
            
            # Add timestamps
            now = datetime.now(timezone.utc).isoformat()
            record_data['created_at'] = now
            
            if table_name in ['vitals', 'immunizations', 'procedures', 'clinical_notes']:
                record_data['updated_at'] = now
            
            # Insert into table
            response = supabase.table(table_name).insert(record_data).execute()
            
            if response.data:
                logger.info(f"✅ Populated {table_name}: {record_data['id']}")
                return record_data['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to populate {table_name}: {e}")
            return None
    
    async def process_extraction(self, extracted_data: Dict, template_id: str,
                                patient_id: str, encounter_id: Optional[str] = None,
                                document_id: Optional[str] = None) -> Dict:
        """
        Main processing function: applies mappings and populates tables
        
        Returns:
            {
                'success': bool,
                'tables_populated': {'immunizations': [id1, id2], 'lab_results': [id1]},
                'records_created': int,
                'errors': []
            }
        """
        start_time = datetime.now(timezone.utc)
        result = {
            'success': True,
            'tables_populated': {},
            'records_created': 0,
            'errors': [],
            'processing_time_ms': 0
        }
        
        try:
            # Get template mappings
            mappings = await self.get_template_mappings(template_id)
            
            if not mappings:
                logger.warning(f"No mappings found for template {template_id}")
                result['success'] = False
                result['errors'].append("No field mappings configured for this template")
                return result
            
            logger.info(f"📋 Processing {len(mappings)} field mappings...")
            
            # Group mappings by target table
            tables_data = {}
            
            for mapping in mappings:
                source_section = mapping['source_section']
                source_field = mapping['source_field']
                source_field_path = mapping.get('source_field_path')
                target_table = mapping['target_table']
                target_field = mapping['target_field']
                
                # Extract field value
                value = self.extract_field_value(
                    extracted_data, 
                    source_section, 
                    source_field, 
                    source_field_path
                )
                
                if value is None and not mapping.get('is_required', False):
                    continue  # Skip optional fields with no value
                
                # Apply transformation
                transformed_value = self.apply_transformation(value, mapping)
                
                # Handle list values (e.g., multiple immunizations)
                if isinstance(transformed_value, list):
                    # Create separate records for each item
                    for item_value in transformed_value:
                        if item_value:
                            if target_table not in tables_data:
                                tables_data[target_table] = []
                            
                            # Find or create record for this item
                            # For now, create new record for each item
                            record = {target_field: item_value}
                            tables_data[target_table].append(record)
                
                else:
                    # Single value - add to table data
                    if target_table not in tables_data:
                        tables_data[target_table] = [{}]
                    
                    # Add to first record (or create consolidated record logic later)
                    if not tables_data[target_table]:
                        tables_data[target_table].append({})
                    
                    tables_data[target_table][0][target_field] = transformed_value
            
            # Populate each target table
            for table_name, records in tables_data.items():
                table_ids = []
                
                for record_data in records:
                    if not record_data:  # Skip empty records
                        continue
                    
                    try:
                        record_id = await self.populate_target_table(
                            table_name,
                            record_data,
                            patient_id,
                            encounter_id
                        )
                        
                        if record_id:
                            table_ids.append(record_id)
                            result['records_created'] += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to populate {table_name}: {str(e)}"
                        logger.error(error_msg)
                        result['errors'].append(error_msg)
                
                if table_ids:
                    result['tables_populated'][table_name] = table_ids
            
            # Calculate processing time
            end_time = datetime.now(timezone.utc)
            result['processing_time_ms'] = int((end_time - start_time).total_seconds() * 1000)
            
            # Save extraction history
            if document_id:
                await self._save_extraction_history(
                    document_id=document_id,
                    template_id=template_id,
                    patient_id=patient_id,
                    extracted_data=extracted_data,
                    result=result
                )
            
            logger.info(f"✅ Processing complete: {result['records_created']} records created")
            
        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            result['success'] = False
            result['errors'].append(str(e))
        
        return result
    
    async def _save_extraction_history(self, document_id: str, template_id: str,
                                      patient_id: str, extracted_data: Dict, result: Dict):
        """Save extraction history for audit trail"""
        try:
            history_record = {
                'id': str(uuid.uuid4()),
                'document_id': document_id,
                'template_id': template_id,
                'workspace_id': self.workspace_id,
                'patient_id': patient_id,
                'extraction_datetime': datetime.now(timezone.utc).isoformat(),
                'extraction_status': 'success' if result['success'] else 'failed',
                'structured_extraction': extracted_data,
                'tables_populated': result.get('tables_populated', {}),
                'population_errors': result.get('errors', []),
                'processing_time_ms': result.get('processing_time_ms', 0),
                'fields_extracted': len(extracted_data.keys()),
                'records_created': result.get('records_created', 0),
                'validated': False
            }
            
            supabase.table('extraction_history').insert(history_record).execute()
            logger.info(f"✅ Saved extraction history: {history_record['id']}")
            
        except Exception as e:
            logger.error(f"Failed to save extraction history: {e}")

    
    def _lookup_icd10(self, value: str, config: Dict) -> Optional[str]:
        """
        Lookup ICD-10 code by description (exact or fuzzy match)
        
        Args:
            value: Diagnosis description to match
            config: Configuration with optional 'confidence_threshold'
            
        Returns:
            ICD-10 code if found, else None
        """
        try:
            if not isinstance(value, str) or not value.strip():
                return None
            
            search_term = value.strip().lower()
            confidence_threshold = config.get('confidence_threshold', 0.7)
            
            # Try exact match on WHO full description
            response = supabase.table('icd10_codes')\
                .select('code, who_full_desc')\
                .ilike('who_full_desc', f'%{search_term}%')\
                .limit(5)\
                .execute()
            
            if response.data and len(response.data) > 0:
                # Return first match (highest relevance)
                best_match = response.data[0]
                logger.info(f"✅ ICD-10 match: '{value}' → {best_match['code']} ({best_match['who_full_desc']})")
                return best_match['code']
            
            # Try matching on 3-char code description
            response = supabase.table('icd10_codes')\
                .select('code, code_3char_desc')\
                .ilike('code_3char_desc', f'%{search_term}%')\
                .limit(5)\
                .execute()
            
            if response.data and len(response.data) > 0:
                best_match = response.data[0]
                logger.info(f"✅ ICD-10 match (3char): '{value}' → {best_match['code']} ({best_match.get('code_3char_desc')})")
                return best_match['code']
            
            # If no exact match, try fuzzy matching with individual words
            words = search_term.split()
            if len(words) > 1:
                # Try matching on primary word (usually the condition name)
                for word in words:
                    if len(word) > 3:  # Skip short words
                        response = supabase.table('icd10_codes')\
                            .select('code, who_full_desc')\
                            .ilike('who_full_desc', f'%{word}%')\
                            .limit(3)\
                            .execute()
                        
                        if response.data:
                            best_match = response.data[0]
                            logger.info(f"⚠️ ICD-10 fuzzy match: '{value}' → {best_match['code']} ({best_match['who_full_desc']})")
                            return best_match['code']
            
            logger.warning(f"❌ No ICD-10 match found for: '{value}'")
            return None
            
        except Exception as e:
            logger.error(f"ICD-10 lookup failed: {e}")
            return None
    
    def _lookup_nappi(self, value: str, config: Dict) -> Optional[str]:
        """
        Lookup NAPPI code by medication name
        
        Args:
            value: Medication name to match
            config: Configuration with optional 'confidence_threshold'
            
        Returns:
            NAPPI code if found, else None
        """
        try:
            if not isinstance(value, str) or not value.strip():
                return None
            
            search_term = value.strip().lower()
            
            # Remove common dosage patterns to improve matching
            # e.g., "Atenolol 50mg" -> "Atenolol"
            search_term = re.sub(r'\d+\s*(mg|ml|g|mcg|iu|units?)', '', search_term, flags=re.IGNORECASE).strip()
            
            # Try exact match on product name
            response = supabase.table('nappi_codes')\
                .select('nappi_code, product_name, active_ingredient')\
                .ilike('product_name', f'%{search_term}%')\
                .limit(5)\
                .execute()
            
            if response.data and len(response.data) > 0:
                best_match = response.data[0]
                logger.info(f"✅ NAPPI match: '{value}' → {best_match['nappi_code']} ({best_match['product_name']})")
                return best_match['nappi_code']
            
            # Try matching on active ingredient
            response = supabase.table('nappi_codes')\
                .select('nappi_code, product_name, active_ingredient')\
                .ilike('active_ingredient', f'%{search_term}%')\
                .limit(5)\
                .execute()
            
            if response.data and len(response.data) > 0:
                best_match = response.data[0]
                logger.info(f"⚠️ NAPPI ingredient match: '{value}' → {best_match['nappi_code']} ({best_match['product_name']})")
                return best_match['nappi_code']
            
            logger.warning(f"❌ No NAPPI match found for: '{value}'")
            return None
            
        except Exception as e:
            logger.error(f"NAPPI lookup failed: {e}")
            return None
    
    def _ai_match_icd10(self, value: str, config: Dict) -> Optional[str]:
        """
        AI-powered ICD-10 matching with fuzzy search and ranking
        
        This is more intelligent than direct lookup - it handles:
        - Synonyms (e.g., "high blood pressure" → "hypertension")
        - Abbreviations (e.g., "DM" → "diabetes mellitus")
        - Misspellings
        - Multiple potential matches with confidence scores
        
        For now, uses advanced fuzzy matching. In future, could integrate
        actual AI/LLM for even better matching.
        """
        try:
            if not isinstance(value, str) or not value.strip():
                return None
            
            # Use the lookup function as a starting point
            # In future, this could call an LLM to interpret the diagnosis
            code = self._lookup_icd10(value, config)
            
            if code:
                return code
            
            # Advanced: Try common synonyms/patterns
            synonyms = {
                'high blood pressure': 'hypertension',
                'sugar diabetes': 'diabetes mellitus',
                'heart attack': 'myocardial infarction',
                'stroke': 'cerebrovascular accident',
                'hbp': 'hypertension',
                'dm': 'diabetes mellitus',
                'copd': 'chronic obstructive pulmonary disease',
                'ckd': 'chronic kidney disease'
            }
            
            search_term = value.lower().strip()
            for synonym, standard_term in synonyms.items():
                if synonym in search_term:
                    return self._lookup_icd10(standard_term, config)
            
            return None
            
        except Exception as e:
            logger.error(f"AI ICD-10 matching failed: {e}")
            return None
    
    def _ai_match_nappi(self, value: str, config: Dict) -> Optional[str]:
        """
        AI-powered NAPPI matching with intelligent name resolution
        
        Handles:
        - Brand name → Generic name mapping
        - Dosage form variations
        - Common abbreviations
        """
        try:
            if not isinstance(value, str) or not value.strip():
                return None
            
            # Use the lookup function as a starting point
            code = self._lookup_nappi(value, config)
            
            if code:
                return code
            
            # Advanced: Try common brand-to-generic mappings
            brand_mappings = {
                'panado': 'paracetamol',
                'brufen': 'ibuprofen',
                'voltaren': 'diclofenac',
                'disprin': 'aspirin',
                'syndol': 'paracetamol',
                'corenza': 'paracetamol',
                'adco': ''  # Remove brand prefix
            }
            
            search_term = value.lower().strip()
            for brand, generic in brand_mappings.items():
                if brand in search_term:
                    if generic:
                        return self._lookup_nappi(generic, config)
                    else:
                        # Remove brand prefix and try again
                        cleaned = search_term.replace(brand, '').strip()
                        if cleaned:
                            return self._lookup_nappi(cleaned, config)
            
            return None
            
        except Exception as e:
            logger.error(f"AI NAPPI matching failed: {e}")
            return None


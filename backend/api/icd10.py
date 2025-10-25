"""
ICD-10 Code Search and Lookup API
Sprint 1.3: Structured Diagnoses with ICD-10
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

# Pydantic models
class ICD10Code(BaseModel):
    code: str
    who_full_desc: str
    chapter_desc: Optional[str]
    group_desc: Optional[str]
    code_3char: Optional[str]
    code_3char_desc: Optional[str]
    valid_clinical_use: bool
    valid_primary: bool
    gender: Optional[str]
    age_range: Optional[str]

@router.get("/icd10/search", response_model=List[ICD10Code])
async def search_icd10_codes(
    query: str = Query(..., min_length=2, description="Search term (min 2 characters)"),
    limit: int = Query(20, le=100, description="Maximum number of results"),
    clinical_use_only: bool = Query(True, description="Only return codes valid for clinical use")
):
    """
    Search ICD-10 codes by description or code
    Full-text search on WHO description
    """
    from server import supabase
    
    try:
        # Build query
        db_query = supabase.table('icd10_codes').select('*')
        
        # Filter by clinical use if requested
        if clinical_use_only:
            db_query = db_query.eq('valid_clinical_use', True)
        
        # Full-text search on description (using ilike for simple search)
        # For production, use PostgreSQL full-text search
        db_query = db_query.ilike('who_full_desc', f'%{query}%')
        
        # Limit results
        db_query = db_query.limit(limit)
        
        result = db_query.execute()
        
        return result.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/icd10/code/{code}", response_model=ICD10Code)
async def get_icd10_code(code: str):
    """Get specific ICD-10 code details"""
    from server import supabase
    
    try:
        result = supabase.table('icd10_codes').select('*').eq('code', code).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail=f"ICD-10 code '{code}' not found")
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lookup failed: {str(e)}")

@router.get("/icd10/chapter/{chapter_no}", response_model=List[ICD10Code])
async def get_chapter_codes(
    chapter_no: str,
    limit: int = Query(100, le=500, description="Maximum number of results")
):
    """Get all codes in a specific ICD-10 chapter"""
    from server import supabase
    
    try:
        result = supabase.table('icd10_codes')\
            .select('*')\
            .eq('chapter_no', chapter_no)\
            .eq('valid_clinical_use', True)\
            .limit(limit)\
            .execute()
        
        return result.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chapter lookup failed: {str(e)}")

@router.get("/icd10/suggest")
async def suggest_icd10_from_text(
    diagnosis_text: str = Query(..., min_length=5, description="Diagnosis text to analyze"),
    max_suggestions: int = Query(5, le=10, description="Maximum suggestions")
):
    """
    AI-powered ICD-10 code suggestion from diagnosis text
    Uses GPT-4 to suggest appropriate codes
    """
    from server import supabase
    import os
    from openai import OpenAI
    
    try:
        # Check if we have OpenAI integration
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            # Fallback to simple keyword search
            return await search_icd10_codes(query=diagnosis_text, limit=max_suggestions)
        
        # Use GPT-4 to suggest ICD-10 codes
        client = OpenAI(api_key=openai_key)
        
        prompt = f"""You are a medical coding expert. Given the following diagnosis or clinical text, suggest the most appropriate ICD-10 codes.

Clinical Text: "{diagnosis_text}"

Return only the ICD-10 codes (format: A00.0, J45.9, etc.) as a comma-separated list, with the most relevant first.
Maximum {max_suggestions} codes.
Only suggest codes that exist in ICD-10.

Format: code1, code2, code3"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a medical coding assistant specializing in ICD-10 codes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        suggested_codes_text = response.choices[0].message.content.strip()
        suggested_codes = [code.strip() for code in suggested_codes_text.split(',')]
        
        # Look up suggested codes in database
        suggestions = []
        for code in suggested_codes[:max_suggestions]:
            try:
                result = supabase.table('icd10_codes').select('*').eq('code', code).execute()
                if result.data:
                    suggestions.append(result.data[0])
            except:
                continue
        
        return {
            'original_text': diagnosis_text,
            'suggestions': suggestions,
            'ai_response': suggested_codes_text
        }
    
    except Exception as e:
        # Fallback to keyword search
        fallback_results = await search_icd10_codes(query=diagnosis_text, limit=max_suggestions)
        return {
            'original_text': diagnosis_text,
            'suggestions': fallback_results,
            'note': 'AI suggestion unavailable, showing keyword search results'
        }

@router.get("/icd10/stats")
async def get_icd10_stats():
    """Get statistics about loaded ICD-10 codes"""
    from server import supabase
    
    try:
        # Total codes
        total_result = supabase.table('icd10_codes').select('code', count='exact').execute()
        total_count = total_result.count
        
        # Clinically usable codes
        clinical_result = supabase.table('icd10_codes')\
            .select('code', count='exact')\
            .eq('valid_clinical_use', True)\
            .execute()
        clinical_count = clinical_result.count
        
        # Primary diagnosis codes
        primary_result = supabase.table('icd10_codes')\
            .select('code', count='exact')\
            .eq('valid_primary', True)\
            .execute()
        primary_count = primary_result.count
        
        return {
            'total_codes': total_count,
            'clinical_use_codes': clinical_count,
            'primary_diagnosis_codes': primary_count,
            'version': 'ICD-10 MIT 2021 (South Africa)'
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")

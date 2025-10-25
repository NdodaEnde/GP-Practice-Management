"""
NAPPI Codes API endpoints
National Pharmaceutical Product Interface - South African medication coding
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import os
from supabase import create_client

router = APIRouter()

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# Response Models
class NAPPICode(BaseModel):
    nappi_code: str
    brand_name: str
    generic_name: str
    strength: Optional[str]
    dosage_form: Optional[str]
    ingredients: Optional[str]
    schedule: Optional[str]
    atc_code: Optional[str]
    therapeutic_class: Optional[str]
    pack_size: Optional[str]
    manufacturer: Optional[str]
    route_of_administration: Optional[str]
    status: str


class NAPPIStatsResponse(BaseModel):
    total_codes: int
    active_codes: int
    by_schedule: dict


class NAPPISearchResponse(BaseModel):
    results: List[NAPPICode]
    count: int
    query: str


@router.get("/nappi/stats", response_model=NAPPIStatsResponse)
async def get_nappi_stats():
    """Get NAPPI database statistics"""
    try:
        # Total codes
        total_result = supabase.table('nappi_codes').select('nappi_code', count='exact').execute()
        total_count = total_result.count
        
        # Active codes
        active_result = supabase.table('nappi_codes')\
            .select('nappi_code', count='exact')\
            .eq('status', 'active')\
            .execute()
        active_count = active_result.count
        
        # By schedule
        schedule_result = supabase.table('nappi_codes')\
            .select('schedule')\
            .eq('status', 'active')\
            .execute()
        
        by_schedule = {}
        for item in schedule_result.data:
            schedule = item.get('schedule', 'Unscheduled')
            by_schedule[schedule] = by_schedule.get(schedule, 0) + 1
        
        return {
            "total_codes": total_count,
            "active_codes": active_count,
            "by_schedule": by_schedule
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching NAPPI stats: {str(e)}")


@router.get("/nappi/search", response_model=NAPPISearchResponse)
async def search_nappi_codes(
    query: str = Query(..., min_length=2, description="Search query (brand name, generic name, or ingredient)"),
    limit: int = Query(20, le=100, description="Maximum number of results"),
    schedule: Optional[str] = Query(None, description="Filter by schedule (S0-S8)"),
    active_only: bool = Query(True, description="Only return active medications")
):
    """
    Search NAPPI codes by brand name, generic name, or ingredients
    
    Examples:
    - /api/nappi/search?query=paracetamol
    - /api/nappi/search?query=panado&schedule=S0
    - /api/nappi/search?query=amoxicillin&limit=10
    """
    try:
        # Build query
        db_query = supabase.table('nappi_codes').select('*')
        
        # Status filter
        if active_only:
            db_query = db_query.eq('status', 'active')
        
        # Schedule filter
        if schedule:
            db_query = db_query.eq('schedule', schedule.upper())
        
        # Text search using OR conditions
        search_term = f"%{query.lower()}%"
        db_query = db_query.or_(
            f"brand_name.ilike.{search_term},"
            f"generic_name.ilike.{search_term},"
            f"ingredients.ilike.{search_term}"
        )
        
        # Limit and execute
        result = db_query.limit(limit).execute()
        
        return {
            "results": result.data,
            "count": len(result.data),
            "query": query
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching NAPPI codes: {str(e)}")


@router.get("/nappi/code/{nappi_code}", response_model=NAPPICode)
async def get_nappi_code(nappi_code: str):
    """Get specific NAPPI code details"""
    try:
        result = supabase.table('nappi_codes')\
            .select('*')\
            .eq('nappi_code', nappi_code)\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail=f"NAPPI code {nappi_code} not found")
        
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching NAPPI code: {str(e)}")


@router.get("/by-generic/{generic_name}", response_model=List[NAPPICode])
async def get_nappi_by_generic(
    generic_name: str,
    limit: int = Query(20, le=100)
):
    """Get all brand name variations for a generic medication"""
    try:
        search_term = f"%{generic_name.lower()}%"
        result = supabase.table('nappi_codes')\
            .select('*')\
            .ilike('generic_name', search_term)\
            .eq('status', 'active')\
            .limit(limit)\
            .execute()
        
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching NAPPI codes by generic: {str(e)}")


@router.get("/by-schedule/{schedule}", response_model=List[NAPPICode])
async def get_nappi_by_schedule(
    schedule: str,
    limit: int = Query(50, le=200)
):
    """Get all medications in a specific schedule"""
    try:
        result = supabase.table('nappi_codes')\
            .select('*')\
            .eq('schedule', schedule.upper())\
            .eq('status', 'active')\
            .limit(limit)\
            .execute()
        
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching NAPPI codes by schedule: {str(e)}")

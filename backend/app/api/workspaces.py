"""
Workspace Management API
Handles workspace CRUD operations and multi-tenant management
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
from supabase import create_client, Client
import os
import logging
import re

from app.api.auth import get_current_user, get_current_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["Workspace Management"])

# Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== Models ====================

class WorkspaceCreate(BaseModel):
    name: str
    organization_name: str
    organization_type: str  # 'gp_practice', 'occupational_health', 'hospital', 'clinic'
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    contact_person: str
    address_line1: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    subscription_tier: str = 'free'  # 'free', 'basic', 'professional', 'enterprise'

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    contact_person: Optional[str] = None
    subscription_tier: Optional[str] = None
    is_active: Optional[bool] = None

class WorkspaceResponse(BaseModel):
    """
    Response shape includes fields that may not exist on rows from the
    minimal `workspaces` schema in setup_supabase.sql (slug,
    organization_name, organization_type, contact_email, contact_person,
    subscription_*, max_*, storage_quota_gb, is_active, is_trial). Those
    are all Optional so the endpoint surfaces existing rows even when
    they haven't been backfilled with the richer schema. The
    Workspace Management UI can edit them in place.
    """
    id: str
    name: str
    slug: Optional[str] = None
    organization_name: Optional[str] = None
    organization_type: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_person: Optional[str] = None
    subscription_tier: Optional[str] = "free"
    subscription_status: Optional[str] = "active"
    max_users: Optional[int] = 10
    max_documents: Optional[int] = 1000
    storage_quota_gb: Optional[int] = 10
    is_active: Optional[bool] = True
    is_trial: Optional[bool] = False
    created_at: Optional[str] = None
    user_count: Optional[int] = 0

# ==================== Helper Functions ====================

def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from workspace name"""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug

# ==================== Routes ====================

@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all workspaces (admin only)
    """
    try:
        # Get all workspaces
        result = supabase.table('workspaces').select('*').execute()
        
        workspaces = []
        for ws in result.data:
            # Get user count for each workspace
            user_count_result = supabase.table('users').select('id', count='exact').eq('workspace_id', ws['id']).execute()
            user_count = user_count_result.count if user_count_result.count else 0
            
            workspaces.append({
                **ws,
                'user_count': user_count
            })
        
        return workspaces
        
    except Exception as e:
        logger.error(f"Error listing workspaces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspaces"
        )

@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get workspace by ID
    Users can view their own workspace, admins can view any workspace
    """
    try:
        # Check permissions
        if current_user.get("workspace_id") != workspace_id and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # Get workspace
        result = supabase.table('workspaces').select('*').eq('id', workspace_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )
        
        workspace = result.data[0]
        
        # Get user count
        user_count_result = supabase.table('users').select('id', count='exact').eq('workspace_id', workspace_id).execute()
        user_count = user_count_result.count if user_count_result.count else 0
        
        return {
            **workspace,
            'user_count': user_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workspace"
        )

@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Create new workspace (admin only)
    """
    try:
        # Generate slug
        slug = generate_slug(workspace_data.name)
        
        # Check if slug already exists
        existing = supabase.table('workspaces').select('slug').eq('slug', slug).execute()
        if existing.data:
            # Add suffix to make unique
            import random
            slug = f"{slug}-{random.randint(1000, 9999)}"
        
        # Generate tenant_id
        import uuid
        tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
        
        # Prepare workspace record
        workspace_record = {
            'name': workspace_data.name,
            'slug': slug,
            'organization_name': workspace_data.organization_name,
            'organization_type': workspace_data.organization_type,
            'contact_email': workspace_data.contact_email,
            'contact_phone': workspace_data.contact_phone,
            'contact_person': workspace_data.contact_person,
            'address_line1': workspace_data.address_line1,
            'city': workspace_data.city,
            'province': workspace_data.province,
            'postal_code': workspace_data.postal_code,
            'country': 'South Africa',
            'subscription_tier': workspace_data.subscription_tier,
            'subscription_status': 'active',
            'billing_email': workspace_data.contact_email,
            'tenant_id': tenant_id,
            'max_users': 10 if workspace_data.subscription_tier == 'free' else 50,
            'max_documents': 1000 if workspace_data.subscription_tier == 'free' else 10000,
            'storage_quota_gb': 10 if workspace_data.subscription_tier == 'free' else 100,
            'is_active': True,
            'is_trial': workspace_data.subscription_tier == 'free',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Insert workspace
        result = supabase.table('workspaces').insert(workspace_record).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create workspace"
            )
        
        workspace = result.data[0]
        
        logger.info(f"Workspace created: {workspace_data.name} by {current_user.get('email')}")
        
        return {
            **workspace,
            'user_count': 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workspace: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace"
        )

@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Update workspace (admin only)
    """
    try:
        # Prepare update data
        update_data = {}
        if workspace_data.name:
            update_data['name'] = workspace_data.name
        if workspace_data.contact_email:
            update_data['contact_email'] = workspace_data.contact_email
        if workspace_data.contact_phone:
            update_data['contact_phone'] = workspace_data.contact_phone
        if workspace_data.contact_person:
            update_data['contact_person'] = workspace_data.contact_person
        if workspace_data.subscription_tier:
            update_data['subscription_tier'] = workspace_data.subscription_tier
        if workspace_data.is_active is not None:
            update_data['is_active'] = workspace_data.is_active
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )
        
        # Update workspace
        result = supabase.table('workspaces').update(update_data).eq('id', workspace_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )
        
        workspace = result.data[0]
        
        # Get user count
        user_count_result = supabase.table('users').select('id', count='exact').eq('workspace_id', workspace_id).execute()
        user_count = user_count_result.count if user_count_result.count else 0
        
        logger.info(f"Workspace updated: {workspace_id} by {current_user.get('email')}")
        
        return {
            **workspace,
            'user_count': user_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace"
        )

@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Delete workspace (admin only)
    Performs soft delete by setting is_active=False
    """
    try:
        # Soft delete
        result = supabase.table('workspaces').update({
            'is_active': False,
            'subscription_status': 'cancelled'
        }).eq('id', workspace_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )
        
        logger.info(f"Workspace deleted: {workspace_id} by {current_user.get('email')}")
        
        return {
            "status": "success",
            "message": f"Workspace {workspace_id} deactivated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workspace: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workspace"
        )

@router.get("/stats/summary")
async def get_workspace_stats(
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Get workspace statistics (admin only)
    """
    try:
        # Get all workspaces
        workspaces = supabase.table('workspaces').select('*').execute()
        
        stats = {
            "total_workspaces": len(workspaces.data),
            "active_workspaces": len([w for w in workspaces.data if w.get('is_active', True)]),
            "trial_workspaces": len([w for w in workspaces.data if w.get('is_trial', False)]),
            "by_subscription": {
                "free": len([w for w in workspaces.data if w.get('subscription_tier') == 'free']),
                "basic": len([w for w in workspaces.data if w.get('subscription_tier') == 'basic']),
                "professional": len([w for w in workspaces.data if w.get('subscription_tier') == 'professional']),
                "enterprise": len([w for w in workspaces.data if w.get('subscription_tier') == 'enterprise']),
            },
            "by_type": {
                "gp_practice": len([w for w in workspaces.data if w.get('organization_type') == 'gp_practice']),
                "occupational_health": len([w for w in workspaces.data if w.get('organization_type') == 'occupational_health']),
                "hospital": len([w for w in workspaces.data if w.get('organization_type') == 'hospital']),
                "clinic": len([w for w in workspaces.data if w.get('organization_type') == 'clinic']),
            }
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting workspace stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workspace stats"
        )

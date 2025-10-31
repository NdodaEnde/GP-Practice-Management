"""
User Management API
Handles user CRUD operations, role management, and workspace assignments
Integrated with Supabase database
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
from supabase import create_client, Client
import os
import logging

# Import auth dependencies
from app.api.auth import get_current_user, get_current_admin_user, get_password_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Management"])

# Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== Models ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: str  # validator, uploader, admin
    workspace_id: Optional[str] = None

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    workspace_id: str
    tenant_id: str
    is_active: bool
    created_at: str
    last_login: Optional[str] = None

# ==================== Routes ====================

@router.get("/", response_model=List[UserResponse])
async def list_users(
    role: Optional[str] = None,
    workspace_id: Optional[str] = None,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all users (admin only)
    Can filter by role and workspace
    """
    try:
        # TODO: Implement database query
        # For now, return demo users
        
        demo_users = [
            {
                "id": "user-admin",
                "email": "admin@surgiscan.com",
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "workspace_id": "demo-gp-workspace-001",
                "tenant_id": "demo-tenant-001",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "user-validator1",
                "email": "validator@surgiscan.com",
                "first_name": "Sarah",
                "last_name": "Smith",
                "role": "validator",
                "workspace_id": "demo-gp-workspace-001",
                "tenant_id": "demo-tenant-001",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "user-uploader1",
                "email": "uploader@surgiscan.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "uploader",
                "workspace_id": "demo-gp-workspace-001",
                "tenant_id": "demo-tenant-001",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": None
            }
        ]
        
        # Apply filters
        if role:
            demo_users = [u for u in demo_users if u["role"] == role]
        
        if workspace_id:
            demo_users = [u for u in demo_users if u["workspace_id"] == workspace_id]
        
        return demo_users
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get user by ID
    Users can view their own profile, admins can view any user
    """
    try:
        # Check permissions
        if current_user.get("user_id") != user_id and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # TODO: Fetch from database
        # For now, return demo data
        
        return {
            "id": user_id,
            "email": f"{user_id}@surgiscan.com",
            "first_name": "Demo",
            "last_name": "User",
            "role": "validator",
            "workspace_id": "demo-gp-workspace-001",
            "tenant_id": "demo-tenant-001",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Create new user (admin only)
    """
    try:
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Use current user's workspace if not specified
        workspace_id = user_data.workspace_id or current_user.get("workspace_id")
        
        # TODO: Save to database
        # For now, return demo response
        
        new_user = {
            "id": f"user-{user_data.email.split('@')[0]}",
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "role": user_data.role,
            "workspace_id": workspace_id,
            "tenant_id": current_user.get("tenant_id"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None
        }
        
        logger.info(f"User created: {user_data.email} by {current_user.get('email')}")
        
        return new_user
        
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Update user (admin only)
    """
    try:
        # TODO: Update in database
        # For now, return updated demo data
        
        updated_user = {
            "id": user_id,
            "email": f"{user_id}@surgiscan.com",
            "first_name": user_data.first_name or "Demo",
            "last_name": user_data.last_name or "User",
            "role": user_data.role or "validator",
            "workspace_id": "demo-gp-workspace-001",
            "tenant_id": "demo-tenant-001",
            "is_active": user_data.is_active if user_data.is_active is not None else True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"User updated: {user_id} by {current_user.get('email')}")
        
        return updated_user
        
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Delete user (admin only)
    Performs soft delete by setting is_active=False
    """
    try:
        # Prevent self-deletion
        if current_user.get("user_id") == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        # TODO: Soft delete in database (set is_active=False)
        
        logger.info(f"User deleted: {user_id} by {current_user.get('email')}")
        
        return {
            "status": "success",
            "message": f"User {user_id} deactivated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

@router.get("/stats/summary")
async def get_user_stats(
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Get user statistics (admin only)
    """
    try:
        # TODO: Calculate from database
        # For now, return demo stats
        
        return {
            "total_users": 3,
            "active_users": 3,
            "inactive_users": 0,
            "by_role": {
                "admin": 1,
                "validator": 1,
                "uploader": 1
            },
            "recent_logins": 2
        }
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user stats"
        )

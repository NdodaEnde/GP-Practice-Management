"""
Authentication API - JWT-based user authentication
Handles login, logout, token refresh, and password management
Now integrated with Supabase database
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from supabase import create_client, Client
import os
import logging

from app.services.entitlements import practice_capabilities, practice_has_capability

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Security configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token security
security = HTTPBearer()

# ==================== Models ====================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: str = "validator"  # validator, uploader, admin

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr

# ==================== Utility Functions ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"Token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== Multi-workspace helpers (TRACEABILITY §11) ====================

def list_user_workspaces(user_id: str) -> list:
    """Return every workspace this user has access to via user_workspaces,
    with role + is_primary + workspace name. Sorted with primary first.

    Two-step lookup (rather than PostgREST embedded select) because we
    haven't declared a FK constraint between user_workspaces.workspace_id
    and workspaces.id — the embedded variant returns only rows where
    PostgREST happens to infer the relationship.

    Empty list ⇒ user is single-workspace (legacy users.workspace_id only)
    or has no workspace at all. Caller should fall back to
    users.workspace_id when this returns empty.
    """
    try:
        rows = (
            supabase.table("user_workspaces")
            .select("workspace_id, role, is_primary")
            .eq("user_id", user_id)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.error(f"list_user_workspaces failed for {user_id}: {e}")
        return []
    if not rows:
        return []

    workspace_ids = list({r["workspace_id"] for r in rows})
    ws_meta: dict = {}
    try:
        meta = (
            supabase.table("workspaces")
            .select("id, name, type, tenant_id")
            .in_("id", workspace_ids)
            .execute()
            .data or []
        )
        ws_meta = {w["id"]: w for w in meta}
    except Exception as e:
        logger.error(f"workspace metadata fetch failed: {e}")

    out = []
    for r in rows:
        ws = ws_meta.get(r["workspace_id"]) or {}
        out.append({
            "workspace_id": r["workspace_id"],
            "name":         ws.get("name") or r["workspace_id"],
            "type":         ws.get("type"),
            "tenant_id":    ws.get("tenant_id"),
            "role":         r.get("role"),
            "is_primary":   bool(r.get("is_primary")),
        })
    out.sort(key=lambda x: (not x["is_primary"], x["name"] or ""))
    return out


def user_has_workspace_access(user_id: str, workspace_id: str) -> bool:
    """True if user_workspaces grants this user access to this workspace."""
    try:
        res = (
            supabase.table("user_workspaces")
            .select("user_id")
            .eq("user_id", user_id)
            .eq("workspace_id", workspace_id)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        logger.error(f"user_has_workspace_access failed: {e}")
        return False

# ==================== Dependencies ====================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Dependency to get current authenticated user from JWT token
    Use this in routes that require authentication
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    # Verify token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    workspace_id = payload.get("workspace_id")

    # Hydrate capabilities for the active workspace (Phase 2 — capability gating).
    # One Supabase RPC per request; acceptable for v1. When scale demands, cache
    # by (workspace_id, last_entitlement_change_at) or embed a capability hash
    # in the JWT itself.
    capabilities = []
    if workspace_id:
        try:
            capabilities = practice_capabilities(supabase, workspace_id)
        except Exception as e:
            # Fail-closed but loud — never silently grant access on entitlement-fetch failure.
            logger.error(f"Failed to fetch capabilities for workspace {workspace_id}: {e}")
            capabilities = []

    # In production, fetch user from database here
    # For now, return payload data
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role"),
        "workspace_id": workspace_id,
        "tenant_id": payload.get("tenant_id"),
        "first_name": payload.get("first_name"),
        "last_name": payload.get("last_name"),
        "capabilities": capabilities,
    }

async def get_current_admin_user(
    current_user: dict = Depends(get_current_user)
):
    """Dependency to verify user is admin"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_capability(capability_id: str):
    """FastAPI dependency factory — gate a route on a single capability.

    Usage:
        @router.post("/encounters/ai-scribe", ...)
        async def create_scribe(
            ...,
            user: dict = Depends(require_capability("ai_scribe")),
        ):
            ...

    Returns 403 with a structured error body that names the missing capability,
    so the frontend can render a tier-specific upsell card naming exactly which
    Module the doctor would buy to unlock it.

    NOTE: relies on get_current_user having hydrated `capabilities` into the
    user dict. Reads the in-memory list rather than re-querying Supabase per
    dependency invocation.
    """
    async def _dep(current_user: dict = Depends(get_current_user)) -> dict:
        granted = current_user.get("capabilities", [])
        if capability_id not in granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "capability_required",
                    "capability": capability_id,
                    "message": f"This feature requires the '{capability_id}' capability. "
                               f"Contact sales@surgiscan.co.za to add the corresponding module to your plan.",
                },
            )
        return current_user
    return _dep

# ==================== Routes ====================

@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """
    Login endpoint - authenticate user and return JWT tokens
    Verifies credentials against Supabase database
    """
    try:
        # Fetch user from database
        result = supabase.table('users').select('*').eq('email', login_data.email).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        user = result.data[0]
        
        # Check if user is active
        if not user.get('is_active', True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated"
            )
        
        # Verify password
        if not verify_password(login_data.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Update last login
        supabase.table('users').update({
            'last_login': datetime.now(timezone.utc).isoformat()
        }).eq('id', user['id']).execute()
        
        # Create user data for JWT
        user_data = {
            "user_id": user['id'],
            "email": user['email'],
            "role": user['role'],
            "workspace_id": user['workspace_id'],
            "tenant_id": user['tenant_id'],
            "first_name": user['first_name'],
            "last_name": user['last_name']
        }
        
        # Create tokens
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)

        # Hydrate capabilities so the frontend can route by entitlement shape
        # immediately on login (Type C lands on /digitisation, not /dashboard).
        try:
            capabilities = practice_capabilities(supabase, user['workspace_id']) if user.get('workspace_id') else []
        except Exception as e:
            logger.error(f"Failed to fetch capabilities for {user.get('workspace_id')}: {e}")
            capabilities = []

        # Workspace name for sidebar subtitle / dashboard greeting.
        workspace_name = None
        try:
            ws = supabase.table('workspaces').select('name').eq('id', user['workspace_id']).execute()
            if ws.data:
                workspace_name = ws.data[0].get('name')
        except Exception as e:
            logger.error(f"Failed to fetch workspace name for {user.get('workspace_id')}: {e}")

        logger.info(f"User logged in: {login_data.email} (role: {user['role']})")

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user={
                "id": user['id'],
                "email": user['email'],
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "role": user['role'],
                "workspace_id": user['workspace_id'],
                "tenant_id": user['tenant_id'],
                "workspace_name": workspace_name,
                "capabilities": capabilities,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/refresh")
async def refresh_token(refresh_data: TokenRefreshRequest):
    """
    Refresh access token using refresh token
    """
    try:
        payload = decode_token(refresh_data.refresh_token)
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Create new access token
        user_data = {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "workspace_id": payload.get("workspace_id"),
            "tenant_id": payload.get("tenant_id")
        }
        
        new_access_token = create_access_token(user_data)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout endpoint
    In JWT, logout is handled client-side by removing tokens
    This endpoint can be used for logging/audit purposes
    """
    logger.info(f"User logged out: {current_user.get('email')}")
    
    return {
        "status": "success",
        "message": "Logged out successfully"
    }

@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information.
    Hydrates workspace_name so the sidebar subtitle / dashboard greeting can
    render after a hard refresh (login response carries it on first load).
    """
    workspace_name = None
    workspace_id = current_user.get("workspace_id")
    if workspace_id:
        try:
            ws = supabase.table('workspaces').select('name').eq('id', workspace_id).execute()
            if ws.data:
                workspace_name = ws.data[0].get('name')
        except Exception as e:
            logger.error(f"Failed to fetch workspace name for {workspace_id}: {e}")

    return {
        "status": "success",
        "user": {**current_user, "workspace_name": workspace_name},
    }


# ==================== Multi-workspace endpoints (TRACEABILITY §11) ====================

@router.get("/workspaces")
async def list_my_workspaces(current_user: dict = Depends(get_current_user)):
    """All workspaces this user has access to via the user_workspaces join.
    The frontend uses this to populate the workspace switcher dropdown.

    Falls back to the legacy single users.workspace_id when user_workspaces
    has no rows for this user (back-compat for users provisioned before
    migration 013, before the migration backfill runs)."""
    user_id = current_user.get("user_id")
    accessible = list_user_workspaces(user_id) if user_id else []

    if not accessible:
        # Legacy fallback: derive from the JWT's workspace_id only
        workspace_id = current_user.get("workspace_id")
        if workspace_id:
            try:
                ws = supabase.table('workspaces').select('id, name, type, tenant_id') \
                    .eq('id', workspace_id).limit(1).execute()
                if ws.data:
                    r = ws.data[0]
                    accessible = [{
                        "workspace_id": r["id"],
                        "name":         r.get("name") or r["id"],
                        "type":         r.get("type"),
                        "tenant_id":    r.get("tenant_id"),
                        "role":         current_user.get("role") or "clinical",
                        "is_primary":   True,
                    }]
            except Exception as e:
                logger.error(f"workspaces fallback fetch failed: {e}")

    return {
        "active_workspace_id": current_user.get("workspace_id"),
        "workspaces":          accessible,
        "count":               len(accessible),
    }


class SwitchWorkspaceRequest(BaseModel):
    workspace_id: str


@router.post("/switch-workspace")
async def switch_workspace(
    body: SwitchWorkspaceRequest,
    current_user: dict = Depends(get_current_user),
):
    """Issue a fresh token bound to a different workspace the user has
    access to. Returns the new access + refresh tokens; capabilities are
    rehydrated for the target workspace.

    Tenancy gate: refuses if user_workspaces has no row for
    (user_id, workspace_id). The legacy single-workspace user with
    no user_workspaces row may still switch INTO their own
    users.workspace_id (so this endpoint is harmless to call even for
    single-workspace users)."""
    user_id      = current_user.get("user_id")
    target_ws_id = body.workspace_id

    if not user_id:
        raise HTTPException(status_code=400, detail="No user context")

    # Authorise: user_workspaces row OR the user's legacy primary workspace.
    has_access = user_has_workspace_access(user_id, target_ws_id)
    if not has_access:
        # Legacy: a user with no user_workspaces rows may still hit
        # their original users.workspace_id.
        try:
            u = supabase.table('users').select('workspace_id').eq('id', user_id).limit(1).execute()
            legacy = u.data[0]["workspace_id"] if u.data else None
        except Exception:
            legacy = None
        if legacy != target_ws_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have access to that workspace",
            )

    # Rehydrate user data for the new token
    try:
        u = supabase.table('users').select('*').eq('id', user_id).limit(1).execute()
        if not u.data:
            raise HTTPException(status_code=404, detail="User not found")
        user = u.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"switch-workspace user fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Could not switch workspace")

    new_user_data = {
        "user_id":      user_id,
        "email":        user["email"],
        "role":         user.get("role"),
        "workspace_id": target_ws_id,
        "tenant_id":    user.get("tenant_id"),
        "first_name":   user.get("first_name"),
        "last_name":    user.get("last_name"),
    }
    access_token  = create_access_token(new_user_data)
    refresh_token = create_refresh_token(new_user_data)

    # Workspace name + capabilities for the new context
    workspace_name = None
    capabilities   = []
    try:
        ws = supabase.table('workspaces').select('name').eq('id', target_ws_id).limit(1).execute()
        if ws.data:
            workspace_name = ws.data[0].get('name')
    except Exception as e:
        logger.error(f"workspace name fetch failed: {e}")
    try:
        capabilities = practice_capabilities(supabase, target_ws_id)
    except Exception as e:
        logger.error(f"capabilities fetch failed for {target_ws_id}: {e}")

    logger.info(f"User {user['email']} switched to workspace {target_ws_id}")

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "user": {
            **new_user_data,
            "workspace_name": workspace_name,
            "capabilities":   capabilities,
        },
    }


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Change user password
    TODO: Implement with database
    """
    # This is a placeholder
    # In production, verify current password and update in database
    
    logger.info(f"Password change requested for: {current_user.get('email')}")
    
    return {
        "status": "success",
        "message": "Password changed successfully (demo mode)"
    }

@router.post("/reset-password")
async def reset_password(reset_data: ResetPasswordRequest):
    """
    Request password reset
    TODO: Implement email sending and reset token generation
    """
    # This is a placeholder
    # In production, generate reset token and send email
    
    logger.info(f"Password reset requested for: {reset_data.email}")
    
    return {
        "status": "success",
        "message": "Password reset instructions sent (demo mode)"
    }

# ==================== Admin Routes ====================

@router.post("/register", response_model=LoginResponse)
async def register_user(
    register_data: RegisterRequest,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Register new user (admin only)
    Creates user in Supabase database
    """
    try:
        # Check if email already exists
        existing = supabase.table('users').select('email').eq('email', register_data.email).execute()
        
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = get_password_hash(register_data.password)
        
        # Prepare user record
        user_record = {
            "email": register_data.email,
            "password_hash": hashed_password,
            "first_name": register_data.first_name,
            "last_name": register_data.last_name,
            "role": register_data.role,
            "workspace_id": current_user.get("workspace_id"),
            "tenant_id": current_user.get("tenant_id"),
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Insert user
        result = supabase.table('users').insert(user_record).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        user = result.data[0]
        
        # Create user data for JWT
        user_data = {
            "user_id": user['id'],
            "email": user['email'],
            "role": user['role'],
            "workspace_id": user['workspace_id'],
            "tenant_id": user['tenant_id'],
            "first_name": user['first_name'],
            "last_name": user['last_name']
        }
        
        # Create tokens for new user
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)
        
        logger.info(f"New user registered: {register_data.email} by {current_user.get('email')}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user={
                "id": user['id'],
                "email": user['email'],
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "role": user['role'],
                "workspace_id": user['workspace_id'],
                "tenant_id": user['tenant_id']
            }
        )
        
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

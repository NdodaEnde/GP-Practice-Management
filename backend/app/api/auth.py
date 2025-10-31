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
    
    # In production, fetch user from database here
    # For now, return payload data
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role"),
        "workspace_id": payload.get("workspace_id"),
        "tenant_id": payload.get("tenant_id")
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
                "tenant_id": user['tenant_id']
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
    Get current authenticated user information
    """
    return {
        "status": "success",
        "user": current_user
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
    TODO: Implement with database
    """
    try:
        # This is a placeholder
        # In production, check if email exists, hash password, save to database
        
        # Hash password
        hashed_password = get_password_hash(register_data.password)
        
        user_data = {
            "user_id": f"user-{register_data.email.split('@')[0]}",
            "email": register_data.email,
            "role": register_data.role,
            "workspace_id": current_user.get("workspace_id"),
            "tenant_id": current_user.get("tenant_id"),
            "first_name": register_data.first_name,
            "last_name": register_data.last_name
        }
        
        # Create tokens for new user
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)
        
        logger.info(f"New user registered: {register_data.email} by {current_user.get('email')}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user={
                "id": user_data["user_id"],
                "email": user_data["email"],
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "role": user_data["role"],
                "workspace_id": user_data["workspace_id"],
                "tenant_id": user_data["tenant_id"]
            }
        )
        
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

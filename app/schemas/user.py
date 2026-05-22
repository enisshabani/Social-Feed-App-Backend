"""
KaPak - User Schemas
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ─── Request Schemas ────────────────────────────────────────

class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    display_name: Optional[str] = Field(None, max_length=100)
    tenant_id: Optional[str] = Field("default", max_length=50)


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=255)


class PasswordChange(BaseModel):
    """Schema for changing password."""
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""
    token: str
    new_password: str = Field(..., min_length=6, max_length=100)

class RefreshTokenRequest(BaseModel):
    """Schema for requesting new access token via refresh token."""
    refresh_token: str

# ─── Response Schemas ───────────────────────────────────────

class UserResponse(BaseModel):
    """Schema for user data in API responses."""
    id: int
    username: str
    email: EmailStr
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    two_factor_enabled: bool = False
    tenant_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserPublicResponse(BaseModel):
    """Public user profile - visible to other users."""
    id: int
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Auth Response Schemas ──────────────────────────────────

class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    is_2fa_temp: Optional[bool] = False

class LoginResponse(BaseModel):
    """Custom response for login that might require 2FA."""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    requires_2fa: bool = False
    temp_token: Optional[str] = None
    trusted_device_token: Optional[str] = None

class TwoFactorVerifyRequest(BaseModel):
    """Schema for verifying a 2FA code."""
    code: str

class TwoFactorLoginRequest(BaseModel):
    """Schema for logging in with a 2FA code and temp token."""
    temp_token: str
    code: str
    remember_device: bool = False

class TwoFactorSetupResponse(BaseModel):
    """Schema for returning 2FA setup details."""
    secret: str
    qr_code_url: str

class TwoFactorEnableResponse(BaseModel):
    """Schema for returning backup codes after enabling 2FA."""
    message: str
    backup_codes: list[str]

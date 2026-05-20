from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel

from app.schemas.common import CamelModel


class UserProfile(CamelModel):
    id: str
    email: str
    nickname: Optional[str] = None
    profile_image_url: Optional[str] = None
    provider: Literal["kakao", "google", "email"]
    created_at: str  # ISO 8601


class UserQuota(CamelModel):
    type: Literal["none", "single", "pass_3month"]
    remaining: int  # -1 = unlimited
    pass_expires_at: Optional[str] = None  # ISO 8601


class KakaoLoginRequest(CamelModel):
    code: str
    redirect_uri: str


class GoogleLoginRequest(CamelModel):
    code: str
    redirect_uri: str


class AuthResponse(CamelModel):
    access_token: str
    refresh_token: str
    user: UserProfile
    is_new_user: bool


class RefreshRequest(CamelModel):
    refresh_token: str


class RefreshResponse(CamelModel):
    access_token: str
    refresh_token: str


class TermsAgreeRequest(CamelModel):
    terms_of_service: bool
    privacy_policy: bool
    marketing: bool = False


class TermsAgreeResponse(CamelModel):
    agreed: bool = True
    agreed_at: str  # ISO 8601


class MeResponse(CamelModel):
    user: UserProfile
    quota: UserQuota


class LogoutResponse(CamelModel):
    success: bool = True

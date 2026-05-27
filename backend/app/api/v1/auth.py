"""
Authentication API endpoints.

POST /auth/kakao          — Kakao OAuth login
POST /auth/google         — Google OAuth login
POST /auth/refresh        — Token refresh (rotation)
POST /auth/agree          — Terms agreement
POST /auth/logout         — Logout (invalidate refresh token)
GET  /auth/me             — Current user profile + quota
POST /auth/dev-login      — 개발용 테스트 로그인 (APP_ENV=development 전용)
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_request_id, DISCLAIMER
from app.core.security import hash_token
from app.models.user import User
from app.schemas.auth import (
    KakaoLoginRequest,
    GoogleLoginRequest,
    AuthResponse,
    RefreshRequest,
    RefreshResponse,
    TermsAgreeRequest,
    TermsAgreeResponse,
    MeResponse,
    LogoutResponse,
)
from app.schemas.common import SuccessResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _error(code: str, message: str, status_code: int, request_id: str):
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {"code": code, "message": message},
            "request_id": request_id,
            "disclaimer": DISCLAIMER,
        },
    )


@router.post("/kakao", response_model=AuthResponse, status_code=200)
async def kakao_login(
    body: KakaoLoginRequest,
    request_id: str = Depends(get_request_id),
    db: AsyncSession = Depends(get_db),
):
    """Kakao OAuth 로그인."""
    if not body.code:
        _error("VALIDATION_ERROR", "code가 누락되었습니다.", 400, request_id)
    try:
        return await auth_service.kakao_login(db, body.code, body.redirect_uri)
    except ValueError as e:
        if "AUTH_PROVIDER_FAILED" in str(e):
            _error("AUTH_PROVIDER_FAILED", "카카오 인증에 실패했습니다.", 401, request_id)
        raise


@router.post("/google", response_model=AuthResponse, status_code=200)
async def google_login(
    body: GoogleLoginRequest,
    request_id: str = Depends(get_request_id),
    db: AsyncSession = Depends(get_db),
):
    """Google OAuth 로그인."""
    if not body.code:
        _error("VALIDATION_ERROR", "code가 누락되었습니다.", 400, request_id)
    try:
        return await auth_service.google_login(db, body.code, body.redirect_uri)
    except ValueError as e:
        if "AUTH_PROVIDER_FAILED" in str(e):
            _error("AUTH_PROVIDER_FAILED", "구글 인증에 실패했습니다.", 401, request_id)
        raise


@router.post("/refresh", response_model=RefreshResponse, status_code=200)
async def refresh_token(
    body: RefreshRequest,
    request_id: str = Depends(get_request_id),
    db: AsyncSession = Depends(get_db),
):
    """토큰 갱신 (refresh token rotation)."""
    try:
        access_tok, refresh_tok = await auth_service.refresh_tokens(db, body.refresh_token)
        return RefreshResponse(access_token=access_tok, refresh_token=refresh_tok)
    except ValueError:
        _error("AUTH_REFRESH_EXPIRED", "리프레시 토큰이 만료되었습니다.", 401, request_id)


@router.post("/agree", response_model=TermsAgreeResponse, status_code=200)
async def agree_terms(
    body: TermsAgreeRequest,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """약관 동의 저장."""
    if not body.terms_of_service or not body.privacy_policy:
        _error("VALIDATION_ERROR", "필수 약관에 동의해야 합니다.", 400, request_id)

    now = datetime.now(timezone.utc)
    current_user.terms_agreed = body.terms_of_service
    current_user.privacy_agreed = body.privacy_policy
    current_user.marketing_agreed = body.marketing
    current_user.agreed_at = now
    await db.flush()

    return TermsAgreeResponse(agreed=True, agreed_at=now.isoformat())


@router.post("/logout", response_model=LogoutResponse, status_code=200)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """로그아웃 — refresh token 무효화."""
    current_user.refresh_token_hash = None
    await db.flush()
    return LogoutResponse(success=True)


@router.get("/me", response_model=MeResponse, status_code=200)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 프로필 및 할당량 조회."""
    from app.services.auth_service import get_user_quota, _user_to_profile

    profile = _user_to_profile(current_user)
    quota = await get_user_quota(db, current_user.id)
    return MeResponse(user=profile, quota=quota)


@router.post("/dev-login", response_model=SuccessResponse[AuthResponse], status_code=200)
async def dev_login(
    request_id: str = Depends(get_request_id),
    db: AsyncSession = Depends(get_db),
):
    """개발/테스트 전용 로그인 — APP_ENV=development 에서만 동작.

    OAuth 없이 즉시 테스트 계정으로 로그인하여 실제 JWT 토큰을 발급한다.
    프로덕션에서는 403 반환.
    """
    if settings.APP_ENV != "development":
        _error("FORBIDDEN", "개발 환경에서만 사용 가능합니다.", 403, request_id)

    DEV_EMAIL = "dev-test@contalktok.kr"
    DEV_NICKNAME = "테스트유저"

    user, is_new = await auth_service._get_or_create_user(
        db,
        email=DEV_EMAIL,
        provider="kakao",   # 스키마 호환: kakao/google/email 만 허용
        provider_id="dev-test-001",
        nickname=DEV_NICKNAME,
    )

    # 테스트 계정은 약관 동의 처리 + 넉넉한 쿼터 부여
    if is_new or not user.terms_agreed:
        user.terms_agreed = True
        user.privacy_agreed = True
        user.marketing_agreed = False
        user.agreed_at = datetime.now(timezone.utc)
        await db.flush()

    # 쿼터 넉넉하게 (단건 99개)
    from app.models.quota import UserQuotaRecord
    from sqlalchemy import select as sa_select
    quota_rec = (await db.execute(
        sa_select(UserQuotaRecord).where(UserQuotaRecord.user_id == user.id)
    )).scalar_one_or_none()
    if quota_rec:
        quota_rec.quota_type = "single"
        quota_rec.remaining = 99
    else:
        db.add(UserQuotaRecord(user_id=user.id, quota_type="single", remaining=99))
    await db.flush()

    access_tok, refresh_tok = auth_service._build_tokens(user)
    user.refresh_token_hash = hash_token(refresh_tok)
    await db.flush()

    profile = auth_service._user_to_profile(user)
    return SuccessResponse(data=AuthResponse(
        access_token=access_tok,
        refresh_token=refresh_tok,
        user=profile,
        is_new_user=False,
    ))

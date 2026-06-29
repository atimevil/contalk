import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.quota import UserQuotaRecord
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    hash_token,
)
from app.schemas.auth import UserProfile, UserQuota, AuthResponse


KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


async def _get_or_create_user(
    db: AsyncSession,
    email: str,
    provider: str,
    provider_id: str,
    nickname: Optional[str] = None,
    profile_image_url: Optional[str] = None,
) -> tuple[User, bool]:
    """Return (user, is_new_user)."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        # Update provider info if needed
        user.nickname = nickname or user.nickname
        user.profile_image_url = profile_image_url or user.profile_image_url
        await db.flush()
        return user, False

    user = User(
        email=email,
        provider=provider,
        provider_id=provider_id,
        nickname=nickname,
        profile_image_url=profile_image_url,
    )
    db.add(user)
    await db.flush()

    # Initialize quota record — 신규 가입 시 무료 체험 1회 부여
    quota = UserQuotaRecord(user_id=user.id, quota_type="free_trial", remaining=1)
    db.add(quota)
    await db.flush()

    return user, True


def _build_tokens(user: User) -> tuple[str, str]:
    data = {"sub": str(user.id)}
    return create_access_token(data), create_refresh_token(data)


def _user_to_profile(user: User) -> UserProfile:
    return UserProfile(
        id=str(user.id),
        email=user.email,
        nickname=user.nickname,
        profile_image_url=user.profile_image_url,
        provider=user.provider,
        created_at=user.created_at.isoformat(),
    )


async def get_user_quota(db: AsyncSession, user_id: uuid.UUID) -> UserQuota:
    result = await db.execute(
        select(UserQuotaRecord).where(UserQuotaRecord.user_id == user_id)
    )
    quota_rec = result.scalar_one_or_none()
    if not quota_rec:
        return UserQuota(type="none", remaining=0)

    # Check pass expiry
    if (
        quota_rec.quota_type.startswith("pass_")
        and quota_rec.pass_expires_at
        and quota_rec.pass_expires_at < datetime.now(timezone.utc)
    ):
        quota_rec.quota_type = "none"
        quota_rec.remaining = 0
        await db.flush()

    return UserQuota(
        type=quota_rec.quota_type,
        remaining=quota_rec.remaining,
        pass_expires_at=quota_rec.pass_expires_at.isoformat() if quota_rec.pass_expires_at else None,
    )


async def kakao_login(
    db: AsyncSession, code: str, redirect_uri: str
) -> AuthResponse:
    from app.core.config import settings

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            KAKAO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.KAKAO_CLIENT_ID,
                "client_secret": settings.KAKAO_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if token_resp.status_code != 200:
            raise ValueError("AUTH_PROVIDER_FAILED")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # Get user info
        user_resp = await client.get(
            KAKAO_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise ValueError("AUTH_PROVIDER_FAILED")

        kakao_data = user_resp.json()
        kakao_account = kakao_data.get("kakao_account", {})
        kakao_profile = kakao_account.get("profile", {})

        email = kakao_account.get("email", f"kakao_{kakao_data['id']}@kakao.local")
        nickname = kakao_profile.get("nickname")
        profile_img = kakao_profile.get("profile_image_url")
        provider_id = str(kakao_data["id"])

    user, is_new = await _get_or_create_user(
        db, email, "kakao", provider_id, nickname, profile_img
    )
    access_tok, refresh_tok = _build_tokens(user)
    user.refresh_token_hash = hash_token(refresh_tok)
    await db.flush()

    return AuthResponse(
        access_token=access_tok,
        refresh_token=refresh_tok,
        user=_user_to_profile(user),
        is_new_user=is_new,
    )


async def google_login(
    db: AsyncSession, code: str, redirect_uri: str
) -> AuthResponse:
    from app.core.config import settings

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if token_resp.status_code != 200:
            raise ValueError("AUTH_PROVIDER_FAILED")

        google_token = token_resp.json().get("access_token")

        user_resp = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {google_token}"},
        )
        if user_resp.status_code != 200:
            raise ValueError("AUTH_PROVIDER_FAILED")

        g_data = user_resp.json()
        email = g_data.get("email", "")
        nickname = g_data.get("name")
        profile_img = g_data.get("picture")
        provider_id = g_data.get("id", "")

    user, is_new = await _get_or_create_user(
        db, email, "google", provider_id, nickname, profile_img
    )
    access_tok, refresh_tok = _build_tokens(user)
    user.refresh_token_hash = hash_token(refresh_tok)
    await db.flush()

    return AuthResponse(
        access_token=access_tok,
        refresh_token=refresh_tok,
        user=_user_to_profile(user),
        is_new_user=is_new,
    )


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    from app.core.security import decode_token
    from jose import JWTError

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("AUTH_REFRESH_EXPIRED")
        user_id = payload.get("sub")
    except JWTError:
        raise ValueError("AUTH_REFRESH_EXPIRED")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("AUTH_REFRESH_EXPIRED")

    # Rotate tokens
    access_tok, new_refresh_tok = _build_tokens(user)
    user.refresh_token_hash = get_password_hash(new_refresh_tok)
    await db.flush()

    return access_tok, new_refresh_tok

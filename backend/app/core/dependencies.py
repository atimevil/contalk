import uuid
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

DISCLAIMER = "본 분석은 법률 조언이 아닌 정보 제공 서비스입니다."


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "success": False,
            "error": {
                "code": "AUTH_TOKEN_INVALID",
                "message": "인증 토큰이 유효하지 않습니다.",
            },
        },
    )
    expired_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "success": False,
            "error": {
                "code": "AUTH_TOKEN_EXPIRED",
                "message": "인증 토큰이 만료되었습니다.",
            },
        },
    )

    if not credentials:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as e:
        if "expired" in str(e).lower():
            raise expired_exception
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


def get_request_id(x_request_id: Optional[str] = Header(default=None)) -> str:
    return x_request_id or str(uuid.uuid4())

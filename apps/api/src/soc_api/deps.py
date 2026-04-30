"""FastAPI dependency resolvers for authentication."""
from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.config import settings
from soc_api.db import get_session
from soc_api.models.orm import ApiKey, User
from soc_api.security import verify_api_key

try:
    import jwt
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False

_UNAUTH = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def current_api_key(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ApiKey:
    """Resolve Bearer API key to an active ApiKey row. Raises 401 if missing or invalid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise _UNAUTH
    raw_key = authorization.removeprefix("Bearer ")

    result = await session.execute(select(ApiKey).where(ApiKey.revoked_at.is_(None)))
    for key in result.scalars():
        if verify_api_key(key.key_hash, raw_key):
            return key

    raise _UNAUTH


async def current_user(
    session_token: str | None = Cookie(default=None, alias="next-auth.session-token"),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Cookie-first (NextAuth JWT), Bearer fallback. Raises 401 if neither resolves."""
    if not _JWT_AVAILABLE:
        raise HTTPException(status_code=500, detail="JWT library not installed")

    user_id: str | None = None

    # Try NextAuth session cookie first
    if session_token and not user_id:
        try:
            payload = jwt.decode(
                session_token,
                settings.nextauth_secret,
                algorithms=["HS256"],
            )
            user_id = payload.get("sub")
        except jwt.PyJWTError:
            pass

    # Fall back to Bearer JWT
    if not user_id and authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        try:
            payload = jwt.decode(
                token,
                settings.nextauth_secret,
                algorithms=["HS256"],
            )
            user_id = payload.get("sub")
        except jwt.PyJWTError:
            pass

    if not user_id:
        raise _UNAUTH

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise _UNAUTH

    return user

"""Dependency FastAPI: sesi database, autentikasi, dan otorisasi role."""

from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.models import User
from lan_server.database import SessionLocal
from lan_server.security import TokenError, decode_access_token


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization wajib dikirim.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format Authorization harus 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1].strip()


def get_token_payload(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer(authorization)
    try:
        return decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> User:
    user_id = payload.get("sub")
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak memuat identitas pengguna yang sah.",
        ) from exc

    user = db.get(User, user_id_int)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pengguna tidak aktif atau tidak ditemukan.",
        )
    return user


def require_roles(*role_names: str):
    """Batasi endpoint ke role tertentu. OWNER selalu diizinkan."""
    allowed = {name.upper() for name in role_names} | {"OWNER"}

    def _dependency(user: User = Depends(get_current_user)) -> User:
        role = (user.role.name if user.role else "").upper()
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {role or 'tidak dikenal'} tidak berhak mengakses endpoint ini.",
            )
        return user

    return _dependency


__all__ = [
    "get_current_user",
    "get_db",
    "get_token_payload",
    "require_roles",
]

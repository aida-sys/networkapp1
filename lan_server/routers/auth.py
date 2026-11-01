"""Router autentikasi POS LAN."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, PasswordChangeRequired
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from lan_server.config import settings
from lan_server.deps import get_current_user, get_db, get_token_payload
from lan_server.schemas import LoginRequest, LoginResponse, MeResponse, UserOut
from lan_server.security import create_access_token
from lan_server.serializers import resolve_store

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role.name if user.role else "",
        is_active=user.is_active,
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Login memakai AuthService desktop: lockout dan audit login ikut berlaku."""
    service = AuthService(UserRepository(db))
    try:
        user = service.login(payload.username, payload.password)
    except PasswordChangeRequired as exc:
        # Password sementara: tetap tolak, klien harus minta ganti password.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password harus diganti sebelum dapat menggunakan aplikasi.",
        ) from exc
    except AuthenticationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    db.commit()
    db.refresh(user)

    store = resolve_store(db)
    role_name = user.role.name if user.role else ""
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=role_name,
        store_id=store.id if store else None,
        device_id=payload.device_id,
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.token_ttl_minutes * 60,
        user=_user_out(user),
        store_id=store.id if store else None,
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    payload: dict = Depends(get_token_payload),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Terbitkan token baru dari token yang masih sah."""
    store = resolve_store(db)
    role_name = user.role.name if user.role else ""
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=role_name,
        store_id=store.id if store else None,
        device_id=payload.get("device_id"),
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.token_ttl_minutes * 60,
        user=_user_out(user),
        store_id=store.id if store else None,
    )


@router.get("/me", response_model=MeResponse)
def me(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    store = resolve_store(db)
    return MeResponse(
        user=_user_out(user),
        store_id=store.id if store else None,
        store_name=store.name if store else None,
    )

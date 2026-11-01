"""Router shift kasir."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import POSException
from app.models import Shift
from app.repositories.shift_repository import ShiftRepository
from app.services.shift_service import ShiftService
from lan_server.deps import get_current_user, get_db
from lan_server.schemas import ShiftCloseRequest, ShiftOpenRequest, ShiftOut
from lan_server.serializers import utcnow

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.get("/current", response_model=ShiftOut | None)
def current_shift(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShiftOut | None:
    shift = ShiftRepository(db).get_open_for_cashier(user.id)
    if shift is None:
        return None
    return ShiftOut.model_validate(shift)


@router.post("/open", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def open_shift(
    payload: ShiftOpenRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShiftOut:
    service = ShiftService(db, ShiftRepository(db))
    try:
        shift = service.open_shift(user, payload.opening_cash)
    except POSException as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return ShiftOut.model_validate(shift)


@router.post("/close", response_model=ShiftOut)
def close_shift(
    payload: ShiftCloseRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShiftOut:
    shift = ShiftRepository(db).get_open_for_cashier(user.id)
    if shift is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tidak ada shift terbuka untuk pengguna ini.",
        )
    shift.closing_cash = payload.closing_cash
    shift.closed_at = utcnow()
    shift.status = "CLOSED"
    try:
        db.commit()
        db.refresh(shift)
    except Exception:
        db.rollback()
        raise
    return ShiftOut.model_validate(shift)


@router.get("", response_model=list[ShiftOut])
def list_shifts(
    limit: int = 50,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShiftOut]:
    role = (user.role.name if user.role else "").upper()
    statement = select(Shift).order_by(Shift.opened_at.desc(), Shift.id.desc())
    if role == "CASHIER":
        statement = statement.where(Shift.cashier_id == user.id)
    statement = statement.limit(max(1, min(limit, 200)))
    return [ShiftOut.model_validate(row) for row in db.scalars(statement)]

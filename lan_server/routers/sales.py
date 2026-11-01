"""Router penjualan POS LAN.

Aturan bisnis TIDAK disalin di sini. Semua validasi harga, stok, shift, dan
pembayaran dijalankan oleh `app.services.sales_service.SalesService` yang sama
dengan aplikasi desktop. Router hanya menangani HTTP, idempotency, dan DTO.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InsufficientStockError,
    PaymentIncompleteError,
    POSException,
    ShiftNotOpenError,
    ValidationError,
)
from app.models import Sale, Shift
from app.services.sales_service import SalesService
from lan_server.deps import get_current_user, get_db, require_roles
from lan_server.idempotency import (
    IdempotencyConflict,
    IdempotencyReplay,
    abandon,
    begin,
    complete,
)
from lan_server.schemas import CheckoutRequest, RefundRequest, SaleOut
from lan_server.serializers import serialize_sale


router = APIRouter(prefix="/sales", tags=["sales"])


def _map_service_error(exc: Exception) -> HTTPException:
    """Petakan exception domain ke status HTTP yang bisa ditindaklanjuti klien."""
    if isinstance(exc, InsufficientStockError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ShiftNotOpenError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, PaymentIncompleteError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, (ValidationError, ValueError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, POSException):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Terjadi kesalahan pada server saat memproses transaksi.",
    )


def _active_shift(db: Session, cashier_id: int) -> Shift | None:
    return db.scalar(
        select(Shift)
        .where(
            Shift.cashier_id == cashier_id,
            Shift.status == "OPEN",
            Shift.closed_at.is_(None),
        )
        .order_by(Shift.opened_at.desc(), Shift.id.desc())
    )


@router.post("/checkout", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SaleOut:
    """Simpan transaksi secara atomik.

    Server menentukan harga satuan, diskon baris, dan grand total. Klien hanya
    mengirim produk, qty, dan pembayaran. Retry dengan Idempotency-Key yang
    sama tidak membuat transaksi kedua.
    """
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header Idempotency-Key wajib dikirim untuk operasi checkout.",
        )

    shift = _active_shift(db, user.id)
    if shift is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Buka shift sebelum menyelesaikan penjualan.",
        )

    request_payload = payload.model_dump(mode="json")
    try:
        record = begin(
            db,
            key=idempotency_key,
            endpoint="POST /api/v1/sales/checkout",
            request_payload={"user_id": user.id, **request_payload},
        )
    except IdempotencyReplay as replay:
        db.rollback()
        # Kembalikan status asli yang tersimpan (201), bukan 200, supaya klien
        # melihat hasil yang identik dengan permintaan pertama.
        return JSONResponse(
            status_code=replay.status_code, content=jsonable_encoder(replay.body)
        )
    except IdempotencyConflict as conflict:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(conflict)
        ) from conflict

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    service = SalesService(db)
    try:
        sale = service.create_and_checkout(
            cashier_id=user.id,
            shift_id=shift.id,
            items=[item.model_dump() for item in payload.items],
            payments=[payment.model_dump() for payment in payload.payments],
            customer_id=payload.customer_id,
            discount=payload.discount,
            tax=payload.tax,
        )
    except Exception as exc:
        db.rollback()
        # Operasi gagal: hapus catatan idempotency agar klien bisa mencoba lagi
        # dengan key yang sama tanpa dianggap konflik.
        try:
            stale = db.scalar(
                select(type(record)).where(
                    type(record).idempotency_key == idempotency_key
                )
            )
            if stale is not None:
                abandon(db, stale)
                db.commit()
        except Exception:
            db.rollback()
        raise _map_service_error(exc) from exc

    result = serialize_sale(db, sale)
    body = result.model_dump(mode="json")
    try:
        stored = db.scalar(
            select(type(record)).where(type(record).idempotency_key == idempotency_key)
        )
        if stored is not None:
            complete(db, stored, status_code=201, body=body)
            db.commit()
    except Exception:
        db.rollback()

    return result


@router.get("", response_model=list[SaleOut])
def list_sales(
    on_date: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=100, ge=1, le=500),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SaleOut]:
    target = on_date or date.today()
    local_start = datetime.combine(target, time.min).astimezone(timezone.utc)
    local_end = datetime.combine(
        target + timedelta(days=1), time.min
    ).astimezone(timezone.utc)
    statement = (
        select(Sale)
        .where(
            Sale.created_at >= local_start.replace(tzinfo=None),
            Sale.created_at < local_end.replace(tzinfo=None),
        )
        .order_by(Sale.created_at.desc(), Sale.id.desc())
        .limit(limit)
    )
    if (user.role.name if user.role else "") == "CASHIER":
        statement = statement.where(Sale.cashier_id == user.id)
    return [serialize_sale(db, sale) for sale in db.scalars(statement)]


@router.get("/{sale_id}", response_model=SaleOut)
def get_sale(
    sale_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SaleOut:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaksi tidak ditemukan."
        )
    if (user.role.name if user.role else "") == "CASHIER" and sale.cashier_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kasir hanya dapat melihat transaksinya sendiri.",
        )
    return serialize_sale(db, sale)


@router.post("/{sale_id}/refund", response_model=SaleOut)
def refund_sale(
    sale_id: int,
    payload: RefundRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> SaleOut:
    """Refund mengembalikan stok dan mencatat audit log."""
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header Idempotency-Key wajib dikirim untuk operasi refund.",
        )
    try:
        begin(
            db,
            key=idempotency_key,
            endpoint=f"POST /api/v1/sales/{sale_id}/refund",
            request_payload={"sale_id": sale_id, "reason": payload.reason},
        )
        db.commit()
    except IdempotencyReplay as replay:
        db.rollback()
        return JSONResponse(
            status_code=replay.status_code, content=jsonable_encoder(replay.body)
        )
    except IdempotencyConflict as conflict:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(conflict)
        ) from conflict

    service = SalesService(db)
    try:
        sale = service.refund_sale(sale_id, payload.reason)
    except Exception as exc:
        db.rollback()
        raise _map_service_error(exc) from exc

    result = serialize_sale(db, sale)
    return result

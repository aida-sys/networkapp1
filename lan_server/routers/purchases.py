"""Router pembelian.

`PurchaseService.record_purchase()` di desktop langsung menerima barang
(status RECEIVED, stok bertambah, jurnal diposting) dalam satu transaksi.
API mengikuti perilaku yang sama supaya tidak ada dua arti "pembelian".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import POSException
from app.services.purchase_service import PurchaseService
from lan_server.deps import get_db, require_roles
from lan_server.idempotency import (
    ApiIdempotency,
    IdempotencyConflict,
    IdempotencyReplay,
    begin,
    complete,
)
from lan_server.schemas import PurchaseCreate, PurchaseOut

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get("", response_model=list[dict])
def list_purchases(
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> list[dict]:
    service = PurchaseService(db)
    rows = service.list_purchases(user)
    result = []
    for row in rows:
        purchase = row["purchase"]
        result.append(
            {
                "id": purchase.id,
                "order_no": purchase.order_no,
                "supplier_name": row.get("supplier_name"),
                "product_name": row.get("product_name"),
                "qty": row.get("qty"),
                "subtotal": purchase.subtotal,
                "status": purchase.status,
                "payment_status": purchase.payment_status,
                "paid_amount": purchase.paid_amount,
                "ordered_at": purchase.ordered_at,
                "due_date": purchase.due_date,
                "notes": purchase.notes,
            }
        )
    return result


@router.post("", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    payload: PurchaseCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> PurchaseOut:
    """Catat pembelian sekaligus penerimaan barang.

    Idempotency-Key mencegah pembelian dan penambahan stok ganda saat retry.
    """
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header Idempotency-Key wajib dikirim untuk pencatatan pembelian.",
        )

    request_payload = payload.model_dump(mode="json")
    try:
        begin(
            db,
            key=idempotency_key,
            endpoint="POST /api/v1/purchases",
            request_payload=request_payload,
        )
        db.commit()
    except IdempotencyReplay as replay:
        db.rollback()
        return replay.body
    except IdempotencyConflict as conflict:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(conflict)
        ) from conflict

    service = PurchaseService(db)
    try:
        purchase = service.record_purchase(
            user,
            supplier_id=payload.supplier_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            unit_cost=payload.unit_cost,
            payment_status=payload.payment_status,
            due_date=payload.due_date,
            payment_account_id=payload.payment_account_id,
            dp_amount=payload.dp_amount,
        )
    except POSException as exc:
        db.rollback()
        _abandon(db, idempotency_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    result = PurchaseOut.model_validate(purchase)
    _complete(db, idempotency_key, 201, result.model_dump(mode="json"))
    return result


def _abandon(db: Session, key: str) -> None:
    """Buang catatan idempotency agar klien bisa retry dengan key yang sama."""
    try:
        stale = db.scalar(
            select(ApiIdempotency).where(ApiIdempotency.idempotency_key == key)
        )
        if stale is not None:
            db.delete(stale)
            db.commit()
    except Exception:
        db.rollback()


def _complete(db: Session, key: str, status_code: int, body: dict) -> None:
    try:
        stored = db.scalar(
            select(ApiIdempotency).where(ApiIdempotency.idempotency_key == key)
        )
        if stored is not None:
            complete(db, stored, status_code=status_code, body=body)
            db.commit()
    except Exception:
        db.rollback()

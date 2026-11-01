"""Router laporan dan pengaturan toko."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.exceptions import POSException
from app.services.report_service import ReportService
from app.services.store_settings_service import StoreSettingsService
from lan_server.deps import get_current_user, get_db, require_roles
from lan_server.schemas import DailyReportOut, RangeReportOut, StoreOut, StoreUpdate
from lan_server.serializers import resolve_store

reports_router = APIRouter(prefix="/reports", tags=["reports"])
settings_router = APIRouter(prefix="/settings", tags=["settings"])


def _period_bounds(
    start: date | None, end: date | None
) -> tuple[datetime, datetime]:
    """Ubah rentang tanggal lokal menjadi batas UTC-naive seperti desktop."""
    first = start or date.today()
    last = end or first
    if last < first:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tanggal akhir tidak boleh sebelum tanggal mulai.",
        )
    local_start = datetime.combine(first, time.min).astimezone(timezone.utc)
    local_end = datetime.combine(
        last + timedelta(days=1), time.min
    ).astimezone(timezone.utc)
    return local_start.replace(tzinfo=None), local_end.replace(tzinfo=None)


@reports_router.get("/daily", response_model=DailyReportOut)
def daily_report(
    on_date: date | None = Query(default=None, alias="date"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyReportOut:
    target = on_date or date.today()
    start, end = _period_bounds(target, target)
    service = ReportService(db)

    role = (user.role.name if user.role else "").upper()
    cashier_id = user.id if role == "CASHIER" else None
    sales = service.sales(start, end, cashier_id)
    profits = service.profits(start, end)

    breakdown: dict[str, dict] = {}
    for row in sales:
        name = row.get("cashier_name") or "-"
        bucket = breakdown.setdefault(name, {"cashier_name": name, "count": 0, "total": 0})
        bucket["count"] += 1
        bucket["total"] += int(row.get("revenue") or 0)

    return DailyReportOut(
        date=target,
        sales_count=len(sales),
        sales_total=sum(int(row.get("revenue") or 0) for row in sales),
        profit_total=sum(int(row.get("profit") or 0) for row in profits),
        cashier_breakdown=sorted(
            breakdown.values(), key=lambda item: item["total"], reverse=True
        ),
    )


@reports_router.get("/range", response_model=RangeReportOut)
def range_report(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RangeReportOut:
    first = start or date.today()
    last = end or first
    start_dt, end_dt = _period_bounds(first, last)
    service = ReportService(db)

    role = (user.role.name if user.role else "").upper()
    cashier_id = user.id if role == "CASHIER" else None
    sales = service.sales(start_dt, end_dt, cashier_id)
    profits = service.profits(start_dt, end_dt)

    rows = [
        {
            "invoice_no": row.get("invoice_no"),
            "created_at": row.get("created_at"),
            "cashier_name": row.get("cashier_name"),
            "revenue": row.get("revenue"),
            "items": row.get("items", []),
        }
        for row in sales
    ]
    return RangeReportOut(
        start=start_dt,
        end=end_dt,
        sales_count=len(sales),
        sales_total=sum(int(row.get("revenue") or 0) for row in sales),
        profit_total=sum(int(row.get("profit") or 0) for row in profits),
        rows=rows,
    )


@reports_router.get("/low-stock", response_model=list[dict])
def low_stock(
    threshold: int = Query(default=5, ge=0),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    service = ReportService(db)
    return [
        {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "stock_qty": product.stock_qty,
            "min_stock": product.min_stock,
        }
        for product in service.low_stock_products(threshold)
    ]


@settings_router.get("/store", response_model=StoreOut | None)
def get_store(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoreOut | None:
    store = resolve_store(db)
    if store is None:
        return None
    return StoreOut.model_validate(store)


@settings_router.put("/store", response_model=StoreOut)
def update_store(
    payload: StoreUpdate,
    user=Depends(require_roles("ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
) -> StoreOut:
    service = StoreSettingsService(db)
    try:
        store = service.save(
            user,
            name=payload.name,
            address=payload.address,
            whatsapp=payload.whatsapp,
            slogan=payload.slogan,
            logo_source=None,
        )
    except POSException as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return StoreOut.model_validate(store)

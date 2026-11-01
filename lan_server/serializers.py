"""Helper serialisasi bersama untuk router POS LAN."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Payment, Product, Sale, SaleItem, Store
from lan_server.schemas import (
    PaymentOut,
    ProductOut,
    SaleItemOut,
    SaleOut,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resolve_store(session: Session) -> Store | None:
    """Toko aktif. Aplikasi ini single-store, jadi ambil yang pertama."""
    return session.scalar(
        select(Store).where(Store.deleted_at.is_(None)).order_by(Store.id)
    )


def serialize_product(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        sku=product.sku,
        barcode=product.barcode,
        name=product.name,
        category_id=product.category_id,
        category_name=product.category.name if product.category else None,
        unit_id=product.unit_id,
        supplier_id=product.supplier_id,
        purchase_price=product.purchase_price,
        selling_price=product.selling_price,
        stock_qty=product.stock_qty,
        min_stock=product.min_stock,
        is_active=product.is_active,
    )


def serialize_sale(session: Session, sale: Sale) -> SaleOut:
    items = list(
        session.scalars(
            select(SaleItem).where(SaleItem.sale_id == sale.id).order_by(SaleItem.id)
        )
    )
    payments = list(
        session.scalars(
            select(Payment).where(Payment.sale_id == sale.id).order_by(Payment.id)
        )
    )
    return SaleOut(
        id=sale.id,
        invoice_no=sale.invoice_no,
        store_id=sale.store_id,
        shift_id=sale.shift_id,
        cashier_id=sale.cashier_id,
        customer_id=sale.customer_id,
        subtotal=sale.subtotal,
        discount=sale.discount,
        tax=sale.tax,
        grand_total=sale.grand_total,
        status=sale.status,
        created_at=sale.created_at,
        items=[
            SaleItemOut(
                id=item.id,
                product_id=item.product_id,
                qty=item.qty,
                unit_price=item.unit_price,
                discount=item.discount,
                line_total=item.line_total,
            )
            for item in items
        ],
        payments=[
            PaymentOut(
                id=payment.id,
                method=payment.method,
                amount=payment.amount,
                reference=payment.reference,
            )
            for payment in payments
        ],
    )


__all__ = ["resolve_store", "serialize_product", "serialize_sale", "utcnow"]

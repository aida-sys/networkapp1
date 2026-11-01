"""DTO/API contract POS LAN API, versi 1.

Kontrak ini eksplisit dan dipisah dari model SQLAlchemy supaya perubahan
internal tidak langsung memutus klien Android/web.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Auth -----------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)
    device_id: str | None = Field(default=None, max_length=120)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    store_id: int | None = None


class MeResponse(BaseModel):
    user: UserOut
    store_id: int | None = None
    store_name: str | None = None


# --- Katalog --------------------------------------------------------------


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    symbol: str | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class UnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    symbol: str | None = Field(default=None, max_length=20)


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    phone: str | None = None
    address: str | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    barcode: str | None = None
    name: str
    category_id: int | None = None
    category_name: str | None = None
    unit_id: int | None = None
    supplier_id: int | None = None
    purchase_price: int
    selling_price: int
    stock_qty: int
    min_stock: int
    is_active: bool


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    barcode: str = ""
    name: str = Field(min_length=1, max_length=200)
    # Opsional: bila kosong, server memakai (atau membuat) kategori "Umum"
    # dan satuan "Pcs" supaya instalasi LAN baru bisa langsung berjualan.
    category_id: int | None = None
    unit_id: int | None = None
    purchase_price: int = Field(ge=0)
    selling_price: int = Field(ge=0)
    stock_qty: int = Field(default=0, ge=0)
    min_stock: int = Field(default=0, ge=0)
    is_active: bool = True
    supplier_id: int | None = None


class ProductUpdate(ProductCreate):
    product_id: int


class StockAdjustRequest(BaseModel):
    product_id: int
    quantity: int = Field(description="Positif menambah, negatif mengurangi.")


# --- Shift ----------------------------------------------------------------


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    cashier_id: int
    opened_at: datetime
    closed_at: datetime | None = None
    opening_cash: int
    closing_cash: int | None = None
    status: str


class ShiftOpenRequest(BaseModel):
    opening_cash: int = Field(ge=0)


class ShiftCloseRequest(BaseModel):
    closing_cash: int = Field(ge=0)


# --- Penjualan ------------------------------------------------------------


class CheckoutItem(BaseModel):
    product_id: int
    qty: int = Field(gt=0)
    discount: int = Field(default=0, ge=0)


class CheckoutPayment(BaseModel):
    method: str = Field(min_length=1, max_length=40)
    amount: int = Field(ge=0)
    reference: str | None = Field(default=None, max_length=120)


class CheckoutRequest(BaseModel):
    """Klien TIDAK mengirim harga atau total.

    Server menghitung harga satuan, diskon, dan total dari database. Ini yang
    membuat klien tidak bisa menjadi sumber kebenaran stok/harga.
    """

    items: list[CheckoutItem] = Field(min_length=1)
    payments: list[CheckoutPayment] = Field(min_length=1)
    customer_id: int | None = None
    discount: int = Field(default=0, ge=0)
    tax: int = Field(default=0, ge=0)


class SaleItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    qty: int
    unit_price: int
    discount: int
    line_total: int


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    method: str
    amount: int
    reference: str | None = None


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_no: str
    store_id: int
    shift_id: int
    cashier_id: int
    customer_id: int | None = None
    subtotal: int
    discount: int
    tax: int
    grand_total: int
    status: str
    created_at: datetime
    items: list[SaleItemOut] = []
    payments: list[PaymentOut] = []


class RefundRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


# --- Pembelian ------------------------------------------------------------


class PurchaseCreate(BaseModel):
    supplier_id: int
    product_id: int
    quantity: int = Field(gt=0)
    unit_cost: int = Field(gt=0)
    payment_status: Literal["PAID", "TEMPO", "DP"] = "TEMPO"
    due_date: date | None = None
    payment_account_id: int | None = None
    dp_amount: int = Field(default=0, ge=0)


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    supplier_id: int
    status: str
    subtotal: int
    payment_status: str
    paid_amount: int
    ordered_at: datetime | None = None
    due_date: date | None = None
    notes: str | None = None


# --- Laporan --------------------------------------------------------------


class DailyReportOut(BaseModel):
    date: date
    sales_count: int
    sales_total: int
    profit_total: int
    cashier_breakdown: list[dict[str, Any]] = []


class RangeReportOut(BaseModel):
    start: datetime
    end: datetime
    sales_count: int
    sales_total: int
    profit_total: int
    rows: list[dict[str, Any]] = []


# --- Pengaturan toko ------------------------------------------------------


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    slogan: str | None = None
    address: str | None = None
    whatsapp: str | None = None
    logo_path: str | None = None


class StoreUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str = ""
    whatsapp: str = ""
    slogan: str = ""


# --- Health ---------------------------------------------------------------


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    database: str
    server_time: datetime


__all__ = [name for name in dir() if name.endswith(("Out", "Request", "Create", "Update", "Response", "Item", "Payment"))]

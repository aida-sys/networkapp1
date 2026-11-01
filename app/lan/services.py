"""Adapter service untuk mode LAN.

Setiap kelas di sini meniru signature service lokal yang dipakai UI, tetapi
mengambil data dari POS LAN API. UI tidak tahu (dan tidak perlu tahu) mana
yang sedang dipakai.

Yang dikembalikan adalah objek ringan (bukan instance SQLAlchemy), karena
tidak ada Session lokal di mode LAN. View sudah diubah agar hanya memakai
atribut yang memang tersedia di kedua jalur.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.lan.client import LanClient


def new_idempotency_key() -> str:
    """Key unik per operasi tulis. Retry memakai key yang sama."""
    return uuid.uuid4().hex


# --- Objek data ringan ----------------------------------------------------


@dataclass
class LanProduct:
    id: int
    sku: str
    name: str
    selling_price: int
    purchase_price: int
    stock_qty: int
    min_stock: int
    is_active: bool
    barcode: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    supplier_id: int | None = None
    unit_id: int | None = None

    @classmethod
    def from_payload(cls, payload: dict) -> "LanProduct":
        return cls(
            id=payload["id"],
            sku=payload.get("sku", ""),
            name=payload.get("name", ""),
            selling_price=int(payload.get("selling_price") or 0),
            purchase_price=int(payload.get("purchase_price") or 0),
            stock_qty=int(payload.get("stock_qty") or 0),
            min_stock=int(payload.get("min_stock") or 0),
            is_active=bool(payload.get("is_active", True)),
            barcode=payload.get("barcode"),
            category_id=payload.get("category_id"),
            category_name=payload.get("category_name"),
            supplier_id=payload.get("supplier_id"),
            unit_id=payload.get("unit_id"),
        )


@dataclass
class LanSaleItem:
    product_id: int
    qty: int
    unit_price: int
    discount: int
    line_total: int


@dataclass
class LanSale:
    id: int
    invoice_no: str
    store_id: int
    shift_id: int
    cashier_id: int
    subtotal: int
    discount: int
    tax: int
    grand_total: int
    status: str
    created_at: datetime
    items: list[LanSaleItem] = field(default_factory=list)
    cashier_name: str | None = None
    customer_id: int | None = None

    @classmethod
    def from_payload(cls, payload: dict) -> "LanSale":
        created = payload.get("created_at")
        return cls(
            id=payload["id"],
            invoice_no=payload.get("invoice_no", ""),
            store_id=payload.get("store_id", 0),
            shift_id=payload.get("shift_id", 0),
            cashier_id=payload.get("cashier_id", 0),
            subtotal=int(payload.get("subtotal") or 0),
            discount=int(payload.get("discount") or 0),
            tax=int(payload.get("tax") or 0),
            grand_total=int(payload.get("grand_total") or 0),
            status=payload.get("status", "PAID"),
            created_at=(
                datetime.fromisoformat(created) if isinstance(created, str) else datetime.now()
            ),
            items=[
                LanSaleItem(
                    product_id=item["product_id"],
                    qty=item["qty"],
                    unit_price=item["unit_price"],
                    discount=item.get("discount", 0),
                    line_total=item.get("line_total", 0),
                )
                for item in payload.get("items", [])
            ],
            customer_id=payload.get("customer_id"),
        )


@dataclass
class LanShift:
    id: int
    store_id: int
    cashier_id: int
    opening_cash: int
    status: str
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    closing_cash: int | None = None


@dataclass
class LanStore:
    id: int
    code: str
    name: str
    slogan: str | None = None
    address: str | None = None
    whatsapp: str | None = None
    logo_path: str | None = None


# --- Service --------------------------------------------------------------


class LanSalesService:
    """Padanan `SalesService` untuk mode LAN."""

    def __init__(self, client: LanClient):
        self.client = client

    @staticmethod
    def new_invoice_number() -> str:
        """Nomor invoice final tetap dibuat server; ini hanya untuk tampilan."""
        return f"POS-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

    def checkout(
        self,
        sale,
        items: list[dict],
        payments: list[dict],
        *,
        idempotency_key: str | None = None,
    ) -> LanSale:
        """Kirim checkout ke server.

        `sale` diabaikan untuk harga: server menghitung ulang semuanya. Parameter
        dipertahankan agar signature sama dengan service lokal.
        """
        payload = {
            "items": [
                {
                    "product_id": int(item["product_id"]),
                    "qty": int(item["qty"]),
                    "discount": int(item.get("discount", 0)),
                }
                for item in items
            ],
            "payments": [
                {
                    "method": payment["method"],
                    "amount": int(payment["amount"]),
                    "reference": payment.get("reference"),
                }
                for payment in payments
            ],
            "discount": int(getattr(sale, "discount", 0) or 0),
            "tax": int(getattr(sale, "tax", 0) or 0),
            "customer_id": getattr(sale, "customer_id", None),
        }
        result = self.client.post(
            "/sales/checkout",
            json=payload,
            headers={"Idempotency-Key": idempotency_key or new_idempotency_key()},
        )
        return LanSale.from_payload(result)

    def daily_sales(self, on_date: date | None = None) -> list[LanSale]:
        params = {"date": (on_date or date.today()).isoformat()}
        rows = self.client.get("/sales", params=params)
        return [LanSale.from_payload(row) for row in rows or []]

    def refund_sale(self, sale_id: int, reason: str = "") -> LanSale:
        result = self.client.post(
            f"/sales/{sale_id}/refund",
            json={"reason": reason},
            headers={"Idempotency-Key": new_idempotency_key()},
        )
        return LanSale.from_payload(result)


class LanProductRepository:
    """Padanan `ProductRepository` untuk mode LAN (baca saja)."""

    def __init__(self, client: LanClient):
        self.client = client

    def find_by_barcode_or_sku(self, value: str) -> LanProduct | None:
        if not value:
            return None
        rows = self.client.get("/catalog/products", params={"search": value})
        for row in rows or []:
            product = LanProduct.from_payload(row)
            if value in (product.barcode, product.sku):
                return product
        return None

    def search_active(self, query: str, limit: int = 50) -> list[LanProduct]:
        rows = self.client.get("/catalog/products", params={"search": query})
        return [LanProduct.from_payload(row) for row in (rows or [])[:limit]]


class LanPricingService:
    """Padanan `BulkPricingService` untuk mode LAN.

    Harga grosir dan harga spesial dihitung server. Klien hanya menampilkan.
    Ini penting: kalau klien menghitung sendiri, harga di keranjang bisa
    berbeda dari harga saat checkout, dan pengguna akan mengira server salah.
    """

    def __init__(self, client: LanClient):
        self.client = client
        self._cache: dict[tuple[int, int], dict] = {}

    def price_for(self, product_id: int, quantity: int) -> dict:
        key = (product_id, quantity)
        if key not in self._cache:
            self._cache[key] = self.client.get(
                f"/catalog/products/{product_id}/price", params={"qty": quantity}
            )
        return self._cache[key]

    def unit_price(self, product, quantity: int) -> int:
        product_id = product.id if hasattr(product, "id") else int(product)
        return int(self.price_for(product_id, quantity)["unit_price"])

    def rule_for_product(self, product_id: int):
        """Kembalikan objek mirip BulkPriceRule, atau None bila tanpa aturan."""
        payload = self.price_for(product_id, 1)
        if not payload.get("has_rule"):
            return None

        class _Rule:
            def __init__(self, data: dict):
                self.quantity_threshold = data.get("rule_threshold") or 0
                self.special_price = data.get("special_price") or 0
                self.pricing_mode = "PRICE"

        return _Rule(payload)

    def effective_special_price(self, product, rule) -> int:
        return int(getattr(rule, "special_price", 0) or 0)


class LanMasterDataService:
    """Padanan `MasterDataService` untuk mode LAN (baca + tulis produk)."""

    def __init__(self, client: LanClient):
        self.client = client

    def get_product(self, product_id: int) -> LanProduct | None:
        try:
            return LanProduct.from_payload(
                self.client.get(f"/catalog/products/{product_id}")
            )
        except Exception:
            return None

    def list_products(self) -> list[LanProduct]:
        rows = self.client.get("/catalog/products", params={"include_inactive": True})
        return [LanProduct.from_payload(row) for row in rows or []]

    def search_products(self, query: str = "") -> list[LanProduct]:
        rows = self.client.get("/catalog/products", params={"search": query})
        return [LanProduct.from_payload(row) for row in rows or []]

    def list_categories(self) -> list[dict]:
        return self.client.get("/catalog/categories") or []

    def list_units(self) -> list[dict]:
        return self.client.get("/catalog/units") or []

    def list_suppliers(self) -> list[dict]:
        return self.client.get("/catalog/suppliers") or []

    def save_product(self, actor, **kwargs) -> LanProduct:
        product_id = kwargs.pop("product_id", None)
        if product_id is None:
            result = self.client.post("/catalog/products", json=kwargs)
        else:
            result = self.client.put(
                f"/catalog/products/{product_id}", json={**kwargs, "product_id": product_id}
            )
        return LanProduct.from_payload(result)

    def delete_product(self, actor, product_id: int) -> None:
        self.client.delete(f"/catalog/products/{product_id}")

    def add_stock(self, actor, product_id: int, quantity: int) -> LanProduct:
        result = self.client.post(
            "/catalog/products/stock",
            json={"product_id": product_id, "quantity": quantity},
        )
        return LanProduct.from_payload(result)


class LanShiftService:
    """Padanan `ShiftService` untuk mode LAN."""

    def __init__(self, client: LanClient):
        self.client = client

    def get_current(self) -> LanShift | None:
        payload = self.client.get("/shifts/current")
        if not payload:
            return None
        return LanShift(
            id=payload["id"],
            store_id=payload["store_id"],
            cashier_id=payload["cashier_id"],
            opening_cash=payload["opening_cash"],
            status=payload["status"],
            opened_at=payload.get("opened_at"),
            closed_at=payload.get("closed_at"),
            closing_cash=payload.get("closing_cash"),
        )

    def get_open_shift(self, user) -> LanShift | None:
        """Alias dengan nama yang dipakai CashierView."""
        return self.get_current()

    def open_shift(self, user, opening_cash: int) -> LanShift:
        payload = self.client.post("/shifts/open", json={"opening_cash": opening_cash})
        return LanShift(
            id=payload["id"],
            store_id=payload["store_id"],
            cashier_id=payload["cashier_id"],
            opening_cash=payload["opening_cash"],
            status=payload["status"],
            opened_at=payload.get("opened_at"),
        )

    def close_shift(self, closing_cash: int) -> LanShift:
        payload = self.client.post("/shifts/close", json={"closing_cash": closing_cash})
        return LanShift(
            id=payload["id"],
            store_id=payload["store_id"],
            cashier_id=payload["cashier_id"],
            opening_cash=payload["opening_cash"],
            status=payload["status"],
            closing_cash=payload.get("closing_cash"),
        )


class LanStoreSettingsService:
    """Padanan `StoreSettingsService` (baca/tulis identitas toko)."""

    def __init__(self, client: LanClient):
        self.client = client

    def get_store(self) -> LanStore | None:
        payload = self.client.get("/settings/store")
        if not payload:
            return None
        return LanStore(
            id=payload["id"],
            code=payload.get("code", "MAIN"),
            name=payload.get("name", ""),
            slogan=payload.get("slogan"),
            address=payload.get("address"),
            whatsapp=payload.get("whatsapp"),
            logo_path=payload.get("logo_path"),
        )

    def save(self, actor, *, name, address, whatsapp, slogan="", logo_source=None, remove_logo=False):
        payload = self.client.put(
            "/settings/store",
            json={
                "name": name,
                "address": address,
                "whatsapp": whatsapp,
                "slogan": slogan,
            },
        )
        return LanStore(
            id=payload["id"],
            code=payload.get("code", "MAIN"),
            name=payload.get("name", ""),
            slogan=payload.get("slogan"),
            address=payload.get("address"),
            whatsapp=payload.get("whatsapp"),
            logo_path=payload.get("logo_path"),
        )


class LanDailyReportService:
    """Padanan `CashierDailyReportService` untuk mode LAN.

    Laporan kasir harian dihitung server dari transaksi nyata, bukan dari
    catatan lokal yang bisa berbeda antar perangkat.
    """

    def __init__(self, client: LanClient):
        self.client = client

    def get_for_cashier(self, cashier_id: int, report_date: date):
        """Belum ada catatan naratif terpisah di v1; UI hanya butuh notes."""
        return None

    def daily_totals(self, cashier_id: int, report_date: date) -> tuple[int, int]:
        payload = self.client.get(
            "/reports/daily", params={"date": report_date.isoformat()}
        )
        return int(payload.get("sales_count") or 0), int(payload.get("sales_total") or 0)

    def save(self, *args, **kwargs):
        """Catatan laporan kasir belum diekspos API di v1.

        Melempar error yang jelas lebih baik daripada pura-pura berhasil.
        """
        from app.core.exceptions import ValidationError

        raise ValidationError(
            "Catatan laporan kasir belum tersedia di mode LAN. "
            "Gunakan mode standalone untuk fitur ini."
        )


class LanReportService:
    """Padanan `ReportService` untuk laporan harian dan rentang."""

    def __init__(self, client: LanClient):
        self.client = client

    def daily(self, on_date: date | None = None) -> dict:
        return self.client.get(
            "/reports/daily", params={"date": (on_date or date.today()).isoformat()}
        )

    def range(self, start: date, end: date) -> dict:
        return self.client.get(
            "/reports/range",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )

    def low_stock(self, threshold: int = 5) -> list[dict]:
        return self.client.get("/reports/low-stock", params={"threshold": threshold}) or []


__all__ = [
    "LanDailyReportService",
    "LanMasterDataService",
    "LanPricingService",
    "LanProduct",
    "LanProductRepository",
    "LanReportService",
    "LanSale",
    "LanSalesService",
    "LanShift",
    "LanShiftService",
    "LanStore",
    "LanStoreSettingsService",
    "new_idempotency_key",
]

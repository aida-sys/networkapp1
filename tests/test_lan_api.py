"""Test POS LAN API.

Fokus pada hal yang paling berbahaya bila salah: uang, stok, dan retry
jaringan. Setiap test memakai database SQLite sementara sendiri.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import Base  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    Account,
    FinancialSettings,
    Product,
    Role,
    Shift,
    Store,
    Supplier,
    User,
)
from lan_server import idempotency  # noqa: E402,F401  (registrasi tabel)
from lan_server.deps import get_db  # noqa: E402
from lan_server.main import create_app  # noqa: E402

API = "/api/v1"


# --- Fixture --------------------------------------------------------------


@pytest.fixture()
def api():
    """Client API dengan database sementara berisi satu toko dan dua user."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    from lan_server.database import LanBase

    LanBase.metadata.create_all(engine)
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    with TestingSession() as session:
        owner_role = Role(name="OWNER", description="Owner")
        cashier_role = Role(name="CASHIER", description="Kasir")
        store = Store(code="MAIN", name="Toko Uji")
        supplier = Supplier(code="SUP-001", name="Pemasok Uji")
        session.add_all([owner_role, cashier_role, store, supplier])
        session.flush()

        owner = User(
            username="owner",
            full_name="Owner Uji",
            password_hash=hash_password("rahasia123"),
            role=owner_role,
            is_active=True,
        )
        cashier = User(
            username="kasir",
            full_name="Kasir Uji",
            password_hash=hash_password("rahasia123"),
            role=cashier_role,
            is_active=True,
        )
        session.add_all([owner, cashier])

        accounts = [
            Account(
                code=code,
                name=name,
                account_type=account_type,
                is_active=True,
                is_system=True,
            )
            for code, name, account_type in (
                ("1000", "Kas", "ASSET"),
                ("1200", "Persediaan", "ASSET"),
                ("2000", "Hutang Usaha", "LIABILITY"),
                ("3000", "Modal Pemilik", "EQUITY"),
                ("4000", "Penjualan", "REVENUE"),
                ("5000", "Harga Pokok Penjualan", "EXPENSE"),
            )
        ]
        session.add_all(accounts)
        session.flush()

        session.add(
            FinancialSettings(
                id=1,
                effective_from=date.today(),
                initialized_by=owner.id,
            )
        )

        products = [
            Product(
                sku="SKU-A",
                name="Beras 5kg",
                purchase_price=60_000,
                selling_price=72_000,
                stock_qty=10,
                min_stock=2,
                is_active=True,
            ),
            Product(
                sku="SKU-B",
                name="Gula 1kg",
                purchase_price=15_000,
                selling_price=18_000,
                stock_qty=3,
                min_stock=2,
                is_active=True,
            ),
        ]
        session.add_all(products)
        session.commit()

        owner_id = owner.id
        cashier_id = cashier.id
        product_ids = [product.id for product in products]

    app = create_app()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    client.testing_session = TestingSession  # type: ignore[attr-defined]
    client.owner_id = owner_id  # type: ignore[attr-defined]
    client.cashier_id = cashier_id  # type: ignore[attr-defined]
    client.product_ids = product_ids  # type: ignore[attr-defined]

    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        from lan_server.database import LanBase as _LanBase

        _LanBase.metadata.drop_all(engine)
        engine.dispose()


def _login(client, username="kasir", password="rahasia123") -> str:
    response = client.post(
        f"{API}/auth/login",
        json={"username": username, "password": password, "device_id": "test-device"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _open_shift(client, token: str, opening_cash: int = 200_000) -> int:
    response = client.post(
        f"{API}/shifts/open",
        json={"opening_cash": opening_cash},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _stock(client, token: str, product_id: int) -> int:
    response = client.get(f"{API}/catalog/products/{product_id}", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()["stock_qty"]


# --- Health & auth --------------------------------------------------------


def test_health_is_public_and_reports_database(api):
    response = api.get(f"{API}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_login_returns_token_and_role(api):
    response = api.post(
        f"{API}/auth/login",
        json={"username": "kasir", "password": "rahasia123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "CASHIER"
    assert body["access_token"]
    assert body["expires_in"] > 0


def test_login_rejects_wrong_password(api):
    response = api.post(
        f"{API}/auth/login",
        json={"username": "kasir", "password": "salah"},
    )
    assert response.status_code == 401


def test_protected_endpoint_requires_token(api):
    assert api.get(f"{API}/catalog/products").status_code == 401
    assert api.get(f"{API}/sales").status_code == 401


def test_tampered_token_is_rejected(api):
    token = _login(api)
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    response = api.get(f"{API}/catalog/products", headers=_auth(tampered))
    assert response.status_code == 401


def test_me_returns_store(api):
    token = _login(api)
    response = api.get(f"{API}/auth/me", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["store_name"] == "Toko Uji"


# --- Checkout -------------------------------------------------------------


def test_checkout_persists_sale_and_reduces_stock(api):
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[0]

    response = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": product_id, "qty": 2}],
            "payments": [{"method": "CASH", "amount": 200_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "checkout-1"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["grand_total"] == 144_000
    assert body["status"] == "PAID"
    assert len(body["items"]) == 1
    assert body["items"][0]["unit_price"] == 72_000
    assert _stock(api, token, product_id) == 8


def test_checkout_requires_idempotency_key(api):
    token = _login(api)
    _open_shift(api, token)
    response = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": api.product_ids[0], "qty": 1}],
            "payments": [{"method": "CASH", "amount": 100_000}],
        },
        headers=_auth(token),
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["detail"]


def test_checkout_without_open_shift_is_rejected(api):
    token = _login(api)
    response = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": api.product_ids[0], "qty": 1}],
            "payments": [{"method": "CASH", "amount": 100_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "no-shift"},
    )
    assert response.status_code == 409
    assert "shift" in response.json()["detail"].lower()


def test_checkout_after_shift_closed_is_rejected(api):
    token = _login(api)
    _open_shift(api, token)
    closed = api.post(
        f"{API}/shifts/close", json={"closing_cash": 200_000}, headers=_auth(token)
    )
    assert closed.status_code == 200

    response = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": api.product_ids[0], "qty": 1}],
            "payments": [{"method": "CASH", "amount": 100_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "closed-shift"},
    )
    assert response.status_code == 409


def test_checkout_rejects_overselling(api):
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[1]  # stok 3

    response = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": product_id, "qty": 99}],
            "payments": [{"method": "CASH", "amount": 10_000_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "oversell-1"},
    )
    assert response.status_code == 409
    assert "stok" in response.json()["detail"].lower()
    # Stok tidak boleh berubah sama sekali.
    assert _stock(api, token, product_id) == 3


def test_checkout_rejects_underpayment(api):
    token = _login(api)
    _open_shift(api, token)
    response = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": api.product_ids[0], "qty": 1}],
            "payments": [{"method": "CASH", "amount": 1_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "underpay-1"},
    )
    assert response.status_code == 400


def test_checkout_ignores_client_supplied_price(api):
    """Klien tidak boleh menentukan harga: field asing harus diabaikan."""
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[0]

    response = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [
                {"product_id": product_id, "qty": 1, "unit_price": 1, "line_total": 1}
            ],
            "payments": [{"method": "CASH", "amount": 1}],
        },
        headers={**_auth(token), "Idempotency-Key": "fake-price"},
    )
    # Ditolak karena pembayaran kurang dari harga server (72.000), bukan 1.
    assert response.status_code == 400
    assert _stock(api, token, product_id) == 10


# --- Idempotency ----------------------------------------------------------


def test_checkout_retry_with_same_key_does_not_duplicate(api):
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[0]
    payload = {
        "items": [{"product_id": product_id, "qty": 2}],
        "payments": [{"method": "CASH", "amount": 200_000}],
    }
    headers = {**_auth(token), "Idempotency-Key": "retry-same"}

    first = api.post(f"{API}/sales/checkout", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    second = api.post(f"{API}/sales/checkout", json=payload, headers=headers)
    assert second.status_code == 201, second.text

    # Respons identik dan stok hanya berkurang sekali.
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["invoice_no"] == second.json()["invoice_no"]
    assert _stock(api, token, product_id) == 8

    sales = api.get(f"{API}/sales", headers=_auth(token)).json()
    assert len(sales) == 1


def test_checkout_same_key_different_body_conflicts(api):
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[0]
    headers = {**_auth(token), "Idempotency-Key": "reused-key"}

    first = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": product_id, "qty": 1}],
            "payments": [{"method": "CASH", "amount": 100_000}],
        },
        headers=headers,
    )
    assert first.status_code == 201

    second = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": product_id, "qty": 2}],
            "payments": [{"method": "CASH", "amount": 200_000}],
        },
        headers=headers,
    )
    assert second.status_code == 409
    assert _stock(api, token, product_id) == 9


def test_failed_checkout_allows_retry_with_same_key(api):
    """Checkout gagal tidak boleh mengunci key selamanya."""
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[1]  # stok 3
    headers = {**_auth(token), "Idempotency-Key": "retry-after-fail"}

    failed = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": product_id, "qty": 99}],
            "payments": [{"method": "CASH", "amount": 10_000_000}],
        },
        headers=headers,
    )
    assert failed.status_code == 409

    ok = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": product_id, "qty": 2}],
            "payments": [{"method": "CASH", "amount": 100_000}],
        },
        headers=headers,
    )
    assert ok.status_code == 201, ok.text
    assert _stock(api, token, product_id) == 1


# --- Konkurensi -----------------------------------------------------------


def test_two_checkouts_cannot_oversell_last_items(api):
    """Dua kasir berebut stok yang sama: hanya satu yang boleh berhasil."""
    cashier_token = _login(api, "kasir")
    owner_token = _login(api, "owner")
    _open_shift(api, cashier_token)
    _open_shift(api, owner_token)

    product_id = api.product_ids[1]  # stok 3
    payload = {
        "items": [{"product_id": product_id, "qty": 3}],
        "payments": [{"method": "CASH", "amount": 100_000}],
    }

    first = api.post(
        f"{API}/sales/checkout",
        json=payload,
        headers={**_auth(cashier_token), "Idempotency-Key": "race-a"},
    )
    second = api.post(
        f"{API}/sales/checkout",
        json=payload,
        headers={**_auth(owner_token), "Idempotency-Key": "race-b"},
    )

    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [201, 409], (first.text, second.text)
    assert _stock(api, cashier_token, product_id) == 0


def test_stock_never_goes_negative_across_many_attempts(api):
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[1]  # stok 3

    statuses = []
    for index in range(6):
        response = api.post(
            f"{API}/sales/checkout",
            json={
                "items": [{"product_id": product_id, "qty": 1}],
                "payments": [{"method": "CASH", "amount": 20_000}],
            },
            headers={**_auth(token), "Idempotency-Key": f"loop-{index}"},
        )
        statuses.append(response.status_code)

    assert statuses.count(201) == 3
    assert statuses.count(409) == 3
    assert _stock(api, token, product_id) == 0


# --- Refund ---------------------------------------------------------------


def test_refund_restores_stock_and_marks_status(api):
    token = _login(api)
    _open_shift(api, token)
    product_id = api.product_ids[0]

    sale = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": product_id, "qty": 2}],
            "payments": [{"method": "CASH", "amount": 200_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "refund-src"},
    ).json()

    owner_token = _login(api, "owner")
    refund = api.post(
        f"{API}/sales/{sale['id']}/refund",
        json={"reason": "Barang rusak"},
        headers={**_auth(owner_token), "Idempotency-Key": "refund-1"},
    )
    assert refund.status_code == 200, refund.text
    assert refund.json()["status"] == "REFUNDED"
    assert _stock(api, token, product_id) == 10


def test_cashier_cannot_refund(api):
    token = _login(api)
    _open_shift(api, token)
    sale = api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": api.product_ids[0], "qty": 1}],
            "payments": [{"method": "CASH", "amount": 100_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "cashier-refund-src"},
    ).json()

    response = api.post(
        f"{API}/sales/{sale['id']}/refund",
        json={"reason": "coba"},
        headers={**_auth(token), "Idempotency-Key": "cashier-refund"},
    )
    assert response.status_code == 403


# --- Katalog & laporan ----------------------------------------------------


def test_catalog_lists_products(api):
    token = _login(api)
    response = api.get(f"{API}/catalog/products", headers=_auth(token))
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_catalog_search_filters(api):
    token = _login(api)
    response = api.get(
        f"{API}/catalog/products", params={"search": "Beras"}, headers=_auth(token)
    )
    assert len(response.json()) == 1
    assert response.json()[0]["sku"] == "SKU-A"


def test_stock_adjustment_is_recorded(api):
    token = _login(api, "owner")
    product_id = api.product_ids[0]
    response = api.post(
        f"{API}/catalog/products/stock",
        json={"product_id": product_id, "quantity": 5},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["stock_qty"] == 15


def test_daily_report_totals_sales(api):
    token = _login(api)
    _open_shift(api, token)
    api.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": api.product_ids[0], "qty": 1}],
            "payments": [{"method": "CASH", "amount": 100_000}],
        },
        headers={**_auth(token), "Idempotency-Key": "report-1"},
    )

    response = api.get(f"{API}/reports/daily", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sales_count"] == 1
    assert body["sales_total"] == 72_000


def test_store_settings_roundtrip(api):
    token = _login(api, "owner")
    update = api.put(
        f"{API}/settings/store",
        json={
            "name": "Toko Baru",
            "address": "Jl. Uji 1",
            "whatsapp": "081200000000",
            "slogan": "Murah",
        },
        headers=_auth(token),
    )
    assert update.status_code == 200, update.text

    read = api.get(f"{API}/settings/store", headers=_auth(token))
    assert read.json()["name"] == "Toko Baru"


def test_purchase_is_idempotent(api):
    token = _login(api, "owner")
    product_id = api.product_ids[0]
    supplier_id = api.get(
        f"{API}/catalog/suppliers", headers=_auth(token)
    ).json()[0]["id"]

    payload = {
        "supplier_id": supplier_id,
        "product_id": product_id,
        "quantity": 4,
        "unit_cost": 60_000,
        "payment_status": "TEMPO",
        "due_date": (date.today() + timedelta(days=14)).isoformat(),
    }
    headers = {**_auth(token), "Idempotency-Key": "purchase-1"}

    first = api.post(f"{API}/purchases", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    second = api.post(f"{API}/purchases", json=payload, headers=headers)
    assert second.status_code == 201, second.text

    assert first.json()["id"] == second.json()["id"]
    assert _stock(api, token, product_id) == 14


# --- Isolasi dari billing -------------------------------------------------


def test_lan_server_does_not_import_billing_modules():
    """Server transaksi tidak boleh bergantung pada server billing.

    Yang diperiksa adalah pernyataan import, bukan kata "billing" di komentar
    atau docstring (dokumentasi justru harus menjelaskan pemisahan ini).
    """
    import ast

    modules = [
        "lan_server.main",
        "lan_server.routers.sales",
        "lan_server.routers.catalog",
        "lan_server.routers.purchases",
        "lan_server.routers.reports",
        "lan_server.routers.auth",
        "lan_server.deps",
        "lan_server.database",
    ]
    for module_name in modules:
        path = Path(sys.modules[module_name].__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        offenders = [
            name
            for name in imported
            if name == "server" or name.startswith("server.")
        ]
        assert not offenders, f"{module_name} mengimpor modul billing: {offenders}"


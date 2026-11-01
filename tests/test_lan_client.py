"""Test lapisan klien LAN pada aplikasi desktop.

Tidak ada server yang dijalankan: transport httpx diganti dengan handler palsu
supaya perilaku jaringan bisa diuji deterministik, termasuk saat server mati.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.exceptions import (
    AuthenticationError,
    InsufficientStockError,
    ShiftNotOpenError,
    ValidationError,
)
from app.lan.client import LanClient, LanUnavailableError
from app.lan.config import (
    LanConfig,
    LanConfigError,
    MODE_LAN,
    MODE_STANDALONE,
    load_config,
    save_config,
)
from app.lan.service_factory import ServiceFactory


def _config(tmp_path: Path, mode: str = MODE_LAN, api_url: str = "http://192.168.1.10:8002"):
    return LanConfig(
        mode=mode,
        api_url=api_url,
        device_id="test",
        timeout_seconds=5,
        token_path=tmp_path / "token.json",
    )


def _client(tmp_path: Path, handler, *, mode: str = MODE_LAN) -> LanClient:
    return LanClient(
        _config(tmp_path, mode=mode),
        transport=httpx.MockTransport(handler),
    )


# --- Konfigurasi ----------------------------------------------------------


def test_default_mode_is_standalone(tmp_path, monkeypatch):
    monkeypatch.delenv("POS_MODE", raising=False)
    monkeypatch.delenv("POS_API_URL", raising=False)
    monkeypatch.setattr("app.lan.config._data_dir", lambda: tmp_path)
    config = load_config()
    assert config.mode == MODE_STANDALONE
    assert config.is_standalone


def test_lan_mode_requires_api_url(tmp_path, monkeypatch):
    monkeypatch.setenv("POS_MODE", "lan")
    monkeypatch.delenv("POS_API_URL", raising=False)
    monkeypatch.setattr("app.lan.config._data_dir", lambda: tmp_path)
    with pytest.raises(LanConfigError):
        load_config()


def test_invalid_mode_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("POS_MODE", "cloud")
    monkeypatch.setattr("app.lan.config._data_dir", lambda: tmp_path)
    with pytest.raises(LanConfigError):
        load_config()


def test_save_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("POS_MODE", raising=False)
    monkeypatch.delenv("POS_API_URL", raising=False)
    monkeypatch.setattr("app.lan.config._data_dir", lambda: tmp_path)
    saved = save_config(mode="lan", api_url="http://10.0.0.5:8002/")
    assert saved.mode == MODE_LAN
    assert saved.api_url == "http://10.0.0.5:8002"
    assert load_config().api_url == "http://10.0.0.5:8002"


def test_save_lan_without_url_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("app.lan.config._data_dir", lambda: tmp_path)
    with pytest.raises(LanConfigError):
        save_config(mode="lan", api_url="")


# --- Klien ----------------------------------------------------------------


def test_login_stores_token(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/auth/login")
        return httpx.Response(
            200,
            json={
                "access_token": "tok-123",
                "expires_in": 3600,
                "user": {"id": 1, "username": "kasir", "role": "CASHIER"},
            },
        )

    client = _client(tmp_path, handler)
    payload = client.login("kasir", "rahasia")
    assert payload["access_token"] == "tok-123"
    assert client.tokens.read() == "tok-123"
    client.close()


def test_request_without_token_is_rejected_locally(tmp_path):
    client = _client(tmp_path, lambda request: httpx.Response(200, json=[]))
    with pytest.raises(AuthenticationError):
        client.get("/catalog/products")
    client.close()


def test_network_failure_raises_unavailable_not_local_fallback(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(tmp_path, handler)
    client.tokens.write("tok")
    with pytest.raises(LanUnavailableError) as excinfo:
        client.get("/catalog/products")
    assert "tidak dapat dihubungi" in str(excinfo.value)
    client.close()


def test_stock_conflict_maps_to_insufficient_stock(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Stok produk tidak mencukupi."})

    client = _client(tmp_path, handler)
    client.tokens.write("tok")
    with pytest.raises(InsufficientStockError):
        client.post("/sales/checkout", json={})
    client.close()


def test_shift_conflict_maps_to_shift_not_open(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Buka shift sebelum berjualan."})

    client = _client(tmp_path, handler)
    client.tokens.write("tok")
    with pytest.raises(ShiftNotOpenError):
        client.post("/sales/checkout", json={})
    client.close()


def test_bad_request_maps_to_validation_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "Qty harus lebih dari 0."})

    client = _client(tmp_path, handler)
    client.tokens.write("tok")
    with pytest.raises(ValidationError):
        client.post("/sales/checkout", json={})
    client.close()


def test_401_maps_to_authentication_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Token kedaluwarsa."})

    client = _client(tmp_path, handler)
    client.tokens.write("tok")
    with pytest.raises(AuthenticationError):
        client.get("/catalog/products")
    client.close()


# --- Service adapter ------------------------------------------------------


def test_lan_sales_service_sends_server_authoritative_payload(tmp_path):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "id": 7,
                "invoice_no": "INV-1",
                "store_id": 1,
                "shift_id": 2,
                "cashier_id": 3,
                "subtotal": 144000,
                "discount": 0,
                "tax": 0,
                "grand_total": 144000,
                "status": "PAID",
                "created_at": "2026-11-01T10:00:00+00:00",
                "items": [
                    {
                        "id": 1,
                        "product_id": 5,
                        "qty": 2,
                        "unit_price": 72000,
                        "discount": 0,
                        "line_total": 144000,
                    }
                ],
                "payments": [],
            },
        )

    client = _client(tmp_path, handler)
    client.tokens.write("tok")

    from app.lan.services import LanSalesService

    class FakeSale:
        discount = 0
        tax = 0
        customer_id = None

    sale = LanSalesService(client).checkout(
        FakeSale(),
        [{"product_id": 5, "qty": 2, "unit_price": 1}],
        [{"method": "CASH", "amount": 200000}],
        idempotency_key="fixed-key",
    )

    assert sale.grand_total == 144000
    assert sale.invoice_no == "INV-1"
    # Klien tidak boleh mengirim harga sendiri.
    assert "unit_price" not in captured["body"]["items"][0]
    assert captured["headers"]["idempotency-key"] == "fixed-key"
    client.close()


def test_lan_pricing_service_uses_server_price(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/catalog/products/5/price")
        return httpx.Response(
            200,
            json={
                "product_id": 5,
                "qty": 10,
                "unit_price": 65000,
                "regular_price": 72000,
                "has_rule": True,
                "rule_threshold": 10,
                "special_price": 65000,
            },
        )

    client = _client(tmp_path, handler)
    client.tokens.write("tok")

    from app.lan.services import LanPricingService

    pricing = LanPricingService(client)

    class FakeProduct:
        id = 5

    assert pricing.unit_price(FakeProduct(), 10) == 65000
    assert pricing.rule_for_product(5).quantity_threshold == 10
    client.close()


# --- Factory --------------------------------------------------------------


def test_factory_standalone_does_not_require_network(tmp_path):
    factory = ServiceFactory(_config(tmp_path, mode=MODE_STANDALONE))
    assert factory.is_standalone
    assert "standalone" in factory.describe()


def test_factory_lan_refuses_local_session(tmp_path):
    factory = ServiceFactory(_config(tmp_path))
    assert factory.is_lan
    with pytest.raises(LanConfigError):
        _ = factory.session


def test_factory_lan_builds_remote_services(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    factory = ServiceFactory(_config(tmp_path))
    factory._client = LanClient(
        _config(tmp_path), transport=httpx.MockTransport(handler)
    )

    from app.lan.services import (
        LanMasterDataService,
        LanPricingService,
        LanSalesService,
        LanShiftService,
    )

    assert isinstance(factory.sales(), LanSalesService)
    assert isinstance(factory.master_data(), LanMasterDataService)
    assert isinstance(factory.pricing(), LanPricingService)
    assert isinstance(factory.shifts(), LanShiftService)
    factory.close()

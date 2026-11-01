"""Klien HTTP untuk POS LAN API.

Tugas utama modul ini bukan sekadar memanggil endpoint, tetapi menjaga agar
kegagalan jaringan muncul sebagai exception yang sudah dikenal UI
(`InsufficientStockError`, `ShiftNotOpenError`, dst). Dengan begitu tidak ada
satu pun view yang perlu diubah saat aplikasi berjalan di mode LAN.

Aturan penting: TIDAK ADA fallback ke database lokal. Bila server tidak
terjangkau, operasi gagal dengan `LanUnavailableError`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InsufficientStockError,
    PaymentIncompleteError,
    POSException,
    ShiftNotOpenError,
    ValidationError,
)
from app.lan.config import LanConfig


class LanUnavailableError(POSException):
    """Server LAN tidak dapat dihubungi. Operasi tulis ditolak, bukan dialihkan."""


class LanApiError(POSException):
    """Server menjawab dengan error yang tidak bisa dipetakan ke exception domain."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class TokenStore:
    """Simpan token akses di file lokal dengan izin terbatas."""

    def __init__(self, path: Path):
        self.path = path

    def read(self) -> str | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        token = payload.get("access_token")
        return token if isinstance(token, str) and token else None

    def write(self, token: str, username: str | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"access_token": token, "username": username}
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def _map_error(status_code: int, detail: str) -> Exception:
    """Petakan status HTTP ke exception domain yang sudah dipakai UI."""
    lowered = (detail or "").lower()
    if status_code == 401:
        return AuthenticationError(detail or "Sesi berakhir, silakan login ulang.")
    if status_code == 403:
        return AuthorizationError(detail or "Anda tidak berhak melakukan ini.")
    if status_code == 409:
        if "stok" in lowered:
            return InsufficientStockError(detail)
        if "shift" in lowered:
            return ShiftNotOpenError(detail)
        return ValidationError(detail)
    if status_code == 400:
        if "lunas" in lowered or "pembayaran" in lowered:
            return PaymentIncompleteError(detail)
        return ValidationError(detail)
    if status_code == 404:
        return ValidationError(detail or "Data tidak ditemukan di server.")
    return LanApiError(status_code, detail or "Permintaan ke server gagal.")


class LanClient:
    """Pembungkus httpx dengan token, idempotency, dan pemetaan error."""

    def __init__(self, config: LanConfig, *, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.tokens = TokenStore(config.token_path)
        self._client = httpx.Client(
            base_url=f"{config.api_url}/api/v1",
            timeout=config.timeout_seconds,
            transport=transport,
        )

    # --- Siklus hidup -------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LanClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # --- Autentikasi --------------------------------------------------

    def login(self, username: str, password: str) -> dict:
        response = self._request(
            "POST",
            "/auth/login",
            json={
                "username": username,
                "password": password,
                "device_id": self.config.device_id,
            },
            authenticated=False,
        )
        token = response.get("access_token")
        if token:
            self.tokens.write(token, username)
        return response

    def logout(self) -> None:
        self.tokens.clear()

    def health(self) -> dict:
        return self._request("GET", "/health", authenticated=False)

    # --- Inti request -------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict | None = None,
        headers: dict | None = None,
        authenticated: bool = True,
    ) -> Any:
        request_headers = dict(headers or {})
        if authenticated:
            token = self.tokens.read()
            if not token:
                raise AuthenticationError("Belum login ke server LAN.")
            request_headers["Authorization"] = f"Bearer {token}"

        try:
            response = self._client.request(
                method,
                path,
                json=json,
                params=params,
                headers=request_headers,
            )
        except httpx.HTTPError as exc:
            # Tidak ada fallback ke database lokal. Ini keputusan sadar.
            raise LanUnavailableError(
                f"Server POS LAN tidak dapat dihubungi ({self.config.api_url}). "
                "Periksa kabel/WiFi dan pastikan server menyala. "
                f"Detail: {exc.__class__.__name__}"
            ) from exc

        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                detail = payload.get("detail") or ""
                if isinstance(detail, list):
                    detail = "; ".join(str(item) for item in detail)
            except (ValueError, json.JSONDecodeError):
                detail = response.text[:300]
            raise _map_error(response.status_code, str(detail))

        if response.status_code == 204:
            return None
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError):
            return None

    def get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Any:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Any:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self._request("DELETE", path, **kwargs)


__all__ = [
    "LanApiError",
    "LanClient",
    "LanUnavailableError",
    "TokenStore",
]

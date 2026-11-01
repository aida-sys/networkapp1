"""Token akses untuk POS LAN API.

JWT HS256 diimplementasikan langsung dengan hmac/hashlib supaya tidak menambah
dependency baru ke paket installer desktop. Formatnya JWT standar sehingga
klien lain (Dart, JS) bisa memverifikasi bila perlu.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from lan_server.config import settings

_EPOCH = 0


class TokenError(Exception):
    """Token tidak valid, kedaluwarsa, atau tanda tangan salah."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(message: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    store_id: int | None = None,
    device_id: str | None = None,
    ttl_minutes: int | None = None,
) -> str:
    """Buat token akses bertanda tangan untuk satu user + device."""
    issued_at = int(time.time())
    ttl = ttl_minutes if ttl_minutes is not None else settings.token_ttl_minutes
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "store_id": store_id,
        "device_id": device_id,
        "iat": issued_at,
        "exp": issued_at + (ttl * 60),
    }
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    segments = [
        _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = _sign(signing_input, settings.resolve_jwt_secret())
    segments.append(_b64encode(signature))
    return ".".join(segments)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verifikasi tanda tangan dan masa berlaku, lalu kembalikan payload."""
    if not token or token.count(".") != 2:
        raise TokenError("Format token tidak valid.")
    header_segment, payload_segment, signature_segment = token.split(".")
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected = _sign(signing_input, settings.resolve_jwt_secret())
    try:
        provided = _b64decode(signature_segment)
    except (ValueError, base64.binascii.Error) as exc:
        raise TokenError("Tanda tangan token tidak dapat dibaca.") from exc
    if not hmac.compare_digest(expected, provided):
        raise TokenError("Tanda tangan token tidak cocok.")

    try:
        header = json.loads(_b64decode(header_segment))
        payload = json.loads(_b64decode(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Isi token tidak dapat dibaca.") from exc

    if header.get("alg") != settings.jwt_algorithm:
        raise TokenError("Algoritma token tidak didukung.")

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        raise TokenError("Token tidak memiliki masa berlaku.")
    if int(time.time()) >= expires_at:
        raise TokenError("Token sudah kedaluwarsa.")
    return payload


__all__ = ["TokenError", "create_access_token", "decode_access_token"]

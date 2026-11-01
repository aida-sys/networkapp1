"""Idempotency untuk operasi tulis POS.

Retry jaringan tidak boleh membuat transaksi atau pembayaran ganda. Setiap
operasi tulis yang berisiko (checkout, refund, penerimaan barang) wajib
membawa header `Idempotency-Key`.

Perilaku:
- key baru -> operasi dijalankan, respons disimpan.
- key sama + body sama -> respons tersimpan dikembalikan apa adanya (replay).
- key sama + body beda -> 409 Conflict.
- key sama tapi permintaan pertama belum selesai -> 409 Conflict.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from lan_server.database import LanBase


class ApiIdempotency(LanBase):
    """Catatan idempotency. Tabel ini hanya milik server LAN."""

    __tablename__ = "api_idempotency"

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="IN_PROGRESS", nullable=False)
    response_code: Mapped[int | None] = mapped_column()
    response_body: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class IdempotencyConflict(Exception):
    """Key dipakai ulang dengan body berbeda, atau masih diproses."""


class IdempotencyReplay(Exception):
    """Permintaan ini sudah pernah berhasil; kembalikan respons tersimpan."""

    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__("Replay respons idempotent.")


def hash_request(payload: Any) -> str:
    """Hash stabil dari body permintaan."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def begin(
    session: Session,
    *,
    key: str,
    endpoint: str,
    request_payload: Any,
) -> ApiIdempotency:
    """Daftarkan permintaan baru, atau picu replay/konflik.

    Mengembalikan record yang harus diisi lewat `complete()`.
    """
    normalized_key = (key or "").strip()
    if not normalized_key:
        raise ValueError("Idempotency-Key wajib dikirim.")
    if len(normalized_key) > 200:
        raise ValueError("Idempotency-Key maksimal 200 karakter.")

    request_hash = hash_request(request_payload)
    existing = session.scalar(
        select(ApiIdempotency).where(
            ApiIdempotency.idempotency_key == normalized_key
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflict(
                "Idempotency-Key sudah dipakai untuk permintaan yang berbeda."
            )
        if existing.status != "COMPLETED":
            raise IdempotencyConflict(
                "Permintaan dengan Idempotency-Key ini masih diproses."
            )
        body = json.loads(existing.response_body) if existing.response_body else None
        raise IdempotencyReplay(existing.response_code or 200, body)

    record = ApiIdempotency(
        idempotency_key=normalized_key,
        endpoint=endpoint,
        request_hash=request_hash,
        status="IN_PROGRESS",
    )
    session.add(record)
    session.flush()
    return record


def complete(
    session: Session,
    record: ApiIdempotency,
    *,
    status_code: int,
    body: Any,
) -> None:
    """Simpan respons sukses agar retry berikutnya mendapat hasil yang sama."""
    record.status = "COMPLETED"
    record.response_code = status_code
    record.response_body = json.dumps(body, default=str)
    record.updated_at = datetime.now(timezone.utc)
    session.flush()


def abandon(session: Session, record: ApiIdempotency) -> None:
    """Hapus catatan bila operasi gagal, supaya klien bisa mencoba lagi."""
    session.delete(record)
    session.flush()


def purge_older_than(session: Session, days: int = 7) -> int:
    """Bersihkan catatan lama. Dipakai skrip pemeliharaan."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = list(
        session.scalars(
            select(ApiIdempotency).where(ApiIdempotency.created_at < cutoff)
        )
    )
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)


__all__ = [
    "ApiIdempotency",
    "IdempotencyConflict",
    "IdempotencyReplay",
    "abandon",
    "begin",
    "complete",
    "hash_request",
    "purge_older_than",
]

"""Konfigurasi mode operasi aplikasi desktop.

Dua mode, dipilih eksplisit dan tidak pernah berpindah sendiri:

- ``standalone`` (default): database SQLite lokal seperti sebelumnya.
- ``lan``: semua operasi POS lewat POS LAN API dan database pusat.

Tidak ada dual-write dan tidak ada fallback diam-diam dari LAN ke lokal.
Bila server tidak terjangkau di mode LAN, operasi tulis gagal dengan pesan
jelas, bukan diam-diam menulis ke database lokal.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

MODE_STANDALONE = "standalone"
MODE_LAN = "lan"

VALID_MODES = {MODE_STANDALONE, MODE_LAN}


class LanConfigError(Exception):
    """Konfigurasi mode LAN tidak lengkap atau tidak valid."""


@dataclass(frozen=True)
class LanConfig:
    mode: str
    api_url: str
    device_id: str
    timeout_seconds: float
    token_path: Path

    @property
    def is_lan(self) -> bool:
        return self.mode == MODE_LAN

    @property
    def is_standalone(self) -> bool:
        return self.mode == MODE_STANDALONE


def _data_dir() -> Path:
    from app.core.config import settings

    return settings.data_dir


def _read_mode_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_config() -> LanConfig:
    """Baca konfigurasi mode dari environment, lalu file, lalu default.

    Urutan prioritas: environment (POS_MODE, POS_API_URL) menang atas file
    `lan_mode.json`, supaya admin toko bisa memaksa mode lewat shortcut/script.
    """
    data_dir = _data_dir()
    stored = _read_mode_file(data_dir / "lan_mode.json")

    mode = (os.getenv("POS_MODE") or stored.get("mode") or MODE_STANDALONE).strip().lower()
    if mode not in VALID_MODES:
        raise LanConfigError(
            f"POS_MODE tidak dikenal: {mode!r}. Gunakan 'standalone' atau 'lan'."
        )

    api_url = (os.getenv("POS_API_URL") or stored.get("api_url") or "").strip()
    device_id = (stored.get("device_id") or "").strip() or "desktop"

    if mode == MODE_LAN and not api_url:
        raise LanConfigError(
            "Mode LAN aktif tetapi POS_API_URL belum diisi. "
            "Contoh: http://192.168.1.10:8002"
        )

    return LanConfig(
        mode=mode,
        api_url=api_url.rstrip("/"),
        device_id=device_id,
        timeout_seconds=float(stored.get("timeout_seconds") or 15),
        token_path=data_dir / "lan_token.json",
    )


def save_config(*, mode: str, api_url: str, device_id: str = "desktop") -> LanConfig:
    """Simpan pilihan mode. Dipakai layar pengaturan, bukan saat aplikasi dibuka."""
    normalized = mode.strip().lower()
    if normalized not in VALID_MODES:
        raise LanConfigError(
            f"Mode tidak dikenal: {mode!r}. Gunakan 'standalone' atau 'lan'."
        )
    if normalized == MODE_LAN and not api_url.strip():
        raise LanConfigError("Alamat server LAN wajib diisi untuk mode LAN.")

    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": normalized,
        "api_url": api_url.strip().rstrip("/"),
        "device_id": device_id.strip() or "desktop",
    }
    (data_dir / "lan_mode.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return load_config()


__all__ = [
    "LanConfig",
    "LanConfigError",
    "MODE_LAN",
    "MODE_STANDALONE",
    "load_config",
    "save_config",
]

"""Konfigurasi POS LAN API.

Terpisah total dari `server/` (billing/lisensi). Modul ini tidak pernah
membaca atau menulis database billing, dan sebaliknya.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAN_DIR = PROJECT_ROOT / "lan_server"


class LanSettings(BaseSettings):
    """Pengaturan server POS LAN.

    Semua nilai bisa ditimpa lewat environment atau `lan_server/.env`.
    """

    app_name: str = "POS LAN API"
    app_env: str = "development"

    # Bind ke 0.0.0.0 agar bisa diakses dari Android/browser di jaringan lokal.
    # JANGAN diekspos ke internet tanpa reverse proxy + TLS.
    host: str = "0.0.0.0"
    port: int = 8002

    # Database pusat. Default di disk komputer server (bukan shared folder).
    database_path: str | None = None

    # JWT. Bila kosong, secret dibuat sekali dan disimpan ke file lokal supaya
    # token tidak invalid setiap restart.
    jwt_secret: str | None = None
    jwt_secret_path: str | None = None
    jwt_algorithm: str = "HS256"
    token_ttl_minutes: int = 720

    # CORS untuk Flutter web. Dikosongkan berarti hanya origin yang sama.
    cors_origins: str = ""

    # Folder build Flutter web yang disajikan server (opsional).
    web_build_dir: str | None = None

    # Batas waktu koneksi database (detik).
    db_busy_timeout_ms: int = 5000

    model_config = SettingsConfigDict(
        env_file=str(LAN_DIR / ".env"),
        env_prefix="LAN_",
        extra="ignore",
    )

    # --- Path turunan -------------------------------------------------

    @property
    def data_dir(self) -> Path:
        path = LAN_DIR / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def resolved_database_path(self) -> Path:
        if self.database_path:
            path = Path(self.database_path).expanduser()
            if not path.is_absolute():
                path = LAN_DIR / path
        else:
            path = self.data_dir / "pos_lan.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.resolved_database_path}"

    @property
    def resolved_web_build_dir(self) -> Path | None:
        if not self.web_build_dir:
            return None
        path = Path(self.web_build_dir).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path if path.is_dir() else None

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def resolve_jwt_secret(self) -> str:
        """Ambil secret JWT, buat dan simpan sekali bila belum ada."""
        if self.jwt_secret:
            return self.jwt_secret
        if self.jwt_secret_path:
            path = Path(self.jwt_secret_path).expanduser()
            if not path.is_absolute():
                path = LAN_DIR / path
        else:
            path = self.data_dir / "jwt_secret.key"
        if path.is_file():
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        generated = secrets.token_urlsafe(48)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Windows tidak selalu mendukung chmod; bukan kegagalan fatal.
            pass
        return generated


settings = LanSettings()

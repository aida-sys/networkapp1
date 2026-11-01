"""Buat atau perbarui skema database pusat POS LAN.

Memakai metadata model desktop, jadi skema LAN selalu identik dengan skema
standalone. Tabel tambahan milik server (`api_idempotency`) dibuat di sini.

Aman dijalankan berulang: `create_all` tidak menghapus data yang sudah ada.
Untuk database yang sudah punya data standalone, gunakan
`lan_server/migrate_from_standalone.py`, bukan skrip ini.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import Base  # noqa: E402
import app.models.entities  # noqa: E402,F401  (registrasi 37 tabel POS)
from lan_server import idempotency  # noqa: E402,F401  (registrasi tabel server)
from lan_server.config import settings  # noqa: E402
from lan_server.database import LanBase, engine  # noqa: E402


def main() -> int:
    print(f"Database pusat: {settings.resolved_database_path}")
    # Dua metadata: skema POS (37 tabel, sama dengan desktop) + tabel server.
    Base.metadata.create_all(bind=engine)
    LanBase.metadata.create_all(bind=engine)
    pos_tables = sorted(Base.metadata.tables.keys())
    server_tables = sorted(LanBase.metadata.tables.keys())
    print(
        f"Skema siap. {len(pos_tables)} tabel POS + "
        f"{len(server_tables)} tabel server = "
        f"{len(pos_tables) + len(server_tables)} tabel."
    )
    if len(pos_tables) < 2:
        print("[X] Model POS tidak terdaftar; skema tidak lengkap.")
        return 1

    # Data dasar yang di desktop dibuat oleh migrasi Alembic. Tanpa ini
    # checkout pertama gagal karena akun 4000 belum ada.
    from lan_server.bootstrap import bootstrap  # noqa: PLC0415
    from lan_server.database import SessionLocal  # noqa: PLC0415

    with SessionLocal() as session:
        report = bootstrap(session)
    print(f"Data dasar siap. Ditambahkan: {report.describe()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

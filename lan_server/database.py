"""Engine database pusat untuk POS LAN API.

Memakai model dan pragma SQLite yang sama dengan aplikasi desktop, supaya
skema tidak pernah berbeda antara standalone dan LAN.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.database import Base
from lan_server.config import settings


class LanBase(DeclarativeBase):
    """Metadata khusus server LAN.

    Tabel milik server (mis. `api_idempotency`) TIDAK boleh masuk ke
    `app.core.database.Base`, karena metadata itu dipakai aplikasi desktop dan
    jumlah tabelnya sudah dikunci oleh test skema. Memisahkan metadata menjaga
    skema standalone tetap 37 tabel persis.
    """

# Satu engine untuk seluruh proses. SQLite tidak boleh ditulis dari beberapa
# proses sekaligus, jadi server harus dijalankan dengan --workers 1.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _):
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={settings.db_busy_timeout_ms}")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_session() -> Session:
    return SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "Base",
    "LanBase",
    "SessionLocal",
    "engine",
    "get_session",
    "session_scope",
]

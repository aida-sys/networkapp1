"""Test bootstrap data dasar instalasi LAN.

Regresi yang dijaga: instalasi LAN baru pernah gagal checkout pertama dengan
"Akun wajib 4000 tidak ditemukan", karena bagan akun hanya dibuat oleh migrasi
Alembic desktop, bukan oleh `create_all` milik server LAN.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import Account, Category, PaymentMethod, Role, Store, Unit
from lan_server.bootstrap import DEFAULT_ACCOUNTS, bootstrap


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_bootstrap_creates_all_default_accounts(session):
    report = bootstrap(session)
    codes = set(session.scalars(select(Account.code)))
    expected = {code for code, _n, _t, _s in DEFAULT_ACCOUNTS}
    assert expected <= codes
    assert report.accounts == len(DEFAULT_ACCOUNTS)


def test_bootstrap_creates_account_4000_used_by_checkout(session):
    bootstrap(session)
    account = session.scalar(select(Account).where(Account.code == "4000"))
    assert account is not None
    assert account.account_type == "REVENUE"


def test_bootstrap_creates_roles_payment_methods_store_and_defaults(session):
    bootstrap(session)
    assert {"OWNER", "ADMIN", "SUPERVISOR", "CASHIER"} <= set(
        session.scalars(select(Role.name))
    )
    assert {"CASH", "QRIS", "BANK", "EWALLET"} <= set(
        session.scalars(select(PaymentMethod.code))
    )
    assert session.scalar(select(Store)) is not None
    assert session.scalar(select(Category).where(Category.name == "Umum")) is not None
    assert session.scalar(select(Unit)) is not None


def test_bootstrap_is_idempotent(session):
    first = bootstrap(session)
    assert first.total() > 0

    second = bootstrap(session)
    assert second.total() == 0, "bootstrap kedua tidak boleh menambah baris"

    # Jumlah baris tetap sama setelah dua kali jalan.
    assert len(list(session.scalars(select(Account)))) == len(DEFAULT_ACCOUNTS)
    assert len(list(session.scalars(select(Role)))) == 4
    assert len(list(session.scalars(select(PaymentMethod)))) == 4
    assert len(list(session.scalars(select(Store)))) == 1


def test_bootstrap_does_not_duplicate_existing_store(session):
    session.add(Store(code="MAIN", name="Toko Sendiri"))
    session.commit()

    report = bootstrap(session, store_name="Toko Lain")
    assert report.store == 0
    stores = list(session.scalars(select(Store)))
    assert len(stores) == 1
    assert stores[0].name == "Toko Sendiri", "toko yang sudah ada tidak boleh ditimpa"

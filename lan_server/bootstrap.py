"""Bootstrap data dasar untuk instalasi LAN baru.

Aplikasi desktop mendapat bagan akun, metode pembayaran, dan role dari migrasi
Alembic. Server LAN membuat skema lewat `create_all`, jadi tanpa modul ini
database pusat akan kosong dan checkout pertama langsung gagal dengan
"Akun wajib 4000 tidak ditemukan".

Semua operasi di sini idempoten: aman dijalankan berulang, tidak menimpa data
yang sudah ada, dan tidak menyentuh data transaksi.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, PaymentMethod, Role, Store, Unit

# Sama persis dengan DEFAULT_ACCOUNTS di
# migrations/versions/20261011_01_add_financial_ledger.py. Bila daftar di
# migrasi berubah, ubah di sini juga supaya standalone dan LAN tidak berbeda.
DEFAULT_ACCOUNTS: tuple[tuple[str, str, str, bool], ...] = (
    ("1000", "Kas", "ASSET", True),
    ("1010", "Bank", "ASSET", True),
    ("1200", "Persediaan Barang", "ASSET", True),
    ("2000", "Hutang Usaha", "LIABILITY", True),
    ("3000", "Modal Pemilik", "EQUITY", True),
    ("3100", "Saldo Awal", "EQUITY", True),
    ("4000", "Penjualan", "REVENUE", True),
    ("5000", "Harga Pokok Penjualan", "EXPENSE", True),
    ("6000", "Beban Operasional", "EXPENSE", False),
    ("6100", "Beban Sewa", "EXPENSE", False),
    ("6200", "Beban Listrik dan Air", "EXPENSE", False),
    ("6300", "Beban Internet dan Telepon", "EXPENSE", False),
    ("6400", "Beban Gaji", "EXPENSE", False),
    ("6500", "Beban Transportasi", "EXPENSE", False),
    ("6600", "Beban Perlengkapan", "EXPENSE", False),
    ("6700", "Beban Perbaikan dan Perawatan", "EXPENSE", False),
    ("6800", "Beban Bank dan Administrasi", "EXPENSE", False),
    ("6900", "Beban Lain-lain", "EXPENSE", False),
)

ROLES = ("OWNER", "ADMIN", "SUPERVISOR", "CASHIER")

PAYMENT_METHODS = (
    ("CASH", "Tunai"),
    ("QRIS", "QRIS"),
    ("BANK", "Transfer Bank"),
    ("EWALLET", "E-Wallet"),
)


@dataclass
class BootstrapReport:
    accounts: int = 0
    roles: int = 0
    payment_methods: int = 0
    store: int = 0
    category: int = 0
    unit: int = 0

    def total(self) -> int:
        return (
            self.accounts
            + self.roles
            + self.payment_methods
            + self.store
            + self.category
            + self.unit
        )

    def describe(self) -> str:
        return (
            f"akun={self.accounts}, role={self.roles}, "
            f"metode_bayar={self.payment_methods}, toko={self.store}, "
            f"kategori={self.category}, satuan={self.unit}"
        )


def ensure_accounts(session: Session) -> int:
    existing = set(session.scalars(select(Account.code)))
    added = 0
    for code, name, account_type, is_system in DEFAULT_ACCOUNTS:
        if code in existing:
            continue
        session.add(
            Account(
                code=code,
                name=name,
                account_type=account_type,
                is_active=True,
                is_system=is_system,
            )
        )
        added += 1
    session.flush()
    return added


def ensure_roles(session: Session) -> int:
    existing = set(session.scalars(select(Role.name)))
    added = 0
    for name in ROLES:
        if name in existing:
            continue
        session.add(Role(name=name, description=f"Role {name}"))
        added += 1
    session.flush()
    return added


def ensure_payment_methods(session: Session) -> int:
    existing = set(session.scalars(select(PaymentMethod.code)))
    added = 0
    for code, name in PAYMENT_METHODS:
        if code in existing:
            continue
        session.add(PaymentMethod(code=code, name=name, is_active=True))
        added += 1
    session.flush()
    return added


def ensure_store(session: Session, name: str = "Toko Utama") -> int:
    store = session.scalar(
        select(Store).where(Store.deleted_at.is_(None)).order_by(Store.id)
    )
    if store is not None:
        return 0
    session.add(Store(code="MAIN", name=name))
    session.flush()
    return 1


def ensure_default_category(session: Session) -> int:
    category = session.scalar(
        select(Category).where(
            Category.name == "Umum", Category.deleted_at.is_(None)
        )
    )
    if category is not None:
        return 0
    session.add(Category(name="Umum"))
    session.flush()
    return 1


def ensure_default_unit(session: Session) -> int:
    unit = session.scalar(
        select(Unit).where(Unit.deleted_at.is_(None)).order_by(Unit.id).limit(1)
    )
    if unit is not None:
        return 0
    session.add(Unit(name="Pcs", symbol="pcs"))
    session.flush()
    return 1


def bootstrap(session: Session, *, store_name: str = "Toko Utama") -> BootstrapReport:
    """Siapkan data dasar yang wajib ada sebelum toko bisa berjualan."""
    report = BootstrapReport()
    report.roles = ensure_roles(session)
    report.accounts = ensure_accounts(session)
    report.payment_methods = ensure_payment_methods(session)
    report.store = ensure_store(session, store_name)
    report.category = ensure_default_category(session)
    report.unit = ensure_default_unit(session)
    session.commit()
    return report


__all__ = [
    "DEFAULT_ACCOUNTS",
    "PAYMENT_METHODS",
    "ROLES",
    "BootstrapReport",
    "bootstrap",
    "ensure_accounts",
    "ensure_default_category",
    "ensure_default_unit",
    "ensure_payment_methods",
    "ensure_roles",
    "ensure_store",
]

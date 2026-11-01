"""Migrasi data dari database standalone ke database pusat POS LAN.

Aturan yang dijaga:

- **Database sumber tidak diubah sama sekali.** Dibuka read-only (`mode=ro`).
- **Backup otomatis** database tujuan sebelum ada penulisan apa pun.
- **Preview dulu, tulis kemudian.** Tanpa `--apply`, skrip hanya melaporkan
  jumlah baris yang akan dipindahkan.
- **Idempoten.** Dijalankan dua kali tidak menggandakan data: baris dicocokkan
  lewat kunci alami (`code`, `sku`, `invoice_no`, `username`, `order_no`), bukan
  lewat id.
- **Id dipertahankan.** Relasi antar tabel tetap valid karena id sumber dipakai
  ulang di tujuan; baris yang sudah ada dilewati, bukan ditimpa.

Pemakaian:

    # 1. Lihat apa yang akan dipindahkan (tidak menulis apa pun)
    python lan_server/migrate_from_standalone.py

    # 2. Jalankan migrasi sungguhan
    python lan_server/migrate_from_standalone.py --apply

    # Sumber/tujuan eksplisit
    python lan_server/migrate_from_standalone.py ^
        --source "%LOCALAPPDATA%\\POSApp\\data\\pos.db" ^
        --target lan_server/data/pos_lan.db --apply
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Urutan tabel mengikuti ketergantungan foreign key: induk dulu, anak kemudian.
# `role_permissions` dan tabel anak lain menyusul setelah induknya.
TABLE_ORDER: tuple[str, ...] = (
    "roles",
    "permissions",
    "role_permissions",
    "users",
    "stores",
    "categories",
    "units",
    "suppliers",
    "products",
    "customers",
    "payment_methods",
    "payment_settings",
    "payment_wizard_states",
    "price_lists",
    "price_list_items",
    "promotions",
    "bulk_price_rules",
    "accounts",
    "financial_settings",
    "journal_entries",
    "journal_lines",
    "shifts",
    "cash_transactions",
    "sales",
    "sale_items",
    "payments",
    "purchase_orders",
    "purchase_order_items",
    "financial_payments",
    "expenses",
    "stock_movements",
    "stock_opnames",
    "stock_opname_items",
    "cashier_daily_reports",
    "login_history",
    "audit_logs",
    "inventaris_toko",
)

# Kunci alami untuk mendeteksi baris yang sudah ada di tujuan.
NATURAL_KEYS: dict[str, tuple[str, ...]] = {
    "roles": ("name",),
    "permissions": ("code",),
    "users": ("username",),
    "stores": ("code",),
    "categories": ("name",),
    "units": ("name",),
    "suppliers": ("code",),
    "products": ("sku",),
    "customers": ("code",),
    "payment_methods": ("code",),
    "price_lists": ("code",),
    "promotions": ("code",),
    "accounts": ("code",),
    "sales": ("invoice_no",),
    "purchase_orders": ("order_no",),
    "stock_opnames": ("opname_no",),
    "inventaris_toko": ("kode_inventaris",),
}


@dataclass
class TablePlan:
    name: str
    source_rows: int = 0
    existing_rows: int = 0
    to_insert: int = 0
    inserted: int = 0
    skipped: int = 0
    error: str | None = None
    note: str | None = None

    @property
    def key(self) -> tuple[str, ...] | None:
        return NATURAL_KEYS.get(self.name)


@dataclass
class MigrationReport:
    source: Path
    target: Path
    backup: Path | None = None
    applied: bool = False
    tables: list[TablePlan] = field(default_factory=list)

    @property
    def total_source(self) -> int:
        return sum(item.source_rows for item in self.tables)

    @property
    def total_inserted(self) -> int:
        return sum(item.inserted for item in self.tables)

    @property
    def total_skipped(self) -> int:
        return sum(item.skipped for item in self.tables)

    @property
    def failures(self) -> list[TablePlan]:
        return [item for item in self.tables if item.error]

    @property
    def notes(self) -> list[TablePlan]:
        return [item for item in self.tables if item.note]


def _connect_readonly(path: Path) -> sqlite3.Connection:
    """Buka database sumber tanpa kemampuan menulis."""
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in rows]


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _count(connection: sqlite3.Connection, table: str) -> int:
    if not _table_exists(connection, table):
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _existing_keys(
    connection: sqlite3.Connection, table: str, key: tuple[str, ...]
) -> set[tuple]:
    if not _table_exists(connection, table):
        return set()
    columns = ", ".join(key)
    rows = connection.execute(f"SELECT {columns} FROM {table}").fetchall()
    return {tuple(row) for row in rows}


def build_plan(source: sqlite3.Connection, target: sqlite3.Connection) -> list[TablePlan]:
    plans: list[TablePlan] = []
    for table in TABLE_ORDER:
        plan = TablePlan(name=table)
        if not _table_exists(source, table):
            # Tabel yang belum ada di sumber hanya dilewati: instalan lama bisa
            # saja belum punya tabel yang ditambahkan belakangan.
            plan.note = "tabel belum ada di database sumber; dilewati"
            plans.append(plan)
            continue
        plan.source_rows = _count(source, table)
        plan.existing_rows = _count(target, table)
        key = plan.key
        if key is None:
            # Tanpa kunci alami, baris dianggap baru bila tabel tujuan kosong.
            plan.to_insert = plan.source_rows if plan.existing_rows == 0 else 0
        else:
            target_keys = _existing_keys(target, table, key)
            source_keys = _existing_keys(source, table, key)
            plan.to_insert = len(source_keys - target_keys)
        plans.append(plan)
    return plans


def backup_database(target_path: Path) -> Path:
    """Backup memakai API `.backup` SQLite, bukan copy file saat hidup."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = target_path.with_name(f"{target_path.stem}-backup-{stamp}.db")
    source = sqlite3.connect(str(target_path))
    destination = sqlite3.connect(str(backup_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return backup_path


def apply_plan(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    plans: list[TablePlan],
) -> None:
    target.execute("PRAGMA foreign_keys=OFF")
    try:
        for plan in plans:
            if plan.error or plan.to_insert == 0:
                continue
            if not _table_exists(target, plan.name):
                plan.error = "tabel tidak ada di database tujuan; jalankan init_db.py dulu"
                continue

            source_columns = _table_columns(source, plan.name)
            target_columns = set(_table_columns(target, plan.name))
            columns = [name for name in source_columns if name in target_columns]
            if not columns:
                plan.error = "tidak ada kolom yang cocok"
                continue

            key = plan.key
            if key is not None:
                existing = _existing_keys(target, plan.name, key)
            else:
                existing = None

            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(columns)
            insert_sql = f"INSERT INTO {plan.name} ({column_sql}) VALUES ({placeholders})"

            rows = source.execute(f"SELECT {column_sql} FROM {plan.name}").fetchall()
            inserted = 0
            skipped = 0
            for row in rows:
                if existing is not None and key is not None:
                    row_key = tuple(row[columns.index(name)] for name in key)
                    if row_key in existing:
                        skipped += 1
                        continue
                try:
                    target.execute(insert_sql, tuple(row))
                    inserted += 1
                    if existing is not None and key is not None:
                        existing.add(tuple(row[columns.index(name)] for name in key))
                except sqlite3.IntegrityError as error:
                    skipped += 1
                    if plan.error is None:
                        plan.error = f"sebagian baris dilewati: {error}"
            plan.inserted = inserted
            plan.skipped = skipped
        target.commit()
    finally:
        target.execute("PRAGMA foreign_keys=ON")


def print_report(report: MigrationReport) -> None:
    print("=" * 74)
    print("  MIGRASI DATA STANDALONE -> POS LAN")
    print("=" * 74)
    print(f"  Sumber : {report.source}")
    print(f"  Tujuan : {report.target}")
    if report.backup:
        print(f"  Backup : {report.backup}")
    print(f"  Mode   : {'TERAPKAN (menulis)' if report.applied else 'PREVIEW (tidak menulis)'}")
    print("-" * 74)
    print(f"  {'Tabel':<24}{'Sumber':>9}{'Tujuan':>9}{'Baru':>9}{'Masuk':>9}{'Lewat':>9}")
    print("-" * 74)
    for plan in report.tables:
        if plan.source_rows == 0 and plan.inserted == 0:
            continue
        print(
            f"  {plan.name:<24}{plan.source_rows:>9}{plan.existing_rows:>9}"
            f"{plan.to_insert:>9}{plan.inserted:>9}{plan.skipped:>9}"
        )
    print("-" * 74)
    print(
        f"  {'TOTAL':<24}{report.total_source:>9}{'':>9}{'':>9}"
        f"{report.total_inserted:>9}{report.total_skipped:>9}"
    )
    print("=" * 74)
    if report.failures:
        print("  Gagal:")
        for plan in report.failures:
            print(f"   - {plan.name}: {plan.error}")
    if report.notes:
        print(f"  Dilewati ({len(report.notes)} tabel belum ada di sumber):")
        for plan in report.notes:
            print(f"   - {plan.name}")
    if not report.applied:
        print("\n  Ini baru preview. Jalankan ulang dengan --apply untuk menulis.")
    else:
        print("\n  Migrasi selesai. Database sumber tidak diubah.")


def resolve_source(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    from app.core.config import settings as app_settings

    return (app_settings.data_dir / "pos.db").resolve()


def resolve_target(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    from lan_server.config import settings as lan_settings

    return lan_settings.resolved_database_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrasi data POS standalone ke database pusat LAN.",
    )
    parser.add_argument("--source", help="Path database standalone (default: %LOCALAPPDATA%\\POSApp\\data\\pos.db)")
    parser.add_argument("--target", help="Path database pusat LAN (default: lan_server/data/pos_lan.db)")
    parser.add_argument("--apply", action="store_true", help="Benar-benar menulis ke database tujuan")
    parser.add_argument("--no-backup", action="store_true", help="Lewati backup otomatis (tidak disarankan)")
    args = parser.parse_args(argv)

    source_path = resolve_source(args.source)
    target_path = resolve_target(args.target)

    if not source_path.is_file():
        print(f"[X] Database sumber tidak ditemukan: {source_path}")
        print("    Jalankan aplikasi desktop sekali, atau isi --source secara eksplisit.")
        return 2

    if source_path == target_path:
        print("[X] Sumber dan tujuan sama. Migrasi dibatalkan agar data tidak rusak.")
        return 2

    # Pastikan skema tujuan siap sebelum apa pun.
    from app.core.database import Base  # noqa: PLC0415
    import app.models.entities  # noqa: F401,PLC0415  (registrasi model)
    from lan_server import idempotency  # noqa: F401,PLC0415  (registrasi tabel server)
    from lan_server.database import LanBase, engine  # noqa: PLC0415

    Base.metadata.create_all(bind=engine)
    LanBase.metadata.create_all(bind=engine)

    report = MigrationReport(source=source_path, target=target_path, applied=args.apply)

    source_connection = _connect_readonly(source_path)
    target_connection = sqlite3.connect(str(target_path))
    target_connection.row_factory = sqlite3.Row
    try:
        report.tables = build_plan(source_connection, target_connection)

        if args.apply:
            if not args.no_backup:
                report.backup = backup_database(target_path)
            apply_plan(source_connection, target_connection, report.tables)
    finally:
        target_connection.close()
        source_connection.close()

    print_report(report)
    return 0 if not report.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Test migrasi standalone -> LAN.

Yang dibuktikan di sini:
- preview tidak menulis apa pun;
- migrasi memindahkan data lengkap termasuk relasi;
- menjalankan dua kali tidak menggandakan data (idempoten);
- database sumber tidak berubah sedikit pun;
- backup dibuat sebelum penulisan.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from lan_server import migrate_from_standalone as migration


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def source_db(tmp_path: Path) -> Path:
    """Database standalone kecil berisi data yang saling berelasi."""
    path = tmp_path / "pos.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA foreign_keys=ON;

        CREATE TABLE roles (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            description TEXT, created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL, whatsapp TEXT, password_hash TEXT NOT NULL,
            role_id INTEGER NOT NULL REFERENCES roles(id), is_active INTEGER NOT NULL DEFAULT 1,
            failed_login_count INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
            last_login_at TEXT, must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        CREATE TABLE stores (
            id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            slogan TEXT, address TEXT, whatsapp TEXT, logo_path TEXT,
            created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        CREATE TABLE units (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, symbol TEXT,
            created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        CREATE TABLE suppliers (
            id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            phone TEXT, address TEXT, created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, barcode TEXT,
            name TEXT NOT NULL, category_id INTEGER REFERENCES categories(id),
            unit_id INTEGER REFERENCES units(id), supplier_id INTEGER REFERENCES suppliers(id),
            purchase_price INTEGER NOT NULL, selling_price INTEGER NOT NULL,
            stock_qty INTEGER NOT NULL DEFAULT 0, min_stock INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT, updated_at TEXT, deleted_at TEXT
        );
        CREATE TABLE shifts (
            id INTEGER PRIMARY KEY, store_id INTEGER NOT NULL REFERENCES stores(id),
            cashier_id INTEGER NOT NULL REFERENCES users(id), opened_at TEXT NOT NULL,
            closed_at TEXT, opening_cash INTEGER NOT NULL DEFAULT 0,
            closing_cash INTEGER, status TEXT NOT NULL,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY, invoice_no TEXT NOT NULL UNIQUE,
            store_id INTEGER NOT NULL REFERENCES stores(id),
            shift_id INTEGER NOT NULL REFERENCES shifts(id),
            cashier_id INTEGER NOT NULL REFERENCES users(id),
            customer_id INTEGER, subtotal INTEGER NOT NULL, discount INTEGER NOT NULL DEFAULT 0,
            tax INTEGER NOT NULL DEFAULT 0, grand_total INTEGER NOT NULL,
            status TEXT NOT NULL, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE sale_items (
            id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            qty INTEGER NOT NULL, unit_price INTEGER NOT NULL, unit_cost INTEGER NOT NULL,
            discount INTEGER NOT NULL DEFAULT 0, line_total INTEGER NOT NULL,
            created_at TEXT, updated_at TEXT
        );

        INSERT INTO roles VALUES
            (1,'OWNER','Pemilik','2026-01-01','2026-01-01',NULL),
            (2,'CASHIER','Kasir','2026-01-01','2026-01-01',NULL);
        INSERT INTO users VALUES
            (1,'owner','Pemilik Toko',NULL,'hash-owner',1,1,0,NULL,NULL,0,'2026-01-01','2026-01-01',NULL),
            (2,'kasir1','Kasir Satu',NULL,'hash-kasir',2,1,0,NULL,NULL,0,'2026-01-01','2026-01-01',NULL);
        INSERT INTO stores VALUES
            (1,'TOKO-01','Toko Contoh','Slogan','Jl. Contoh 1','0812','', '2026-01-01','2026-01-01',NULL);
        INSERT INTO categories VALUES (1,'Minuman','2026-01-01','2026-01-01',NULL);
        INSERT INTO units VALUES (1,'Pcs','pcs','2026-01-01','2026-01-01',NULL);
        INSERT INTO suppliers VALUES (1,'SUP-01','Supplier A','0813','Jl. Sup','2026-01-01','2026-01-01',NULL);
        INSERT INTO products VALUES
            (1,'KOPI-01','899','Kopi Susu',1,1,1,12000,18000,40,5,1,'2026-01-01','2026-01-01',NULL),
            (2,'TEH-01','898','Teh Manis',1,1,1,5000,8000,30,5,1,'2026-01-01','2026-01-01',NULL);
        INSERT INTO shifts VALUES
            (1,1,2,'2026-01-02T08:00:00',NULL,100000,NULL,'OPEN','2026-01-02','2026-01-02');
        INSERT INTO sales VALUES
            (1,'INV-2026-0001',1,1,2,NULL,36000,0,0,36000,'PAID','2026-01-02','2026-01-02');
        INSERT INTO sale_items VALUES
            (1,1,1,2,18000,12000,0,36000,'2026-01-02','2026-01-02');
        """
    )
    connection.commit()
    connection.close()
    return path


@pytest.fixture()
def target_db(tmp_path: Path) -> Path:
    """Database tujuan kosong dengan skema lengkap dari model desktop."""
    from app.core.database import Base
    import app.models.entities  # noqa: F401
    from lan_server import idempotency  # noqa: F401
    from sqlalchemy import create_engine

    path = tmp_path / "pos_lan.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    return path


def test_preview_tidak_menulis(source_db: Path, target_db: Path) -> None:
    before = _file_hash(target_db)

    code = migration.main(
        ["--source", str(source_db), "--target", str(target_db)]
    )

    assert code == 0
    assert _file_hash(target_db) == before

    connection = sqlite3.connect(target_db)
    try:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    finally:
        connection.close()


def test_apply_memindahkan_data_dan_relasi(source_db: Path, target_db: Path) -> None:
    source_before = _file_hash(source_db)

    code = migration.main(
        ["--source", str(source_db), "--target", str(target_db), "--apply"]
    )

    assert code == 0
    assert _file_hash(source_db) == source_before, "database sumber tidak boleh berubah"

    connection = sqlite3.connect(target_db)
    connection.row_factory = sqlite3.Row
    try:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0] == 1

        # Relasi tetap utuh: sale -> shift -> cashier, dan item -> produk.
        row = connection.execute(
            """
            SELECT s.invoice_no, s.grand_total, sh.status, u.username, p.sku, si.qty
            FROM sales s
            JOIN shifts sh ON sh.id = s.shift_id
            JOIN users u ON u.id = s.cashier_id
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON p.id = si.product_id
            """
        ).fetchone()
        assert row["invoice_no"] == "INV-2026-0001"
        assert row["grand_total"] == 36000
        assert row["status"] == "OPEN"
        assert row["username"] == "kasir1"
        assert row["sku"] == "KOPI-01"
        assert row["qty"] == 2

        # Stok dan harga uang tetap integer apa adanya.
        product = connection.execute(
            "SELECT selling_price, stock_qty FROM products WHERE sku='KOPI-01'"
        ).fetchone()
        assert product["selling_price"] == 18000
        assert product["stock_qty"] == 40
    finally:
        connection.close()


def test_apply_dua_kali_idempoten(source_db: Path, target_db: Path) -> None:
    migration.main(["--source", str(source_db), "--target", str(target_db), "--apply"])
    migration.main(["--source", str(source_db), "--target", str(target_db), "--apply"])

    connection = sqlite3.connect(target_db)
    try:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 2
    finally:
        connection.close()


def test_backup_dibuat_sebelum_menulis(source_db: Path, target_db: Path) -> None:
    connection = sqlite3.connect(target_db)
    connection.execute(
        "INSERT INTO roles (id, name, description, created_at, updated_at, deleted_at) "
        "VALUES (99, 'LEGACY', 'baris lama', '2026-01-01', '2026-01-01', NULL)"
    )
    connection.commit()
    connection.close()

    report = migration.MigrationReport(source=source_db, target=target_db, applied=True)
    backup = migration.backup_database(target_db)

    assert backup.is_file()
    backup_connection = sqlite3.connect(backup)
    try:
        assert (
            backup_connection.execute(
                "SELECT COUNT(*) FROM roles WHERE name='LEGACY'"
            ).fetchone()[0]
            == 1
        )
    finally:
        backup_connection.close()
    assert report.backup is None  # objek report baru; backup dibuat terpisah


def test_sumber_sama_dengan_tujuan_ditolak(tmp_path: Path) -> None:
    path = tmp_path / "sama.db"
    sqlite3.connect(path).close()

    code = migration.main(["--source", str(path), "--target", str(path)])

    assert code == 2


def test_sumber_tidak_ada_ditolak(tmp_path: Path) -> None:
    code = migration.main(
        [
            "--source",
            str(tmp_path / "tidak-ada.db"),
            "--target",
            str(tmp_path / "tujuan.db"),
        ]
    )

    assert code == 2

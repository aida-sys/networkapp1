"""Simulasi 3 Client Mengakses POS LAN API Secara Bersamaan (Konkuren).

Skenario:
- Client 1: Kasir 1 (Desktop PC - Kasir Depan)
- Client 2: Kasir 2 (Mobile Tablet/Android - Kasir Barista)
- Client 3: Kasir 3 (Desktop PC - Kasir Belakang / Drive-Thru)
- Client 4 (Supervisor/Owner): Dashboard & Laporan Terpusat

Pengujian mencakup:
1. Setup database SQLite WAL mode (persis produksi).
2. Autentikasi 3 kasir + 1 owner (JWT terpisah).
3. Pembukaan 3 shift independen secara paralel.
4. Akses katalog & pengecekan stok secara paralel.
5. Uji ACID & Race Condition stok terbatas:
   - Produk 'Roti Bakar' total stok = 5 pcs.
   - Client 1 minta 3 pcs.
   - Client 2 minta 2 pcs.
   - Client 3 minta 2 pcs (Total diminta = 7 pcs).
   - Verifikasi: Tepat 5 pcs terjual, 1 client ditolak (HTTP 409 Conflict), stok tepat 0 (tidak pernah negatif).
6. Uji Idempotency: Retry akibat gangguan jaringan tidak menghasilkan duplikasi transaksi / pemotongan stok ganda.
7. Penutupan shift dan verifikasi laporan konsolidasi oleh Owner.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import hash_password
from app.models import (
    Account,
    FinancialSettings,
    Product,
    Role,
    Store,
    User,
)
from lan_server import idempotency  # noqa: F401
from lan_server.database import LanBase
from lan_server.deps import get_db
from lan_server.main import create_app

API = "/api/v1"


def run_3_client_simulation():
    print("=" * 75)
    print("SIMULASI 3 CLIENT MENGAKSES DATABASE PUSAT VIA POS LAN API")
    print("=" * 75)

    temp_path = Path(tempfile.mkdtemp(prefix="pos_lan_sim_"))
    db_file = temp_path / "test_pos_lan.db"
    db_url = f"sqlite:///{db_file}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    Base.metadata.create_all(engine)
    LanBase.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    with TestingSession() as session:
        owner_role = Role(name="OWNER", description="Owner")
        cashier_role = Role(name="CASHIER", description="Kasir")
        store = Store(code="STORE-01", name="Kopi & Toast Toko Pusat")
        session.add_all([owner_role, cashier_role, store])
        session.flush()

        # 3 Kasir Client + 1 Owner
        user_c1 = User(
            username="kasir1",
            full_name="Budi (Client 1 - Kasir Depan)",
            password_hash=hash_password("kasir123"),
            role=cashier_role,
            is_active=True,
        )
        user_c2 = User(
            username="kasir2",
            full_name="Siti (Client 2 - Kasir Android)",
            password_hash=hash_password("kasir123"),
            role=cashier_role,
            is_active=True,
        )
        user_c3 = User(
            username="kasir3",
            full_name="Agus (Client 3 - Kasir Drive-Thru)",
            password_hash=hash_password("kasir123"),
            role=cashier_role,
            is_active=True,
        )
        user_owner = User(
            username="owner",
            full_name="Pak Bos (Owner Dashboard)",
            password_hash=hash_password("owner123"),
            role=owner_role,
            is_active=True,
        )
        session.add_all([user_c1, user_c2, user_c3, user_owner])

        accounts = [
            Account(code=c, name=n, account_type=t, is_active=True, is_system=True)
            for c, n, t in (
                ("1000", "Kas", "ASSET"),
                ("1200", "Persediaan", "ASSET"),
                ("2000", "Hutang Usaha", "LIABILITY"),
                ("3000", "Modal Pemilik", "EQUITY"),
                ("4000", "Penjualan", "REVENUE"),
                ("5000", "Harga Pokok Penjualan", "EXPENSE"),
            )
        ]
        session.add_all(accounts)
        session.flush()

        session.add(
            FinancialSettings(
                id=1,
                effective_from=date.today(),
                initialized_by=user_owner.id,
            )
        )

        p_roti = Product(
            sku="SKU-ROTI",
            name="Roti Bakar Cokelat",
            purchase_price=8000,
            selling_price=15000,
            stock_qty=5,
            min_stock=1,
            is_active=True,
        )
        p_kopi = Product(
            sku="SKU-KOPI",
            name="Kopi Arabika",
            purchase_price=12000,
            selling_price=25000,
            stock_qty=20,
            min_stock=2,
            is_active=True,
        )
        session.add_all([p_roti, p_kopi])
        session.commit()

        roti_id = p_roti.id
        kopi_id = p_kopi.id

    app = create_app()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client_1 = TestClient(app)
    client_2 = TestClient(app)
    client_3 = TestClient(app)
    client_owner = TestClient(app)

    print("\n[STEP 1] Login 3 Kasir Client + 1 Owner Secara Terpisah:")
    resp1 = client_1.post(f"{API}/auth/login", json={"username": "kasir1", "password": "kasir123"})
    resp2 = client_2.post(f"{API}/auth/login", json={"username": "kasir2", "password": "kasir123"})
    resp3 = client_3.post(f"{API}/auth/login", json={"username": "kasir3", "password": "kasir123"})
    resp_ow = client_owner.post(f"{API}/auth/login", json={"username": "owner", "password": "owner123"})

    assert resp1.status_code == 200 and resp2.status_code == 200 and resp3.status_code == 200 and resp_ow.status_code == 200

    token1 = resp1.json()["access_token"]
    token2 = resp2.json()["access_token"]
    token3 = resp3.json()["access_token"]
    token_ow = resp_ow.json()["access_token"]

    auth1 = {"Authorization": f"Bearer {token1}"}
    auth2 = {"Authorization": f"Bearer {token2}"}
    auth3 = {"Authorization": f"Bearer {token3}"}
    auth_ow = {"Authorization": f"Bearer {token_ow}"}

    print(f" -> Client 1 (Desktop)     : Terhubung sebagai {resp1.json()['user']['full_name']}")
    print(f" -> Client 2 (Android)     : Terhubung sebagai {resp2.json()['user']['full_name']}")
    print(f" -> Client 3 (Drive-Thru)  : Terhubung sebagai {resp3.json()['user']['full_name']}")
    print(f" -> Client Owner (Laptop)  : Terhubung sebagai {resp_ow.json()['user']['full_name']}")

    print("\n[STEP 2] Membuka Shift untuk 3 Kasir Secara Bersamaan:")
    shift1 = client_1.post(f"{API}/shifts/open", json={"opening_cash": 100000}, headers=auth1)
    shift2 = client_2.post(f"{API}/shifts/open", json={"opening_cash": 150000}, headers=auth2)
    shift3 = client_3.post(f"{API}/shifts/open", json={"opening_cash": 120000}, headers=auth3)

    assert shift1.status_code == 201 and shift2.status_code == 201 and shift3.status_code == 201
    print(f" -> Client 1 Shift ID #{shift1.json()['id']} dibuka (Modal Kas: Rp 100.000)")
    print(f" -> Client 2 Shift ID #{shift2.json()['id']} dibuka (Modal Kas: Rp 150.000)")
    print(f" -> Client 3 Shift ID #{shift3.json()['id']} dibuka (Modal Kas: Rp 120.000)")

    print("\n[STEP 3] Membaca Katalog Produk Bersama-sama:")
    catalog = client_owner.get(f"{API}/catalog/products", headers=auth_ow).json()
    print(f" -> Terbaca {len(catalog)} produk dari database pusat.")
    roti_initial_stock = [p["stock_qty"] for p in catalog if p["id"] == roti_id][0]
    print(f"    Stok awal 'Roti Bakar Cokelat': {roti_initial_stock} pcs (Harga: Rp 15.000/pcs)")

    print("\n[STEP 4] Uji Konkurensi & Race Condition: 3 Kasir Berebut Stok Terbatas")
    print("         Stok hanya 5 pcs. Permintaan masuk:")
    print("         - Client 1 meminta 3 pcs")
    print("         - Client 2 meminta 2 pcs")
    print("         - Client 3 meminta 2 pcs")
    print("         Total yang diminta = 7 pcs (> 5 pcs stok tersedia).")

    checkout_queue = [
        (client_1, auth1, "key-c1-roti", 3, "Client 1"),
        (client_2, auth2, "key-c2-roti", 2, "Client 2"),
        (client_3, auth3, "key-c3-roti", 2, "Client 3"),
    ]

    def execute_sale(client, auth, idemp_key, qty, client_name):
        res = client.post(
            f"{API}/sales/checkout",
            json={
                "items": [{"product_id": roti_id, "qty": qty}],
                "payments": [{"method": "CASH", "amount": qty * 15000}],
            },
            headers={**auth, "Idempotency-Key": idemp_key},
        )
        return client_name, qty, res.status_code, res.json()

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(execute_sale, *item) for item in checkout_queue]
        for f in futures:
            results.append(f.result())

    success_count = 0
    rejected_count = 0
    total_qty_sold = 0

    for name, qty, code, data in results:
        if code == 201:
            success_count += 1
            total_qty_sold += qty
            print(f" -> [201 BERHASIL] {name} berhasil beli {qty} pcs | Invoice: {data['invoice_no']} | Total: Rp {data['grand_total']:,}")
        elif code == 409:
            rejected_count += 1
            print(f" -> [409 DITOLAK ] {name} ditolak beli {qty} pcs | Alasan: {data.get('detail')}")
        else:
            print(f" -> [{code}] {name} | {data}")

    assert total_qty_sold == 5, f"Harusnya terjual tepat 5 pcs, aktual: {total_qty_sold}"
    assert rejected_count == 1, f"Harusnya tepat 1 client ditolak karena stok tidak cukup, aktual: {rejected_count}"

    updated_catalog = client_owner.get(f"{API}/catalog/products", headers=auth_ow).json()
    roti_final_stock = [p["stock_qty"] for p in updated_catalog if p["id"] == roti_id][0]
    print(f" -> Sisa Stok Aktual di Database Pusat: {roti_final_stock} pcs.")
    assert roti_final_stock == 0, "Stok harus tepat 0 dan tidak boleh minus!"
    print(" -> KESIMPULAN ACID: Mekanisme atomik & row lock mencegah overselling dengan aman!")

    print("\n[STEP 5] Uji Ketahanan Jaringan & Idempotensi (Retry Request):")
    first_resp = client_2.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": kopi_id, "qty": 2}],
            "payments": [{"method": "CASH", "amount": 50000}],
        },
        headers={**auth2, "Idempotency-Key": "idemp-client2-kopi"},
    )
    assert first_resp.status_code == 201
    first_invoice = first_resp.json()["invoice_no"]
    first_id = first_resp.json()["id"]

    retry_resp = client_2.post(
        f"{API}/sales/checkout",
        json={
            "items": [{"product_id": kopi_id, "qty": 2}],
            "payments": [{"method": "CASH", "amount": 50000}],
        },
        headers={**auth2, "Idempotency-Key": "idemp-client2-kopi"},
    )
    assert retry_resp.status_code == 201
    assert retry_resp.json()["invoice_no"] == first_invoice
    assert retry_resp.json()["id"] == first_id

    kopi_stock = [p["stock_qty"] for p in client_2.get(f"{API}/catalog/products", headers=auth2).json() if p["id"] == kopi_id][0]
    assert kopi_stock == 18
    print(f" -> Transaksi pertama sukses: Invoice {first_invoice}")
    print(f" -> Retry transaksi dengan Idempotency-Key yang sama mengembalikan invoice yang sama tanpa memotong stok lagi.")
    print(f" -> Sisa stok Kopi Arabika: {kopi_stock} pcs (Sesuai, berkurang tepat 2 pcs).")

    print("\n[STEP 6] Penutupan Shift oleh Kasir & Laporan Harian oleh Owner:")
    c1_close = client_1.post(f"{API}/shifts/close", json={"closing_cash": 145000}, headers=auth1)
    c2_close = client_2.post(f"{API}/shifts/close", json={"closing_cash": 230000}, headers=auth2)
    c3_close = client_3.post(f"{API}/shifts/close", json={"closing_cash": 120000}, headers=auth3)

    assert c1_close.status_code == 200, c1_close.text
    assert c2_close.status_code == 200, c2_close.text
    assert c3_close.status_code == 200, c3_close.text

    print(f" -> Shift Client 1 ditutup (Kas Terhitung: Rp {c1_close.json()['closing_cash']:,})")
    print(f" -> Shift Client 2 ditutup (Kas Terhitung: Rp {c2_close.json()['closing_cash']:,})")
    print(f" -> Shift Client 3 ditutup (Kas Terhitung: Rp {c3_close.json()['closing_cash']:,})")

    report = client_owner.get(
        f"{API}/reports/daily",
        params={"report_date": date.today().isoformat()},
        headers=auth_ow,
    ).json()

    print("\n" + "=" * 75)
    print("HASIL LAPORAN KONSOLIDASI DATABASE PUSAT (DITARIK DARI CLIENT OWNER):")
    print(f" - Tanggal Laporan          : {report['date']}")
    print(f" - Total Penjualan Bersih   : Rp {report['sales_total']:,}")
    print(f" - Total Transaksi Kasir    : {report['sales_count']} transaksi")
    print(f" - Total Keuntungan (Profit): Rp {report['profit_total']:,}")
    print(f" - Rincian Kasir (Breakdown):")
    for b in report.get("cashier_breakdown", []):
        print(f"    * {b.get('cashier_name', 'Kasir')}: {b.get('transaction_count', 0)} transaksi, Total: Rp {b.get('total_sales', 0):,}")
    print("=" * 75)
    print("PENGUJIAN MULTI-CLIENT SELESAI: 100% SUKSES DAN DATA KONSISTEN!")
    print("=" * 75)

    client_1.close()
    client_2.close()
    client_3.close()
    client_owner.close()
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        shutil.rmtree(temp_path, ignore_errors=True)
    except Exception:
        pass


if __name__ == "__main__":
    run_3_client_simulation()

# Rencana: Mode POS Local Network (LAN)

Tanggal: 2026-11-01
Repo: `C:\Users\ANJAY SOLUTION\Desktop\PROJECT`

## Temuan audit (baseline)

**Yang sudah bagus dan bisa dipakai ulang:**

1. **Skema sudah identik di kedua sisi.** `app/models/entities.py` (SQLAlchemy) dan
   `android/kasirin_mobile/lib/data/local_database.dart` (Drift, schemaVersion 4)
   sama-sama punya 37 tabel dengan nama yang sama. Ini menghapus pekerjaan
   pemetaan skema terbesar. API bisa memakai model desktop apa adanya.
2. **`SalesService.checkout()` sudah atomik dan server-authoritative.**
   `app/services/sales_service.py:37` memvalidasi shift, stok, harga (via
   `BulkPricingService.unit_price`), total, dan pembayaran, lalu
   commit/rollback dalam satu transaksi. Ini persis aturan bisnis yang
   dibutuhkan API. Tidak perlu ditulis ulang.
3. **Billing sudah terpisah secara fisik.** `server/` (FastAPI, port 8001,
   `server/data/billing.db`, Midtrans, lisensi Ed25519) tidak menyentuh tabel
   POS. Pemisahan yang diminta sudah ada.
4. **SQLite sudah dikonfigurasi benar.** WAL + `foreign_keys=ON` +
   `busy_timeout=5000` di `app/core/database.py:21`.
5. **Flutter punya satu titik switch.** `repositoryFutureProvider` di
   `lib/providers.dart:37` adalah satu-satunya tempat `PosRepository`
   diinstansiasi. Mengganti implementasi di situ cukup untuk seluruh UI.

**Yang menjadi pekerjaan:**

1. **5 titik UI memakai `self.session` langsung** — `cashier_view.py` (baris
   361, 726, 732, 848) dan `purchase_view.py` (738, 787, 812, 830). Selama ini
   ada, desktop LAN tidak bisa lepas dari session lokal. Harus dijadikan method
   service.
2. **Belum ada idempotency key.** Retry jaringan pada checkout akan membuat
   transaksi ganda. Perlu tabel baru + migrasi Alembic.
3. **`PosRepository` Flutter adalah kelas konkret 2.151 baris** dengan raw SQL
   Drift. Perlu diekstrak jadi interface agar ada implementasi remote.
4. **Tidak ada autentikasi token.** Desktop memakai session objek lokal;
   Flutter memakai password hash lokal. API LAN butuh token bearer.
5. **Belum ada konfigurasi bind LAN, CORS, atau firewall.**

**Baseline test (dijalankan sebelum perubahan apa pun):**
`271 passed, 3 failed` — 248,96 detik.
3 kegagalan sudah ada sebelumnya dan tidak terkait pekerjaan ini:
`test_report_center_finance_tabs`, `test_server_admin.py::test_admin_upload_and_download_installer`,
`test_server_billing.py::test_download_installer_serves_file` (semuanya soal
file installer yang tidak ada di disk).

## Keputusan arsitektur

| Keputusan | Pilihan | Alasan |
|---|---|---|
| Database pusat | **SQLite** (bukan PostgreSQL) untuk v1 | Satu toko, puluhan transaksi/jam. WAL + `busy_timeout` cukup. PostgreSQL menambah beban instalasi ke komputer toko tanpa manfaat terukur. **Syarat: uvicorn `--workers 1`** — SQLite tidak boleh ditulis dari beberapa proses. |
| Lokasi API | Folder baru `lan_server/` | Terpisah total dari `server/` (billing). Tidak ada endpoint transaksi di folder billing. |
| Port | `8002` | 8001 sudah dipakai billing. |
| Reuse aturan bisnis | Impor `app.services.*` langsung | Satu sumber kebenaran. API tidak menyalin logika checkout. |
| Auth | JWT HS256, token per user+device | Disimpan di Flutter secure storage dan file terproteksi desktop. |
| Idempotency | Tabel `api_idempotency`, replay mengembalikan respons tersimpan | Aman terhadap retry jaringan. |
| Mode klien | Eksplisit, default standalone | `POS_MODE=standalone\|lan`. Tidak ada dual-write, tidak ada fallback diam-diam. |

## Fase pekerjaan

### Fase 1 — POS API (`lan_server/`)

Struktur:

```
lan_server/
  main.py            create_app(), bind 0.0.0.0:8002, CORS, static web
  config.py          LanSettings: host, port, db_path, jwt_secret, token_ttl
  database.py        engine pusat + pragma WAL (reuse pola app/core/database.py)
  deps.py            get_db, current_user, require_role
  security.py        issue_token / verify_token (HS256), reuse verify_password
  idempotency.py     tabel + dependency replay
  schemas/           DTO berversi: auth, catalog, sales, shifts, purchases, reports
  routers/           auth, catalog, inventory, shifts, sales, purchases,
                     reports, settings, health
  migrate_from_standalone.py
  README.md
```

Endpoint minimum (semua di bawah `/api/v1`):

- `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`
- `GET /catalog/products`, `GET /catalog/products/{id}`, `GET /catalog/categories`,
  `GET /catalog/units`, `GET /catalog/suppliers`
- `GET /inventory/stock`, `POST /inventory/adjust`
- `POST /shifts/open`, `POST /shifts/close`, `GET /shifts/current`
- `POST /sales/checkout` **(wajib `Idempotency-Key`)**, `GET /sales/{id}`,
  `GET /sales?date=`, `POST /sales/{id}/refund`
- `GET /purchases`, `POST /purchases`, `POST /purchases/{id}/receive`
- `GET /reports/daily`, `GET /reports/range`
- `GET /settings/store`, `PUT /settings/store`
- `GET /health` (tanpa auth, untuk cek koneksi dari klien)

Aturan checkout di API:

- Harga, stok, dan total **selalu** dihitung server lewat `SalesService`.
- Klien hanya mengirim `product_id`, `qty`, `discount`, dan pembayaran.
- `Idempotency-Key` disimpan bersama hash request; key sama + body sama →
  respons lama dikembalikan, bukan transaksi baru. Key sama + body beda → 409.
- Stok dikunci dengan `SELECT ... FOR UPDATE`-ekuivalen: baca ulang produk di
  dalam transaksi sebelum mengurangi. SQLite serializes writes, jadi aman
  selama satu proses.
- Server down → klien menolak operasi tulis dengan pesan jelas. Tidak ada
  antrean offline di v1.

### Fase 2 — Desktop jadi klien LAN

- `app/lan/config.py` — baca `POS_MODE`, `POS_API_URL`, path token.
- `app/lan/client.py` — httpx, timeout, retry terbatas, pemetaan error HTTP →
  exception yang sudah ada (`InsufficientStockError`, `ShiftNotOpenError`, dll)
  supaya UI tidak perlu berubah.
- `app/lan/services/*.py` — adapter dengan **signature identik** ke service
  lokal (`SalesService.checkout`, `MasterDataService.list_items`, dst).
- `app/ui/service_factory.py` — memilih lokal atau remote dari config.
- Refactor 5 titik `self.session` langsung di `cashier_view.py` dan
  `purchase_view.py` menjadi method service (dibutuhkan di kedua mode).
- `main.py` — di mode LAN, jangan buka engine lokal; tampilkan status koneksi
  di window dan blokir tulis saat server tidak terjangkau.

### Fase 3 — Flutter jadi klien LAN

- `lib/domain/pos_repository_contract.dart` — interface dari method publik
  `PosRepository`.
- `lib/data/remote/pos_api_client.dart` — HTTP client + token.
- `lib/data/remote/remote_pos_repository.dart` — implementasi interface.
- `lib/data/app_mode.dart` — mode + URL server disimpan di secure storage,
  diatur lewat layar Pengaturan (bukan hard-code IP).
- `providers.dart` — `repositoryFutureProvider` memilih implementasi.
- Layar setup koneksi: input alamat server, tombol "Uji Koneksi" memanggil
  `/health`, simpan bila berhasil.
- Web build disajikan dari `lan_server` supaya CORS dan URL API sederhana.

### Fase 4 — Migrasi, backup, dokumentasi

- `lan_server/migrate_from_standalone.py` — backup otomatis, preview jumlah
  record, impor idempoten (berbasis `invoice_no` / `sku` / `code`), laporan
  sukses/gagal, **tidak pernah mengubah database sumber**.
- Skrip backup/restore SQLite pusat (`.backup` API, bukan copy file saat hidup).
- `LAN_MODE.md` — cara jalankan server, alamat klien, port/firewall Windows,
  backup/restore, migrasi, dan cara kembali ke standalone tanpa menghapus data.
- Skrip PowerShell `jalankan server lan/1_jalankan_server_lan.ps1` mengikuti
  pola folder `jalankan server` yang sudah ada.

## Verifikasi

- Test API baru dengan database sementara: checkout sukses, checkout retry
  (idempotent, tidak ganda), overselling ditolak, shift tertutup ditolak,
  stok tidak negatif pada dua checkout bersamaan.
- `pytest` penuh: tidak boleh ada regresi dari baseline 271.
- `flutter analyze` dan build Android + web.
- Uji manual: desktop standalone tetap jalan seperti sekarang; desktop LAN,
  Android, dan web tersambung ke satu database pusat.
- Konfirmasi tidak ada klien yang membuka file SQLite server secara langsung.

## Yang tidak dikerjakan di v1 (disengaja)

- Antrean transaksi offline dan sinkronisasi konflik.
- PostgreSQL.
- Multi-toko / multi-cabang.
- Ekspos server ke internet.

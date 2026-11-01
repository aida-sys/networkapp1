# Mode POS Local Network (LAN)

## Temuan audit

Kabar baik: fondasinya jauh lebih siap daripada biasanya.

- **Skema sudah identik** — `app/models/entities.py` dan Drift `local_database.dart` sama-sama 37 tabel dengan nama sama. Nol pekerjaan pemetaan skema.
- **`SalesService.checkout()` sudah atomik dan server-authoritative** (`app/services/sales_service.py:37`) — validasi shift, stok, harga, total, pembayaran, commit/rollback. Ini persis aturan yang dibutuhkan API. Tidak ditulis ulang.
- **Billing sudah terpisah fisik** — `server/` (port 8001, `billing.db`, Midtrans, lisensi Ed25519) tidak menyentuh tabel POS.
- **Flutter punya satu titik switch** — `repositoryFutureProvider` (`lib/providers.dart:37`) satu-satunya tempat `PosRepository` dibuat.

Yang jadi pekerjaan:

1. **5 titik UI pakai `self.session` langsung** — `cashier_view.py` (361, 726, 732, 848), `purchase_view.py` (738, 787, 812, 830). Selama ada, desktop LAN tidak bisa lepas dari DB lokal.
2. **Belum ada idempotency key** — retry jaringan akan membuat transaksi ganda.
3. **`PosRepository` Flutter kelas konkret 2.151 baris** — perlu interface agar ada implementasi remote.
4. **Belum ada auth token, bind LAN, CORS, firewall.**

**Baseline test:** `271 passed, 3 failed` (248,96 dtk). 3 gagal sudah ada sebelumnya, soal file installer yang tidak ada di disk — tidak terkait pekerjaan ini.

## Keputusan arsitektur

| Hal | Pilihan | Alasan |
|---|---|---|
| DB pusat | **SQLite**, bukan PostgreSQL | Satu toko. WAL + busy_timeout cukup. Syarat: uvicorn `--workers 1`. |
| Lokasi API | Folder baru `lan_server/` | Terpisah total dari `server/` billing. |
| Port | `8002` | 8001 sudah dipakai billing. |
| Aturan bisnis | Impor `app.services.*` | Satu sumber kebenaran, tidak disalin. |
| Auth | JWT HS256 per user+device | Disimpan di secure storage / file terproteksi. |
| Idempotency | Tabel `api_idempotency`, replay respons | Aman terhadap retry. |
| Mode klien | `POS_MODE=standalone\|lan`, default standalone | Tidak ada dual-write, tidak ada fallback diam-diam. |

## Fase 1 — POS API (`lan_server/`)

`main.py`, `config.py`, `database.py`, `deps.py`, `security.py`, `idempotency.py`, `schemas/`, `routers/`, `migrate_from_standalone.py`, `README.md`.

Endpoint di bawah `/api/v1`: auth (login/refresh/me), catalog (products/categories/units/suppliers), inventory (stock/adjust), shifts (open/close/current), sales (checkout wajib `Idempotency-Key`, get, list, refund), purchases (list/create/receive), reports (daily/range), settings (store), health (tanpa auth).

Aturan checkout: harga/stok/total **selalu** dihitung server lewat `SalesService`. Klien hanya kirim `product_id`, `qty`, `discount`, pembayaran. Key sama + body sama → respons lama. Key sama + body beda → 409. Server down → tolak tulis dengan pesan jelas, tanpa antrean offline.

## Fase 2 — Desktop jadi klien LAN

- `app/lan/config.py`, `app/lan/client.py` (httpx, pemetaan error HTTP ke exception yang sudah ada supaya UI tidak berubah), `app/lan/services/*.py` (signature identik service lokal).
- `app/ui/service_factory.py` — pilih lokal atau remote.
- Refactor 5 titik `self.session` jadi method service.
- `main.py` — mode LAN tidak membuka engine lokal; status koneksi tampil di window; tulis diblokir saat server mati.

## Fase 3 — Flutter jadi klien LAN

- `pos_repository_contract.dart` (interface), `remote/pos_api_client.dart`, `remote/remote_pos_repository.dart`, `app_mode.dart`.
- `providers.dart` memilih implementasi.
- Layar setup koneksi: input alamat server + tombol "Uji Koneksi" ke `/health`. Tidak hard-code IP.
- Web build disajikan dari `lan_server` supaya CORS/URL sederhana.

## Fase 4 — Migrasi, backup, dokumentasi

- `migrate_from_standalone.py` — backup otomatis, preview jumlah record, impor idempoten (berbasis `invoice_no`/`sku`/`code`), laporan sukses/gagal, **tidak mengubah DB sumber**.
- Backup/restore pakai `.backup` API SQLite, bukan copy file saat hidup.
- `LAN_MODE.md` + `jalankan server lan/1_jalankan_server_lan.ps1` mengikuti pola folder yang sudah ada.

## Verifikasi

- Test API dengan DB sementara: checkout sukses, retry idempoten (tidak ganda), overselling ditolak, shift tertutup ditolak, dua checkout bersamaan tidak membuat stok negatif.
- `pytest` penuh: tidak ada regresi dari baseline 271.
- `flutter analyze` + build Android dan web.
- Uji manual: standalone tetap jalan; desktop LAN, Android, web tersambung ke satu DB pusat.
- Konfirmasi tidak ada klien membuka file SQLite server langsung.

## Tidak dikerjakan di v1 (disengaja)

Antrean offline dan sinkronisasi konflik, PostgreSQL, multi-cabang, ekspos ke internet.
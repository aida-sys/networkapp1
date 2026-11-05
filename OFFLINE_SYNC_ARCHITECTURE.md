# Arsitektur Offline-First & Cloud Sync (Kasirin POS)

Dokumen ini mendefinisikan rancangan arsitektur **Offline-First dengan Cloud Sync** untuk Kasirin POS. Dalam arsitektur ini, aplikasi klien (Desktop PySide6 dan Mobile Android) tetap memiliki **database SQLite lokal** agar dapat beroperasi penuh 100% meskipun koneksi internet terputus (offline), dan secara otomatis melakukan sinkronisasi data dengan **Cloud Backend (PostgreSQL)** saat internet kembali terhubung.

---

## 1. Prinsip Utama Arsitektur

1. **Local Autonomy (Otonomi Lokal):** 
   - Operasi kasir (buka shift, pilih produk, keranjang belanja, checkout, pembayaran tunai, dan cetak struk) membaca dan menulis ke database lokal SQLite di perangkat klien. Tidak ada operasi kasir yang tertunda hanya karena latensi jaringan.
2. **Idempotent Sync (Sinkronisasi Idempoten):**
   - Setiap transaksi penjualan lokal diberi **Idempotency Key** (UUID v4) unik sebelum disync ke cloud. Jika terjadi retry akibat gangguan jaringan, server cloud tidak akan mencatat transaksi ganda.
3. **Eventual Consistency (Konsistensi Berkelanjutan):**
   - Master data (harga produk, stok minimum, pengaturan toko) di-download dari cloud saat online. Transaksi penjualan di-push ke cloud secara background.

---

## 2. Alur Data & Status Koneksi

```
[ Klien (Desktop / Mobile) ]
       │
       ├─── (Online) ──► Push Transaksi (dengan Idempotency Key) ──► [ Cloud Backend (FastAPI) ]
       │             ◄── Pull Master Data & Update Produk       ──┤           │
       │                                                          │           ▼
       └─── (Offline) ──► Simpan ke Offline Queue Lokal (SQLite)  ──► [ PostgreSQL Cloud ]
```

### State Mesin Koneksi:
- **Online Mode:** Klien terhubung ke Cloud API. Sinkronisasi background berjalan setiap interval tertentu (mis. tiap 2 menit) atau saat ada transaksi baru selesai.
- **Offline Mode:** Klien mendeteksi kegagalan koneksi (`Network/Timeout Error`). Transaksi baru tetap berhasil disimpan ke database lokal dan dimasukkan ke tabel `sync_outbox` (antrean offline). Banner UI menampilkan status "Offline — Transaksi tersimpan lokal".

---

## 3. Skema Antrean Sinkronisasi (`sync_outbox`)

Pada database lokal klien, ditambahkan tabel antrean sinkronisasi untuk mencatat aksi yang belum terkirim ke cloud:

```sql
CREATE TABLE sync_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,         -- 'CREATE_SALE', 'OPEN_SHIFT', 'CLOSE_SHIFT'
    payload_json TEXT NOT NULL,        -- Data JSON lengkap transaksi
    idempotency_key TEXT UNIQUE NOT NULL, -- UUID unik pencegah duplikat
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'PENDING',     -- 'PENDING', 'SYNCED', 'FAILED'
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
);
```

---

## 4. Protokol Sinkronisasi (Push & Pull)

### A. Push (Klien ke Cloud)
1. Setiap transaksi checkout selesai secara lokal, sistem memasukkan record ke tabel lokal dan satu record ke `sync_outbox` dengan status `PENDING`.
2. Background sync worker mengambil record `PENDING` dari `sync_outbox`.
3. Mengirimkan HTTP POST ke Cloud API:
   ```http
   POST /api/v1/sync/push
   Authorization: Bearer <token>
   Idempotency-Key: <uuid-v4>
   Content-Type: application/json

   {
     "sale": { ... },
     "items": [ ... ],
     "payments": [ ... ]
   }
   ```
4. Jika server merespon `200 OK`, status di `sync_outbox` diubah menjadi `SYNCED`.
5. Jika gagal (timeout/server error), `retry_count` bertambah dan dicoba kembali pada siklus sinkronisasi berikutnya dengan *exponential backoff*.

### B. Pull (Cloud ke Klien - Master Data)
1. Secara berkala atau saat aplikasi dibuka, klien melakukan HTTP GET untuk memperbarui master data katalog produk, kategori, dan pengaturan toko:
   ```http
   GET /api/v1/sync/catalog?since=<last_sync_timestamp>
   ```
2. Klien memperbarui tabel lokal menggunakan data terbaru dari server cloud.

---

## 5. Resolusi Konflik (Conflict Resolution)
- **Master Data (Produk/Harga):** Server Cloud adalah *Source of Truth* (Sumber Kebenaran Utama). Perubahan harga atau stok dari cloud akan menimpa data lokal.
- **Transaksi Penjualan:** Karena setiap transaksi kasir bersifat *append-only* (hanya menambah data penjualan baru), tidak ada konflik timpa data penjualan antar kasir selama menggunakan Idempotency Key yang unik.

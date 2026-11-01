# Mode POS Local Network (LAN)

Panduan mengubah aplikasi dari standalone (satu database per perangkat) menjadi
aplikasi jaringan lokal dengan **satu database pusat** di komputer server toko.

Standalone tetap menjadi mode default. Tidak ada yang berubah bagi pengguna yang
tidak mengaktifkan LAN.

---

## 1. Gambaran

```
                    ┌──────────────────────────────┐
                    │  PC Server Toko (Windows)    │
                    │                              │
   Desktop ────────►│  POS LAN API  :8002          │
   Android ────────►│      │                       │
   Browser ────────►│      ▼                       │
                    │  pos_lan.db (SQLite, WAL)    │
                    │  di disk lokal PC ini        │
                    └──────────────────────────────┘

                    ┌──────────────────────────────┐
                    │  Server Billing (terpisah)   │
                    │  :8001  billing.db           │
                    │  HANYA aktivasi lisensi      │
                    └──────────────────────────────┘
```

Dua server itu **tidak saling bergantung**:

| | Server Billing | Server POS LAN |
|---|---|---|
| Port | 8001 | 8002 |
| Database | `server/billing.db` | `lan_server/data/pos_lan.db` |
| Isi | lisensi, aktivasi, Midtrans | transaksi, stok, pengguna |
| Kode | `server/` | `lan_server/` |
| Dipakai saat | aktivasi & perpanjangan | operasi kasir sehari-hari |

Mematikan server billing tidak menghentikan kasir. Mematikan server LAN tidak
membatalkan lisensi.

### Kenapa skripnya dipisah

| Folder | Server | Port | Akses |
|---|---|---|---|
| `jalankan server\` | Billing / lisensi | 8001 | **ngrok + hosting** (nanti) |
| `jalankan server lan\` | POS LAN API | 8002 | **hanya jaringan lokal** |

Billing perlu dijangkau dari luar toko untuk aktivasi, jadi wajar diekspos lewat
ngrok atau hosting. POS LAN tidak: isinya data transaksi toko dan hanya diakses
dari perangkat di jaringan yang sama. Skrip di `jalankan server lan\` **tidak
menjalankan ngrok** dan tidak membuka tunnel apa pun.

---

## 2. Aturan yang dipegang

1. **Standalone tetap default.** Tanpa konfigurasi, aplikasi memakai
   `%LOCALAPPDATA%\POSApp\data\pos.db` seperti sebelumnya.
2. **Tidak ada migrasi otomatis.** Instalasi lama tidak dipindahkan diam-diam.
   Migrasi dijalankan manual, sekali, dengan preview dulu.
3. **Tidak ada dual-write.** Mode LAN tidak menulis ke database lokal dan
   sebaliknya. Satu mode, satu sumber data.
4. **Tidak ada fallback diam-diam.** Kalau server mati, aplikasi menolak operasi
   tulis dengan pesan jelas. Tidak ada antrean offline di v1.
5. **Klien tidak pernah membuka file SQLite server langsung.** Tidak lewat
   shared folder, tidak lewat drive jaringan (`\\server\...`), tidak lewat SMB.
   Semua akses lewat HTTP API.
6. **Harga, stok, dan total selalu dihitung server** memakai `app.services.*`
   yang sama dengan aplikasi desktop. Klien hanya mengirim `product_id`, `qty`,
   dan pembayaran.
7. **Billing tetap terpisah.** `lan_server` tidak mengimpor modul billing.

---

## 3. Menyiapkan server (sekali)

Di komputer yang akan menjadi server (Windows, satu PC di toko):

```powershell
# 1. Jalankan server LAN
cd "jalankan server lan"
.\1_jalankan_server_lan.ps1
```

Script itu akan:

- memeriksa venv dan dependensi,
- membuat skema database pusat bila belum ada (`lan_server/init_db.py`),
- **mengisi data dasar wajib** (bagan akun, role, metode bayar, toko,
  kategori `Umum`, satuan `Pcs`) lewat `lan_server/bootstrap.py`,
- menampilkan alamat IP LAN komputer ini,
- menjalankan uvicorn dengan `--workers 1` (wajib untuk SQLite),
- menunggu sampai `/api/v1/health` menjawab.

Catat alamat **Jaringan LAN** yang ditampilkan, misalnya
`http://192.168.1.10:8002`. Itu yang diisi di perangkat lain.

### Kenapa ada bootstrap

Di aplikasi desktop, bagan akun dan metode pembayaran dibuat oleh migrasi
Alembic. Server LAN membuat skema lewat `create_all`, yang **tidak** menjalankan
migrasi. Tanpa `lan_server/bootstrap.py`, database pusat akan kosong dan checkout
pertama langsung gagal:

```
Akun wajib 4000 tidak ditemukan.
```

Bootstrap mengisi 18 akun standar (termasuk `4000 Penjualan` dan
`5000 Harga Pokok Penjualan`), 4 role, 4 metode bayar, satu toko, kategori
`Umum`, dan satuan `Pcs`. Semua idempoten: menjalankannya berkali-kali tidak
menggandakan baris dan tidak menimpa data yang sudah ada.

Bila memakai `migrate_from_standalone.py` dari database desktop yang sudah
berisi data, bagan akun ikut terbawa; bootstrap hanya menambah yang belum ada.

### Menghentikan server

```powershell
.\2_hentikan_server_lan.ps1
```

Hanya port 8002 yang disentuh. Server billing di 8001 tidak terganggu.

### Menguji server

```powershell
.\3_uji_server_lan.ps1 -Username owner -Password <password-owner> -DryRun
```

Tanpa `-DryRun`, script juga melakukan checkout sungguhan lalu mengulanginya
dengan `Idempotency-Key` yang sama untuk membuktikan tidak ada transaksi ganda.

---

## 4. Memindahkan data standalone ke server

**Lakukan sekali, sebelum kasir mulai memakai mode LAN.**

### Langkah 1 — preview (tidak menulis apa pun)

```powershell
.\venv\Scripts\python.exe lan_server\migrate_from_standalone.py
```

Keluarannya menunjukkan, per tabel: jumlah baris di sumber, jumlah di tujuan,
dan berapa yang akan masuk. Database sumber dibuka **read-only**.

### Langkah 2 — terapkan

```powershell
.\venv\Scripts\python.exe lan_server\migrate_from_standalone.py --apply
```

Yang dilakukan skrip:

- **backup otomatis** database tujuan sebelum menulis apa pun,
- memindahkan data dengan **id asli dipertahankan**, jadi relasi
  (`sales` → `shift` → `users`, `sale_items` → `products`) tetap utuh,
- **idempoten**: dijalankan dua kali tidak menggandakan data, karena baris
  dicocokkan lewat kunci alami (`sku`, `invoice_no`, `username`, `code`,
  `order_no`),
- **tidak mengubah database sumber** sama sekali.

Sumber dan tujuan bisa ditentukan eksplisit:

```powershell
.\venv\Scripts\python.exe lan_server\migrate_from_standalone.py `
    --source "$env:LOCALAPPDATA\POSApp\data\pos.db" `
    --target "lan_server\data\pos_lan.db" --apply
```

Tabel yang belum ada di database sumber hanya dilewati dan dicatat, bukan
dianggap gagal.

---

## 5. Backup dan restore

Jangan pernah menyalin `pos_lan.db` dengan Ctrl+C saat server hidup: WAL yang
belum di-checkpoint bisa membuat salinan rusak. Pakai skrip ini.

```powershell
# Backup (nama berstempel waktu, di lan_server/data/backups/)
.\venv\Scripts\python.exe lan_server\backup_restore.py backup

# Backup ke folder lain (mis. flashdisk)
.\venv\Scripts\python.exe lan_server\backup_restore.py backup --out D:\backup-pos

# Daftar backup
.\venv\Scripts\python.exe lan_server\backup_restore.py list

# Verifikasi integritas
.\venv\Scripts\python.exe lan_server\backup_restore.py verify

# Restore (otomatis membackup database aktif dulu)
.\venv\Scripts\python.exe lan_server\backup_restore.py restore `
    --file lan_server\data\backups\pos_lan-20260101-120000.db
```

Hentikan server sebelum restore agar tidak ada penulisan bersamaan.

---

## 6. Menghubungkan perangkat

### Desktop (PySide6)

Mode dipilih lewat environment, default `standalone`:

```powershell
$env:POS_MODE = "lan"
$env:POS_API_URL = "http://192.168.1.10:8002"
.\venv\Scripts\python.exe main.py
```

Tanpa `POS_MODE=lan`, aplikasi berjalan persis seperti sebelumnya.

Pilihan mode juga bisa disimpan permanen di
`%LOCALAPPDATA%\POSApp\data\lan_mode.json` (dibuat oleh `save_config()`), supaya
tidak perlu menyetel environment setiap kali. Environment menang atas file,
sehingga admin toko bisa memaksa mode lewat shortcut.

### Android / Flutter

1. Buka aplikasi, di layar login tekan **Koneksi Server LAN**.
2. Isi alamat server, mis. `http://192.168.1.10:8002`.
3. Tekan **Uji Koneksi** — aplikasi benar-benar memanggil `/api/v1/health`.
4. Tekan **Simpan & Pakai LAN**, lalu login.

Alamat tidak pernah di-hard-code. Untuk kembali ke standalone, tekan
**Pakai Standalone** di layar yang sama; data lokal di perangkat tidak diubah.

### Browser

Build Flutter web bisa disajikan langsung oleh server LAN supaya tidak ada
masalah CORS:

```powershell
cd android\kasirin_mobile
flutter build web
```

Lalu arahkan `LAN_WEB_BUILD_DIR` ke folder `build\web` sebelum menjalankan
server. Buka `http://192.168.1.10:8002` dari browser di jaringan yang sama.

---

## 7. Konfigurasi server

Semua lewat environment atau `lan_server/.env` (prefix `LAN_`):

| Variabel | Default | Keterangan |
|---|---|---|
| `LAN_HOST` | `0.0.0.0` | Bind address. Jangan diekspos ke internet. |
| `LAN_PORT` | `8002` | Port server LAN. |
| `LAN_DATABASE_PATH` | `lan_server/data/pos_lan.db` | Lokasi database pusat. |
| `LAN_JWT_SECRET` | dibuat otomatis | Disimpan di `lan_server/data/jwt_secret.key`. |
| `LAN_TOKEN_TTL_MINUTES` | `720` | Umur token akses. |
| `LAN_CORS_ORIGINS` | kosong | Daftar origin dipisah koma untuk Flutter web. |
| `LAN_WEB_BUILD_DIR` | kosong | Folder `build/web` Flutter untuk disajikan server. |
| `LAN_DB_BUSY_TIMEOUT_MS` | `5000` | Batas tunggu lock SQLite. |

**Jangan jalankan dengan lebih dari satu worker.** SQLite hanya boleh ditulis
satu proses. Script menjalankan `--workers 1` secara eksplisit.

---

## 8. Firewall Windows

Perangkat lain tidak akan tersambung kalau port 8002 diblokir. Jalankan sekali
di komputer server, dari PowerShell **sebagai Administrator**:

```powershell
New-NetFirewallRule -DisplayName "POS LAN API 8002" `
    -Direction Inbound -Protocol TCP -LocalPort 8002 -Action Allow `
    -Profile Private
```

Batasi ke profil `Private` supaya tidak terbuka di jaringan publik.

---

## 9. Kalau ada masalah

| Gejala | Penyebab biasanya | Tindakan |
|---|---|---|
| "Server POS LAN tidak dapat dihubungi" | server mati, IP salah, atau firewall | jalankan `1_jalankan_server_lan.ps1`, cek IP, buka port 8002 |
| "Belum login ke server POS LAN" | token kedaluwarsa | login ulang |
| Checkout ditolak "shift" | shift belum dibuka untuk kasir itu | buka shift dulu |
| Checkout ditolak "stok" | stok di server tidak cukup | cek stok di server, bukan di perangkat |
| Data lama tidak muncul di LAN | migrasi belum dijalankan | jalankan `migrate_from_standalone.py --apply` |
| `database is locked` | ada lebih dari satu proses menulis | pastikan hanya satu instance server |

Log server: `lan_server_stdout.log` dan `lan_server_stderr.log` di root repo.

---

## 10. Yang sengaja belum ada di v1

- Antrean offline dan sinkronisasi konflik. Server mati berarti kasir berhenti
  menulis, bukan menumpuk transaksi yang bisa bentrok.
- PostgreSQL atau database multi-tulis.
- Multi-cabang.
- Ekspos ke internet. Mode ini untuk jaringan lokal toko. Untuk akses jarak jauh,
  pasang reverse proxy dengan TLS dan autentikasi tambahan.

---

## 11. Berkas terkait

| Berkas | Isi |
|---|---|
| `lan_server/main.py` | Aplikasi FastAPI, CORS, penyajian web build |
| `lan_server/routers/` | Endpoint `/api/v1/*` |
| `lan_server/security.py` | JWT HS256 |
| `lan_server/idempotency.py` | Tabel `api_idempotency`, replay respons |
| `lan_server/migrate_from_standalone.py` | Migrasi data |
| `lan_server/backup_restore.py` | Backup, restore, verifikasi |
| `app/lan/` | Adapter desktop sebagai klien LAN |
| `android/kasirin_mobile/lib/remote/` | Klien HTTP + repository remote Flutter |
| `android/kasirin_mobile/lib/domain/pos_repository_contract.dart` | Kontrak repository |
| `tests/test_lan_api.py` | Test API |
| `tests/test_lan_client.py` | Test adapter desktop |
| `tests/test_lan_migration.py` | Test migrasi |
| `tests/test_lan_backup.py` | Test backup/restore |
| `android/kasirin_mobile/test/remote_repository_test.dart` | Test klien Flutter |

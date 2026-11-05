# Panduan Deployment Full Cloud (POS Cloud Architecture)

Panduan ini menjelaskan cara mengubah dan mendeploy arsitektur **Kasirin POS** menjadi **Full Cloud** (Cloud Database + Cloud POS Backend API), sehingga seluruh klien (Desktop PySide6, Mobile Android, dan Web) dapat terhubung langsung ke server cloud tanpa mengubah struktur database yang sudah ada.

---

## 1. Arsitektur Full Cloud

- **Database Cloud:** Menggunakan database relasional cloud (seperti PostgreSQL di Render, Supabase, Neon, Railway, atau AWS RDS). Karena menggunakan SQLAlchemy, skema 37 tabel tetap sama persis tanpa modifikasi.
- **Backend Cloud (`lan_server`):** Di-deploy sebagai web service cloud (FastAPI + Uvicorn) di platform seperti Render, Railway, Fly.io, atau VPS Linux.
- **Klien (Desktop, Android, Web):** Menggunakan mode koneksi remote (sama seperti mode LAN, namun mengarah ke URL publik cloud, misal `https://api.tokokasir.com`).

---

## 2. Menyiapkan Database Cloud (PostgreSQL)

1. Buat database PostgreSQL baru di layanan cloud pilihan Anda (contoh: **Render**, **Supabase**, atau **Neon**).
2. Dapatkan connection string PostgreSQL, contoh:
   ```env
   DATABASE_URL=postgresql://user:password@hostname:5432/dbname
   ```

---

## 3. Deployment Backend ke Cloud (Contoh: Render / Railway)

Folder `lan_server/` sudah siap digunakan sebagai cloud backend API. 

### Variabel Lingkungan (Environment Variables) yang Diperlukan di Server Cloud:
| Variabel | Keterangan | Contoh Nilai |
| --- | --- | --- |
| `DATABASE_URL` | Connection string database cloud | `postgresql://user:pass@host:5432/db` |
| `LAN_JWT_SECRET` | Secret key untuk token JWT | (string acak yang panjang dan aman) |
| `LAN_CORS_ORIGINS` | Domain yang diizinkan (untuk Web) | `https://app.tokokasir.com` |
| `PORT` | Port server (biasanya otomatis diset cloud provider) | `8002` atau `10000` |

### Perintah Start Server:
```bash
uvicorn lan_server.main:app --host 0.0.0.0 --port $PORT --workers 1
```

---

## 4. Menghubungkan Klien (Desktop & Mobile) ke Cloud

Sama seperti mode LAN, aplikasi klien tidak memerlukan database lokal di cloud mode. Klien cukup diarahkan ke URL endpoint Cloud API.

### A. Aplikasi Desktop (Python / PySide6)
Atur konfigurasi LAN/Cloud URL melalui file konfigurasi mode atau set environment variable:
```json
{
  "mode": "lan",
  "api_url": "https://api.tokokasir.com",
  "device_id": "desktop-cloud-01"
}
```
Atau jalankan dengan environment variable:
```powershell
$env:POS_MODE="lan"
$env:POS_API_URL="https://api.tokokasir.com"
python main.py
```

### B. Aplikasi Mobile (Flutter Android)
Pada layar pengaturan koneksi server (LanSetupView), masukkan URL cloud backend Anda:
`https://api.tokokasir.com`

---

## 5. Migrasi Data Eksisting ke Cloud (Opsional)
Jika Anda memiliki data dari database SQLite lokal dan ingin memindahkannya ke database PostgreSQL cloud:
1. Jalankan skrip migrasi/ekspor data.
2. Impor menggunakan tool manajemen database (seperti pgAdmin, DBeaver) atau jalankan migrasi Alembic pada database cloud baru:
   ```bash
   alembic upgrade head
   ```

# Jalankan Server LAN (lokal saja)

Folder ini khusus untuk **server POS LAN** — database pusat toko di jaringan
lokal. Tidak ada ngrok, tidak ada tunnel, tidak ada hosting.

## Dua folder, dua tujuan

| Folder | Server | Port | Dipakai untuk | Akses |
|---|---|---|---|---|
| `jalankan server\` | Billing / lisensi | 8001 | aktivasi & perpanjangan lisensi | **ngrok + hosting** (nanti) |
| `jalankan server lan\` | POS LAN API | 8002 | transaksi kasir sehari-hari | **hanya jaringan lokal** |

Bedanya disengaja:

- **Billing** perlu dijangkau dari luar toko (aplikasi di lokasi pelanggan harus
  bisa aktivasi), jadi wajar diekspos lewat ngrok atau hosting.
- **POS LAN** tidak boleh diekspos ke internet. Isinya data transaksi toko dan
  hanya diakses dari perangkat di jaringan yang sama. Membukanya ke publik
  berarti database penjualan bisa dijangkau dari mana saja.

Karena itu skrip di folder ini **tidak menjalankan ngrok** dan sengaja mengikat
port ke jaringan lokal saja.

## Isi folder

| Skrip | Fungsi |
|---|---|
| `1_jalankan_server_lan.ps1` | Siapkan skema DB, jalankan uvicorn `--workers 1`, tampilkan IP LAN |
| `2_hentikan_server_lan.ps1` | Hentikan proses di port 8002 (port 8001 tidak disentuh) |
| `3_uji_server_lan.ps1` | Uji health, login, produk, dan idempotensi checkout |

## Pakai

```powershell
cd "jalankan server lan"
.\1_jalankan_server_lan.ps1
```

Script akan menampilkan alamat seperti `http://192.168.1.10:8002`. Alamat
**Jaringan LAN** itulah yang diisi di layar "Koneksi Server" pada aplikasi
Android/desktop.

Menghentikan:

```powershell
.\2_hentikan_server_lan.ps1
```

Menguji:

```powershell
.\3_uji_server_lan.ps1 -Username owner -Password <password-owner> -DryRun
```

## Kalau nanti butuh akses dari luar toko

Jangan pasang ngrok di server LAN. Yang benar: pasang reverse proxy dengan TLS
dan autentikasi tambahan di depan port 8002, batasi ke pengguna tertentu, dan
tetap jalankan `--workers 1`. Untuk v1 ini sengaja tidak dikerjakan.

Panduan lengkap: `LAN_MODE.md` di root repo.

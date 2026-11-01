# Code signing (menandatangani installer)

Tanpa tanda tangan Authenticode, Windows SmartScreen memblokir installer di
komputer pelanggan dengan layar "Windows protected your PC". Pelanggan harus
menekan **More info → Run anyway**. Untuk produk POS berbayar, itu terbaca
seperti malware.

Build **tidak** menandatangani apa pun secara default: build tetap jalan dan
mencetak peringatan besar bahwa hasilnya unsigned.

## Yang perlu dibeli

Sertifikat **Authenticode code signing** (bukan SSL). Pilihan umum:

| Jenis | Verifikasi | SmartScreen |
|---|---|---|
| OV (Organization Validation) | bisnis, beberapa hari | reputasi dibangun bertahap |
| EV (Extended Validation) | bisnis + token hardware | langsung tepercaya |

Catatan penting: **sertifikat OV baru tidak langsung menghilangkan peringatan
SmartScreen.** Reputasi dibangun dari jumlah unduhan. EV langsung tepercaya
tetapi jauh lebih mahal dan biasanya berupa token USB yang harus dicolok saat
build.

## Cara mengaktifkan

Set environment variable sebelum menjalankan build. Jangan pernah menaruh nilai
ini di repo (`.gitignore` sudah menutup `*.pfx` dan `*.p12`).

### Opsi A — file PFX

```powershell
$env:KASIRIN_SIGN_PFX      = "C:\sertifikat\kasirin.pfx"
$env:KASIRIN_SIGN_PFX_PASS = "<password>"
.\venv\Scripts\python.exe scripts\build_installer.py
```

### Opsi B — sertifikat di Windows Certificate Store (disarankan)

Tidak ada file rahasia yang bisa tersalin ke mesin lain.

```powershell
# lihat thumbprint
Get-ChildItem Cert:\CurrentUser\My | Format-Table Subject, Thumbprint

$env:KASIRIN_SIGN_THUMBPRINT = "<40 karakter thumbprint>"
.\venv\Scripts\python.exe scripts\build_installer.py
```

### Variabel opsional

| Variabel | Default | Keterangan |
|---|---|---|
| `KASIRIN_SIGN_TIMESTAMP` | `http://timestamp.digicert.com` | Server timestamp RFC 3161 |
| `SIGNTOOL` | terdeteksi otomatis | Path ke `signtool.exe` |
| `KASIRIN_SIGN_REQUIRED` | tidak diset | `1` = build GAGAL bila tidak ada sertifikat |

`KASIRIN_SIGN_REQUIRED=1` sebaiknya diset di mesin rilis, supaya tidak pernah
ada build yang terkirim tanpa sengaja dalam keadaan unsigned.

## Prasyarat: signtool.exe

`signtool.exe` berasal dari **Windows SDK** (komponen "Signing Tools for
Windows"). Kalau belum ada, pasang:

```powershell
winget install Microsoft.WindowsSDK.10.0.26100
```

Atau install Visual Studio Build Tools dan centang Windows SDK.

Script mencari `signtool.exe` di urutan ini: `SIGNTOOL` env var → `PATH` →
`C:\Program Files (x86)\Windows Kits\10\bin\<versi>\x64\signtool.exe`
(versi terbaru lebih dulu).

## Yang ditandatangani

| Build | File |
|---|---|
| `scripts/build_installer.py` | `dist\POS\POS.exe` lalu `build\installer_v3\Kasirin.exe` |
| `scripts/build_server_installer.py` | `dist\KasirinServer\KasirinServer.exe` lalu `build\installer_server\KasirinServer.exe` |

`POS.exe` ikut ditandatangani karena itu file yang benar-benar dijalankan
pengguna setiap hari, bukan hanya installernya.

## Kenapa timestamp wajib

Tanpa timestamp, tanda tangan berhenti valid begitu sertifikat kedaluwarsa,
dan installer lama yang sudah terpasang akan mulai diperingatkan Windows lagi.
Dengan timestamp, tanda tangan tetap valid selamanya karena waktu penandatanganan
dibuktikan pihak ketiga.

## Memeriksa hasil

```powershell
Get-AuthenticodeSignature "build\installer_v3\Kasirin.exe" | Format-List Status, SignerCertificate
```

`Status` harus `Valid`. Kalau `NotSigned`, sertifikat belum terpakai. Kalau
`HashMismatch`, file berubah setelah ditandatangani.

Dari Python:

```powershell
.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from scripts.code_signing import verify; from pathlib import Path; print(verify(Path('build/installer_v3/Kasirin.exe')))"
```

## Kalau dikonfigurasi tetapi gagal, build GAGAL

Ini disengaja. Skenario yang harus menghentikan build:

- `KASIRIN_SIGN_PFX` menunjuk ke file yang tidak ada
- `signtool.exe` tidak ditemukan
- password PFX salah
- server timestamp tidak terjangkau

Build tidak boleh diam-diam menghasilkan installer unsigned padahal admin
mengira sudah ditandatangani.

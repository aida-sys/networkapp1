<#
.SYNOPSIS
    1_jalankan_server_lan.ps1 - Menjalankan POS LAN API (port 8002).

.DESCRIPTION
    Server ini adalah database pusat untuk mode LAN. Berbeda dari server billing
    (port 8001) yang hanya mengurus aktivasi lisensi:

      - server billing : port 8001, billing.db, Midtrans, lisensi Ed25519
      - server LAN     : port 8002, pos_lan.db, data transaksi POS

    Script ini akan:
    1. Memeriksa Python venv dan dependensi.
    2. Menyiapkan skema database pusat bila belum ada.
    3. Menampilkan alamat IP LAN komputer ini (untuk diisi di perangkat lain).
    4. Menjalankan uvicorn dengan --workers 1 (wajib untuk SQLite).
    5. Menunggu sampai /api/v1/health menjawab.

.PARAMETER Port
    Port server LAN. Default 8002.

.PARAMETER HostAddress
    Alamat bind. Default 0.0.0.0 agar bisa diakses dari perangkat lain.

.EXAMPLE
    .\1_jalankan_server_lan.ps1
    .\1_jalankan_server_lan.ps1 -Port 8002
#>
[CmdletBinding()]
param(
    [int]$Port = 8002,
    [string]$HostAddress = "0.0.0.0"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "        MENJALANKAN SERVER POS LAN (PORT $Port)          " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# --- 1. Python ---------------------------------------------------------
$python = Join-Path $repoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "[!] venv tidak ditemukan di $repoRoot\venv" -ForegroundColor Red
    Write-Host "    Jalankan dulu: python -m venv venv" -ForegroundColor Yellow
    Read-Host "Tekan Enter untuk keluar..."
    exit 1
}
Write-Host "[1/5] Python: $python" -ForegroundColor Gray

# --- 2. Dependensi -----------------------------------------------------
Write-Host "[2/5] Memeriksa dependensi (fastapi, uvicorn, sqlalchemy)..." -ForegroundColor Yellow
& $python -c "import fastapi, uvicorn, sqlalchemy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Ada dependensi yang belum terpasang. Memasang dari requirements.txt..." -ForegroundColor Yellow
    & $python -m pip install -r (Join-Path $repoRoot "requirements.txt") --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Gagal memasang dependensi." -ForegroundColor Red
        Read-Host "Tekan Enter untuk keluar..."
        exit 1
    }
}

# --- 3. Skema database -------------------------------------------------
Write-Host "[3/5] Menyiapkan skema database pusat..." -ForegroundColor Yellow
Push-Location $repoRoot
try {
    & $python "lan_server\init_db.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Gagal menyiapkan skema database." -ForegroundColor Red
        Read-Host "Tekan Enter untuk keluar..."
        exit 1
    }
} finally {
    Pop-Location
}

# --- 4. Hentikan instance lama di port yang sama ------------------------
$netstat = netstat -ano | findstr ":$Port" | findstr "LISTENING"
if ($netstat) {
    foreach ($line in $netstat) {
        $parts = $line.Trim() -split '\s+'
        $existingPid = $parts[-1]
        if ($existingPid -match '^\d+$' -and $existingPid -ne "0") {
            try {
                Stop-Process -Id ([int]$existingPid) -Force -ErrorAction SilentlyContinue
                Write-Host "      Proses lama (PID $existingPid) dihentikan untuk restart." -ForegroundColor Gray
            } catch {}
        }
    }
    Start-Sleep -Milliseconds 800
}

# --- 5. Jalankan uvicorn ----------------------------------------------
Write-Host "[4/5] Menjalankan uvicorn (--workers 1, wajib untuk SQLite)..." -ForegroundColor Yellow
$stdout = Join-Path $repoRoot "lan_server_stdout.log"
$stderr = Join-Path $repoRoot "lan_server_stderr.log"

Start-Process -FilePath $python `
    -ArgumentList @(
        "-m", "uvicorn", "lan_server.main:app",
        "--host", $HostAddress,
        "--port", "$Port",
        "--workers", "1"
    ) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Minimized

$isReady = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $Port)
        $client.Close()
        $isReady = $true
        break
    } catch {}
}

Write-Host "[5/5] Memeriksa kesehatan server..." -ForegroundColor Yellow
if (-not $isReady) {
    Write-Host "      [!] Server belum merespons di port $Port." -ForegroundColor Red
    Write-Host "          Cek $stderr" -ForegroundColor Yellow
    Read-Host "Tekan Enter untuk keluar..."
    exit 1
}

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 5
    Write-Host "      Health: status=$($health.status) database=$($health.database) versi=$($health.version)" -ForegroundColor Green
} catch {
    Write-Host "      Health check warning: $_" -ForegroundColor Yellow
}

# --- Alamat untuk perangkat lain --------------------------------------
$addresses = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -ExpandProperty IPAddress

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "              SERVER POS LAN SIAP DIPAKAI               " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  Lokal (komputer ini) : http://127.0.0.1:$Port" -ForegroundColor White
foreach ($address in $addresses) {
    Write-Host "  Jaringan LAN         : http://${address}:$Port" -ForegroundColor White
}
Write-Host ""
Write-Host "  Isi alamat JARINGAN LAN di layar 'Koneksi Server' pada" -ForegroundColor Gray
Write-Host "  aplikasi Android/desktop, lalu tekan 'Uji Koneksi'." -ForegroundColor Gray
Write-Host ""
Write-Host "  Database pusat : lan_server\data\pos_lan.db" -ForegroundColor Gray
Write-Host "  Backup         : python lan_server\backup_restore.py backup" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Untuk menghentikan: 2_hentikan_server_lan.ps1" -ForegroundColor Cyan
Write-Host ""
Read-Host "Tekan Enter untuk menutup jendela ini (server tetap berjalan di latar belakang)..."

<#
.SYNOPSIS
    3_uji_server_lan.ps1 - Menguji POS LAN API dari komputer server.

.DESCRIPTION
    Menjalankan rangkaian pemeriksaan nyata terhadap server yang sedang hidup:

    1. /api/v1/health tanpa token
    2. login (butuh username/password)
    3. daftar produk dengan token
    4. checkout dengan Idempotency-Key, lalu diulang untuk membuktikan
       retry tidak membuat transaksi ganda

    Tidak ada data contoh yang ditulis bila -DryRun dipakai.

.PARAMETER BaseUrl
    Alamat server. Default http://127.0.0.1:8002

.PARAMETER Username
    Username untuk login.

.PARAMETER Password
    Password untuk login.

.PARAMETER DryRun
    Hanya uji health dan login, tanpa checkout.

.EXAMPLE
    .\3_uji_server_lan.ps1 -Username owner -Password rahasia123 -DryRun
#>
[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8002",
    [string]$Username = "",
    [string]$Password = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = "$BaseUrl/api/v1"

function Write-Step($text) {
    Write-Host "`n[>] $text" -ForegroundColor Yellow
}

function Write-Ok($text) {
    Write-Host "    OK  $text" -ForegroundColor Green
}

function Write-Fail($text) {
    Write-Host "    !!  $text" -ForegroundColor Red
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "            UJI SERVER POS LAN - $BaseUrl" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# --- 1. Health ---------------------------------------------------------
Write-Step "Health check (tanpa token)"
try {
    $health = Invoke-RestMethod -Uri "$root/health" -TimeoutSec 5
    Write-Ok "status=$($health.status) database=$($health.database) versi=$($health.version)"
} catch {
    Write-Fail "Server tidak menjawab: $_"
    Write-Host "`nJalankan dulu 1_jalankan_server_lan.ps1" -ForegroundColor Yellow
    Read-Host "Tekan Enter untuk keluar..."
    exit 1
}

# --- 2. Login ----------------------------------------------------------
if ([string]::IsNullOrWhiteSpace($Username)) {
    $Username = Read-Host "Username"
}
if ([string]::IsNullOrWhiteSpace($Password)) {
    $secure = Read-Host "Password" -AsSecureString
    $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    )
}

Write-Step "Login sebagai '$Username'"
try {
    $body = @{ username = $Username; password = $Password } | ConvertTo-Json
    $login = Invoke-RestMethod -Uri "$root/auth/login" -Method Post `
        -ContentType "application/json" -Body $body -TimeoutSec 10
    $token = $login.access_token
    if (-not $token) { throw "access_token tidak ada di respons" }
    Write-Ok "login berhasil sebagai $($login.user.full_name) ($($login.user.role))"
} catch {
    Write-Fail "Login gagal: $_"
    Read-Host "Tekan Enter untuk keluar..."
    exit 1
}

$headers = @{ Authorization = "Bearer $token" }

# --- 3. Produk ---------------------------------------------------------
Write-Step "Daftar produk (dengan token)"
try {
    $products = Invoke-RestMethod -Uri "$root/catalog/products" -Headers $headers -TimeoutSec 10
    Write-Ok "$($products.Count) produk terbaca"
    if ($products.Count -gt 0) {
        $first = $products[0]
        Write-Host "       contoh: $($first.sku) - $($first.name) stok=$($first.stock_qty) harga=$($first.selling_price)" -ForegroundColor Gray
    }
} catch {
    Write-Fail "Gagal membaca produk: $_"
}

if ($DryRun) {
    Write-Host "`n-DryRun: berhenti sebelum checkout." -ForegroundColor Gray
    Read-Host "Tekan Enter untuk menutup jendela ini..."
    exit 0
}

# --- 4. Checkout idempoten --------------------------------------------
if ($products.Count -eq 0) {
    Write-Host "`nTidak ada produk untuk diuji checkout." -ForegroundColor Yellow
    Read-Host "Tekan Enter untuk menutup jendela ini..."
    exit 0
}

Write-Step "Shift aktif"
try {
    $shift = Invoke-RestMethod -Uri "$root/shifts/current" -Headers $headers -TimeoutSec 10
    if ($null -eq $shift) {
        Write-Fail "Belum ada shift terbuka untuk akun ini. Buka shift dulu di aplikasi."
        Read-Host "Tekan Enter untuk menutup jendela ini..."
        exit 1
    }
    Write-Ok "shift #$($shift.id) status=$($shift.status)"
} catch {
    Write-Fail "Gagal membaca shift: $_"
    Read-Host "Tekan Enter untuk menutup jendela ini..."
    exit 1
}

$product = $products[0]
$key = "UJI-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
$checkoutBody = @{
    items    = @(@{ product_id = $product.id; qty = 1 })
    payments = @(@{ method = "CASH"; amount = [int]$product.selling_price })
} | ConvertTo-Json -Depth 5

Write-Step "Checkout pertama (Idempotency-Key: $key)"
try {
    $first = Invoke-RestMethod -Uri "$root/sales/checkout" -Method Post `
        -Headers ($headers + @{ "Idempotency-Key" = $key }) `
        -ContentType "application/json" -Body $checkoutBody -TimeoutSec 15
    Write-Ok "sale #$($first.id) invoice=$($first.invoice_no) total=$($first.grand_total)"
} catch {
    Write-Fail "Checkout gagal: $_"
    Read-Host "Tekan Enter untuk menutup jendela ini..."
    exit 1
}

Write-Step "Checkout ulang dengan key yang sama (harus mengembalikan sale yang sama)"
try {
    $second = Invoke-RestMethod -Uri "$root/sales/checkout" -Method Post `
        -Headers ($headers + @{ "Idempotency-Key" = $key }) `
        -ContentType "application/json" -Body $checkoutBody -TimeoutSec 15
    if ($second.id -eq $first.id) {
        Write-Ok "idempoten: sale #$($second.id) sama, tidak ada transaksi ganda"
    } else {
        Write-Fail "TIDAK idempoten: sale #$($first.id) vs #$($second.id)"
    }
} catch {
    Write-Fail "Retry gagal: $_"
}

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "                  UJI SELESAI                          " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Read-Host "Tekan Enter untuk menutup jendela ini..."

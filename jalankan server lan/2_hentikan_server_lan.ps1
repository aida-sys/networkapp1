<#
.SYNOPSIS
    2_hentikan_server_lan.ps1 - Menghentikan POS LAN API.

.DESCRIPTION
    Menghentikan proses yang mendengarkan di port server LAN (default 8002).
    Server billing di port 8001 TIDAK disentuh.
#>
[CmdletBinding()]
param(
    [int]$Port = 8002
)

$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "          MENGHENTIKAN SERVER POS LAN (PORT $Port)       " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$netstat = netstat -ano | findstr ":$Port" | findstr "LISTENING"
if (-not $netstat) {
    Write-Host "Tidak ada proses yang mendengarkan di port $Port." -ForegroundColor Yellow
    Read-Host "Tekan Enter untuk keluar..."
    exit 0
}

$stopped = 0
foreach ($line in $netstat) {
    $parts = $line.Trim() -split '\s+'
    $targetPid = $parts[-1]
    if ($targetPid -match '^\d+$' -and $targetPid -ne "0") {
        try {
            $process = Get-Process -Id ([int]$targetPid) -ErrorAction Stop
            Stop-Process -Id ([int]$targetPid) -Force
            Write-Host "  Dihentikan: PID $targetPid ($($process.ProcessName))" -ForegroundColor Green
            $stopped++
        } catch {
            Write-Host "  Gagal menghentikan PID $targetPid : $_" -ForegroundColor Red
        }
    }
}

Write-Host ""
if ($stopped -gt 0) {
    Write-Host "Server POS LAN dihentikan ($stopped proses)." -ForegroundColor Green
} else {
    Write-Host "Tidak ada proses yang dihentikan." -ForegroundColor Yellow
}
Write-Host "Server billing (port 8001) tidak disentuh." -ForegroundColor Gray
Write-Host ""
Read-Host "Tekan Enter untuk menutup jendela ini..."

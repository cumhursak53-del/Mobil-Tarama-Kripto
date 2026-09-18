# Krpito Live — yalnizca Bybit canli motor (Flet/MTF arayuzu acilmaz)
# Usage: .\scripts\start_live_stack.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$env:KRPITO_MODE = "live"

if (-not (Test-Path "live.env")) {
    if (Test-Path "live.env.example") {
        Copy-Item "live.env.example" "live.env"
        Write-Host "live.env olusturuldu (live.env.example dosyasindan)." -ForegroundColor Yellow
        Write-Host "Bybit testnet API anahtarlarinizi live.env dosyasina ekleyin." -ForegroundColor Yellow
    }
}

Get-Content "live.env" -ErrorAction SilentlyContinue | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line -match "=") {
        $k, $v = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
    }
}

Get-Content "local.env" -ErrorAction SilentlyContinue | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line -match "=") {
        $k, $v = $line.Split("=", 2)
        if (-not [Environment]::GetEnvironmentVariable($k.Trim(), "Process")) {
            [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
        }
    }
}

$python = $null
foreach ($cmd in @("py -3", "python", "python3")) {
    try {
        $null = & cmd /c "$cmd --version" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $cmd; break }
    } catch { }
}
if (-not $python) {
    Write-Host "HATA: Python bulunamadi." -ForegroundColor Red
    exit 1
}

& cmd /c "$python -c `"import requests, pandas`"" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Bagimliliklar yukleniyor..." -ForegroundColor Cyan
    & cmd /c "$python -m pip install -r requirements-live.txt"
}

$engineUrl = if ($env:ENGINE_URL) { $env:ENGINE_URL } else { "http://127.0.0.1:10001" }
try {
    $null = Invoke-RestMethod -Uri $engineUrl -TimeoutSec 2
    Write-Host "Canli motor zaten calisiyor: $engineUrl" -ForegroundColor Green
    Write-Host "Ikinci pencere acilmadi. Durdurmak icin mevcut motor penceresini kapatin." -ForegroundColor Yellow
    Start-Sleep -Seconds 4
    exit 0
} catch {
    Write-Host "Krpito Live baslatiliyor (Hacim + PiyasaEvresi)..." -ForegroundColor Cyan
    Write-Host "API: $engineUrl | Durdurmak icin bu pencereyi kapatin veya Ctrl+C" -ForegroundColor Gray
    Write-Host ""
}

& cmd /c "$python start_live.py"

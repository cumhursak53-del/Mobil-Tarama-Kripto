# Krpito Live — PC tarayici arayuzu (VPS motoruna baglanir)
# Usage: .\scripts\start_live_ui.ps1
# VPS portu kapaliysa once SSH tuneli acin (asagiya bakin).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$env:KRPITO_MODE = "live"
$env:KRPITO_REMOTE_ONLY = "1"

# live.env icinden REMOTE_ENGINE_URL veya ENGINE_URL oku
$remoteUrl = $env:REMOTE_ENGINE_URL
if (-not $remoteUrl -and (Test-Path "live.env")) {
    Get-Content "live.env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -match "^REMOTE_ENGINE_URL=(.+)$") { $remoteUrl = $Matches[1].Trim() }
        elseif (-not $remoteUrl -and $line -match "^ENGINE_URL=(.+)$") {
            $candidate = $Matches[1].Trim()
            if ($candidate -notmatch "127\.0\.0\.1|localhost") { $remoteUrl = $candidate }
        }
    }
}
if (-not $remoteUrl) {
    $remoteUrl = "http://76.13.150.125:10001"
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

& cmd /c "$python -c `"import streamlit, requests`"" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Streamlit yukleniyor..." -ForegroundColor Cyan
    & cmd /c "$python -m pip install streamlit streamlit-autorefresh -q"
}

Write-Host ""
Write-Host "Krpito Live arayuzu" -ForegroundColor Cyan
Write-Host "Veri kaynagi: $remoteUrl" -ForegroundColor Gray
Write-Host ""

try {
    $null = Invoke-RestMethod -Uri $remoteUrl -TimeoutSec 5
    Write-Host "VPS motoru erisilebilir." -ForegroundColor Green
} catch {
    Write-Host "UYARI: VPS motoruna ulasilamadi ($remoteUrl)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Cozum secenekleri:" -ForegroundColor Yellow
    Write-Host "  1) Hostinger firewall'da TCP 10001 acin, live.env icine:" -ForegroundColor Gray
    Write-Host "     REMOTE_ENGINE_URL=http://76.13.150.125:10001" -ForegroundColor Gray
    Write-Host "  2) SSH tuneli (ayri terminal):" -ForegroundColor Gray
    Write-Host "     ssh -L 10001:127.0.0.1:10001 root@76.13.150.125" -ForegroundColor Gray
    Write-Host "     sonra live.env: REMOTE_ENGINE_URL=http://127.0.0.1:10001" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Baglanti olmadan arayuz acilacak; veri bos gelebilir." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}

$env:REMOTE_ENGINE_URL = $remoteUrl
$env:ENGINE_URL = $remoteUrl

Write-Host "Tarayici: http://localhost:8501" -ForegroundColor Green
Write-Host "Durdurmak icin bu pencerede Ctrl+C" -ForegroundColor Gray
Write-Host ""

& cmd /c "$python -m streamlit run app.py --server.headless true"

# Render Worker env — render.env dosyasini Render'a uygular
# Usage:
#   $env:RENDER_API_KEY = "rnd_..."
#   $env:GEMINI_API_KEY = "AQ...."   # opsiyonel
#   .\scripts\configure_render_worker.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not $env:RENDER_API_KEY) {
    Write-Host "RENDER_API_KEY yok." -ForegroundColor Yellow
    Write-Host "GitHub: Settings -> Secrets -> RENDER_API_KEY" -ForegroundColor Cyan
    Write-Host "render.env dosyasindaki degiskenler:" -ForegroundColor Yellow
    Get-Content (Join-Path $root "render.env") | Where-Object { $_ -match "^[A-Z]" }
    Start-Process "https://github.com/cumhursak53-del/Mobil-Tarama-Kripto/settings/secrets/actions"
    exit 0
}

python (Join-Path $root "scripts/sync_render_env.py") --deploy

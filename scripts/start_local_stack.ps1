# Local Krpito stack: Ollama kontrol + motor + Flet masaustu
# Usage: .\scripts\start_local_stack.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$env:KRPITO_MODE = "desktop"

if (-not (Test-Path "local.env")) {
    if (Test-Path "local.env.example") {
        Copy-Item "local.env.example" "local.env"
        Write-Host "local.env olusturuldu (local.env.example'dan)." -ForegroundColor Yellow
    }
}

Get-Content "local.env" -ErrorAction SilentlyContinue | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line -match "=") {
        $k, $v = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
    }
}

# Python bul (py launcher veya PATH)
$python = $null
foreach ($cmd in @("py -3", "python", "python3")) {
    try {
        $null = & cmd /c "$cmd --version" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $cmd; break }
    } catch { }
}
if (-not $python) {
    Write-Host "HATA: Python bulunamadi. Python 3.12+ kurun." -ForegroundColor Red
    exit 1
}

# Flet kontrol
& cmd /c "$python -c `"import flet`"" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Flet yukleniyor (requirements-desktop.txt)..." -ForegroundColor Cyan
    & cmd /c "$python -m pip install -r requirements-desktop.txt"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "HATA: pip install basarisiz." -ForegroundColor Red
        exit 1
    }
}

$ollamaUrl = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL } else { "http://127.0.0.1:11434" }
try {
    $null = Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 4
    Write-Host "Ollama: OK ($ollamaUrl)" -ForegroundColor Green
} catch {
    Write-Host "UYARI: Ollama erisilemiyor. 'ollama serve' calistirin." -ForegroundColor Yellow
}

$engineUrl = if ($env:ENGINE_URL) { $env:ENGINE_URL } else { "http://127.0.0.1:10000" }
try {
    $null = Invoke-RestMethod -Uri $engineUrl -TimeoutSec 2
    Write-Host "Motor: zaten calisiyor ($engineUrl)" -ForegroundColor Green
} catch {
    Write-Host "Motor baslatiliyor..." -ForegroundColor Cyan
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "$python start.py" -WorkingDirectory $root -WindowStyle Minimized
    Start-Sleep -Seconds 5
    try {
        $null = Invoke-RestMethod -Uri $engineUrl -TimeoutSec 4
        Write-Host "Motor: baslatildi" -ForegroundColor Green
    } catch {
        Write-Host "UYARI: Motor henuz hazir degil; Flet yine de acilacak." -ForegroundColor Yellow
    }
}

Write-Host "Flet masaustu aciliyor..." -ForegroundColor Cyan
& cmd /c "$python -m desktop.main"
exit $LASTEXITCODE

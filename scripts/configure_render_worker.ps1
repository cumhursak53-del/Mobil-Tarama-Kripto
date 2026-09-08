# Render Worker env vars for mobil-tarama-kripto.onrender.com
# Usage:
#   $env:RENDER_API_KEY = "rnd_..."
#   .\scripts\configure_render_worker.ps1

$ErrorActionPreference = "Stop"
$ServiceName = "mobil-tarama-kripto"

$EnvVars = [ordered]@{
    ENTRY_MODE_DEFAULT         = "live"
    LIVE_ENTRY_LEDGERS         = "Kasa_RejimOsilator,Kasa_PatlamaSelale,Kasa_TrendCizgisi,Kasa_PulbackRetest,Kasa_DUK,Kasa_Tuzak,Kasa_Dominance,Kasa_SMA9_14,Kasa_EMA_Fib,Kasa_DinamikMA,Kasa_PiyasaEvresi,Kasa_MumOnay,Kasa_YapiKirilim,Kasa_RSI_Uyumsuzluk,Kasa_RSI_Bolge,Kasa_MACD,Kasa_BB_Squeeze,Kasa_CCI,Kasa_Stoch,Kasa_StochRSI,Kasa_Ichimoku,Kasa_Hacim,Kasa_OBO_TOBO,Kasa_IkiliDipTepe,Kasa_Ucgen,Kasa_BayrakFlama,Kasa_Dortgen,Kasa_FincanCanak,Kasa_Takoz,Kasa_Fib618,Kasa_SMC"
    RESEARCH_ENABLED           = "1"
    LAB_AUTO                   = "1"
    LAB_AUTO_INTERVAL_SEC      = "1800"
    YOUTUBE_MAX_VIDEOS_PER_RUN = "3"
    YOUTUBE_VIDEO_IDS          = "DHqGzh5PN0s,Nmu5Rkt7Mjw"
    YOUTUBE_CHANNEL_IDS        = "@teknikanalizdersleri"
    LAB_MAX_CANDIDATES         = "8"
}

function Show-ManualInstructions {
    Write-Host ""
    Write-Host "Render Dashboard -> Worker ($ServiceName) -> Environment" -ForegroundColor Cyan
    Write-Host "Add/update these variables, Save Changes, Manual Deploy:" -ForegroundColor Yellow
    Write-Host ""
    foreach ($kv in $EnvVars.GetEnumerator()) {
        Write-Host ("  {0} = {1}" -f $kv.Key, $kv.Value)
    }
    Write-Host ""
    Write-Host "Keep existing GEMINI_API_KEY if already set." -ForegroundColor DarkGray
    Start-Process "https://dashboard.render.com/"
}

$apiKey = $env:RENDER_API_KEY
if (-not $apiKey) {
    Write-Host "RENDER_API_KEY not set - manual setup:" -ForegroundColor Yellow
    Show-ManualInstructions
    exit 0
}

$headers = @{
    Authorization  = "Bearer $apiKey"
    Accept         = "application/json"
    "Content-Type" = "application/json"
}

Write-Host "Searching Render services..." -ForegroundColor Cyan
$services = Invoke-RestMethod -Uri "https://api.render.com/v1/services?limit=100" -Headers $headers -TimeoutSec 30
$svc = $services | ForEach-Object { $_.service } | Where-Object {
    $_.name -eq $ServiceName -or ($_.serviceDetails.url -like "*$ServiceName*")
} | Select-Object -First 1

if (-not $svc) {
    Write-Host "Service not found: $ServiceName" -ForegroundColor Red
    Show-ManualInstructions
    exit 1
}

Write-Host "Service: $($svc.name) ($($svc.id))" -ForegroundColor Green

$existing = Invoke-RestMethod -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars" -Headers $headers -TimeoutSec 30
$map = @{}
foreach ($row in $existing) {
    if ($row.envVar.key) { $map[$row.envVar.key] = $row.envVar.value }
}
foreach ($kv in $EnvVars.GetEnumerator()) {
    $map[$kv.Key] = $kv.Value
}

$body = @(
    foreach ($key in $map.Keys) {
        @{ key = $key; value = $map[$key] }
    }
) | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Put -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars" -Headers $headers -Body $body -TimeoutSec 60 | Out-Null
Write-Host "Env vars updated." -ForegroundColor Green

Write-Host "Triggering deploy..." -ForegroundColor Cyan
Invoke-RestMethod -Method Post -Uri "https://api.render.com/v1/services/$($svc.id)/deploys" -Headers $headers -Body "{}" -TimeoutSec 60 | Out-Null
$url = "https://" + $ServiceName + ".onrender.com"
Write-Host "Deploy started: $url" -ForegroundColor Green

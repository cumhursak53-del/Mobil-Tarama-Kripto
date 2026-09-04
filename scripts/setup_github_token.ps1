# GitHub token -> Render kurulum (tek seferlik)
# Token dosyaya yazilmaz; panoya kopyalanir.

$ErrorActionPreference = "Stop"
$Repo = "cumhursak53-del/Mobil-Tarama-Kripto"

function Get-GitHubToken {
    $inputText = "protocol=https`nhost=github.com`n"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "git"
    $psi.Arguments = "credential fill"
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.UseShellExecute = $false
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.StandardInput.Write($inputText)
    $p.StandardInput.Close()
    $out = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()
    foreach ($line in $out -split "`n") {
        if ($line -like "password=*") {
            return $line.Substring(9).Trim()
        }
    }
    return ""
}

$token = Get-GitHubToken
if (-not $token) {
    Write-Host "GitHub token bulunamadi. Once GitHub'a git ile giris yap." -ForegroundColor Red
    exit 1
}

$headers = @{
    Authorization = "Bearer $token"
    Accept        = "application/vnd.github+json"
    "User-Agent"  = "KrpitoSetup"
}
try {
    $repoInfo = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo" -Headers $headers -TimeoutSec 20
    if (-not $repoInfo.permissions.push) {
        Write-Host "Token repo yazma yetkisi yok." -ForegroundColor Red
        exit 1
    }
    Write-Host "GitHub token OK ($($token.Substring(0,4))..., repo: $($repoInfo.full_name))" -ForegroundColor Green
} catch {
    Write-Host "GitHub test basarisiz: $_" -ForegroundColor Red
    exit 1
}

Set-Clipboard -Value $token

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " TOKEN PANOYA KOPYALANDI (Ctrl+V)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Render Worker servisi -> Environment:" -ForegroundColor Yellow
Write-Host "  GITHUB_TOKEN  = Ctrl+V yap"
Write-Host "  GITHUB_REPO   = $Repo"
Write-Host ""
Write-Host "Kaydet -> Manual Deploy"
Write-Host ""
Write-Host "Not: gho OAuth token gecici olabilir." -ForegroundColor DarkGray
Write-Host "Kalici cozum: GitHub -> Settings -> Developer settings -> Fine-grained token" -ForegroundColor DarkGray
Write-Host "  Repo: $Repo | Permission: Contents Read/Write"
Write-Host ""

Start-Process "https://dashboard.render.com/"
Start-Process "https://github.com/settings/personal-access-tokens/new"

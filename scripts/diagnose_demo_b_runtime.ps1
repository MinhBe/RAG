$ErrorActionPreference = "Continue"
Set-Location (Resolve-Path "$PSScriptRoot\..")
Write-Host "=== docker compose ps ==="
docker compose ps
Write-Host "=== health ==="
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
    Write-Host ("health_status=" + [int]$r.StatusCode)
    Write-Host $r.Content
} catch {
    Write-Host ("health_error=" + $_.Exception.GetType().Name)
    Write-Host $_.Exception.Message
}
Write-Host "=== logs tail ==="
docker compose logs --tail=120 hermes-api

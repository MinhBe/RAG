$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Admin\Documents\Hermes'
Write-Host '--- 9Router status before ---'
$ready = $false
try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:20128/v1/models' -UseBasicParsing -TimeoutSec 5
    Write-Host ('status=' + [int]$r.StatusCode)
    $ready = $true
} catch {
    Write-Host 'status=unreachable'
    Write-Host ('error=' + $_.Exception.GetType().Name)
}
Write-Host ('router_ready_before=' + $ready)
if (-not $ready) {
    Write-Host '--- attempting start ---'
    if (Test-Path 'scripts\start-9router.ps1') {
        Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File','C:\Users\Admin\Documents\Hermes\scripts\start-9router.ps1'
        Start-Sleep -Seconds 10
    } else {
        Write-Host 'start_script_missing=True'
    }
}
Write-Host '--- 9Router status after ---'
try {
    $r2 = Invoke-WebRequest -Uri 'http://127.0.0.1:20128/v1/models' -UseBasicParsing -TimeoutSec 8
    Write-Host ('status=' + [int]$r2.StatusCode)
    Write-Host 'router_ready_after=True'
} catch {
    Write-Host 'router_ready_after=False'
    Write-Host ('error=' + $_.Exception.GetType().Name)
}

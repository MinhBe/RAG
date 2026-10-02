$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")

function Invoke-Checked($Name, $Command) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Test-Http($Uri, $TimeoutSec = 3) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec $TimeoutSec
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Ensure-DockerDesktop {
    try {
        docker version | Out-Host
        return
    } catch {
        Write-Host "Docker daemon is not ready. Attempting to start Docker Desktop." -ForegroundColor Yellow
    }

    $candidates = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $dockerDesktop = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($dockerDesktop) {
        Start-Process -FilePath $dockerDesktop | Out-Null
    }

    for ($i = 0; $i -lt 90; $i++) {
        try {
            docker version | Out-Null
            Write-Host "Docker daemon ready."
            return
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Docker daemon did not become ready. Open Docker Desktop manually and rerun this script."
}

function Ensure-9Router {
    if (Test-Http "http://127.0.0.1:20128/v1/models" 5) {
        Write-Host "9Router already reachable."
        return
    }

    Write-Host "9Router not reachable. Attempting to start it." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $PSScriptRoot "start-9router.ps1")
    ) | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        if (Test-Http "http://127.0.0.1:20128/v1/models" 5) {
            Write-Host "9Router reachable."
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "9Router did not become reachable on http://127.0.0.1:20128/v1/models."
}

function Ensure-HermesApi {
    docker compose up -d --build --force-recreate | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
    }
    for ($i = 0; $i -lt 40; $i++) {
        if (Test-Http "http://127.0.0.1:8000/health" 3) {
            Write-Host "Hermes API healthy."
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "Hermes API did not become healthy."
}

Write-Host "Hermes Demo B Security runner" -ForegroundColor Green
Write-Host "Repo: $(Get-Location)"

Ensure-DockerDesktop
Ensure-9Router
Ensure-HermesApi

Invoke-Checked "compileall" { uv run python -m compileall app scripts tests training | Out-Host }
Invoke-Checked "ruff" { uv run ruff check app tests scripts training | Out-Host }
Invoke-Checked "pytest" { uv run pytest -q | Out-Host }
Invoke-Checked "Demo B security" { uv run python scripts/demo_security_b.py | Out-Host }
Invoke-Checked "Supabase readback demo" { uv run python scripts/demo_end_to_end.py | Out-Host }

Write-Host "`nPASS Hermes Demo B Security end-to-end" -ForegroundColor Green

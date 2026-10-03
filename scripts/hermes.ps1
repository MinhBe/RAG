param(
  [Parameter(Position=0)] [string]$Command = "help",
  [string]$ApiHost = "127.0.0.1",
  [int]$Port = 8000
)
$ErrorActionPreference = "Stop"

$Repo = Split-Path $PSScriptRoot -Parent
Set-Location $Repo
$ApiLog = Join-Path $Repo "artifacts\hermes_api.log"
$TelegramLog = Join-Path $Repo "artifacts\telegram_bot.runner.log"
$RouterLog = Join-Path $Repo "artifacts\9router.log"
$RouterHost = "127.0.0.1"
$RouterPort = 20128

function Show-Help {
  @"
Hermes local control CLI

Usage:
  hermes status
  hermes router
  hermes router-bg
  hermes demo-a
  hermes gate
  hermes api
  hermes api-bg
  hermes telegram
  hermes telegram-bg
  hermes up
  hermes full-up
  hermes stop

Alias typo kept intentionally: hermers <command>
"@
}

function Get-HermesRuntimeProcess {
  Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -match 'uvicorn app\.main:app' -or
      $_.CommandLine -match 'run_telegram_bot\.py'
    )
  }
}

function Get-RouterProcess {
  Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -match '9router\\cli\.js' -or
      $_.CommandLine -match 'node_modules\\9router\\cli\.js' -or
      $_.CommandLine -match 'start-9router\.ps1'
    )
  }
}

function Test-PortOpen([string]$TargetHost, [int]$TargetPort) {
  $client = New-Object Net.Sockets.TcpClient
  try {
    $iar = $client.BeginConnect($TargetHost, $TargetPort, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(500, $false)
    if (-not $ok) { return $false }
    $client.EndConnect($iar)
    return $true
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Test-HttpOk([string]$Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
    return ([int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Test-DotEnvValue([string]$Name) {
  $envFile = Join-Path $Repo ".env"
  if (-not (Test-Path $envFile)) { return $false }
  $line = Get-Content $envFile | Where-Object { $_ -match "^$Name\s*=" } | Select-Object -Last 1
  if (-not $line) { return $false }
  $value = ($line -split '=', 2)[1].Trim()
  return -not [string]::IsNullOrWhiteSpace($value)
}

function Show-Status {
  Write-Output "Hermes repo: $Repo"
  if (Test-PortOpen $RouterHost $RouterPort) {
    $modelsOk = Test-HttpOk "http://${RouterHost}:${RouterPort}/v1/models"
    Write-Output "9Router port ${RouterPort}: listening"
    Write-Output "9Router /v1/models: $(if ($modelsOk) { 'reachable' } else { 'not reachable' })"
  } else {
    Write-Output "9Router port ${RouterPort}: not listening"
  }
  if (Test-PortOpen $ApiHost $Port) {
    Write-Output "API port ${Port}: listening"
  } else {
    Write-Output "API port ${Port}: not listening"
  }

  $runners = Get-HermesRuntimeProcess
  if ($runners | Where-Object { $_.CommandLine -match 'run_telegram_bot\.py' }) {
    Write-Output "Telegram runner: running"
  } else {
    Write-Output "Telegram runner: not running"
  }

  Write-Output "Configured .env booleans:"
  @(
    "TELEGRAM_ALLOWED_CHAT_ID",
    "TELEGRAM_SWAIN_BOT_TOKEN",
    "TELEGRAM_SHEN_BOT_TOKEN",
    "TELEGRAM_GAREN_BOT_TOKEN",
    "TELEGRAM_KAYN_BOT_TOKEN",
    "TELEGRAM_TARIC_BOT_TOKEN",
    "TELEGRAM_XINZHAO_BOT_TOKEN",
    "AI_BASE_URL",
    "AI_API_KEY",
    "AI_MODEL",
    "HERMES_A_LLM_ENABLED"
  ) | ForEach-Object {
    $configured = if (Test-DotEnvValue $_) { "yes" } else { "no" }
    Write-Output "  ${_}: $configured"
  }

  $routerProcs = Get-RouterProcess
  if ($routerProcs) {
    Write-Output "9Router processes:"
    $routerProcs | ForEach-Object { Write-Output "  $($_.ProcessId) $($_.CommandLine)" }
  }
  if ($runners) {
    Write-Output "Runtime processes:"
    $runners | ForEach-Object { Write-Output "  $($_.ProcessId) $($_.CommandLine)" }
  }
}

function Start-RouterBackground {
  if (Test-HttpOk "http://${RouterHost}:${RouterPort}/v1/models") {
    Write-Output "9router already reachable at http://${RouterHost}:${RouterPort}"
    return
  }
  New-Item -ItemType Directory -Force -Path (Split-Path $RouterLog) | Out-Null
  $cmd = "Set-Location '$Repo'; powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-9router.ps1 *> '$RouterLog'"
  Start-Process -WindowStyle Minimized -FilePath powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`""
  Write-Output "started 9router; log=$RouterLog"
  for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    if (Test-HttpOk "http://${RouterHost}:${RouterPort}/v1/models") {
      Write-Output "9router ready"
      return
    }
  }
  Write-Output "9router started but /v1/models is not reachable yet"
}

function Start-ApiBackground {
  if (Test-PortOpen $ApiHost $Port) {
    Write-Output "api already listening at http://${ApiHost}:${Port}"
    return
  }
  New-Item -ItemType Directory -Force -Path (Split-Path $ApiLog) | Out-Null
  $cmd = "Set-Location '$Repo'; uv run uvicorn app.main:app --host $ApiHost --port $Port *> '$ApiLog'"
  Start-Process -WindowStyle Minimized -FilePath powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`""
  Write-Output "started api; log=$ApiLog"
}

function Start-TelegramBackground {
  $existing = Get-HermesRuntimeProcess | Where-Object { $_.CommandLine -match 'run_telegram_bot\.py' }
  if ($existing) {
    Write-Output "telegram runner already running"
    return
  }
  New-Item -ItemType Directory -Force -Path (Split-Path $TelegramLog) | Out-Null
  $cmd = "Set-Location '$Repo'; uv run python scripts/run_telegram_bot.py *> '$TelegramLog'"
  Start-Process -WindowStyle Minimized -FilePath powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`""
  Write-Output "started telegram; log=$TelegramLog"
}

function Stop-HermesRuntime {
  $targets = @(Get-HermesRuntimeProcess)
  if (-not $targets) {
    Write-Output "no hermes api/telegram runtime processes found"
  } else {
    $targets | ForEach-Object {
      Write-Output "stopping $($_.ProcessId) $($_.CommandLine)"
      Stop-Process -Id $_.ProcessId -Force
    }
  }
}

switch ($Command.ToLowerInvariant()) {
  "help" { Show-Help; break }
  "status" { Show-Status; break }
  "router" { powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-9router.ps1; break }
  "router-bg" { Start-RouterBackground; break }
  "demo-a" { uv run python scripts/run_hermes_a_demo.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; break }
  "gate" {
    uv run python -m compileall -q app scripts tests training
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    uv run ruff check app scripts tests training
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    uv run pytest -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    uv run python scripts/run_hermes_a_demo.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output "HERMES_GATE_PASS"
    break
  }
  "api" { uv run uvicorn app.main:app --host $ApiHost --port $Port; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; break }
  "api-bg" { Start-ApiBackground; break }
  "telegram" { uv run python scripts/run_telegram_bot.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; break }
  "telegram-bg" { Start-TelegramBackground; break }
  "up" { Start-RouterBackground; Start-ApiBackground; Start-TelegramBackground; Start-Sleep -Seconds 2; Show-Status; break }
  "full-up" { Start-RouterBackground; Start-ApiBackground; Start-TelegramBackground; Start-Sleep -Seconds 2; Show-Status; break }
  "stop" { Stop-HermesRuntime; break }
  default { Write-Error "Unknown Hermes command: $Command"; Show-Help; exit 2 }
}

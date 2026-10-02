$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Admin\Documents\Hermes'
Write-Host '=== HERMES DEMO B PREFLIGHT ==='
Write-Host ('time=' + (Get-Date -Format o))
Write-Host ('pwd=' + (Get-Location))

Write-Host '--- git ---'
git branch --show-current
git status --short
git remote -v

Write-Host '--- local files ---'
$paths = @(
  'pyproject.toml', 'uv.lock', '.env', '.env.example',
  'docker-compose.yml', 'app\main.py',
  'scripts\demo_end_to_end.py', 'scripts\check_kaggle.py',
  'scripts\check_kaggle_credentials.ps1', 'training\seqgan'
)
foreach ($path in $paths) {
  Write-Host ($path + '=' + [bool](Test-Path $path))
}
Write-Host '--- env presence only ---'
if (Test-Path '.env') {
  $envText = Get-Content '.env' -Raw
  $keys = @('AI_BASE_URL','AI_API_KEY','AI_MODEL','SUPABASE_URL','SUPABASE_SECRET_KEY')
  foreach ($key in $keys) {
    $configured = [bool]($envText -match ('(?m)^' + [regex]::Escape($key) + '=.+'))
    Write-Host ($key + '_configured=' + $configured)
  }
} else {
  Write-Host '.env_configured=False'
}

Write-Host '--- commands ---'
$commands = @('uv','python','git','docker','node','npm','vercel','gh')
foreach ($cmd in $commands) {
  $found = Get-Command $cmd -ErrorAction SilentlyContinue
  Write-Host ($cmd + '_available=' + [bool]$found)
}
Write-Host '--- docker ---'
try { docker version --format '{{.Server.Version}}' } catch { Write-Host ('docker_version_error=' + $_.Exception.GetType().Name) }
try { docker info --format '{{.ServerVersion}} {{.OperatingSystem}}' } catch { Write-Host ('docker_info_error=' + $_.Exception.GetType().Name) }
try { docker compose ps } catch { Write-Host ('compose_ps_error=' + $_.Exception.GetType().Name) }

Write-Host '--- ports/http ---'
$urls = @(
  'http://127.0.0.1:8000/health',
  'http://127.0.0.1:8000/health/providers',
  'http://127.0.0.1:20128/v1/models'
)
foreach ($url in $urls) {
  try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
    Write-Host ($url + ' status=' + $response.StatusCode)
  } catch {
    Write-Host ($url + ' error=' + $_.Exception.GetType().Name)
  }
}
Write-Host '--- kaggle ---'
if (Test-Path 'scripts\check_kaggle.py') {
  uv run python scripts\check_kaggle.py
} else {
  Write-Host 'check_kaggle_missing=True'
}
if (Test-Path 'scripts\check_kaggle_credentials.ps1') {
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_kaggle_credentials.ps1
} else {
  Write-Host 'check_kaggle_credentials_missing=True'
}

Write-Host '--- vercel/github auth ---'
try { gh auth status 2>&1 } catch { Write-Host ('gh_auth_error=' + $_.Exception.GetType().Name) }
try { vercel whoami 2>&1 } catch { Write-Host ('vercel_whoami_error=' + $_.Exception.GetType().Name) }
Write-Host '--- quick quality gates ---'
uv run python -m compileall -q app scripts 2>&1
Write-Host ('compileall_exit=' + $LASTEXITCODE)

uv run ruff check app tests scripts 2>&1
Write-Host ('ruff_exit=' + $LASTEXITCODE)

uv run pytest -q 2>&1
Write-Host ('pytest_exit=' + $LASTEXITCODE)

Write-Host '=== PREFLIGHT_DONE ==='

$ErrorActionPreference = 'Stop'
$project = 'C:\Users\Admin\Documents\Hermes'
$primaryPath = Join-Path $env:USERPROFILE '.kaggle\kaggle.json'
$backupPath = Join-Path $env:USERPROFILE '.kaggle\backup\kaggle_token_backup.clixml'
$accessTokenPath = Join-Path $env:USERPROFILE '.kaggle\access_token'
Set-Location $project

function Convert-SecureStringToPlainText($secure) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

Write-Host '=== Kaggle primary legacy token ==='
Write-Host ('primary_path_exists=' + (Test-Path $primaryPath))
$primaryUser = ''
$primaryKey = ''
if (Test-Path $primaryPath) {
    $primary = Get-Content $primaryPath -Raw | ConvertFrom-Json
    $primaryUser = [string]$primary.username
    $primaryKey = [string]$primary.key
    Write-Host ('primary_username_configured=' + [bool]$primaryUser)
    Write-Host ('primary_key_configured=' + [bool]$primaryKey)
    Write-Host ('primary_key_length_gt_20=' + ($primaryKey.Length -gt 20))
}
Write-Host '=== Kaggle primary authenticate ==='
try {
    uv run python scripts\check_kaggle.py
} catch {
    Write-Host ('primary_check_error=' + $_.Exception.GetType().Name)
}

Write-Host '=== Kaggle backup DPAPI token ==='
Write-Host ('backup_path_exists=' + (Test-Path $backupPath))
$backupUser = ''
$backupKey = ''
if (Test-Path $backupPath) {
    try {
        $backupLoaded = Import-Clixml $backupPath
        $backupUser = [string]$backupLoaded.username
        $secureKey = ConvertTo-SecureString ([string]$backupLoaded.encrypted_key)
        $backupKey = Convert-SecureStringToPlainText $secureKey
        Write-Host ('backup_username_configured=' + [bool]$backupUser)
        Write-Host ('backup_key_configured=' + [bool]$backupKey)
        Write-Host ('backup_key_length_gt_20=' + ($backupKey.Length -gt 20))
        Write-Host ('backup_same_username_as_primary=' + ($backupUser -eq $primaryUser))
        Write-Host ('backup_same_key_as_primary=' + ($backupKey -eq $primaryKey))
    } catch {
        Write-Host ('backup_decrypt_error=' + $_.Exception.GetType().Name)
    }
}
if ($backupUser -and $backupKey) {
    Write-Host '=== Kaggle backup authenticate ==='
    $oldUser = $env:KAGGLE_USERNAME
    $oldKey = $env:KAGGLE_KEY
    $env:KAGGLE_USERNAME = $backupUser
    $env:KAGGLE_KEY = $backupKey
    $tmp = Join-Path $env:TEMP 'hermes_check_kaggle_backup.py'
    @'
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    print('backup_kaggle_authenticate=True')
    print('backup_kaggle_ready=True')
except Exception as exc:
    print('backup_kaggle_authenticate=False')
    print('backup_auth_error_type=' + type(exc).__name__)
    print('backup_kaggle_ready=False')
'@ | Set-Content -Path $tmp -Encoding UTF8
    try { uv run python $tmp } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        $env:KAGGLE_USERNAME = $oldUser
        $env:KAGGLE_KEY = $oldKey
    }
}
Write-Host '=== Kaggle new CLI quota capability ==='
Write-Host ('access_token_path_exists=' + (Test-Path $accessTokenPath))
if (Test-Path $accessTokenPath) {
    try { uv run kaggle quota --format json }
    catch { Write-Host ('quota_error=' + $_.Exception.GetType().Name) }
} else {
    Write-Host 'quota_available_via_cli=False'
    Write-Host 'quota_reason=missing OAuth/API access token for new Kaggle CLI quota command'
}

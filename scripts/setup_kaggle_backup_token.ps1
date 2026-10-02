Write-Host "Hermes Kaggle BACKUP token setup"
Write-Host "This stores token #2 encrypted with Windows DPAPI for the current Windows user."
Write-Host "Nothing is sent to chat. Do not commit the backup file."

$backupDir = Join-Path $env:USERPROFILE ".kaggle\backup"
$backupPath = Join-Path $backupDir "kaggle_token_backup.clixml"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$username = Read-Host "Paste backup Kaggle username"
$secureKey = Read-Host "Paste backup Kaggle key" -AsSecureString

if ([string]::IsNullOrWhiteSpace($username)) {
    throw "Kaggle username is empty"
}
if ($secureKey.Length -lt 20) {
    throw "Kaggle key appears too short"
}
$backup = [pscustomobject]@{
    username = $username.Trim()
    encrypted_key = ($secureKey | ConvertFrom-SecureString)
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    storage = "Windows DPAPI CurrentUser"
    purpose = "Hermes Kaggle backup token"
}

$backup | Export-Clixml -Path $backupPath

try {
    icacls $backupDir /inheritance:r | Out-Null
    icacls $backupDir /grant:r "$($env:USERNAME):(OI)(CI)(F)" | Out-Null
    icacls $backupPath /inheritance:r | Out-Null
    icacls $backupPath /grant:r "$($env:USERNAME):(R,W)" | Out-Null
} catch {
    Write-Warning "Could not fully harden ACLs: $($_.Exception.Message)"
}
$backupLoaded = Import-Clixml -Path $backupPath
$hasUsername = -not [string]::IsNullOrWhiteSpace($backupLoaded.username)
$hasEncryptedKey = -not [string]::IsNullOrWhiteSpace($backupLoaded.encrypted_key)

Write-Host "backup_path=$backupPath"
Write-Host "username_configured=$hasUsername"
Write-Host "encrypted_key_configured=$hasEncryptedKey"
Write-Host "storage=Windows DPAPI CurrentUser"
Write-Host "Done. Backup token is encrypted at rest and is not used by Kaggle CLI unless restored."

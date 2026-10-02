Write-Host "Hermes Kaggle backup restore"
Write-Host "This restores the encrypted backup token into C:\Users\<you>\.kaggle\kaggle.json."

$backupPath = Join-Path $env:USERPROFILE ".kaggle\backup\kaggle_token_backup.clixml"
$tokenDir = Join-Path $env:USERPROFILE ".kaggle"
$tokenPath = Join-Path $tokenDir "kaggle.json"

if (-not (Test-Path $backupPath)) {
    throw "Backup file not found: $backupPath"
}

$backup = Import-Clixml -Path $backupPath
$secureKey = ConvertTo-SecureString $backup.encrypted_key
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
$json = [ordered]@{
    username = $backup.username
    key = $plainKey
} | ConvertTo-Json

New-Item -ItemType Directory -Force -Path $tokenDir | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tokenPath, $json, $utf8NoBom)

try {
    icacls $tokenPath /inheritance:r | Out-Null
    icacls $tokenPath /grant:r "$($env:USERNAME):(R,W)" | Out-Null
} catch {
    Write-Warning "Could not fully harden ACLs: $($_.Exception.Message)"
}

Write-Host "restored_token_path=$tokenPath"
Write-Host "username_configured=True"
Write-Host "key_configured=True"

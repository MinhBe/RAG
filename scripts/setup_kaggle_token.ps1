$ErrorActionPreference = "Stop"
Write-Host "Hermes Kaggle token setup"
Write-Host "Paste values from Kaggle API token. Nothing is sent to chat."
Write-Host ""

$username = Read-Host "Paste Kaggle username"
$keySecure = Read-Host "Paste Kaggle key" -AsSecureString

$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($keySecure)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($username)) {
    throw "Kaggle username is empty"
}
if ([string]::IsNullOrWhiteSpace($key)) {
    throw "Kaggle key is empty"
}
$kaggleDir = Join-Path $env:USERPROFILE ".kaggle"
$tokenPath = Join-Path $kaggleDir "kaggle.json"
New-Item -ItemType Directory -Force -Path $kaggleDir | Out-Null

$payload = [ordered]@{
    username = $username.Trim()
    key = $key.Trim()
}
$json = $payload | ConvertTo-Json
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tokenPath, $json, $utf8NoBom)

icacls $tokenPath /inheritance:r | Out-Null
icacls $tokenPath /grant:r "$($env:USERNAME):(R,W)" | Out-Null
$parsed = Get-Content -Raw -Path $tokenPath | ConvertFrom-Json
Write-Host "token_path=$tokenPath"
Write-Host "username_configured=$([bool]$parsed.username)"
Write-Host "key_configured=$([bool]$parsed.key)"
Write-Host "key_length_gt_20=$($parsed.key.Length -gt 20)"
Write-Host "Done. Now run: uv run python scripts\check_kaggle.py"

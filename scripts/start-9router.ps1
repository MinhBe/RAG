$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
node .tools\9router\node_modules\9router\cli.js --host 127.0.0.1 --port 20128 --no-browser --skip-update --log

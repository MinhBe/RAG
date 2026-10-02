param(
    [switch]$ProvisionBase,
    [int]$Limit = 16
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Step($Name, $Command) {
    Write-Host "`n=== $Name ==="
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name exit=$LASTEXITCODE"
    }
}

Step 'Compile' 'uv run python -m compileall -q app scripts tests training'
Step 'Lint' 'uv run ruff check app scripts tests training'

if ($ProvisionBase) {
    Step 'Provision Ubuntu base' 'uv run --with paramiko python scripts/provision_lab_base.py'
    Step 'Provision Suricata' 'uv run --with paramiko python scripts/provision_lab_suricata.py'
    Step 'Provision Atomic tooling' 'uv run --with paramiko python scripts/provision_lab_atomic.py'
}

Step 'Prepare SeqGAN V3 corpus' 'uv run python scripts/prepare_seqgan_corpus_v3.py --archive training/seqgan/data/raw/SQLGAN_PostgreSQL_Boolean_Attack_Structure_Corpus_V3.zip'
Step 'Provision PostgreSQL sandbox' 'uv run --with paramiko python scripts/provision_lab_postgres.py'
Step 'Provision WAF/CRS' 'uv run --with paramiko python scripts/provision_lab_waf.py'
Step 'Run PostgreSQL probe' "uv run --with paramiko python scripts/run_seqgan_postgres_probe.py --limit $Limit"
Step 'Run WAF probe' "uv run --with paramiko python scripts/run_seqgan_waf_probe.py --limit $Limit"
Step 'Build Hermes evidence' 'uv run python scripts/build_seqgan_lab_evidence.py'
Step 'Tests' 'uv run pytest -q'

Write-Host "`n=== SeqGAN Lab B complete ==="
Get-Content training/seqgan/data/processed/v3/runtime/postgres_probe_sample.summary.json
Get-Content training/seqgan/data/processed/v3/runtime/waf_probe_sample.summary.json
Get-Content artifacts/demo_b/seqgan_lab_triage_result.json -TotalCount 20

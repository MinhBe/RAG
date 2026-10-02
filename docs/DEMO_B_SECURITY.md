# Demo B — Hermes Security

Demo B is the recruiter-facing security slice for Hermes SOC Post-Audit.
It demonstrates that Hermes treats external text as evidence, preserves
human approval boundaries, stores an audit trail, and can be run end to end
from one command on the local machine.

## What it proves

- Schema enforcement: unknown fields and unredacted evidence are rejected.
- Evidence injection resistance: hostile text inside evidence is never used
  as an instruction to the system.
- Human-in-the-loop gate: high and critical hints require review rather
  than autonomous remediation.
- Evidence reference integrity: every finding must cite submitted evidence.
- Storage/readback: when Supabase is configured, demo runs are persisted
  and read back through the API.

## One-command run

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo_b.ps1
```

This command checks Docker, starts the API with `docker compose`, runs
compile, lint, tests, the Demo B security script, and the Supabase readback
demo.

## Demo cases

The fixture file is `data/public/security_demo_b.jsonl`.

- `DEMO-B-001`: prompt-injection text embedded in synthetic EDR evidence.
- `DEMO-B-002`: indirect-injection text quoted from a synthetic ticket.
- `DEMO-B-003`: benign low-severity baseline that should not create a claim.

## Safety boundary

Demo B does not exploit systems, scan targets, evade controls, or perform
autonomous remediation. It uses synthetic evidence only.

## Visible report

After a successful run, open:

```text
artifacts/demo_b/security_demo_b_report.html
```

The HTML report summarizes health, AI gateway reachability, Supabase status,
case outcomes, run UUIDs, and recruiter talking points.

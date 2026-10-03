
# Hermes Vaccine Lab Architecture

## Scope

This lab validates a controlled defensive vaccine workflow over a safe restricted Boolean oracle behind ModSecurity. Public artifacts are redacted. Private replay artifacts remain local only.

## Data flow

```text
Client / runner
  -> Apache + ModSecurity on Ubuntu lab VM :18080
  -> /bool_oracle
  -> safe Boolean oracle backend :18081
  -> TRUE/FALSE observation
  -> reward / detector / regression artifacts
```

## Sprint ladder

```text
Sprint 1  - Boolean vaccine generation lab
Sprint 2  - Vaccine effectiveness / temporary patch validation
Sprint 3  - Negative/control corpus expansion
Sprint 4  - Multi-family attack grammar expansion
Sprint 5  - SeqGAN adapter lineage and reward loop
Sprint 6  - One-command vaccine regression gate
Sprint 7  - Classical ML baseline
Sprint 8  - Human review workflow
Sprint 9  - Safe deployment modes
Sprint 10 - Drift / mutation robustness
Sprint 11 - Documentation and reproducibility pack
```

## Non-claims

- This is not a production WAF deployment.
- This is not broad SQL injection protection.
- This does not claim vendor full raw SeqGAN self-clean generation.
- Public artifacts must not expose sensitive raw payload material.


# Hermes Vaccine Lab Claim Boundary

The valid claim is:

```text
Controlled lab defensive validation over a safe restricted Boolean oracle behind ModSecurity. Public artifacts are redacted. Regression, review, deployment-mode, mutation, and ML-baseline workflows are validated as lab artifacts.
```

Invalid claims:

```text
This is production WAF protection.
This is broad SQL injection protection.
This proves vendor full raw SeqGAN generated clean accepted outputs unaided.
This replaces analyst review.
This can be used safely against public targets.
```

Operational rule:

```text
If a result lacks command output, summary artifact, or replay instructions, it is not considered verified.
```

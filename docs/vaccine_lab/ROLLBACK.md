
# Hermes Vaccine Lab Rollback Instructions

Sprint 9 validates artifact-level safe deployment modes:

```text
observe -> detection-only -> blocking -> rollback to observe
```

Rollback evidence is stored in:

```text
artifacts/vaccine_sprints_8_9_10/rollback.summary.json
```

Required evidence:

```text
rollback_from = blocking
rollback_to = observe
health_check_after_rollback = PASS
```

This is an artifact-level deployment-mode validation. It does not mutate a production WAF.

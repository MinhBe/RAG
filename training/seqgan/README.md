# Hermes SeqGAN Training Lane

Purpose: generate synthetic SQLi-like payload candidates for defensive SOC evaluation only.

This lane is not an autonomous attack tool. Generated samples are for isolated lab testing, WAF/log-normalizer evaluation, and Hermes golden/security eval datasets.

## Authentication

Use Kaggle credentials only on the local machine:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_kaggle_token.ps1
uv run python scripts/check_kaggle.py
```

Never commit `kaggle.json`, raw downloaded datasets, generated checkpoints, or secrets.

## Directory map

- `data/raw/`: local Kaggle downloads, gitignored.
- `data/processed/`: derived defensive fixtures, gitignored unless sanitized and intentionally promoted.
- `checkpoints/`: local model checkpoints, gitignored.
- `src/`: training/data-prep code.

## Dataset policy

Use public datasets only when their license permits defensive research. Keep raw data local until reviewed. Promote only synthetic/redacted samples into Hermes eval fixtures.

## Next planned scripts

- dataset download manifest
- payload tokenizer
- SeqGAN generator/discriminator scaffold
- synthetic payload export into `evals/golden/`

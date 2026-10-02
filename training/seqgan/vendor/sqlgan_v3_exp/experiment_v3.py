# ruff: noqa
from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from .data_v3 import (
    MODULES,
    LabelMaps,
    V3TextDataset,
    make_weighted_sampler,
    materialize_dataset,
    read_attack_samples,
    row_to_contract,
    sample_rows_by_cell,
    training_text,
)
from .models import LSTMGenerator, MultiHeadDiscriminator, clean_state_dict, sample_after_prefix
from .reward_v3 import score_payload_v3
from .tokenizer import CharCodec, HybridSQLCodec
from .validators import parse_condition_prefix, repair_small, sha256_text, static_validate
from .strict_audit import parserlike_static_audit

DIRECTIONS = {
    1: "full_corpus_conditioned_mle",
    2: "contract_weighted_mle",
    3: "grammar_reward_policy_gradient",
    4: "multihead_discriminator_adv",
    5: "hybrid_token_mle",
    6: "constrained_decode_filter",
    7: "truth_pair_conditioned",
    8: "curriculum_y1_to_y4",
    9: "mle_guarded_adversarial",
    10: "generate_validate_repair_loop",
}


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def device_auto(requested: str) -> str:
    if requested != "auto":
        return requested
    return "cuda" if torch.cuda.is_available() else "cpu"


def autocast_ctx(device: str, amp: bool):
    if amp and str(device).startswith("cuda"):
        return torch.amp.autocast("cuda", dtype=torch.float16)
    return torch.amp.autocast("cpu", enabled=False)


def make_codec(texts: list[str], tokenizer: str, max_len: int):
    if tokenizer == "hybrid":
        return HybridSQLCodec.fit(texts, max_len=max_len)
    return CharCodec.fit(texts, max_len=max_len)


def train_mle_epoch(gen, loader, opt, pad_id: int, device: str, amp: bool = True) -> float:
    gen.train()
    ce = nn.CrossEntropyLoss(ignore_index=pad_id, reduction="sum")
    scaler = torch.amp.GradScaler("cuda", enabled=(amp and str(device).startswith("cuda")))
    total_loss = 0.0
    total_tok = 0
    for batch in tqdm(loader, desc="MLE", leave=False):
        x = batch["ids"].to(device, non_blocking=True)
        opt.zero_grad(set_to_none=True)
        with autocast_ctx(device, amp):
            logits = gen(x[:, :-1])
            tgt = x[:, 1:]
            loss_sum = ce(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1))
            ntok = int(tgt.ne(pad_id).sum().item())
            loss = loss_sum / max(ntok, 1)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(gen.parameters(), 5.0)
        scaler.step(opt)
        scaler.update()
        total_loss += float(loss_sum.detach().item())
        total_tok += ntok
    return total_loss / max(total_tok, 1)


def discriminator_step(disc, gen, loader, contracts, codec, opt_d, device: str, args, multihead: bool = False) -> float:
    disc.train()
    gen.eval()
    bce = nn.BCEWithLogitsLoss()
    ce = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler("cuda", enabled=(not args.no_amp and str(device).startswith("cuda")))
    losses = []
    n = len(contracts)
    for batch in tqdm(loader, desc="D", leave=False):
        real = batch["ids"].to(device, non_blocking=True)
        bsz = real.size(0)
        idx = np.random.randint(0, n, size=bsz).tolist()
        prefixes = [str(contracts[i].get("seqgan_prefix", "")) + " " for i in idx]
        with torch.no_grad():
            fake_out = sample_after_prefix(
                gen,
                codec,
                prefixes,
                max_new_tokens=args.max_new_tokens,
                temperature=args.temperature,
                device=device,
                top_k=args.top_k,
            )
            fake = fake_out.full
        opt_d.zero_grad(set_to_none=True)
        with autocast_ctx(device, not args.no_amp):
            r = disc(real)
            f = disc(fake)
            loss = bce(r["real_fake"], torch.ones_like(r["real_fake"])) + bce(f["real_fake"], torch.zeros_like(f["real_fake"]))
            if multihead:
                loss = loss + 0.25 * (
                    ce(r["root"], batch["root"].to(device))
                    + ce(r["cell"], batch["cell"].to(device))
                    + ce(r["truth"], batch["truth"].to(device))
                    + ce(r["module"], batch["module"].to(device))
                    + ce(r["rep"], batch["rep"].to(device))
                    + ce(r["syntax"], torch.ones(bsz, dtype=torch.long, device=device))
                )
        scaler.scale(loss).backward()
        scaler.step(opt_d)
        scaler.update()
        losses.append(float(loss.detach().item()))
    return float(np.mean(losses)) if losses else 0.0


def pg_epoch(gen, disc, codec, opt_g, contracts, training_hashes, device: str, args, *, guarded: bool = False) -> dict[str, float]:
    gen.train()
    if disc is not None:
        disc.eval()
    scaler = torch.amp.GradScaler("cuda", enabled=(not args.no_amp and str(device).startswith("cuda")))
    losses = []
    rewards = []
    static_rewards = []
    d_rewards = []
    recent: list[str] = []
    coverage_counts: Counter[str] = Counter()
    n = len(contracts)
    for _ in tqdm(range(max(0, args.adv_steps)), desc="PG", leave=False):
        idx = np.random.randint(0, n, size=args.batch_size).tolist()
        batch_contracts = [contracts[i] for i in idx]
        prefixes = [str(c.get("seqgan_prefix", "")) + " " for c in batch_contracts]
        out = sample_after_prefix(
            gen,
            codec,
            prefixes,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            device=device,
            top_k=args.top_k,
        )
        with torch.no_grad():
            if disc is not None:
                d_reward = torch.sigmoid(disc(out.full)["real_fake"]).float()
            else:
                d_reward = torch.full((len(batch_contracts),), 0.5, dtype=torch.float32, device=device)
            sv = [
                score_payload_v3(
                    text,
                    c,
                    training_hashes=training_hashes,
                    recent_payloads=recent,
                    coverage_count=coverage_counts[str(c.get("structure_cell_id", ""))],
                    max_len=codec.max_len,
                )
                for text, c in zip(out.decoded, batch_contracts)
            ]
            s_reward = torch.tensor([r.reward_total for r in sv], dtype=torch.float32, device=device)
            reward = (1.0 - args.static_weight) * d_reward + args.static_weight * s_reward
            if guarded:
                # Strongly suppress samples that break contracts.
                gate = torch.tensor([1.0 if r.contract_valid else 0.15 for r in sv], dtype=torch.float32, device=device)
                reward = reward * gate
            centered = reward - reward.mean()
        loss = -((out.logps * centered[:, None] * out.mask).sum() / out.mask.sum().clamp_min(1.0))
        opt_g.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt_g)
        torch.nn.utils.clip_grad_norm_(gen.parameters(), 5.0)
        scaler.step(opt_g)
        scaler.update()
        losses.append(float(loss.detach().item()))
        rewards.append(float(reward.mean().detach().item()))
        static_rewards.append(float(s_reward.mean().detach().item()))
        d_rewards.append(float(d_reward.mean().detach().item()))
        for text, r, c in zip(out.decoded, sv, batch_contracts):
            recent.append(text)
            if r.contract_valid:
                coverage_counts[str(c.get("structure_cell_id", ""))] += 1
        recent = recent[-512:]
    return {
        "pg_loss": float(np.mean(losses)) if losses else 0.0,
        "reward_mean": float(np.mean(rewards)) if rewards else 0.0,
        "static_reward_mean": float(np.mean(static_rewards)) if static_rewards else 0.0,
        "disc_reward_mean": float(np.mean(d_rewards)) if d_rewards else 0.0,
    }


def audit_generation(gen, codec, df: pd.DataFrame, contracts: list[dict[str, Any]], out_dir: Path, args, device: str, *, repair: bool = False, strict: bool = False) -> dict[str, Any]:
    gen.eval()
    if args.direction == 7 and "boolean_pair_id" in df.columns:
        # Pair audit: request TRUE/FALSE siblings from the same oracle pair where possible.
        targets_df = (
            df.sort_values(["boolean_pair_id", "expected_truth", "sample_id"])
              .groupby("boolean_pair_id", sort=True)
              .head(2)
              .head(args.generate_limit)
              .reset_index(drop=True)
        )
    else:
        targets_df = sample_rows_by_cell(df, per_cell=max(1, args.generate_per_cell), max_rows=args.generate_limit, seed=args.seed)
    target_contracts = [row_to_contract(r) for _, r in targets_df.iterrows()]
    rows: list[dict[str, Any]] = []
    recent: list[str] = []
    coverage_counts: Counter[str] = Counter()
    with torch.no_grad():
        for start in tqdm(range(0, len(target_contracts), args.batch_size), desc="Generate", leave=False):
            batch_contracts = target_contracts[start : start + args.batch_size]
            prefixes = [str(c.get("seqgan_prefix", "")) + " " for c in batch_contracts]
            out = sample_after_prefix(
                gen,
                codec,
                prefixes,
                max_new_tokens=args.max_new_tokens,
                temperature=args.temperature,
                device=device,
                top_k=args.top_k,
            )
            for text, c in zip(out.decoded, batch_contracts):
                meta, payload = parse_condition_prefix(text)
                repair_actions = []
                payload_for_score = payload
                repaired_payload = ""
                if repair:
                    repaired_payload, repair_actions = repair_small(payload, c)
                    payload_for_score = repaired_payload
                    # Score with original condition prefix preserved.
                    prefix = str(c.get("seqgan_prefix", ""))
                    text_for_score = f"{prefix} {payload_for_score}".strip()
                else:
                    text_for_score = text
                repair_count = len(repair_actions)
                audit = parserlike_static_audit(
                    payload_for_score,
                    repair_count=repair_count,
                    unknown_alpha_max=args.unknown_alpha_max,
                    max_repair_actions=args.repair_budget,
                    version=args.strict_audit_version,
                )
                raw_audit = parserlike_static_audit(
                    payload,
                    repair_count=0,
                    unknown_alpha_max=args.unknown_alpha_max,
                    max_repair_actions=0,
                    version=args.strict_audit_version,
                )
                r = score_payload_v3(
                    text_for_score,
                    c,
                    recent_payloads=recent,
                    coverage_count=coverage_counts[str(c.get("structure_cell_id", ""))],
                    max_len=codec.max_len,
                )
                base_accepted = bool(r.reward_total >= args.accepted_threshold and r.hard_gate_pass and r.contract_valid)
                accepted = base_accepted
                if strict:
                    accepted = accepted and r.required_tokens_valid and r.root_adherence_valid and r.cell_adherence_valid
                policy = str(args.acceptance_policy)
                if policy == "strict":
                    accepted = accepted and audit.clean
                elif policy == "strict_score":
                    accepted = accepted and audit.score >= args.min_audit_score
                elif policy == "raw_strict":
                    accepted = accepted and raw_audit.clean and repair_count == 0
                elif policy == "reward_only":
                    accepted = bool(r.reward_total >= args.accepted_threshold)
                else:
                    # "reward_contract" is the backwards-compatible base policy.
                    accepted = accepted
                if accepted:
                    coverage_counts[str(c.get("structure_cell_id", ""))] += 1
                recent.append(text_for_score)
                row = {
                    "sample_id": f"GEN_{len(rows):08d}",
                    "direction": DIRECTIONS[args.direction],
                    "target_module_id": c.get("module_id"),
                    "target_y_level": c.get("y_level"),
                    "target_root_grammar": c.get("root_grammar_id"),
                    "target_structure_cell": c.get("structure_cell_id"),
                    "target_truth": c.get("expected_truth"),
                    "target_required_tokens": c.get("required_tokens"),
                    "generated_text": text,
                    "generated_payload": payload,
                    "repaired_payload": repaired_payload,
                    "repair_actions": "|".join(repair_actions),
                    "reward_total": r.reward_total,
                    "r_ruleset": r.r_ruleset,
                    "r_cell": r.r_cell,
                    "r_required": r.r_required,
                    "r_structure": r.r_structure,
                    "r_slot": r.r_slot,
                    "r_truth_condition": r.r_truth_condition,
                    "r_diversity": r.r_diversity,
                    "r_coverage": r.r_coverage,
                    "r_length": r.r_length,
                    "p_duplicate": r.p_duplicate,
                    "p_near_duplicate": r.p_near_duplicate,
                    "p_off_condition": r.p_off_condition,
                    "hard_gate_pass": r.hard_gate_pass,
                    "contract_valid": r.contract_valid,
                    "root_adherence_valid": r.root_adherence_valid,
                    "cell_adherence_valid": r.cell_adherence_valid,
                    "required_tokens_valid": r.required_tokens_valid,
                    "static_error_class": r.static_error_class,
                    "parserlike_clean": audit.clean,
                    "parserlike_score": audit.score,
                    "parserlike_reasons": ";".join(audit.reasons),
                    "parserlike_unknown_alpha_rate": audit.unknown_alpha_rate,
                    "raw_parserlike_clean": raw_audit.clean,
                    "raw_parserlike_score": raw_audit.score,
                    "raw_parserlike_reasons": ";".join(raw_audit.reasons),
                    "raw_parserlike_unknown_alpha_rate": raw_audit.unknown_alpha_rate,
                    "repair_action_count": repair_count,
                    "base_accepted": base_accepted,
                    "acceptance_policy": args.acceptance_policy,
                    "strict_audit_version": args.strict_audit_version,
                    "accepted_for_next_stage": accepted,
                    "runtime_claim_allowed": False,
                    "postgres_parse_status": "not_run",
                    "postgres_runtime_status": "not_run",
                    "truth_oracle_status": "not_run",
                    "exploit_confirmed": False,
                }
                rows.append(row)
            recent = recent[-512:]
    out_dir.mkdir(parents=True, exist_ok=True)
    gen_df = pd.DataFrame(rows)
    gen_df.to_csv(out_dir / "generated_candidates.csv", index=False)
    if not gen_df.empty:
        gen_df[gen_df["accepted_for_next_stage"].astype(bool)].to_csv(out_dir / "accepted_for_next_stage.csv", index=False)
        gen_df[~gen_df["accepted_for_next_stage"].astype(bool)].to_csv(out_dir / "rejected_for_next_stage.csv", index=False)
    summary = summarize_generated(gen_df)
    (out_dir / "generation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def summarize_generated(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"rows": 0}
    accepted_df = df[df["accepted_for_next_stage"].astype(bool)]
    pair_coverage = int(accepted_df["target_structure_cell"].nunique())
    if "target_truth" in accepted_df.columns and not accepted_df.empty:
        truth_balance = accepted_df["target_truth"].astype(str).value_counts().to_dict()
    else:
        truth_balance = {}
    return {
        "rows": int(len(df)),
        "accepted": int(df["accepted_for_next_stage"].sum()),
        "accepted_rate": float(df["accepted_for_next_stage"].mean()),
        "unique_payloads": int(df["generated_payload"].nunique()),
        "duplicate_rate": float(1.0 - df["generated_payload"].nunique() / max(len(df), 1)),
        "mean_reward": float(df["reward_total"].mean()),
        "mean_structure": float(df["r_structure"].mean()),
        "contract_valid_rate": float(df["contract_valid"].mean()),
        "required_tokens_rate": float(df["required_tokens_valid"].mean()),
        "root_adherence_rate": float(df["root_adherence_valid"].mean()),
        "cell_adherence_rate": float(df["cell_adherence_valid"].mean()),
        "hard_gate_rate": float(df["hard_gate_pass"].mean()),
        "parserlike_clean_rate": float(df["parserlike_clean"].mean()) if "parserlike_clean" in df.columns else 0.0,
        "raw_parserlike_clean_rate": float(df["raw_parserlike_clean"].mean()) if "raw_parserlike_clean" in df.columns else 0.0,
        "mean_parserlike_score": float(df["parserlike_score"].mean()) if "parserlike_score" in df.columns else 0.0,
        "mean_raw_parserlike_score": float(df["raw_parserlike_score"].mean()) if "raw_parserlike_score" in df.columns else 0.0,
        "repair_action_count_mean": float(df["repair_action_count"].mean()) if "repair_action_count" in df.columns else 0.0,
        "base_accepted_rate": float(df["base_accepted"].mean()) if "base_accepted" in df.columns else float(df["accepted_for_next_stage"].mean()),
        "accepted_root_coverage": int(accepted_df["target_root_grammar"].nunique()),
        "accepted_cell_coverage": int(accepted_df["target_structure_cell"].nunique()),
        "accepted_truth_balance": truth_balance,
    }


def train_one(args, df: pd.DataFrame, out_dir: Path, device: str) -> dict[str, Any]:
    direction_name = DIRECTIONS[args.direction]
    if args.direction == 7 and "boolean_pair_id" in df.columns:
        # Keep oracle siblings adjacent for pair-conditioned exposure.
        df = df.sort_values(["boolean_pair_id", "expected_truth", "sample_id"]).reset_index(drop=True)
    tokenizer = args.tokenizer
    if args.direction == 5:
        tokenizer = "hybrid"
    text_mode = "conditioned" if args.direction != 1 or args.conditioned else "raw"
    texts = [training_text(r, text_mode) for _, r in df.iterrows()]
    codec = make_codec(texts, tokenizer, args.max_len)
    label_maps = LabelMaps.from_frame(df)
    ds = V3TextDataset(df, codec, text_mode=text_mode, label_maps=label_maps)
    sampler = None
    shuffle = True
    if args.direction == 2:
        sampler = make_weighted_sampler(df, "contract_weighted")
        shuffle = False
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=shuffle, sampler=sampler, num_workers=args.num_workers, pin_memory=torch.cuda.is_available())
    contracts = [row_to_contract(r) for _, r in df.iterrows()]

    gen = LSTMGenerator(codec.vocab_size, emb_dim=args.emb_dim, hidden_dim=args.hidden_dim, pad_id=codec.pad_id, dropout=args.dropout).to(device)
    disc = MultiHeadDiscriminator(
        codec.vocab_size,
        emb_dim=args.emb_dim,
        pad_id=codec.pad_id,
        n_roots=len(label_maps.root_to_id),
        n_cells=len(label_maps.cell_to_id),
        n_modules=len(label_maps.module_to_id),
        n_reps=len(label_maps.rep_to_id),
        dropout=args.dropout,
    ).to(device)
    opt_g = torch.optim.AdamW(gen.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    opt_d = torch.optim.AdamW(disc.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    out_dir.mkdir(parents=True, exist_ok=True)
    codec.save(out_dir / "codec.json")
    (out_dir / "label_maps.json").write_text(json.dumps({
        "root_to_id": label_maps.root_to_id,
        "cell_to_id": label_maps.cell_to_id,
        "module_to_id": label_maps.module_to_id,
        "rep_to_id": label_maps.rep_to_id,
    }, indent=2), encoding="utf-8")

    history = []
    best_nll = math.inf
    best_state = None
    start_time = time.time()
    print(f"[train] direction={args.direction}:{direction_name} rows={len(df)} vocab={codec.vocab_size} tokenizer={tokenizer} mode={text_mode} device={device}", flush=True)

    # Direction 8: curriculum by Y/difficulty. Run MLE in sorted curriculum order.
    if args.direction == 8:
        train_order = sorted(df["module_id"].unique(), key=lambda m: MODULES.index(m) if m in MODULES else 99)
        for mod in train_order:
            sub = df[df["module_id"] == mod].sort_values(["difficulty_level", "root_grammar_id", "structure_cell_id"])
            sub_ds = V3TextDataset(sub, codec, text_mode=text_mode, label_maps=label_maps)
            sub_loader = DataLoader(sub_ds, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers, pin_memory=torch.cuda.is_available())
            for ep in range(1, args.mle_epochs + 1):
                nll = train_mle_epoch(gen, sub_loader, opt_g, codec.pad_id, device, amp=not args.no_amp)
                history.append({"phase": "curriculum_mle", "module": mod, "epoch": ep, "nll": nll})
                print(f"[{mod}] MLE {ep}/{args.mle_epochs} nll={nll:.4f}", flush=True)
                if nll < best_nll:
                    best_nll = nll
                    best_state = clean_state_dict(gen)
    else:
        for ep in range(1, args.mle_epochs + 1):
            nll = train_mle_epoch(gen, loader, opt_g, codec.pad_id, device, amp=not args.no_amp)
            history.append({"phase": "mle", "epoch": ep, "nll": nll})
            print(f"[MLE] {ep}/{args.mle_epochs} nll={nll:.4f}", flush=True)
            if nll < best_nll:
                best_nll = nll
                best_state = clean_state_dict(gen)
                torch.save(best_state, out_dir / "generator_mle_best.pt")

    if best_state is not None and args.direction in {9}:
        gen.load_state_dict(best_state)

    training_hashes = {sha256_text(str(r.get("validation_payload", r.get("raw_payload", "")))) for _, r in df.iterrows()}

    if args.direction in {3, 4, 9} and args.d_epochs > 0:
        for ep in range(1, args.d_epochs + 1):
            d_loss = discriminator_step(disc, gen, loader, contracts, codec, opt_d, device, args, multihead=args.direction == 4)
            history.append({"phase": "discriminator", "epoch": ep, "d_loss": d_loss})
            print(f"[D] {ep}/{args.d_epochs} loss={d_loss:.4f}", flush=True)

    if args.direction in {3, 4, 9} and args.adv_epochs > 0:
        prev_audit_rate = None
        for ep in range(1, args.adv_epochs + 1):
            pg = pg_epoch(gen, disc, codec, opt_g, contracts, training_hashes, device, args, guarded=args.direction == 9)
            d_loss = discriminator_step(disc, gen, loader, contracts, codec, opt_d, device, args, multihead=args.direction == 4) if args.d_epochs > 0 else 0.0
            row = {"phase": "adv", "epoch": ep, "d_loss": d_loss, **pg}
            history.append(row)
            print(f"[ADV] {ep}/{args.adv_epochs} pg={pg['pg_loss']:.4f} reward={pg['reward_mean']:.4f} static={pg['static_reward_mean']:.4f}", flush=True)
            if args.direction == 9 and ep % max(1, args.guard_audit_every) == 0:
                tmp = audit_generation(gen, codec, df, contracts, out_dir / f"guard_audit_ep{ep}", args, device, repair=False, strict=True)
                rate = tmp.get("contract_valid_rate", 0.0)
                history.append({"phase": "guard_audit", "epoch": ep, **tmp})
                if prev_audit_rate is not None and rate + args.guard_tolerance < prev_audit_rate:
                    print(f"[guard] contract_valid_rate worsened {prev_audit_rate:.3f}->{rate:.3f}; restoring best MLE and stopping adversarial", flush=True)
                    if best_state is not None:
                        gen.load_state_dict(best_state)
                    break
                prev_audit_rate = rate

    torch.save({
        "generator_state_dict": clean_state_dict(gen),
        "discriminator_state_dict": clean_state_dict(disc),
        "config": vars(args),
        "direction_name": direction_name,
        "best_mle_nll": best_nll,
    }, out_dir / "checkpoint.pt")

    repair = args.direction == 10
    strict = args.direction in {6, 9, 10}
    gen_summary = audit_generation(gen, codec, df, contracts, out_dir / "generated_candidates", args, device, repair=repair, strict=strict)
    summary = {
        "direction": args.direction,
        "direction_name": direction_name,
        "rows": len(df),
        "modules": sorted(df["module_id"].unique().tolist()),
        "vocab_size": codec.vocab_size,
        "tokenizer": tokenizer,
        "text_mode": text_mode,
        "best_mle_nll": best_nll,
        "seconds_total": round(time.time() - start_time, 3),
        "generated": gen_summary,
        "runtime_claim_allowed": False,
        "exploit_confirmed": False,
    }
    (out_dir / "history.json").write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    return summary


def run(args) -> dict[str, Any]:
    set_seed(args.seed)
    device = device_auto(args.device)
    root = materialize_dataset(args.data, Path(args.out) / "_dataset_work")
    modules = args.modules or MODULES
    if args.direction == 8 and args.modules is None:
        modules = MODULES
    df = read_attack_samples(root, modules=modules, limit=args.limit)
    if args.sample_per_cell > 0:
        df = sample_rows_by_cell(df, per_cell=args.sample_per_cell, max_rows=args.limit, seed=args.seed)
    out = Path(args.out) / f"direction_{args.direction:02d}_{DIRECTIONS[args.direction]}"
    summary = train_one(args, df, out, device)
    (Path(args.out) / "last_run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SQLGAN V3: 10 offline structure-learning experiment directions")
    p.add_argument("--data", required=True, help="Path to SQLGAN_PostgreSQL_Boolean_Attack_Structure_Corpus_V3.zip or extracted Dataset root")
    p.add_argument("--out", required=True, help="Output directory")
    p.add_argument("--direction", type=int, choices=sorted(DIRECTIONS), required=True)
    p.add_argument("--modules", nargs="+", default=None, help="Subset of modules; default all for direction 8, otherwise all unless specified")
    p.add_argument("--limit", type=int, default=None, help="Max rows per module before optional sampling")
    p.add_argument("--sample-per-cell", type=int, default=0, help="Optional balanced subset per structure cell")
    p.add_argument("--conditioned", action="store_true", help="For direction 1, use condition prefix too. Other directions default conditioned.")
    p.add_argument("--tokenizer", choices=["char", "hybrid"], default="char")
    p.add_argument("--max-len", type=int, default=256)
    p.add_argument("--max-new-tokens", type=int, default=128)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--mle-epochs", type=int, default=8)
    p.add_argument("--d-epochs", type=int, default=1)
    p.add_argument("--adv-epochs", type=int, default=1)
    p.add_argument("--adv-steps", type=int, default=40)
    p.add_argument("--emb-dim", type=int, default=128)
    p.add_argument("--hidden-dim", type=int, default=256)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--temperature", type=float, default=0.85)
    p.add_argument("--top-k", type=int, default=0)
    p.add_argument("--static-weight", type=float, default=0.65)
    p.add_argument("--accepted-threshold", type=float, default=0.72)
    p.add_argument("--acceptance-policy", choices=["reward_contract", "strict", "strict_score", "raw_strict", "reward_only"], default="reward_contract")
    p.add_argument("--strict-audit-version", choices=["v1", "v2", "v3", "v4", "v5", "strict"], default="v5")
    p.add_argument("--repair-budget", type=int, default=1)
    p.add_argument("--unknown-alpha-max", type=float, default=0.12)
    p.add_argument("--min-audit-score", type=float, default=0.90)
    p.add_argument("--generate-per-cell", type=int, default=1)
    p.add_argument("--generate-limit", type=int, default=300)
    p.add_argument("--guard-audit-every", type=int, default=1)
    p.add_argument("--guard-tolerance", type=float, default=0.05)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--device", default="auto")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--no-amp", action="store_true")
    return p


def main(argv=None) -> None:
    args = build_argparser().parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()

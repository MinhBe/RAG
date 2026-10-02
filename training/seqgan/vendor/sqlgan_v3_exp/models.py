# ruff: noqa
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence


class LSTMGenerator(nn.Module):
    def __init__(self, vocab_size: int, emb_dim: int = 128, hidden_dim: int = 256, num_layers: int = 1, pad_id: int = 0, dropout: float = 0.1):
        super().__init__()
        self.vocab_size = int(vocab_size)
        self.pad_id = int(pad_id)
        self.emb = nn.Embedding(vocab_size, emb_dim, padding_idx=pad_id)
        self.rnn = nn.LSTM(emb_dim, hidden_dim, num_layers=num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0.0)
        self.drop = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e = self.emb(x)
        h, _ = self.rnn(e)
        return self.fc(self.drop(h))

    def step(self, last_token: torch.Tensor, hidden: Any | None) -> tuple[torch.Tensor, Any]:
        e = self.emb(last_token.unsqueeze(1))
        h, hidden = self.rnn(e, hidden)
        return self.fc(h[:, -1]), hidden


class MultiHeadDiscriminator(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        emb_dim: int = 128,
        pad_id: int = 0,
        n_roots: int = 1,
        n_cells: int = 1,
        n_modules: int = 1,
        n_reps: int = 1,
        channels: int = 128,
        kernels: tuple[int, ...] = (3, 5, 7),
        dropout: float = 0.2,
    ):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, emb_dim, padding_idx=pad_id)
        self.convs = nn.ModuleList([nn.Conv1d(emb_dim, channels, k, padding=k // 2) for k in kernels])
        feat_dim = channels * len(kernels)
        self.drop = nn.Dropout(dropout)
        self.real_fake = nn.Linear(feat_dim, 1)
        self.root_head = nn.Linear(feat_dim, max(1, n_roots))
        self.cell_head = nn.Linear(feat_dim, max(1, n_cells))
        self.truth_head = nn.Linear(feat_dim, 2)
        self.module_head = nn.Linear(feat_dim, max(1, n_modules))
        self.rep_head = nn.Linear(feat_dim, max(1, n_reps))
        self.syntax_head = nn.Linear(feat_dim, 2)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        e = self.emb(x).transpose(1, 2)
        feats = []
        for conv in self.convs:
            z = torch.relu(conv(e))
            z = torch.max(z, dim=-1).values
            feats.append(z)
        return self.drop(torch.cat(feats, dim=-1))

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        f = self.encode(x)
        return {
            "real_fake": self.real_fake(f).squeeze(-1),
            "root": self.root_head(f),
            "cell": self.cell_head(f),
            "truth": self.truth_head(f),
            "module": self.module_head(f),
            "rep": self.rep_head(f),
            "syntax": self.syntax_head(f),
        }


@dataclass
class SampleOutput:
    full: torch.Tensor
    logps: torch.Tensor
    mask: torch.Tensor
    decoded: list[str]


def sample_after_prefix(
    gen: LSTMGenerator,
    codec: Any,
    prefixes: list[str],
    *,
    max_new_tokens: int,
    temperature: float,
    device: str,
    top_k: int = 0,
    forbidden_token_ids: list[int] | None = None,
) -> SampleOutput:
    """Sample continuations after fixed condition prefixes.

    The prefix is forced and excluded from the policy-gradient mask.
    """
    gen.train()
    batch = len(prefixes)
    prefix_ids = [codec.encode_prefix_no_bos_eos(p, reserve_new_tokens=max_new_tokens + 2) for p in prefixes]
    lengths = [len(ids) + 1 for ids in prefix_ids]
    max_pref = max(lengths)
    inp = torch.full((batch, max_pref), codec.pad_id, dtype=torch.long, device=device)
    for i, ids in enumerate(prefix_ids):
        row = [codec.bos_id] + ids
        inp[i, : len(row)] = torch.tensor(row, dtype=torch.long, device=device)
    emb = gen.emb(inp)
    packed = pack_padded_sequence(emb, lengths, batch_first=True, enforce_sorted=False)
    _, hidden = gen.rnn(packed)
    last = torch.tensor([ids[-1] if ids else codec.bos_id for ids in prefix_ids], dtype=torch.long, device=device)

    banned = torch.zeros(gen.vocab_size, dtype=torch.bool, device=device)
    banned[codec.pad_id] = True
    banned[codec.bos_id] = True
    if forbidden_token_ids:
        for i in forbidden_token_ids:
            if 0 <= int(i) < gen.vocab_size:
                banned[int(i)] = True

    tokens = []
    logps = []
    masks = []
    finished = torch.zeros(batch, dtype=torch.bool, device=device)
    steps = max(1, int(max_new_tokens))
    for _ in range(steps):
        logits, hidden = gen.step(last, hidden)
        logits = logits / max(float(temperature), 1e-6)
        logits = logits.masked_fill(banned.unsqueeze(0), -1e9)
        if top_k and top_k > 0 and top_k < logits.size(-1):
            vals, idx = torch.topk(logits, int(top_k), dim=-1)
            keep = torch.full_like(logits, -1e9)
            keep.scatter_(1, idx, vals)
            logits = keep
        probs = torch.softmax(logits.float(), dim=-1)
        dist = torch.distributions.Categorical(probs=probs)
        sampled = dist.sample()
        lp = dist.log_prob(sampled)
        active = ~finished
        tok = torch.where(active, sampled, torch.full_like(sampled, codec.eos_id))
        tokens.append(tok)
        logps.append(torch.where(active, lp, torch.zeros_like(lp)))
        masks.append(active.float())
        finished = finished | tok.eq(codec.eos_id)
        last = tok
        if bool(finished.all().item()):
            break

    if not tokens:
        tokens.append(torch.full((batch,), codec.eos_id, dtype=torch.long, device=device))
        logps.append(torch.zeros(batch, dtype=torch.float32, device=device))
        masks.append(torch.zeros(batch, dtype=torch.float32, device=device))

    sampled = torch.stack(tokens, dim=1)
    full_rows = []
    for i in range(batch):
        seq = prefix_ids[i] + sampled[i].detach().cpu().tolist()
        if not seq or seq[-1] != codec.eos_id:
            seq.append(codec.eos_id)
        seq = seq[: codec.max_len]
        if seq[-1] != codec.eos_id:
            seq[-1] = codec.eos_id
        seq += [codec.pad_id] * (codec.max_len - len(seq))
        full_rows.append(seq)
    full = torch.tensor(full_rows, dtype=torch.long, device=device)
    decoded = [codec.decode(row.tolist()) for row in full.detach().cpu()]
    return SampleOutput(full=full, logps=torch.stack(logps, dim=1), mask=torch.stack(masks, dim=1), decoded=decoded)


def clean_state_dict(model: nn.Module) -> dict[str, torch.Tensor]:
    sd = model.state_dict()
    if any(k.startswith("_orig_mod.") for k in sd):
        return {k.replace("_orig_mod.", "", 1): v for k, v in sd.items()}
    return sd

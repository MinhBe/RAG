# ruff: noqa
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

SPECIALS = ["<PAD>", "<BOS>", "<EOS>", "<UNK>"]


class CharCodec:
    def __init__(self, stoi: dict[str, int], max_len: int = 256):
        self.stoi = dict(stoi)
        self.itos = {i: s for s, i in self.stoi.items()}
        self.max_len = int(max_len)
        self.pad_id = self.stoi["<PAD>"]
        self.bos_id = self.stoi["<BOS>"]
        self.eos_id = self.stoi["<EOS>"]
        self.unk_id = self.stoi["<UNK>"]

    @classmethod
    def fit(cls, texts: Iterable[str], max_len: int = 256) -> "CharCodec":
        chars = sorted(set("".join(str(t) for t in texts)))
        stoi = {s: i for i, s in enumerate(SPECIALS)}
        for ch in chars:
            if ch not in stoi:
                stoi[ch] = len(stoi)
        return cls(stoi, max_len=max_len)

    @property
    def vocab_size(self) -> int:
        return len(self.stoi)

    def encode(self, text: str) -> list[int]:
        ids = [self.bos_id]
        ids += [self.stoi.get(ch, self.unk_id) for ch in str(text)[: max(0, self.max_len - 2)]]
        ids.append(self.eos_id)
        ids = ids[: self.max_len]
        if ids[-1] != self.eos_id:
            ids[-1] = self.eos_id
        ids += [self.pad_id] * (self.max_len - len(ids))
        return ids

    def encode_prefix_no_bos_eos(self, text: str, reserve_new_tokens: int = 8) -> list[int]:
        max_prefix = max(0, self.max_len - int(reserve_new_tokens) - 1)
        return [self.stoi.get(ch, self.unk_id) for ch in str(text)[:max_prefix]]

    def decode(self, ids: Iterable[int], skip_special: bool = True) -> str:
        out = []
        for i in ids:
            tok = self.itos.get(int(i), "<UNK>")
            if tok == "<EOS>":
                break
            if skip_special and tok in SPECIALS:
                continue
            out.append(tok)
        return "".join(out)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"type": "char", "stoi": self.stoi, "max_len": self.max_len}, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CharCodec":
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(obj["stoi"], obj["max_len"])


TOKEN_RE = re.compile(
    r"(<[^>]+>|%[0-9A-Fa-f]{2}|::|<>|!=|>=|<=|\?\||\?&|&&|@>|<@|!~\*|~\*|!~|~|"
    r"\bIS\s+DISTINCT\s+FROM\b|\bIS\s+NOT\s+DISTINCT\s+FROM\b|"
    r"\bSIMILAR\s+TO\b|\bNOT\s+IN\b|\bNOT\s+LIKE\b|\bNOT\s+ILIKE\b|"
    r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|'(?:''|[^'])*'|\s+|.)",
    re.I | re.S,
)


class HybridSQLCodec(CharCodec):
    """Token-level codec that keeps SQL keywords/operators/encoding units atomic.

    This reduces keyword corruption such as BETWEEN -> BET ENT.
    """

    @staticmethod
    def tokenize(text: str) -> list[str]:
        toks = []
        for m in TOKEN_RE.finditer(str(text)):
            t = m.group(0)
            if t.isspace():
                toks.append(" ")
            else:
                # Canonicalize pure SQL words, but keep prefix tags intact.
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t):
                    toks.append(t.upper())
                else:
                    toks.append(t)
        return toks

    @classmethod
    def fit(cls, texts: Iterable[str], max_len: int = 256) -> "HybridSQLCodec":
        vocab = set()
        for t in texts:
            vocab.update(cls.tokenize(str(t)))
        stoi = {s: i for i, s in enumerate(SPECIALS)}
        for tok in sorted(vocab):
            if tok not in stoi:
                stoi[tok] = len(stoi)
        return cls(stoi, max_len=max_len)

    def encode(self, text: str) -> list[int]:
        toks = self.tokenize(text)
        ids = [self.bos_id] + [self.stoi.get(t, self.unk_id) for t in toks[: max(0, self.max_len - 2)]] + [self.eos_id]
        ids = ids[: self.max_len]
        if ids[-1] != self.eos_id:
            ids[-1] = self.eos_id
        ids += [self.pad_id] * (self.max_len - len(ids))
        return ids

    def encode_prefix_no_bos_eos(self, text: str, reserve_new_tokens: int = 8) -> list[int]:
        toks = self.tokenize(text)
        max_prefix = max(0, self.max_len - int(reserve_new_tokens) - 1)
        return [self.stoi.get(t, self.unk_id) for t in toks[:max_prefix]]

    def decode(self, ids: Iterable[int], skip_special: bool = True) -> str:
        out = []
        for i in ids:
            tok = self.itos.get(int(i), "<UNK>")
            if tok == "<EOS>":
                break
            if skip_special and tok in SPECIALS:
                continue
            out.append(tok)
        return "".join(out)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"type": "hybrid", "stoi": self.stoi, "max_len": self.max_len}, ensure_ascii=False, indent=2), encoding="utf-8")


def load_codec(path: str | Path) -> CharCodec:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    typ = obj.get("type", "char")
    cls = HybridSQLCodec if typ == "hybrid" else CharCodec
    return cls(obj["stoi"], obj["max_len"])

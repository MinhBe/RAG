# ruff: noqa
from __future__ import annotations

import json
import os
import random
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import torch
from torch.utils.data import Dataset, WeightedRandomSampler

MODULES = [
    "Y1_basic_boolean",
    "Y2_boolean_variation",
    "Y3_encoded_boolean",
    "Y4_obfuscated_boolean",
]

Y_SHORT = {
    "Y1_basic_boolean": "Y1",
    "Y2_boolean_variation": "Y2",
    "Y3_encoded_boolean": "Y3",
    "Y4_obfuscated_boolean": "Y4",
}


def materialize_dataset(data_path: str | os.PathLike[str], work_dir: str | os.PathLike[str]) -> Path:
    """Return extracted Dataset root for a V3 zip or an already extracted dataset.

    Expected final path contains `B_attack_samples` and `D_training_views`.
    """
    data_path = Path(data_path)
    work_dir = Path(work_dir)
    if data_path.is_dir():
        if (data_path / "Dataset").is_dir():
            return data_path / "Dataset"
        return data_path
    if not data_path.exists():
        raise FileNotFoundError(data_path)
    work_dir.mkdir(parents=True, exist_ok=True)
    extract_root = work_dir / data_path.stem
    marker = extract_root / "Dataset" / "dataset_manifest.json"
    if not marker.exists():
        if extract_root.exists():
            # Avoid stale partial extraction.
            import shutil
            shutil.rmtree(extract_root)
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(data_path) as zf:
            zf.extractall(extract_root)
    dataset_root = extract_root / "Dataset"
    if not (dataset_root / "B_attack_samples").exists():
        raise RuntimeError(f"Invalid V3 dataset layout under {dataset_root}")
    return dataset_root


def read_manifest(dataset_root: Path) -> dict[str, Any]:
    p = dataset_root / "dataset_manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def read_attack_samples(dataset_root: Path, modules: Iterable[str] | None = None, limit: int | None = None) -> pd.DataFrame:
    modules = list(modules or MODULES)
    frames: list[pd.DataFrame] = []
    for mod in modules:
        p = dataset_root / "B_attack_samples" / mod / "attack_samples.csv"
        if not p.exists():
            raise FileNotFoundError(p)
        df = pd.read_csv(p)
        if limit:
            # Keep deterministic, balanced subset by structure_cell_id where possible.
            df = df.sort_values(["root_grammar_id", "structure_cell_id", "truth_variant", "sample_id"]).head(int(limit))
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    return normalize_frame(out)


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    bool_cols = [
        "expected_truth", "truth_variant", "contract_valid", "syntax_valid", "delimiter_valid",
        "quote_valid", "parenthesis_valid", "boolean_signal_valid", "root_adherence_valid",
        "cell_adherence_valid", "required_tokens_valid", "forbidden_tokens_valid",
        "runtime_claim_allowed", "truth_oracle_defined",
    ]
    for c in bool_cols:
        if c in df.columns:
            df[c] = df[c].map(lambda x: str(x).strip().lower() in {"true", "1", "yes"})
    for c in ["difficulty_level", "token_count", "char_length", "depth", "parenthesis_depth"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    for c in ["seqgan_conditioned_text", "seqgan_prefix", "raw_payload", "validation_payload", "payload_normalized", "payload_decoded"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)
    return df


def preferred_payload(row: pd.Series | dict[str, Any]) -> str:
    """Choose the representation to validate/score.

    For V3 the validation_payload column is explicitly intended for static/runtime probes.
    """
    for c in ["validation_payload", "payload_normalized", "payload_decoded", "canonical_payload", "raw_payload"]:
        v = row.get(c, "") if isinstance(row, dict) else row.get(c, "")
        if v is not None and str(v) and str(v).lower() != "nan":
            return str(v)
    return ""


def training_text(row: pd.Series | dict[str, Any], mode: str = "conditioned") -> str:
    if mode == "raw":
        return str(row.get("raw_payload", ""))
    if mode == "validation_payload":
        return str(row.get("validation_payload", row.get("raw_payload", "")))
    txt = row.get("seqgan_conditioned_text", "")
    if txt is not None and str(txt) and str(txt).lower() != "nan":
        return str(txt)
    prefix = str(row.get("seqgan_prefix", ""))
    payload = str(row.get("raw_payload", row.get("validation_payload", "")))
    return f"{prefix} {payload}".strip()


def row_to_contract(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    def g(k: str, default: Any = "") -> Any:
        return row.get(k, default) if isinstance(row, dict) else row.get(k, default)

    slot_schema = g("slot_schema", "")
    slot_values = g("slot_values_json", "")
    try:
        slot_schema_parsed = json.loads(slot_schema) if isinstance(slot_schema, str) and slot_schema else slot_schema
    except Exception:
        slot_schema_parsed = slot_schema
    try:
        slot_values_parsed = json.loads(slot_values) if isinstance(slot_values, str) and slot_values else slot_values
    except Exception:
        slot_values_parsed = slot_values
    return {
        "sample_id": g("sample_id"),
        "module_id": g("module_id"),
        "y_level": g("y_level"),
        "root_grammar_id": g("root_grammar_id"),
        "structure_cell_id": g("structure_cell_id"),
        "target_root_grammar": g("target_root_grammar"),
        "target_structure_cell": g("target_structure_cell"),
        "semantic_family": g("semantic_family"),
        "target_family": g("target_family"),
        "cell_recipe": g("cell_recipe"),
        "required_tokens": g("required_tokens"),
        "forbidden_tokens": g("forbidden_tokens"),
        "required_operator_pattern": g("required_operator_pattern"),
        "operator_pattern": g("operator_pattern"),
        "slot_schema_id": g("slot_schema_id"),
        "slot_schema": slot_schema_parsed,
        "slot_values": slot_values_parsed,
        "expected_truth": bool(g("expected_truth", False)),
        "truth_variant": bool(g("truth_variant", False)),
        "boolean_pair_id": g("boolean_pair_id"),
        "contrastive_pair_id": g("contrastive_pair_id"),
        "quote_contract": g("quote_contract"),
        "parenthesis_contract": g("parenthesis_contract"),
        "comment_contract": g("comment_contract"),
        "difficulty_level": int(g("difficulty_level", 0) or 0),
        "syntax_complexity_score": float(g("syntax_complexity_score", 0.0) or 0.0),
        "representation_complexity_score": float(g("representation_complexity_score", 0.0) or 0.0),
        "raw_payload": g("raw_payload"),
        "validation_payload": g("validation_payload"),
        "seqgan_prefix": g("seqgan_prefix"),
        "generation_recipe": g("generation_recipe"),
        "lineage_path": g("lineage_path"),
    }


@dataclass
class LabelMaps:
    root_to_id: dict[str, int]
    cell_to_id: dict[str, int]
    truth_to_id: dict[str, int]
    module_to_id: dict[str, int]
    rep_to_id: dict[str, int]

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "LabelMaps":
        def mp(col: str) -> dict[str, int]:
            vals = sorted(str(x) for x in df[col].fillna("").unique()) if col in df.columns else [""]
            return {v: i for i, v in enumerate(vals)}
        return cls(
            root_to_id=mp("root_grammar_id"),
            cell_to_id=mp("structure_cell_id"),
            truth_to_id={"False": 0, "True": 1},
            module_to_id=mp("module_id"),
            rep_to_id=mp("representation_recipe"),
        )

    def encode_row(self, row: pd.Series) -> dict[str, int]:
        return {
            "root": self.root_to_id.get(str(row.get("root_grammar_id", "")), 0),
            "cell": self.cell_to_id.get(str(row.get("structure_cell_id", "")), 0),
            "truth": 1 if bool(row.get("expected_truth", False)) else 0,
            "module": self.module_to_id.get(str(row.get("module_id", "")), 0),
            "rep": self.rep_to_id.get(str(row.get("representation_recipe", "")), 0),
        }


class V3TextDataset(Dataset):
    def __init__(self, df: pd.DataFrame, codec: Any, text_mode: str = "conditioned", label_maps: LabelMaps | None = None):
        self.df = df.reset_index(drop=True)
        self.codec = codec
        self.texts = [training_text(r, text_mode) for _, r in self.df.iterrows()]
        self.contracts = [row_to_contract(r) for _, r in self.df.iterrows()]
        self.label_maps = label_maps or LabelMaps.from_frame(self.df)
        self.labels = [self.label_maps.encode_row(r) for _, r in self.df.iterrows()]

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        ids = torch.tensor(self.codec.encode(self.texts[idx]), dtype=torch.long)
        lab = self.labels[idx]
        return {
            "ids": ids,
            "root": torch.tensor(lab["root"], dtype=torch.long),
            "cell": torch.tensor(lab["cell"], dtype=torch.long),
            "truth": torch.tensor(lab["truth"], dtype=torch.long),
            "module": torch.tensor(lab["module"], dtype=torch.long),
            "rep": torch.tensor(lab["rep"], dtype=torch.long),
            "idx": torch.tensor(idx, dtype=torch.long),
        }


def make_weighted_sampler(df: pd.DataFrame, direction: str = "coverage") -> WeightedRandomSampler:
    """Weighted sampler for direction 2: emphasizes harder or structurally rarer rows."""
    weights = []
    fam_counts = df.get("semantic_family", pd.Series([""] * len(df))).value_counts().to_dict()
    cell_counts = df.get("structure_cell_id", pd.Series([""] * len(df))).value_counts().to_dict()
    for _, r in df.iterrows():
        w = 1.0
        if direction in {"coverage", "contract_weighted"}:
            w *= 1.0 / max(float(cell_counts.get(r.get("structure_cell_id", ""), 1)), 1.0)
            w *= 1.0 / max(float(fam_counts.get(r.get("semantic_family", ""), 1)), 1.0) ** 0.25
        if direction in {"difficulty", "contract_weighted"}:
            w *= 1.0 + 0.15 * float(r.get("difficulty_level", 0) or 0)
            w *= 1.0 + float(r.get("representation_complexity_score", 0.0) or 0.0)
        weights.append(float(w))
    return WeightedRandomSampler(torch.tensor(weights, dtype=torch.double), num_samples=len(weights), replacement=True)


def sample_rows_by_cell(df: pd.DataFrame, per_cell: int = 1, max_rows: int | None = None, seed: int = 7) -> pd.DataFrame:
    rng = random.Random(seed)
    selected = []
    for _, g in df.groupby("structure_cell_id", sort=True):
        rows = list(g.index)
        rng.shuffle(rows)
        selected.extend(rows[:per_cell])
        if max_rows and len(selected) >= max_rows:
            break
    return df.loc[selected[:max_rows]].reset_index(drop=True) if max_rows else df.loc[selected].reset_index(drop=True)

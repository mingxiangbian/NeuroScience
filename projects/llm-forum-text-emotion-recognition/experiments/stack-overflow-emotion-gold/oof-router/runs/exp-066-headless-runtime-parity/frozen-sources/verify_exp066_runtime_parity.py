#!/usr/bin/env python3
"""Independently reload both checkpoints and verify EXP-066 runtime parity."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import resource
import stat
import sys
from typing import Any
import zipfile

import numpy as np


EXPERIMENT_ID = "EXP-066"
RUN_ID = "exp-066-headless-runtime-parity"
CONFIG_SCHEMA = "exp-066-runtime-parity-config-v1"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
FEATURE_NAMES = (
    "m1_probability_love", "m1_probability_joy", "m1_probability_surprise",
    "m1_probability_anger", "m1_probability_sadness", "m1_probability_fear",
    "m1_mean_binary_entropy", "m1_max_binary_entropy", "m1_minimum_threshold_margin",
    "m1_predicted_cardinality", "m1_highest_probability", "m1_lowest_probability",
    "character_length", "m1_token_length",
)
PARAMETER_KEYS = {
    "scaler_mean", "scaler_var", "scaler_scale", "classes", "coef", "intercept"
}
PARITY_SCHEMA = {
    "ordinal": {"shape": [32], "dtype": "int16", "fortran_order": False},
    "m1_probabilities": {"shape": [32, 6], "dtype": "float32", "fortran_order": False},
    "m3_probabilities": {"shape": [32, 6], "dtype": "float32", "fortran_order": False},
    "features": {"shape": [32, 14], "dtype": "float64", "fortran_order": False},
    "standardized_features": {"shape": [32, 14], "dtype": "float64", "fortran_order": False},
    "route_score": {"shape": [32], "dtype": "float64", "fortran_order": False},
    "route_mask": {"shape": [32], "dtype": "uint8", "fortran_order": False},
    "m1_prediction": {"shape": [32, 6], "dtype": "uint8", "fortran_order": False},
    "m3_prediction": {"shape": [32, 6], "dtype": "uint8", "fortran_order": False},
    "final_prediction": {"shape": [32, 6], "dtype": "uint8", "fortran_order": False},
    "selected_path": {"shape": [32], "dtype": "uint8", "fortran_order": False},
    "neutral": {"shape": [32], "dtype": "uint8", "fortran_order": False},
    "character_length": {"shape": [32], "dtype": "int32", "fortran_order": False},
    "m1_token_length": {"shape": [32], "dtype": "int32", "fortran_order": False},
}
SENSITIVE_KEYS = {
    "text", "raw_text", "ordinal", "ordinals", "sample_id", "sample_ids",
    "component_id", "component_ids", "probabilities", "m1_probabilities",
    "m3_probabilities", "features", "standardized_features", "route_score",
    "route_mask", "prediction", "predictions", "m1_prediction", "m3_prediction",
    "final_prediction", "selected_path", "neutral", "active_labels", "token_ids",
}
CLAIM_BOUNDARY = (
    "A verified 32-row checkpoint-to-headless-runtime parity result for the frozen seed-42 "
    "local development stack only; no classification performance, independent-test, latency, "
    "production, forum-generalization, or emotion-mechanism claim."
)


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-066-headless-runtime-parity.json"
PUBLIC_DIR = PROJECT_ROOT / BASE / "runs" / RUN_ID
PRIVATE_DIR = PROJECT_ROOT / BASE / "private" / RUN_ID
CLI_PATH = PROJECT_ROOT / BASE / "phase_a_predict.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _resolve(value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses symlink: {value}")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def _regular(path: Path, mode: int) -> os.stat_result:
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise ValueError(f"File mode/type drift: {path}")
    return metadata


def record(path: Path, include_path: bool = True) -> dict[str, Any]:
    metadata = os.lstat(path)
    value: dict[str, Any] = {
        "bytes": metadata.st_size,
        "sha256": sha256_file(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }
    if include_path:
        value["path"] = str(path.relative_to(PROJECT_ROOT))
    return value


def require_record(value: dict[str, Any], mode: int) -> Path:
    if set(value) != {"path", "bytes", "sha256", "mode"}:
        raise ValueError("Artifact record schema drift")
    path = _resolve(value["path"])
    metadata = _regular(path, mode)
    if (
        metadata.st_size != value["bytes"]
        or value["mode"] != f"{mode:04o}"
        or sha256_file(path) != value["sha256"]
    ):
        raise ValueError(f"Artifact identity drift: {value['path']}")
    return path


def require_inventory(root_value: str, records: list[dict[str, Any]], root_mode: int) -> Path:
    root = _resolve(root_value)
    metadata = os.lstat(root)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != root_mode:
        raise ValueError(f"Asset root drift: {root_value}")
    if {path.name for path in root.iterdir() if path.is_file()} != {row["name"] for row in records}:
        raise ValueError(f"Asset inventory drift: {root_value}")
    for row in records:
        require_record(
            {
                "path": str((root / row["name"]).relative_to(PROJECT_ROOT)),
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "mode": row["mode"],
            },
            int(row["mode"], 8),
        )
    return root


def load_json(path: Path, mode: int | None = None) -> dict[str, Any]:
    if mode is not None:
        _regular(path, mode)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def npz_schema(path: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("NPZ duplicate members")
        for member in sorted(members):
            if not member.endswith(".npy") or "/" in member:
                raise ValueError("NPZ member layout drift")
            with archive.open(member) as source:
                version = np.lib.format.read_magic(source)
                if version == (1, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_1_0(source)
                elif version == (2, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_2_0(source)
                else:
                    shape, fortran, dtype = np.lib.format._read_array_header(source, version)
            output[Path(member).stem] = {
                "shape": list(shape), "dtype": str(dtype), "fortran_order": bool(fortran)
            }
    return output


def environment_identity() -> dict[str, Any]:
    packages = {
        name: importlib.metadata.version(distribution)
        for name, distribution in {
            "numpy": "numpy", "scikit_learn": "scikit-learn", "torch": "torch",
            "transformers": "transformers", "tokenizers": "tokenizers", "mlx": "mlx",
            "mlx_lm": "mlx-lm", "safetensors": "safetensors",
        }.items()
    }
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "packages": packages,
        "offline_environment": {
            "PYTHONNOUSERSITE": os.environ.get("PYTHONNOUSERSITE"),
            "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
            "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
            "TOKENIZERS_PARALLELISM": os.environ.get("TOKENIZERS_PARALLELISM"),
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "VECLIB_MAXIMUM_THREADS": os.environ.get("VECLIB_MAXIMUM_THREADS"),
        },
    }


def load_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    config_path = config_path.resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise ValueError("Verifier requires frozen EXP-066 config")
    config = load_json(config_path, 0o644)
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("labels") != list(LABEL_ORDER)
        or config.get("features") != list(FEATURE_NAMES)
        or config.get("claim_boundary") != CLAIM_BOUNDARY
        or config.get("environment") != environment_identity()
    ):
        raise ValueError("EXP-066 verifier config/environment drift")
    sources: dict[str, Path] = {"config": config_path}
    for section in ("prerequisite", "implementation"):
        for name, source_record in config[section].items():
            sources[name] = require_record(source_record, 0o644)
    assets = config["runtime_assets"]
    for name, mode in (
        ("bundle_manifest", 0o600), ("bundle_parameters", 0o600),
        ("projection", 0o600), ("replay", 0o600), ("projection_manifest", 0o600),
        ("m3_adapter", 0o600), ("m3_head", 0o600), ("m3_prompt", 0o644),
        ("m3_base_manifest", 0o644),
    ):
        sources[name] = require_record(assets[name], mode)
    sources["m1_checkpoint_root"] = require_inventory(
        assets["m1_checkpoint_root"], assets["m1_checkpoint_files"], 0o755
    )
    sources["m3_base_root"] = require_inventory(
        assets["m3_base_root"], assets["m3_base_files"], 0o755
    )
    return config, sources


def load_inputs(sources: dict[str, Path]) -> tuple[list[str], dict[str, np.ndarray]]:
    with np.load(sources["replay"], allow_pickle=False) as archive:
        if set(archive.files) != {"ordinal", "m1_probabilities", "m3_probabilities"}:
            raise ValueError("Replay keys drift")
        replay = {name: np.asarray(archive[name]) for name in archive.files}
    requested = replay["ordinal"].astype(int).tolist()
    selected: dict[int, str] = {}
    with sources["projection"].open("r", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if set(row) != {"ordinal", "opaque_component_group", "text"}:
                raise ValueError("Projection row drift")
            if row["ordinal"] in requested:
                selected[row["ordinal"]] = row["text"]
    if set(selected) != set(requested):
        raise ValueError("Projection/replay alignment drift")
    return [selected[value] for value in requested], replay


def sigmoid64(value: np.ndarray | float) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    output = np.empty_like(array)
    positive = array >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-array[positive]))
    exponent = np.exp(array[~positive])
    output[~positive] = exponent / (1.0 + exponent)
    return output


def sigmoid32(value: np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    output = np.empty_like(array, dtype=np.float32)
    positive = array >= 0
    output[positive] = np.float32(1) / (np.float32(1) + np.exp(-array[positive]))
    exponent = np.exp(array[~positive])
    output[~positive] = exponent / (np.float32(1) + exponent)
    return output


def qwen_ids(tokenizer: Any, prompt: dict[str, Any], text: str) -> list[int]:
    def apply(value: str) -> list[int]:
        result = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user_prefix"] + value + prompt["user_suffix"]},
            ],
            tokenize=True,
            return_dict=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if not isinstance(result, list) or any(type(token) is not int for token in result):
            raise TypeError("Independent M3 tokenizer drift")
        return result

    full = apply(text)
    if len(full) <= 384:
        selected = full
    else:
        raw = tokenizer.encode(text, add_special_tokens=False)
        low, high, selected = 0, len(raw), apply("")
        while low <= high:
            middle = (low + high) // 2
            candidate = apply(tokenizer.decode(raw[:middle], skip_special_tokens=False))
            if len(candidate) <= 384:
                selected, low = candidate, middle + 1
            else:
                high = middle - 1
    if not selected or len(selected) > 384:
        raise ValueError("Independent M3 length drift")
    if not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Independent M3 suffix drift")
    return selected


class IndependentModels:
    def __init__(self, config: dict[str, Any], sources: dict[str, Path]) -> None:
        import torch
        import mlx.core as mx
        import mlx.nn as nn
        from mlx_lm import load
        from mlx_lm.tuner import linear_to_lora_layers
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.set_num_threads(1)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            if torch.get_num_interop_threads() != 1:
                raise
        self.torch = torch
        checkpoint = sources["m1_checkpoint_root"]
        self.m1_tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        self.m1_model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint, local_files_only=True
        )
        self.m1_model.to(torch.device("cpu"))
        self.m1_model.eval()
        if [self.m1_model.config.id2label[index] for index in range(6)] != list(LABEL_ORDER):
            raise ValueError("Independent M1 label order drift")

        self.mx = mx
        self.m3_model, self.m3_tokenizer = load(str(sources["m3_base_root"]), lazy=False)
        self.m3_model.freeze()
        self.m3_model.eval()
        self.prompt = load_json(sources["m3_prompt"], 0o644)
        mx.random.seed(42)
        self.head = nn.Linear(2560, 6, bias=True)

        class Wrapper(nn.Module):
            def __init__(inner_self, model: Any, head: Any) -> None:
                super().__init__()
                inner_self.model = model
                inner_self.head = head

            def __call__(inner_self, input_ids: Any) -> Any:
                hidden = inner_self.model.model(input_ids)
                return inner_self.head(hidden[:, -1, :].astype(inner_self.head.weight.dtype))

        self.wrapper = Wrapper(self.m3_model, self.head)
        mx.random.seed(100042)
        linear_to_lora_layers(
            self.m3_model,
            16,
            {
                "rank": 8, "scale": 20.0, "dropout": 0.0,
                "keys": [
                    "self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj",
                    "self_attn.o_proj", "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj",
                ],
            },
        )
        insertions = []
        for name, module in self.m3_model.named_modules():
            if type(module).__name__ == "LoRALinear":
                match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
                if not match:
                    raise ValueError("Independent LoRA path drift")
                insertions.append((int(match.group(1)), match.group(2)))
        if len(insertions) != 112:
            raise ValueError("Independent LoRA insertion count drift")
        self.m3_model.load_weights(str(sources["m3_adapter"]), strict=False)
        self.head.load_weights(str(sources["m3_head"]), strict=True)
        self.m3_model.eval()

    def m1(self, text: str) -> tuple[np.ndarray, int]:
        batch = self.m1_tokenizer(
            [text], add_special_tokens=True, max_length=256, truncation=True, padding=True,
            return_attention_mask=True, return_tensors="pt",
        )
        length = int(batch["attention_mask"][0].sum().item())
        with self.torch.inference_mode():
            logits = self.m1_model(**batch).logits
            probability = self.torch.sigmoid(logits).detach().cpu().numpy().astype(np.float32)
        return np.ascontiguousarray(probability[0], dtype=np.float32), length

    def m3(self, text: str) -> np.ndarray:
        ids = qwen_ids(self.m3_tokenizer, self.prompt, text)
        logits = self.wrapper(self.mx.array([ids], dtype=self.mx.int32)).astype(self.mx.float32)
        self.mx.eval(logits)
        return np.ascontiguousarray(sigmoid32(np.asarray(logits, dtype=np.float32))[0])


class IndependentBundle:
    def __init__(self, sources: dict[str, Path]) -> None:
        manifest = load_json(sources["bundle_manifest"], 0o600)
        with np.load(sources["bundle_parameters"], allow_pickle=False) as archive:
            if set(archive.files) != PARAMETER_KEYS:
                raise ValueError("Independent bundle parameter keys drift")
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
        if manifest.get("labels") != list(LABEL_ORDER) or manifest.get("features") != list(FEATURE_NAMES):
            raise ValueError("Independent bundle order drift")
        self.m1_threshold = float(manifest["thresholds"]["m1"])
        self.m3_threshold = float(manifest["thresholds"]["m3"])
        self.cutoff = float(manifest["operating_point"]["cutoff"])
        self.mean = arrays["scaler_mean"].astype(np.float64)
        self.scale = arrays["scaler_scale"].astype(np.float64)
        self.coef = arrays["coef"].astype(np.float64)[0]
        self.intercept = float(arrays["intercept"].astype(np.float64)[0])

    def compute(self, probability: np.ndarray, chars: int, tokens: int) -> tuple[np.ndarray, np.ndarray, float, bool]:
        p = np.asarray(probability, dtype=np.float64)
        clipped = np.clip(p, 1e-15, 1.0 - 1e-15)
        entropy = -(clipped * np.log(clipped) + (1 - clipped) * np.log1p(-clipped))
        feature = np.concatenate(
            [
                p,
                np.asarray(
                    [
                        np.mean(entropy), np.max(entropy),
                        np.min(np.abs(p - self.m1_threshold)),
                        np.sum(p >= self.m1_threshold), np.max(p), np.min(p), chars, tokens,
                    ],
                    dtype=np.float64,
                ),
            ]
        )
        standardized = (feature - self.mean) / self.scale
        score = float(sigmoid64(float(standardized @ self.coef + self.intercept)))
        return feature, standardized, score, bool(score >= self.cutoff)


def recompute(
    config: dict[str, Any], sources: dict[str, Path], texts: list[str], replay: dict[str, np.ndarray]
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    models = IndependentModels(config, sources)
    bundle = IndependentBundle(sources)
    arrays = {
        "ordinal": replay["ordinal"].astype("<i2"),
        "m1_probabilities": np.empty((32, 6), dtype="<f4"),
        "m3_probabilities": np.empty((32, 6), dtype="<f4"),
        "features": np.empty((32, 14), dtype="<f8"),
        "standardized_features": np.empty((32, 14), dtype="<f8"),
        "route_score": np.empty(32, dtype="<f8"),
        "route_mask": np.empty(32, dtype=np.uint8),
        "m1_prediction": np.empty((32, 6), dtype=np.uint8),
        "m3_prediction": np.empty((32, 6), dtype=np.uint8),
        "final_prediction": np.empty((32, 6), dtype=np.uint8),
        "selected_path": np.empty(32, dtype=np.uint8),
        "neutral": np.empty(32, dtype=np.uint8),
        "character_length": np.empty(32, dtype="<i4"),
        "m1_token_length": np.empty(32, dtype="<i4"),
    }
    for index, text in enumerate(texts):
        m1, token_length = models.m1(text)
        m3 = models.m3(text)
        feature, standardized, score, route = bundle.compute(m1, len(text), token_length)
        m1_prediction = (m1 >= bundle.m1_threshold).astype(np.uint8)
        m3_prediction = (m3 >= bundle.m3_threshold).astype(np.uint8)
        final = m3_prediction if route else m1_prediction
        arrays["m1_probabilities"][index] = m1
        arrays["m3_probabilities"][index] = m3
        arrays["features"][index] = feature
        arrays["standardized_features"][index] = standardized
        arrays["route_score"][index] = score
        arrays["route_mask"][index] = int(route)
        arrays["m1_prediction"][index] = m1_prediction
        arrays["m3_prediction"][index] = m3_prediction
        arrays["final_prediction"][index] = final
        arrays["selected_path"][index] = int(route)
        arrays["neutral"][index] = int(not np.any(final))
        arrays["character_length"][index] = len(text)
        arrays["m1_token_length"][index] = token_length
    errors = {
        "m1_replay_max_abs_error": float(
            np.max(np.abs(arrays["m1_probabilities"] - replay["m1_probabilities"]))
        ),
        "m3_replay_max_abs_error": float(
            np.max(np.abs(arrays["m3_probabilities"] - replay["m3_probabilities"]))
        ),
    }
    return arrays, errors


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in SENSITIVE_KEYS:
                output.append(path)
            output.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return output


def _typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def _create(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o644)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, 0o644)


def acquire_lock(config: dict[str, Any]):
    path = _resolve(config["heavy_workload_lock"])
    descriptor = path.open("r+")
    try:
        fcntl.flock(descriptor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        descriptor.close()
        raise RuntimeError("EXP-066 verifier heavy workload lock is busy")
    return descriptor


def verify(config_path: Path) -> dict[str, Any]:
    config, sources = load_config(config_path)
    if stat.S_IMODE(os.lstat(PUBLIC_DIR).st_mode) != 0o755:
        raise ValueError("EXP-066 public dir mode drift")
    if stat.S_IMODE(os.lstat(PRIVATE_DIR).st_mode) != 0o700:
        raise ValueError("EXP-066 private dir mode drift")
    if os.path.lexists(CLI_PATH):
        raise ValueError("EXP-066 CLI exists before independent parity completion")
    for name in ("verification.json", "VERIFICATION-SUMMARY.md", "runtime-complete.json"):
        if os.path.lexists(PUBLIC_DIR / name):
            raise FileExistsError(f"EXP-066 verifier output exists: {name}")
    claim = load_json(PUBLIC_DIR / "run-claim.json", 0o644)
    run = load_json(PUBLIC_DIR / "run.json", 0o644)
    _regular(PUBLIC_DIR / "stdout.log", 0o644)
    if (
        claim.get("status") != "Claimed"
        or claim.get("cli_gate") != "closed_pending_independent_parity"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("cli_gate") != "closed_pending_independent_parity"
        or public_sensitive_paths(claim)
        or public_sensitive_paths(run)
    ):
        raise ValueError("EXP-066 public run/claim state or privacy drift")
    frozen = run.get("implementation", {})
    source_map = {"config": config_path.resolve()}
    source_map.update(
        {name: sources[name] for name in ("protocol", "runtime", "runner", "verifier", "tests", "finalizer")}
    )
    if set(frozen) != set(source_map):
        raise ValueError("EXP-066 frozen source set drift")
    for name, original in source_map.items():
        frozen_path = require_record(frozen[name], 0o644)
        if original.read_bytes() != frozen_path.read_bytes():
            raise ValueError(f"EXP-066 frozen source bytes drift: {name}")
    texts, replay = load_inputs(sources)
    parity_path = PRIVATE_DIR / "parity-output.npz"
    manifest_path = PRIVATE_DIR / "runtime-manifest.json"
    _regular(parity_path, 0o600)
    _regular(manifest_path, 0o600)
    if npz_schema(parity_path) != PARITY_SCHEMA:
        raise ValueError("EXP-066 observed parity schema drift")
    with np.load(parity_path, allow_pickle=False) as archive:
        if set(archive.files) != set(PARITY_SCHEMA):
            raise ValueError("EXP-066 observed parity keys drift")
        observed = {name: np.asarray(archive[name]) for name in archive.files}
    lock = acquire_lock(config)
    try:
        import mlx.core as mx

        mx.reset_peak_memory()
        expected, verifier_errors = recompute(config, sources, texts, replay)
        verifier_resources = {
            "ru_maxrss_raw": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "mlx_active_bytes": int(mx.get_active_memory()),
            "mlx_cache_bytes": int(mx.get_cache_memory()),
            "mlx_peak_bytes": int(mx.get_peak_memory()),
        }
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
    tolerances = config["parity"]
    continuous = {
        "m1_probabilities": tolerances["m1_probability_atol"],
        "m3_probabilities": tolerances["m3_probability_atol"],
        "features": tolerances["feature_atol"],
        "standardized_features": tolerances["standardized_feature_atol"],
        "route_score": tolerances["route_score_atol"],
    }
    max_differences: dict[str, float] = {}
    for name, tolerance in continuous.items():
        difference = float(np.max(np.abs(observed[name] - expected[name])))
        max_differences[f"{name}_max_abs_difference"] = difference
        if difference > tolerance:
            raise ValueError(f"EXP-066 independent continuous parity failed: {name}")
    for name in set(PARITY_SCHEMA) - set(continuous):
        if not np.array_equal(observed[name], expected[name]):
            raise ValueError(f"EXP-066 independent discrete parity failed: {name}")
    if (
        verifier_errors["m1_replay_max_abs_error"] > tolerances["m1_probability_atol"]
        or verifier_errors["m3_replay_max_abs_error"] > tolerances["m3_probability_atol"]
    ):
        raise ValueError("EXP-066 independent historical replay tolerance failed")
    observed_errors = {
        "m1_replay_max_abs_error": float(
            np.max(np.abs(observed["m1_probabilities"] - replay["m1_probabilities"]))
        ),
        "m3_replay_max_abs_error": float(
            np.max(np.abs(observed["m3_probabilities"] - replay["m3_probabilities"]))
        ),
    }
    output_record = {
        "logical_name": parity_path.name,
        **record(parity_path, include_path=False),
        "schema": PARITY_SCHEMA,
    }
    expected_manifest = {
        "schema_version": "exp-066-runtime-parity-private-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "CompletedAwaitingVerification",
        "environment": config["environment"],
        "runtime_assets": config["runtime_assets"],
        "prerequisite": config["prerequisite"],
        "implementation": config["implementation"],
        "parity_contract": config["parity"],
        "aggregate_replay_errors": observed_errors,
        "route_count": int(np.sum(observed["route_mask"])),
        "fallback_count": 0,
        "output": output_record,
        "access_attestation": config["access"],
        "no_classification_metrics_computed": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    manifest = load_json(manifest_path, 0o600)
    if not _typed_equal(manifest, expected_manifest):
        raise ValueError("EXP-066 private runtime manifest mismatch")
    private_outputs = {
        "parity_output": {
            "logical_name": parity_path.name,
            **record(parity_path, include_path=False),
            "schema_sha256": canonical_digest(PARITY_SCHEMA),
        },
        "runtime_manifest": {
            "logical_name": manifest_path.name,
            **record(manifest_path, include_path=False),
        },
    }
    if run.get("private_outputs") != private_outputs:
        raise ValueError("EXP-066 public/private cross-hash drift")
    if run.get("aggregate_parity") != {
        **observed_errors,
        "route_count": int(np.sum(observed["route_mask"])),
        "fallback_count": 0,
    }:
        raise ValueError("EXP-066 public aggregate parity drift")
    access = run.get("access_attestation", {})
    if any(
        access.get(name) is not False
        for name in (
            "original_validation_accessed", "historical_validation_npz_accessed",
            "test_accessed", "network_accessed",
        )
    ) or access.get("fallback_count") != 0:
        raise ValueError("EXP-066 access/fallback attestation drift")
    checks = [
        "config_environment", "source_identities", "asset_inventories", "exp064_prerequisite",
        "exp065_prerequisite", "output_modes", "append_only_terminal_absence",
        "cli_absent_before_parity", "run_state", "public_privacy", "frozen_sources",
        "projection_replay_alignment", "parity_npz_schema", "independent_m1_load",
        "independent_m3_load", "independent_m1_tokenization", "independent_m3_tokenization",
        "m1_historical_probability_replay", "m3_historical_probability_replay",
        "feature_replay", "standardized_feature_replay", "route_score_replay",
        "route_mask_exact", "selected_path_exact", "model_predictions_exact",
        "final_prediction_exact", "neutral_exact", "lengths_exact", "zero_fallback",
        "private_manifest_replay", "public_private_cross_hash", "access_boundary",
        "no_metrics", "cli_ready_only_after_pass",
    ]
    result = {
        "schema_version": "exp-066-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Passed",
        "verified_at_utc": utc_now(),
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "rows": 32,
        "aggregate_replay": verifier_errors,
        "runner_verifier_max_differences": max_differences,
        "route_count": int(np.sum(expected["route_mask"])),
        "fallback_count": 0,
        "private_outputs": private_outputs,
        "resources": verifier_resources,
        "access_attestation": {
            "original_validation_accessed": False,
            "historical_validation_npz_accessed": False,
            "test_accessed": False,
            "network_accessed": False,
            "fallback_count": 0,
        },
        "no_classification_metrics_computed": True,
        "cli_gate": "ready_for_activation",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if public_sensitive_paths(result):
        raise ValueError("EXP-066 verification public privacy drift")
    summary = (
        "# EXP-066 Runtime Parity Verification\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(checks)}/{len(checks)}`\n"
        "- Replay rows: `32`\n"
        "- M1/M3 probability tolerance: `1e-5 / 1e-5`\n"
        "- Fallback count: `0`\n"
        "- Original validation/test access: `false/false`\n"
        "- Classification metrics: `none`\n"
        "- CLI gate: `ready_for_activation`\n\n"
        f"Claim boundary: {CLAIM_BOUNDARY}\n"
    ).encode("utf-8")
    _create(PUBLIC_DIR / "VERIFICATION-SUMMARY.md", summary)
    _create(PUBLIC_DIR / "verification.json", canonical_json(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        result = verify(args.config)
    except Exception as error:
        if PUBLIC_DIR.exists() and not os.path.lexists(PUBLIC_DIR / "verification.json"):
            failed = {
                "schema_version": "exp-066-verification-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "status": "Failed",
                "verified_at_utc": utc_now(),
                "passed_count": 0,
                "failed_count": 1,
                "error_type": type(error).__name__,
                "fallback_count": 0,
                "test_accessed": False,
                "cli_gate": "closed",
                "claim_boundary": CLAIM_BOUNDARY,
            }
            _create(PUBLIC_DIR / "verification.json", canonical_json(failed))
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

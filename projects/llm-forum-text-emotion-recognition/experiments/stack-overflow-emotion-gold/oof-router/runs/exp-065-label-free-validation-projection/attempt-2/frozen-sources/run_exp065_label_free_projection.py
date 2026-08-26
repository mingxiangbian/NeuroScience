#!/usr/bin/env python3
"""Materialize the one-shot EXP-065 label-free validation projection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import sys
import time
from typing import Any
import zipfile

import numpy as np


EXPERIMENT_ID = "EXP-065"
RUN_ID = "exp-065-label-free-validation-projection"
ATTEMPT_ID = "attempt-2"
CONFIG_SCHEMA = "exp-065-label-free-projection-config-v2"
MANIFEST_SCHEMA = "exp-065-label-free-projection-manifest-v1"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
VALIDATION_KEYS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "text",
    "labels", "neutral", "label_cardinality",
}
PROJECTION_KEYS = {"ordinal", "opaque_component_group", "text"}
M1_SCHEMA = {
    "probabilities": {"shape": [5, 720, 6], "dtype": "float32", "fortran_order": False},
    "gold": {"shape": [720, 6], "dtype": "uint8", "fortran_order": False},
    "fixed_predictions": {"shape": [720, 6], "dtype": "uint8", "fortran_order": False},
    "shared_threshold_predictions": {"shape": [720, 6], "dtype": "uint8", "fortran_order": False},
    "sample_ids": {"shape": [720], "dtype": "<U31", "fortran_order": False},
    "component_ids": {"shape": [720], "dtype": "<U34", "fortran_order": False},
}
M3_SCHEMA = {
    **M1_SCHEMA,
    "probabilities": {"shape": [2, 720, 6], "dtype": "float32", "fortran_order": False},
}
REPLAY_SCHEMA = {
    "ordinal": {"shape": [32], "dtype": "int16", "fortran_order": False},
    "m1_probabilities": {"shape": [32, 6], "dtype": "float32", "fortran_order": False},
    "m3_probabilities": {"shape": [32, 6], "dtype": "float32", "fortran_order": False},
}
PUBLIC_SENSITIVE_KEYS = {
    "text", "raw_text", "ordinal", "ordinals", "opaque_component_group",
    "sample_id", "sample_ids", "component_id", "component_ids", "labels", "gold",
    "probabilities", "m1_probabilities", "m3_probabilities", "predictions",
    "fixed_predictions", "shared_threshold_predictions", "private_path",
}
PUBLIC_SOURCE_ALIASES = {
    "validation": "validation_source",
    "m1_probabilities": "m1_stack_source",
    "m1_selection": "m1_selection_source",
    "m3_probabilities": "m3_stack_source",
    "m3_selection": "m3_selection_source",
}
CLAIM_BOUNDARY = (
    "A private label-free validation-text projection and selected-epoch probability replay "
    "for runtime parity/latency work only; no classification metric, model-selection, test, "
    "deployment-generalization, or emotion-mechanism claim."
)


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-065-label-free-validation-projection-attempt-2.json"
PUBLIC_REL = BASE / "runs" / RUN_ID / ATTEMPT_ID
PRIVATE_REL = BASE / "private" / RUN_ID / ATTEMPT_ID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _resolve(value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe project-relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses symlink: {value}")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def artifact_record(path: Path, include_path: bool = True) -> dict[str, Any]:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"Artifact is not one regular file: {path}")
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
        raise ValueError("Source record schema drift")
    path = _resolve(value["path"])
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
        or metadata.st_size != value["bytes"]
        or value["mode"] != f"{mode:04o}"
        or sha256_file(path) != value["sha256"]
    ):
        raise ValueError(f"Source identity/mode drift: {value['path']}")
    return path


def npz_schema(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("NPZ contains duplicate members")
        if any(not member.endswith(".npy") or "/" in member for member in members):
            raise ValueError("NPZ member layout drift")
        for member in sorted(members):
            with archive.open(member) as source:
                version = np.lib.format.read_magic(source)
                if version == (1, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_1_0(source)
                elif version == (2, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_2_0(source)
                else:
                    shape, fortran, dtype = np.lib.format._read_array_header(source, version)
            result[Path(member).stem] = {
                "shape": list(shape), "dtype": str(dtype), "fortran_order": bool(fortran)
            }
    return result


def replay_ordinals() -> np.ndarray:
    values = [(2 * k * 719 + 31) // 62 for k in range(32)]
    result = np.asarray(values, dtype="<i2")
    if result.shape != (32,) or result[0] != 0 or result[-1] != 719:
        raise RuntimeError("EXP-065 ordinal formula drift")
    if not np.all(np.diff(result.astype(np.int64)) > 0):
        raise RuntimeError("EXP-065 replay ordinals are not strictly increasing")
    return result


def project_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, int] = {}
    projected: list[dict[str, Any]] = []
    for ordinal, row in enumerate(source_rows):
        if set(row) != VALIDATION_KEYS:
            raise ValueError("EXP-065 validation row key drift")
        sample_id = row["sample_id"]
        component_id = row["component_id"]
        text = row["text"]
        if (
            not isinstance(sample_id, str)
            or not sample_id
            or not isinstance(component_id, str)
            or not component_id
            or not isinstance(text, str)
            or not text
        ):
            raise ValueError("EXP-065 allowed validation field type/value drift")
        group = groups.setdefault(component_id, len(groups))
        projected.append(
            {"ordinal": ordinal, "opaque_component_group": group, "text": text}
        )
    if len(projected) != 720 or len({row["ordinal"] for row in projected}) != 720:
        raise ValueError("EXP-065 projection row/ordinal drift")
    return projected


def projection_jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    chunks: list[str] = []
    for row in rows:
        if set(row) != PROJECTION_KEYS:
            raise ValueError("EXP-065 projected row key drift")
        chunks.append(
            json.dumps(
                row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        )
    return ("\n".join(chunks) + "\n").encode("utf-8")


def selected_probabilities(stack: np.ndarray, selected_epoch: int, ordinals: np.ndarray) -> np.ndarray:
    values = np.asarray(stack)
    if values.ndim != 3 or values.shape[1:] != (720, 6) or values.dtype != np.float32:
        raise ValueError("EXP-065 probability stack contract drift")
    if type(selected_epoch) is not int or not 1 <= selected_epoch <= values.shape[0]:
        raise ValueError("EXP-065 selected epoch out of bounds")
    selected = np.ascontiguousarray(values[selected_epoch - 1, ordinals.astype(np.int64), :], dtype="<f4")
    if selected.shape != (32, 6) or not np.all(np.isfinite(selected)):
        raise ValueError("EXP-065 selected probabilities shape/finite drift")
    if np.any((selected < 0) | (selected > 1)):
        raise ValueError("EXP-065 selected probabilities outside [0,1]")
    return selected


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    config_path = config_path.resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise ValueError("EXP-065 requires the frozen config path")
    if artifact_record(config_path)["mode"] != "0644":
        raise ValueError("EXP-065 config must be mode 0644")
    config = _load_json(config_path)
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or config.get("rq_id") != "RQ-S3"
        or config.get("tier") != "Major"
        or config.get("model_seed") != 42
        or config.get("labels") != list(LABEL_ORDER)
        or config.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("EXP-065 config identity drift")
    if config.get("outputs") != {
        "public_dir": str(PUBLIC_REL), "private_dir": str(PRIVATE_REL)
    }:
        raise ValueError("EXP-065 output contract drift")
    if config.get("projection") != {
        "rows": 720,
        "fields": ["ordinal", "opaque_component_group", "text"],
        "encoding": "UTF-8",
        "json": "sorted keys compact separators allow_nan=false one LF per row terminal LF",
    }:
        raise ValueError("EXP-065 projection contract drift")
    if config.get("replay") != {
        "rows": 32,
        "ordinal_formula": "(2*k*719+31)//62 for k=0..31",
        "m1_selected_epoch": 4,
        "m3_selected_epoch": 2,
        "npz_schema": REPLAY_SCHEMA,
        "allow_pickle": False,
    }:
        raise ValueError("EXP-065 replay contract drift")
    if config.get("access") != {
        "role": "EXP-065 independent data steward",
        "label_bearing_containers_accessed": True,
        "label_values_used": False,
        "label_values_persisted": False,
        "historical_prediction_values_used": False,
        "raw_text_persisted_only_in_private_projection": True,
        "validation_access": True,
        "test_access": False,
        "model_or_checkpoint_access": False,
        "model_forward": False,
    }:
        raise ValueError("EXP-065 access contract drift")
    sources: dict[str, Path] = {"config": config_path}
    inputs = config.get("inputs", {})
    if set(inputs) != {"validation", "m1_probabilities", "m1_selection", "m3_probabilities", "m3_selection"}:
        raise ValueError("EXP-065 input set drift")
    sources["validation"] = require_record(inputs["validation"]["artifact"], 0o600)
    if inputs["validation"].get("row_count") != 720 or set(inputs["validation"].get("row_keys", [])) != VALIDATION_KEYS:
        raise ValueError("EXP-065 validation contract drift")
    sources["m1_probabilities"] = require_record(inputs["m1_probabilities"]["artifact"], 0o600)
    sources["m3_probabilities"] = require_record(inputs["m3_probabilities"]["artifact"], 0o600)
    if inputs["m1_probabilities"].get("npz_schema") != M1_SCHEMA:
        raise ValueError("EXP-065 M1 NPZ schema contract drift")
    if inputs["m3_probabilities"].get("npz_schema") != M3_SCHEMA:
        raise ValueError("EXP-065 M3 NPZ schema contract drift")
    sources["m1_selection"] = require_record(inputs["m1_selection"]["artifact"], 0o644)
    sources["m3_selection"] = require_record(inputs["m3_selection"]["artifact"], 0o644)
    if inputs["m1_selection"].get("selected_epoch") != 4 or inputs["m3_selection"].get("selected_epoch") != 2:
        raise ValueError("EXP-065 selected epoch contract drift")
    for section in ("prerequisite", "implementation"):
        values = config.get(section, {})
        if not isinstance(values, dict) or not values:
            raise ValueError(f"EXP-065 {section} missing")
        for name, source_record in values.items():
            sources[name] = require_record(source_record, 0o644)
    prerequisite_completion = _load_json(sources["exp064_completion"])
    prerequisite_verification = _load_json(sources["exp064_verification"])
    if prerequisite_completion.get("status") != "Complete" or prerequisite_completion.get("experiment_id") != "EXP-064":
        raise ValueError("EXP-065 prerequisite completion drift")
    if prerequisite_verification.get("status") != "Passed" or prerequisite_verification.get("failed_count") != 0:
        raise ValueError("EXP-065 prerequisite verification drift")
    recovery = config.get("recovery", {})
    if set(recovery) != {"prior_claim", "prior_run", "reason", "method_changed", "data_changed"}:
        raise ValueError("EXP-065 recovery contract drift")
    sources["prior_claim"] = require_record(recovery["prior_claim"], 0o644)
    sources["prior_run"] = require_record(recovery["prior_run"], 0o644)
    prior_claim = _load_json(sources["prior_claim"])
    prior_run = _load_json(sources["prior_run"])
    if (
        prior_claim.get("experiment_id") != EXPERIMENT_ID
        or prior_claim.get("status") != "Claimed"
        or prior_run.get("experiment_id") != EXPERIMENT_ID
        or prior_run.get("status") != "Failed"
        or recovery["reason"] != "public_source_alias_privacy_false_positive"
        or recovery["method_changed"] is not False
        or recovery["data_changed"] is not False
    ):
        raise ValueError("EXP-065 prior failed attempt lineage drift")
    return config, sources


def load_sources(config: dict[str, Any], sources: dict[str, Path]) -> dict[str, Any]:
    validation_rows: list[dict[str, Any]] = []
    with sources["validation"].open("r", encoding="utf-8") as source:
        for line in source:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("EXP-065 validation row is not an object")
            validation_rows.append(value)
    if len(validation_rows) != 720:
        raise ValueError("EXP-065 validation row count drift")
    projected = project_rows(validation_rows)
    validation_sample_ids = [row["sample_id"] for row in validation_rows]
    validation_component_ids = [row["component_id"] for row in validation_rows]
    if len(set(validation_sample_ids)) != 720:
        raise ValueError("EXP-065 validation sample IDs not unique")
    family_values: dict[str, Any] = {}
    for family, schema, epoch in (("m1", M1_SCHEMA, 4), ("m3", M3_SCHEMA, 2)):
        path = sources[f"{family}_probabilities"]
        if npz_schema(path) != schema:
            raise ValueError(f"EXP-065 {family} NPZ header drift")
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != set(schema):
                raise ValueError(f"EXP-065 {family} NPZ key drift")
            sample_ids = np.asarray(archive["sample_ids"])
            component_ids = np.asarray(archive["component_ids"])
            probability_stack = np.asarray(archive["probabilities"])
        selection = _load_json(sources[f"{family}_selection"])
        if set(selection) != {
            "eligible_epochs", "maximum_fixed_macro_f1", "practical_tie_delta",
            "selected_epoch", "selected_fixed_macro_f1", "selection_deficit_from_maximum",
        }:
            raise ValueError(f"EXP-065 {family} selection schema drift")
        if selection.get("selected_epoch") != epoch:
            raise ValueError(f"EXP-065 {family} selected epoch drift")
        if sample_ids.tolist() != validation_sample_ids:
            raise ValueError(f"EXP-065 {family} sample order drift")
        if component_ids.tolist() != validation_component_ids:
            raise ValueError(f"EXP-065 {family} component order drift")
        family_values[family] = {"stack": probability_stack, "selected_epoch": epoch}
    return {"projected": projected, "families": family_values}


def replay_npz_bytes(arrays: dict[str, np.ndarray]) -> bytes:
    buffer = BytesIO()
    np.savez(buffer, **arrays)
    return buffer.getvalue()


def _create(path: Path, payload: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, mode)


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(child_path)
            violations.extend(public_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def public_source_aliases(inputs: dict[str, Any]) -> dict[str, Any]:
    if set(inputs) != set(PUBLIC_SOURCE_ALIASES):
        raise ValueError("EXP-065 public source alias input set drift")
    return {
        alias: {
            "logical_name": alias,
            "bytes": inputs[source]["artifact"]["bytes"],
            "sha256": inputs[source]["artifact"]["sha256"],
            "mode": inputs[source]["artifact"]["mode"],
        }
        for source, alias in PUBLIC_SOURCE_ALIASES.items()
    }


def _freeze(public_dir: Path, sources: dict[str, Path]) -> dict[str, Any]:
    frozen = public_dir / "frozen-sources"
    frozen.mkdir(mode=0o755)
    result: dict[str, Any] = {}
    for name in ("config", "protocol", "runner", "verifier", "tests"):
        source = sources[name]
        target = frozen / ("config.json" if name == "config" else source.name)
        _create(target, source.read_bytes(), 0o644)
        result[name] = artifact_record(target)
    return result


def _assert_outputs_absent(public_dir: Path, private_dir: Path) -> None:
    for path in (public_dir, private_dir):
        if os.path.lexists(path):
            raise FileExistsError(f"EXP-065 output already exists: {path.relative_to(PROJECT_ROOT)}")
        _resolve(path.relative_to(PROJECT_ROOT))


def preflight(config_path: Path) -> dict[str, Any]:
    config, sources = load_config(config_path)
    public_dir = _resolve(config["outputs"]["public_dir"])
    private_dir = _resolve(config["outputs"]["private_dir"])
    _assert_outputs_absent(public_dir, private_dir)
    loaded = load_sources(config, sources)
    del loaded
    return {
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Ready",
        "rows": 720,
        "replay_rows": 32,
        "public_output_absent": True,
        "private_output_absent": True,
        "label_bearing_containers_accessed": True,
        "label_values_used": False,
        "label_values_persisted": False,
        "test_access": False,
    }


def execute(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    started_at = utc_now()
    started = time.perf_counter()
    config, sources = load_config(config_path)
    config_record = artifact_record(config_path)
    public_dir = _resolve(config["outputs"]["public_dir"])
    private_dir = _resolve(config["outputs"]["private_dir"])
    _assert_outputs_absent(public_dir, private_dir)
    loaded = load_sources(config, sources)
    public_dir.mkdir(mode=0o755)
    os.chmod(public_dir, 0o755)
    private_dir.mkdir(mode=0o700)
    os.chmod(private_dir, 0o700)
    implementation = _freeze(public_dir, sources)
    claim = {
        "schema_version": "exp-065-run-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Claimed",
        "claimed_at_utc": started_at,
        "config": config_record,
        "one_shot": True,
    }
    _create(public_dir / "run-claim.json", canonical_json_bytes(claim), 0o644)
    try:
        ordinals = replay_ordinals()
        projection_payload = projection_jsonl_bytes(loaded["projected"])
        replay_arrays = {
            "ordinal": ordinals,
            "m1_probabilities": selected_probabilities(
                loaded["families"]["m1"]["stack"], 4, ordinals
            ),
            "m3_probabilities": selected_probabilities(
                loaded["families"]["m3"]["stack"], 2, ordinals
            ),
        }
        replay_payload = replay_npz_bytes(replay_arrays)
        projection_path = private_dir / "validation-text-projection.jsonl"
        replay_path = private_dir / "validation-probability-replay-32.npz"
        _create(projection_path, projection_payload, 0o600)
        _create(replay_path, replay_payload, 0o600)
        if npz_schema(replay_path) != REPLAY_SCHEMA:
            raise RuntimeError("EXP-065 written replay schema drift")
        output_records = {
            "text_projection": {
                "logical_name": projection_path.name,
                **artifact_record(projection_path, include_path=False),
            },
            "probability_replay": {
                "logical_name": replay_path.name,
                **artifact_record(replay_path, include_path=False),
                "content_schema_sha256": canonical_digest(REPLAY_SCHEMA),
            },
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "model_seed": 42,
            "status": "MaterializedAwaitingVerification",
            "labels": list(LABEL_ORDER),
            "sources": config["inputs"],
            "prerequisite": config["prerequisite"],
            "recovery": config["recovery"],
            "implementation": config["implementation"],
            "selected_epochs": {"m1": 4, "m3": 2},
            "alignment": {
                "rows": 720,
                "validation_m1_m3_sample_order_exact": True,
                "validation_m1_m3_component_order_exact": True,
            },
            "projection": {
                "rows": 720,
                "fields": ["ordinal", "opaque_component_group", "text"],
                "dense_group_rule": "first appearance, zero based, gap free",
                "encoding": "UTF-8 JSONL with one terminal LF",
            },
            "replay": {
                "rows": 32,
                "ordinal_formula": "(2*k*719+31)//62 for k=0..31",
                "npz_schema": REPLAY_SCHEMA,
                "selected_epoch_indexing": "zero-based selected_epoch_minus_one",
                "allow_pickle": False,
            },
            "outputs": output_records,
            "access_attestation": {
                "label_bearing_containers_accessed": True,
                "label_values_used": False,
                "label_values_affected_outputs": False,
                "label_values_persisted": False,
                "historical_gold_or_prediction_values_used": False,
                "sample_or_component_ids_persisted": False,
                "test_accessed": False,
                "model_or_checkpoint_accessed": False,
                "model_forward_executed": False,
            },
            "no_classification_metrics_computed": True,
            "claim_boundary": CLAIM_BOUNDARY,
        }
        manifest_path = private_dir / "projection-manifest.json"
        _create(manifest_path, canonical_json_bytes(manifest), 0o600)
        output_records["projection_manifest"] = {
            "logical_name": manifest_path.name,
            **artifact_record(manifest_path, include_path=False),
        }
        source_aliases = public_source_aliases(config["inputs"])
        run = {
            "schema_version": "exp-065-run-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "tier": "Major",
            "rq_id": "RQ-S3",
            "stage": "label-free-validation-projection-and-probability-replay",
            "status": "CompletedAwaitingVerification",
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "elapsed_seconds": time.perf_counter() - started,
            "command": f"{sys.executable} {Path(__file__).relative_to(PROJECT_ROOT)} --config {config_path.relative_to(PROJECT_ROOT)}",
            "working_directory": str(PROJECT_ROOT),
            "implementation": implementation,
            "prerequisite": config["prerequisite"],
            "recovery": config["recovery"],
            "source_aliases": source_aliases,
            "contract": {
                "model_seed": 42,
                "projection_row_count": 720,
                "replay_row_count": 32,
                "label_count": 6,
                "m1_selected_epoch": 4,
                "m3_selected_epoch": 2,
                "no_classification_metrics": True,
            },
            "private_outputs": output_records,
            "access_attestation": {
                "label_bearing_containers_accessed": True,
                "label_values_used": False,
                "label_values_affected_outputs": False,
                "label_values_persisted": False,
                "historical_gold_or_prediction_values_used": False,
                "sample_or_component_ids_persisted": False,
                "test_accessed": False,
                "model_or_checkpoint_accessed": False,
                "model_forward_executed": False,
            },
            "privacy": {"row_level_public": False, "public_scan_passed": True},
            "claim_boundary": CLAIM_BOUNDARY,
            "warnings": [],
        }
        violations = public_sensitive_paths(run)
        if violations:
            raise RuntimeError(f"EXP-065 public privacy schema violation: {violations}")
        _create(
            public_dir / "stdout.log",
            (
                f"{EXPERIMENT_ID} {RUN_ID}\nstatus=CompletedAwaitingVerification\n"
                "rows=720\nreplay_rows=32\nlabel_values_used=false\n"
                "label_values_persisted=false\ntest_access=false\n"
            ).encode("utf-8"),
            0o644,
        )
        _create(public_dir / "run.json", canonical_json_bytes(run), 0o644)
        return run
    except Exception as error:
        private_failure = {
            "schema_version": "exp-065-private-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if not os.path.lexists(private_dir / "failure.json"):
            _create(private_dir / "failure.json", canonical_json_bytes(private_failure), 0o600)
        public_failure = {
            "schema_version": "exp-065-run-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "label_values_persisted": False,
            "test_accessed": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
        if not os.path.lexists(public_dir / "run.json"):
            _create(public_dir / "run.json", canonical_json_bytes(public_failure), 0o644)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = preflight(args.config) if args.check else execute(args.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

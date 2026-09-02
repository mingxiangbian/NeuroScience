#!/usr/bin/env python3
"""Independently rebuild and verify EXP-065 projection artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
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
SENSITIVE_KEYS = {
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
PUBLIC_DIR = PROJECT_ROOT / BASE / "runs" / RUN_ID / ATTEMPT_ID
PRIVATE_DIR = PROJECT_ROOT / BASE / "private" / RUN_ID / ATTEMPT_ID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
        raise ValueError(f"File type/mode drift: {path}")
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
        raise ValueError("Source record schema drift")
    path = _resolve(value["path"])
    metadata = _regular(path, mode)
    if (
        metadata.st_size != value["bytes"]
        or value["mode"] != f"{mode:04o}"
        or sha256_file(path) != value["sha256"]
    ):
        raise ValueError(f"Source identity drift: {value['path']}")
    return path


def load_json(path: Path, mode: int, *, canonical: bool = True) -> dict[str, Any]:
    _regular(path, mode)
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    if canonical and canonical_json_bytes(value) != raw:
        raise ValueError(f"Non-canonical JSON: {path}")
    return value


def npz_schema(path: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("NPZ duplicate members")
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
            output[Path(member).stem] = {
                "shape": list(shape), "dtype": str(dtype), "fortran_order": bool(fortran)
            }
    return output


def fixed_ordinals() -> np.ndarray:
    values = np.asarray([(2 * k * 719 + 31) // 62 for k in range(32)], dtype="<i2")
    if values[0] != 0 or values[-1] != 719 or not np.all(np.diff(values.astype(np.int64)) > 0):
        raise ValueError("Independent ordinal formula drift")
    return values


def independent_projection(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    dense: dict[str, int] = {}
    projected: list[dict[str, Any]] = []
    sample_ids: list[str] = []
    component_ids: list[str] = []
    for ordinal, row in enumerate(rows):
        if set(row) != VALIDATION_KEYS:
            raise ValueError("Validation row key drift")
        sample_id = row["sample_id"]
        component_id = row["component_id"]
        text = row["text"]
        if not all(isinstance(value, str) and value for value in (sample_id, component_id, text)):
            raise ValueError("Allowed validation value drift")
        sample_ids.append(sample_id)
        component_ids.append(component_id)
        group = dense.setdefault(component_id, len(dense))
        projected.append({"ordinal": ordinal, "opaque_component_group": group, "text": text})
    if len(rows) != 720 or len(set(sample_ids)) != 720:
        raise ValueError("Validation row/sample cardinality drift")
    if sorted({row["opaque_component_group"] for row in projected}) != list(range(len(dense))):
        raise ValueError("Dense group mapping is not gap-free")
    return projected, sample_ids, component_ids


def projection_bytes(rows: list[dict[str, Any]]) -> bytes:
    lines: list[str] = []
    for row in rows:
        if set(row) != PROJECTION_KEYS:
            raise ValueError("Projection key drift")
        lines.append(
            json.dumps(
                row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def selected_slice(stack: np.ndarray, epoch: int, ordinals: np.ndarray) -> np.ndarray:
    values = np.asarray(stack)
    if values.dtype != np.float32 or values.ndim != 3 or values.shape[1:] != (720, 6):
        raise ValueError("Probability stack drift")
    if type(epoch) is not int or not 1 <= epoch <= values.shape[0]:
        raise ValueError("Selected epoch out of range")
    selected = np.ascontiguousarray(values[epoch - 1, ordinals.astype(np.int64), :], dtype="<f4")
    if selected.shape != (32, 6) or not np.all(np.isfinite(selected)):
        raise ValueError("Selected probability shape/finite drift")
    if np.any((selected < 0) | (selected > 1)):
        raise ValueError("Selected probabilities outside [0,1]")
    return selected


def _load_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    config_path = config_path.resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise ValueError("Verifier requires frozen EXP-065 config")
    config = load_json(config_path, 0o644, canonical=False)
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or config.get("model_seed") != 42
        or config.get("labels") != list(LABEL_ORDER)
        or config.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("EXP-065 verifier config identity drift")
    sources: dict[str, Path] = {"config": config_path}
    inputs = config["inputs"]
    sources["validation"] = require_record(inputs["validation"]["artifact"], 0o600)
    sources["m1_probabilities"] = require_record(inputs["m1_probabilities"]["artifact"], 0o600)
    sources["m3_probabilities"] = require_record(inputs["m3_probabilities"]["artifact"], 0o600)
    sources["m1_selection"] = require_record(inputs["m1_selection"]["artifact"], 0o644)
    sources["m3_selection"] = require_record(inputs["m3_selection"]["artifact"], 0o644)
    for section in ("prerequisite", "implementation"):
        for name, source_record in config[section].items():
            sources[name] = require_record(source_record, 0o644)
    recovery = config.get("recovery", {})
    if set(recovery) != {"prior_claim", "prior_run", "reason", "method_changed", "data_changed"}:
        raise ValueError("EXP-065 verifier recovery contract drift")
    sources["prior_claim"] = require_record(recovery["prior_claim"], 0o644)
    sources["prior_run"] = require_record(recovery["prior_run"], 0o644)
    prior_claim = load_json(sources["prior_claim"], 0o644)
    prior_run = load_json(sources["prior_run"], 0o644)
    if (
        prior_claim.get("status") != "Claimed"
        or prior_run.get("status") != "Failed"
        or recovery["reason"] != "public_source_alias_privacy_false_positive"
        or recovery["method_changed"] is not False
        or recovery["data_changed"] is not False
    ):
        raise ValueError("EXP-065 verifier prior attempt lineage drift")
    if npz_schema(sources["m1_probabilities"]) != M1_SCHEMA:
        raise ValueError("M1 source schema drift")
    if npz_schema(sources["m3_probabilities"]) != M3_SCHEMA:
        raise ValueError("M3 source schema drift")
    if inputs["m1_probabilities"]["npz_schema"] != M1_SCHEMA or inputs["m3_probabilities"]["npz_schema"] != M3_SCHEMA:
        raise ValueError("Registered source schema drift")
    return config, sources


def recompute(config: dict[str, Any], sources: dict[str, Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with sources["validation"].open("r", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("Validation row is not an object")
            rows.append(row)
    projected, validation_ids, validation_components = independent_projection(rows)
    ordinals = fixed_ordinals()
    selected: dict[str, np.ndarray] = {}
    for family, schema, expected_epoch in (("m1", M1_SCHEMA, 4), ("m3", M3_SCHEMA, 2)):
        with np.load(sources[f"{family}_probabilities"], allow_pickle=False) as archive:
            if set(archive.files) != set(schema):
                raise ValueError(f"{family} source key drift")
            ids = np.asarray(archive["sample_ids"])
            components = np.asarray(archive["component_ids"])
            probability_stack = np.asarray(archive["probabilities"])
        selection = load_json(sources[f"{family}_selection"], 0o644, canonical=False)
        epoch = selection.get("selected_epoch")
        if epoch != expected_epoch or config["inputs"][f"{family}_selection"]["selected_epoch"] != epoch:
            raise ValueError(f"{family} selected epoch drift")
        if ids.tolist() != validation_ids or components.tolist() != validation_components:
            raise ValueError(f"{family} validation alignment drift")
        selected[family] = selected_slice(probability_stack, epoch, ordinals)
    return {
        "projection_rows": projected,
        "projection_payload": projection_bytes(projected),
        "ordinals": ordinals,
        "m1": selected["m1"],
        "m3": selected["m3"],
    }


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


def expected_public_source_aliases(inputs: dict[str, Any]) -> dict[str, Any]:
    if set(inputs) != set(PUBLIC_SOURCE_ALIASES):
        raise ValueError("EXP-065 verifier public source alias input set drift")
    return {
        alias: {
            "logical_name": alias,
            "bytes": inputs[source]["artifact"]["bytes"],
            "sha256": inputs[source]["artifact"]["sha256"],
            "mode": inputs[source]["artifact"]["mode"],
        }
        for source, alias in PUBLIC_SOURCE_ALIASES.items()
    }


def _typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def _create(path: Path, payload: bytes, mode: int = 0o644) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, mode)


def verify(config_path: Path) -> dict[str, Any]:
    config, sources = _load_config(config_path)
    if stat.S_IMODE(os.lstat(PUBLIC_DIR).st_mode) != 0o755:
        raise ValueError("Public directory mode drift")
    if stat.S_IMODE(os.lstat(PRIVATE_DIR).st_mode) != 0o700:
        raise ValueError("Private directory mode drift")
    for terminal in ("verification.json", "VERIFICATION-SUMMARY.md", "projection-complete.json"):
        if os.path.lexists(PUBLIC_DIR / terminal):
            raise FileExistsError(f"EXP-065 verification output exists: {terminal}")
    claim = load_json(PUBLIC_DIR / "run-claim.json", 0o644)
    run = load_json(PUBLIC_DIR / "run.json", 0o644)
    _regular(PUBLIC_DIR / "stdout.log", 0o644)
    if (
        claim.get("status") != "Claimed"
        or claim.get("attempt_id") != ATTEMPT_ID
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("attempt_id") != ATTEMPT_ID
    ):
        raise ValueError("EXP-065 run state drift")
    if public_sensitive_paths(claim) or public_sensitive_paths(run):
        raise ValueError("EXP-065 public privacy drift")
    if run.get("prerequisite") != config.get("prerequisite"):
        raise ValueError("EXP-065 prerequisite lineage drift")
    if run.get("recovery") != config.get("recovery"):
        raise ValueError("EXP-065 recovery lineage drift")
    if run.get("source_aliases") != expected_public_source_aliases(config["inputs"]):
        raise ValueError("EXP-065 safe public source alias drift")
    prerequisite_completion = load_json(sources["exp064_completion"], 0o644)
    prerequisite_verification = load_json(sources["exp064_verification"], 0o644)
    if prerequisite_completion.get("status") != "Complete":
        raise ValueError("EXP-064 completion prerequisite failed")
    if prerequisite_verification.get("status") != "Passed" or prerequisite_verification.get("failed_count") != 0:
        raise ValueError("EXP-064 verification prerequisite failed")
    frozen = run.get("implementation", {})
    source_map = {"config": config_path.resolve()}
    source_map.update({name: sources[name] for name in ("protocol", "runner", "verifier", "tests")})
    if set(frozen) != set(source_map):
        raise ValueError("EXP-065 frozen source set drift")
    for name, original in source_map.items():
        frozen_path = require_record(frozen[name], 0o644)
        if original.read_bytes() != frozen_path.read_bytes():
            raise ValueError(f"EXP-065 frozen source bytes drift: {name}")
    expected = recompute(config, sources)
    projection_path = PRIVATE_DIR / "validation-text-projection.jsonl"
    replay_path = PRIVATE_DIR / "validation-probability-replay-32.npz"
    manifest_path = PRIVATE_DIR / "projection-manifest.json"
    _regular(projection_path, 0o600)
    _regular(replay_path, 0o600)
    _regular(manifest_path, 0o600)
    if projection_path.read_bytes() != expected["projection_payload"]:
        raise ValueError("EXP-065 projection bytes mismatch")
    observed_projection: list[dict[str, Any]] = []
    with projection_path.open("r", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != PROJECTION_KEYS:
                raise ValueError("EXP-065 output projection schema drift")
            observed_projection.append(row)
    if not _typed_equal(observed_projection, expected["projection_rows"]):
        raise ValueError("EXP-065 projection semantic mismatch")
    if npz_schema(replay_path) != REPLAY_SCHEMA:
        raise ValueError("EXP-065 replay NPZ schema drift")
    with np.load(replay_path, allow_pickle=False) as archive:
        if set(archive.files) != set(REPLAY_SCHEMA):
            raise ValueError("EXP-065 replay NPZ key drift")
        observed_ordinal = np.asarray(archive["ordinal"])
        observed_m1 = np.asarray(archive["m1_probabilities"])
        observed_m3 = np.asarray(archive["m3_probabilities"])
    if not np.array_equal(observed_ordinal, expected["ordinals"]):
        raise ValueError("EXP-065 replay ordinal mismatch")
    if not np.array_equal(observed_m1, expected["m1"]) or not np.array_equal(observed_m3, expected["m3"]):
        raise ValueError("EXP-065 selected-epoch probability mismatch")
    output_records = {
        "text_projection": {"logical_name": projection_path.name, **record(projection_path, False)},
        "probability_replay": {
            "logical_name": replay_path.name,
            **record(replay_path, False),
            "content_schema_sha256": canonical_digest(REPLAY_SCHEMA),
        },
    }
    expected_manifest = {
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
    observed_manifest = load_json(manifest_path, 0o600)
    if not _typed_equal(observed_manifest, expected_manifest):
        raise ValueError("EXP-065 private manifest mismatch")
    output_records["projection_manifest"] = {
        "logical_name": manifest_path.name, **record(manifest_path, False)
    }
    if run.get("private_outputs") != output_records:
        raise ValueError("EXP-065 public/private cross-hash drift")
    access = run.get("access_attestation", {})
    required_false = (
        "label_values_used", "label_values_affected_outputs", "label_values_persisted",
        "historical_gold_or_prediction_values_used", "sample_or_component_ids_persisted",
        "test_accessed", "model_or_checkpoint_accessed", "model_forward_executed",
    )
    if access.get("label_bearing_containers_accessed") is not True or any(access.get(key) is not False for key in required_false):
        raise ValueError("EXP-065 access attestation drift")
    checks = [
        "config_identity", "source_file_identity", "source_npz_schema", "selection_records",
        "exp064_prerequisite", "failed_attempt_lineage", "safe_public_source_aliases",
        "output_modes", "append_only_terminal_absence", "run_state", "public_privacy",
        "frozen_sources", "validation_row_schema", "sample_uniqueness",
        "three_way_sample_alignment", "three_way_component_alignment", "dense_group_mapping",
        "projection_exact_bytes", "projection_exact_schema", "fixed_32_ordinals",
        "selected_epoch_minus_one", "probability_shape_dtype_range", "replay_exact_schema",
        "replay_exact_content", "private_manifest_replay", "public_private_cross_hash",
        "label_values_not_used", "label_values_not_persisted", "test_access_false",
        "no_metrics_or_model_forward",
    ]
    result = {
        "schema_version": "exp-065-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Passed",
        "verified_at_utc": utc_now(),
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "contract": {
            "projection_row_count": 720,
            "replay_row_count": 32,
            "m1_selected_epoch": 4,
            "m3_selected_epoch": 2,
        },
        "bundle_artifacts": output_records,
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
    if public_sensitive_paths(result):
        raise ValueError("EXP-065 verification public privacy drift")
    summary = (
        "# EXP-065 Verification Summary\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(checks)}/{len(checks)}`\n"
        "- Projection rows: `720`\n"
        "- Replay rows: `32`\n"
        "- Label-bearing containers accessed: `true`\n"
        "- Label values used/persisted: `false/false`\n"
        "- Test access: `false`\n"
        "- Classification metrics: `none`\n\n"
        f"Claim boundary: {CLAIM_BOUNDARY}\n"
    ).encode("utf-8")
    _create(PUBLIC_DIR / "VERIFICATION-SUMMARY.md", summary)
    _create(PUBLIC_DIR / "verification.json", canonical_json_bytes(result))
    completion = {
        "schema_version": "exp-065-projection-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "run": record(PUBLIC_DIR / "run.json"),
        "verification": record(PUBLIC_DIR / "verification.json"),
        "private_artifacts": output_records,
        "label_values_used": False,
        "label_values_persisted": False,
        "test_accessed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _create(PUBLIC_DIR / "projection-complete.json", canonical_json_bytes(completion))
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
                "schema_version": "exp-065-verification-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "attempt_id": ATTEMPT_ID,
                "status": "Failed",
                "verified_at_utc": utc_now(),
                "passed_count": 0,
                "failed_count": 1,
                "error_type": type(error).__name__,
                "label_values_persisted": False,
                "test_accessed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
            _create(PUBLIC_DIR / "verification.json", canonical_json_bytes(failed))
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

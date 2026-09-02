#!/usr/bin/env python3
"""EXP-075: one-shot, post-diagnostic degenerate-aware geometry producer."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
EXPERIMENT_ID = "EXP-075"
RUN_ID = "exp-075-degenerate-aware-geometry"
ATTEMPT_ID = "attempt-1"
ALL_POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
CONFIRMATION_POINTS = ("H19", "H27", "HF")
FOLDS = (0, 1, 2, 3, 4)
CONDITION_ORDER = tuple([f"s42:{p}" for p in ALL_POINTS] + [f"s43:{p}" for p in CONFIRMATION_POINTS] + [f"s44:{p}" for p in CONFIRMATION_POINTS])
SANITY_CONDITIONS = frozenset([f"s42:{p}" for p in ("H-1", "H7", "H15", "H19")] + ["s43:H19", "s44:H19"])
NPZ_ORDER = ("heldout_ordinals", "cosine_distance", "relative_l2_distance", "max_abs_difference")
NPZ_MEMBERS = {
    "heldout_ordinals": {"shape": [5, 672], "dtype": "<i4"},
    "cosine_distance": {"shape": [15, 3360], "dtype": "<f8"},
    "relative_l2_distance": {"shape": [15, 3360], "dtype": "<f8"},
    "max_abs_difference": {"shape": [15, 5], "dtype": "<f8"},
}
METHOD = {"zero_cka_policy": "null_only_exact_zero_centered_variance", "fold_aggregation": "all_five_or_null", "spearman": "fixed_nine_or_null", "post_diagnostic": True}
RESOURCES = {"max_wall_seconds": 7200, "max_peak_rss_bytes": 4294967296, "max_private_bytes": 67108864, "min_free_bytes": 1073741824}
PARENT_RECORD = {"path": "experiments/stack-overflow-emotion-gold/phase-b-representation/configs/exp-071-representation-drift-formal-attempt-1.json", "bytes": 30400, "mode": "0644", "sha256": "0709c963f88242a706784f92d5033fe08eb46fb752d7e59e96607bc259d0ae35"}
HELPER_PATH = MODULE_DIR / "verify_exp071_drift.py"
HELPER_BYTES = 121050
HELPER_SHA256 = "0a6e0e03a2f14212bc2bf0d3a1ecc3d9cf4eec1ee8a3a9f7b44cd3ca83a0bbd2"
IMPLEMENTATION_PATHS = {"runner": "experiments/stack-overflow-emotion-gold/phase-b-representation/run_exp075_geometry.py", "verifier": "experiments/stack-overflow-emotion-gold/phase-b-representation/verify_exp075_geometry.py", "tests": "experiments/stack-overflow-emotion-gold/phase-b-representation/tests/test_exp075_geometry.py"}
OUTPUTS = {"public_root": "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/exp-075-degenerate-aware-geometry/attempt-1", "private_root": "experiments/stack-overflow-emotion-gold/phase-b-representation/private/exp-075-degenerate-aware-geometry/attempt-1"}
PROTOCOL_PATH = "experiments/stack-overflow-emotion-gold/protocols/exp-075-degenerate-aware-geometry.md"
ACCESS = {"source_file_bytes_hashed": True, "representation_values_read": True, "outer_heldout_only": True, "row_contract_value_members_read": ["ordinal", "fold_id"], "component_code_values_read": False, "probe_metric_values_read": True, "private_probe_artifacts_read": False, "public_fold_manifest_parsed": False, "labels_read": False, "sample_component_ids_read": False, "train_text_read": False, "model_loaded": False, "forward_executed": False, "validation_accessed": False, "test_accessed": False, "source_mutated": False}
CLAIM_BOUNDARY = "Post-diagnostic same-train outer-heldout geometry under the frozen last-token, point and seed contracts. Exact zero-centered-variance CKA and dependent aggregates remain undefined; no original EXP-071 success, exact onset, significance, causal mechanism, independent-data generalization or human-emotion claim."


def _load_helpers() -> Any:
    info = HELPER_PATH.stat()
    payload = HELPER_PATH.read_bytes()
    if HELPER_PATH.is_symlink() or not HELPER_PATH.is_file() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o644 or len(payload) != HELPER_BYTES or hashlib.sha256(payload).hexdigest() != HELPER_SHA256:
        raise ValueError("pinned_helper_identity_drift")
    spec = importlib.util.spec_from_file_location("exp075_pinned_io_helpers", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAFE = _load_helpers()
canonical_json_bytes = SAFE.canonical_json_bytes
artifact = SAFE.artifact
require_record = SAFE.require_record


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _validated_pair(x: Any, z: Any) -> tuple[Any, Any, Any, Any]:
    import numpy as np
    x, z = np.ascontiguousarray(x, dtype=np.float64), np.ascontiguousarray(z, dtype=np.float64)
    if x.ndim != 2 or x.shape != z.shape or x.shape[0] < 2 or x.shape[1] < 1 or not np.all(np.isfinite(x)) or not np.all(np.isfinite(z)):
        raise ValueError("invalid_geometry_input")
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        nx, nz = np.linalg.norm(x, axis=1), np.linalg.norm(z, axis=1)
    if not np.all(np.isfinite(nx)) or not np.all(np.isfinite(nz)) or np.any(nx == 0) or np.any(nz == 0):
        raise ValueError("zero_or_nonfinite_row_norm")
    return x, z, nx, nz


def linear_cka_nullable(x: Any, z: Any) -> tuple[float | None, str | None]:
    import numpy as np
    x, z, _, _ = _validated_pair(x, z)
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        xc = x - np.mean(x, axis=0, dtype=np.float64)
        zc = z - np.mean(z, axis=0, dtype=np.float64)
        k, l = xc @ xc.T, zc @ zc.T
        norm_x = float(np.sum(k * k, dtype=np.float64))
        norm_z = float(np.sum(l * l, dtype=np.float64))
    degenerate = []
    for centered, gram, norm in ((xc, k, norm_x), (zc, l, norm_z)):
        if not np.all(np.isfinite(centered)) or not np.all(np.isfinite(gram)) or not math.isfinite(norm) or norm < 0:
            raise ValueError("nonfinite_or_invalid_cka_intermediate")
        centered_zero, gram_zero = bool(np.all(centered == 0)), bool(np.all(gram == 0))
        if norm == 0 and not (centered_zero and gram_zero):
            raise ValueError("zero_norm_without_exact_zero_centered_variance")
        if norm > 0 and (centered_zero or gram_zero):
            raise ValueError("inconsistent_centered_variance")
        degenerate.append(centered_zero and gram_zero and norm == 0)
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        product = norm_x * norm_z
        denominator = float(np.sqrt(product))
    if not math.isfinite(product) or not math.isfinite(denominator):
        raise ValueError("nonfinite_cka_denominator")
    if any(degenerate):
        if product != 0 or denominator != 0:
            raise ValueError("inconsistent_zero_cka_denominator")
        return None, "zero_centered_variance"
    if product <= 0 or denominator <= 0:
        raise ValueError("positive_norm_denominator_underflow")
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        numerator = float(np.sum(k * l, dtype=np.float64))
        value = numerator / denominator
    if not math.isfinite(numerator) or not math.isfinite(value) or value < -1e-12 or value > 1 + 1e-12:
        raise ValueError("cka_numeric_range_violation")
    return float(np.clip(value, 0, 1)), None


def compute_geometry_pair(x: Any, z: Any) -> tuple[Any, Any, float | None, float, str | None]:
    import numpy as np
    x, z, nx, nz = _validated_pair(x, z)
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        raw = np.einsum("ij,ij->i", x, z) / (nx * nz)
        relative = np.linalg.norm(z - x, axis=1) / nx
        maximum = float(np.max(np.abs(z - x)))
    if not np.all(np.isfinite(raw)) or np.any(raw < -1 - 1e-12) or np.any(raw > 1 + 1e-12) or not np.all(np.isfinite(relative)) or not math.isfinite(maximum):
        raise ValueError("distance_numeric_violation")
    cka, reason = linear_cka_nullable(x, z)
    return np.ascontiguousarray(1 - np.clip(raw, -1, 1), dtype="<f8"), np.ascontiguousarray(relative, dtype="<f8"), cka, maximum, reason


def distance_statistics(values: Any) -> dict[str, float]:
    import numpy as np
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("invalid_distance_vector")
    median, p90, p95 = np.percentile(values, [50, 90, 95], method="linear")
    return {"mean": float(np.mean(values)), "median": float(median), "p90": float(p90), "p95": float(p95)}


def aggregate_cka(values: Sequence[float | None], reasons: Sequence[str | None]) -> dict[str, Any]:
    import numpy as np
    if len(values) != 5 or len(reasons) != 5 or any((value is None) != (reason == "zero_centered_variance") for value, reason in zip(values, reasons)) or any(value is not None and (not math.isfinite(value) or reason is not None) for value, reason in zip(values, reasons)):
        raise ValueError("nullable_cka_schema_drift")
    count = sum(value is not None for value in values)
    return {"per_fold": list(values), "reason_by_fold": list(reasons), "mean": float(np.mean(values)) if count == 5 else None, "sample_sd": float(np.std(values, ddof=1)) if count == 5 else None, "n_defined": count, "reason": None if count == 5 else "undefined_fold_cka"}


def average_ranks(values: Any) -> Any:
    import numpy as np
    values = np.asarray(values, dtype=np.float64)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and values[order[stop]] == values[order[start]]:
            stop += 1
        ranks[order[start:stop]] = (start + stop - 1) / 2 + 1
        start = stop
    return ranks


def fixed_nine_spearman(means: Sequence[float | None], ap5: Sequence[float]) -> dict[str, Any]:
    import numpy as np
    if len(means) != 9 or len(ap5) != 9 or not np.all(np.isfinite(ap5)):
        raise ValueError("fixed_nine_spearman_shape_drift")
    if any(value is None for value in means):
        return {"rho": None, "reason": "undefined_cka_input"}
    if not np.all(np.isfinite(means)):
        raise ValueError("nonfinite_spearman_input")
    x, y = average_ranks(1 - np.asarray(means)), average_ranks(ap5)
    x, y = x - np.mean(x), y - np.mean(y)
    denominator = float(np.linalg.norm(x) * np.linalg.norm(y))
    if denominator == 0:
        return {"rho": None, "reason": "constant_vector"}
    rho = float(np.dot(x, y) / denominator)
    if not math.isfinite(rho) or not -1 - 1e-12 <= rho <= 1 + 1e-12:
        raise ValueError("spearman_numeric_violation")
    return {"rho": float(np.clip(rho, -1, 1)), "reason": None}


def build_results(arrays: Mapping[str, Any], cka: Sequence[Sequence[float | None]], reasons: Sequence[Sequence[str | None]], ap5: Sequence[float]) -> dict[str, Any]:
    import numpy as np
    if len(cka) != 15 or len(reasons) != 15:
        raise ValueError("condition_count_drift")
    conditions, sanity = {}, {}
    for index, condition in enumerate(CONDITION_ORDER):
        per_fold = []
        for fold in FOLDS:
            span = slice(fold * 672, (fold + 1) * 672)
            per_fold.append({"fold": fold, **{name: distance_statistics(arrays[name][index, span]) for name in ("cosine_distance", "relative_l2_distance")}})
        maxima = [float(value) for value in arrays["max_abs_difference"][index]]
        if len(maxima) != 5 or any(not math.isfinite(value) or value < 0 for value in maxima):
            raise ValueError("max_abs_difference_drift")
        maximum, applies = max(maxima), condition in SANITY_CONDITIONS
        passed = maximum <= 1e-5 if applies else None
        if applies and not passed:
            raise ValueError("pre_lora_sanity_failure")
        conditions[condition] = {
            "per_fold_distance_statistics": per_fold,
            "pooled_distance_statistics": {name: distance_statistics(arrays[name][index]) for name in ("cosine_distance", "relative_l2_distance")},
            "linear_cka": aggregate_cka(cka[index], reasons[index]),
            "max_abs_difference": {"per_fold": maxima, "maximum": maximum, "sanity_gate_applies": applies, "sanity_gate_passed": passed},
        }
        if applies:
            sanity[condition] = {"per_fold": maxima, "maximum": maximum, "passed": bool(passed)}
    means = [conditions[f"s42:{point}"]["linear_cka"]["mean"] for point in ALL_POINTS]
    return {"condition_order": list(CONDITION_ORDER), "conditions": conditions,
            "pre_lora_sanity": {"tolerance": 1e-5, "conditions": sanity, "passed": True},
            "seed42_spearman": {"point_order": list(ALL_POINTS), "x": "1-five_fold_mean_linear_cka", "y": "verified_exp070_main_delta_five_label_macro_ap", "n": 9, **fixed_nine_spearman(means, ap5)}}


def validate_config(config: Mapping[str, Any]) -> None:
    if set(config) != {"experiment_id", "parent_config", "protocol", "implementation", "outputs", "resources", "environment", "method"}:
        raise ValueError("config_schema_drift")
    if config["experiment_id"] != EXPERIMENT_ID or config["parent_config"] != PARENT_RECORD or config["method"] != METHOD or config["resources"] != RESOURCES or config["environment"] != SAFE.ENVIRONMENT or config["outputs"] != OUTPUTS:
        raise ValueError("frozen_config_contract_drift")
    if set(config["implementation"]) != set(IMPLEMENTATION_PATHS):
        raise ValueError("implementation_inventory_drift")
    records = {"protocol": config["protocol"], **config["implementation"]}
    for name, record in records.items():
        if set(record) != {"path", "bytes", "mode", "sha256"} or record["path"] != ({"protocol": PROTOCOL_PATH, **IMPLEMENTATION_PATHS}[name]) or type(record["bytes"]) is not int or record["bytes"] <= 0 or record["mode"] != "0644" or not re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"])):
            raise ValueError("artifact_record_drift")


def load_config(path: Path) -> dict[str, Any]:
    config = SAFE.strict_json(path.resolve())
    validate_config(config)
    return config


def require_frozen_files(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    config_path = config_path.resolve()
    if SAFE.resolve_project(config_path.relative_to(PROJECT_ROOT).as_posix()) != config_path:
        raise ValueError("config_location_drift")
    for record in (config["parent_config"], config["protocol"], *config["implementation"].values()):
        require_record(record)
    if require_record(config["implementation"]["runner"]).resolve() != Path(__file__).resolve():
        raise ValueError("runner_identity_points_elsewhere")
    parent = SAFE.strict_json(require_record(config["parent_config"]))
    if digest(parent["source"]) != "8f7bc1836021053d0ffd48a620170996ed72475f54c57034ca2591dd515dffcf" or digest(parent["method"]) != "f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210":
        raise ValueError("parent_contract_drift")
    SAFE.require_environment(config)
    return parent


def _peak_rss_bytes() -> int:
    return SAFE._peak_rss_bytes()


def budget_check(started: float) -> None:
    if time.monotonic() - started > RESOURCES["max_wall_seconds"] or _peak_rss_bytes() > RESOURCES["max_peak_rss_bytes"]:
        raise RuntimeError("resource_ceiling_exceeded")


@contextmanager
def producer_lock() -> Any:
    with SAFE._file_mutex(MODULE_DIR / "private/locks/heavy-research-workload.lock", "heavy research"):
        with SAFE._file_mutex(MODULE_DIR / "private/locks/exp075-geometry.lock", "EXP-075 geometry"):
            yield


def compute_geometry(parent: Mapping[str, Any], started: float, progress: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    import numpy as np
    ordinal, _fold_ids, rows_by_fold = SAFE._load_row_contract_values(parent)
    matrices, points = SAFE._matrix_map(parent), SAFE._matrix_point_indices(parent)
    arrays = {name: np.empty(record["shape"], dtype=record["dtype"]) for name, record in NPZ_MEMBERS.items()}
    arrays["heldout_ordinals"][:] = np.stack([ordinal[rows] for rows in rows_by_fold])
    cka, reasons = [], []
    for index, condition in enumerate(CONDITION_ORDER):
        seed, point = condition.split(":", 1)
        fold_cka, fold_reasons = [], []
        for fold, rows in enumerate(rows_by_fold):
            budget_check(started)
            worker = f"m3-{seed}-f{fold}"
            x = np.ascontiguousarray(matrices["base"][rows, points["base"][point], :], dtype=np.float64)
            z = np.ascontiguousarray(matrices[worker][rows, points[worker][point], :], dtype=np.float64)
            if x.shape != (672, 2560) or z.shape != x.shape:
                raise ValueError("heldout_slice_shape_drift")
            cosine, relative, value, maximum, reason = compute_geometry_pair(x, z)
            span = slice(fold * 672, (fold + 1) * 672)
            arrays["cosine_distance"][index, span] = cosine
            arrays["relative_l2_distance"][index, span] = relative
            arrays["max_abs_difference"][index, fold] = maximum
            fold_cka.append(value)
            fold_reasons.append(reason)
            progress({"event": "pair_complete", "condition": condition, "fold": fold, "cka_defined": value is not None})
            del x, z, cosine, relative
        cka.append(fold_cka)
        reasons.append(fold_reasons)
    ap5 = SAFE._load_probe_deltas(parent)
    budget_check(started)
    return arrays, build_results(arrays, cka, reasons, ap5)


def _atomic_once(path: Path, writer: Any, *, mode: int) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir() or os.path.lexists(path):
        raise FileExistsError("unsafe_or_existing_output")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def create_json_once(path: Path, value: Any, *, private: bool = False) -> None:
    payload = canonical_json_bytes(value)
    _atomic_once(path, lambda handle: handle.write(payload), mode=0o600 if private else 0o644)


def save_geometry_once(path: Path, arrays: Mapping[str, Any]) -> None:
    import numpy as np
    if list(arrays) != list(NPZ_ORDER):
        raise ValueError("geometry_member_order_drift")
    for name, record in NPZ_MEMBERS.items():
        value = arrays[name]
        if list(value.shape) != record["shape"] or value.dtype.str != record["dtype"] or not value.flags.c_contiguous or not np.all(np.isfinite(value)):
            raise ValueError("geometry_array_contract_drift")
    _atomic_once(path, lambda handle: np.savez(handle, **arrays), mode=0o600)


def validate_public_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or not SAFE.public_privacy_ok(value):
        raise ValueError("public_privacy_drift")
    def walk(item: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                walk(child, path + (str(key),))
        elif isinstance(item, list):
            if len(item) >= 672:
                raise ValueError("public_rowwise_vector")
            for index, child in enumerate(item):
                walk(child, path + (str(index),))
        elif isinstance(item, str) and ("/Users/" in item or "phase-b-representation/private/" in item):
            if path != ("execution", "command", "0") or item != SAFE.ENVIRONMENT["python_executable"]:
                raise ValueError("private_path_disclosure")
    walk(value)


def require_inventory(root: Path, names: Sequence[str], *, private: bool) -> None:
    if SAFE.require_safe_root(root, private=private) != set(names):
        raise ValueError("output_inventory_drift")
    SAFE.require_file_modes(root, names, private=private)


def _create_root(root: Path, *, private: bool) -> None:
    if os.path.lexists(root):
        raise FileExistsError("attempt_root_exists")
    mode = 0o700 if private else 0o755
    missing, cursor = [], root
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    if cursor.is_symlink() or not cursor.is_dir():
        raise ValueError("unsafe_root_parent")
    for directory in reversed(missing):
        directory.mkdir(mode=mode)
        directory.chmod(mode)


def _execution(config_path: Path, config: Mapping[str, Any], started: str, ended: str) -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True, capture_output=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True, capture_output=True, check=True).stdout)
    return {"started_at_utc": started, "ended_at_utc": ended,
            "command": [config["environment"]["python_executable"], IMPLEMENTATION_PATHS["runner"], "--config", config_path.relative_to(PROJECT_ROOT).as_posix(), "run"],
            "cwd": ".", "git_commit": commit, "git_dirty": dirty}


def run(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    started, started_utc = time.monotonic(), datetime.now(timezone.utc).isoformat()
    config = load_config(config_path)
    config_record = artifact(config_path)
    with producer_lock():
        parent = require_frozen_files(config_path, config)
        SAFE.require_parent_statuses(parent, read_probe_values=False)
        before = SAFE.source_identity_snapshot(parent)
        SAFE.matrix_headers(parent)
        SAFE.row_contract_headers(parent)
        budget_check(started)
        public = SAFE.resolve_project(config["outputs"]["public_root"], must_exist=False)
        private = SAFE.resolve_project(config["outputs"]["private_root"], must_exist=False)
        if os.path.lexists(public) or os.path.lexists(private):
            raise FileExistsError("attempt_roots_must_be_fresh")
        if shutil.disk_usage(PROJECT_ROOT).free < RESOURCES["min_free_bytes"]:
            raise RuntimeError("insufficient_free_disk")
        _create_root(public, private=False)
        _create_root(private, private=True)
        log_path = public / "stdout.log"
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb") as log:
                os.fchmod(log.fileno(), 0o644)
                def progress(event: Mapping[str, Any]) -> None:
                    validate_public_payload(event)
                    log.write(canonical_json_bytes(event))
                    log.flush()
                    os.fsync(log.fileno())
                progress({"event": "started", "experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID})
                arrays, results = compute_geometry(parent, started, progress)
                after = SAFE.source_identity_snapshot(parent)
                if after != before or artifact(config_path) != config_record:
                    raise ValueError("source_or_config_mutated")
                require_frozen_files(config_path, config)
                budget_check(started)
                save_geometry_once(private / "geometry.npz", arrays)
                manifest = {"schema_version": "exp-075-geometry-manifest-v1", "experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID,
                            "config": config_record, "parent_config": config["parent_config"], "method": config["method"], "source_before": before, "source_after": after,
                            "npz": artifact(private / "geometry.npz", logical_name="geometry.npz"), "member_order": list(NPZ_ORDER), "members": NPZ_MEMBERS,
                            "results_sha256": digest(results), "access": ACCESS}
                create_json_once(private / "geometry-manifest.json", manifest, private=True)
                private_bytes = sum(path.stat().st_size for path in private.iterdir())
                if private_bytes > RESOURCES["max_private_bytes"]:
                    raise RuntimeError("private_output_ceiling_exceeded")
                progress({"event": "finished", "status": "Analyzed", "pairs": 75})
            execution = _execution(config_path, config, started_utc, datetime.now(timezone.utc).isoformat())
            budget_check(started)
            payload = {"schema_version": "exp-075-geometry-run-v1", "experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID,
                       "tier": "Major", "rq_id": "RQ-S4.2", "stage": "formal-analysis", "status": "Analyzed", "config": config_record, "protocol": config["protocol"],
                       "parent_config": config["parent_config"], "method": config["method"], "source_snapshot_sha256": before["sha256"], "results": results,
                       "artifacts": {"geometry_private": artifact(private / "geometry.npz", logical_name="geometry.npz"), "manifest_private": artifact(private / "geometry-manifest.json", logical_name="geometry-manifest.json"), "stdout": artifact(log_path)},
                       "resources": {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": _peak_rss_bytes(), "private_bytes": private_bytes, "api_cost_usd": 0.0},
                       "execution": execution, "access": ACCESS, "claim_boundary": CLAIM_BOUNDARY}
            validate_public_payload(payload)
            require_inventory(public, ["stdout.log"], private=False)
            require_inventory(private, ["geometry.npz", "geometry-manifest.json"], private=True)
            create_json_once(public / "run.json", payload)
            require_inventory(public, ["stdout.log", "run.json"], private=False)
            return payload
        except BaseException as error:
            failure = {"schema_version": "exp-075-geometry-failure-v1", "experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID, "status": "Failed", "retry_authorized": False, "error_type": type(error).__name__}
            if not os.path.lexists(public / "failure.json"):
                create_json_once(public / "failure.json", failure)
            raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("stage", choices=["run"])
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args.config.resolve())
    except BaseException as error:
        print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": "Failed", "error_type": type(error).__name__, "retry_authorized": False}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

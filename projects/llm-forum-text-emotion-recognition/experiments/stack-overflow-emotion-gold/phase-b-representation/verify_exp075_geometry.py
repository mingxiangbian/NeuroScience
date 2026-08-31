#!/usr/bin/env python3
"""Independently recompute EXP-075 geometry and seal one verification result."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import stat
import sys
import time
from typing import Any, Iterator, Mapping, Sequence


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
EXPERIMENT_ID = "EXP-075"
RUN_ID = "exp-075-degenerate-aware-geometry"
ATTEMPT_ID = "attempt-1"
PARENT_RECORD = {
    "path": "experiments/stack-overflow-emotion-gold/phase-b-representation/configs/exp-071-representation-drift-formal-attempt-1.json",
    "bytes": 30400, "mode": "0644",
    "sha256": "0709c963f88242a706784f92d5033fe08eb46fb752d7e59e96607bc259d0ae35",
}
PROTOCOL_PATH = "experiments/stack-overflow-emotion-gold/protocols/exp-075-degenerate-aware-geometry.md"
IMPLEMENTATION_PATHS = {
    "runner": "experiments/stack-overflow-emotion-gold/phase-b-representation/run_exp075_geometry.py",
    "verifier": "experiments/stack-overflow-emotion-gold/phase-b-representation/verify_exp075_geometry.py",
    "tests": "experiments/stack-overflow-emotion-gold/phase-b-representation/tests/test_exp075_geometry.py",
}
OUTPUTS = {
    "public_root": "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/exp-075-degenerate-aware-geometry/attempt-1",
    "private_root": "experiments/stack-overflow-emotion-gold/phase-b-representation/private/exp-075-degenerate-aware-geometry/attempt-1",
}
METHOD = {
    "zero_cka_policy": "null_only_exact_zero_centered_variance",
    "fold_aggregation": "all_five_or_null", "spearman": "fixed_nine_or_null", "post_diagnostic": True,
}
RESOURCES = {"max_wall_seconds": 7200, "max_peak_rss_bytes": 4294967296,
             "max_private_bytes": 67108864, "min_free_bytes": 1073741824}
ALL_POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
FOLDS = (0, 1, 2, 3, 4)
CONDITION_ORDER = tuple([f"s42:{p}" for p in ALL_POINTS] + [f"s{s}:{p}" for s in (43, 44) for p in ("H19", "H27", "HF")])
SANITY_CONDITIONS = frozenset([f"s42:{p}" for p in ("H-1", "H7", "H15", "H19")] + ["s43:H19", "s44:H19"])
MEMBERS = {
    "heldout_ordinals": {"shape": [5, 672], "dtype": "<i4"},
    "cosine_distance": {"shape": [15, 3360], "dtype": "<f8"},
    "relative_l2_distance": {"shape": [15, 3360], "dtype": "<f8"},
    "max_abs_difference": {"shape": [15, 5], "dtype": "<f8"},
}
ACCESS = {
    "source_file_bytes_hashed": True, "representation_values_read": True, "outer_heldout_only": True,
    "row_contract_value_members_read": ["ordinal", "fold_id"], "component_code_values_read": False,
    "probe_metric_values_read": True, "private_probe_artifacts_read": False,
    "public_fold_manifest_parsed": False, "labels_read": False, "sample_component_ids_read": False,
    "train_text_read": False, "model_loaded": False, "forward_executed": False,
    "validation_accessed": False, "test_accessed": False, "source_mutated": False,
}
CLAIM_BOUNDARY = "Post-diagnostic same-train outer-heldout geometry under the frozen last-token, point and seed contracts. Exact zero-centered-variance CKA and dependent aggregates remain undefined; no original EXP-071 success, exact onset, significance, causal mechanism, independent-data generalization or human-emotion claim."


def _pin(path: Path, record: Mapping[str, Any]) -> None:
    cursor = path
    while cursor != PROJECT_ROOT:
        if cursor.is_symlink():
            raise ValueError("Symlink in pinned artifact path")
        if cursor == cursor.parent:
            raise ValueError("Pinned artifact is outside project")
        cursor = cursor.parent
    if path.is_symlink() or not path.is_file():
        raise ValueError("Unsafe pinned artifact")
    info = path.stat()
    if info.st_nlink != 1 or info.st_size != record["bytes"] or f"{stat.S_IMODE(info.st_mode):04o}" != record["mode"] or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("Pinned artifact identity drift")


def _load_helpers() -> Any:
    parent_path = PROJECT_ROOT / PARENT_RECORD["path"]
    _pin(parent_path, PARENT_RECORD)
    parent = json.loads(parent_path.read_bytes())
    record = parent["implementation"]["verifier"]
    path = PROJECT_ROOT / record["path"]
    if path != MODULE_DIR / "verify_exp071_drift.py":
        raise ValueError("Independent helper path drift")
    _pin(path, record)
    spec = importlib.util.spec_from_file_location("exp075_frozen_independent_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import pinned independent helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAFE = _load_helpers()
canonical_json_bytes = SAFE.canonical_json_bytes
artifact = SAFE.artifact
require_record = SAFE.require_record
strict_json = SAFE.strict_json
distance_statistics = SAFE.distance_statistics


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def linear_cka_nullable(x: Any, z: Any) -> tuple[float | None, str | None]:
    import numpy as np

    x, z = np.ascontiguousarray(x, dtype=np.float64), np.ascontiguousarray(z, dtype=np.float64)
    if x.ndim != 2 or x.shape != z.shape or x.shape[0] < 2 or x.shape[1] < 1 or not np.all(np.isfinite(x)) or not np.all(np.isfinite(z)):
        raise ValueError("Invalid CKA input")
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        raw_norms = (np.linalg.norm(x, axis=1), np.linalg.norm(z, axis=1))
    if any(not np.all(np.isfinite(v)) or np.any(v == 0.0) for v in raw_norms):
        raise ValueError("Zero or non-finite raw CKA input norm")
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        xc, zc = x - np.mean(x, axis=0, dtype=np.float64), z - np.mean(z, axis=0, dtype=np.float64)
        k, l = xc @ xc.T, zc @ zc.T
        nx, nz = float(np.sum(k * k, dtype=np.float64)), float(np.sum(l * l, dtype=np.float64))
        denominator = float(np.sqrt(nx * nz))
    if not all(np.all(np.isfinite(v)) for v in (xc, zc, k, l)) or not all(math.isfinite(v) and v >= 0.0 for v in (nx, nz, denominator)):
        raise ValueError("Non-finite or negative CKA intermediate")
    zero_x, zero_z = bool(np.all(xc == 0.0)), bool(np.all(zc == 0.0))
    for centered_zero, gram, norm in ((zero_x, k, nx), (zero_z, l, nz)):
        if centered_zero:
            if not np.all(gram == 0.0) or norm != 0.0:
                raise ValueError("Inconsistent exact-zero CKA domain")
        elif np.all(gram == 0.0) or norm == 0.0:
            raise ValueError("Nonzero centered CKA underflow")
    if zero_x or zero_z:
        if denominator != 0.0:
            raise ValueError("Inconsistent zero-domain denominator")
        return None, "zero_centered_variance"
    if denominator == 0.0:
        raise ValueError("Positive CKA norm product underflow")
    numerator = float(np.sum(k * l, dtype=np.float64))
    value = numerator / denominator
    if not math.isfinite(numerator) or not math.isfinite(value) or not -1e-12 <= value <= 1.0 + 1e-12:
        raise ValueError("CKA numeric range failure")
    return float(np.clip(value, 0.0, 1.0)), None


def compute_geometry_pair(x: Any, z: Any) -> tuple[Any, Any, float | None, float, str | None]:
    import numpy as np

    x, z = np.ascontiguousarray(x, dtype=np.float64), np.ascontiguousarray(z, dtype=np.float64)
    if x.ndim != 2 or x.shape != z.shape or not np.all(np.isfinite(x)) or not np.all(np.isfinite(z)):
        raise ValueError("Invalid geometry pair")
    nx, nz = np.linalg.norm(x, axis=1), np.linalg.norm(z, axis=1)
    if not np.all(np.isfinite(nx)) or not np.all(np.isfinite(nz)) or np.any(nx == 0) or np.any(nz == 0):
        raise ValueError("Zero or non-finite row norm")
    raw = np.einsum("ij,ij->i", x, z) / (nx * nz)
    if not np.all(np.isfinite(raw)) or np.any(raw < -1 - 1e-12) or np.any(raw > 1 + 1e-12):
        raise ValueError("Cosine range failure")
    cosine = 1.0 - np.clip(raw, -1.0, 1.0)
    difference = z - x
    relative = np.linalg.norm(difference, axis=1) / nx
    maximum = float(np.max(np.abs(difference)))
    if not np.all(np.isfinite(relative)) or not math.isfinite(maximum):
        raise ValueError("Non-finite distance")
    cka, reason = linear_cka_nullable(x, z)
    return cosine, relative, cka, maximum, reason


def aggregate_cka(values: Sequence[float | None], reasons: Sequence[str | None]) -> dict[str, Any]:
    import numpy as np
    if len(values) != 5 or len(reasons) != 5 or any((v is None) != (r == "zero_centered_variance") or (v is not None and (r is not None or not math.isfinite(v))) for v, r in zip(values, reasons, strict=True)):
        raise ValueError("Nullable CKA domain binding drift")
    count = sum(v is not None for v in values)
    return {"per_fold": list(values), "reason_by_fold": list(reasons), "mean": float(np.mean(values)) if count == 5 else None, "sample_sd": float(np.std(values, ddof=1)) if count == 5 else None, "n_defined": count, "reason": None if count == 5 else "undefined_fold_cka"}


def fixed_nine_spearman(means: Sequence[float | None], ap5: Sequence[float]) -> dict[str, Any]:
    import numpy as np
    if len(means) != 9 or len(ap5) != 9 or not np.all(np.isfinite(ap5)):
        raise ValueError("Fixed-nine Spearman input drift")
    if any(value is None for value in means):
        return {"rho": None, "reason": "undefined_cka_input"}
    return SAFE.spearman_description([1.0 - value for value in means], ap5)


def build_results(arrays: Mapping[str, Any], cka: Sequence[Sequence[float | None]], reasons: Sequence[Sequence[str | None]], ap5: Sequence[float]) -> dict[str, Any]:
    import numpy as np

    if len(cka) != 15 or len(reasons) != 15 or len(ap5) != 9 or not np.all(np.isfinite(ap5)):
        raise ValueError("Geometry summary input drift")
    distance_shape = arrays["cosine_distance"].shape
    if len(distance_shape) != 2 or distance_shape[0] != 15 or distance_shape[1] == 0 or distance_shape[1] % 5 or arrays["relative_l2_distance"].shape != distance_shape or arrays["max_abs_difference"].shape != (15, 5):
        raise ValueError("Geometry summary array shape drift")
    if any(not np.all(np.isfinite(arrays[name])) for name in ("cosine_distance", "relative_l2_distance", "max_abs_difference")):
        raise ValueError("Non-finite geometry summary array")
    fold_size = distance_shape[1] // 5
    conditions, sanity = {}, {}
    for index, condition in enumerate(CONDITION_ORDER):
        values, missing = list(cka[index]), list(reasons[index])
        cka_summary = aggregate_cka(values, missing)
        per_fold = []
        for fold in FOLDS:
            span = slice(fold * fold_size, (fold + 1) * fold_size)
            per_fold.append({"fold": fold, "cosine_distance": distance_statistics(arrays["cosine_distance"][index, span]), "relative_l2_distance": distance_statistics(arrays["relative_l2_distance"][index, span])})
        maxima = arrays["max_abs_difference"][index]
        applies = condition in SANITY_CONDITIONS
        maximum = float(np.max(maxima))
        passed = maximum <= 1e-5 if applies else None
        if applies and not passed:
            raise ValueError("Pre-LoRA sanity failure")
        conditions[condition] = {
            "per_fold_distance_statistics": per_fold,
            "pooled_distance_statistics": {"cosine_distance": distance_statistics(arrays["cosine_distance"][index]), "relative_l2_distance": distance_statistics(arrays["relative_l2_distance"][index])},
            "linear_cka": cka_summary,
            "max_abs_difference": {"per_fold": [float(v) for v in maxima], "maximum": maximum, "sanity_gate_applies": applies, "sanity_gate_passed": passed},
        }
        if applies:
            sanity[condition] = {"per_fold": [float(v) for v in maxima], "maximum": maximum, "passed": bool(passed)}
    means = [conditions[f"s42:{point}"]["linear_cka"]["mean"] for point in ALL_POINTS]
    correlation = fixed_nine_spearman(means, ap5)
    return {"condition_order": list(CONDITION_ORDER), "conditions": conditions,
            "pre_lora_sanity": {"tolerance": 1e-5, "conditions": sanity, "passed": True},
            "seed42_spearman": {"point_order": list(ALL_POINTS), "x": "1-five_fold_mean_linear_cka", "y": "verified_exp070_main_delta_five_label_macro_ap", "n": 9, **correlation}}


def validate_config(config: Mapping[str, Any]) -> None:
    if set(config) != {"experiment_id", "parent_config", "protocol", "implementation", "outputs", "resources", "environment", "method"}:
        raise ValueError("EXP-075 config schema drift")
    if config["experiment_id"] != EXPERIMENT_ID or config["parent_config"] != PARENT_RECORD or config["method"] != METHOD or config["outputs"] != OUTPUTS or config["resources"] != RESOURCES or config["environment"] != SAFE.ENVIRONMENT:
        raise ValueError("EXP-075 frozen contract drift")
    if config["method"]["post_diagnostic"] is not True or any(type(value) is not int for value in config["resources"].values()):
        raise ValueError("EXP-075 frozen contract type drift")
    if set(config["protocol"]) != {"path", "bytes", "mode", "sha256"} or config["protocol"]["path"] != PROTOCOL_PATH:
        raise ValueError("EXP-075 protocol identity drift")
    if set(config["implementation"]) != set(IMPLEMENTATION_PATHS):
        raise ValueError("EXP-075 implementation inventory drift")
    for name, expected_path in IMPLEMENTATION_PATHS.items():
        record = config["implementation"][name]
        if set(record) != {"path", "bytes", "mode", "sha256"} or record["path"] != expected_path or type(record["bytes"]) is not int or record["bytes"] <= 0 or record["mode"] != "0644" or not re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"])):
            raise ValueError("EXP-075 implementation record drift")


def load_config(path: Path) -> dict[str, Any]:
    value = strict_json(path.resolve())
    validate_config(value)
    return value


def require_frozen_files(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    for record in (config["parent_config"], config["protocol"], *config["implementation"].values()):
        require_record(record)
    if require_record(config["implementation"]["verifier"]).resolve() != Path(__file__).resolve():
        raise ValueError("EXP-075 verifier identity points elsewhere")
    parent = strict_json(require_record(config["parent_config"]))
    if digest(parent["source"]) != "8f7bc1836021053d0ffd48a620170996ed72475f54c57034ca2591dd515dffcf" or digest(parent["method"]) != "f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210":
        raise ValueError("EXP-075 parent source or method drift")
    SAFE.require_environment(config)
    return parent


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def budget_check(started: float) -> None:
    if time.monotonic() - started > RESOURCES["max_wall_seconds"] or _peak_rss_bytes() > RESOURCES["max_peak_rss_bytes"]:
        raise RuntimeError("EXP-075 verifier resource ceiling exceeded")


@contextmanager
def verification_lock() -> Iterator[None]:
    with SAFE._file_mutex(MODULE_DIR / "private/locks/heavy-research-workload.lock", "heavy research"):
        with SAFE._file_mutex(MODULE_DIR / "private/locks/exp075-geometry.lock", "EXP-075 geometry"):
            yield


def recompute_geometry(parent: Mapping[str, Any], started: float) -> tuple[dict[str, Any], dict[str, Any]]:
    import numpy as np

    ordinal, _fold_ids, rows_by_fold = SAFE._load_row_contract_values(parent)
    matrices, point_indices = SAFE._matrix_map(parent), SAFE._matrix_point_indices(parent)
    arrays = {name: np.empty(record["shape"], dtype=record["dtype"]) for name, record in MEMBERS.items()}
    arrays["heldout_ordinals"][:] = np.stack([ordinal[rows] for rows in rows_by_fold])
    cka, reasons = [], []
    for condition_index, condition in enumerate(CONDITION_ORDER):
        seed, point = condition.split(":", 1)
        fold_cka, fold_reasons = [], []
        for fold, rows in enumerate(rows_by_fold):
            budget_check(started)
            worker = f"m3-{seed}-f{fold}"
            x = np.ascontiguousarray(matrices["base"][rows, point_indices["base"][point], :], dtype=np.float64)
            z = np.ascontiguousarray(matrices[worker][rows, point_indices[worker][point], :], dtype=np.float64)
            if x.shape != (672, 2560) or z.shape != x.shape:
                raise ValueError("EXP-075 heldout slice shape drift")
            cosine, relative, value, maximum, reason = compute_geometry_pair(x, z)
            span = slice(fold * 672, (fold + 1) * 672)
            arrays["cosine_distance"][condition_index, span] = cosine
            arrays["relative_l2_distance"][condition_index, span] = relative
            arrays["max_abs_difference"][condition_index, fold] = maximum
            fold_cka.append(value)
            fold_reasons.append(reason)
        cka.append(fold_cka)
        reasons.append(fold_reasons)
    ap5 = SAFE._load_probe_deltas(parent)
    return arrays, build_results(arrays, cka, reasons, ap5)


def recursive_close(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        return isinstance(actual, Mapping) and set(actual) == set(expected) and all(recursive_close(actual[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(recursive_close(a, b) for a, b in zip(actual, expected, strict=True))
    if type(expected) is float:
        return type(actual) is float and math.isfinite(actual) and math.isfinite(expected) and math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
    return type(actual) is type(expected) and actual == expected


def validate_npz(path: Path, expected_arrays: Mapping[str, Any]) -> None:
    import numpy as np

    headers = SAFE.read_npz_headers(path)
    if headers["member_order"] != list(MEMBERS):
        raise ValueError("EXP-075 private NPZ member order drift")
    for name, expected in MEMBERS.items():
        header = headers["members"][name]
        if header["shape"] != expected["shape"] or header["descr"] != expected["dtype"] or header["fortran_order"]:
            raise ValueError("EXP-075 private NPZ header drift")
    with np.load(path, allow_pickle=False) as bundle:
        if bundle.files != list(MEMBERS):
            raise ValueError("EXP-075 private NPZ inventory drift")
        for name in MEMBERS:
            actual = bundle[name]
            if name == "heldout_ordinals":
                matched = np.array_equal(actual, expected_arrays[name])
            else:
                matched = bool(np.all(np.isfinite(actual)) and np.allclose(actual, expected_arrays[name], rtol=0.0, atol=1e-12, equal_nan=False))
            if not matched:
                raise ValueError("EXP-075 independently recomputed array mismatch")


def require_inventory(root: Path, names: Sequence[str], *, private: bool) -> None:
    if SAFE.require_safe_root(root, private=private) != set(names):
        raise ValueError("EXP-075 output inventory drift")
    SAFE.require_file_modes(root, names, private=private)


def validate_public_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or not SAFE.public_privacy_ok(value):
        raise ValueError("EXP-075 public privacy drift")
    def walk(item: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                walk(child, path + (str(key),))
        elif isinstance(item, list):
            if len(item) >= 672:
                raise ValueError("EXP-075 public rowwise array")
            for index, child in enumerate(item):
                walk(child, path + (str(index),))
        elif isinstance(item, str) and ("/Users/" in item or "phase-b-representation/private/" in item):
            if path != ("execution", "command", "0") or item != SAFE.ENVIRONMENT["python_executable"]:
                raise ValueError("EXP-075 public private-path disclosure")
    walk(value)


def validate_execution(value: Any, config: Mapping[str, Any], config_path: Path) -> None:
    if not isinstance(value, Mapping) or set(value) != {"started_at_utc", "ended_at_utc", "command", "cwd", "git_commit", "git_dirty"}:
        raise ValueError("EXP-075 execution schema drift")
    expected = [config["environment"]["python_executable"], IMPLEMENTATION_PATHS["runner"], "--config", config_path.relative_to(PROJECT_ROOT).as_posix(), "run"]
    if value["command"] != expected or value["cwd"] != "." or not re.fullmatch(r"[0-9a-f]{40}", str(value["git_commit"])) or type(value["git_dirty"]) is not bool:
        raise ValueError("EXP-075 execution identity drift")
    times = []
    for key in ("started_at_utc", "ended_at_utc"):
        text = value[key]
        if type(text) is not str:
            raise ValueError("EXP-075 execution timestamp drift")
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("EXP-075 execution timestamp is not UTC")
        times.append(parsed)
    if not 0 <= (times[1] - times[0]).total_seconds() <= RESOURCES["max_wall_seconds"]:
        raise ValueError("EXP-075 execution duration drift")


def validate_stdout(path: Path, results: Mapping[str, Any]) -> None:
    expected = [{"event": "started", "experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID}]
    for condition in CONDITION_ORDER:
        values = results["conditions"][condition]["linear_cka"]["per_fold"]
        for fold in FOLDS:
            expected.append({"event": "pair_complete", "condition": condition, "fold": fold, "cka_defined": values[fold] is not None})
    expected.append({"event": "finished", "status": "Analyzed", "pairs": 75})
    if path.read_bytes() != b"".join(canonical_json_bytes(value) for value in expected):
        raise ValueError("EXP-075 stdout trace schema or order drift")


def validate_payloads(config_path: Path, config: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    public = SAFE.resolve_project(config["outputs"]["public_root"])
    private = SAFE.resolve_project(config["outputs"]["private_root"])
    run_path, log_path = public / "run.json", public / "stdout.log"
    npz_path, manifest_path = private / "geometry.npz", private / "geometry-manifest.json"
    run, manifest = SAFE.require_canonical_json(run_path), SAFE.require_canonical_json(manifest_path)
    ids = {"experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID}
    expected_run = {
        "schema_version": "exp-075-geometry-run-v1", **ids, "tier": "Major", "rq_id": "RQ-S4.2",
        "stage": "formal-analysis", "status": "Analyzed", "config": artifact(config_path),
        "protocol": config["protocol"], "parent_config": config["parent_config"], "method": METHOD,
        "source_snapshot_sha256": snapshot["sha256"], "access": ACCESS, "claim_boundary": CLAIM_BOUNDARY,
        "artifacts": {"geometry_private": artifact(npz_path, logical_name=npz_path.name),
                      "manifest_private": artifact(manifest_path, logical_name=manifest_path.name),
                      "stdout": artifact(log_path)},
    }
    if set(run) != set(expected_run) | {"results", "resources", "execution"} or any(not recursive_close(run.get(key), value) for key, value in expected_run.items()):
        raise ValueError("EXP-075 run payload binding drift")
    expected_manifest = {
        "schema_version": "exp-075-geometry-manifest-v1", **ids, "config": artifact(config_path),
        "parent_config": config["parent_config"], "method": METHOD, "source_before": snapshot,
        "source_after": snapshot, "npz": artifact(npz_path, logical_name=npz_path.name),
        "member_order": list(MEMBERS), "members": MEMBERS, "results_sha256": digest(run["results"]), "access": ACCESS,
    }
    if not recursive_close(manifest, expected_manifest):
        raise ValueError("EXP-075 private manifest binding drift")
    resources = run["resources"]
    private_bytes = npz_path.stat().st_size + manifest_path.stat().st_size
    if not isinstance(resources, Mapping) or set(resources) != {"wall_seconds", "peak_rss_bytes", "private_bytes", "api_cost_usd"}:
        raise ValueError("EXP-075 resource payload schema drift")
    if type(resources["wall_seconds"]) not in (int, float) or type(resources["peak_rss_bytes"]) is not int or type(resources["private_bytes"]) is not int or type(resources["api_cost_usd"]) not in (int, float) or not 0 <= resources["wall_seconds"] <= RESOURCES["max_wall_seconds"] or not 0 < resources["peak_rss_bytes"] <= RESOURCES["max_peak_rss_bytes"] or resources["private_bytes"] != private_bytes or private_bytes > RESOURCES["max_private_bytes"] or resources["api_cost_usd"] != 0:
        raise ValueError("EXP-075 resource ceiling or accounting drift")
    validate_execution(run["execution"], config, config_path)
    validate_public_payload(run)
    validate_stdout(log_path, run["results"])
    return run, manifest


def _no_producer_or_model_import() -> None:
    if {name.split(".", 1)[0] for name in sys.modules} & {"torch", "transformers", "mlx", "mlx_lm"}:
        raise RuntimeError("EXP-075 verifier imported a model library")
    forbidden = {MODULE_DIR / "run_exp075_geometry.py", MODULE_DIR / "run_exp071_drift.py"}
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).resolve() in forbidden:
            raise RuntimeError("EXP-075 verifier imported a producer")


CHECKS = [
    "config_protocol_implementation_identity", "parent_source_contract", "runtime_and_locks",
    "public_private_inventory_modes_links", "run_manifest_artifact_bindings", "stdout_trace",
    "sixteen_source_headers", "row_contract_heldout_partition", "independent_cosine_distance",
    "independent_relative_l2", "independent_nullable_cka", "exact_zero_domain_only",
    "five_fold_all_or_null", "fixed_nine_spearman_or_null", "pre_lora_sanity",
    "private_npz_exact_schema", "independent_public_statistics", "access_privacy_boundary",
    "resource_ceilings", "source_and_sealed_outputs_unchanged",
]


def verify(config_path: Path) -> dict[str, Any]:
    started = time.monotonic()
    config_path = config_path.resolve()
    config = load_config(config_path)
    parent = require_frozen_files(config_path, config)
    _no_producer_or_model_import()
    initial_config = artifact(config_path)
    public = SAFE.resolve_project(config["outputs"]["public_root"])
    private = SAFE.resolve_project(config["outputs"]["private_root"])
    require_inventory(public, ["run.json", "stdout.log"], private=False)
    require_inventory(private, ["geometry.npz", "geometry-manifest.json"], private=True)
    with verification_lock():
        if shutil.disk_usage(PROJECT_ROOT).free < RESOURCES["min_free_bytes"]:
            raise ValueError("EXP-075 verifier free-disk gate failed")
        SAFE.require_parent_statuses(parent, read_probe_values=False)
        before = SAFE.source_identity_snapshot(parent)
        SAFE.matrix_headers(parent)
        SAFE.row_contract_headers(parent)
        run, _manifest = validate_payloads(config_path, config, before)
        output_paths = [public / "run.json", public / "stdout.log", private / "geometry.npz", private / "geometry-manifest.json"]
        sealed = [artifact(path) for path in output_paths]
        arrays, results = recompute_geometry(parent, started)
        validate_npz(private / "geometry.npz", arrays)
        if not recursive_close(run["results"], results):
            raise ValueError("EXP-075 independently recomputed statistics mismatch")
        after = SAFE.source_identity_snapshot(parent)
        require_frozen_files(config_path, config)
        if after != before or artifact(config_path) != initial_config or [artifact(path) for path in output_paths] != sealed:
            raise ValueError("EXP-075 source or sealed artifact changed")
        budget_check(started)
        _no_producer_or_model_import()
        result = {
            "schema_version": "exp-075-geometry-verification-v1", "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID, "attempt_id": ATTEMPT_ID, "tier": "Major", "rq_id": "RQ-S4.2",
            "status": "Passed", "complete": True, "exp075_complete": True, "exp071_complete": False,
            "passed_count": len(CHECKS), "failed_count": 0, "checks": CHECKS,
            "config": initial_config, "protocol": config["protocol"], "parent_config": config["parent_config"],
            "run": artifact(public / "run.json"), "source_snapshot_sha256": before["sha256"],
            "source_unchanged": True, "results_sha256": digest(run["results"]),
            "recomputed_results_sha256": digest(results), "access": ACCESS,
            "resources": {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": _peak_rss_bytes(), "api_cost_usd": 0},
            "claim_boundary": CLAIM_BOUNDARY,
        }
        validate_public_payload(result)
        SAFE.create_json_once(public / "verification.json", result)
        require_inventory(public, ["run.json", "stdout.log", "verification.json"], private=False)
        return result


def _record_failure(config_path: Path, error: BaseException) -> None:
    try:
        config = load_config(config_path.resolve())
        public = SAFE.resolve_project(config["outputs"]["public_root"])
        target = public / "verification.json"
        if os.path.lexists(target):
            return
        require_inventory(public, ["run.json", "stdout.log"], private=False)
        value = {"schema_version": "exp-075-geometry-verification-v1", "experiment_id": EXPERIMENT_ID,
                 "run_id": RUN_ID, "attempt_id": ATTEMPT_ID, "status": "Failed", "complete": False,
                 "exp075_complete": False, "exp071_complete": False, "error_code": "verification_failed",
                 "error_type": type(error).__name__, "config": artifact(config_path.resolve())}
        SAFE.create_json_once(target, value)
    except Exception:
        return


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    path = args.config.resolve()
    try:
        result = verify(path)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:
        _record_failure(path, error)
        print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": "Failed", "error_code": "verification_failed", "error_type": type(error).__name__}), file=sys.stderr)
        return 1
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": result["status"], "complete": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

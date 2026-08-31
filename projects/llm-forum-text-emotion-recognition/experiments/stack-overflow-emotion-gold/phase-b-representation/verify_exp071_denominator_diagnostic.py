#!/usr/bin/env python3
"""Independently verify the bounded EXP-071 Incident-002 diagnostic.

Only the three CKA denominator terms are classified.  No term magnitude,
representation, AP5 value or other drift metric is emitted.  The frozen prior
independent verifier supplies identity-only IO and header helpers; neither
the diagnostic producer nor the original producer is imported.
"""

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
import resource
import shutil
import stat
import subprocess
import sys
import time
from typing import Any, Iterator, Mapping, Sequence


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_STATIC_CONFIG = MODULE_DIR / "configs" / "exp-071-denominator-diagnostic-preflight.json"
DEFAULT_DIAGNOSTIC_CONFIG = (
    MODULE_DIR / "configs" / "exp-071-denominator-diagnostic-formal-attempt-1.json"
)
DIAGNOSTIC_ID = "EXP-071-DENOMINATOR-DIAGNOSTIC-INCIDENT-002"
SNAPSHOT_SCOPE = "diagnostic_minimal_bound_artifacts_no_ap5_probe"
EXPERIMENT_ID = "EXP-071"
ALL_POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
CONFIRMATION_POINTS = ("H19", "H27", "HF")
FOLDS = (0, 1, 2, 3, 4)
CONDITION_ORDER = tuple(
    [f"s42:{point}" for point in ALL_POINTS]
    + [f"s43:{point}" for point in CONFIRMATION_POINTS]
    + [f"s44:{point}" for point in CONFIRMATION_POINTS]
)
CATEGORIES = {"zero", "finite_positive", "nonfinite"}
LOCALIZATION_KEYS = {
    "condition", "fold", "pairs_examined", "norm_x", "norm_z", "denominator"
}
HELPER_PATH = MODULE_DIR / "verify_exp071_drift.py"
HELPER_BYTES = 121050
HELPER_SHA256 = "0a6e0e03a2f14212bc2bf0d3a1ecc3d9cf4eec1ee8a3a9f7b44cd3ca83a0bbd2"
ORIGINAL_SOURCE_SHA256 = "8f7bc1836021053d0ffd48a620170996ed72475f54c57034ca2591dd515dffcf"
ORIGINAL_METHOD_SHA256 = "f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210"
ORIGINAL_SNAPSHOT_SHA256 = "df5e9d00c2464462eb541b3416efe4d96c6836efb43d778699392fe3501535d9"
HEAVY_LOCK = MODULE_DIR / "private" / "locks" / "heavy-research-workload.lock"
DIAGNOSTIC_LOCK = MODULE_DIR / "private" / "locks" / "exp071-denominator-diagnostic.lock"
METHOD_SHA256 = "a90ed692f6171f4fd55ce1f67c85bb11c071c26276d3e48777d9c97aced7fa76"
SOURCE_SHA256 = "20ab3dd3789b2440d8cd9ab1b9a4035cee20224c05d2dcda85bfe9419f11516b"
INCIDENT_SHA256 = "b91c017308a410cacc1448142985ed868b534f757d53ff4147b1d476d90d3864"
PROTOCOL_RECORD = {
    "path": "experiments/stack-overflow-emotion-gold/protocols/exp-071-denominator-diagnostic-incident-002.md",
    "bytes": 6098,
    "mode": "0644",
    "sha256": "43cdf1efa8cea5cf226e3ea6877504200a8433c3d46314f8101e6b7ea129b353",
}
BLOCK_HASHES = {
    "method": METHOD_SHA256,
    "source": SOURCE_SHA256,
    "incident": INCIDENT_SHA256,
    "resources": "6097d45a95994fc6d3eae4b3459df1ff5bac129ab049c861ee4e6112f32214e0",
}
CONTROL_HASHES = {
    "static": {
        "outputs": "b865b05e29f64bd6a2d18211dbd43607d8deed9417562ca11ceb692e3e518c43",
        "access": "e398e14343d77f644b1aca598622677578baad715852452417395e8119b135b2",
        "authorization": "ad130962cfc9c546a38ac454e5b2c9a9e009931f34e228782fed99bbb4840830",
        "claim_boundary": "1f9ab6ebefcf5454f5824891dda881e5a590256fe4f5634ff2b702c0d1d04235",
    },
    "diagnostic": {
        "outputs": "2668331a730ff1f7ce18bdbada9eb20317cee37a4f1bf37d33318dc05a981d2b",
        "access": "80a1df03f58f05fd22a1fa235565e7826c3119352b326afdfa1ce17b60e901f1",
        "authorization": "eab0d83561133d3b8d1d686fa1f21e7758c7b561f09073b033522c1198f4b6a7",
        "claim_boundary": "d1858974360f3d77ec6936cf803ef9da19b1750b43bd028725783982bb2840dc",
    },
}
IMPLEMENTATION_PATHS = {
    "runner": "experiments/stack-overflow-emotion-gold/phase-b-representation/run_exp071_denominator_diagnostic.py",
    "verifier": "experiments/stack-overflow-emotion-gold/phase-b-representation/verify_exp071_denominator_diagnostic.py",
    "tests": "experiments/stack-overflow-emotion-gold/phase-b-representation/tests/test_exp071_denominator_diagnostic.py",
}
PENDING_ACTIVATION = "replace_TBD_identities_after_Passed_static_completion_in_separate_active_config"
STATIC_ACCESS = {
    "bound_artifact_bytes_hashed": True, "headers_read": True,
    "original_failure_metadata_read": True, "representation_values_read": False,
    "row_contract_ordinal_fold_values_read": False, "component_code_values_read": False,
    "denominator_categories_computed": False, "other_drift_metrics_computed": False,
    "ap5_probe_files_opened": False, "labels_read": False, "sample_component_ids_read": False,
    "text_read": False, "model_loaded": False, "forward_executed": False,
    "validation_test_accessed": False, "exact_term_values_persisted": False,
    "source_mutated": False,
}
DIAGNOSTIC_ACCESS = {
    **STATIC_ACCESS, "representation_values_read": True,
    "row_contract_ordinal_fold_values_read": True, "denominator_categories_computed": True,
}
STATIC_CHECKS = [
    "frozen_config_method_source_incident", "implementation_and_helper_identity",
    "original_failed_prefix", "selected_source_headers", "no_ap5_probe_file_access",
    "runtime_identity", "synthetic_suite", "exact_output_prefix_modes_links",
    "static_payload_bindings", "private_budget", "public_schema_privacy", "source_unchanged",
]
DIAGNOSTIC_CHECKS = [
    "frozen_config_method_source_incident", "implementation_and_helper_identity",
    "preflight_exact_replay", "original_failed_prefix", "selected_source_headers",
    "runtime_identity", "exact_output_prefix_modes_links", "input_and_claim_bindings",
    "heldout_only_row_contract", "read_only_matrix_mappings", "original_condition_fold_order",
    "independent_denominator_categories", "first_failure_stop", "exact_localization",
    "no_ap5_other_metric_or_exact_term", "resource_ceilings", "public_schema_privacy",
    "source_unchanged", "no_producer_import",
]


def _load_identity_helpers() -> Any:
    if HELPER_PATH.is_symlink() or not HELPER_PATH.is_file():
        raise ValueError("Unsafe frozen independent-verifier helper")
    info = HELPER_PATH.stat()
    payload = HELPER_PATH.read_bytes()
    if (
        info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) != 0o644
        or len(payload) != HELPER_BYTES
        or hashlib.sha256(payload).hexdigest() != HELPER_SHA256
    ):
        raise ValueError("Frozen independent-verifier helper identity drift")
    specification = importlib.util.spec_from_file_location(
        "exp071_frozen_independent_identity_helpers", HELPER_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("Cannot load frozen identity helpers")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SAFE = _load_identity_helpers()
canonical_json_bytes = SAFE.canonical_json_bytes
strict_json = SAFE.strict_json
strict_json_bytes = SAFE.strict_json_bytes
artifact = SAFE.artifact
require_record = SAFE.require_record
resolve_project = SAFE.resolve_project
read_npy_header = SAFE.read_npy_header
read_npz_headers = SAFE.read_npz_headers
select_json_scalars = SAFE.select_json_scalars


class FailureNotReproduced(RuntimeError):
    """All registered pairs passed; no localization may be published."""


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def validate_config(config: Mapping[str, Any], kind: str, *, allow_tbd: bool = False) -> None:
    common = {
        "schema_version", "experiment_id", "diagnostic_id", "rq_id", "tier", "registered_at",
        "run_id", "attempt_id", "stage", "method_protocol", "implementation", "incident",
        "source", "method", "environment", "resources", "authorization", "access", "outputs",
        "claim_boundary",
    }
    if kind not in {"static", "diagnostic"} or set(config) != common | ({"preflight"} if kind == "diagnostic" else set()):
        raise ValueError("Diagnostic config schema drift")
    suffix = "preflight" if kind == "static" else "formal"
    expected_run = "exp-071-denominator-diagnostic" + ("-preflight" if kind == "static" else "")
    expected_attempt = "denominator-diagnostic" + ("-preflight" if kind == "static" else "") + "-attempt-1"
    if (
        config["schema_version"] != f"exp-071-denominator-diagnostic-{suffix}-config-v1"
        or config["experiment_id"] != EXPERIMENT_ID or config["diagnostic_id"] != DIAGNOSTIC_ID
        or config["run_id"] != expected_run or config["attempt_id"] != expected_attempt
        or config["stage"] != ("no-result-preflight" if kind == "static" else "formal-diagnostic")
        or config["rq_id"] != "RQ-S4.2" or config["tier"] != "Minor technical failure diagnostic"
        or config["registered_at"] != "2026-08-30" or config["method_protocol"] != PROTOCOL_RECORD
        or config["environment"] != SAFE.ENVIRONMENT
    ):
        raise ValueError("Diagnostic config identity drift")
    for key, expected in BLOCK_HASHES.items():
        if digest(config[key]) != expected:
            raise ValueError(f"Diagnostic frozen {key} drift")
    for key in ("outputs", "claim_boundary"):
        if digest(config[key]) != CONTROL_HASHES[kind][key]:
            raise ValueError(f"Diagnostic frozen {key} drift")
    authorization = dict(config["authorization"])
    access = dict(config["access"])
    if kind == "diagnostic":
        active = not allow_tbd or access.get("currently_authorized") is True
        value_keys = (
            "diagnostic_initialize_authorized", "diagnostic_run_authorized",
            "diagnostic_verification_authorized", "diagnostic_completion_authorized",
            "representation_value_access_authorized", "row_contract_value_access_authorized",
        )
        if active and (any(authorization.get(key) is not True for key in value_keys)
                       or authorization.get("activation_condition") != "Passed_static_completion_exact_identities_bound"
                       or access.get("currently_authorized") is not True):
            raise PermissionError("Diagnostic activation is incomplete")
        for key in value_keys:
            authorization[key] = False
        authorization["activation_condition"] = PENDING_ACTIVATION
        access["currently_authorized"] = False
    if digest(authorization) != CONTROL_HASHES[kind]["authorization"] or digest(access) != CONTROL_HASHES[kind]["access"]:
        raise PermissionError("Diagnostic authorization or access drift")
    implementation = config["implementation"]
    if not isinstance(implementation, Mapping) or set(implementation) != set(IMPLEMENTATION_PATHS):
        raise ValueError("Diagnostic implementation inventory drift")
    for name, path in IMPLEMENTATION_PATHS.items():
        record = implementation[name]
        if set(record) != {"path", "bytes", "mode", "sha256", "status"} or record["path"] != path:
            raise ValueError("Diagnostic implementation path or schema drift")
        if not allow_tbd and (record["status"] != "Frozen" or record["bytes"] <= 0 or record["mode"] != "0644" or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])):
            raise ValueError("Diagnostic implementation is not frozen")


def load_config(path: Path, kind: str, *, allow_tbd: bool = False) -> dict[str, Any]:
    resolved = path.resolve()
    config = strict_json(resolved)
    validate_config(config, kind, allow_tbd=allow_tbd)
    if not allow_tbd:
        expected = DEFAULT_STATIC_CONFIG.resolve() if kind == "static" else resolve_project(config["outputs"]["active_config_path"], must_exist=False)
        if resolved != expected:
            raise ValueError("Diagnostic config path is not the registered active path")
    return config


def require_implementation(config: Mapping[str, Any]) -> dict[str, Path]:
    paths = {name: require_record(record) for name, record in config["implementation"].items()}
    if paths["verifier"].resolve() != Path(__file__).resolve():
        raise ValueError("Diagnostic verifier identity points elsewhere")
    if any(name in sys.modules for name in ("run_exp071_drift", "run_exp071_denominator_diagnostic")):
        raise RuntimeError("Diagnostic verifier imported a producer")
    return paths


def source_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for group in ("method_protocol", "implementation", "incident", "source"):
        for record in SAFE.iter_artifact_records(config[group]):
            current = artifact(require_record(record))
            if current["path"] in records and records[current["path"]] != current:
                raise ValueError("Conflicting diagnostic source identity")
            records[current["path"]] = current
    ordered = [records[key] for key in sorted(records)]
    return {"artifact_count": len(ordered), "artifacts": ordered, "sha256": digest(ordered)}


def require_inventory(root: Path, names: Sequence[str], *, private: bool) -> None:
    if SAFE.require_safe_root(root, private=private) != set(names):
        raise ValueError("Diagnostic exact-prefix inventory drift")
    SAFE.require_file_modes(root, names, private=private)


def _root(config: Mapping[str, Any], kind: str, private: bool) -> Path:
    prefix = "preflight" if kind == "static" else "formal"
    return resolve_project(config["outputs"][f"{prefix}_{'private' if private else 'public'}_root"], must_exist=False)


def inspect_sources(config: Mapping[str, Any]) -> dict[str, Any]:
    incident = config["incident"]
    original = strict_json(require_record(incident["failed_config"]))
    if digest(original["source"]) != ORIGINAL_SOURCE_SHA256 or digest(original["method"]) != ORIGINAL_METHOD_SHA256:
        raise ValueError("Original method or source metadata drift")
    source = config["source"]
    if source["matrices"] != original["source"]["matrices"] or source["matrix_root"] != original["source"]["matrix_root"] or source["row_contract"] != original["source"]["exp070_extraction_terminal"]["row_contract"]:
        raise ValueError("Diagnostic source allowlist diverges from original")
    for name in ("runner", "verifier"):
        if source["helpers"][name] != {key: original["implementation"][name][key] for key in ("path", "bytes", "mode", "sha256")}:
            raise ValueError("Diagnostic helper binding diverges from original")
    original_identity = original["source"]["exp070_extraction_terminal"]["row_identity"]
    if source["row_identity"] != {key: original_identity[key] for key in ("rows", "ordinal_sha256", "fold_id_order_sha256")}:
        raise ValueError("Diagnostic row identity binding drift")
    failure_path = require_record(incident["failure_artifact"])
    targets = [(key,) for key in incident["expected_failure"]]
    selected, _ = select_json_scalars(failure_path.read_bytes(), targets)
    if selected != {(key,): value for key, value in incident["expected_failure"].items()}:
        raise ValueError("Original denominator failure identity drift")
    claim_path = require_record(incident["run_claim"])
    input_path = require_record(incident["input_manifest"])
    require_inventory(claim_path.parent, ["run-claim.json", "failure.json"], private=False)
    require_inventory(input_path.parent, ["input-manifest.json"], private=True)
    claim = SAFE.require_canonical_json(claim_path)
    original_input = SAFE.require_canonical_json(input_path)
    if claim["config"] != incident["failed_config"] or original_input["config"] != incident["failed_config"] or claim["status"] != "Initialized" or original_input["status"] != "Initialized":
        raise ValueError("Original failed-prefix config binding drift")
    if claim["input_manifest"] != artifact(input_path, logical_name=input_path.name) or claim["method_sha256"] != ORIGINAL_METHOD_SHA256:
        raise ValueError("Original claim/input seal binding drift")
    if original_input["source_snapshot_sha256"] != ORIGINAL_SNAPSHOT_SHA256 or original_input["method_sha256"] != ORIGINAL_METHOD_SHA256:
        raise ValueError("Original input seal drift")
    headers = []
    for item in source["matrices"]:
        path = require_record(item["artifact"])
        header = read_npy_header(path)
        if header["shape"] != item["shape"] or header["descr"] != "<f4" or header["fortran_order"] or header["file_bytes"] != header["data_offset"] + math.prod(item["shape"]) * 4:
            raise ValueError("Diagnostic matrix header drift")
        headers.append({"worker_id": item["worker_id"], **header})
    row_headers = read_npz_headers(require_record(source["row_contract"]))
    expected = {"ordinal": ([3360], "<i4"), "fold_id": ([3360], "|i1"), "component_code": ([3360], "<i4")}
    if row_headers["member_order"] != list(expected):
        raise ValueError("Diagnostic row-contract member order drift")
    for name, (shape, dtype) in expected.items():
        value = row_headers["members"][name]
        if value["shape"] != shape or value["descr"] != dtype or value["fortran_order"]:
            raise ValueError("Diagnostic row-contract header drift")
    return {"matrix_headers": headers, "row_contract_headers": row_headers}


def classify_nonnegative(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        return "nonfinite"
    if number < 0.0:
        raise ValueError("Unexpected finite-negative denominator term")
    return "zero" if number == 0.0 else "finite_positive"


def denominator_categories(x: Any, z: Any) -> dict[str, str]:
    import numpy as np

    frozen = np.ascontiguousarray(x, dtype=np.float64)
    adapted = np.ascontiguousarray(z, dtype=np.float64)
    if frozen.ndim != 2 or adapted.shape != frozen.shape or frozen.shape[0] < 2 or frozen.shape[1] < 1:
        raise ValueError("Diagnostic pair shape drift")
    if not np.all(np.isfinite(frozen)) or not np.all(np.isfinite(adapted)):
        raise ValueError("Unexpected non-finite diagnostic input")
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        centered_x = frozen - np.mean(frozen, axis=0, dtype=np.float64)
        centered_z = adapted - np.mean(adapted, axis=0, dtype=np.float64)
        gram_x = centered_x @ centered_x.T
        gram_z = centered_z @ centered_z.T
        norm_x = float(np.sum(gram_x * gram_x, dtype=np.float64))
        norm_z = float(np.sum(gram_z * gram_z, dtype=np.float64))
        category_x = classify_nonnegative(norm_x)
        category_z = classify_nonnegative(norm_z)
        denominator = float(np.sqrt(norm_x * norm_z))
    return {
        "norm_x": category_x,
        "norm_z": category_z,
        "denominator": classify_nonnegative(denominator),
    }


def first_denominator_failure(
    partitions: Sequence[Any],
    pair_loader: Any,
    condition_order: Sequence[str] = CONDITION_ORDER,
    budget_check: Any = None,
) -> dict[str, Any]:
    if not partitions or not condition_order:
        raise ValueError("Empty diagnostic comparison plan")
    pairs_examined = 0
    for condition in condition_order:
        for fold, ordinals in enumerate(partitions):
            if budget_check is not None:
                budget_check()
            x, z = pair_loader(condition, fold, ordinals)
            categories = denominator_categories(x, z)
            pairs_examined += 1
            if any(value != "finite_positive" for value in categories.values()):
                return {
                    "condition": condition,
                    "fold": fold,
                    "pairs_examined": pairs_examined,
                    **categories,
                }
    raise FailureNotReproduced("failure_not_reproduced")


def validate_localization(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != LOCALIZATION_KEYS:
        raise ValueError("Diagnostic localization schema drift")
    condition = value.get("condition")
    fold = value.get("fold")
    if condition not in CONDITION_ORDER or type(fold) is not int or fold not in FOLDS:
        raise ValueError("Diagnostic localization identity drift")
    expected_count = CONDITION_ORDER.index(condition) * len(FOLDS) + fold + 1
    if type(value.get("pairs_examined")) is not int or value["pairs_examined"] != expected_count:
        raise ValueError("Diagnostic comparison prefix drift")
    categories = [value.get(key) for key in ("norm_x", "norm_z", "denominator")]
    if any(type(item) is not str or item not in CATEGORIES for item in categories) or all(item == "finite_positive" for item in categories):
        raise ValueError("Diagnostic did not identify a denominator failure")


def _peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


@contextmanager
def diagnostic_lock() -> Iterator[None]:
    with SAFE._file_mutex(HEAVY_LOCK, "heavy research"):
        with SAFE._file_mutex(DIAGNOSTIC_LOCK, "EXP-071 denominator diagnostic verifier"):
            yield


def recompute_localization(config: Mapping[str, Any], started: float) -> dict[str, Any]:
    import numpy as np

    source = config["source"]
    with np.load(require_record(source["row_contract"]), allow_pickle=False) as archive:
        if archive.files != ["ordinal", "fold_id", "component_code"]:
            raise ValueError("Diagnostic row-contract inventory drift")
        ordinal = np.asarray(archive["ordinal"])
        fold_id = np.asarray(archive["fold_id"])
    if ordinal.dtype != np.dtype("<i4") or fold_id.dtype != np.dtype("i1") or ordinal.shape != (3360,) or fold_id.shape != (3360,):
        raise ValueError("Diagnostic row-contract type drift")
    array_hash = lambda value: hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
    identity = source["row_identity"]
    if array_hash(ordinal) != identity["ordinal_sha256"] or array_hash(fold_id) != identity["fold_id_order_sha256"] or not np.array_equal(ordinal, np.arange(3360, dtype="<i4")):
        raise ValueError("Diagnostic row-contract identity drift")
    partitions = [np.sort(ordinal[fold_id == fold]) for fold in FOLDS]
    if any(rows.shape != (672,) for rows in partitions):
        raise ValueError("Diagnostic heldout partition drift")
    records = {item["worker_id"]: item for item in source["matrices"]}
    opened: dict[str, Any] = {}

    def open_matrix(worker: str) -> Any:
        if worker not in opened:
            record = records[worker]
            value = np.load(require_record(record["artifact"]), mmap_mode="r", allow_pickle=False)
            if not isinstance(value, np.memmap) or value.dtype != np.dtype("<f4") or list(value.shape) != record["shape"] or value.flags.writeable or not value.flags.c_contiguous:
                raise ValueError("Diagnostic read-only matrix mapping drift")
            opened[worker] = value
        return opened[worker]

    def pair_loader(condition: str, fold: int, rows: Any) -> tuple[Any, Any]:
        if time.monotonic() - started > config["resources"]["verifier_wall_seconds"] or _peak_rss_bytes() > config["resources"]["peak_rss_bytes"]:
            raise RuntimeError("Diagnostic verifier resource ceiling exceeded")
        seed, point = condition.split(":", 1)
        worker = f"m3-{seed}-f{fold}"
        base = open_matrix("base")
        adapted = open_matrix(worker)
        x = np.ascontiguousarray(base[rows, records["base"]["points"].index(point), :], dtype=np.float64)
        z = np.ascontiguousarray(adapted[rows, records[worker]["points"].index(point), :], dtype=np.float64)
        if x.shape != (672, 2560) or z.shape != x.shape:
            raise ValueError("Diagnostic heldout slice shape drift")
        return x, z

    result = first_denominator_failure(partitions, pair_loader)
    validate_localization(result)
    return result


def synthetic_summary(config: Mapping[str, Any], *, execute: bool) -> dict[str, Any]:
    path = require_record(config["implementation"]["tests"])
    command = [sys.executable, str(path)]
    if not execute:
        raise ValueError("Recorded synthetic summary must be provided by the static run")
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=environment, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600, check=False)
    matches = re.findall(r"Ran\s+(\d+)\s+tests?", result.stdout + "\n" + result.stderr)
    if result.returncode or not matches or int(matches[-1]) < 1:
        raise RuntimeError("Diagnostic synthetic suite failed")
    return {"status": "Passed", "tests_run": int(matches[-1]), "test_artifact": artifact(path), "command_sha256": digest(command)}


def validate_resources(value: Any, config: Mapping[str, Any], *, private_root: Path | None = None) -> None:
    required = {"elapsed_seconds", "peak_rss_bytes", "api_cost_usd"}
    allowed = required | {"private_output_bytes", "source_artifact_count"}
    if not isinstance(value, Mapping) or not required <= set(value) or not set(value) <= allowed:
        raise ValueError("Diagnostic resource payload schema drift")
    if not 0 <= float(value["elapsed_seconds"]) <= 7200 or not 0 < int(value["peak_rss_bytes"]) <= 4294967296 or value["api_cost_usd"] != 0:
        raise ValueError("Diagnostic resource ceiling drift")
    if private_root is not None:
        private_bytes = sum(path.stat().st_size for path in private_root.iterdir())
        if private_bytes > config["resources"]["private_output_budget_bytes"]:
            raise ValueError("Diagnostic private-output budget exceeded")
        if "private_output_bytes" in value and value["private_output_bytes"] != private_bytes:
            raise ValueError("Diagnostic private-output byte accounting drift")


def validate_execution(value: Any, config: Mapping[str, Any]) -> None:
    keys = {"started_at_utc", "ended_at_utc", "command", "cwd", "git_commit", "git_dirty"}
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("Diagnostic execution record schema drift")
    command = [config["environment"]["python_executable"], IMPLEMENTATION_PATHS["runner"],
               "--stage", "diagnose", "--config", config["outputs"]["active_config_path"]]
    if value["command"] != command or value["cwd"] != "." or type(value["git_dirty"]) is not bool or not re.fullmatch(r"[0-9a-f]{40}", str(value["git_commit"])):
        raise ValueError("Diagnostic execution command or git identity drift")
    times = []
    for key in ("started_at_utc", "ended_at_utc"):
        text = value[key]
        if type(text) is not str or not text.endswith("Z"):
            raise ValueError("Diagnostic execution timestamp is not UTC")
        try:
            parsed = datetime.fromisoformat(text[:-1] + "+00:00")
        except ValueError as error:
            raise ValueError("Diagnostic execution timestamp format drift") from error
        if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError("Diagnostic execution timestamp timezone drift")
        times.append(parsed)
    if not 0 <= (times[1] - times[0]).total_seconds() <= 7200:
        raise ValueError("Diagnostic execution timestamp duration drift")


def _identity(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: config[key] for key in ("experiment_id", "diagnostic_id", "run_id", "attempt_id")}


def _check_equal(value: Mapping[str, Any], expected: Mapping[str, Any], keys: set[str]) -> None:
    if set(value) != keys or any(value.get(key) != item for key, item in expected.items()):
        raise ValueError("Diagnostic exact payload binding drift")


def validate_public_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or not SAFE.public_privacy_ok(value):
        raise ValueError("Diagnostic public privacy drift")
    def visit(item: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if key in {"norm_x", "norm_z", "denominator"} and (type(child) is not str or child not in CATEGORIES):
                    raise ValueError("Diagnostic exact term value would be disclosed")
                visit(child, path + (str(key),))
        elif isinstance(item, list):
            if len(item) >= 672:
                raise ValueError("Diagnostic rowwise public value would be disclosed")
            for index, child in enumerate(item):
                visit(child, path + (str(index),))
        elif isinstance(item, str) and ("/Users/" in item or "phase-b-representation/private/" in item):
            if path != ("execution", "command", "0") or item != SAFE.ENVIRONMENT["python_executable"]:
                raise ValueError("Diagnostic private path would be disclosed")
    visit(value)


def _base_payload(config: Mapping[str, Any], name: str) -> dict[str, Any]:
    return {"schema_version": f"exp-071-denominator-diagnostic-{name}-v1", **_identity(config)}


def _validate_synthetic_record(config: Mapping[str, Any], value: Any) -> None:
    test_path = require_record(config["implementation"]["tests"])
    if not isinstance(value, Mapping) or set(value) != {"status", "tests_run", "test_artifact", "command_sha256"}:
        raise ValueError("Diagnostic synthetic proof schema drift")
    if value["status"] != "Passed" or type(value["tests_run"]) is not int or value["tests_run"] < 1 or value["test_artifact"] != artifact(test_path) or value["command_sha256"] != digest([sys.executable, str(test_path)]):
        raise ValueError("Diagnostic synthetic proof identity drift")


def _validate_static_payloads(
    config_path: Path, config: Mapping[str, Any], snapshot: Mapping[str, Any],
    headers: Mapping[str, Any], synthetic: Mapping[str, Any],
) -> tuple[Path, Path]:
    public, private = _root(config, "static", False), _root(config, "static", True)
    input_path, run_path = private / "input-contract-manifest.json", public / "static.json"
    input_doc, run = SAFE.require_canonical_json(input_path), SAFE.require_canonical_json(run_path)
    expected_input = {
        **_base_payload(config, "static-input"), "status": "Sealed", "config": artifact(config_path),
        "method_sha256": METHOD_SHA256, "source_snapshot": snapshot, **headers, "access": STATIC_ACCESS,
    }
    _check_equal(input_doc, expected_input, set(expected_input))
    expected_run = {
        **_base_payload(config, "static-run"), "stage": "static", "status": "CompletedAwaitingVerification",
        "config": artifact(config_path), "input_manifest": artifact(input_path, logical_name=input_path.name),
        "method_sha256": METHOD_SHA256, "source_snapshot_sha256": snapshot["sha256"],
        "source_snapshot_scope": SNAPSHOT_SCOPE, "synthetic_tests": synthetic,
        "access": STATIC_ACCESS, "claim_boundary": config["claim_boundary"],
    }
    _check_equal(run, expected_run, set(expected_run) | {"resources"})
    if set(run["resources"]) != {"elapsed_seconds", "peak_rss_bytes", "api_cost_usd"}:
        raise ValueError("Diagnostic static resource schema drift")
    validate_resources(run["resources"], config, private_root=private)
    validate_public_payload(run)
    return run_path, input_path


def _static_verification_payload(
    config_path: Path, config: Mapping[str, Any], snapshot: Mapping[str, Any],
    run_path: Path, input_path: Path, synthetic: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        **_base_payload(config, "static-verification"), "stage": "static-verify", "status": "Passed",
        "passed_count": len(STATIC_CHECKS), "failed_count": 0, "checks": STATIC_CHECKS,
        "config": artifact(config_path), "run": artifact(run_path),
        "input_manifest": artifact(input_path, logical_name=input_path.name),
        "method_sha256": METHOD_SHA256, "source_snapshot_sha256": snapshot["sha256"],
        "source_snapshot_scope": SNAPSHOT_SCOPE, "synthetic_tests": synthetic,
        "access": STATIC_ACCESS, "diagnostic_execution_authorized": False,
        "diagnostic_complete": False, "exp071_complete": False, "recovery_authorized": False,
        "exp072_authorized": False, "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(value)
    return value


def _static_completion_payload(
    config_path: Path, config: Mapping[str, Any], snapshot: Mapping[str, Any],
    run_path: Path, input_path: Path, verification_path: Path,
) -> dict[str, Any]:
    value = {
        **_base_payload(config, "no-result-complete"), "stage": "static-complete", "status": "Complete",
        "config": artifact(config_path), "run": artifact(run_path), "verification": artifact(verification_path),
        "input_manifest": artifact(input_path, logical_name=input_path.name), "method_sha256": METHOD_SHA256,
        "source_snapshot_sha256": snapshot["sha256"], "source_snapshot_scope": SNAPSHOT_SCOPE,
        "diagnostic_execution_authorized": True, "diagnostic_complete": False, "exp071_complete": False,
        "recovery_authorized": False, "exp072_authorized": False, "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(value)
    return value


def _require_no_producer_or_model_import() -> None:
    forbidden = {"mlx", "mlx_lm", "torch", "transformers"}
    if {name.split(".", 1)[0] for name in sys.modules} & forbidden:
        raise RuntimeError("Diagnostic verifier imported a model library")
    producer_paths = {MODULE_DIR / "run_exp071_drift.py", MODULE_DIR / "run_exp071_denominator_diagnostic.py"}
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).resolve() in producer_paths:
            raise RuntimeError("Diagnostic verifier imported a producer")


def _require_static_value_boundary() -> None:
    if "numpy" in sys.modules:
        raise RuntimeError("Static diagnostic verifier imported NumPy")


def verify_static(config_path: Path, *, complete: bool) -> dict[str, Any]:
    started = time.monotonic()
    config_path = config_path.resolve()
    config = load_config(config_path, "static")
    require_implementation(config)
    _require_no_producer_or_model_import()
    _require_static_value_boundary()
    SAFE.require_environment(config)
    if shutil.disk_usage(PROJECT_ROOT).free < config["resources"]["minimum_free_disk_bytes"]:
        raise ValueError("Diagnostic static verifier free-disk gate failed")
    public, private = _root(config, "static", False), _root(config, "static", True)
    files = SAFE.require_safe_root(public, private=False)
    allowed = [{"static.json"}, {"static.json", "static-verification.json"}, set(config["outputs"]["public_success_allowlist"])]
    if files not in allowed:
        raise ValueError("Diagnostic static public prefix drift")
    SAFE.require_file_modes(public, sorted(files), private=False)
    existing_verification = public / "static-verification.json"
    if existing_verification.exists():
        prior = SAFE.require_canonical_json(existing_verification)
        if prior.get("status") != "Passed" or prior.get("failed_count") != 0:
            raise ValueError("Failed static verification cannot resume")
    elif complete:
        raise ValueError("Static completion requires an existing Passed prefix")
    if not complete and (public / "no-result-complete.json").exists():
        raise ValueError("Static verify cannot consume completion")
    require_inventory(private, ["input-contract-manifest.json"], private=True)
    for private_flag in (False, True):
        if os.path.lexists(_root(config, "diagnostic", private_flag)):
            raise ValueError("Diagnostic formal root exists during static verification")
    before = source_snapshot(config)
    headers = inspect_sources(config)
    synthetic = synthetic_summary(config, execute=True)
    run_path, input_path = _validate_static_payloads(config_path, config, before, headers, synthetic)
    if source_snapshot(config) != before:
        raise ValueError("Diagnostic static source changed")
    inspect_sources(config)
    if time.monotonic() - started > 7200 or _peak_rss_bytes() > 4294967296:
        raise ValueError("Diagnostic static verifier resource ceiling exceeded")
    verification_path, completion_path = public / "static-verification.json", public / "no-result-complete.json"
    expected = _static_verification_payload(config_path, config, before, run_path, input_path, synthetic)
    if verification_path.exists():
        if SAFE.require_canonical_json(verification_path) != expected:
            raise ValueError("Diagnostic static verification prefix drift")
    elif complete:
        raise ValueError("Diagnostic static completion requires Passed verification")
    else:
        SAFE.create_json_once(verification_path, expected)
    if not complete:
        if completion_path.exists():
            raise ValueError("Static verify cannot consume completion")
        require_inventory(public, ["static.json", "static-verification.json"], private=False)
        return expected
    completion = _static_completion_payload(config_path, config, before, run_path, input_path, verification_path)
    if completion_path.exists():
        if SAFE.require_canonical_json(completion_path) != completion:
            raise ValueError("Diagnostic static completion prefix drift")
    else:
        SAFE.create_json_once(completion_path, completion)
    require_inventory(public, config["outputs"]["public_success_allowlist"], private=False)
    return completion


def _preflight_completion(config: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Path:
    parent = config["preflight"]
    if set(parent) != {"config", "static_run", "static_verification", "no_result_completion", "required_statuses", "diagnostic_execution_authorized_by_preflight"}:
        raise ValueError("Diagnostic preflight binding schema drift")
    if parent["required_statuses"] != {"static_run": "CompletedAwaitingVerification", "static_verification": "Passed", "no_result_completion": "Complete"} or parent["diagnostic_execution_authorized_by_preflight"] is not True:
        raise ValueError("Diagnostic preflight activation drift")
    paths = {}
    for key in ("config", "static_run", "static_verification", "no_result_completion"):
        if set(parent[key]) != {"path", "bytes", "mode", "sha256"}:
            raise ValueError("Diagnostic preflight artifact schema drift")
        paths[key] = require_record(parent[key])
    if paths["config"] != DEFAULT_STATIC_CONFIG.resolve():
        raise ValueError("Diagnostic preflight config path drift")
    static = load_config(paths["config"], "static")
    for key in ("source", "method", "incident", "method_protocol", "implementation", "environment", "resources"):
        if static[key] != config[key]:
            raise ValueError("Diagnostic static/formal contract drift")
    for key in ("formal_public_root", "formal_private_root", "public_directory_mode", "public_file_mode", "private_directory_mode", "private_file_mode"):
        if static["outputs"][key] != config["outputs"][key]:
            raise ValueError("Diagnostic static/formal output binding drift")
    public, private = _root(static, "static", False), _root(static, "static", True)
    require_inventory(public, static["outputs"]["public_success_allowlist"], private=False)
    require_inventory(private, ["input-contract-manifest.json"], private=True)
    expected_paths = {"static_run": public / "static.json", "static_verification": public / "static-verification.json", "no_result_completion": public / "no-result-complete.json"}
    if any(paths[key] != path for key, path in expected_paths.items()):
        raise ValueError("Diagnostic preflight artifact path drift")
    if source_snapshot(static) != snapshot:
        raise ValueError("Diagnostic preflight shared snapshot drift")
    run = SAFE.require_canonical_json(paths["static_run"])
    synthetic = run.get("synthetic_tests")
    _validate_synthetic_record(static, synthetic)
    run_path, input_path = _validate_static_payloads(paths["config"], static, snapshot, inspect_sources(static), synthetic)
    expected_verification = _static_verification_payload(paths["config"], static, snapshot, run_path, input_path, synthetic)
    if SAFE.require_canonical_json(paths["static_verification"]) != expected_verification:
        raise ValueError("Diagnostic preflight verification replay drift")
    expected_completion = _static_completion_payload(paths["config"], static, snapshot, run_path, input_path, paths["static_verification"])
    if SAFE.require_canonical_json(paths["no_result_completion"]) != expected_completion:
        raise ValueError("Diagnostic preflight completion replay drift")
    return paths["no_result_completion"]


def _validate_diagnostic_payloads(
    config_path: Path, config: Mapping[str, Any], snapshot: Mapping[str, Any],
    headers: Mapping[str, Any], preflight_completion: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    public, private = _root(config, "diagnostic", False), _root(config, "diagnostic", True)
    input_path, claim_path = private / "input-manifest.json", public / "run-claim.json"
    manifest_path, run_path = private / "diagnostic-manifest.json", public / "run.json"
    input_doc, claim = SAFE.require_canonical_json(input_path), SAFE.require_canonical_json(claim_path)
    expected_input = {
        **_base_payload(config, "input"), "status": "Initialized", "config": artifact(config_path),
        "preflight_completion": artifact(preflight_completion), "method_sha256": METHOD_SHA256,
        "source_snapshot": snapshot, **headers, "access": STATIC_ACCESS,
    }
    _check_equal(input_doc, expected_input, set(expected_input))
    expected_claim = {
        **_base_payload(config, "claim"), "stage": "initialize", "status": "Initialized",
        "config": artifact(config_path), "input_manifest": artifact(input_path, logical_name=input_path.name),
        "preflight_completion": artifact(preflight_completion), "method_sha256": METHOD_SHA256,
        "source_snapshot_sha256": snapshot["sha256"], "source_snapshot_scope": SNAPSHOT_SCOPE,
        "access": STATIC_ACCESS, "claim_boundary": config["claim_boundary"],
    }
    _check_equal(claim, expected_claim, set(expected_claim))
    validate_public_payload(claim)
    manifest, run = SAFE.require_canonical_json(manifest_path), SAFE.require_canonical_json(run_path)
    localization = manifest.get("localization")
    validate_localization(localization)
    expected_manifest = {
        **_base_payload(config, "manifest"), "status": "Sealed", "config": artifact(config_path),
        "input_manifest": artifact(input_path, logical_name=input_path.name), "method_sha256": METHOD_SHA256,
        "source_before": snapshot, "source_after": snapshot, "localization": localization,
        "access": DIAGNOSTIC_ACCESS,
    }
    _check_equal(manifest, expected_manifest, set(expected_manifest) | {"resources"})
    if set(manifest["resources"]) != {"elapsed_seconds", "peak_rss_bytes", "api_cost_usd"}:
        raise ValueError("Diagnostic manifest resource schema drift")
    validate_resources(manifest["resources"], config, private_root=private)
    expected_run = {
        **_base_payload(config, "run"), "stage": "diagnose", "status": "CompletedAwaitingVerification",
        "tier": config["tier"], "rq_id": config["rq_id"],
        "config": artifact(config_path), "input_manifest": artifact(input_path, logical_name=input_path.name),
        "diagnostic_manifest": artifact(manifest_path, logical_name=manifest_path.name),
        "method_sha256": METHOD_SHA256, "source_snapshot_sha256": snapshot["sha256"],
        "source_snapshot_scope": SNAPSHOT_SCOPE, "localization": localization, "access": DIAGNOSTIC_ACCESS,
        "diagnostic_complete": False, "exp071_complete": False, "recovery_authorized": False,
        "exp072_authorized": False, "claim_boundary": config["claim_boundary"],
    }
    _check_equal(run, expected_run, set(expected_run) | {"resources", "execution"})
    validate_execution(run["execution"], config)
    if set(run["resources"]) != {"elapsed_seconds", "peak_rss_bytes", "api_cost_usd", "private_output_bytes"}:
        raise ValueError("Diagnostic run resource schema drift")
    if {key: run["resources"][key] for key in manifest["resources"]} != manifest["resources"]:
        raise ValueError("Diagnostic run/manifest resource binding drift")
    validate_resources(run["resources"], config, private_root=private)
    validate_public_payload(run)
    return manifest, run


def _diagnostic_verification_payload(
    config_path: Path, config: Mapping[str, Any], snapshot: Mapping[str, Any],
    preflight_completion: Path, localization: Mapping[str, Any],
) -> dict[str, Any]:
    public, private = _root(config, "diagnostic", False), _root(config, "diagnostic", True)
    value = {
        **_base_payload(config, "verification"), "stage": "diagnostic-verify", "status": "Passed",
        "passed_count": len(DIAGNOSTIC_CHECKS), "failed_count": 0, "checks": DIAGNOSTIC_CHECKS,
        "config": artifact(config_path), "preflight_completion": artifact(preflight_completion),
        "run_claim": artifact(public / "run-claim.json"), "run": artifact(public / "run.json"),
        "input_manifest": artifact(private / "input-manifest.json", logical_name="input-manifest.json"),
        "diagnostic_manifest": artifact(private / "diagnostic-manifest.json", logical_name="diagnostic-manifest.json"),
        "method_sha256": METHOD_SHA256, "source_snapshot_sha256": snapshot["sha256"],
        "source_snapshot_scope": SNAPSHOT_SCOPE, "localization": localization, "access": DIAGNOSTIC_ACCESS,
        "diagnostic_complete": False, "exp071_complete": False, "recovery_authorized": False,
        "exp072_authorized": False, "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(value)
    return value


def _diagnostic_completion_payload(
    config_path: Path, config: Mapping[str, Any], snapshot: Mapping[str, Any],
    verification_path: Path, localization: Mapping[str, Any],
) -> dict[str, Any]:
    public, private = _root(config, "diagnostic", False), _root(config, "diagnostic", True)
    value = {
        **_base_payload(config, "complete"), "stage": "diagnostic-complete", "status": "Complete",
        "config": artifact(config_path), "run": artifact(public / "run.json"),
        "verification": artifact(verification_path),
        "diagnostic_manifest": artifact(private / "diagnostic-manifest.json", logical_name="diagnostic-manifest.json"),
        "method_sha256": METHOD_SHA256, "source_snapshot_sha256": snapshot["sha256"],
        "source_snapshot_scope": SNAPSHOT_SCOPE, "localization": localization,
        "diagnostic_complete": True, "original_exp071_status": "Failed", "exp071_complete": False,
        "recovery_authorized": False, "exp072_authorized": False, "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(value)
    return value


def verify_diagnostic(config_path: Path, *, complete: bool) -> dict[str, Any]:
    started = time.monotonic()
    config_path = config_path.resolve()
    config = load_config(config_path, "diagnostic")
    require_implementation(config)
    _require_no_producer_or_model_import()
    SAFE.require_environment(config)
    with diagnostic_lock():
        public, private = _root(config, "diagnostic", False), _root(config, "diagnostic", True)
        files = SAFE.require_safe_root(public, private=False)
        allowed = [set(config["outputs"][key]) for key in ("public_diagnosed_allowlist", "public_verified_allowlist", "public_success_allowlist")]
        if files not in allowed:
            raise ValueError("Diagnostic formal failed or unexpected prefix")
        SAFE.require_file_modes(public, sorted(files), private=False)
        existing_verification = public / "verification.json"
        if existing_verification.exists():
            prior = SAFE.require_canonical_json(existing_verification)
            if prior.get("status") != "Passed" or prior.get("failed_count") != 0:
                raise ValueError("Failed diagnostic verification cannot resume")
        elif complete:
            raise ValueError("Diagnostic completion requires an existing Passed prefix")
        if not complete and (public / "diagnostic-complete.json").exists():
            raise ValueError("Diagnostic verify cannot consume completion")
        require_inventory(private, config["outputs"]["private_success_allowlist"], private=True)
        if shutil.disk_usage(PROJECT_ROOT).free < config["resources"]["minimum_free_disk_bytes"]:
            raise ValueError("Diagnostic verifier free-disk gate failed")
        before = source_snapshot(config)
        headers = inspect_sources(config)
        completion_source = _preflight_completion(config, before)
        manifest, _run = _validate_diagnostic_payloads(config_path, config, before, headers, completion_source)
        localization = recompute_localization(config, started)
        if localization != manifest["localization"]:
            raise ValueError("Independent diagnostic localization mismatch")
        if source_snapshot(config) != before:
            raise ValueError("Diagnostic source changed during independent verification")
        inspect_sources(config)
        for key in ("config", "static_run", "static_verification", "no_result_completion"):
            require_record(config["preflight"][key])
        if time.monotonic() - started > 7200 or _peak_rss_bytes() > 4294967296:
            raise ValueError("Diagnostic verifier resource ceiling exceeded")
        _require_no_producer_or_model_import()
        verification_path, completion_path = public / "verification.json", public / "diagnostic-complete.json"
        expected = _diagnostic_verification_payload(config_path, config, before, completion_source, localization)
        if verification_path.exists():
            if SAFE.require_canonical_json(verification_path) != expected:
                raise ValueError("Diagnostic verification prefix drift")
        elif complete:
            raise ValueError("Diagnostic completion requires Passed verification")
        else:
            SAFE.create_json_once(verification_path, expected)
        if not complete:
            if completion_path.exists():
                raise ValueError("Diagnostic verify cannot consume completion")
            require_inventory(public, config["outputs"]["public_verified_allowlist"], private=False)
            return expected
        completion = _diagnostic_completion_payload(config_path, config, before, verification_path, localization)
        if completion_path.exists():
            if SAFE.require_canonical_json(completion_path) != completion:
                raise ValueError("Diagnostic completion replay drift")
        else:
            SAFE.create_json_once(completion_path, completion)
        require_inventory(public, config["outputs"]["public_success_allowlist"], private=False)
        return completion


def _record_failure(config_path: Path, kind: str, error: BaseException) -> None:
    try:
        config = load_config(config_path.resolve(), kind)
        public = _root(config, kind, False)
        prerequisite = public / ("static.json" if kind == "static" else "run.json")
        target = public / ("static-verification.json" if kind == "static" else "verification.json")
        SAFE.require_safe_root(public, private=False)
        if not prerequisite.is_file() or prerequisite.is_symlink() or prerequisite.stat().st_nlink != 1 or SAFE.file_mode(prerequisite) != "0644" or os.path.lexists(target):
            return
        value = {
            **_base_payload(config, "verification-failure"), "stage": f"{kind}-verify", "status": "Failed",
            "error_code": "failure_not_reproduced" if isinstance(error, FailureNotReproduced) else "verification_failed",
            "error_type": type(error).__name__, "diagnostic_complete": False, "exp071_complete": False,
            "recovery_authorized": False, "exp072_authorized": False,
        }
        SAFE.create_json_once(target, value)
    except Exception:
        return


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("static-verify", "static-complete", "diagnostic-verify", "diagnostic-complete"))
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    kind, phase = args.stage.split("-", 1)
    config_path = (args.config or (DEFAULT_STATIC_CONFIG if kind == "static" else DEFAULT_DIAGNOSTIC_CONFIG)).resolve()
    try:
        result = verify_static(config_path, complete=phase == "complete") if kind == "static" else verify_diagnostic(config_path, complete=phase == "complete")
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:
        if phase == "verify":
            _record_failure(config_path, kind, error)
        error_code = "failure_not_reproduced" if isinstance(error, FailureNotReproduced) else "verification_failed"
        print(json.dumps({"stage": args.stage, "status": "Failed", "error_code": error_code, "error_type": type(error).__name__}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"stage": args.stage, "status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

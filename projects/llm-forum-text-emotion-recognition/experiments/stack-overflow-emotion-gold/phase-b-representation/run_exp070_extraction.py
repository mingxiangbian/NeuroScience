#!/usr/bin/env python3
"""Run the staged, extraction-only formal producer for EXP-070.

The frozen default config must provide:

* ``parent_no_result`` records named ``config``, ``run``, ``verification``,
  ``completion`` and ``input_contract``;
* ``authorization`` booleans ``initialize``, ``formal_extraction``, ``model_loading``,
  ``forward`` and ``train_text`` set true, with label/probe/metric/validation/test access false;
* the fixed formal ``outputs`` public/private roots and heavy-workload lock;
* the exact 16-item ``workers`` list returned by :func:`expected_worker_plan`.

Only private ``progress.json`` files are replaceable. All evidence artifacts are
created once. A killed process may resume the continuous committed chunk prefix;
an explicit exception records a terminal public failure and blocks later stages.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import shutil
import stat
import sys
import time
from typing import Any, Iterator, Sequence

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-070-formal-extraction.json"
NO_RESULT_CONFIG = MODULE_DIR / "configs" / "exp-070-layerwise-probe-preflight.json"
EXP069_RUNNER = MODULE_DIR / "run_exp069_preflight.py"

EXPERIMENT_ID = "EXP-070"
RUN_ID = "exp-070-layerwise-probe-formal-extraction"
ATTEMPT_ID = "formal-attempt-1"
ROWS = 3360
HIDDEN_SIZE = 2560
CHUNK_ROWS = 32
SEEDS = (42, 43, 44)
FOLDS = (0, 1, 2, 3, 4)
ALL_POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
CONFIRMATION_POINTS = ("H19", "H27", "HF")
PRE_LORA_POINTS = ("H-1", "H7", "H15", "H19")
SMOKE_ORDINALS = (
    0, 108, 217, 325, 433, 542, 650, 758,
    867, 975, 1084, 1192, 1300, 1409, 1517, 1625,
    1734, 1842, 1950, 2059, 2167, 2275, 2384, 2492,
    2601, 2709, 2817, 2926, 3034, 3142, 3251, 3359,
)
PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-extraction-attempt-1"
)
PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-070-layerwise-probes/formal-extraction-attempt-1"
)
HEAVY_LOCK = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/locks/"
    "heavy-research-workload.lock"
)
PARENT_PATHS = {
    "config": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/configs/"
        "exp-070-layerwise-probe-preflight.json"
    ),
    "run": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
        "exp-070-layerwise-probe-preflight/attempt-1/static.json"
    ),
    "verification": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
        "exp-070-layerwise-probe-preflight/attempt-1/static-verification.json"
    ),
    "completion": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
        "exp-070-layerwise-probe-preflight/attempt-1/no-result-complete.json"
    ),
    "input_contract": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
        "exp-070-layerwise-probe-preflight/attempt-1/input-contract-manifest.json"
    ),
}
EXPECTED_NONSELF_CONFIG_SHA256 = "60a5d9cc0fcade65770ebe239731f3d664a4836bc9a4e90791594349864885ae"


def _no_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(payload: bytes) -> Any:
    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_no_constant,
    )


def strict_json(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def resolve_project(relative: str, *, must_exist: bool = True) -> Path:
    if type(relative) is not str:
        raise TypeError("Project path must be a string")
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or pure.as_posix() != relative:
        raise ValueError("Unsafe project path")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe project path")
    path = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError("Symlink path rejected")
    if must_exist and not os.path.lexists(path):
        raise FileNotFoundError(path)
    return path


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Unsafe or missing artifact: {path}")
    result: dict[str, Any] = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        result["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        result["logical_name"] = logical_name
    return result


def require_record(record: dict[str, Any], *, expected_path: str | None = None) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    if expected_path is not None and record["path"] != expected_path:
        raise ValueError("Artifact record path drift")
    path = resolve_project(record["path"])
    if artifact(path) != record:
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def create_json_once(path: Path, value: Any, *, private: bool = False) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    directory_mode = 0o700 if private else 0o755
    mode = 0o600 if private else 0o644
    path.parent.mkdir(parents=True, exist_ok=True, mode=directory_mode)
    os.chmod(path.parent, directory_mode)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.link(temporary, path)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def replace_private_json(path: Path, value: Any) -> None:
    """Atomically replace mutable private technical state."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def save_npz_once(path: Path, **arrays: np.ndarray) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with temporary.open("xb") as handle:
            np.savez(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.link(temporary, path)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def expected_worker_plan() -> list[dict[str, Any]]:
    plan = [
        {
            "worker_id": "base",
            "kind": "base",
            "seed": None,
            "fold": None,
            "points": list(ALL_POINTS),
            "shape": [ROWS, len(ALL_POINTS), HIDDEN_SIZE],
            "payload_bytes": ROWS * len(ALL_POINTS) * HIDDEN_SIZE * 4,
        }
    ]
    for seed in SEEDS:
        points = ALL_POINTS if seed == 42 else CONFIRMATION_POINTS
        for fold in FOLDS:
            plan.append(
                {
                    "worker_id": f"m3-s{seed}-f{fold}",
                    "kind": "m3",
                    "seed": seed,
                    "fold": fold,
                    "points": list(points),
                    "shape": [ROWS, len(points), HIDDEN_SIZE],
                    "payload_bytes": ROWS * len(points) * HIDDEN_SIZE * 4,
                }
            )
    return plan


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("EXP-070 extraction requires the frozen default config")
    config = strict_json(path)
    if set(config) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "rq_id", "tier",
        "registered_at", "method_protocol", "formal_protocol", "parent_no_result",
        "sources", "environment", "workers", "extraction", "resources", "authorization",
        "access_history", "outputs", "implementation", "claim_boundary",
    }:
        raise ValueError("EXP-070 formal extraction config schema drift")
    nonself = {key: value for key, value in config.items() if key != "implementation"}
    if bytes_sha256(canonical_json_bytes(nonself)) != EXPECTED_NONSELF_CONFIG_SHA256:
        raise ValueError("EXP-070 formal extraction non-self config drift")
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or config.get("schema_version") != "exp-070-formal-extraction-config-v1"
    ):
        raise ValueError("EXP-070 formal extraction identity drift")
    if config.get("workers") != expected_worker_plan():
        raise ValueError("EXP-070 worker plan drift")
    outputs = config.get("outputs", {})
    if outputs != {
        "public_root": PUBLIC_ROOT,
        "private_root": PRIVATE_ROOT,
        "heavy_lock": HEAVY_LOCK,
        "public_allowlist": [
            "run-claim.json", "extraction.json", "extraction-verification.json",
            "extraction-complete.json", "failure.json",
        ],
        "private_top_level_allowlist": [
            "input-manifest.json", "row-contract.npz", "extraction", "extraction-manifest.json",
        ],
    }:
        raise ValueError("EXP-070 extraction output contract drift")
    authorization = config.get("authorization", {})
    expected_true = {"initialize", "formal_extraction", "model_loading", "forward", "train_text"}
    expected_false = {
        "train_label_values", "heldout_gold", "training", "probe_fitting",
        "threshold_selection", "label_shuffle", "bootstrap", "performance_metrics",
        "validation", "test", "formal_completion", "exp071",
    }
    if any(authorization.get(key) is not True for key in expected_true) or any(
        authorization.get(key) is not False for key in expected_false
    ):
        raise PermissionError("EXP-070 extraction authorization drift")
    if authorization.get("historical_heldout_members") != ["sample_ids", "fold_ids", "logits"]:
        raise PermissionError("EXP-070 heldout-member authorization drift")
    if set(authorization) != expected_true | expected_false | {"historical_heldout_members"}:
        raise PermissionError("EXP-070 authorization inventory drift")
    if config.get("access_history") != {
        "design_time_train_rows_displayed": 2,
        "used_for_method_or_result_selection": False,
        "model_loaded": False,
        "forward_executed": False,
        "metrics_computed": False,
        "validation_accessed": False,
        "test_accessed": False,
        "disposition": "recorded_and_excluded_from_scientific_use",
    }:
        raise ValueError("EXP-070 access-history drift")
    parent = config.get("parent_no_result")
    if not isinstance(parent, dict) or set(parent) != set(PARENT_PATHS):
        raise ValueError("EXP-070 parent preflight schema drift")
    for key, expected_path in PARENT_PATHS.items():
        require_record(parent[key], expected_path=expected_path)
    require_record(config["method_protocol"])
    require_record(config["formal_protocol"])
    if set(config.get("sources", {})) != {
        "exp069_config", "exp069_input_manifest", "exp069_runner", "gitignore"
    }:
        raise ValueError("EXP-070 source inventory drift")
    for record in config["sources"].values():
        require_record(record)
    gitignore = require_record(config["sources"]["gitignore"])
    if "private/" not in gitignore.read_text(encoding="utf-8").splitlines():
        raise ValueError("EXP-070 private ignore rule drift")
    implementation = config.get("implementation", {})
    if set(implementation) != {"runner", "verifier", "tests"}:
        raise ValueError("EXP-070 implementation inventory drift")
    for record in implementation.values():
        require_record(record)
    extraction = config.get("extraction", {})
    if int(extraction.get("chunk_rows", CHUNK_ROWS)) != CHUNK_ROWS:
        raise ValueError("EXP-070 chunk-size drift")
    representation = extraction
    if (
        representation.get("rows") != ROWS
        or representation.get("hidden_size") != HIDDEN_SIZE
        or representation.get("dtype") != "float32"
        or representation.get("all_points") != list(ALL_POINTS)
        or config["workers"][0]["points"] != list(ALL_POINTS)
        or config["workers"][6]["points"] != list(CONFIRMATION_POINTS)
        or representation.get("pre_lora_points") != list(PRE_LORA_POINTS)
        or representation.get("transient_confirmation_points") != ["H-1", "H7", "H15"]
        or representation.get("rtol") != 0.0
        or representation.get("atol") != 1e-5
        or representation.get("raw_payload_bytes") != 2_890_137_600
    ):
        raise ValueError("EXP-070 representation contract drift")
    return config


def public_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["public_root"], must_exist=False)


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["private_root"], must_exist=False)


def worker_dir(config: dict[str, Any], worker_id: str) -> Path:
    if worker_id not in {item["worker_id"] for item in expected_worker_plan()}:
        raise ValueError("Unknown EXP-070 extraction worker")
    return private_root(config) / "extraction" / worker_id


def _record_from_logical(record: dict[str, Any], root: Path) -> Path:
    if set(record) != {"logical_name", "bytes", "mode", "sha256"}:
        raise ValueError("Logical artifact record schema drift")
    pure = PurePosixPath(record["logical_name"])
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe logical artifact path")
    path = root.joinpath(*pure.parts)
    if artifact(path, logical_name=record["logical_name"]) != record:
        raise ValueError("Logical artifact identity drift")
    return path


def require_parent_gate(config: dict[str, Any]) -> dict[str, Any]:
    parent = config["parent_no_result"]
    parent_config = strict_json(require_record(parent["config"], expected_path=PARENT_PATHS["config"]))
    run = strict_json(require_record(parent["run"], expected_path=PARENT_PATHS["run"]))
    verification = strict_json(
        require_record(parent["verification"], expected_path=PARENT_PATHS["verification"])
    )
    completion = strict_json(
        require_record(parent["completion"], expected_path=PARENT_PATHS["completion"])
    )
    input_contract = strict_json(
        require_record(parent["input_contract"], expected_path=PARENT_PATHS["input_contract"])
    )
    if (
        run.get("status") != "CompletedAwaitingVerification"
        or verification.get("status") != "Passed"
        or verification.get("passed_count") != 24
        or verification.get("failed_count") != 0
        or completion.get("status") != "Complete"
        or completion.get("formal_execution_authorized") is not False
        or completion.get("exp070_formal_complete") is not False
        or completion.get("exp071_authorized") is not False
        or completion.get("run") != parent["run"]
        or completion.get("verification") != parent["verification"]
        or completion.get("input_contract")
        != {
            "logical_name": "input-contract-manifest.json",
            "bytes": parent["input_contract"]["bytes"],
            "mode": parent["input_contract"]["mode"],
            "sha256": parent["input_contract"]["sha256"],
        }
        or input_contract.get("status") != "Registered"
        or input_contract.get("source_snapshot_sha256") != run.get("source_snapshot_sha256")
        or input_contract.get("smoke_rows_usable_for_probe_fitting") is not False
    ):
        raise ValueError("EXP-070 no-result completion binding drift")
    original_record = config["sources"]["exp069_config"]
    original_config = strict_json(require_record(original_record))
    if original_record != parent_config["parent_exp069"]["original_config"]:
        raise ValueError("EXP-069 config parent binding drift")
    runner_path = require_record(config["sources"]["exp069_runner"])
    if config["sources"]["exp069_runner"] != original_config["implementation"]["runner"]:
        raise ValueError("EXP-069 runner parent binding drift")
    source_manifest_record = input_contract["source_snapshot"]["files"]["input-manifest.json"]
    if config["sources"]["exp069_input_manifest"] != source_manifest_record:
        raise ValueError("EXP-069 input-manifest parent binding drift")
    formal_environment = config["environment"]
    expected_environment = {
        key: original_config["environment"][key]
        for key in ("python_executable", "python_version", "architecture", "packages", "offline_environment")
    }
    if formal_environment != expected_environment:
        raise ValueError("EXP-070 formal environment contract drift")
    if runner_path.resolve() != EXP069_RUNNER.resolve():
        raise ValueError("EXP-069 runner source drift")
    return {
        "parent_config": parent_config,
        "run": run,
        "verification": verification,
        "completion": completion,
        "input_contract": input_contract,
        "original_config": original_config,
        "exp069_runner": artifact(runner_path),
    }


def _load_exp069(record: dict[str, Any]) -> Any:
    path = require_record(record)
    spec = importlib.util.spec_from_file_location("exp069_frozen_for_exp070", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("qwen_prompt_ids", "lora_identity", "token_stream_digest"):
        if not callable(getattr(module, name, None)):
            raise ValueError(f"Missing frozen EXP-069 helper: {name}")
    return module


def require_source_snapshot(input_contract: dict[str, Any]) -> None:
    snapshot = input_contract.get("source_snapshot")
    if set(snapshot or {}) != {
        "files", "npz_headers", "checkpoint_files", "fold_lineage_files", "model_files"
    }:
        raise ValueError("EXP-070 parent source snapshot schema drift")
    for family in ("files", "checkpoint_files", "fold_lineage_files", "model_files"):
        records = snapshot[family]
        if not isinstance(records, dict):
            raise ValueError("EXP-070 parent source record inventory drift")
        for record in records.values():
            require_record(record)
    observed = bytes_sha256(canonical_json_bytes(snapshot))
    if observed != input_contract.get("source_snapshot_sha256"):
        raise ValueError("EXP-070 parent source snapshot digest drift")


def require_environment(original: dict[str, Any]) -> None:
    expected = original["environment"]
    if os.path.realpath(sys.executable) != os.path.realpath(expected["python_executable"]):
        raise PermissionError("EXP-070 extraction Python drift")
    if platform.python_version() != expected["python_version"] or platform.machine() != expected["architecture"]:
        raise PermissionError("EXP-070 extraction platform drift")
    observed = {
        name: importlib.metadata.version(name)
        for name in expected["packages"]
    }
    if observed != expected["packages"]:
        raise PermissionError("EXP-070 extraction package drift")
    for key, value in expected["offline_environment"].items():
        if os.environ.get(key) != value:
            raise PermissionError(f"EXP-070 extraction environment flag drift: {key}")
    source = expected["qwen3_source"]
    path = Path(source["path"])
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or path.stat().st_size != source["bytes"]
        or file_mode(path) != source["mode"]
        or sha256(path) != source["sha256"]
    ):
        raise ValueError("EXP-070 Qwen source identity drift")


def _string_sequence_digest(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        payload = value.encode("utf-8")
        digest.update(len(payload).to_bytes(4, "little", signed=False))
        digest.update(payload)
    return digest.hexdigest()


def _array_digest(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    return bytes_sha256(array.tobytes(order="C"))


def _load_fold_rows(original: dict[str, Any]) -> list[dict[str, Any]]:
    path = require_record(original["data"]["fold_manifest_public"])
    rows: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            value = strict_json_bytes(line)
            if (
                value.get("protocol_id") != "DATA-SO-TASK-V1"
                or value.get("fold_id") not in FOLDS
                or not isinstance(value.get("sample_id"), str)
                or not isinstance(value.get("component_id"), str)
            ):
                raise ValueError("EXP-070 fold row schema drift")
            rows.append(
                {
                    "ordinal": ordinal,
                    "sample_id": value["sample_id"],
                    "component_id": value["component_id"],
                    "fold_id": int(value["fold_id"]),
                }
            )
    if len(rows) != ROWS:
        raise ValueError("EXP-070 fold row count drift")
    if len({row["sample_id"] for row in rows}) != ROWS:
        raise ValueError("EXP-070 sample identity duplicate")
    if [sum(row["fold_id"] == fold for row in rows) for fold in FOLDS] != [672] * 5:
        raise ValueError("EXP-070 fold count drift")
    return rows


def _row_identity(rows: Sequence[dict[str, Any]], component_code: np.ndarray) -> dict[str, Any]:
    ordinal = np.arange(ROWS, dtype=np.int32)
    fold_id = np.asarray([row["fold_id"] for row in rows], dtype=np.int8)
    return {
        "ordinal_sha256": _array_digest(ordinal),
        "sample_id_order_sha256": _string_sequence_digest([row["sample_id"] for row in rows]),
        "component_id_order_sha256": _string_sequence_digest([row["component_id"] for row in rows]),
        "fold_id_order_sha256": _array_digest(fold_id),
        "component_code_sha256": _array_digest(component_code),
        "component_count": int(len(np.unique(component_code))),
    }


def _build_row_contract(config: dict[str, Any], original: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = _load_fold_rows(original)
    components = sorted({row["component_id"] for row in rows})
    if len(components) != 3277:
        raise ValueError("EXP-070 component count drift")
    code = {value: index for index, value in enumerate(components)}
    component_code = np.asarray([code[row["component_id"]] for row in rows], dtype=np.int32)
    arrays = {
        "ordinal": np.arange(ROWS, dtype=np.int32),
        "fold_id": np.asarray([row["fold_id"] for row in rows], dtype=np.int8),
        "component_code": component_code,
    }
    path = private_root(config) / "row-contract.npz"
    save_npz_once(path, **arrays)
    return artifact(path, logical_name="row-contract.npz"), _row_identity(rows, component_code)


def initialize(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    parent = require_parent_gate(config)
    require_environment(parent["original_config"])
    require_source_snapshot(parent["input_contract"])
    pub = public_root(config)
    priv = private_root(config)
    for path in (pub, priv):
        if os.path.lexists(path):
            raise FileExistsError(f"EXP-070 formal root exists: {path}")
    if shutil.disk_usage(PROJECT_ROOT).free < int(config["resources"]["minimum_free_disk_bytes"]):
        raise OSError("EXP-070 extraction free-disk gate failed")
    priv.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(priv.parent, 0o700)
    priv.mkdir(parents=True, mode=0o700)
    os.chmod(priv, 0o700)
    row_contract, row_identity = _build_row_contract(config, parent["original_config"])
    manifest = {
        "schema_version": "exp-070-extraction-input-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Initialized",
        "config": artifact(config_path),
        "parent_no_result": config["parent_no_result"],
        "parent_source_snapshot_sha256": parent["input_contract"]["source_snapshot_sha256"],
        "exp069_runner": parent["exp069_runner"],
        "row_contract": row_contract,
        "row_identity": row_identity,
        "workers": expected_worker_plan(),
        "access_history": config["access_history"],
        "access": {
            "fold_manifest_values_read": True,
            "train_text_accessed": False,
            "train_label_values_used": False,
            "model_loaded": False,
            "forward_executed": False,
            "probe_fitted": False,
            "performance_metrics_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
    }
    manifest_path = priv / "input-manifest.json"
    create_json_once(manifest_path, manifest, private=True)
    claim = {
        "schema_version": "exp-070-extraction-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "stage": "formal-extraction",
        "status": "Initialized",
        "config": artifact(config_path),
        "parent_completion": config["parent_no_result"]["completion"],
        "input_manifest": artifact(manifest_path, logical_name="input-manifest.json"),
        "worker_count": 16,
        "access_history": config["access_history"],
        "formal_probe_authorized": False,
        "performance_metrics_authorized": False,
        "validation_access": False,
        "test_access": False,
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(pub / "run-claim.json", claim)
    return claim


def require_initialized(config_path: Path, config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    require_parent_gate(config)
    pub = public_root(config)
    priv = private_root(config)
    failure = pub / "failure.json"
    if os.path.lexists(failure):
        raise RuntimeError("EXP-070 extraction attempt is terminal Failed")
    claim_path = pub / "run-claim.json"
    manifest_path = priv / "input-manifest.json"
    if not claim_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("EXP-070 extraction is not initialized")
    claim = strict_json(claim_path)
    manifest = strict_json(manifest_path)
    if (
        claim.get("status") != "Initialized"
        or claim.get("config") != artifact(config_path)
        or claim.get("input_manifest") != artifact(manifest_path, logical_name="input-manifest.json")
        or claim.get("access_history") != config["access_history"]
        or claim.get("claim_boundary") != config["claim_boundary"]
        or manifest.get("status") != "Initialized"
        or manifest.get("config") != artifact(config_path)
        or manifest.get("workers") != expected_worker_plan()
        or manifest.get("access_history") != config["access_history"]
    ):
        raise ValueError("EXP-070 initialization binding drift")
    row_path = _record_from_logical(manifest["row_contract"], priv)
    with np.load(row_path, allow_pickle=False) as archive:
        if set(archive.files) != {"ordinal", "fold_id", "component_code"}:
            raise ValueError("EXP-070 row-contract member drift")
        if (
            archive["ordinal"].shape != (ROWS,)
            or archive["fold_id"].shape != (ROWS,)
            or archive["component_code"].shape != (ROWS,)
            or archive["ordinal"].dtype != np.int32
            or archive["fold_id"].dtype != np.int8
            or archive["component_code"].dtype != np.int32
        ):
            raise ValueError("EXP-070 row-contract schema drift")
    return manifest, strict_json(NO_RESULT_CONFIG)


def _load_train_rows(original: dict[str, Any]) -> list[dict[str, Any]]:
    fold_rows = _load_fold_rows(original)
    train_path = require_record(original["data"]["train"])
    rows: list[dict[str, Any]] = []
    with train_path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            value = strict_json_bytes(line)
            expected = fold_rows[ordinal] if ordinal < len(fold_rows) else None
            if (
                expected is None
                or value.get("sample_id") != expected["sample_id"]
                or value.get("component_id") != expected["component_id"]
                or not isinstance(value.get("text"), str)
            ):
                raise ValueError("EXP-070 train source-order drift")
            rows.append(
                {
                    "ordinal": ordinal,
                    "sample_id": value["sample_id"],
                    "component_id": value["component_id"],
                    "fold_id": expected["fold_id"],
                    "text": value["text"],
                }
            )
    if len(rows) != ROWS:
        raise ValueError("EXP-070 train row count drift")
    return rows


def _worker_spec(worker_id: str) -> dict[str, Any]:
    matches = [item for item in expected_worker_plan() if item["worker_id"] == worker_id]
    if len(matches) != 1:
        raise ValueError("EXP-070 worker identity drift")
    return matches[0]


def _validate_worker_manifest(path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    value = strict_json(path)
    final = path.parent / "representations.npy"
    if (
        value.get("schema_version") != "exp-070-extraction-worker-v1"
        or value.get("status") != "Completed"
        or value.get("worker_id") != spec["worker_id"]
        or value.get("kind") != spec["kind"]
        or value.get("seed") != spec["seed"]
        or value.get("fold") != spec["fold"]
        or value.get("points") != spec["points"]
        or value.get("shape") != spec["shape"]
        or value.get("dtype") != "float32"
        or value.get("layout") != "C"
        or value.get("output") != artifact(final, logical_name=f"{spec['worker_id']}/representations.npy")
    ):
        raise ValueError("EXP-070 worker manifest drift")
    return value


def _cleanup_completed_worker(directory: Path) -> None:
    """Remove only validated technical resume state after immutable completion."""
    if (directory / "representations.npy.part").exists():
        raise ValueError("Completed worker retains a partial matrix")
    for name in ("claim.json", "progress.json"):
        path = directory / name
        if path.exists():
            if path.is_symlink() or not path.is_file() or file_mode(path) != "0600":
                raise ValueError("Unsafe completed-worker technical state")
            path.unlink()


def _validate_completed_worker_for_resume(
    config: dict[str, Any],
    spec: dict[str, Any],
    input_manifest: dict[str, Any],
    parent: dict[str, Any],
    common_sources: dict[str, Any],
) -> dict[str, Any]:
    directory = worker_dir(config, spec["worker_id"])
    worker_path = directory / "worker.json"
    allowed = {"representations.npy", "worker.json", "claim.json", "progress.json"}
    entries = list(directory.iterdir()) if directory.is_dir() else []
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or file_mode(directory) != "0700"
        or {path.name for path in entries} - allowed
        or {"representations.npy", "worker.json"} - {path.name for path in entries}
        or any(
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_nlink != 1
            or file_mode(path) != "0600"
            for path in entries
        )
    ):
        raise PermissionError("EXP-070 completed-prefix private inventory or mode drift")
    worker = _validate_worker_manifest(worker_path, spec)
    matrix = np.load(directory / "representations.npy", mmap_mode="r", allow_pickle=False)
    if matrix.shape != tuple(spec["shape"]) or matrix.dtype != np.float32 or not matrix.flags.c_contiguous:
        raise ValueError("EXP-070 completed-prefix matrix schema drift")
    for start in range(0, ROWS, CHUNK_ROWS):
        if not np.isfinite(matrix[start : min(start + CHUNK_ROWS, ROWS)]).all():
            raise ValueError("EXP-070 completed-prefix non-finite matrix")
    expected_access = {
        "label_bearing_train_container_accessed": True,
        "train_text_accessed": True,
        "train_label_values_used": False,
        "heldout_members_read": (
            ["sample_ids", "fold_ids", "logits"] if spec["kind"] == "m3" else []
        ),
        "heldout_gold_read": False,
        "validation_accessed": False,
        "test_accessed": False,
        "model_loaded": True,
        "forward_executed": True,
        "probe_fitted": False,
        "performance_metrics_computed": False,
    }
    expected_sources = _current_worker_sources(
        config,
        parent["original_config"],
        parent["input_contract"]["source_snapshot"],
        spec,
        common_sources=common_sources,
    )
    errors = worker.get("max_errors")
    numeric_values: list[float] = []
    if isinstance(errors, dict) and isinstance(errors.get("pre_lora"), dict):
        numeric_values = [
            float(errors.get("standard_hf", float("nan"))),
            float(errors.get("m2_hf", float("nan"))),
            float(errors.get("heldout_logit", float("nan"))),
            *(float(errors["pre_lora"].get(point, float("nan"))) for point in PRE_LORA_POINTS),
            float(worker.get("adapter_load_max_abs_error", float("nan"))),
            float(worker.get("resources", {}).get("elapsed_seconds", float("nan"))),
            float(worker.get("resources", {}).get("mlx_peak_bytes", float("nan"))),
        ]
    token_digest = worker.get("token_id_stream_sha256")
    if (
        worker.get("row_identity") != input_manifest["row_identity"]
        or not isinstance(token_digest, str)
        or len(token_digest) != 64
        or any(character not in "0123456789abcdef" for character in token_digest)
        or worker.get("source_before") != expected_sources
        or worker.get("source_after") != expected_sources
        or worker.get("access") != expected_access
        or worker.get("checks")
        != {
            "finite_values": True,
            "row_count": ROWS,
            "token_count": ROWS,
            "continuous_chunk_prefix": True,
        }
        or not isinstance(errors, dict)
        or set(errors) != {"standard_hf", "m2_hf", "heldout_logit", "pre_lora"}
        or not isinstance(errors.get("pre_lora"), dict)
        or len(numeric_values) != 10
        or any(not math.isfinite(value) or value < 0.0 for value in numeric_values)
        or set(errors["pre_lora"]) != set(PRE_LORA_POINTS)
        or max(float(errors["pre_lora"][point]) for point in PRE_LORA_POINTS)
        > float(config["extraction"]["atol"])
        or float(errors["standard_hf"])
        > float(parent["original_config"]["smoke"]["tolerances"]["standard_hf_atol"])
        or float(errors["m2_hf"])
        > float(parent["original_config"]["smoke"]["tolerances"]["m2_hf_atol"])
        or float(errors["heldout_logit"])
        > float(parent["original_config"]["smoke"]["tolerances"]["m3_logit_atol"])
        or worker.get("heldout_rows_checked") != (672 if spec["kind"] == "m3" else 0)
        or float(worker.get("adapter_load_max_abs_error", 0.0)) != 0.0
        or float(worker.get("resources", {}).get("elapsed_seconds", float("inf")))
        > float(config["resources"]["worker_wall_hours"]) * 3600.0
        or int(worker.get("resources", {}).get("mlx_peak_bytes", 2**63))
        > float(config["resources"]["worker_peak_mlx_gb"]) * 1e9
    ):
        raise ValueError("EXP-070 completed-prefix contract drift")
    return worker


def _require_worker_turn(
    config: dict[str, Any],
    requested: str,
    input_manifest: dict[str, Any],
    parent: dict[str, Any],
) -> dict[str, Any] | None:
    plan = expected_worker_plan()
    requested_index = next(index for index, item in enumerate(plan) if item["worker_id"] == requested)
    completed = 0
    first_incomplete: int | None = None
    token_digest: str | None = None
    common_sources: dict[str, Any] | None = None
    for index, item in enumerate(plan):
        directory = worker_dir(config, item["worker_id"])
        manifest_path = directory / "worker.json"
        if manifest_path.is_file():
            if first_incomplete is not None:
                raise ValueError("EXP-070 worker completion order drift")
            if common_sources is None:
                common_sources = _common_worker_sources(
                    config,
                    parent["original_config"],
                    parent["input_contract"]["source_snapshot"],
                )
            worker = _validate_completed_worker_for_resume(
                config, item, input_manifest, parent, common_sources
            )
            if token_digest is not None and worker["token_id_stream_sha256"] != token_digest:
                raise ValueError("EXP-070 completed-prefix token stream drift")
            token_digest = worker["token_id_stream_sha256"]
            _cleanup_completed_worker(directory)
            completed += 1
            continue
        if first_incomplete is None:
            first_incomplete = index
        if index > first_incomplete and os.path.lexists(directory):
            raise ValueError("EXP-070 later-worker artifact drift")
    if requested_index < completed:
        assert common_sources is not None
        return _validate_completed_worker_for_resume(
            config, plan[requested_index], input_manifest, parent, common_sources
        )
    if first_incomplete != requested_index:
        raise ValueError("EXP-070 worker invoked out of order")
    return None


@contextmanager
def heavy_mutex(config: dict[str, Any]) -> Iterator[None]:
    path = resolve_project(config["outputs"]["heavy_lock"], must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another heavy research workload is active") from error
        os.fchmod(descriptor, 0o600)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def manual_points(backbone: Any, input_ids: Any, create_attention_mask: Any) -> dict[str, Any]:
    """Extract raw residual points without a second standard forward."""
    core = backbone.model
    if len(core.layers) != 36:
        raise ValueError("Qwen block-count drift")
    hidden = core.embed_tokens(input_ids)
    mask = create_attention_mask(hidden, None)
    points: dict[str, Any] = {"H-1": hidden[:, -1, :]}
    wanted = {7, 15, 19, 20, 27, 31, 35}
    for index, block in enumerate(core.layers):
        hidden = block(hidden, mask, None)
        if index in wanted:
            points[f"H{index}"] = hidden[:, -1, :]
    points["HF"] = core.norm(hidden)[:, -1, :]
    if tuple(points) != ALL_POINTS:
        raise ValueError("EXP-070 representation point order drift")
    return points


def max_abs(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape or not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("Invalid numeric comparison")
    return float(
        np.max(
            np.abs(left.astype(np.float64, copy=False) - right.astype(np.float64, copy=False)),
            initial=0.0,
        )
    )


def _chunk_digest(matrix: np.ndarray, start: int, stop: int) -> str:
    return _array_digest(np.asarray(matrix[start:stop], dtype=np.float32))


def _prepare_partial(
    config: dict[str, Any], spec: dict[str, Any], source_snapshot_sha256: str
) -> tuple[np.memmap, dict[str, Any]]:
    directory = worker_dir(config, spec["worker_id"])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    allowed_names = {
        "claim.json", "representations.npy.part", "progress.json",
        "representations.npy", "worker.json",
    }
    entries = list(directory.iterdir())
    if any(
        path.name not in allowed_names
        or path.is_symlink()
        or (not path.is_file() and not path.is_dir())
        for path in entries
    ) or any(path.is_dir() for path in entries):
        raise ValueError("EXP-070 worker technical inventory drift")
    claim_path = directory / "claim.json"
    claim = {
        "schema_version": "exp-070-extraction-worker-claim-v1",
        "worker": spec,
        "source_snapshot_sha256": source_snapshot_sha256,
    }
    if claim_path.exists():
        if file_mode(claim_path) != "0600":
            raise PermissionError("EXP-070 worker claim mode drift")
        if strict_json(claim_path) != claim:
            raise ValueError("EXP-070 worker claim drift")
    else:
        create_json_once(claim_path, claim, private=True)
    part = directory / "representations.npy.part"
    final = directory / "representations.npy"
    progress_path = directory / "progress.json"
    if final.exists():
        if file_mode(final) != "0600":
            raise PermissionError("EXP-070 orphan final cache mode drift")
        if not progress_path.exists():
            raise ValueError("EXP-070 orphan final cache lacks progress state")
        if part.exists():
            if part.stat().st_ino != final.stat().st_ino:
                raise ValueError("EXP-070 final/partial cache identity drift")
            part.unlink()
        matrix = np.load(final, mmap_mode="r", allow_pickle=False)
        if matrix.shape != tuple(spec["shape"]) or matrix.dtype != np.float32:
            raise ValueError("EXP-070 orphan final cache schema drift")
    elif not part.exists():
        if progress_path.exists():
            raise ValueError("EXP-070 progress exists without partial cache")
        matrix = np.lib.format.open_memmap(
            part, mode="w+", dtype=np.float32, shape=tuple(spec["shape"])
        )
        matrix.flush()
        os.chmod(part, 0o600)
    else:
        matrix = np.load(part, mmap_mode="r+", allow_pickle=False)
        if matrix.shape != tuple(spec["shape"]) or matrix.dtype != np.float32:
            raise ValueError("EXP-070 partial cache schema drift")
    if part.exists() and file_mode(part) != "0600":
        raise PermissionError("EXP-070 partial cache mode drift")
    if progress_path.exists():
        if file_mode(progress_path) != "0600":
            raise PermissionError("EXP-070 progress mode drift")
        progress = strict_json(progress_path)
    else:
        progress = {
            "schema_version": "exp-070-extraction-progress-v1",
            "worker_id": spec["worker_id"],
            "status": "InProgress",
            "shape": spec["shape"],
            "points": spec["points"],
            "chunk_rows": CHUNK_ROWS,
            "next_ordinal": 0,
            "generation": 0,
            "resume_count": 0,
            "elapsed_seconds": 0.0,
            "mlx_peak_bytes": 0,
            "chunks": [],
            "source_snapshot_sha256": source_snapshot_sha256,
        }
        replace_private_json(progress_path, progress)
    if (
        progress.get("schema_version") != "exp-070-extraction-progress-v1"
        or progress.get("worker_id") != spec["worker_id"]
        or progress.get("shape") != spec["shape"]
        or progress.get("points") != spec["points"]
        or progress.get("chunk_rows") != CHUNK_ROWS
        or progress.get("source_snapshot_sha256") != source_snapshot_sha256
    ):
        raise ValueError("EXP-070 progress contract drift")
    expected_start = 0
    for chunk in progress.get("chunks", []):
        expected_parity_digest = bytes_sha256(
            canonical_json_bytes(
                {
                    "max_errors": chunk.get("max_errors"),
                    "heldout_rows_checked": chunk.get("heldout_rows_checked"),
                }
            )
        )
        if (
            chunk.get("start") != expected_start
            or chunk.get("stop") != min(expected_start + CHUNK_ROWS, ROWS)
            or chunk.get("representation_sha256")
            != _chunk_digest(matrix, int(chunk["start"]), int(chunk["stop"]))
            or chunk.get("parity_sha256") != expected_parity_digest
            or not isinstance(chunk.get("token_sha256"), str)
        ):
            raise ValueError("EXP-070 committed chunk drift")
        expected_start = int(chunk["stop"])
    if progress.get("next_ordinal") != expected_start or not 0 <= expected_start <= ROWS:
        raise ValueError("EXP-070 progress prefix drift")
    if expected_start > 0 and progress.get("status") == "InProgress":
        progress = dict(progress)
        progress["resume_count"] = int(progress.get("resume_count", 0)) + 1
        progress["generation"] = int(progress["generation"]) + 1
        replace_private_json(progress_path, progress)
    return matrix, progress


def _verify_committed_token_chunks(
    progress: dict[str, Any], rows: Sequence[dict[str, Any]], tokenizer: Any, prompt: dict[str, Any], exp069: Any
) -> None:
    for chunk in progress["chunks"]:
        token_pairs: list[tuple[int, list[int]]] = []
        for row in rows[int(chunk["start"]): int(chunk["stop"])]:
            ids, _, _ = exp069.qwen_prompt_ids(tokenizer, prompt, row["text"], 384)
            token_pairs.append((row["ordinal"], ids))
        if exp069.token_stream_digest(token_pairs) != chunk["token_sha256"]:
            raise ValueError("EXP-070 committed token chunk drift")


def _source_record(snapshot: dict[str, Any], seed: int, fold: int, name: str) -> dict[str, Any]:
    key = f"seed-{seed}/fold-{fold}/{name}"
    record = snapshot["checkpoint_files"].get(key)
    if not isinstance(record, dict):
        raise ValueError(f"Missing EXP-070 checkpoint record: {key}")
    require_record(record)
    return record


def _require_external_record(record: dict[str, Any]) -> dict[str, Any]:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("External source record schema drift")
    path = Path(record["path"])
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or path.stat().st_size != record["bytes"]
        or file_mode(path) != record["mode"]
        or sha256(path) != record["sha256"]
    ):
        raise ValueError("External source identity drift")
    return dict(record)


def _verified_record(record: dict[str, Any]) -> dict[str, Any]:
    require_record(record)
    return dict(record)


def _common_worker_sources(
    config: dict[str, Any], original: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    model_files = {
        name: _verified_record(record)
        for name, record in sorted(snapshot["model_files"].items())
    }
    require_record(config["method_protocol"])
    require_record(config["formal_protocol"])
    require_record(config["parent_no_result"]["input_contract"])
    require_record(original["model"]["prompt"])
    require_record(config["sources"]["exp069_runner"])
    require_record(config["implementation"]["runner"])
    return {
        "formal_config": artifact(DEFAULT_CONFIG),
        "method_protocol": dict(config["method_protocol"]),
        "formal_protocol": dict(config["formal_protocol"]),
        "parent_input_contract": dict(config["parent_no_result"]["input_contract"]),
        "model_files": model_files,
        "prompt": dict(original["model"]["prompt"]),
        "exp069_runner": dict(config["sources"]["exp069_runner"]),
        "formal_runner": dict(config["implementation"]["runner"]),
        "qwen3_source": _require_external_record(original["environment"]["qwen3_source"]),
    }


def _current_worker_sources(
    config: dict[str, Any],
    original: dict[str, Any],
    snapshot: dict[str, Any],
    spec: dict[str, Any],
    *,
    common_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(
        common_sources
        if common_sources is not None
        else _common_worker_sources(config, original, snapshot)
    )
    if spec["kind"] == "m3":
        seed = int(spec["seed"])
        fold = int(spec["fold"])
        for name in ("adapter", "head", "heldout"):
            record = _source_record(snapshot, seed, fold, name)
            result[name] = _verified_record(record)
    return result


def _load_reference(
    heldout_path: Path, fold: int
) -> tuple[dict[str, int], np.ndarray, np.ndarray]:
    with np.load(heldout_path, allow_pickle=False) as archive:
        if not {"sample_ids", "fold_ids", "logits"}.issubset(archive.files):
            raise ValueError("Heldout reference schema drift")
        sample_ids = np.asarray(archive["sample_ids"])
        fold_ids = np.asarray(archive["fold_ids"], dtype=np.int8)
        logits = np.asarray(archive["logits"], dtype=np.float32)
    if sample_ids.shape != (672,) or fold_ids.shape != (672,) or logits.shape != (672, 6):
        raise ValueError("Heldout reference shape drift")
    if not np.all(fold_ids == fold) or len(set(map(str, sample_ids.tolist()))) != 672:
        raise ValueError("Heldout reference identity drift")
    return {str(value): index for index, value in enumerate(sample_ids.tolist())}, fold_ids, logits


def _aggregate_errors(chunks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        name: max((float(chunk["max_errors"].get(name, 0.0)) for chunk in chunks), default=0.0)
        for name in ("standard_hf", "m2_hf", "heldout_logit")
    }
    result["pre_lora"] = {
        point: max(
            (
                float(chunk["max_errors"].get("pre_lora", {}).get(point, 0.0))
                for chunk in chunks
            ),
            default=0.0,
        )
        for point in PRE_LORA_POINTS
    }
    return result


def _finalize_worker(
    config: dict[str, Any], spec: dict[str, Any], progress: dict[str, Any]
) -> dict[str, Any]:
    finalize_started = time.perf_counter()
    directory = worker_dir(config, spec["worker_id"])
    part = directory / "representations.npy.part"
    final = directory / "representations.npy"
    worker_path = directory / "worker.json"
    progress_path = directory / "progress.json"
    if progress.get("next_ordinal") != ROWS or progress.get("status") != "ReadyToFinalize":
        raise ValueError("EXP-070 worker is not ready to finalize")
    if final.exists():
        if part.exists() and part.stat().st_ino == final.stat().st_ino:
            part.unlink()
        elif part.exists():
            raise ValueError("EXP-070 final/partial cache identity drift")
    else:
        if not part.is_file():
            raise FileNotFoundError(part)
        os.link(part, final)
        os.chmod(final, 0o600)
        part.unlink()
    matrix = np.load(final, mmap_mode="r", allow_pickle=False)
    if matrix.shape != tuple(spec["shape"]) or matrix.dtype != np.float32:
        raise ValueError("EXP-070 final cache schema drift")
    for start in range(0, ROWS, CHUNK_ROWS):
        if not np.isfinite(matrix[start : min(start + CHUNK_ROWS, ROWS)]).all():
            raise ValueError("EXP-070 final cache contains non-finite values")
    output = artifact(final, logical_name=f"{spec['worker_id']}/representations.npy")
    progress = dict(progress)
    progress["elapsed_seconds"] = float(progress["elapsed_seconds"]) + (
        time.perf_counter() - finalize_started
    )
    if float(progress["elapsed_seconds"]) > float(config["resources"]["worker_wall_hours"]) * 3600.0:
        raise TimeoutError("EXP-070 extraction worker exceeded wall-time budget during finalization")
    worker = {
        "schema_version": "exp-070-extraction-worker-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "stage": "formal-extraction",
        "status": "Completed",
        "worker_id": spec["worker_id"],
        "kind": spec["kind"],
        "condition": "Frozen Qwen" if spec["kind"] == "base" else "M3",
        "seed": spec["seed"],
        "fold": spec["fold"],
        "rows": ROWS,
        "points": spec["points"],
        "shape": spec["shape"],
        "dtype": "float32",
        "layout": "C",
        "output": output,
        "row_identity": progress["row_identity"],
        "token_id_stream_sha256": progress["token_id_stream_sha256"],
        "max_errors": _aggregate_errors(progress["chunks"]),
        "heldout_rows_checked": sum(int(chunk.get("heldout_rows_checked", 0)) for chunk in progress["chunks"]),
        "source_before": progress["source_before"],
        "source_after": progress["source_after"],
        "adapter_load_max_abs_error": float(progress.get("adapter_load_max_abs_error", 0.0)),
        "resume_count": int(progress.get("resume_count", 0)),
        "resources": {
            "elapsed_seconds": float(progress["elapsed_seconds"]),
            "mlx_peak_bytes": int(progress["mlx_peak_bytes"]),
        },
        "access": {
            "label_bearing_train_container_accessed": True,
            "train_text_accessed": True,
            "train_label_values_used": False,
            "heldout_members_read": ["sample_ids", "fold_ids", "logits"] if spec["kind"] == "m3" else [],
            "heldout_gold_read": False,
            "validation_accessed": False,
            "test_accessed": False,
            "model_loaded": True,
            "forward_executed": True,
            "probe_fitted": False,
            "performance_metrics_computed": False,
        },
        "checks": {
            "finite_values": True,
            "row_count": ROWS,
            "token_count": ROWS,
            "continuous_chunk_prefix": True,
        },
    }
    if spec["kind"] == "m3" and worker["heldout_rows_checked"] != 672:
        raise ValueError("EXP-070 heldout parity coverage drift")
    create_json_once(worker_path, worker, private=True)
    _cleanup_completed_worker(directory)
    return worker


def extract_worker(
    config_path: Path, config: dict[str, Any], *, seed: int | None, fold: int | None
) -> dict[str, Any]:
    manifest, _ = require_initialized(config_path, config)
    parent = require_parent_gate(config)
    original = parent["original_config"]
    require_environment(original)
    worker_id = "base" if seed is None else f"m3-s{seed}-f{fold}"
    spec = _worker_spec(worker_id)
    if spec["seed"] != seed or spec["fold"] != fold:
        raise ValueError("EXP-070 extraction CLI identity drift")
    invocation_started = time.perf_counter()
    already = _require_worker_turn(config, worker_id, manifest, parent)
    if already is not None:
        return already
    source_snapshot = parent["input_contract"]["source_snapshot"]
    source_snapshot_sha256 = parent["input_contract"]["source_snapshot_sha256"]
    rows = _load_train_rows(original)
    exp069 = _load_exp069(manifest["exp069_runner"])
    prompt = strict_json(require_record(original["model"]["prompt"]))
    source_before = _current_worker_sources(config, original, source_snapshot, spec)
    adapter_path: Path | None = None
    head_path: Path | None = None
    heldout_path: Path | None = None
    if spec["kind"] == "m3":
        assert seed is not None and fold is not None
        for name in ("adapter", "head", "heldout"):
            _source_record(source_snapshot, seed, fold, name)
        adapter_path = require_record(_source_record(source_snapshot, seed, fold, "adapter"))
        head_path = require_record(_source_record(source_snapshot, seed, fold, "head"))
        heldout_path = require_record(_source_record(source_snapshot, seed, fold, "heldout"))
    with heavy_mutex(config):
        matrix, progress = _prepare_partial(config, spec, source_snapshot_sha256)
        import mlx.core as mx
        import mlx.nn as nn
        from mlx_lm import load
        from mlx_lm.models.base import create_attention_mask
        from mlx_lm.tuner import linear_to_lora_layers
        from mlx.utils import tree_flatten
        from safetensors.numpy import load_file as load_safetensors

        mx.reset_peak_memory()
        stage_started = invocation_started
        model, tokenizer = load(str(resolve_project(original["model"]["base_path"])), lazy=False)
        model.freeze()
        model.eval()
        head = None
        reference_index: dict[str, int] = {}
        reference_logits: np.ndarray | None = None
        if spec["kind"] == "m3":
            assert seed is not None and fold is not None and adapter_path and head_path and heldout_path
            mx.random.seed(seed)
            head = nn.Linear(HIDDEN_SIZE, 6, bias=True)
            mx.random.seed(seed + 100000)
            linear_to_lora_layers(
                model,
                16,
                {
                    "rank": 8,
                    "scale": 20.0,
                    "dropout": 0.0,
                    "keys": list(original["model"]["lora"]["target_modules"]),
                },
            )
            exp069.lora_identity(model)
            adapter_arrays = load_safetensors(str(adapter_path))
            head_arrays = load_safetensors(str(head_path))
            if set(head_arrays) != {"weight", "bias"}:
                raise ValueError("EXP-070 head tensor inventory drift")
            model.load_weights(str(adapter_path), strict=False)
            head.load_weights(str(head_path), strict=True)
            runtime_arrays = dict(tree_flatten(model.trainable_parameters()))
            if set(runtime_arrays) != set(adapter_arrays):
                raise ValueError("EXP-070 adapter runtime coverage drift")
            mx.eval(*runtime_arrays.values(), *[value for _, value in tree_flatten(head.trainable_parameters())])
            adapter_load_error = 0.0
            for name, expected in adapter_arrays.items():
                observed = np.asarray(runtime_arrays[name].astype(mx.float32), dtype=np.float32)
                adapter_load_error = max(
                    adapter_load_error,
                    max_abs(observed, np.asarray(expected, dtype=np.float32)),
                )
            if adapter_load_error != 0.0:
                raise ValueError("EXP-070 adapter tensor load drift")
            progress = dict(progress)
            progress["adapter_load_max_abs_error"] = adapter_load_error
            exp069.lora_identity(model)
            reference_index, _, reference_logits = _load_reference(heldout_path, fold)
        _verify_committed_token_chunks(progress, rows, tokenizer, prompt, exp069)
        base_matrix: np.ndarray | None = None
        if spec["kind"] == "m3":
            base_manifest = _validate_worker_manifest(
                worker_dir(config, "base") / "worker.json", _worker_spec("base")
            )
            base_path = _record_from_logical(base_manifest["output"], worker_dir(config, "base").parent)
            base_matrix = np.load(base_path, mmap_mode="r", allow_pickle=False)
        m2_features: np.ndarray | None = None
        if spec["kind"] == "base":
            m2_path = require_record(original["m2_cache"]["features"])
            m2_features = np.load(m2_path, mmap_mode="r", allow_pickle=False)
            if m2_features.shape != (ROWS, HIDDEN_SIZE) or m2_features.dtype != np.float32:
                raise ValueError("EXP-070 M2 cache schema drift")
        started = stage_started
        next_ordinal = int(progress["next_ordinal"])
        point_indices = {point: index for index, point in enumerate(ALL_POINTS)}
        stored_points = tuple(spec["points"])
        wall_limit = float(config["resources"].get("worker_wall_hours", 4.0)) * 3600.0
        memory_limit = float(config["resources"].get("worker_peak_mlx_gb", 10.0)) * 1e9
        for start in range(next_ordinal, ROWS, CHUNK_ROWS):
            stop = min(start + CHUNK_ROWS, ROWS)
            buffer = np.empty((stop - start, len(stored_points), HIDDEN_SIZE), dtype=np.float32)
            errors: dict[str, Any] = {
                "standard_hf": 0.0,
                "m2_hf": 0.0,
                "heldout_logit": 0.0,
                "pre_lora": {point: 0.0 for point in PRE_LORA_POINTS},
            }
            heldout_checked = 0
            chunk_token_pairs: list[tuple[int, list[int]]] = []
            for offset, row in enumerate(rows[start:stop]):
                ids, _, _ = exp069.qwen_prompt_ids(tokenizer, prompt, row["text"], 384)
                chunk_token_pairs.append((row["ordinal"], ids))
                input_ids = mx.array([ids], dtype=mx.int32)
                points = manual_points(model, input_ids, create_attention_mask)
                values_to_eval = list(points.values())
                manual_logits = None
                if head is not None and row["fold_id"] == fold:
                    manual_logits = head(points["HF"].astype(head.weight.dtype)).astype(mx.float32)
                    values_to_eval.append(manual_logits)
                standard_hf = None
                if row["ordinal"] in SMOKE_ORDINALS:
                    standard_hf = model.model(input_ids)[:, -1, :]
                    values_to_eval.append(standard_hf)
                mx.eval(*values_to_eval)
                converted = {
                    name: np.asarray(value.astype(mx.float32), dtype=np.float32)[0]
                    for name, value in points.items()
                }
                if any(not np.isfinite(value).all() for value in converted.values()):
                    raise ValueError("EXP-070 extraction produced non-finite representation")
                for point_index, point in enumerate(stored_points):
                    buffer[offset, point_index] = converted[point]
                if standard_hf is not None:
                    errors["standard_hf"] = max(
                        errors["standard_hf"],
                        max_abs(
                            converted["HF"][None, :],
                            np.asarray(standard_hf.astype(mx.float32), dtype=np.float32),
                        ),
                    )
                if m2_features is not None:
                    errors["m2_hf"] = max(
                        errors["m2_hf"], max_abs(converted["HF"], m2_features[row["ordinal"]])
                    )
                if base_matrix is not None:
                    for point in PRE_LORA_POINTS:
                        errors["pre_lora"][point] = max(
                            errors["pre_lora"][point],
                            max_abs(
                                converted[point],
                                np.asarray(base_matrix[row["ordinal"], point_indices[point]], dtype=np.float32),
                            ),
                        )
                if manual_logits is not None:
                    assert reference_logits is not None
                    position = reference_index.get(row["sample_id"])
                    if position is None:
                        raise ValueError("EXP-070 heldout sample alignment drift")
                    errors["heldout_logit"] = max(
                        errors["heldout_logit"],
                        max_abs(
                            np.asarray(manual_logits, dtype=np.float32),
                            reference_logits[position : position + 1],
                        ),
                    )
                    heldout_checked += 1
            limits = original["smoke"]["tolerances"]
            if (
                errors["standard_hf"] > float(limits["standard_hf_atol"])
                or errors["m2_hf"] > float(limits["m2_hf_atol"])
                or errors["heldout_logit"] > float(limits["m3_logit_atol"])
                or max(errors["pre_lora"].values()) > float(config["extraction"]["atol"])
            ):
                raise ValueError("EXP-070 extraction parity gate failed")
            matrix[start:stop] = buffer
            matrix.flush()
            descriptor = os.open(worker_dir(config, worker_id) / "representations.npy.part", os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            chunk = {
                "start": start,
                "stop": stop,
                "representation_sha256": _chunk_digest(matrix, start, stop),
                "token_sha256": exp069.token_stream_digest(chunk_token_pairs),
                "max_errors": errors,
                "heldout_rows_checked": heldout_checked,
            }
            chunk["parity_sha256"] = bytes_sha256(
                canonical_json_bytes(
                    {
                        "max_errors": chunk["max_errors"],
                        "heldout_rows_checked": chunk["heldout_rows_checked"],
                    }
                )
            )
            progress = dict(progress)
            progress["chunks"] = [*progress["chunks"], chunk]
            progress["next_ordinal"] = stop
            progress["generation"] = int(progress["generation"]) + 1
            progress["elapsed_seconds"] = float(progress["elapsed_seconds"]) + (
                time.perf_counter() - started
            )
            progress["mlx_peak_bytes"] = max(
                int(progress.get("mlx_peak_bytes", 0)), int(mx.get_peak_memory())
            )
            replace_private_json(worker_dir(config, worker_id) / "progress.json", progress)
            started = time.perf_counter()
            if float(progress["elapsed_seconds"]) > wall_limit:
                raise TimeoutError("EXP-070 extraction worker exceeded wall-time budget")
            if int(progress["mlx_peak_bytes"]) > memory_limit:
                raise MemoryError("EXP-070 extraction worker exceeded MLX memory budget")
            mx.clear_cache()
        token_pairs: list[tuple[int, list[int]]] = []
        for row in rows:
            ids, _, _ = exp069.qwen_prompt_ids(tokenizer, prompt, row["text"], 384)
            token_pairs.append((row["ordinal"], ids))
        source_after = _current_worker_sources(config, original, source_snapshot, spec)
        if source_after != source_before:
            raise ValueError("EXP-070 source identity changed during extraction")
        progress = dict(progress)
        progress["elapsed_seconds"] = float(progress["elapsed_seconds"]) + (
            time.perf_counter() - started
        )
        progress["status"] = "ReadyToFinalize"
        progress["token_id_stream_sha256"] = exp069.token_stream_digest(token_pairs)
        progress["row_identity"] = manifest["row_identity"]
        progress["source_before"] = source_before
        progress["source_after"] = source_after
        progress["generation"] = int(progress["generation"]) + 1
        replace_private_json(worker_dir(config, worker_id) / "progress.json", progress)
        del model, tokenizer, head
        mx.clear_cache()
        return _finalize_worker(config, spec, progress)


def assemble(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    manifest, _ = require_initialized(config_path, config)
    pub = public_root(config)
    output_path = pub / "extraction.json"
    private_manifest_path = private_root(config) / "extraction-manifest.json"
    if output_path.exists() and not private_manifest_path.exists():
        raise ValueError("EXP-070 public extraction exists without private manifest")
    workers: list[dict[str, Any]] = []
    raw_bytes = 0
    total_elapsed = 0.0
    maximum_peak = 0
    aggregate_errors: dict[str, Any] = {
        "standard_hf": 0.0,
        "m2_hf": 0.0,
        "heldout_logit": 0.0,
        "pre_lora": {point: 0.0 for point in PRE_LORA_POINTS},
    }
    token_digest: str | None = None
    row_identity: dict[str, Any] | None = None
    for spec in expected_worker_plan():
        directory = worker_dir(config, spec["worker_id"])
        if (directory / "representations.npy.part").exists():
            raise ValueError("EXP-070 partial cache remains at assemble")
        entries = {
            path.name for path in directory.iterdir() if path.is_file()
        }
        if entries != {"representations.npy", "worker.json"} or any(
            path.is_dir() or path.is_symlink() for path in directory.iterdir()
        ):
            raise ValueError("EXP-070 terminal worker inventory drift")
        worker = _validate_worker_manifest(directory / "worker.json", spec)
        if worker["source_before"] != worker["source_after"]:
            raise ValueError("EXP-070 sealed worker source drift")
        if float(worker["resources"]["elapsed_seconds"]) > float(
            config["resources"]["worker_wall_hours"]
        ) * 3600.0:
            raise ValueError("EXP-070 sealed worker wall-time drift")
        if int(worker["resources"]["mlx_peak_bytes"]) > float(
            config["resources"]["worker_peak_mlx_gb"]
        ) * 1e9:
            raise ValueError("EXP-070 sealed worker peak-memory drift")
        if worker["token_id_stream_sha256"] != token_digest and token_digest is not None:
            raise ValueError("EXP-070 cross-worker token stream drift")
        if worker["row_identity"] != row_identity and row_identity is not None:
            raise ValueError("EXP-070 cross-worker row identity drift")
        token_digest = worker["token_id_stream_sha256"]
        row_identity = worker["row_identity"]
        raw_bytes += int(np.prod(spec["shape"], dtype=np.int64)) * 4
        total_elapsed += float(worker["resources"]["elapsed_seconds"])
        maximum_peak = max(maximum_peak, int(worker["resources"]["mlx_peak_bytes"]))
        for name in ("standard_hf", "m2_hf", "heldout_logit"):
            aggregate_errors[name] = max(aggregate_errors[name], float(worker["max_errors"][name]))
        for point in PRE_LORA_POINTS:
            aggregate_errors["pre_lora"][point] = max(
                aggregate_errors["pre_lora"][point],
                float(worker["max_errors"]["pre_lora"][point]),
            )
        workers.append(
            {
                "worker_id": spec["worker_id"],
                "manifest": artifact(
                    directory / "worker.json",
                    logical_name=f"{spec['worker_id']}/worker.json",
                ),
                "output": worker["output"],
                "max_errors": worker["max_errors"],
                "resources": worker["resources"],
            }
        )
    expected_raw = int(config["extraction"]["raw_payload_bytes"])
    if raw_bytes != expected_raw:
        raise ValueError("EXP-070 raw representation byte contract drift")
    if total_elapsed > float(config["resources"]["aggregate_model_wall_hours"]) * 3600.0:
        raise ValueError("EXP-070 aggregate wall-time contract drift")
    private_manifest = {
        "schema_version": "exp-070-extraction-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Completed",
        "config": artifact(config_path),
        "input_manifest": artifact(
            private_root(config) / "input-manifest.json", logical_name="input-manifest.json"
        ),
        "row_contract": manifest["row_contract"],
        "row_identity": row_identity,
        "token_id_stream_sha256": token_digest,
        "workers": workers,
        "raw_representation_bytes": raw_bytes,
        "max_errors": aggregate_errors,
        "resources": {
            "total_elapsed_seconds": total_elapsed,
            "maximum_mlx_peak_bytes": maximum_peak,
        },
        "access": {
            "label_bearing_train_container_accessed": True,
            "train_text_accessed": True,
            "train_label_values_used_for_extraction": False,
            "historical_logits_read": True,
            "heldout_gold_read": False,
            "validation_accessed": False,
            "test_accessed": False,
            "model_loaded_by_assemble": False,
            "forward_executed_by_assemble": False,
            "probe_fitted": False,
            "performance_metrics_computed": False,
        },
    }
    if private_manifest_path.exists():
        if strict_json(private_manifest_path) != private_manifest:
            raise ValueError("EXP-070 existing private extraction manifest drift")
    else:
        create_json_once(private_manifest_path, private_manifest, private=True)
    private_bytes = sum(
        path.stat().st_size for path in private_root(config).rglob("*") if path.is_file()
    )
    if private_bytes > int(config["resources"]["private_disk_budget_bytes"]):
        raise ValueError("EXP-070 private disk budget exceeded")
    public = {
        "schema_version": "exp-070-extraction-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "stage": "formal-extraction",
        "status": "CompletedAwaitingVerification",
        "config": artifact(config_path),
        "input_manifest": artifact(
            private_root(config) / "input-manifest.json", logical_name="input-manifest.json"
        ),
        "extraction_manifest": artifact(
            private_manifest_path, logical_name="extraction-manifest.json"
        ),
        "counts": {"rows": ROWS, "workers": 16, "matrices": 16},
        "points": {
            "seed_42": list(ALL_POINTS),
            "seeds_43_44": list(CONFIRMATION_POINTS),
        },
        "raw_representation_bytes": raw_bytes,
        "max_errors": aggregate_errors,
        "resources": {
            "total_elapsed_seconds": total_elapsed,
            "maximum_mlx_peak_bytes": maximum_peak,
            "private_bytes": private_bytes,
        },
        "formal_probe_executed": False,
        "performance_metrics_computed": False,
        "validation_accessed": False,
        "test_accessed": False,
        "claim_boundary": config["claim_boundary"],
    }
    if output_path.exists():
        if strict_json(output_path) != public:
            raise ValueError("EXP-070 existing public extraction record drift")
    else:
        create_json_once(output_path, public)
    return public


def record_failure(
    config_path: Path, config: dict[str, Any], stage: str, worker_id: str | None, error: BaseException
) -> None:
    try:
        pub = public_root(config)
        claim_exists = (pub / "run-claim.json").is_file()
        if stage == "initialize" and claim_exists:
            return
        if stage != "initialize" and not claim_exists:
            return
        if (pub / "extraction.json").exists():
            return
        pub.mkdir(parents=True, exist_ok=True, mode=0o755)
        os.chmod(pub, 0o755)
        target = pub / "failure.json"
        if target.exists():
            return
        completed = sum(
            (worker_dir(config, spec["worker_id"]) / "worker.json").is_file()
            for spec in expected_worker_plan()
        )
        value = {
            "schema_version": "exp-070-extraction-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "status": "Failed",
            "stage": stage,
            "worker_id": worker_id,
            "error_type": type(error).__name__,
            "config": artifact(config_path),
            "completed_worker_prefix": completed,
            "probe_executed": False,
            "performance_metrics_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "exp071_authorized": False,
        }
        create_json_once(target, value)
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("initialize", "extract-base", "extract-m3", "assemble"),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--fold", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    worker_id: str | None = None
    try:
        if args.stage == "initialize":
            if args.seed is not None or args.fold is not None:
                raise ValueError("initialize accepts no seed/fold")
            result = initialize(args.config, config)
        elif args.stage == "extract-base":
            if args.seed is not None or args.fold is not None:
                raise ValueError("extract-base accepts no seed/fold")
            worker_id = "base"
            result = extract_worker(args.config, config, seed=None, fold=None)
        elif args.stage == "extract-m3":
            if args.seed not in SEEDS or args.fold not in FOLDS:
                raise ValueError("extract-m3 requires frozen seed/fold")
            worker_id = f"m3-s{args.seed}-f{args.fold}"
            result = extract_worker(args.config, config, seed=args.seed, fold=args.fold)
        else:
            if args.seed is not None or args.fold is not None:
                raise ValueError("assemble accepts no seed/fold")
            result = assemble(args.config, config)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        record_failure(args.config, config, args.stage, worker_id, error)
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

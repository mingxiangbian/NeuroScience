#!/usr/bin/env python3
"""Independently verify the extraction-only formal stage of EXP-070.

This verifier is deliberately model-free.  It does not import the extraction
runner, MLX, MLX-LM or Transformers.  It reads only frozen metadata, the M2
feature cache, the whitelisted historical held-out members, head tensors and
the 16 sealed representation matrices.  It never reads train text or labels
and it never fits a probe or computes a classification-performance metric.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import struct
import sys
from typing import Any, BinaryIO, Iterable, Sequence

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-070-formal-extraction.json"

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
FORBIDDEN_MODULES = {"mlx", "mlx_lm", "transformers"}

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


def require_logical(record: dict[str, Any], root: Path, expected_name: str) -> Path:
    if set(record) != {"logical_name", "bytes", "mode", "sha256"}:
        raise ValueError("Logical artifact record schema drift")
    if record["logical_name"] != expected_name:
        raise ValueError("Logical artifact path drift")
    pure = PurePosixPath(expected_name)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe logical artifact path")
    path = root.joinpath(*pure.parts)
    if artifact(path, logical_name=expected_name) != record:
        raise ValueError("Logical artifact identity drift")
    return path


def inventory(root: Path) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid artifact root")
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise PermissionError("Nested symlink rejected")
    return {path.relative_to(root).as_posix() for path in entries if path.is_file()}


def directory_inventory(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir()
    }


def create_json_once(path: Path, value: Any) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(path.parent, 0o755)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
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


def validate_config(config: dict[str, Any]) -> None:
    if set(config) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "rq_id", "tier",
        "registered_at", "method_protocol", "formal_protocol", "parent_no_result", "sources",
        "environment", "workers", "extraction", "resources", "authorization", "access_history",
        "outputs", "implementation", "claim_boundary",
    }:
        raise ValueError("EXP-070 formal config schema drift")
    nonself = {key: value for key, value in config.items() if key != "implementation"}
    if bytes_sha256(canonical_json_bytes(nonself)) != EXPECTED_NONSELF_CONFIG_SHA256:
        raise ValueError("EXP-070 formal non-self config drift")
    if (
        config["schema_version"] != "exp-070-formal-extraction-config-v1"
        or config["experiment_id"] != EXPERIMENT_ID
        or config["run_id"] != RUN_ID
        or config["attempt_id"] != ATTEMPT_ID
        or config["rq_id"] != "RQ-S4.1"
        or config["workers"] != expected_worker_plan()
    ):
        raise ValueError("EXP-070 formal config identity drift")
    if config["outputs"] != {
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
        raise ValueError("EXP-070 output contract drift")
    if config["authorization"] != {
        "initialize": True,
        "formal_extraction": True,
        "model_loading": True,
        "forward": True,
        "train_text": True,
        "train_label_values": False,
        "historical_heldout_members": ["sample_ids", "fold_ids", "logits"],
        "heldout_gold": False,
        "training": False,
        "probe_fitting": False,
        "threshold_selection": False,
        "label_shuffle": False,
        "bootstrap": False,
        "performance_metrics": False,
        "validation": False,
        "test": False,
        "formal_completion": False,
        "exp071": False,
    }:
        raise PermissionError("EXP-070 authorization drift")
    extraction = config["extraction"]
    if (
        extraction.get("rows") != ROWS
        or extraction.get("hidden_size") != HIDDEN_SIZE
        or extraction.get("dtype") != "float32"
        or extraction.get("layout") != "C"
        or extraction.get("all_points") != list(ALL_POINTS)
        or extraction.get("pre_lora_points") != list(PRE_LORA_POINTS)
        or extraction.get("transient_confirmation_points") != ["H-1", "H7", "H15"]
        or extraction.get("comparison_dtype") != "float32"
        or extraction.get("rtol") != 0.0
        or extraction.get("atol") != 1e-5
        or extraction.get("chunk_rows") != CHUNK_ROWS
        or extraction.get("chunks_per_worker") != 105
        or extraction.get("raw_payload_bytes") != 2_890_137_600
    ):
        raise ValueError("EXP-070 extraction contract drift")
    resources = config["resources"]
    if (
        resources.get("model_workers") != 16
        or resources.get("maximum_concurrent_heavy_workers") != 1
        or resources.get("worker_wall_hours") != 4
        or resources.get("aggregate_model_wall_hours") != 64
        or resources.get("worker_peak_mlx_gb") != 10.0
        or resources.get("private_disk_budget_bytes") != 5_368_709_120
        or resources.get("minimum_free_disk_bytes") != 10_737_418_240
        or resources.get("api_cost_usd") != 0
    ):
        raise ValueError("EXP-070 resource contract drift")
    if set(config["parent_no_result"]) != set(PARENT_PATHS):
        raise ValueError("EXP-070 parent inventory drift")
    if set(config["sources"]) != {
        "exp069_config", "exp069_input_manifest", "exp069_runner", "gitignore"
    }:
        raise ValueError("EXP-070 source inventory drift")
    if set(config["implementation"]) != {"runner", "verifier", "tests"}:
        raise ValueError("EXP-070 implementation inventory drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("EXP-070 verifier requires the frozen default config")
    config = strict_json(path)
    validate_config(config)
    return config


def require_frozen_records(config: dict[str, Any]) -> None:
    require_record(config["method_protocol"])
    require_record(config["formal_protocol"])
    for key, expected in PARENT_PATHS.items():
        require_record(config["parent_no_result"][key], expected_path=expected)
    for record in config["sources"].values():
        require_record(record)
    for record in config["implementation"].values():
        require_record(record)
    verifier_path = require_record(config["implementation"]["verifier"])
    if verifier_path.resolve() != Path(__file__).resolve():
        raise ValueError("EXP-070 verifier self identity drift")
    gitignore = require_record(config["sources"]["gitignore"])
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    if "private/" not in lines or any(line.startswith("!private") for line in lines):
        raise PermissionError("EXP-070 private ignore rule drift")


def validate_parent(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
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
    logical_input = {
        "logical_name": "input-contract-manifest.json",
        "bytes": parent["input_contract"]["bytes"],
        "mode": parent["input_contract"]["mode"],
        "sha256": parent["input_contract"]["sha256"],
    }
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
        or completion.get("input_contract") != logical_input
        or input_contract.get("status") != "Registered"
        or input_contract.get("source_snapshot_sha256") != run.get("source_snapshot_sha256")
        or input_contract.get("smoke_rows_usable_for_probe_fitting") is not False
    ):
        raise ValueError("EXP-070 no-result parent binding drift")
    snapshot = input_contract.get("source_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("EXP-070 parent source snapshot drift")
    observed_digest = hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()
    if observed_digest != input_contract["source_snapshot_sha256"]:
        raise ValueError("EXP-070 parent source snapshot digest drift")
    for category in ("files", "checkpoint_files", "fold_lineage_files", "model_files"):
        records = snapshot.get(category)
        if not isinstance(records, dict):
            raise ValueError("EXP-070 parent source snapshot schema drift")
        for record in records.values():
            require_record(record)
    original_record = config["sources"]["exp069_config"]
    original = strict_json(require_record(original_record))
    if original_record != parent_config["parent_exp069"]["original_config"]:
        raise ValueError("EXP-069 config parent binding drift")
    if config["sources"]["exp069_runner"] != original["implementation"]["runner"]:
        raise ValueError("EXP-069 runner parent binding drift")
    source_input = snapshot["files"]["input-manifest.json"]
    if config["sources"]["exp069_input_manifest"] != source_input:
        raise ValueError("EXP-069 input-manifest parent binding drift")
    expected_environment = {
        key: original["environment"][key]
        for key in ("python_executable", "python_version", "architecture", "packages", "offline_environment")
    }
    if config["environment"] != expected_environment:
        raise ValueError("EXP-070 environment binding drift")
    return original, input_contract


def require_verifier_environment(config: dict[str, Any]) -> None:
    expected = config["environment"]
    if os.path.realpath(sys.executable) != os.path.realpath(expected["python_executable"]):
        raise PermissionError("EXP-070 verifier Python drift")
    if platform.python_version() != expected["python_version"]:
        raise PermissionError("EXP-070 verifier Python version drift")
    if platform.machine() != expected["architecture"]:
        raise PermissionError("EXP-070 verifier architecture drift")
    observed = {name: importlib.metadata.version(name) for name in expected["packages"]}
    if observed != expected["packages"]:
        raise PermissionError("EXP-070 verifier package drift")
    for key, value in expected["offline_environment"].items():
        if os.environ.get(key) != value:
            raise PermissionError(f"EXP-070 verifier environment flag drift: {key}")
    if {name.split(".")[0] for name in sys.modules} & FORBIDDEN_MODULES:
        raise RuntimeError("EXP-070 verifier imported a forbidden model library")
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    if imports & FORBIDDEN_MODULES:
        raise RuntimeError("EXP-070 verifier source imports a forbidden model library")


def _string_sequence_digest(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        payload = value.encode("utf-8")
        digest.update(len(payload).to_bytes(4, "little", signed=False))
        digest.update(payload)
    return digest.hexdigest()


def _array_digest(value: np.ndarray) -> str:
    return bytes_sha256(np.ascontiguousarray(value).tobytes(order="C"))


def load_fold_rows(original: dict[str, Any]) -> list[dict[str, Any]]:
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
                raise ValueError("EXP-070 fold-row schema drift")
            rows.append(
                {
                    "ordinal": ordinal,
                    "sample_id": value["sample_id"],
                    "component_id": value["component_id"],
                    "fold_id": int(value["fold_id"]),
                }
            )
    if len(rows) != ROWS or len({row["sample_id"] for row in rows}) != ROWS:
        raise ValueError("EXP-070 fold-row identity drift")
    if [sum(row["fold_id"] == fold for row in rows) for fold in FOLDS] != [672] * 5:
        raise ValueError("EXP-070 fold counts drift")
    return rows


def expected_row_contract(rows: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    components = sorted({row["component_id"] for row in rows})
    if len(components) != 3277:
        raise ValueError("EXP-070 component count drift")
    component_map = {value: index for index, value in enumerate(components)}
    ordinal = np.arange(ROWS, dtype=np.int32)
    fold_id = np.asarray([row["fold_id"] for row in rows], dtype=np.int8)
    component_code = np.asarray(
        [component_map[row["component_id"]] for row in rows], dtype=np.int32
    )
    identity = {
        "ordinal_sha256": _array_digest(ordinal),
        "sample_id_order_sha256": _string_sequence_digest([row["sample_id"] for row in rows]),
        "component_id_order_sha256": _string_sequence_digest(
            [row["component_id"] for row in rows]
        ),
        "fold_id_order_sha256": _array_digest(fold_id),
        "component_code_sha256": _array_digest(component_code),
        "component_count": 3277,
    }
    return identity, {
        "ordinal": ordinal,
        "fold_id": fold_id,
        "component_code": component_code,
    }


def validate_row_contract(
    private: Path,
    input_manifest: dict[str, Any],
    rows: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], np.ndarray]:
    row_path = require_logical(input_manifest["row_contract"], private, "row-contract.npz")
    expected_identity, expected_arrays = expected_row_contract(rows)
    with np.load(row_path, allow_pickle=False) as archive:
        if set(archive.files) != set(expected_arrays):
            raise ValueError("EXP-070 row-contract member drift")
        for name, expected in expected_arrays.items():
            observed = archive[name]
            if observed.shape != expected.shape or observed.dtype != expected.dtype:
                raise ValueError("EXP-070 row-contract schema drift")
            if not np.array_equal(observed, expected):
                raise ValueError("EXP-070 row-contract value drift")
    if input_manifest.get("row_identity") != expected_identity:
        raise ValueError("EXP-070 row-identity digest drift")
    return expected_identity, expected_arrays["fold_id"]


def npy_header(path: Path) -> tuple[tuple[int, ...], np.dtype[Any], bool, int]:
    with path.open("rb") as handle:
        version = np.lib.format.read_magic(handle)
        if version == (1, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_1_0(handle)
        elif version == (2, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_2_0(handle)
        else:
            shape, fortran, dtype = np.lib.format._read_array_header(handle, version)
        offset = handle.tell()
    return tuple(int(value) for value in shape), np.dtype(dtype), bool(fortran), offset


def max_abs(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise ValueError("EXP-070 parity shape drift")
    if left.size == 0:
        return 0.0
    return float(
        np.max(
            np.abs(
                left.astype(np.float64, copy=False) - right.astype(np.float64, copy=False)
            )
        )
    )


def full_max_abs(left: np.ndarray, right: np.ndarray) -> float:
    value = 0.0
    for start in range(0, left.shape[0], CHUNK_ROWS):
        stop = min(start + CHUNK_ROWS, left.shape[0])
        value = max(value, max_abs(left[start:stop], right[start:stop]))
    return value


def require_finite(matrix: np.ndarray) -> None:
    for start in range(0, matrix.shape[0], CHUNK_ROWS):
        stop = min(start + CHUNK_ROWS, matrix.shape[0])
        if not np.isfinite(matrix[start:stop]).all():
            raise ValueError("EXP-070 representation contains non-finite values")


def read_safetensors_f32(path: Path) -> dict[str, np.ndarray]:
    with path.open("rb") as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise ValueError("Truncated safetensors header")
        header_length = struct.unpack("<Q", raw_length)[0]
        if header_length <= 0 or header_length > 1024 * 1024:
            raise ValueError("Unsafe safetensors header length")
        header = strict_json_bytes(handle.read(header_length))
        if set(header) - {"__metadata__"} != {"weight", "bias"}:
            raise ValueError("EXP-070 head tensor inventory drift")
        data_start = 8 + header_length
        output: dict[str, np.ndarray] = {}
        maximum_end = 0
        for name, expected_shape in (("weight", (6, HIDDEN_SIZE)), ("bias", (6,))):
            item = header[name]
            if item.get("dtype") != "F32" or tuple(item.get("shape", ())) != expected_shape:
                raise ValueError("EXP-070 head tensor schema drift")
            start, end = (int(value) for value in item["data_offsets"])
            expected_bytes = int(np.prod(expected_shape, dtype=np.int64)) * 4
            if start < 0 or end - start != expected_bytes:
                raise ValueError("EXP-070 head tensor offset drift")
            handle.seek(data_start + start)
            payload = handle.read(expected_bytes)
            if len(payload) != expected_bytes:
                raise ValueError("Truncated head tensor")
            output[name] = np.frombuffer(payload, dtype="<f4").reshape(expected_shape).copy()
            maximum_end = max(maximum_end, end)
    if data_start + maximum_end != path.stat().st_size:
        raise ValueError("EXP-070 head tensor trailing-byte drift")
    return output


def load_heldout_reference(path: Path, fold: int) -> tuple[list[str], np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        if not {"sample_ids", "fold_ids", "logits"}.issubset(archive.files):
            raise ValueError("EXP-070 heldout-reference member drift")
        sample_ids = archive["sample_ids"]
        fold_ids = np.asarray(archive["fold_ids"], dtype=np.int8)
        logits = np.asarray(archive["logits"], dtype=np.float32)
    values = [str(value) for value in sample_ids.tolist()]
    if (
        sample_ids.shape != (672,)
        or fold_ids.shape != (672,)
        or logits.shape != (672, 6)
        or len(set(values)) != 672
        or not np.all(fold_ids == fold)
        or not np.isfinite(logits).all()
    ):
        raise ValueError("EXP-070 heldout-reference schema drift")
    return values, logits


def public_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(public_sensitive(key) for key in value) or any(
            public_sensitive(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(public_sensitive(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(
            marker in lowered
            for marker in (
                "/users/", "phase-b-representation/private/", "derived-private/",
                "oof-router/private/", "sample-", "component-", "row_identity",
                "token_id_stream",
            )
        )
    return False


def expected_private_files() -> set[str]:
    result = {"input-manifest.json", "row-contract.npz", "extraction-manifest.json"}
    for spec in expected_worker_plan():
        prefix = f"extraction/{spec['worker_id']}"
        result.add(f"{prefix}/representations.npy")
        result.add(f"{prefix}/worker.json")
    return result


def expected_private_dirs() -> set[str]:
    return {"extraction", *{f"extraction/{item['worker_id']}" for item in expected_worker_plan()}}


def validate_initialization(
    config_path: Path,
    config: dict[str, Any],
    original: dict[str, Any],
    parent_contract: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray]:
    public = resolve_project(config["outputs"]["public_root"])
    private = resolve_project(config["outputs"]["private_root"])
    if file_mode(public) != "0755" or file_mode(private) != "0700":
        raise PermissionError("EXP-070 formal root mode drift")
    if private.parent.is_symlink() or file_mode(private.parent) != "0700":
        raise PermissionError("EXP-070 private parent-directory mode drift")
    observed_public = inventory(public)
    if observed_public not in (
        {"run-claim.json", "extraction.json"},
        {"run-claim.json", "extraction.json", "extraction-verification.json"},
    ):
        raise ValueError("EXP-070 public preverification inventory drift")
    if directory_inventory(public):
        raise ValueError("EXP-070 public directory inventory drift")
    if inventory(private) != expected_private_files():
        raise ValueError("EXP-070 private terminal inventory drift")
    if directory_inventory(private) != expected_private_dirs():
        raise ValueError("EXP-070 private directory inventory drift")
    if any(file_mode(private / relative) != "0600" for relative in expected_private_files()):
        raise PermissionError("EXP-070 private file mode drift")
    if any(file_mode(private / relative) != "0700" for relative in expected_private_dirs()):
        raise PermissionError("EXP-070 private directory mode drift")
    if any(path.stat().st_nlink != 1 for path in private.rglob("*") if path.is_file()):
        raise PermissionError("EXP-070 private hardlink drift")
    if any(file_mode(public / relative) != "0644" for relative in inventory(public)):
        raise PermissionError("EXP-070 public file mode drift")
    if any(path.stat().st_nlink != 1 for path in public.rglob("*") if path.is_file()):
        raise PermissionError("EXP-070 public hardlink drift")
    if (public / "failure.json").exists():
        raise RuntimeError("EXP-070 extraction attempt is terminal Failed")

    claim_path = public / "run-claim.json"
    run_path = public / "extraction.json"
    input_path = private / "input-manifest.json"
    extraction_path = private / "extraction-manifest.json"
    claim = strict_json(claim_path)
    run = strict_json(run_path)
    input_manifest = strict_json(input_path)
    extraction_manifest = strict_json(extraction_path)
    if set(claim) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "parent_completion", "input_manifest", "worker_count",
        "access_history",
        "formal_probe_authorized", "performance_metrics_authorized", "validation_access",
        "test_access", "claim_boundary",
    }:
        raise ValueError("EXP-070 initialization claim schema drift")
    if set(input_manifest) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status", "config",
        "parent_no_result", "parent_source_snapshot_sha256", "exp069_runner", "row_contract",
        "row_identity", "workers", "access_history", "access",
    }:
        raise ValueError("EXP-070 initialization manifest schema drift")
    if set(extraction_manifest) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status", "config",
        "input_manifest", "row_contract", "row_identity", "token_id_stream_sha256", "workers",
        "raw_representation_bytes", "max_errors", "resources", "access",
    }:
        raise ValueError("EXP-070 extraction manifest schema drift")
    if set(run) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status", "config",
        "input_manifest", "extraction_manifest", "counts", "points",
        "raw_representation_bytes", "max_errors", "resources", "formal_probe_executed",
        "performance_metrics_computed", "validation_accessed", "test_accessed", "claim_boundary",
    }:
        raise ValueError("EXP-070 public extraction run schema drift")
    if (
        claim.get("schema_version") != "exp-070-extraction-claim-v1"
        or claim.get("experiment_id") != EXPERIMENT_ID
        or claim.get("run_id") != RUN_ID
        or claim.get("attempt_id") != ATTEMPT_ID
        or claim.get("stage") != "formal-extraction"
        or claim.get("status") != "Initialized"
        or claim.get("config") != artifact(config_path)
        or claim.get("parent_completion") != config["parent_no_result"]["completion"]
        or claim.get("input_manifest")
        != artifact(input_path, logical_name="input-manifest.json")
        or claim.get("worker_count") != 16
        or claim.get("access_history") != config["access_history"]
        or claim.get("claim_boundary") != config["claim_boundary"]
        or any(
            claim.get(key) is not False
            for key in (
                "formal_probe_authorized", "performance_metrics_authorized",
                "validation_access", "test_access",
            )
        )
    ):
        raise ValueError("EXP-070 initialization claim drift")
    expected_input_access = {
        "fold_manifest_values_read": True,
        "train_text_accessed": False,
        "train_label_values_used": False,
        "model_loaded": False,
        "forward_executed": False,
        "probe_fitted": False,
        "performance_metrics_computed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    if (
        input_manifest.get("schema_version") != "exp-070-extraction-input-v1"
        or input_manifest.get("experiment_id") != EXPERIMENT_ID
        or input_manifest.get("run_id") != RUN_ID
        or input_manifest.get("attempt_id") != ATTEMPT_ID
        or input_manifest.get("status") != "Initialized"
        or input_manifest.get("config") != artifact(config_path)
        or input_manifest.get("parent_no_result") != config["parent_no_result"]
        or input_manifest.get("parent_source_snapshot_sha256")
        != parent_contract["source_snapshot_sha256"]
        or input_manifest.get("exp069_runner") != config["sources"]["exp069_runner"]
        or input_manifest.get("workers") != expected_worker_plan()
        or input_manifest.get("access_history") != config["access_history"]
        or input_manifest.get("access") != expected_input_access
    ):
        raise ValueError("EXP-070 initialization manifest drift")
    rows = load_fold_rows(original)
    row_identity, fold_id = validate_row_contract(private, input_manifest, rows)
    expected_extract_access = {
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
    }
    if (
        extraction_manifest.get("schema_version") != "exp-070-extraction-manifest-v1"
        or extraction_manifest.get("experiment_id") != EXPERIMENT_ID
        or extraction_manifest.get("run_id") != RUN_ID
        or extraction_manifest.get("attempt_id") != ATTEMPT_ID
        or extraction_manifest.get("status") != "Completed"
        or extraction_manifest.get("config") != artifact(config_path)
        or extraction_manifest.get("input_manifest")
        != artifact(input_path, logical_name="input-manifest.json")
        or extraction_manifest.get("row_contract") != input_manifest.get("row_contract")
        or extraction_manifest.get("row_identity") != row_identity
        or extraction_manifest.get("raw_representation_bytes") != 2_890_137_600
        or extraction_manifest.get("max_errors") != run.get("max_errors")
        or run.get("resources", {}).get("total_elapsed_seconds")
        != extraction_manifest.get("resources", {}).get("total_elapsed_seconds")
        or run.get("resources", {}).get("maximum_mlx_peak_bytes")
        != extraction_manifest.get("resources", {}).get("maximum_mlx_peak_bytes")
        or type(run.get("resources", {}).get("private_bytes")) is not int
        or not 0 <= run["resources"]["private_bytes"] <= 5_368_709_120
        or extraction_manifest.get("access") != expected_extract_access
        or not isinstance(extraction_manifest.get("workers"), list)
        or len(extraction_manifest["workers"]) != 16
    ):
        raise ValueError("EXP-070 extraction manifest drift")
    if (
        run.get("schema_version") != "exp-070-extraction-run-v1"
        or run.get("experiment_id") != EXPERIMENT_ID
        or run.get("run_id") != RUN_ID
        or run.get("attempt_id") != ATTEMPT_ID
        or run.get("stage") != "formal-extraction"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("config") != artifact(config_path)
        or run.get("input_manifest") != artifact(input_path, logical_name="input-manifest.json")
        or run.get("extraction_manifest")
        != artifact(extraction_path, logical_name="extraction-manifest.json")
        or run.get("counts") != {"rows": ROWS, "workers": 16, "matrices": 16}
        or run.get("points")
        != {"seed_42": list(ALL_POINTS), "seeds_43_44": list(CONFIRMATION_POINTS)}
        or run.get("raw_representation_bytes") != 2_890_137_600
        or run.get("claim_boundary") != config["claim_boundary"]
        or any(
            run.get(key) is not False
            for key in (
                "formal_probe_executed", "performance_metrics_computed",
                "validation_accessed", "test_accessed",
            )
        )
    ):
        raise ValueError("EXP-070 public extraction run drift")
    if public_sensitive(claim) or public_sensitive(run):
        raise ValueError("EXP-070 public privacy drift")
    return extraction_manifest, rows, fold_id


def validate_worker_access(worker: dict[str, Any], spec: dict[str, Any]) -> None:
    expected = {
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
    if worker.get("access") != expected:
        raise PermissionError("EXP-070 worker access drift")


def require_external_record(record: dict[str, Any]) -> dict[str, Any]:
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


def validate_source_records(
    worker: dict[str, Any],
    spec: dict[str, Any],
    config: dict[str, Any],
    original: dict[str, Any],
    parent_contract: dict[str, Any],
) -> None:
    snapshot = parent_contract["source_snapshot"]
    expected: dict[str, Any] = {
        "formal_config": artifact(DEFAULT_CONFIG),
        "method_protocol": artifact(require_record(config["method_protocol"])),
        "formal_protocol": artifact(require_record(config["formal_protocol"])),
        "parent_input_contract": artifact(
            require_record(config["parent_no_result"]["input_contract"])
        ),
        "model_files": {
            name: artifact(require_record(record))
            for name, record in sorted(snapshot["model_files"].items())
        },
        "prompt": artifact(require_record(original["model"]["prompt"])),
        "exp069_runner": artifact(require_record(config["sources"]["exp069_runner"])),
        "formal_runner": artifact(require_record(config["implementation"]["runner"])),
        "qwen3_source": require_external_record(original["environment"]["qwen3_source"]),
    }
    if spec["kind"] == "m3":
        assert spec["seed"] is not None and spec["fold"] is not None
        for name in ("adapter", "head", "heldout"):
            key = f"seed-{spec['seed']}/fold-{spec['fold']}/{name}"
            expected[name] = artifact(
                require_record(parent_contract["source_snapshot"]["checkpoint_files"][key])
            )
    if worker.get("source_before") != expected or worker.get("source_after") != expected:
        raise ValueError("EXP-070 worker source binding drift")


def validate_worker_manifest(
    private: Path,
    spec: dict[str, Any],
    expected_identity: dict[str, Any],
    parent_contract: dict[str, Any],
    config: dict[str, Any],
    original: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    directory = private / "extraction" / spec["worker_id"]
    worker_path = directory / "worker.json"
    matrix_path = directory / "representations.npy"
    worker = strict_json(worker_path)
    expected_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "worker_id", "kind", "condition", "seed", "fold", "rows", "points", "shape", "dtype",
        "layout", "output",
        "row_identity", "token_id_stream_sha256", "max_errors", "heldout_rows_checked",
        "source_before", "source_after", "adapter_load_max_abs_error", "resume_count", "resources",
        "access", "checks",
    }
    if set(worker) != expected_keys:
        raise ValueError("EXP-070 worker schema drift")
    if (
        worker["schema_version"] != "exp-070-extraction-worker-v1"
        or worker["experiment_id"] != EXPERIMENT_ID
        or worker["run_id"] != RUN_ID
        or worker["attempt_id"] != ATTEMPT_ID
        or worker["stage"] != "formal-extraction"
        or worker["status"] != "Completed"
        or worker["worker_id"] != spec["worker_id"]
        or worker["kind"] != spec["kind"]
        or worker["condition"] != ("Frozen Qwen" if spec["kind"] == "base" else "M3")
        or worker["seed"] != spec["seed"]
        or worker["fold"] != spec["fold"]
        or worker["rows"] != ROWS
        or worker["points"] != spec["points"]
        or worker["shape"] != spec["shape"]
        or worker["dtype"] != "float32"
        or worker["layout"] != "C"
        or worker["row_identity"] != expected_identity
        or worker["output"]
        != artifact(matrix_path, logical_name=f"{spec['worker_id']}/representations.npy")
        or type(worker["resume_count"]) is not int
        or worker["resume_count"] < 0
    ):
        raise ValueError("EXP-070 worker identity drift")
    validate_worker_access(worker, spec)
    validate_source_records(worker, spec, config, original, parent_contract)
    errors = worker["max_errors"]
    if set(errors) != {"standard_hf", "m2_hf", "heldout_logit", "pre_lora"}:
        raise ValueError("EXP-070 worker parity schema drift")
    if set(errors["pre_lora"]) != set(PRE_LORA_POINTS):
        raise ValueError("EXP-070 worker pre-LoRA schema drift")
    scalar_errors = [errors[name] for name in ("standard_hf", "m2_hf", "heldout_logit")]
    parity_values = [*scalar_errors, *errors["pre_lora"].values()]
    if any(not math.isfinite(float(value)) or float(value) < 0 for value in parity_values):
        raise ValueError("EXP-070 worker parity value drift")
    if any(float(value) > 1e-5 for value in parity_values):
        raise ValueError("EXP-070 worker parity gate failed")
    adapter_error = float(worker["adapter_load_max_abs_error"])
    if not math.isfinite(adapter_error) or adapter_error != 0.0:
        raise ValueError("EXP-070 adapter-load parity gate failed")
    if worker["checks"] != {
        "finite_values": True,
        "row_count": ROWS,
        "token_count": ROWS,
        "continuous_chunk_prefix": True,
    }:
        raise ValueError("EXP-070 worker check-state drift")
    resources = worker["resources"]
    if set(resources) != {"elapsed_seconds", "mlx_peak_bytes"}:
        raise ValueError("EXP-070 worker resource schema drift")
    if (
        not math.isfinite(float(resources["elapsed_seconds"]))
        or not 0 <= float(resources["elapsed_seconds"]) <= 4 * 3600
        or type(resources["mlx_peak_bytes"]) is not int
        or not 0 <= resources["mlx_peak_bytes"] <= 10_000_000_000
    ):
        raise ValueError("EXP-070 worker resource gate failed")
    shape, dtype, fortran, offset = npy_header(matrix_path)
    if (
        list(shape) != spec["shape"]
        or dtype != np.dtype("float32")
        or fortran
        or matrix_path.stat().st_size != offset + spec["payload_bytes"]
    ):
        raise ValueError("EXP-070 NPY header or payload drift")
    matrix = np.load(matrix_path, mmap_mode="r", allow_pickle=False)
    if (
        matrix.shape != tuple(spec["shape"])
        or matrix.dtype != np.float32
        or not matrix.flags.c_contiguous
        or matrix.nbytes != spec["payload_bytes"]
    ):
        raise ValueError("EXP-070 representation schema drift")
    require_finite(matrix)
    return worker, matrix


def read_m2_features(original: dict[str, Any]) -> np.ndarray:
    path = require_record(original["m2_cache"]["features"])
    value = np.load(path, mmap_mode="r", allow_pickle=False)
    if value.shape != (ROWS, HIDDEN_SIZE) or value.dtype != np.float32:
        raise ValueError("EXP-070 M2 feature-cache schema drift")
    return value


def independent_heldout_error(
    worker: dict[str, Any],
    spec: dict[str, Any],
    matrix: np.ndarray,
    rows: Sequence[dict[str, Any]],
) -> float:
    assert spec["fold"] is not None
    head_path = require_record(worker["source_before"]["head"])
    heldout_path = require_record(worker["source_before"]["heldout"])
    head = read_safetensors_f32(head_path)
    reference_ids, reference_logits = load_heldout_reference(heldout_path, int(spec["fold"]))
    reference_index = {value: index for index, value in enumerate(reference_ids)}
    canonical = [row for row in rows if row["fold_id"] == spec["fold"]]
    if len(canonical) != 672 or {row["sample_id"] for row in canonical} != set(reference_ids):
        raise ValueError("EXP-070 heldout sample alignment drift")
    row_indices = np.asarray([row["ordinal"] for row in canonical], dtype=np.int64)
    reference_order = np.asarray(
        [reference_index[row["sample_id"]] for row in canonical], dtype=np.int64
    )
    hf_index = spec["points"].index("HF")
    hidden = np.asarray(matrix[row_indices, hf_index, :], dtype=np.float32)
    recomputed = (hidden @ head["weight"].T + head["bias"]).astype(np.float32)
    return max_abs(recomputed, reference_logits[reference_order])


def validate_all_workers(
    config: dict[str, Any],
    original: dict[str, Any],
    parent_contract: dict[str, Any],
    extraction_manifest: dict[str, Any],
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    private = resolve_project(config["outputs"]["private_root"])
    expected_identity = extraction_manifest["row_identity"]
    manifest_entries = extraction_manifest["workers"]
    if [entry.get("worker_id") for entry in manifest_entries] != [
        item["worker_id"] for item in expected_worker_plan()
    ]:
        raise ValueError("EXP-070 worker order drift")
    base_worker, base = validate_worker_manifest(
        private, expected_worker_plan()[0], expected_identity, parent_contract, config, original
    )
    base_entry = manifest_entries[0]
    base_directory = private / "extraction" / "base"
    if (
        set(base_entry) != {"worker_id", "manifest", "output", "max_errors", "resources"}
        or base_entry.get("worker_id") != "base"
        or base_entry.get("manifest")
        != artifact(base_directory / "worker.json", logical_name="base/worker.json")
        or base_entry.get("output") != base_worker["output"]
        or base_entry.get("max_errors") != base_worker["max_errors"]
        or base_entry.get("resources") != base_worker["resources"]
        or base_worker.get("heldout_rows_checked") != 0
    ):
        raise ValueError("EXP-070 base extraction-manifest binding drift")
    if base_worker["token_id_stream_sha256"] != original["m2_cache"]["token_id_stream_sha256"]:
        raise ValueError("EXP-070 base token-stream digest drift")
    m2 = read_m2_features(original)
    m2_error = full_max_abs(base[:, ALL_POINTS.index("HF"), :], m2)
    if m2_error > 1e-5 or not math.isclose(
        m2_error, float(base_worker["max_errors"]["m2_hf"]), rel_tol=0.0, abs_tol=1e-12
    ):
        raise ValueError("EXP-070 independent M2-HF parity gate failed")

    worker_values = [base_worker]
    raw_bytes = int(base.nbytes)
    elapsed = float(base_worker["resources"]["elapsed_seconds"])
    peak = int(base_worker["resources"]["mlx_peak_bytes"])
    max_errors = {
        "m2_hf": m2_error,
        "persisted_pre_lora": 0.0,
        "heldout_head_logit": 0.0,
        "recorded_transient_pre_lora": 0.0,
    }
    token_digest = base_worker["token_id_stream_sha256"]

    for index, spec in enumerate(expected_worker_plan()[1:], start=1):
        worker, matrix = validate_worker_manifest(
            private, spec, expected_identity, parent_contract, config, original
        )
        worker_values.append(worker)
        if worker["token_id_stream_sha256"] != token_digest:
            raise ValueError("EXP-070 cross-worker token-stream drift")
        if worker["heldout_rows_checked"] != 672:
            raise ValueError("EXP-070 heldout parity coverage drift")
        points_to_compare = PRE_LORA_POINTS if spec["seed"] == 42 else ("H19",)
        independent_by_point = {
            point: full_max_abs(
                matrix[:, spec["points"].index(point), :],
                base[:, ALL_POINTS.index(point), :],
            )
            for point in points_to_compare
        }
        persisted_error = max(independent_by_point.values(), default=0.0)
        recorded_by_point = {
            point: float(worker["max_errors"]["pre_lora"][point])
            for point in PRE_LORA_POINTS
        }
        recorded_pre_lora = max(recorded_by_point.values())
        if persisted_error > 1e-5 or recorded_pre_lora > 1e-5:
            raise ValueError("EXP-070 all-row pre-LoRA gate failed")
        for point in points_to_compare:
            if not math.isclose(
                independent_by_point[point],
                recorded_by_point[point],
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("EXP-070 persisted pre-LoRA point drift")
        if spec["seed"] in (43, 44) and any(
            recorded_by_point[point] > 1e-5 for point in ("H-1", "H7", "H15")
        ):
            raise ValueError("EXP-070 transient pre-LoRA record drift")
        heldout_error = independent_heldout_error(worker, spec, matrix, rows)
        if not math.isfinite(heldout_error) or heldout_error > 1e-5:
            raise ValueError("EXP-070 independent heldout-head parity gate failed")
        entry = manifest_entries[index]
        directory = private / "extraction" / spec["worker_id"]
        if (
            set(entry) != {"worker_id", "manifest", "output", "max_errors", "resources"}
            or entry.get("worker_id") != spec["worker_id"]
            or entry.get("manifest")
            != artifact(directory / "worker.json", logical_name=f"{spec['worker_id']}/worker.json")
            or entry.get("output") != worker["output"]
            or entry.get("max_errors") != worker["max_errors"]
            or entry.get("resources") != worker["resources"]
        ):
            raise ValueError("EXP-070 extraction-manifest worker binding drift")
        raw_bytes += int(matrix.nbytes)
        elapsed += float(worker["resources"]["elapsed_seconds"])
        peak = max(peak, int(worker["resources"]["mlx_peak_bytes"]))
        max_errors["persisted_pre_lora"] = max(
            max_errors["persisted_pre_lora"], persisted_error
        )
        max_errors["heldout_head_logit"] = max(
            max_errors["heldout_head_logit"], heldout_error
        )
        if spec["seed"] in (43, 44):
            max_errors["recorded_transient_pre_lora"] = max(
                max_errors["recorded_transient_pre_lora"],
                *(recorded_by_point[point] for point in ("H-1", "H7", "H15")),
            )
    if raw_bytes != config["extraction"]["raw_payload_bytes"]:
        raise ValueError("EXP-070 raw representation byte total drift")
    if elapsed > config["resources"]["aggregate_model_wall_hours"] * 3600:
        raise TimeoutError("EXP-070 aggregate worker wall-time gate failed")
    if peak > config["resources"]["worker_peak_mlx_gb"] * 1e9:
        raise MemoryError("EXP-070 peak MLX resource gate failed")
    private_size = sum(
        path.stat().st_size
        for path in private.rglob("*")
        if path.is_file()
    )
    if private_size > config["resources"]["private_disk_budget_bytes"]:
        raise OSError("EXP-070 private disk budget exceeded")
    if extraction_manifest["token_id_stream_sha256"] != token_digest:
        raise ValueError("EXP-070 extraction-manifest token digest drift")
    for entry, worker in zip(manifest_entries, worker_values):
        if entry.get("max_errors") != worker["max_errors"]:
            raise ValueError("EXP-070 worker aggregate binding drift")
    reported_errors: dict[str, Any] = {
        name: max(float(worker["max_errors"][name]) for worker in worker_values)
        for name in ("standard_hf", "m2_hf", "heldout_logit")
    }
    reported_errors["pre_lora"] = {
        point: max(
            float(worker["max_errors"]["pre_lora"][point])
            for worker in worker_values
        )
        for point in PRE_LORA_POINTS
    }
    if extraction_manifest.get("max_errors") != reported_errors:
        raise ValueError("EXP-070 extraction-manifest parity aggregate drift")
    if extraction_manifest.get("resources") != {
        "total_elapsed_seconds": elapsed,
        "maximum_mlx_peak_bytes": peak,
    }:
        raise ValueError("EXP-070 extraction-manifest resource aggregate drift")
    return {
        "raw_representation_bytes": raw_bytes,
        "private_bytes": private_size,
        "aggregate_elapsed_seconds": elapsed,
        "maximum_mlx_peak_bytes": peak,
        "max_errors": max_errors,
        "reported_errors": reported_errors,
    }


def verify(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_frozen_records(config)
    require_verifier_environment(config)
    original, parent_contract = validate_parent(config)
    extraction_manifest, rows, _ = validate_initialization(
        config_path, config, original, parent_contract
    )
    aggregate = validate_all_workers(
        config, original, parent_contract, extraction_manifest, rows
    )
    public = resolve_project(config["outputs"]["public_root"])
    private = resolve_project(config["outputs"]["private_root"])
    run_path = public / "extraction.json"
    manifest_path = private / "extraction-manifest.json"
    if (public / "failure.json").exists():
        raise RuntimeError("EXP-070 extraction failure record exists")
    run = strict_json(run_path)
    if (
        run.get("max_errors") != aggregate["reported_errors"]
        or run.get("resources")
        != {
            "total_elapsed_seconds": aggregate["aggregate_elapsed_seconds"],
            "maximum_mlx_peak_bytes": aggregate["maximum_mlx_peak_bytes"],
            "private_bytes": aggregate["private_bytes"],
        }
    ):
        raise ValueError("EXP-070 public aggregate replay drift")
    if any(
        path.name.lower().startswith(("probe", "prediction", "metric", "bootstrap", "shuffle"))
        for path in [*public.rglob("*"), *private.rglob("*")]
    ):
        raise ValueError("EXP-070 forbidden downstream artifact exists")
    checks = [
        "config_identity",
        "implementation_identity",
        "parent_no_result_gate",
        "source_snapshot_identity",
        "environment_identity",
        "public_inventory_modes_privacy",
        "private_inventory_modes_ignored",
        "initialization_binding",
        "row_contract_values_and_digests",
        "worker_order_and_manifest_binding",
        "sixteen_npy_headers_shapes_dtype_c_order",
        "sixteen_npy_full_finite_scan",
        "raw_representation_bytes",
        "cross_worker_token_digest",
        "independent_m2_hf_parity",
        "all_row_persisted_pre_lora_parity",
        "transient_pre_lora_record_gate",
        "independent_heldout_head_logit_parity",
        "source_before_after_identity",
        "resource_ceilings",
        "no_probe_threshold_shuffle_bootstrap_metrics",
        "no_validation_test_or_gold_access",
    ]
    access = {
        "train_text_read_by_verifier": False,
        "train_label_values_read_by_verifier": False,
        "fold_manifest_values_read": True,
        "m2_feature_values_read": True,
        "representation_values_read": True,
        "head_tensor_values_read": True,
        "heldout_members_read": ["sample_ids", "fold_ids", "logits"],
        "heldout_gold_read": False,
        "model_loaded": False,
        "forward_executed": False,
        "probe_fitted": False,
        "threshold_selected": False,
        "label_shuffle_executed": False,
        "bootstrap_executed": False,
        "performance_metrics_computed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    verification = {
        "schema_version": "exp-070-extraction-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "stage": "formal-extraction",
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "config": artifact(config_path),
        "run": artifact(run_path),
        "extraction_manifest": artifact(
            manifest_path, logical_name="extraction-manifest.json"
        ),
        "parent_no_result_completion": config["parent_no_result"]["completion"],
        "counts": {"rows": ROWS, "workers": 16, "matrices": 16},
        "raw_representation_bytes": aggregate["raw_representation_bytes"],
        "resources": {
            "private_bytes": aggregate["private_bytes"],
            "aggregate_elapsed_seconds": aggregate["aggregate_elapsed_seconds"],
            "maximum_mlx_peak_bytes": aggregate["maximum_mlx_peak_bytes"],
        },
        "max_errors": aggregate["max_errors"],
        "probe_fitting_authorized": False,
        "performance_metrics_computed": False,
        "exp071_authorized": False,
        "model_libraries_imported": False,
        "runner_imported": False,
        "access": access,
        "claim_boundary": config["claim_boundary"],
    }
    if public_sensitive(verification):
        raise ValueError("EXP-070 verification public privacy drift")
    verification_path = public / "extraction-verification.json"
    if verification_path.exists():
        if strict_json(verification_path) != verification or file_mode(verification_path) != "0644":
            raise ValueError("EXP-070 existing Passed verification drift")
    else:
        create_json_once(verification_path, verification)
    if inventory(public) != {
        "run-claim.json", "extraction.json", "extraction-verification.json"
    }:
        raise ValueError("EXP-070 public precompletion inventory drift")
    completion = {
        "schema_version": "exp-070-extraction-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Complete",
        "config": artifact(config_path),
        "run": artifact(run_path),
        "verification": artifact(verification_path),
        "extraction_manifest": artifact(
            manifest_path, logical_name="extraction-manifest.json"
        ),
        "parent_no_result_completion": config["parent_no_result"]["completion"],
        "formal_extraction_complete": True,
        "probe_fitting_authorized": False,
        "performance_metrics_computed": False,
        "exp070_complete": False,
        "exp071_authorized": False,
        "claim_boundary": config["claim_boundary"],
        "next_gate": "A separate immutable EXP-070 probe consumer remains required and unexecuted",
    }
    if public_sensitive(completion):
        raise ValueError("EXP-070 completion public privacy drift")
    completion_path = public / "extraction-complete.json"
    create_json_once(completion_path, completion)
    if inventory(public) != {
        "run-claim.json", "extraction.json", "extraction-verification.json",
        "extraction-complete.json",
    }:
        raise ValueError("EXP-070 terminal public inventory drift")
    if any(file_mode(public / name) != "0644" for name in inventory(public)):
        raise PermissionError("EXP-070 terminal public mode drift")
    return verification


def record_failure(config: dict[str, Any], error: BaseException) -> None:
    try:
        public = resolve_project(config["outputs"]["public_root"], must_exist=False)
        if not public.is_dir() or not (public / "extraction.json").is_file():
            return
        target = public / "extraction-verification.json"
        if os.path.lexists(target):
            return
        value = {
            "schema_version": "exp-070-extraction-verification-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "stage": "formal-extraction",
            "status": "Failed",
            "error_type": type(error).__name__,
            "formal_extraction_complete": False,
            "probe_fitting_authorized": False,
            "performance_metrics_computed": False,
            "exp070_complete": False,
            "exp071_authorized": False,
            "claim_boundary": config.get("claim_boundary"),
        }
        create_json_once(target, value)
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    try:
        result = verify(args.config, config)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        record_failure(config, error)
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Frozen EXP-072 singleton LoRA inference; scoring is a separate sealed consumer.

Import and metadata_gate never import NumPy/MLX or decode scientific arrays/text.
The only model entry point is an inherited-lock, fresh-process worker. Failed
prefixes are terminal; there is intentionally no resume or retry operation.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import shutil
import stat
import subprocess
import sys
import time
import traceback
from typing import Any, Iterator, Mapping, Sequence
import zipfile

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
PREFIX = "experiments/stack-overflow-emotion-gold/phase-b-representation"
EXPERIMENT_ID = "EXP-072"
RUN_ID = "exp-072-lora-functional-ablation"
ATTEMPT_ID = "formal-attempt-1"
DEFAULT_CONFIG = MODULE_DIR / "configs/exp-072-lora-functional-ablation.json"
HEAVY_LOCK = PREFIX + "/private/locks/heavy-research-workload.lock"
SCHEDULER_LOCK = PREFIX + "/private/locks/exp-072-scheduler.lock"
RECORD_FIELDS = {"path", "bytes", "mode", "sha256"}
IMPLEMENTATION_KEYS = {"runner", "tests", "scorer", "scoring_tests", "verifier", "verifier_tests"}
MODULES = ["self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj",
           "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj"]
DEFAULT_METHOD = {
    "seeds": [42, 43, 44], "folds": [0, 1, 2, 3, 4], "rows": 3360,
    "heldout_rows": 672, "labels": ["love", "joy", "surprise", "anger", "sadness", "fear"],
    "a0_conditions": ["A0"], "discovery_conditions": ["A1", "A2", "A3", "A4", "A5"],
    "replication_conditions": ["A1", "A2", "A3"], "worker_count": 70,
    "a0_worker_count": 15, "max_length": 384, "batch_size": 1,
    "lora_blocks": list(range(20, 36)), "lora_modules": MODULES,
    "lora_rank": 8, "lora_scale": 20.0, "lora_dropout": 0.0,
    "replay_dtype": "float32", "replay_atol": 1e-5, "replay_rtol": 0.0,
    "token_cache": False, "checkpoint_reconstruction": False,
}
DEFAULT_RESOURCES = {
    "max_workers": 70, "max_worker_wall_seconds": 3600,
    "max_total_wall_seconds": 57600, "max_mlx_bytes": 10_000_000_000,
    "max_rss_bytes": 16 * 1024**3, "max_private_bytes": 1024**3,
    "min_free_disk_bytes": 10 * 1024**3, "max_concurrent_workers": 1, "api_cost_usd": 0,
}
DEFAULT_AUTHORIZATION = {
    "formal_inference_authorized": True, "labels_before_prediction_seal": False,
    "validation_access": False, "test_access": False, "retraining": False,
    "calibration": False, "checkpoint_reconstruction": False,
    "automatic_retry": False, "automatic_resume": False,
}
INFERENCE_ACCESS = {
    "train_heldout_text_accessed": True, "sample_identity_accessed": True,
    "row_ordinal_fold_id_accessed": True, "model_forward_executed": True,
    "heldout_reference_logits_accessed": True, "labels_accessed": False,
    "component_ids_accessed": False, "threshold_values_accessed": False,
    "metrics_computed": False, "validation_accessed": False, "test_accessed": False,
    "training_executed": False, "calibration_executed": False,
    "token_cache_written": False, "external_api_accessed": False,
}
METADATA_ACCESS = {key: False for key in INFERENCE_ACCESS}
PINNED_HELPERS = {
    "exp069": ("run_exp069_preflight.py", 54903,
               "cb2655c61f7ff4e49ed9de47cbd92176e9547273e3e378f7c26ae587b2735bb0"),
    "exp070": ("run_exp070_extraction.py", 79878,
               "83ab85046490023380ced3d95922791ad9592d5ed2e3ee092085fc86b70c7025"),
    "selective_json": ("verify_exp071_drift.py", 121050,
                       "0a6e0e03a2f14212bc2bf0d3a1ecc3d9cf4eec1ee8a3a9f7b44cd3ca83a0bbd2"),
}
PINNED_SOURCE = {
    "exp069_config": (13544, "a7f7ac209d9d3993c901cbdf92b20b64e3f810fcdd97a50e4e7064411f6597e2"),
    "exp069_input_manifest": (34133, "7c6fc8546a472265317dcd8af7516bdf837a2db525f5f805b17531e4e590146d"),
    "exp070_input_contract": (63253, "9bf597dd1b2a43000c726033ed25f0ead3ed7c89251f093e8b799ff25a954c86"),
    "exp070_row_contract": (31014, "f85a250cb2809f1cf5f33f6faf21dccc1eacccae3cbdc8adb839d4ae97f22308"),
}
THRESHOLD_SHAS = {
    42: "47aaa4a8a9a8e45a9ddd1a4ee9f99573ab56b592cf6d921546a2025e36421f27",
    43: "e53f61344e1b298c2ea2894c02f5a5eec74c6a0cb2b30f90bc97c7c6660ecc37",
    44: "25b6d2702e769d52e555840c93d23e3e8f70ae1cf339e50099a68638c25e6e99",
}


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid(value: str) -> None:
        raise ValueError("Non-finite JSON")
    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=invalid)


def resolve_project(relative: str, *, must_exist: bool = True) -> Path:
    if type(relative) is not str:
        raise TypeError("Path must be a string")
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or pure.as_posix() != relative or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise ValueError("Unsafe project path")
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink path rejected")
    if must_exist and not current.exists():
        raise FileNotFoundError("Required project artifact missing")
    return current


def artifact(path: Path) -> dict[str, Any]:
    path = Path(path)
    relative = path.relative_to(PROJECT_ROOT).as_posix()
    resolve_project(relative)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Artifact must be a single-link regular file")
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024**2), b""):
            h.update(chunk)
    after = path.stat()
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise ValueError("Artifact changed during hashing")
    return {"path": relative, "bytes": info.st_size,
            "mode": f"{stat.S_IMODE(info.st_mode):04o}", "sha256": h.hexdigest()}


def require_record(record: Mapping[str, Any]) -> Path:
    if set(record) != RECORD_FIELDS or type(record["bytes"]) is not int or record["bytes"] < 0:
        raise ValueError("Exact four-field artifact required")
    path = resolve_project(record["path"])
    if artifact(path) != record:
        raise ValueError("Frozen artifact identity drift")
    return path


def _import_record(record: Mapping[str, Any], name: str) -> Any:
    path = require_record(record)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("Frozen helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_workers() -> list[dict[str, Any]]:
    def item(seed: int, fold: int, condition: str) -> dict[str, Any]:
        return {"worker_id": f"s{seed}-f{fold}-{condition}", "seed": seed,
                "fold": fold, "condition": condition}
    result = [item(seed, fold, "A0") for seed in (42, 43, 44) for fold in range(5)]
    for seed in (42, 43, 44):
        for condition in (("A1", "A2", "A3", "A4", "A5") if seed == 42 else ("A1", "A2", "A3")):
            result.extend(item(seed, fold, condition) for fold in range(5))
    return result


def scale_map(condition: str) -> list[dict[str, Any]]:
    if condition not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
        raise ValueError("Unknown frozen condition")
    result = []
    for block in range(20, 36):
        for name in MODULES:
            disabled = (condition == "A1" or condition == "A2" and name.startswith("self_attn.")
                        or condition == "A3" and name.startswith("mlp.")
                        or condition == "A4" and block <= 27 or condition == "A5" and block >= 28)
            result.append({"block": block, "module": name, "scale": 0.0 if disabled else 20.0})
    return result


def roots(config: Mapping[str, Any]) -> tuple[Path, Path]:
    output = config["outputs"]
    expected = {"public_root": f"{PREFIX}/runs/{RUN_ID}/{ATTEMPT_ID}",
                "private_root": f"{PREFIX}/private/{RUN_ID}/{ATTEMPT_ID}"}
    if any(output.get(key) != value for key, value in expected.items()):
        raise ValueError("Output root drift")
    return (resolve_project(expected["public_root"], must_exist=False),
            resolve_project(expected["private_root"], must_exist=False))


def load_config(config_path: Path) -> dict[str, Any]:
    config_path = Path(config_path).absolute()
    artifact(config_path)
    config = strict_json(config_path)
    expected = {"schema_version": "exp-072-lora-ablation-config-v1", "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID, "attempt_id": ATTEMPT_ID, "tier": "Major", "rq_id": "RQ-S4.3",
                "method": DEFAULT_METHOD, "resources": DEFAULT_RESOURCES,
                "authorization": DEFAULT_AUTHORIZATION}
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("Frozen EXP-072 contract drift")
    implementation = config["implementation"]
    if not {"runner", "tests"}.issubset(implementation) or not set(implementation).issubset(IMPLEMENTATION_KEYS):
        raise ValueError("Implementation inventory drift")
    expected_files = {"runner": "run_exp072_ablation.py", "tests": "tests/test_exp072_ablation.py",
                      "scorer": "score_exp072_ablation.py", "scoring_tests": "tests/test_exp072_scoring.py",
                      "verifier": "verify_exp072_ablation.py", "verifier_tests": "tests/test_exp072_verifier.py"}
    for name, record in implementation.items():
        if require_record(record) != MODULE_DIR / expected_files[name]:
            raise ValueError("Implementation path drift")
    require_record(config["method_protocol"])
    for key, (name, size, sha) in PINNED_HELPERS.items():
        record = config["source"]["helpers"][key]
        if record != {"path": f"{PREFIX}/{name}", "bytes": size, "mode": "0644", "sha256": sha}:
            raise ValueError("Frozen helper record drift")
        require_record(record)
    for key, (size, sha) in PINNED_SOURCE.items():
        record = config["source"][key]
        if record["bytes"] != size or record["sha256"] != sha:
            raise ValueError("Original source identity drift")
        require_record(record)
    roots(config)
    return config


def require_environment(original: Mapping[str, Any]) -> None:
    env = original["environment"]
    if os.path.realpath(sys.executable) != os.path.realpath(env["python_executable"]):
        raise ValueError("Python executable drift")
    if platform.python_version() != env["python_version"] or platform.machine() != env["architecture"]:
        raise ValueError("Python/platform drift")
    if {name: importlib.metadata.version(name) for name in env["packages"]} != env["packages"]:
        raise ValueError("Package drift")
    if any(os.environ.get(key) != value for key, value in env["offline_environment"].items()):
        raise ValueError("Offline/thread environment drift")
    record = env["qwen3_source"]
    path = Path(record["path"])
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("External model source unsafe")
    if (path.stat().st_size != record["bytes"] or f"{stat.S_IMODE(path.stat().st_mode):04o}" != record["mode"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]):
        raise ValueError("External model source drift")


def metadata_gate(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    """Rehash minimal source set, never recursively open the old full snapshot."""
    source = config["source"]
    helper = _import_record(source["helpers"]["selective_json"], "exp072_selective_metadata")
    snapshot: dict[str, Any] = {}
    def add(record: Mapping[str, Any]) -> Path:
        path = require_record(record)
        if record["path"] in snapshot and snapshot[record["path"]] != record:
            raise ValueError("Conflicting source records")
        snapshot[record["path"]] = dict(record)
        return path
    add(artifact(config_path))
    add(config["method_protocol"])
    for record in config["implementation"].values():
        add(record)
    for record in source["helpers"].values():
        add(record)
    for key in PINNED_SOURCE:
        add(source[key])
    original = strict_json(require_record(source["exp069_config"]))
    # EXP-069's unrelated smoke rows carry IDs; only its checkpoint-record subtree
    # may be materialized by this metadata-only gate.
    _, spans = helper.select_json_scalars(require_record(source["exp069_input_manifest"]).read_bytes(), [],
                                          capture_paths=[("m3_sources",)])
    manifest = {"m3_sources": helper.strict_json_bytes(spans[("m3_sources",)])}
    contract = strict_json(require_record(source["exp070_input_contract"]))
    if config["environment"] != original["environment"]:
        raise ValueError("Environment no longer equals EXP-069")
    require_environment(original)
    for key, experiment in (("exp069_completion", "EXP-069"), ("exp070_extraction_completion", "EXP-070"),
                            ("exp075_verification", "EXP-075")):
        path = add(config["parents"][key])
        targets = [("experiment_id",), ("status",)]
        if experiment == "EXP-075":
            targets.extend([("exp075_complete",), ("complete",)])
        values, _ = helper.select_json_scalars(path.read_bytes(), targets)
        if values.get(("experiment_id",)) != experiment or values.get(("status",)) != (
            "Passed" if experiment == "EXP-075" else "Complete"
        ):
            raise ValueError("Parent terminal gate not satisfied")
        if experiment == "EXP-075" and (values.get(("exp075_complete",)) is not True or values.get(("complete",)) is not True):
            raise ValueError("EXP-075 geometry gate incomplete")
    old_snapshot = contract["source_snapshot"]
    if digest(old_snapshot) != contract["source_snapshot_sha256"]:
        raise ValueError("EXP-070 snapshot metadata digest drift")
    for key in ("train", "fold_manifest_public", "fold_manifest_private"):
        add(original["data"][key])
    add(original["model"]["prompt"])
    models = old_snapshot["model_files"]
    if len(models) != 9 or any(record["path"] != original["model"]["base_path"] + "/" + name for name, record in models.items()):
        raise ValueError("Base model file inventory drift")
    for record in models.values():
        add(record)
    sources = manifest["m3_sources"]
    if [(value["seed"], value["fold"]) for value in sources] != [(s, f) for s in (42, 43, 44) for f in range(5)]:
        raise ValueError("Fifteen-fold source order drift")
    checkpoint_count = 0
    for value in sources:
        for name in ("run", "verification", "adapter", "head", "heldout_logits", "checkpoint_provenance"):
            record = value[name]
            if record is None:
                if name != "checkpoint_provenance" or value["seed"] != 42:
                    raise ValueError("Missing checkpoint source")
                continue
            path = add(record)
            checkpoint_count += 1
            if name in {"adapter", "head", "heldout_logits", "checkpoint_provenance"}:
                suffix = "heldout" if name == "heldout_logits" else name
                key = f"seed-{value['seed']}/fold-{value['fold']}/{suffix}"
                if old_snapshot["checkpoint_files"].get(key) != record:
                    raise ValueError("EXP-069/070 checkpoint binding drift")
            if name == "verification":
                selected, _ = helper.select_json_scalars(path.read_bytes(), [("status",)])
                if selected.get(("status",)) != "Passed":
                    raise ValueError("Original fold verification failed")
    if checkpoint_count != 85:
        raise ValueError("Expected exactly 85 fold metadata/checkpoint artifacts")
    thresholds = source["thresholds"]
    if [item["seed"] for item in thresholds] != [42, 43, 44]:
        raise ValueError("Threshold seed inventory drift")
    for item in thresholds:
        if item["allowed_members"] != ["fold_ids", "m3_raw_thresholds"] or item["artifact"]["sha256"] != THRESHOLD_SHAS[item["seed"]]:
            raise ValueError("Frozen threshold container drift")
        add(item["artifact"])
    return {"original_config": original, "exp069_manifest": manifest, "exp070_contract": contract,
            "source_snapshot": snapshot, "source_snapshot_sha256": digest(snapshot)}


def create_bytes_once(path: Path, payload: bytes, *, private: bool) -> dict[str, Any]:
    resolve_project(path.relative_to(PROJECT_ROOT).as_posix(), must_exist=False)
    if os.path.lexists(path) or not path.parent.is_dir():
        raise FileExistsError("Output already exists or parent missing")
    mode = 0o600 if private else 0o644
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.fchmod(descriptor, mode)
        os.link(temporary, path)
    finally:
        os.close(descriptor)
        if temporary.exists():
            temporary.unlink()
    return artifact(path)


def create_json_once(path: Path, value: Any, *, private: bool = False) -> dict[str, Any]:
    return create_bytes_once(path, canonical_json_bytes(value), private=private)


def read_npz_members(path: Path, names: Sequence[str]) -> dict[str, Any]:
    """Decode only named NPY members, including compressed containers; never gold."""
    import numpy as np
    result = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(set(members)) != len(members):
            raise ValueError("Duplicate ZIP members")
        for name in names:
            member = name + ".npy"
            if member not in members or archive.getinfo(member).file_size > 16 * 1024**2:
                raise ValueError("Missing or oversized selective NPZ member")
            with archive.open(member) as handle:
                value = np.lib.format.read_array(handle, allow_pickle=False)
                if handle.read(1):
                    raise ValueError("Trailing selective NPY bytes")
            if value.dtype.hasobject:
                raise ValueError("Object member forbidden")
            result[name] = value
    return result


def load_row_contract(path: Path) -> tuple[Any, Any]:
    import numpy as np
    values = read_npz_members(path, ("ordinal", "fold_id"))
    ordinal, folds = values["ordinal"], values["fold_id"]
    if ordinal.dtype != np.dtype("int32") or folds.dtype != np.dtype("int8") or ordinal.shape != (3360,) or folds.shape != (3360,):
        raise ValueError("Row contract shape/dtype drift")
    if not np.array_equal(ordinal, np.arange(3360, dtype=np.int32)) or [int(np.sum(folds == f)) for f in range(5)] != [672] * 5:
        raise ValueError("Row contract fold coverage drift")
    return ordinal, folds


def load_selected_text(path: Path, ordinals: Sequence[int], selector: Any, *, expected_rows: int = 3360) -> list[dict[str, Any]]:
    """The parser skips gold lexically; unselected rows are never JSON-decoded."""
    wanted = set(map(int, ordinals))
    if len(wanted) != len(ordinals) or any(value < 0 or value >= expected_rows for value in wanted):
        raise ValueError("Invalid heldout ordinal selection")
    result = []
    count = 0
    with path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            count += 1
            if ordinal not in wanted:
                continue
            values, _ = selector(line, [("sample_id",), ("text",)])
            sample_id, text = values.get(("sample_id",)), values.get(("text",))
            if not isinstance(sample_id, str) or not sample_id or not isinstance(text, str):
                raise ValueError("Selected train row schema drift")
            result.append({"ordinal": ordinal, "sample_id": sample_id, "text": text})
    if count != expected_rows or len(result) != len(wanted) or len({row["sample_id"] for row in result}) != len(result):
        raise ValueError("Selected train identity/count drift")
    return result


def array_sha256(value: Any) -> str:
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()


def string_digest(values: Sequence[str]) -> str:
    value = hashlib.sha256()
    for item in values:
        payload = item.encode("utf-8")
        value.update(len(payload).to_bytes(4, "little"))
        value.update(payload)
    return value.hexdigest()


def replay_check(observed: Any, reference: Any) -> dict[str, Any]:
    import numpy as np
    if observed.dtype != np.dtype("float32") or reference.dtype != np.dtype("float32") or observed.shape != reference.shape:
        raise ValueError("A0 replay dtype/shape drift")
    if not np.isfinite(observed).all() or not np.isfinite(reference).all():
        raise ValueError("Nonfinite A0 logits")
    error = float(np.max(np.abs(observed.astype(np.float64) - reference.astype(np.float64)), initial=0.0))
    if error > 1e-5:
        raise ValueError("A0 frozen 1e-5 replay gate failed")
    return {"required": True, "checked_rows": int(len(observed)), "max_abs_error": error, "atol": 1e-5, "rtol": 0.0}


def apply_scale_map(model: Any, condition: str, *, apply: bool) -> str:
    expected = {(v["block"], v["module"]): v["scale"] for v in scale_map(condition)}
    observed = set()
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError("Unexpected LoRA module path")
        key = (int(match.group(1)), match.group(2))
        if key not in expected or key in observed or int(module.lora_a.shape[-1]) != 8 or int(module.lora_b.shape[0]) != 8 or float(module.dropout._p_1) != 1.0:
            raise ValueError("LoRA inventory/rank/dropout drift")
        if apply:
            if float(module.scale) != 20.0:
                raise ValueError("LoRA pre-intervention scale drift")
            module.scale = expected[key]
        if float(module.scale) != expected[key]:
            raise ValueError("LoRA fixed scale map drift")
        observed.add(key)
    if observed != set(expected):
        raise ValueError("Expected 112 LoRA branches")
    return digest(scale_map(condition))


def _peak_rss() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def check_budget(started: float, private: Path, *, mlx_bytes: int = 0, worker: bool = False) -> dict[str, Any]:
    elapsed, rss = time.monotonic() - started, _peak_rss()
    limit = DEFAULT_RESOURCES["max_worker_wall_seconds" if worker else "max_total_wall_seconds"]
    if elapsed > limit or rss > DEFAULT_RESOURCES["max_rss_bytes"] or mlx_bytes > DEFAULT_RESOURCES["max_mlx_bytes"]:
        raise RuntimeError("Frozen time/memory budget exceeded")
    total = 0
    if private.exists():
        for path in private.rglob("*"):
            if path.is_symlink() or (path.is_file() and path.stat().st_nlink != 1):
                raise ValueError("Unsafe private output tree")
            if path.is_file():
                total += path.stat().st_size
    if total > DEFAULT_RESOURCES["max_private_bytes"]:
        raise RuntimeError("Private output budget exceeded")
    return {"wall_seconds": elapsed, "peak_mlx_bytes": mlx_bytes, "peak_rss_bytes": rss}


@contextmanager
def file_lock(relative: str) -> Iterator[int]:
    path = resolve_project(relative, must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if f"{stat.S_IMODE(path.parent.stat().st_mode):04o}" != "0700":
        raise ValueError("Lock directory mode drift")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("Unsafe persistent lock inode")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield descriptor
    finally:
        os.close(descriptor)


def _inherited_lock(claim: Mapping[str, Any]) -> None:
    raw = os.environ.get("EXP072_HEAVY_LOCK_FD", "")
    if not raw.isdecimal() or claim["scheduler_pid"] != os.getppid():
        raise PermissionError("Worker requires live scheduling parent")
    descriptor = int(raw)
    path = resolve_project(HEAVY_LOCK)
    fd_info, path_info = os.fstat(descriptor), path.stat()
    if (fd_info.st_dev, fd_info.st_ino) != (path_info.st_dev, path_info.st_ino) or fd_info.st_nlink != 1:
        raise PermissionError("Worker inherited lock inode mismatch")
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _mkdir_root(path: Path, *, private: bool) -> None:
    if os.path.lexists(path):
        raise FileExistsError("Fresh output root required")
    mode = 0o700 if private else 0o755
    path.parent.mkdir(parents=True, exist_ok=True, mode=mode)
    resolve_project(path.relative_to(PROJECT_ROOT).as_posix(), must_exist=False)
    path.mkdir(mode=mode)
    os.chmod(path, mode)
    (path / "workers").mkdir(mode=mode)
    os.chmod(path / "workers", mode)


def _common() -> dict[str, str]:
    return {"experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID}


def _source_for(context: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    matches = [value for value in context["exp069_manifest"]["m3_sources"]
               if (value["seed"], value["fold"]) == (spec["seed"], spec["fold"])]
    if len(matches) != 1:
        raise ValueError("Fold checkpoint identity ambiguous")
    return matches[0]


def _worker_prefix(config: Mapping[str, Any], config_path: Path, spec: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    public, private = roots(config)
    for root, mode in ((public, 0o755), (private, 0o700)):
        if not root.is_dir() or root.is_symlink() or stat.S_IMODE(root.stat().st_mode) != mode:
            raise ValueError("Output root mode drift")
    claim = strict_json(public / "run-claim.json")
    if claim.get("status") != "Running" or claim.get("config") != artifact(config_path):
        raise ValueError("Run claim binding drift")
    _inherited_lock(claim)
    manifest = strict_json(private / "input-manifest.json")
    if claim.get("input_manifest") != artifact(private / "input-manifest.json") or manifest.get("config") != artifact(config_path):
        raise ValueError("Input manifest binding drift")
    workers = expected_workers()
    index = workers.index(dict(spec))
    previous = workers[:index]
    expected_public = {v["worker_id"] + ".json" for v in previous}
    expected_private = {v["worker_id"] + suffix for v in previous for suffix in (".json", ".npz")}
    if {path.name for path in (public / "workers").iterdir()} != expected_public or {path.name for path in (private / "workers").iterdir()} != expected_private:
        raise ValueError("Worker ordering or fresh-prefix gate failed")
    if {p.name for p in public.iterdir()} != {"workers", "run-claim.json", "stdout.log"} or {p.name for p in private.iterdir()} != {"workers", "input-manifest.json"}:
        raise ValueError("Unexpected or failed inference prefix")
    for earlier in previous:
        validate_worker(config, config_path, earlier)
    return claim, manifest


def _tensor_fingerprints(model: Any, head: Any, mx: Any, flatten: Any) -> dict[str, str]:
    import numpy as np
    def tensors(values: Sequence[tuple[str, Any]]) -> str:
        result = {}
        for name, value in values:
            mx.eval(value)
            array = np.asarray(value.astype(mx.float32), dtype=np.float32)
            if not np.isfinite(array).all():
                raise ValueError("Nonfinite frozen model tensor")
            result[name] = {"shape": list(array.shape), "sha256": array_sha256(array)}
        return digest(result)
    base = sorted((name, value) for name, value in flatten(model.parameters())
                  if not name.endswith((".lora_a", ".lora_b")))
    if len(base) < 16:
        raise ValueError("Base tensor inventory too small")
    positions = sorted({round(index * (len(base) - 1) / 15) for index in range(16)})
    sentinel = hashlib.sha256()
    for position in positions:
        name, value = base[position]
        size = int(value.size)
        indices = sorted({0, size // 3, (2 * size) // 3, size - 1})
        sample = np.asarray(value.reshape(-1)[mx.array(indices)].astype(mx.float32), dtype=np.float32)
        if not np.isfinite(sample).all():
            raise ValueError("Nonfinite sampled base sentinel")
        sentinel.update(name.encode())
        sentinel.update(str(tuple(value.shape)).encode())
        sentinel.update(sample.tobytes(order="C"))
    return {"adapter": tensors(flatten(model.trainable_parameters())),
            "head": tensors(flatten(head.parameters())), "base_sentinel": sentinel.hexdigest()}


def worker(config_path: Path, config: Mapping[str, Any], worker_id: str) -> dict[str, Any]:
    spec = next((value for value in expected_workers() if value["worker_id"] == worker_id), None)
    if spec is None:
        raise ValueError("Worker outside frozen plan")
    started = time.monotonic()
    public, private = roots(config)
    _, input_manifest = _worker_prefix(config, config_path, spec)
    context = metadata_gate(config_path, config)
    if context["source_snapshot"] != input_manifest["source_snapshot"] or context["source_snapshot_sha256"] != input_manifest["source_snapshot_sha256"]:
        raise ValueError("Pre-value source snapshot drift")
    check_budget(started, private, worker=True)
    import numpy as np
    import mlx.core as mx
    import mlx.nn as nn
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers
    from mlx.utils import tree_flatten
    from safetensors.numpy import load_file as load_safetensors
    original = context["original_config"]
    exp069 = _import_record(config["source"]["helpers"]["exp069"], "exp072_frozen_prompt")
    exp070 = _import_record(config["source"]["helpers"]["exp070"], "exp072_frozen_reference")
    selector = _import_record(config["source"]["helpers"]["selective_json"], "exp072_selective_text")
    ordinal, folds = load_row_contract(require_record(config["source"]["exp070_row_contract"]))
    selected_ordinals = ordinal[folds == spec["fold"]]
    rows = load_selected_text(require_record(original["data"]["train"]), selected_ordinals.tolist(), selector.select_json_scalars)
    source = _source_for(context, spec)
    source_before = {name: artifact(require_record(source[key])) for name, key in
                     (("adapter", "adapter"), ("head", "head"), ("heldout", "heldout_logits"))}
    reference_index, _, reference_logits = exp070._load_reference(require_record(source["heldout_logits"]), spec["fold"])
    if set(reference_index) != {row["sample_id"] for row in rows}:
        raise ValueError("Heldout sample identity mismatch")
    aligned_reference = reference_logits[[reference_index[row["sample_id"]] for row in rows]]
    if not np.isfinite(aligned_reference).all():
        raise ValueError("Nonfinite old heldout reference")
    prompt = strict_json(require_record(original["model"]["prompt"]))
    mx.reset_peak_memory()
    model, tokenizer = load(str(resolve_project(original["model"]["base_path"])), lazy=False)
    model.freeze()
    model.eval()
    mx.random.seed(spec["seed"])
    head = nn.Linear(2560, 6, bias=True)
    mx.random.seed(spec["seed"] + 100000)
    linear_to_lora_layers(model, 16, {"rank": 8, "scale": 20.0, "dropout": 0.0, "keys": MODULES})
    model.eval()
    head.eval()
    exp069.lora_identity(model)
    adapter_path, head_path = require_record(source["adapter"]), require_record(source["head"])
    adapter_arrays, head_arrays = load_safetensors(str(adapter_path)), load_safetensors(str(head_path))
    model.load_weights(str(adapter_path), strict=False)
    head.load_weights(str(head_path), strict=True)
    runtime_arrays = dict(tree_flatten(model.trainable_parameters()))
    head_runtime = dict(tree_flatten(head.parameters()))
    if set(runtime_arrays) != set(adapter_arrays) or len(runtime_arrays) != 224 or set(head_arrays) != {"weight", "bias"} or set(head_runtime) != set(head_arrays):
        raise ValueError("Adapter/head tensor inventory drift")
    for runtime, expected in ((runtime_arrays, adapter_arrays), (head_runtime, head_arrays)):
        for name, value in expected.items():
            observed = np.asarray(runtime[name].astype(mx.float32), dtype=np.float32)
            expected32 = np.asarray(value, dtype=np.float32)
            if not np.isfinite(observed).all() or not np.array_equal(observed, expected32):
                raise ValueError("Frozen checkpoint load drift")
    tensor_before = _tensor_fingerprints(model, head, mx, tree_flatten)
    exp069.lora_identity(model)
    scale_digest = apply_scale_map(model, spec["condition"], apply=True)
    logits = np.empty((672, 6), dtype=np.float32)
    token_pairs = []
    for index, row in enumerate(rows):
        ids, _, _ = exp069.qwen_prompt_ids(tokenizer, prompt, row["text"], 384)
        token_pairs.append((row["ordinal"], ids))
        hidden = model.model(mx.array([ids], dtype=mx.int32))
        value = head(hidden[:, -1, :].astype(head.weight.dtype)).astype(mx.float32)
        mx.eval(value)
        observed = np.asarray(value, dtype=np.float32)
        if observed.shape != (1, 6) or not np.isfinite(observed).all():
            raise ValueError("Invalid model logits")
        logits[index] = observed[0]
        check_budget(started, private, mlx_bytes=int(mx.get_peak_memory()), worker=True)
        del hidden, value
    token_digest = exp069.token_stream_digest(token_pairs)
    sample_digest = string_digest([row["sample_id"] for row in rows])
    del token_pairs, rows
    replay = replay_check(logits, aligned_reference) if spec["condition"] == "A0" else {
        "required": False, "checked_rows": 0, "max_abs_error": None, "atol": 1e-5, "rtol": 0.0}
    if spec["condition"] != "A0":
        a0 = strict_json(private / "workers" / f"s{spec['seed']}-f{spec['fold']}-A0.json")
        if token_digest != a0["token_stream_sha256"] or tensor_before != a0["tensor_before"]:
            raise ValueError("Ablation rendering/tensor identity differs from Full")
    apply_scale_map(model, spec["condition"], apply=False)
    tensor_after = _tensor_fingerprints(model, head, mx, tree_flatten)
    if tensor_after != tensor_before:
        raise ValueError("Inference mutated checkpoint/base sentinel")
    source_after = {name: artifact(require_record(record)) for name, record in source_before.items()}
    if source_after != source_before:
        raise ValueError("Checkpoint source mutation")
    # Rehash all minimal sources, including base model, data and prompt, after forward.
    for record in input_manifest["source_snapshot"].values():
        require_record(record)
    output = io.BytesIO()
    output_folds = np.full(672, spec["fold"], dtype=np.int8)
    np.savez(output, ordinal=selected_ordinals, fold_id=output_folds, logits=logits)
    output_record = create_bytes_once(private / "workers" / f"{worker_id}.npz", output.getvalue(), private=True)
    resources = check_budget(started, private, mlx_bytes=int(mx.get_peak_memory()), worker=True)
    manifest = {"schema_version": "exp-072-worker-private-v1", **_common(), **spec,
                "status": "Completed", "config": artifact(config_path),
                "input_manifest": artifact(private / "input-manifest.json"), "output": output_record,
                "row_order_sha256": array_sha256(selected_ordinals), "fold_id_sha256": array_sha256(output_folds),
                "sample_id_order_sha256": sample_digest,
                "token_stream_sha256": token_digest, "source_before": source_before, "source_after": source_after,
                "tensor_before": tensor_before, "tensor_after": tensor_after, "scale_map_sha256": scale_digest,
                "disabled_modules": sum(value["scale"] == 0 for value in scale_map(spec["condition"])),
                "rows": 672, "replay": replay, "resources": resources, "access": dict(INFERENCE_ACCESS)}
    manifest_record = create_json_once(private / "workers" / f"{worker_id}.json", manifest, private=True)
    public_value = {"schema_version": "exp-072-worker-public-v1", **_common(), **spec,
                    "status": "Completed", "rows": 672, "output_sha256": output_record["sha256"],
                    "manifest_sha256": manifest_record["sha256"], "replay": replay,
                    "disabled_modules": manifest["disabled_modules"], "scale_map_sha256": scale_digest,
                    "resources": resources, "access": dict(INFERENCE_ACCESS)}
    create_json_once(public / "workers" / f"{worker_id}.json", public_value)
    return public_value


def validate_worker(config: Mapping[str, Any], config_path: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    """Metadata/hash-only worker validation, also reusable after prediction seal."""
    public, private = roots(config)
    worker_id = spec["worker_id"]
    public_path, manifest_path = public / "workers" / f"{worker_id}.json", private / "workers" / f"{worker_id}.json"
    output_path = private / "workers" / f"{worker_id}.npz"
    public_value, manifest = strict_json(public_path), strict_json(manifest_path)
    private_keys = {"schema_version", "experiment_id", "run_id", "attempt_id", "worker_id", "seed", "fold", "condition",
                    "status", "config", "input_manifest", "output", "row_order_sha256", "fold_id_sha256",
                    "sample_id_order_sha256", "token_stream_sha256", "source_before", "source_after", "tensor_before",
                    "tensor_after", "scale_map_sha256", "disabled_modules", "rows", "replay", "resources", "access"}
    if set(manifest) != private_keys or manifest.get("schema_version") != "exp-072-worker-private-v1":
        raise ValueError("Worker private schema drift")
    for path, mode in ((public_path, "0644"), (manifest_path, "0600"), (output_path, "0600")):
        if artifact(path)["mode"] != mode:
            raise ValueError("Worker artifact mode drift")
    for value in (public_value, manifest):
        if any(value.get(key) != val for key, val in {**_common(), **spec, "status": "Completed", "rows": 672}.items()):
            raise ValueError("Worker terminal identity drift")
        if value.get("access") != INFERENCE_ACCESS or value.get("scale_map_sha256") != digest(scale_map(spec["condition"])):
            raise ValueError("Worker access/scale drift")
        if value.get("disabled_modules") != sum(item["scale"] == 0 for item in scale_map(spec["condition"])):
            raise ValueError("Worker disabled count drift")
    if manifest["config"] != artifact(config_path) or manifest["input_manifest"] != artifact(private / "input-manifest.json"):
        raise ValueError("Worker parent binding drift")
    if manifest["output"] != artifact(output_path) or public_value["output_sha256"] != manifest["output"]["sha256"] or public_value["manifest_sha256"] != artifact(manifest_path)["sha256"]:
        raise ValueError("Worker artifact binding drift")
    if manifest["source_before"] != manifest["source_after"] or manifest["tensor_before"] != manifest["tensor_after"]:
        raise ValueError("Worker source/tensor drift")
    frozen_input = strict_json(private / "input-manifest.json")
    source = _source_for({"exp069_manifest": {"m3_sources": frozen_input["fold_sources"]}}, spec)
    if manifest["source_before"] != {name: source[key] for name, key in (("adapter", "adapter"), ("head", "head"), ("heldout", "heldout_logits"))}:
        raise ValueError("Worker source checkpoint binding drift")
    if set(manifest["tensor_before"]) != {"adapter", "head", "base_sentinel"}:
        raise ValueError("Worker tensor fingerprint inventory drift")
    for value in [manifest[name] for name in ("row_order_sha256", "fold_id_sha256", "sample_id_order_sha256", "token_stream_sha256")] + list(manifest["tensor_before"].values()):
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("Worker digest format drift")
    replay = manifest["replay"]
    if public_value["replay"] != replay or replay["atol"] != 1e-5 or replay["rtol"] != 0.0:
        raise ValueError("Worker replay contract drift")
    if spec["condition"] == "A0":
        if replay["required"] is not True or replay["checked_rows"] != 672 or type(replay["max_abs_error"]) not in (int, float) or not math.isfinite(replay["max_abs_error"]) or not 0 <= replay["max_abs_error"] <= 1e-5:
            raise ValueError("A0 replay prerequisite failed")
    elif replay != {"required": False, "checked_rows": 0, "max_abs_error": None, "atol": 1e-5, "rtol": 0.0}:
        raise ValueError("Unexpected ablation replay")
    if spec["condition"] != "A0":
        a0 = strict_json(private / "workers" / f"s{spec['seed']}-f{spec['fold']}-A0.json")
        for name in ("row_order_sha256", "fold_id_sha256", "sample_id_order_sha256", "token_stream_sha256", "tensor_before", "source_before"):
            if manifest[name] != a0[name]:
                raise ValueError("Full/ablation matching contract drift")
    if set(manifest["resources"]) != {"wall_seconds", "peak_mlx_bytes", "peak_rss_bytes"}:
        raise ValueError("Worker resource schema drift")
    for name in ("wall_seconds", "peak_mlx_bytes", "peak_rss_bytes"):
        value = manifest["resources"][name]
        maximum = DEFAULT_RESOURCES[{"wall_seconds": "max_worker_wall_seconds", "peak_mlx_bytes": "max_mlx_bytes", "peak_rss_bytes": "max_rss_bytes"}[name]]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
            raise ValueError("Worker resource budget drift")
    expected_public = {"schema_version": "exp-072-worker-public-v1", **_common(), **spec,
                       "status": "Completed", "rows": 672, "output_sha256": manifest["output"]["sha256"],
                       "manifest_sha256": artifact(manifest_path)["sha256"], "replay": replay,
                       "disabled_modules": manifest["disabled_modules"], "scale_map_sha256": manifest["scale_map_sha256"],
                       "resources": manifest["resources"], "access": dict(INFERENCE_ACCESS)}
    if public_value != expected_public:
        raise ValueError("Worker public exact schema/payload drift")
    return {"public": artifact(public_path), "manifest": artifact(manifest_path), "logits": artifact(output_path)}


def build_prediction_manifest(config_path: Path, config: Mapping[str, Any], workers: Mapping[str, Any]) -> dict[str, Any]:
    _, private = roots(config)
    order = [value["worker_id"] for value in expected_workers()]
    if set(workers) != set(order):
        raise ValueError("Prediction seal requires all 70 workers")
    input_manifest = strict_json(private / "input-manifest.json")
    return {"schema_version": "exp-072-prediction-manifest-v1", **_common(), "status": "Sealed",
            "config": artifact(config_path), "input_manifest": artifact(private / "input-manifest.json"),
            "workers": dict(workers), "worker_order": order, "worker_count": 70, "a0_worker_count": 15,
            "total_forward_rows": 47040, "source_snapshot_sha256": input_manifest["source_snapshot_sha256"],
            "access": dict(INFERENCE_ACCESS)}


def build_prediction_seal(config_path: Path, manifest_record: Mapping[str, Any], workers: Mapping[str, Any]) -> dict[str, Any]:
    if set(workers) != {value["worker_id"] for value in expected_workers()}:
        raise ValueError("Incomplete prediction inventory")
    return {"schema_version": "exp-072-prediction-seal-v1", **_common(), "status": "Sealed",
            "config": artifact(config_path), "prediction_manifest": dict(manifest_record),
            "worker_count": 70, "a0_worker_count": 15, "total_forward_rows": 47040,
            "worker_inventory_sha256": digest(workers), "all_a0_passed": True,
            "all_predictions_sealed": True, "labels_accessed": False, "metrics_computed": False}


def _git_identity() -> dict[str, Any]:
    def command(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {"commit": command("rev-parse", "HEAD"), "dirty": bool(command("status", "--porcelain"))}


def _append_log(path: Path, value: Mapping[str, Any]) -> None:
    if path.is_symlink() or path.stat().st_nlink != 1 or stat.S_IMODE(path.stat().st_mode) != 0o644:
        raise ValueError("Unsafe append-only status log")
    with path.open("ab") as handle:
        handle.write(canonical_json_bytes(value))
        handle.flush()
        os.fsync(handle.fileno())


def run(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    if set(config["implementation"]) != IMPLEMENTATION_KEYS:
        raise ValueError("All runner/scorer/verifier/tests must be frozen before inference")
    started = time.monotonic()
    began = datetime.now(timezone.utc).isoformat()
    public, private = roots(config)
    with file_lock(SCHEDULER_LOCK), file_lock(HEAVY_LOCK) as heavy_fd:
        if public.exists() or private.exists():
            raise FileExistsError("EXP-072 cannot resume or overwrite any attempt")
        context = metadata_gate(config_path, config)
        if shutil.disk_usage(PROJECT_ROOT).free < DEFAULT_RESOURCES["min_free_disk_bytes"]:
            raise OSError("Minimum free disk gate failed")
        _mkdir_root(public, private=False)
        _mkdir_root(private, private=True)
        create_bytes_once(public / "stdout.log", b"", private=False)
        input_manifest = {"schema_version": "exp-072-input-manifest-v1", **_common(),
                          "status": "Frozen", "config": artifact(config_path),
                          "source_snapshot": context["source_snapshot"],
                          "source_snapshot_sha256": context["source_snapshot_sha256"],
                          "fold_sources": [{key: source[key] for key in ("seed", "fold", "adapter", "head", "heldout_logits")}
                                           for source in context["exp069_manifest"]["m3_sources"]],
                          "method_sha256": digest(config["method"]), "worker_plan": expected_workers(),
                          "access": dict(METADATA_ACCESS)}
        input_record = create_json_once(private / "input-manifest.json", input_manifest, private=True)
        claim = {"schema_version": "exp-072-run-claim-v1", **_common(), "status": "Running",
                 "tier": "Major", "rq_id": "RQ-S4.3", "stage": "run", "started_at": began,
                 "command": [sys.executable, str(Path(__file__).resolve()), "--stage", "run", "--config", str(config_path)],
                 "cwd": str(PROJECT_ROOT), "git": _git_identity(), "scheduler_pid": os.getpid(),
                 "config": artifact(config_path), "input_manifest": input_record,
                 "environment": config["environment"], "resources": DEFAULT_RESOURCES,
                 "access": dict(METADATA_ACCESS)}
        create_json_once(public / "run-claim.json", claim)
        completed: dict[str, Any] = {}
        current_worker = None
        try:
            for spec in expected_workers():
                current_worker = spec["worker_id"]
                check_budget(started, private)
                _append_log(public / "stdout.log", {"event": "worker_started", "worker_id": current_worker})
                env = dict(os.environ)
                env.update(config["environment"]["offline_environment"])
                env["EXP072_HEAVY_LOCK_FD"] = str(heavy_fd)
                # Child library messages may contain input fragments; never expose/capture them.
                command = [config["environment"]["python_executable"], str(Path(__file__).resolve()),
                           "--stage", "worker", "--config", str(config_path), "--worker-id", current_worker]
                remaining = DEFAULT_RESOURCES["max_total_wall_seconds"] - (time.monotonic() - started)
                result = subprocess.run(command, cwd=PROJECT_ROOT, env=env, pass_fds=(heavy_fd,),
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=min(DEFAULT_RESOURCES["max_worker_wall_seconds"], remaining), check=False)
                if result.returncode != 0:
                    raise RuntimeError("Fresh inference worker exited nonzero")
                completed[current_worker] = validate_worker(config, config_path, spec)
                _append_log(public / "stdout.log", {"event": "worker_completed", "worker_id": current_worker,
                                                   "completed_workers": len(completed)})
            for record in context["source_snapshot"].values():
                require_record(record)
            resources = check_budget(started, private)
            for records in completed.values():
                worker_resources = strict_json(require_record(records["manifest"]))["resources"]
                for name in ("peak_mlx_bytes", "peak_rss_bytes"):
                    resources[name] = max(resources[name], worker_resources[name])
            manifest = build_prediction_manifest(config_path, config, completed)
            manifest_record = create_json_once(private / "prediction-manifest.json", manifest, private=True)
            seal = build_prediction_seal(config_path, manifest_record, completed)
            seal_record = create_json_once(public / "prediction-seal.json", seal)
            result = {"schema_version": "exp-072-inference-run-v1", **_common(), "tier": "Major", "rq_id": "RQ-S4.3",
                      "stage": "run", "status": "CompletedAwaitingScore", "started_at": began,
                      "finished_at": datetime.now(timezone.utc).isoformat(), "command": claim["command"],
                      "cwd": claim["cwd"], "git": claim["git"], "config": artifact(config_path),
                      "run_claim": artifact(public / "run-claim.json"), "prediction_seal": seal_record,
                      "worker_count": 70, "a0_worker_count": 15, "total_forward_rows": 47040,
                      "dataset": "DATA-SO-TASK-V1", "split": "train_oof", "rows": 3360,
                      "labels": DEFAULT_METHOD["labels"], "method": DEFAULT_METHOD,
                      "source_snapshot_sha256": context["source_snapshot_sha256"], "environment": config["environment"],
                      "resources": resources, "access": dict(INFERENCE_ACCESS), "metrics": None,
                      "warnings": [], "exception": None, "exp072_complete": False}
            create_json_once(public / "run.json", result)
            _append_log(public / "stdout.log", {"event": "predictions_sealed", "worker_count": 70})
            return result
        except BaseException as exc:
            failure = {"schema_version": "exp-072-inference-failure-v1", **_common(), "status": "Failed",
                       "stage": "run", "worker_id": current_worker, "completed_workers": len(completed),
                       "config": artifact(config_path), "exception_type": type(exc).__name__,
                       "error_sha256": hashlib.sha256(str(exc).encode()).hexdigest(),
                       "finished_at": datetime.now(timezone.utc).isoformat(), "automatic_retry": False,
                       "automatic_resume": False, "exp072_complete": False}
            create_json_once(public / "failure.json", failure)
            _append_log(public / "stdout.log", {"event": "failed", "worker_id": current_worker,
                                               "exception_type": type(exc).__name__})
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("run", "worker"), required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--worker-id")
    args = parser.parse_args()
    try:
        config_path = args.config.absolute()
        config = load_config(config_path)
        if args.stage == "worker":
            if args.worker_id is None:
                raise ValueError("Worker id required")
            result = worker(config_path, config, args.worker_id)
        else:
            if args.worker_id is not None:
                raise ValueError("Worker id only allowed for worker")
            result = run(config_path, config)
        print(json.dumps({"experiment_id": EXPERIMENT_ID, "stage": args.stage, "status": result["status"]}, sort_keys=True))
        return 0
    except BaseException as exc:
        failure = {"experiment_id": EXPERIMENT_ID, "stage": args.stage, "status": "Failed",
                   "exception_type": type(exc).__name__,
                   "error_sha256": hashlib.sha256(str(exc).encode()).hexdigest()}
        if args.stage == "worker" and "config" in locals() and args.worker_id in {v["worker_id"] for v in expected_workers()}:
            public, private = roots(config)
            claim_path = public / "run-claim.json"
            if claim_path.is_file():
                # Do not let a standalone, ungated worker mutate an existing run.
                try:
                    _inherited_lock(strict_json(claim_path))
                    create_json_once(private / "workers" / f"{args.worker_id}.failure.json",
                                     {**failure, "message": str(exc), "traceback": traceback.format_exc()}, private=True)
                    create_json_once(public / "workers" / f"{args.worker_id}.failure.json", failure)
                except (OSError, ValueError, PermissionError):
                    pass
        print(json.dumps(failure, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

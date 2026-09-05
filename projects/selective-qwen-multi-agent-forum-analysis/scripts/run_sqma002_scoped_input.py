#!/usr/bin/env python3
"""Materialize the sealed folds 0-2 SQMA-002 scoped-input snapshots.

The data steward decodes private source rows only when the public fold row is
in folds 0-2.  Private rows for folds 3-4 are byte-streamed for source identity
and line-count checks but are never decoded.  No model framework is imported.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
from itertools import zip_longest
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import stat
import sys
import time
from typing import Any, BinaryIO, Mapping, TextIO
import zipfile


sys.dont_write_bytecode = True


CONFIG_RELATIVE_PATH = (
    "projects/selective-qwen-multi-agent-forum-analysis/configs/"
    "sqma-002-dev-scoped-input-materialization.json"
)
EXPECTED_PUBLIC_OUTPUT = (
    "projects/selective-qwen-multi-agent-forum-analysis/runs/"
    "sqma-002-dev-scoped-input/attempt-1"
)
EXPECTED_PRIVATE_OUTPUT = (
    "projects/selective-qwen-multi-agent-forum-analysis/private/"
    "sqma-002-dev-scoped-input/attempt-1"
)
EXPECTED_IMPLEMENTATION_PATHS = {
    "protocol": (
        "projects/selective-qwen-multi-agent-forum-analysis/protocols/"
        "sqma-002-dev-scoped-input-materialization.md"
    ),
    "contract": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "scoped_input_contract.py"
    ),
    "runner": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "run_sqma002_scoped_input.py"
    ),
    "verifier": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "verify_sqma002_scoped_input.py"
    ),
    "contract_tests": (
        "projects/selective-qwen-multi-agent-forum-analysis/tests/"
        "test_scoped_input_contract.py"
    ),
    "integration_tests": (
        "projects/selective-qwen-multi-agent-forum-analysis/tests/"
        "test_sqma002_scoped_input.py"
    ),
}
EXPECTED_PREREQUISITE_PATHS = {
    "d0_static_contract": (
        "projects/selective-qwen-multi-agent-forum-analysis/configs/"
        "d0-static-contract.json"
    ),
    "sqma001_complete": (
        "projects/selective-qwen-multi-agent-forum-analysis/runs/"
        "sqma-001-strict-base-readiness-preflight/attempt-1/complete.json"
    ),
    "public_fold_manifest": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/oof-router/runs/"
        "exp-058-fold-manifest-preflight-attempt-2/fold-manifest.public.jsonl"
    ),
}
EXPECTED_AUTHORIZATION = {
    "basis": "User instructed: 下一步",
    "materialization": True,
    "public_fold_metadata_access": True,
    "monolithic_private_byte_streaming": True,
    "decode_private_rows_for_folds": [0, 1, 2],
    "decode_private_rows_for_fold3": False,
    "decode_private_rows_for_fold4": False,
    "write_private_scoped_outputs": True,
    "model_loading": False,
    "forward": False,
    "training": False,
    "optimizer": False,
    "agent_calls": False,
    "network": False,
    "validation_access": False,
    "test_access": False,
    "formal_training": False,
    "automatic_next_stage": False,
}
EXPECTED_TOP_LEVEL_KEYS = {
    "schema_version",
    "experiment_id",
    "tier",
    "stage",
    "registered_at",
    "authorization",
    "implementation",
    "prerequisites",
    "sources",
    "runtime",
    "folds",
    "snapshot_contract",
    "fit_bindings",
    "resources",
    "outputs",
    "commands",
}
ARTIFACT_KEYS = {"path", "bytes", "sha256"}
PRIVATE_SOURCE_KEYS = {"relative_path", "bytes", "sha256", "mode", "rows"}
FORBIDDEN_FRAMEWORK_ROOTS = {"mlx", "mlx_lm", "torch", "transformers"}


class MaterializationError(RuntimeError):
    """Raised when an SQMA-002 fail-closed gate is violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MaterializationError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file(), f"missing {label}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterializationError(f"invalid {label}") from exc
    require(isinstance(value, dict), f"{label} root must be an object")
    return value


def _has_wildcard(value: str) -> bool:
    return any(character in value for character in "*?[]{}")


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"invalid {label} path")
    require(not Path(relative).is_absolute(), f"absolute {label} path is forbidden")
    require(not _has_wildcard(relative), f"wildcard {label} path is forbidden")
    candidate = Path(relative)
    lexical = root / candidate
    resolved_root = root.resolve()
    resolved = lexical.resolve()
    require(resolved == resolved_root or resolved_root in resolved.parents, f"{label} path escapes root")
    current = root
    for part in candidate.parts:
        current = current / part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains a symlink")
    return lexical


def require_regular_source(path: Path, label: str, *, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), f"invalid {label}")
    require(observed.st_nlink == 1, f"{label} must not be hard-linked")
    require(observed.st_uid == os.getuid(), f"{label} owner drift")
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def artifact(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(repo_root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_artifact_record(
    repo_root: Path, name: str, value: Any, expected_path: str
) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == ARTIFACT_KEYS, f"invalid {name} record")
    require(value["path"] == expected_path, f"{name} path drift")
    require(type(value["bytes"]) is int and value["bytes"] > 0, f"invalid {name} bytes")
    require(
        isinstance(value["sha256"], str)
        and len(value["sha256"]) == 64
        and all(character in "0123456789abcdef" for character in value["sha256"]),
        f"invalid {name} SHA-256",
    )
    require(value["sha256"] != "TO_BE_REGISTERED", f"unregistered {name}")
    path = checked_path(repo_root, value["path"], name)
    observed = require_regular_source(path, name)
    require(observed.st_size == value["bytes"], f"{name} byte drift")
    require(sha256(path) == value["sha256"], f"{name} SHA-256 drift")
    return dict(value)


def validate_file_records(
    repo_root: Path, config: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    implementation = config.get("implementation")
    prerequisites = config.get("prerequisites")
    require(
        isinstance(implementation, dict) and set(implementation) == set(EXPECTED_IMPLEMENTATION_PATHS),
        "implementation record set drift",
    )
    require(
        isinstance(prerequisites, dict) and set(prerequisites) == set(EXPECTED_PREREQUISITE_PATHS),
        "prerequisite record set drift",
    )
    checked_implementation = {
        key: validate_artifact_record(repo_root, f"implementation.{key}", implementation[key], path)
        for key, path in EXPECTED_IMPLEMENTATION_PATHS.items()
    }
    checked_prerequisites = {
        key: validate_artifact_record(repo_root, f"prerequisites.{key}", prerequisites[key], path)
        for key, path in EXPECTED_PREREQUISITE_PATHS.items()
    }
    return checked_implementation, checked_prerequisites


def load_contract(repo_root: Path, record: Mapping[str, Any]) -> Any:
    path = checked_path(repo_root, str(record["path"]), "scoped-input contract")
    module_name = "sqma002_scoped_input_contract_runtime"
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, "contract import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    require(Path(module.__file__).resolve() == path.resolve(), "contract import path drift")
    return module


def validate_config(config: Mapping[str, Any], contract: Any) -> None:
    require(set(config) == EXPECTED_TOP_LEVEL_KEYS, "config top-level schema drift")
    require(config.get("schema_version") == "sqma-002-dev-scoped-input-materialization-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-002", "experiment identity drift")
    require(config.get("tier") == "Major infrastructure", "tier drift")
    require(config.get("stage") == "dev-scoped-input-materialization", "stage drift")
    require(config.get("registered_at") == "2026-09-03", "registration date drift")
    require(config.get("authorization") == EXPECTED_AUTHORIZATION, "authorization drift")

    sources = config.get("sources")
    require(isinstance(sources, dict), "source contract missing")
    require(set(sources) == {"archive_root_env", "audited_archive_root", "train", "private_fold_manifest", "source_ordinal", "input_alignment"}, "source schema drift")
    require(sources["source_ordinal"] == "zero_based_train_jsonl_line_index", "source ordinal drift")
    require(sources["input_alignment"] == "zip_public_train_private_manifest_exact_3360_lines", "source alignment drift")
    for name in ("train", "private_fold_manifest"):
        source = sources[name]
        require(isinstance(source, dict) and set(source) == PRIVATE_SOURCE_KEYS, f"{name} source schema drift")
        require(source["mode"] == "0600" and source["rows"] == 3360, f"{name} source contract drift")
        require(not _has_wildcard(source["relative_path"]), f"{name} source wildcard forbidden")

    runtime = config.get("runtime")
    require(isinstance(runtime, dict) and runtime.get("packages") == {"numpy": "2.2.6"}, "runtime package drift")
    require(runtime.get("model_framework_imports") is False and runtime.get("offline") is True, "runtime access drift")

    folds = config.get("folds")
    require(isinstance(folds, dict), "fold contract missing")
    require(folds.get("output_folds") == list(contract.MATERIALIZED_FOLDS), "output fold drift")
    require(folds.get("fold3_output_rows") == 0 and folds.get("fold4_output_rows") == 0, "forbidden output fold drift")
    require(folds.get("total_output_rows") == 2016 and folds.get("total_output_components") == 1963, "output total drift")
    expected = folds.get("expected")
    require(isinstance(expected, dict) and set(expected) == {"0", "1", "2"}, "fold expectation drift")
    for fold in contract.MATERIALIZED_FOLDS:
        frozen = dict(contract.EXPECTED_FOLD_IDENTITY[fold])
        observed = expected[str(fold)]
        require(isinstance(observed, dict), f"fold {fold} expectation missing")
        for key in ("rows", "components", "sample_order_sha256", "sample_membership_sha256", "component_membership_sha256", "row_membership_sha256"):
            require(observed.get(key) == frozen[key], f"fold {fold} {key} drift")

    snapshots = config.get("snapshot_contract")
    require(isinstance(snapshots, dict), "snapshot contract missing")
    require(snapshots.get("scopes") == ["train-capable", "gold-free-inference", "consumer-gold"], "snapshot scope drift")
    require(snapshots.get("rows_per_scope_per_fold") == 672, "snapshot row drift")
    require(snapshots.get("private_directory_mode") == "0700" and snapshots.get("private_file_mode") == "0600", "snapshot mode drift")
    require(snapshots.get("source_order_preserved") is True and snapshots.get("extra_files_allowed") == 0, "snapshot invariant drift")

    bindings = config.get("fit_bindings")
    require(isinstance(bindings, dict), "fit binding contract missing")
    require(bindings.get("consumer_gold_in_producer_allowlist") is False, "consumer gold producer access drift")
    require(bindings.get("monolithic_source_in_producer_allowlist") is False, "monolithic producer access drift")
    for fit_id, expected_grants in contract.PRODUCER_ALLOWLIST.items():
        binding = bindings.get(fit_id)
        require(isinstance(binding, dict), f"missing fit binding: {fit_id}")
        requests = [("train-capable", fold) for fold in binding.get("training_folds", [])]
        requests.append(("gold-free-inference", binding.get("heldout_inference_fold")))
        try:
            contract.validate_producer_request(fit_id, requests)
        except contract.ContractError as exc:
            raise MaterializationError(f"fit binding drift: {fit_id}") from exc

    resources = config.get("resources")
    require(
        resources
        == {
            "maximum_wall_seconds": 300,
            "maximum_peak_rss_bytes": 1073741824,
            "maximum_private_output_bytes": 134217728,
            "maximum_public_output_bytes": 16777216,
            "minimum_free_disk_bytes": 21474836480,
            "model_or_mlx_allocations": 0,
            "critical_memory_events": 0,
            "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "resource contract drift",
    )
    outputs = config.get("outputs")
    require(isinstance(outputs, dict), "output contract missing")
    require(outputs.get("public_attempt_dir") == EXPECTED_PUBLIC_OUTPUT, "public output path drift")
    require(outputs.get("private_attempt_dir") == EXPECTED_PRIVATE_OUTPUT, "private output path drift")
    require(outputs.get("public_allowed_files") == ["run-claim.json", "run.json", "verification.json", "complete.json"], "public output allowlist drift")
    require(outputs.get("private_allowed_files") == [
        "fold-0/train-capable.jsonl", "fold-0/gold-free-inference.jsonl", "fold-0/consumer-gold.npz",
        "fold-1/train-capable.jsonl", "fold-1/gold-free-inference.jsonl", "fold-1/consumer-gold.npz",
        "fold-2/train-capable.jsonl", "fold-2/gold-free-inference.jsonl", "fold-2/consumer-gold.npz",
        "private-manifest.json",
    ], "private output allowlist drift")


def validate_prerequisites(repo_root: Path, config: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]) -> None:
    d0 = read_json(checked_path(repo_root, records["d0_static_contract"]["path"], "D0 static contract"), "D0 static contract")
    require(d0.get("status") == "static_contract_registered_no_execution_authority", "D0 status drift")
    require(all(value is False for value in d0.get("authorization", {}).values()), "D0 execution authority drift")
    complete = read_json(checked_path(repo_root, records["sqma001_complete"]["path"], "SQMA-001 completion"), "SQMA-001 completion")
    require(complete.get("sqma001_complete") is True and complete.get("status") == "Complete", "SQMA-001 completion drift")
    require(complete.get("training_executed") is False and complete.get("formal_training_authorized") is False, "SQMA-001 authority drift")


def peak_rss_bytes() -> int:
    observed = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return observed * 1024 if sys.platform.startswith("linux") else observed


def validate_output_targets(repo_root: Path, public_target: Path, private_target: Path, minimum_free: int) -> int:
    staging = private_target.with_name(private_target.name + ".staging")
    for path, label in ((public_target, "public target"), (private_target, "private target"), (staging, "private staging target")):
        require(not os.path.lexists(path), f"{label} already exists")
        current = path.parent
        while not os.path.lexists(current):
            current = current.parent
        resolved_root = repo_root.resolve()
        while True:
            observed = os.lstat(current)
            require(not stat.S_ISLNK(observed.st_mode), f"{label} ancestor is a symlink")
            if current.resolve() == resolved_root:
                break
            require(resolved_root in current.resolve().parents, f"{label} escapes repository")
            current = current.parent
    free_bytes = min(shutil.disk_usage(public_target.parent if public_target.parent.exists() else repo_root).free, shutil.disk_usage(private_target.parent if private_target.parent.exists() else repo_root).free)
    require(free_bytes >= minimum_free, "free disk below SQMA-002 minimum")
    return free_bytes


def ensure_directory(path: Path, mode: int) -> None:
    path.mkdir(parents=True, exist_ok=False)
    path.chmod(mode)


def write_json_exclusive(path: Path, value: Mapping[str, Any], mode: int) -> int:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as destination:
        destination.write(payload)
        destination.flush()
        os.fsync(destination.fileno())
    path.chmod(mode)
    return len(payload)


def write_json_atomic(path: Path, value: Mapping[str, Any], mode: int) -> int:
    temporary = path.with_name(path.name + ".tmp")
    require(not os.path.lexists(path) and not os.path.lexists(temporary), f"output already exists: {path.name}")
    size = write_json_exclusive(temporary, value, mode)
    os.replace(temporary, path)
    path.chmod(mode)
    return size


def source_record(path: Path, expected: Mapping[str, Any], label: str) -> dict[str, Any]:
    observed = require_regular_source(path, label, mode=str(expected["mode"]))
    require(observed.st_size == expected["bytes"], f"{label} byte drift")
    digest = sha256(path)
    require(digest == expected["sha256"], f"{label} SHA-256 drift")
    return {"bytes": observed.st_size, "sha256": digest, "mode": expected["mode"], "rows": expected["rows"]}


def private_file_record(path: Path, staging: Path, *, schema_id: str, rows: int, components: int) -> dict[str, Any]:
    observed = require_regular_source(path, path.name, mode="0600")
    return {
        "logical_name": path.relative_to(staging).as_posix(),
        "schema_id": schema_id,
        "bytes": observed.st_size,
        "sha256": sha256(path),
        "mode": "0600",
        "rows": rows,
        "components": components,
    }


def public_artifact_record(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "logical_name": value["logical_name"],
        "schema_id": value["schema_id"],
        "bytes": value["bytes"],
        "sha256": value["sha256"],
        "mode": value["mode"],
        "rows": value["rows"],
        "components": value["components"],
    }


def open_private_text(path: Path, stack: ExitStack) -> TextIO:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    binary = stack.enter_context(os.fdopen(descriptor, "wb"))
    return stack.enter_context(__import__("io").TextIOWrapper(binary, encoding="utf-8", newline="\n", write_through=False))


def flush_text(handle: TextIO) -> None:
    handle.flush()
    buffer = getattr(handle, "buffer", None)
    if buffer is not None:
        buffer.flush()
        os.fsync(buffer.fileno())


def write_npz(path: Path, numpy: Any, values: Mapping[str, list[Any]], contract: Any, fold: int) -> dict[str, Any]:
    sample_width = max(1, max(len(value) for value in values["sample_ids"]))
    component_width = max(1, max(len(value) for value in values["component_ids"]))
    arrays = {
        "sample_ids": numpy.asarray(values["sample_ids"], dtype=f"<U{sample_width}"),
        "component_ids": numpy.asarray(values["component_ids"], dtype=f"<U{component_width}"),
        "fold_ids": numpy.asarray(values["fold_ids"], dtype=numpy.int8),
        "source_ordinals": numpy.asarray(values["source_ordinals"], dtype=numpy.int32),
        "gold": numpy.asarray(values["gold"], dtype=numpy.uint8),
    }
    metadata = {
        name: {
            "dtype": "unicode" if array.dtype.kind == "U" else str(array.dtype),
            "shape": list(array.shape),
        }
        for name, array in arrays.items()
    }
    try:
        contract.validate_consumer_gold_arrays(metadata, fold)
    except contract.ContractError as exc:
        raise MaterializationError(f"consumer-gold array contract failed for fold {fold}") from exc
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as destination:
        numpy.savez(destination, **arrays)
        destination.flush()
        os.fsync(destination.fileno())
    path.chmod(0o600)
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "consumer-gold NPZ has duplicate members")
        require(set(names) == {f"{name}.npy" for name in arrays}, "consumer-gold NPZ member drift")
    with numpy.load(path, allow_pickle=False) as observed:
        require(set(observed.files) == set(arrays), "consumer-gold NPZ array inventory drift")
        for name, expected in arrays.items():
            actual = observed[name]
            require(actual.dtype == expected.dtype and actual.shape == expected.shape, f"consumer-gold {name} metadata drift")
            require(bool(numpy.array_equal(actual, expected)), f"consumer-gold {name} value drift")
    return {"arrays": {name: {"dtype": str(array.dtype), "shape": list(array.shape)} for name, array in arrays.items()}}


def stream_materialize(
    *,
    public_path: Path,
    train_path: Path,
    private_fold_path: Path,
    staging: Path,
    contract: Any,
    numpy: Any,
    expected_rows: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    before = {
        "public_fold_manifest": sha256(public_path),
        "private_train": sha256(train_path),
        "private_fold_manifest": sha256(private_fold_path),
    }
    stream_hashers = {key: hashlib.sha256() for key in before}
    output_rows: dict[int, dict[str, list[dict[str, Any]]]] = {
        fold: {"train-capable": [], "gold-free-inference": []}
        for fold in contract.MATERIALIZED_FOLDS
    }
    gold_values: dict[int, dict[str, list[Any]]] = {
        fold: {"sample_ids": [], "component_ids": [], "fold_ids": [], "source_ordinals": [], "gold": []}
        for fold in contract.MATERIALIZED_FOLDS
    }
    public_rows: dict[int, list[dict[str, Any]]] = {fold: [] for fold in range(5)}
    public_samples: set[str] = set()
    component_folds: dict[str, int] = {}
    decoded_by_fold = {fold: 0 for fold in range(5)}
    streamed_by_fold = {fold: 0 for fold in range(5)}

    for fold in contract.MATERIALIZED_FOLDS:
        ensure_directory(staging / f"fold-{fold}", 0o700)

    with ExitStack() as stack:
        text_outputs: dict[tuple[int, str], TextIO] = {}
        for fold in contract.MATERIALIZED_FOLDS:
            for scope in ("train-capable", "gold-free-inference"):
                text_outputs[(fold, scope)] = open_private_text(staging / f"fold-{fold}" / f"{scope}.jsonl", stack)
        public_source: BinaryIO = stack.enter_context(public_path.open("rb"))
        train_source: BinaryIO = stack.enter_context(train_path.open("rb"))
        private_source: BinaryIO = stack.enter_context(private_fold_path.open("rb"))
        sentinel = object()
        row_count = 0
        for ordinal, triplet in enumerate(zip_longest(public_source, train_source, private_source, fillvalue=sentinel)):
            public_bytes, train_bytes, private_bytes = triplet
            require(sentinel not in triplet, "source line-count mismatch")
            require(isinstance(public_bytes, bytes) and isinstance(train_bytes, bytes) and isinstance(private_bytes, bytes), "source stream type drift")
            require(public_bytes.strip() and train_bytes.strip() and private_bytes.strip(), "empty source line")
            stream_hashers["public_fold_manifest"].update(public_bytes)
            stream_hashers["private_train"].update(train_bytes)
            stream_hashers["private_fold_manifest"].update(private_bytes)
            try:
                public_line = public_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MaterializationError("public fold manifest UTF-8 failure") from exc
            try:
                public = contract.parse_source_json_line("public-fold-manifest", public_line, ordinal)
            except contract.ContractError as exc:
                raise MaterializationError(f"public fold row contract failed at ordinal {ordinal}") from exc
            fold = public["fold_id"]
            sample_id = public["sample_id"]
            component_id = public["component_id"]
            require(sample_id not in public_samples, "duplicate public sample")
            prior_fold = component_folds.setdefault(component_id, fold)
            require(prior_fold == fold, "public component crosses folds")
            public_samples.add(sample_id)
            public_rows[fold].append({
                "sample_id": sample_id,
                "component_id": component_id,
                "fold_id": fold,
                "source_ordinal": ordinal,
            })
            streamed_by_fold[fold] += 1
            if fold in contract.MATERIALIZED_FOLDS:
                try:
                    train_line = train_bytes.decode("utf-8")
                    private_line = private_bytes.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise MaterializationError(f"selected private UTF-8 failure at ordinal {ordinal}") from exc
                try:
                    train = contract.parse_source_json_line("private-train", train_line, ordinal)
                    private = contract.parse_source_json_line("private-fold-manifest", private_line, ordinal)
                    materialized = contract.materialize_selected_row(public, train, private, ordinal)
                    contract.validate_output_json_row("train-capable", materialized["train-capable"], fold)
                    contract.validate_output_json_row("gold-free-inference", materialized["gold-free-inference"], fold)
                except contract.ContractError as exc:
                    raise MaterializationError(f"selected private row contract failed at ordinal {ordinal}") from exc
                for scope in ("train-capable", "gold-free-inference"):
                    row = materialized[scope]
                    text_outputs[(fold, scope)].write(contract.canonical_json_line(row))
                    output_rows[fold][scope].append(row)
                gold = materialized["consumer-gold"]
                for name in ("sample_id", "component_id", "fold_id", "source_ordinal", "gold"):
                    plural = {"sample_id": "sample_ids", "component_id": "component_ids", "fold_id": "fold_ids", "source_ordinal": "source_ordinals", "gold": "gold"}[name]
                    gold_values[fold][plural].append(gold[name])
                decoded_by_fold[fold] += 1
            else:
                # Intentionally do not call decode() or json.loads() on private bytes.
                require(fold in (3, 4), "unexpected non-materialized fold")
            row_count += 1
        require(row_count == expected_rows, "source row count drift")
        for handle in text_outputs.values():
            flush_text(handle)

    stream_digests = {key: digest.hexdigest() for key, digest in stream_hashers.items()}
    require(stream_digests == before, "source stream hash drift")
    after = {
        "public_fold_manifest": sha256(public_path),
        "private_train": sha256(train_path),
        "private_fold_manifest": sha256(private_fold_path),
    }
    require(after == before, "source hash changed during materialization")

    private_folds: dict[str, Any] = {}
    public_folds: dict[str, Any] = {}
    all_artifacts: list[dict[str, Any]] = []
    selected_components: set[str] = set()
    for fold in contract.MATERIALIZED_FOLDS:
        try:
            train_summary = contract.validate_output_rows("train-capable", output_rows[fold]["train-capable"], fold)
            inference_summary = contract.validate_output_rows("gold-free-inference", output_rows[fold]["gold-free-inference"], fold)
        except contract.ContractError as exc:
            raise MaterializationError(f"output membership failed for fold {fold}") from exc
        require(train_summary == inference_summary, f"fold {fold} scope membership mismatch")
        public_summary = contract.membership_summary(public_rows[fold])
        require(train_summary == public_summary, f"fold {fold} public/private membership mismatch")
        components = {row["component_id"] for row in output_rows[fold]["train-capable"]}
        require(not selected_components & components, "component crosses materialized folds")
        selected_components.update(components)

        npz_path = staging / f"fold-{fold}" / "consumer-gold.npz"
        npz_metadata = write_npz(npz_path, numpy, gold_values[fold], contract, fold)
        fold_artifacts = []
        for scope, filename in (
            ("train-capable", "train-capable.jsonl"),
            ("gold-free-inference", "gold-free-inference.jsonl"),
            ("consumer-gold", "consumer-gold.npz"),
        ):
            record = private_file_record(
                staging / f"fold-{fold}" / filename,
                staging,
                schema_id=contract.OUTPUT_SCHEMAS[scope].schema_id,
                rows=train_summary["rows"],
                components=train_summary["components"],
            )
            fold_artifacts.append(record)
            all_artifacts.append(record)
        private_folds[str(fold)] = {
            "membership": train_summary,
            "artifacts": fold_artifacts,
            "consumer_gold": npz_metadata,
            "text_value_sha256": contract.canonical_digest([row["text"] for row in output_rows[fold]["train-capable"]]),
            "gold_value_sha256": contract.canonical_digest(gold_values[fold]["gold"]),
        }
        public_folds[str(fold)] = {
            "rows": train_summary["rows"],
            "components": train_summary["components"],
            "artifacts": [public_artifact_record(record) for record in fold_artifacts],
        }

    require(len(selected_components) == 1963, "total materialized component count drift")
    require(decoded_by_fold == {0: 672, 1: 672, 2: 672, 3: 0, 4: 0}, "private decode count drift")
    require(streamed_by_fold == {0: 672, 1: 672, 2: 672, 3: 672, 4: 672}, "private stream count drift")
    access = {
        "monolithic_private_bytes_streamed": True,
        "private_rows_decoded": 2016,
        "fold0_rows_decoded": 672,
        "fold1_rows_decoded": 672,
        "fold2_rows_decoded": 672,
        "fold3_rows_decoded": 0,
        "fold4_rows_decoded": 0,
        "fold3_rows_byte_streamed": 672,
        "fold4_rows_byte_streamed": 672,
        "selected_train_text_read": True,
        "selected_train_gold_read": True,
        "model_loaded": False,
        "forward_executed": False,
        "training_executed": False,
        "optimizer_executed": False,
        "agent_calls": 0,
        "network_accessed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    private_manifest = {
        "schema_version": "sqma-002-private-manifest-v1",
        "experiment_id": "SQMA-002",
        "status": "SealedAwaitingVerification",
        "source_identity": {
            key: {"sha256_before": before[key], "sha256_stream": stream_digests[key], "sha256_after": after[key]}
            for key in before
        },
        "folds": private_folds,
        "artifacts": all_artifacts,
        "fit_bindings": {
            fit_id: [
                {"scope": grant.scope, "fold_id": grant.fold_id}
                for grant in sorted(grants)
            ]
            for fit_id, grants in contract.PRODUCER_ALLOWLIST.items()
        },
        "access": access,
        "formal_training_authorized": False,
        "next_gate": "independent_scoped_input_verification",
    }
    return private_manifest, {"folds": public_folds, "artifacts": [public_artifact_record(record) for record in all_artifacts]}, access


def inventory_files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def verify_private_inventory(root: Path, expected_files: list[str]) -> int:
    actual = inventory_files(root)
    require(actual == sorted(expected_files), "private output inventory drift")
    total = 0
    for path in root.rglob("*"):
        observed = os.lstat(path)
        require(not stat.S_ISLNK(observed.st_mode), "private output contains a symlink")
        require(observed.st_uid == os.getuid(), "private output owner drift")
        if path.is_dir():
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0700", "private directory mode drift")
        elif path.is_file():
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0600", "private file mode drift")
            require(observed.st_nlink == 1, "private output contains a hard link")
            total += observed.st_size
        else:
            raise MaterializationError("private output contains a non-file entry")
    return total


def stable_public_size(payload: dict[str, Any], claim_bytes: int) -> bytes:
    previous = -1
    for _ in range(10):
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        total = claim_bytes + len(encoded)
        if total == previous:
            return encoded
        payload["resources"]["public_output_bytes_before_verification"] = total
        previous = total
    raise MaterializationError("public output size did not stabilize")


def run(config_argument: str) -> dict[str, Any]:
    started = time.monotonic()
    started_at = utc_now()
    repo_root = Path(__file__).resolve().parents[3]
    project_root = Path(__file__).resolve().parents[1]
    expected_config = checked_path(repo_root, CONFIG_RELATIVE_PATH, "SQMA-002 config")
    supplied = Path(config_argument).expanduser().resolve()
    require(supplied == expected_config.resolve(), "unexpected config path")
    require_regular_source(supplied, "SQMA-002 config")
    config = read_json(supplied, "SQMA-002 config")
    implementation, prerequisites = validate_file_records(repo_root, config)
    contract = load_contract(repo_root, implementation["contract"])
    validate_config(config, contract)
    validate_prerequisites(repo_root, config, prerequisites)

    public_manifest_path = checked_path(repo_root, prerequisites["public_fold_manifest"]["path"], "public fold manifest")
    public_manifest_observed = require_regular_source(public_manifest_path, "public fold manifest")
    require(public_manifest_observed.st_size == prerequisites["public_fold_manifest"]["bytes"], "public fold manifest byte drift")
    require(sha256(public_manifest_path) == prerequisites["public_fold_manifest"]["sha256"], "public fold manifest SHA-256 drift")

    public_target = checked_path(repo_root, config["outputs"]["public_attempt_dir"], "public output")
    private_target = checked_path(repo_root, config["outputs"]["private_attempt_dir"], "private output")
    free_disk = validate_output_targets(repo_root, public_target, private_target, config["resources"]["minimum_free_disk_bytes"])
    public_target.parent.mkdir(parents=True, exist_ok=True)
    public_target.mkdir(mode=0o755, exist_ok=False)
    public_target.chmod(0o755)

    claim = {
        "schema_version": "sqma-002-run-claim-v1",
        "experiment_id": "SQMA-002",
        "stage": config["stage"],
        "status": "ClaimedBeforePrivateAccess",
        "claimed_at_utc": utc_now(),
        "config": artifact(supplied, repo_root),
        "claim_boundary": "An isolated data steward may byte-stream the two registered monolithic private sources and decode only public-fold-selected rows in folds 0-2. No model, training, Agent, validation, test, or fold 3/4 private decoding is authorized.",
        "planned_access": {
            "monolithic_private_bytes_streamed": True,
            "decode_private_rows_for_folds": [0, 1, 2],
            "fold3_rows_decoded": 0,
            "fold4_rows_decoded": 0,
            "model_loading": False,
            "training": False,
            "agent_calls": 0,
            "network": False,
            "validation_access": False,
            "test_access": False,
        },
        "source_identities": {
            "private_train": {"bytes": config["sources"]["train"]["bytes"], "sha256": config["sources"]["train"]["sha256"]},
            "private_fold_manifest": {"bytes": config["sources"]["private_fold_manifest"]["bytes"], "sha256": config["sources"]["private_fold_manifest"]["sha256"]},
            "public_fold_manifest": {"bytes": prerequisites["public_fold_manifest"]["bytes"], "sha256": prerequisites["public_fold_manifest"]["sha256"]},
        },
        "formal_training_authorized": False,
    }
    contract.assert_public_safe(claim)
    claim_path = public_target / "run-claim.json"
    claim_bytes = write_json_exclusive(claim_path, claim, 0o644)

    archive_value = os.environ.get(config["sources"]["archive_root_env"], config["sources"]["audited_archive_root"])
    require(isinstance(archive_value, str) and archive_value, "archive root is empty")
    archive_root = Path(archive_value).expanduser().resolve()
    require(archive_root.is_absolute() and archive_root.is_dir(), "archive root unavailable")
    train_path = checked_path(archive_root, config["sources"]["train"]["relative_path"], "private train")
    private_fold_path = checked_path(archive_root, config["sources"]["private_fold_manifest"]["relative_path"], "private fold manifest")
    train_identity = source_record(train_path, config["sources"]["train"], "private train")
    private_fold_identity = source_record(private_fold_path, config["sources"]["private_fold_manifest"], "private fold manifest")

    runtime = config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve(), "runtime executable drift")
    require(platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime identity drift")
    numpy = importlib.import_module("numpy")
    require(numpy.__version__ == runtime["packages"]["numpy"], "NumPy version drift")
    require(not (FORBIDDEN_FRAMEWORK_ROOTS & set(sys.modules)), "model framework imported")

    staging = private_target.with_name(private_target.name + ".staging")
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.parent.chmod(0o700)
    ensure_directory(staging, 0o700)
    private_manifest, public_outputs, access = stream_materialize(
        public_path=public_manifest_path,
        train_path=train_path,
        private_fold_path=private_fold_path,
        staging=staging,
        contract=contract,
        numpy=numpy,
        expected_rows=config["sources"]["train"]["rows"],
    )
    private_manifest["source_records"] = {
        "private_train": train_identity,
        "private_fold_manifest": private_fold_identity,
        "public_fold_manifest": {
            "bytes": public_manifest_observed.st_size,
            "sha256": prerequisites["public_fold_manifest"]["sha256"],
            "rows": 3360,
        },
    }
    private_manifest_path = staging / "private-manifest.json"
    write_json_atomic(private_manifest_path, private_manifest, 0o600)
    private_bytes = verify_private_inventory(staging, config["outputs"]["private_allowed_files"])
    require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private output budget exceeded")
    os.replace(staging, private_target)
    private_target.chmod(0o700)

    elapsed = time.monotonic() - started
    peak_rss = peak_rss_bytes()
    require(elapsed <= config["resources"]["maximum_wall_seconds"], "wall budget exceeded")
    require(peak_rss <= config["resources"]["maximum_peak_rss_bytes"], "RSS budget exceeded")
    run_payload = {
        "schema_version": "sqma-002-run-v1",
        "experiment_id": "SQMA-002",
        "tier": config["tier"],
        "stage": config["stage"],
        "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "config": artifact(supplied, repo_root),
        "run_claim": artifact(claim_path, repo_root),
        "claim_boundary": "Folds 0-2 scoped-input artifacts were materialized from the registered sources by an isolated data steward. No model was loaded, no training or Agent call occurred, folds 3-4 private rows were byte-streamed but not decoded, and formal training remains unauthorized.",
        "sources": {
            "private_train": {"bytes": train_identity["bytes"], "sha256": train_identity["sha256"], "sha256_unchanged": True},
            "private_fold_manifest": {"bytes": private_fold_identity["bytes"], "sha256": private_fold_identity["sha256"], "sha256_unchanged": True},
            "public_fold_manifest": {"bytes": public_manifest_observed.st_size, "sha256": prerequisites["public_fold_manifest"]["sha256"], "sha256_unchanged": True},
        },
        "outputs": {
            **public_outputs,
            "private_manifest": {
                "logical_name": "private-manifest.json",
                "bytes": (private_target / "private-manifest.json").stat().st_size,
                "sha256": sha256(private_target / "private-manifest.json"),
                "mode": "0600",
            },
            "fold3_output_rows": 0,
            "fold4_output_rows": 0,
            "total_output_rows_per_scope": 2016,
            "total_output_components": 1963,
        },
        "resources": {
            "wall_seconds": elapsed,
            "peak_rss_bytes": peak_rss,
            "free_disk_bytes_before": free_disk,
            "private_output_bytes": private_bytes,
            "public_output_bytes_before_verification": 0,
            "maximum_wall_seconds": config["resources"]["maximum_wall_seconds"],
            "maximum_peak_rss_bytes": config["resources"]["maximum_peak_rss_bytes"],
            "minimum_free_disk_bytes": config["resources"]["minimum_free_disk_bytes"],
            "model_or_mlx_allocations": 0,
            "critical_memory_events": 0,
            "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "access": access,
        "scoped_inputs_verified": False,
        "formal_training_authorized": False,
        "next_gate": "independent_scoped_input_verification",
    }
    contract.assert_public_safe(run_payload)
    encoded = stable_public_size(run_payload, claim_bytes)
    require(claim_bytes + len(encoded) <= config["resources"]["maximum_public_output_bytes"], "public output budget exceeded")
    run_path = public_target / "run.json"
    descriptor = os.open(run_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as destination:
        destination.write(encoded)
        destination.flush()
        os.fsync(destination.fileno())
    run_path.chmod(0o644)
    require(set(path.name for path in public_target.iterdir()) == {"run-claim.json", "run.json"}, "pre-verification public inventory drift")
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = run(args.config)
    print(json.dumps({"experiment_id": "SQMA-002", "status": result["status"], "next_gate": result["next_gate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, MaterializationError) as exc:
        print(f"SQMA-002 materialization Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

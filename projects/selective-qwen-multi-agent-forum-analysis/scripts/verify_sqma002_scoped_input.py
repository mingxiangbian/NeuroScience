#!/usr/bin/env python3
"""Independently verify the sealed SQMA-002 scoped-input artifacts.

The verifier never imports the materialization runner.  It replays the frozen
sources and decodes private rows only when the public fold is 0, 1, or 2.
Private rows in folds 3 and 4 are byte-streamed for identity and line-count
checks but are never decoded.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
from itertools import zip_longest
import json
import os
from pathlib import Path
import platform
import re
import resource
import stat
import sys
import time
from typing import Any, BinaryIO, Mapping, Sequence
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
EXPECTED_PRIVATE_FILES = [
    f"fold-{fold}/{name}"
    for fold in (0, 1, 2)
    for name in (
        "train-capable.jsonl",
        "gold-free-inference.jsonl",
        "consumer-gold.npz",
    )
] + ["private-manifest.json"]
EXPECTED_PREVERIFY_PUBLIC_FILES = ["run-claim.json", "run.json"]
ARTIFACT_KEYS = {"path", "bytes", "sha256"}
PRIVATE_SOURCE_KEYS = {"relative_path", "bytes", "sha256", "mode", "rows"}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FORBIDDEN_FRAMEWORK_ROOTS = {"mlx", "mlx_lm", "torch", "transformers"}


class VerificationError(RuntimeError):
    """Raised when an SQMA-002 independent verification gate fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        require(key not in value, "duplicate JSON key")
        value[key] = child
    return value


def decode_json(raw: str, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=strict_pairs)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise VerificationError(f"invalid {label}") from exc


def read_json(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file(), f"missing {label}")
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VerificationError(f"unreadable {label}") from exc
    value = decode_json(raw, label)
    require(isinstance(value, dict), f"{label} root must be an object")
    return value


def _has_wildcard(value: str) -> bool:
    return any(character in value for character in "*?[]{}")


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"invalid {label} path")
    candidate = Path(relative)
    require(not candidate.is_absolute(), f"absolute {label} path forbidden")
    require(".." not in candidate.parts and not _has_wildcard(relative), f"unsafe {label} path")
    lexical = root / candidate
    resolved_root = root.resolve()
    resolved = lexical.resolve()
    require(resolved == resolved_root or resolved_root in resolved.parents, f"{label} path escapes root")
    current = root
    for part in candidate.parts:
        current = current / part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains symlink")
    return lexical


def require_regular(
    path: Path,
    label: str,
    *,
    mode: str | None = None,
    owner: bool = True,
    single_link: bool = True,
) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), f"invalid {label}")
    if owner:
        require(observed.st_uid == os.getuid(), f"{label} owner drift")
    if single_link:
        require(observed.st_nlink == 1, f"{label} hard-link drift")
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def validate_artifact_record(
    repo_root: Path, name: str, value: Any, expected_path: str
) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == ARTIFACT_KEYS, f"invalid {name} record")
    require(value["path"] == expected_path, f"{name} path drift")
    require(type(value["bytes"]) is int and value["bytes"] > 0, f"{name} byte record drift")
    require(isinstance(value["sha256"], str) and SHA256_RE.fullmatch(value["sha256"]), f"{name} hash record drift")
    path = checked_path(repo_root, value["path"], name)
    observed = require_regular(path, name, single_link=False)
    require(observed.st_size == value["bytes"] and sha256(path) == value["sha256"], f"{name} identity drift")
    return dict(value)


def validate_file_records(
    repo_root: Path, config: Mapping[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    implementation = config.get("implementation")
    prerequisites = config.get("prerequisites")
    require(isinstance(implementation, dict) and set(implementation) == set(EXPECTED_IMPLEMENTATION_PATHS), "implementation record drift")
    require(isinstance(prerequisites, dict) and set(prerequisites) == set(EXPECTED_PREREQUISITE_PATHS), "prerequisite record drift")
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
    module_name = "sqma002_scoped_input_contract_verifier"
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, "contract import unavailable")
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
    require(set(config) == EXPECTED_TOP_LEVEL_KEYS, "config top-level drift")
    require(config.get("schema_version") == "sqma-002-dev-scoped-input-materialization-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-002", "experiment drift")
    require(config.get("tier") == "Major infrastructure", "tier drift")
    require(config.get("stage") == "dev-scoped-input-materialization", "stage drift")
    require(config.get("registered_at") == "2026-09-03", "registration drift")
    require(config.get("authorization") == EXPECTED_AUTHORIZATION, "authorization drift")

    sources = config.get("sources")
    require(
        isinstance(sources, dict)
        and set(sources)
        == {"archive_root_env", "audited_archive_root", "train", "private_fold_manifest", "source_ordinal", "input_alignment"},
        "source contract drift",
    )
    require(sources["archive_root_env"] == "NEUROSCIENCE_ARCHIVE_ROOT", "archive env drift")
    require(sources["audited_archive_root"] == "/Users/phoenix/Assistant/NeuroScience", "archive root record drift")
    require(sources["source_ordinal"] == "zero_based_train_jsonl_line_index", "source ordinal drift")
    require(sources["input_alignment"] == "zip_public_train_private_manifest_exact_3360_lines", "source alignment drift")
    for name in ("train", "private_fold_manifest"):
        value = sources[name]
        require(isinstance(value, dict) and set(value) == PRIVATE_SOURCE_KEYS, f"{name} source schema drift")
        require(value["mode"] == "0600" and value["rows"] == 3360, f"{name} source drift")
        require(not Path(value["relative_path"]).is_absolute() and not _has_wildcard(value["relative_path"]), f"{name} path drift")

    runtime = config.get("runtime")
    require(
        runtime
        == {
            "executable": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
            "python": "3.10.20",
            "machine": "arm64",
            "packages": {"numpy": "2.2.6"},
            "model_framework_imports": False,
            "offline": True,
        },
        "runtime drift",
    )
    folds = config.get("folds")
    require(isinstance(folds, dict) and folds.get("output_folds") == list(contract.MATERIALIZED_FOLDS), "output fold drift")
    require(folds.get("fold3_output_rows") == 0 and folds.get("fold4_output_rows") == 0, "fold3/4 output drift")
    require(folds.get("total_output_rows") == 2016 and folds.get("total_output_components") == 1963, "fold total drift")
    expected = folds.get("expected")
    require(isinstance(expected, dict) and set(expected) == {"0", "1", "2"}, "fold expectation drift")
    for fold in contract.MATERIALIZED_FOLDS:
        observed = expected[str(fold)]
        frozen = contract.EXPECTED_FOLD_IDENTITY[fold]
        for key in ("rows", "components", "sample_order_sha256", "sample_membership_sha256", "component_membership_sha256", "row_membership_sha256"):
            require(observed.get(key) == frozen[key], f"fold {fold} identity drift")

    snapshots = config.get("snapshot_contract")
    require(
        snapshots
        == {
            "scopes": ["train-capable", "gold-free-inference", "consumer-gold"],
            "rows_per_scope_per_fold": 672,
            "private_directory_mode": "0700",
            "private_file_mode": "0600",
            "source_order_preserved": True,
            "extra_files_allowed": 0,
        },
        "snapshot contract drift",
    )
    bindings = config.get("fit_bindings")
    require(isinstance(bindings, dict), "fit binding missing")
    require(bindings.get("consumer_gold_in_producer_allowlist") is False, "consumer-gold producer leak")
    require(bindings.get("monolithic_source_in_producer_allowlist") is False, "monolithic producer leak")
    for fit_id, expected_grants in contract.PRODUCER_ALLOWLIST.items():
        binding = bindings.get(fit_id)
        require(isinstance(binding, dict), f"missing fit binding {fit_id}")
        requests = [("train-capable", fold) for fold in binding.get("training_folds", [])]
        requests.append(("gold-free-inference", binding.get("heldout_inference_fold")))
        try:
            contract.validate_producer_request(fit_id, requests)
        except contract.ContractError as exc:
            raise VerificationError(f"fit binding drift: {fit_id}") from exc
    require(set(bindings) == {*contract.PRODUCER_ALLOWLIST, "consumer_gold_in_producer_allowlist", "monolithic_source_in_producer_allowlist"}, "fit binding schema drift")

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
    require(outputs.get("public_allowed_files") == ["run-claim.json", "run.json", "verification.json", "complete.json"], "public allowlist drift")
    require(outputs.get("private_allowed_files") == EXPECTED_PRIVATE_FILES, "private allowlist drift")


def validate_prerequisites(repo_root: Path, records: Mapping[str, Mapping[str, Any]]) -> None:
    d0 = read_json(checked_path(repo_root, records["d0_static_contract"]["path"], "D0 static contract"), "D0 static contract")
    require(d0.get("status") == "static_contract_registered_no_execution_authority", "D0 status drift")
    require(all(value is False for value in d0.get("authorization", {}).values()), "D0 authority drift")
    complete = read_json(checked_path(repo_root, records["sqma001_complete"]["path"], "SQMA-001 complete"), "SQMA-001 complete")
    require(complete.get("sqma001_complete") is True and complete.get("status") == "Complete", "SQMA-001 completion drift")
    require(complete.get("training_executed") is False and complete.get("formal_training_authorized") is False, "SQMA-001 authority drift")


def inventory(root: Path) -> tuple[list[str], int]:
    require(os.path.lexists(root), "private output missing")
    root_stat = os.lstat(root)
    require(stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode), "private root invalid")
    require(root_stat.st_uid == os.getuid() and f"{stat.S_IMODE(root_stat.st_mode):04o}" == "0700", "private root mode/owner drift")
    files: list[str] = []
    directories: list[str] = []
    total = 0
    for path in root.rglob("*"):
        observed = os.lstat(path)
        require(not stat.S_ISLNK(observed.st_mode), "private output symlink detected")
        require(observed.st_uid == os.getuid(), "private output owner drift")
        if stat.S_ISDIR(observed.st_mode):
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0700", "private directory mode drift")
            directories.append(path.relative_to(root).as_posix())
        elif stat.S_ISREG(observed.st_mode):
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0600", "private file mode drift")
            require(observed.st_nlink == 1, "private hard-link detected")
            files.append(path.relative_to(root).as_posix())
            total += observed.st_size
        else:
            raise VerificationError("private output contains non-file entry")
    require(sorted(files) == sorted(EXPECTED_PRIVATE_FILES), "private inventory drift")
    require(sorted(directories) == ["fold-0", "fold-1", "fold-2"], "private directory inventory drift")
    return sorted(files), total


def validate_public_preinventory(root: Path) -> None:
    require(os.path.lexists(root), "public output missing")
    observed_root = os.lstat(root)
    require(stat.S_ISDIR(observed_root.st_mode) and not stat.S_ISLNK(observed_root.st_mode), "public root invalid")
    require(
        observed_root.st_uid == os.getuid()
        and f"{stat.S_IMODE(observed_root.st_mode):04o}" == "0755",
        "public root mode/owner drift",
    )
    names: list[str] = []
    for path in root.iterdir():
        observed = os.lstat(path)
        require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), "public output contains non-file")
        require(observed.st_uid == os.getuid() and f"{stat.S_IMODE(observed.st_mode):04o}" == "0644", "public file mode/owner drift")
        names.append(path.name)
    require(sorted(names) == EXPECTED_PREVERIFY_PUBLIC_FILES, "pre-verification public inventory drift")


def public_safe(contract: Any, value: Any, private_root_string: str) -> None:
    try:
        contract.assert_public_safe(value)
    except contract.ContractError as exc:
        raise VerificationError("public sensitive-field leak") from exc
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    require(private_root_string not in serialized, "public absolute private path leak")
    require("sample-" not in serialized and "component-" not in serialized, "public row identity leak")


def artifact_record(path: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(repo_root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_jsonl(path: Path, scope: str, fold: int, contract: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as source:
        for line in source:
            require(line.endswith("\n"), f"{scope} line termination drift")
            value = decode_json(line, f"{scope} row")
            require(isinstance(value, dict), f"{scope} row must be object")
            try:
                validated = contract.validate_output_json_row(scope, value, fold)
            except contract.ContractError as exc:
                raise VerificationError(f"{scope} row contract drift") from exc
            require(line == contract.canonical_json_line(validated), f"{scope} canonical serialization drift")
            rows.append(validated)
    try:
        contract.validate_output_rows(scope, rows, fold)
    except contract.ContractError as exc:
        raise VerificationError(f"{scope} membership/order drift for fold {fold}") from exc
    return rows


def npz_arrays(path: Path, fold: int, numpy: Any, contract: Any) -> dict[str, Any]:
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "consumer-gold duplicate ZIP member")
        require(set(names) == {f"{name}.npy" for name in contract.CONSUMER_GOLD_ARRAYS}, "consumer-gold ZIP inventory drift")
        for info in archive.infolist():
            require(not info.is_dir() and not info.flag_bits & 0x1, "consumer-gold ZIP member drift")
    try:
        loaded = numpy.load(path, allow_pickle=False)
    except Exception as exc:
        raise VerificationError("consumer-gold NPZ load failed") from exc
    with loaded as observed:
        require(set(observed.files) == set(contract.CONSUMER_GOLD_ARRAYS), "consumer-gold array inventory drift")
        values = {name: observed[name] for name in observed.files}
    metadata: dict[str, dict[str, Any]] = {}
    for name, value in values.items():
        require(value.dtype.kind != "O", "consumer-gold object dtype forbidden")
        dtype = "unicode" if value.dtype.kind == "U" else str(value.dtype)
        metadata[name] = {"dtype": dtype, "shape": list(value.shape)}
    try:
        contract.validate_consumer_gold_arrays(metadata, fold)
    except contract.ContractError as exc:
        raise VerificationError(f"consumer-gold metadata drift for fold {fold}") from exc
    require(bool(numpy.all((values["gold"] == 0) | (values["gold"] == 1))), "consumer-gold nonbinary value")
    require(bool(numpy.all(values["fold_ids"] == fold)), "consumer-gold fold value drift")
    return values


def expected_artifact(
    path: Path, root: Path, schema_id: str, rows: int, components: int
) -> dict[str, Any]:
    observed = require_regular(path, "private artifact", mode="0600")
    return {
        "logical_name": path.relative_to(root).as_posix(),
        "schema_id": schema_id,
        "bytes": observed.st_size,
        "sha256": sha256(path),
        "mode": "0600",
        "rows": rows,
        "components": components,
    }


def validate_private_manifest(
    manifest: Mapping[str, Any],
    config: Mapping[str, Any],
    contract: Any,
    private_root: Path,
    artifact_records: Sequence[Mapping[str, Any]],
    fold_summaries: Mapping[str, Mapping[str, Any]],
    text_digests: Mapping[str, str],
    value_digests: Mapping[str, str],
    consumer_metadata: Mapping[str, Mapping[str, Any]],
    source_hashes: Mapping[str, str],
) -> None:
    require(
        set(manifest)
        == {"schema_version", "experiment_id", "status", "source_identity", "folds", "artifacts", "fit_bindings", "access", "formal_training_authorized", "next_gate", "source_records"},
        "private manifest schema drift",
    )
    require(manifest["schema_version"] == "sqma-002-private-manifest-v1", "private manifest identity drift")
    require(manifest["experiment_id"] == "SQMA-002" and manifest["status"] == "SealedAwaitingVerification", "private manifest status drift")
    source_identity = manifest["source_identity"]
    require(isinstance(source_identity, dict) and set(source_identity) == set(source_hashes), "private source identity inventory drift")
    for name, expected_hash in source_hashes.items():
        record = source_identity[name]
        require(
            record
            == {"sha256_before": expected_hash, "sha256_stream": expected_hash, "sha256_after": expected_hash},
            f"private source seal drift: {name}",
        )
    require(manifest["artifacts"] == list(artifact_records), "private artifact record drift")
    require(isinstance(manifest["folds"], dict) and set(manifest["folds"]) == {"0", "1", "2"}, "private fold inventory drift")
    records_by_fold = {
        str(fold): [record for record in artifact_records if record["logical_name"].startswith(f"fold-{fold}/")]
        for fold in contract.MATERIALIZED_FOLDS
    }
    for fold in contract.MATERIALIZED_FOLDS:
        item = manifest["folds"][str(fold)]
        require(
            set(item) == {"membership", "artifacts", "consumer_gold", "text_value_sha256", "gold_value_sha256"},
            f"private fold {fold} schema drift",
        )
        require(item["membership"] == fold_summaries[str(fold)], f"private fold {fold} membership drift")
        require(item["artifacts"] == records_by_fold[str(fold)], f"private fold {fold} artifact drift")
        require(item["text_value_sha256"] == text_digests[str(fold)], f"private fold {fold} text digest drift")
        require(item["gold_value_sha256"] == value_digests[str(fold)], f"private fold {fold} value digest drift")
        require(item["consumer_gold"] == consumer_metadata[str(fold)], f"private fold {fold} consumer metadata drift")

    expected_bindings = {
        fit_id: [{"scope": grant.scope, "fold_id": grant.fold_id} for grant in sorted(grants)]
        for fit_id, grants in contract.PRODUCER_ALLOWLIST.items()
    }
    require(manifest["fit_bindings"] == expected_bindings, "private fit binding drift")
    access = manifest["access"]
    require(
        access
        == {
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
        },
        "private access declaration drift",
    )
    require(manifest["formal_training_authorized"] is False, "private manifest formal authority drift")
    require(manifest["next_gate"] == "independent_scoped_input_verification", "private next gate drift")
    source_records = manifest["source_records"]
    require(isinstance(source_records, dict) and set(source_records) == set(source_hashes), "private source record drift")
    require(
        source_records["private_train"]
        == {
            "bytes": config["sources"]["train"]["bytes"],
            "sha256": source_hashes["private_train"],
            "mode": "0600",
            "rows": 3360,
        },
        "private train source record drift",
    )
    require(
        source_records["private_fold_manifest"]
        == {
            "bytes": config["sources"]["private_fold_manifest"]["bytes"],
            "sha256": source_hashes["private_fold_manifest"],
            "mode": "0600",
            "rows": 3360,
        },
        "private fold source record drift",
    )
    require(
        source_records["public_fold_manifest"]
        == {
            "bytes": config["prerequisites"]["public_fold_manifest"]["bytes"],
            "sha256": source_hashes["public_fold_manifest"],
            "rows": 3360,
        },
        "public fold source record drift",
    )


def replay_and_verify(
    *,
    public_path: Path,
    train_path: Path,
    private_fold_path: Path,
    private_root: Path,
    config: Mapping[str, Any],
    contract: Any,
    numpy: Any,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, str],
    dict[str, str],
    dict[str, dict[str, Any]],
    dict[str, str],
]:
    output_rows: dict[int, dict[str, list[dict[str, Any]]]] = {}
    output_arrays: dict[int, dict[str, Any]] = {}
    consumer_metadata: dict[str, dict[str, Any]] = {}
    artifact_records: list[dict[str, Any]] = []
    for fold in contract.MATERIALIZED_FOLDS:
        train_rows = load_jsonl(private_root / f"fold-{fold}/train-capable.jsonl", "train-capable", fold, contract)
        inference_rows = load_jsonl(private_root / f"fold-{fold}/gold-free-inference.jsonl", "gold-free-inference", fold, contract)
        require(len(train_rows) == len(inference_rows) == 672, f"fold {fold} JSONL row drift")
        output_rows[fold] = {"train-capable": train_rows, "gold-free-inference": inference_rows}
        output_arrays[fold] = npz_arrays(private_root / f"fold-{fold}/consumer-gold.npz", fold, numpy, contract)
        consumer_metadata[str(fold)] = {
            "arrays": {
                name: {"dtype": str(value.dtype), "shape": list(value.shape)}
                for name, value in output_arrays[fold].items()
            }
        }
        summary = contract.membership_summary(train_rows)
        components = summary["components"]
        for scope, name in (
            ("train-capable", "train-capable.jsonl"),
            ("gold-free-inference", "gold-free-inference.jsonl"),
            ("consumer-gold", "consumer-gold.npz"),
        ):
            artifact_records.append(
                expected_artifact(
                    private_root / f"fold-{fold}/{name}",
                    private_root,
                    contract.OUTPUT_SCHEMAS[scope].schema_id,
                    672,
                    components,
                )
            )

    source_hashes = {
        "public_fold_manifest": sha256(public_path),
        "private_train": sha256(train_path),
        "private_fold_manifest": sha256(private_fold_path),
    }
    expected_hashes = {
        "public_fold_manifest": config["prerequisites"]["public_fold_manifest"]["sha256"],
        "private_train": config["sources"]["train"]["sha256"],
        "private_fold_manifest": config["sources"]["private_fold_manifest"]["sha256"],
    }
    require(source_hashes == expected_hashes, "source identity drift before replay")
    stream_hashers = {name: hashlib.sha256() for name in source_hashes}
    indices = {fold: 0 for fold in contract.MATERIALIZED_FOLDS}
    streamed_by_fold = {fold: 0 for fold in range(5)}
    decoded_by_fold = {fold: 0 for fold in range(5)}
    public_rows: dict[int, list[dict[str, Any]]] = {fold: [] for fold in contract.MATERIALIZED_FOLDS}
    sentinel = object()
    row_count = 0
    with public_path.open("rb") as public_source, train_path.open("rb") as train_source, private_fold_path.open("rb") as private_source:
        sources: tuple[BinaryIO, BinaryIO, BinaryIO] = (public_source, train_source, private_source)
        for ordinal, triplet in enumerate(zip_longest(*sources, fillvalue=sentinel)):
            public_bytes, train_bytes, private_bytes = triplet
            require(sentinel not in triplet, "source line-count mismatch")
            require(isinstance(public_bytes, bytes) and isinstance(train_bytes, bytes) and isinstance(private_bytes, bytes), "source stream type drift")
            require(public_bytes.strip() and train_bytes.strip() and private_bytes.strip(), "empty source line")
            stream_hashers["public_fold_manifest"].update(public_bytes)
            stream_hashers["private_train"].update(train_bytes)
            stream_hashers["private_fold_manifest"].update(private_bytes)
            try:
                public_line = public_bytes.decode("utf-8")
                public = contract.parse_source_json_line("public-fold-manifest", public_line, ordinal)
            except (UnicodeDecodeError, contract.ContractError) as exc:
                raise VerificationError("public source row drift") from exc
            fold = public["fold_id"]
            streamed_by_fold[fold] += 1
            if fold in contract.MATERIALIZED_FOLDS:
                try:
                    train_line = train_bytes.decode("utf-8")
                    private_line = private_bytes.decode("utf-8")
                    train = contract.parse_source_json_line("private-train", train_line, ordinal)
                    private = contract.parse_source_json_line("private-fold-manifest", private_line, ordinal)
                    expected = contract.materialize_selected_row(public, train, private, ordinal)
                except (UnicodeDecodeError, contract.ContractError) as exc:
                    raise VerificationError("selected source row drift") from exc
                index = indices[fold]
                require(index < 672, f"fold {fold} output overflow")
                observed_train = output_rows[fold]["train-capable"][index]
                observed_inference = output_rows[fold]["gold-free-inference"][index]
                require(observed_train == expected["train-capable"], f"fold {fold} train parity drift")
                require(observed_inference == expected["gold-free-inference"], f"fold {fold} inference parity drift")
                arrays = output_arrays[fold]
                gold = expected["consumer-gold"]
                require(str(arrays["sample_ids"][index]) == gold["sample_id"], f"fold {fold} array identity drift")
                require(str(arrays["component_ids"][index]) == gold["component_id"], f"fold {fold} array component drift")
                require(int(arrays["fold_ids"][index]) == gold["fold_id"], f"fold {fold} array fold drift")
                require(int(arrays["source_ordinals"][index]) == gold["source_ordinal"], f"fold {fold} array order drift")
                require(arrays["gold"][index].tolist() == gold["gold"], f"fold {fold} array value drift")
                public_rows[fold].append({
                    "sample_id": public["sample_id"],
                    "component_id": public["component_id"],
                    "fold_id": fold,
                    "source_ordinal": ordinal,
                })
                indices[fold] += 1
                decoded_by_fold[fold] += 1
            else:
                require(fold in (3, 4), "unexpected source fold")
                # Do not decode train_bytes or private_bytes here.
            row_count += 1
    require(row_count == 3360, "source total row drift")
    require(indices == {0: 672, 1: 672, 2: 672}, "selected output row drift")
    require(decoded_by_fold == {0: 672, 1: 672, 2: 672, 3: 0, 4: 0}, "private decode boundary drift")
    require(streamed_by_fold == {0: 672, 1: 672, 2: 672, 3: 672, 4: 672}, "private stream boundary drift")
    stream_hashes = {name: digest.hexdigest() for name, digest in stream_hashers.items()}
    require(stream_hashes == source_hashes, "source stream hash drift")
    require({name: sha256(path) for name, path in {
        "public_fold_manifest": public_path,
        "private_train": train_path,
        "private_fold_manifest": private_fold_path,
    }.items()} == source_hashes, "source changed during verification")

    fold_summaries: dict[str, Any] = {}
    text_digests: dict[str, str] = {}
    value_digests: dict[str, str] = {}
    selected_components: set[str] = set()
    for fold in contract.MATERIALIZED_FOLDS:
        train_rows = output_rows[fold]["train-capable"]
        inference_rows = output_rows[fold]["gold-free-inference"]
        train_summary = contract.membership_summary(train_rows)
        inference_summary = contract.membership_summary(inference_rows)
        public_summary = contract.membership_summary(public_rows[fold])
        require(train_summary == inference_summary == public_summary, f"fold {fold} cross-scope membership drift")
        for train_row, inference_row in zip(train_rows, inference_rows, strict=True):
            require(
                (train_row["sample_id"], train_row["component_id"], train_row["fold_id"], train_row["source_ordinal"], train_row["text"])
                == (inference_row["sample_id"], inference_row["component_id"], inference_row["fold_id"], inference_row["source_ordinal"], inference_row["text"]),
                f"fold {fold} cross-scope text/order drift",
            )
        components = {row["component_id"] for row in train_rows}
        require(not selected_components & components, "component crosses materialized folds")
        selected_components.update(components)
        fold_summaries[str(fold)] = train_summary
        text_digests[str(fold)] = contract.canonical_digest([row["text"] for row in train_rows])
        value_digests[str(fold)] = contract.canonical_digest([row["labels"] for row in train_rows])
    require(len(selected_components) == 1963, "materialized component total drift")
    return (
        fold_summaries,
        artifact_records,
        text_digests,
        value_digests,
        consumer_metadata,
        source_hashes,
    )


def validate_run_public(
    claim: Mapping[str, Any],
    run: Mapping[str, Any],
    config: Mapping[str, Any],
    contract: Any,
    repo_root: Path,
    public_root: Path,
    private_root: Path,
    private_manifest_record: Mapping[str, Any],
    artifact_records: Sequence[Mapping[str, Any]],
    fold_summaries: Mapping[str, Mapping[str, Any]],
) -> None:
    public_safe(contract, claim, str(private_root.resolve()))
    public_safe(contract, run, str(private_root.resolve()))
    require(
        set(claim)
        == {
            "schema_version",
            "experiment_id",
            "stage",
            "status",
            "claimed_at_utc",
            "config",
            "claim_boundary",
            "planned_access",
            "source_identities",
            "formal_training_authorized",
        },
        "run claim schema drift",
    )
    require(claim.get("schema_version") == "sqma-002-run-claim-v1" and claim.get("status") == "ClaimedBeforePrivateAccess", "run claim drift")
    require(claim.get("experiment_id") == "SQMA-002" and claim.get("stage") == config["stage"], "run claim identity drift")
    require(claim.get("config") == artifact_record(checked_path(repo_root, CONFIG_RELATIVE_PATH, "config"), repo_root), "run claim config drift")
    require(
        claim.get("planned_access")
        == {
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
        "run claim access drift",
    )
    require(
        claim.get("source_identities")
        == {
            "private_train": {
                "bytes": config["sources"]["train"]["bytes"],
                "sha256": config["sources"]["train"]["sha256"],
            },
            "private_fold_manifest": {
                "bytes": config["sources"]["private_fold_manifest"]["bytes"],
                "sha256": config["sources"]["private_fold_manifest"]["sha256"],
            },
            "public_fold_manifest": {
                "bytes": config["prerequisites"]["public_fold_manifest"]["bytes"],
                "sha256": config["prerequisites"]["public_fold_manifest"]["sha256"],
            },
        },
        "run claim source identity drift",
    )
    require(claim.get("formal_training_authorized") is False, "run claim authority drift")
    require(
        set(run)
        == {
            "schema_version",
            "experiment_id",
            "tier",
            "stage",
            "status",
            "started_at_utc",
            "completed_at_utc",
            "config",
            "run_claim",
            "claim_boundary",
            "sources",
            "outputs",
            "resources",
            "access",
            "scoped_inputs_verified",
            "formal_training_authorized",
            "next_gate",
        },
        "run schema drift",
    )
    require(run.get("schema_version") == "sqma-002-run-v1", "run schema drift")
    require(run.get("experiment_id") == "SQMA-002" and run.get("status") == "CompletedAwaitingVerification", "run status drift")
    require(run.get("scoped_inputs_verified") is False and run.get("formal_training_authorized") is False, "run authority drift")
    require(run.get("next_gate") == "independent_scoped_input_verification", "run next gate drift")
    require(run.get("config") == artifact_record(checked_path(repo_root, CONFIG_RELATIVE_PATH, "config"), repo_root), "run config identity drift")
    require(run.get("run_claim") == artifact_record(public_root / "run-claim.json", repo_root), "run claim identity drift")
    require(
        run.get("sources")
        == {
            "private_train": {
                "bytes": config["sources"]["train"]["bytes"],
                "sha256": config["sources"]["train"]["sha256"],
                "sha256_unchanged": True,
            },
            "private_fold_manifest": {
                "bytes": config["sources"]["private_fold_manifest"]["bytes"],
                "sha256": config["sources"]["private_fold_manifest"]["sha256"],
                "sha256_unchanged": True,
            },
            "public_fold_manifest": {
                "bytes": config["prerequisites"]["public_fold_manifest"]["bytes"],
                "sha256": config["prerequisites"]["public_fold_manifest"]["sha256"],
                "sha256_unchanged": True,
            },
        },
        "run source summary drift",
    )
    outputs = run.get("outputs")
    require(isinstance(outputs, dict), "run output summary missing")
    require(outputs.get("fold3_output_rows") == 0 and outputs.get("fold4_output_rows") == 0, "run fold3/4 output drift")
    require(outputs.get("total_output_rows_per_scope") == 2016 and outputs.get("total_output_components") == 1963, "run output total drift")
    require(outputs.get("private_manifest") == private_manifest_record, "run private manifest identity drift")
    require(outputs.get("artifacts") == [dict(record) for record in artifact_records], "run artifact identity drift")
    require(isinstance(outputs.get("folds"), dict) and set(outputs["folds"]) == {"0", "1", "2"}, "run fold summary drift")
    records_by_fold = {
        str(fold): [dict(record) for record in artifact_records if record["logical_name"].startswith(f"fold-{fold}/")]
        for fold in (0, 1, 2)
    }
    for fold in (0, 1, 2):
        item = outputs["folds"][str(fold)]
        require(item == {"rows": fold_summaries[str(fold)]["rows"], "components": fold_summaries[str(fold)]["components"], "artifacts": records_by_fold[str(fold)]}, f"run fold {fold} summary drift")
    access = run.get("access")
    require(
        isinstance(access, dict)
        and access.get("private_rows_decoded") == 2016
        and access.get("fold3_rows_decoded") == 0
        and access.get("fold4_rows_decoded") == 0
        and access.get("fold3_rows_byte_streamed") == 672
        and access.get("fold4_rows_byte_streamed") == 672
        and access.get("model_loaded") is False
        and access.get("training_executed") is False
        and access.get("forward_executed") is False
        and access.get("agent_calls") == 0
        and access.get("network_accessed") is False
        and access.get("validation_accessed") is False
        and access.get("test_accessed") is False,
        "run access drift",
    )
    resources = run.get("resources")
    require(isinstance(resources, dict), "run resources missing")
    require(resources.get("wall_seconds", 301) <= config["resources"]["maximum_wall_seconds"], "runner wall cap drift")
    require(resources.get("peak_rss_bytes", 1073741825) <= config["resources"]["maximum_peak_rss_bytes"], "runner RSS cap drift")
    require(resources.get("private_output_bytes", 134217729) <= config["resources"]["maximum_private_output_bytes"], "runner private byte cap drift")
    require(resources.get("model_or_mlx_allocations") == 0 and resources.get("critical_memory_events") == 0 and resources.get("oom_or_kill_events") == 0 and resources.get("orphan_processes_after_exit") == 0, "runner resource event drift")


def peak_rss_bytes() -> int:
    observed = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return observed * 1024 if sys.platform.startswith("linux") else observed


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> int:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as destination:
        destination.write(payload)
        destination.flush()
        os.fsync(destination.fileno())
    path.chmod(0o644)
    return len(payload)


def verify(config_argument: str) -> dict[str, Any]:
    started = time.monotonic()
    started_at = utc_now()
    repo_root = Path(__file__).resolve().parents[3]
    expected_config = checked_path(repo_root, CONFIG_RELATIVE_PATH, "SQMA-002 config")
    supplied = Path(config_argument).expanduser().resolve()
    require(supplied == expected_config.resolve(), "unexpected config path")
    require_regular(supplied, "SQMA-002 config", single_link=False)
    config = read_json(supplied, "SQMA-002 config")
    implementation, prerequisites = validate_file_records(repo_root, config)
    require("run_sqma002_scoped_input" not in sys.modules, "runner module imported")
    contract = load_contract(repo_root, implementation["contract"])
    validate_config(config, contract)
    validate_prerequisites(repo_root, prerequisites)
    require("run_sqma002_scoped_input" not in sys.modules, "runner module imported")

    runtime = config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve(), "runtime executable drift")
    require(platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime identity drift")
    numpy = importlib.import_module("numpy")
    require(numpy.__version__ == runtime["packages"]["numpy"], "NumPy version drift")
    require(not (FORBIDDEN_FRAMEWORK_ROOTS & set(sys.modules)), "model framework imported")

    public_root = checked_path(repo_root, config["outputs"]["public_attempt_dir"], "public output")
    private_root = checked_path(repo_root, config["outputs"]["private_attempt_dir"], "private output")
    require(
        not os.path.lexists(private_root.with_name(private_root.name + ".staging")),
        "private staging namespace still exists",
    )
    validate_public_preinventory(public_root)
    _, private_bytes = inventory(private_root)
    require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private byte budget drift")
    require(not os.path.lexists(public_root / "verification.json") and not os.path.lexists(public_root / "complete.json"), "verification output already exists")

    claim = read_json(public_root / "run-claim.json", "run claim")
    run = read_json(public_root / "run.json", "run")
    private_manifest_path = private_root / "private-manifest.json"
    private_manifest = read_json(private_manifest_path, "private manifest")

    archive_value = os.environ.get(config["sources"]["archive_root_env"], config["sources"]["audited_archive_root"])
    require(isinstance(archive_value, str) and archive_value, "archive root missing")
    archive_root = Path(archive_value).expanduser().resolve()
    require(archive_root.is_absolute() and archive_root.is_dir(), "archive root unavailable")
    public_path = checked_path(repo_root, prerequisites["public_fold_manifest"]["path"], "public fold manifest")
    train_path = checked_path(archive_root, config["sources"]["train"]["relative_path"], "private train")
    private_fold_path = checked_path(archive_root, config["sources"]["private_fold_manifest"]["relative_path"], "private fold manifest")
    for path, name, expected in (
        (public_path, "public fold manifest", prerequisites["public_fold_manifest"]),
        (train_path, "private train", config["sources"]["train"]),
        (private_fold_path, "private fold manifest", config["sources"]["private_fold_manifest"]),
    ):
        mode = None if name == "public fold manifest" else "0600"
        observed = require_regular(path, name, mode=mode)
        require(observed.st_size == expected["bytes"] and sha256(path) == expected["sha256"], f"{name} identity drift")

    (
        fold_summaries,
        artifact_records,
        text_digests,
        value_digests,
        consumer_metadata,
        source_hashes,
    ) = replay_and_verify(
        public_path=public_path,
        train_path=train_path,
        private_fold_path=private_fold_path,
        private_root=private_root,
        config=config,
        contract=contract,
        numpy=numpy,
    )
    private_manifest_record = {
        "logical_name": "private-manifest.json",
        "bytes": private_manifest_path.stat().st_size,
        "sha256": sha256(private_manifest_path),
        "mode": "0600",
    }
    validate_private_manifest(
        private_manifest,
        config,
        contract,
        private_root,
        artifact_records,
        fold_summaries,
        text_digests,
        value_digests,
        consumer_metadata,
        source_hashes,
    )
    validate_run_public(
        claim,
        run,
        config,
        contract,
        repo_root,
        public_root,
        private_root,
        private_manifest_record,
        artifact_records,
        fold_summaries,
    )
    require("run_sqma002_scoped_input" not in sys.modules, "runner module imported")
    require(not (FORBIDDEN_FRAMEWORK_ROOTS & set(sys.modules)), "model framework imported")

    elapsed = time.monotonic() - started
    peak_rss = peak_rss_bytes()
    require(elapsed <= config["resources"]["maximum_wall_seconds"], "verifier wall cap exceeded")
    require(peak_rss <= config["resources"]["maximum_peak_rss_bytes"], "verifier RSS cap exceeded")
    summary = {
        str(fold): {
            "rows": fold_summaries[str(fold)]["rows"],
            "components": fold_summaries[str(fold)]["components"],
            "scope_count": 3,
        }
        for fold in contract.MATERIALIZED_FOLDS
    }
    verification: dict[str, Any] = {
        "schema_version": "sqma-002-verification-v1",
        "experiment_id": "SQMA-002",
        "status": "Passed",
        "started_at_utc": started_at,
        "verified_at_utc": utc_now(),
        "config": artifact_record(supplied, repo_root),
        "run": artifact_record(public_root / "run.json", repo_root),
        "run_claim": artifact_record(public_root / "run-claim.json", repo_root),
        "private_manifest": private_manifest_record,
        "claim_boundary": "The independent verifier replayed the registered sources, decoded private rows only for public folds 0-2, and verified the nine sealed snapshots. Folds 3-4 private rows were byte-streamed but not decoded. No model, training, forward, Agent, validation, or test access occurred.",
        "checks": [
            "identity_and_authorization",
            "independent_source_replay",
            "fold3_fold4_decode_boundary",
            "exact_private_inventory",
            "snapshot_schema_and_order",
            "cross_scope_text_and_value_parity",
            "consumer_npz_inventory_dtype_shape_and_values",
            "mode_owner_symlink_and_hardlink",
            "fit_allowlist",
            "public_privacy",
            "resource_and_access_boundary",
        ],
        "folds": summary,
        "totals": {"rows_per_scope": 2016, "components": 1963, "private_artifacts": 9, "fold3_output_rows": 0, "fold4_output_rows": 0},
        "resources": {
            "wall_seconds": elapsed,
            "peak_rss_bytes": peak_rss,
            "private_output_bytes": private_bytes,
            "model_or_mlx_allocations": 0,
            "critical_memory_events": 0,
            "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "access": {
            "monolithic_private_bytes_streamed": True,
            "private_rows_decoded": 2016,
            "fold0_rows_decoded": 672,
            "fold1_rows_decoded": 672,
            "fold2_rows_decoded": 672,
            "fold3_rows_decoded": 0,
            "fold4_rows_decoded": 0,
            "fold3_rows_byte_streamed": 672,
            "fold4_rows_byte_streamed": 672,
            "sealed_private_outputs_read": True,
            "runner_imported": False,
            "model_loaded": False,
            "forward_executed": False,
            "training_executed": False,
            "optimizer_executed": False,
            "agent_calls": 0,
            "network_accessed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "files_written_private": False,
        },
        "scoped_inputs_verified": True,
        "formal_training_authorized": False,
        "next_gate": "register_strict_agent_dev_formal_three_m1_three_m3",
    }
    public_safe(contract, verification, str(private_root.resolve()))
    verification_bytes = write_json_exclusive(public_root / "verification.json", verification)
    verification_record = artifact_record(public_root / "verification.json", repo_root)
    complete = {
        "schema_version": "sqma-002-complete-v1",
        "experiment_id": "SQMA-002",
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "verification": verification_record,
        "sqma002_complete": True,
        "scoped_inputs_verified": True,
        "training_executed": False,
        "model_loaded": False,
        "agent_calls": 0,
        "fold3_output_rows": 0,
        "fold4_output_rows": 0,
        "formal_training_authorized": False,
        "next_gate": "register_strict_agent_dev_formal_three_m1_three_m3",
    }
    public_safe(contract, complete, str(private_root.resolve()))
    complete_bytes = write_json_exclusive(public_root / "complete.json", complete)
    total_public = sum(path.stat().st_size for path in public_root.iterdir() if path.is_file())
    require(total_public <= config["resources"]["maximum_public_output_bytes"], "public output budget exceeded")
    require(verification_bytes > 0 and complete_bytes > 0, "verification output write failed")
    require(sorted(path.name for path in public_root.iterdir()) == sorted(config["outputs"]["public_allowed_files"]), "final public inventory drift")
    return verification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = verify(args.config)
    print(json.dumps({"experiment_id": "SQMA-002", "status": result["status"], "next_gate": result["next_gate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, zipfile.BadZipFile, VerificationError) as exc:
        print(f"SQMA-002 verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

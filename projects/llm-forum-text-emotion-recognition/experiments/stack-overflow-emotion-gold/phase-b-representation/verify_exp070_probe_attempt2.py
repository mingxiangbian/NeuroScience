#!/usr/bin/env python3
"""Append-only recovery verifier for the completed EXP-070 formal probe.

The static stages inspect identities, inventories, import boundaries, and a
synthetic privacy regression suite.  They do not read label, probability, or
representation values.  The formal stages call only the frozen verifier's
read-only validation and recomputation helpers.  All recovery artifacts are
written to fresh attempt-2 roots; the source attempt is never written.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib.metadata
import importlib.util
import json
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
from typing import Any, Callable, Iterator, Mapping, Sequence


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = (
    MODULE_DIR / "configs" / "exp-070-formal-probe-verification-attempt-2.json"
)
DEFAULT_PROTOCOL = (
    PROJECT_ROOT
    / "experiments"
    / "stack-overflow-emotion-gold"
    / "protocols"
    / "exp-070-formal-probe-verification-attempt-2.md"
)
DEFAULT_TESTS = MODULE_DIR / "tests" / "test_exp070_probe_attempt2.py"

EXPERIMENT_ID = "EXP-070"
RUN_ID = "exp-070-layerwise-probe-formal-probe"
SOURCE_ATTEMPT_ID = "formal-probe-attempt-1"
ATTEMPT_ID = "formal-probe-verification-attempt-2"
VERIFICATION_ATTEMPT = 2

SOURCE_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-probe-attempt-1"
)
SOURCE_PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-070-layerwise-probes/formal-probe-attempt-1"
)
STATIC_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-probe-verification-attempt-2-preflight"
)
RECOVERY_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-probe-verification-attempt-2"
)

EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256 = (
    "70e965af98259a52baeba677988a790097664a96ba9f54f084243b968ec569a0"
)
EXPECTED_NONSELF_CONFIG_SHA256 = (
    "0983536d8739b231ab741c545d4cf192adca6508465c05c7fa0560d4fa42f064"
)
EXPECTED_PROTOCOL_RECORD = {
    "path": (
        "experiments/stack-overflow-emotion-gold/protocols/"
        "exp-070-formal-probe-verification-attempt-2.md"
    ),
    "bytes": 9070,
    "mode": "0644",
    "sha256": "e908da3625297ddce317fb585b1e8cbc8b46f2c3adeda70b9375f0949f04e187",
}
EXPECTED_TESTS_RECORD = {
    "path": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/tests/"
        "test_exp070_probe_attempt2.py"
    ),
    "bytes": 39071,
    "mode": "0644",
    "sha256": "725cea6f3e8b8545e352585e4563b658b7302ddc264a36544489ba3918ce9532",
}
STATIC_ALLOWLIST = ["static-verification.json", "no-result-complete.json"]
RECOVERY_ALLOWLIST = [
    "source-snapshot-claim.json",
    "verification.json",
    "probe-complete.json",
]
SYNTHETIC_TEST_COUNT = 12

FORBIDDEN_MODEL_MODULES = {"mlx", "mlx_lm", "torch", "transformers"}
STATIC_VALUE_MODULES = {"numpy", "sklearn", "scipy"}

STATIC_CHECKS = [
    "recovery_config_identity",
    "recovery_implementation_identity",
    "source_implementation_identity",
    "source_awaiting_verification_inventory",
    "source_private_inventory",
    "source_modes_links",
    "source_snapshot_identity",
    "old_verifier_unexecuted",
    "exact_root_claim_contract",
    "original_privacy_predicate_preserved",
    "synthetic_privacy_regressions_12_of_12",
    "no_runner_or_model_import",
    "no_value_library_import",
    "no_label_probability_representation_value_read",
    "no_threshold_metric_bootstrap_recomputation",
    "fresh_recovery_output_root",
    "public_privacy",
    "source_unchanged",
]

RECOVERY_CHECKS = [
    "exact_root_claim_boundary_adapter",
    "original_privacy_predicate_restored",
    "immutable_source_snapshot",
    "fresh_append_only_recovery_namespace",
    "source_verifier_probability_only_replay",
]


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
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def require_canonical_json(path: Path) -> Any:
    value = strict_json(path)
    if path.read_bytes() != canonical_json_bytes(value):
        raise ValueError(f"Non-canonical JSON: {path}")
    return value


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
            raise PermissionError("Symlink path rejected")
    if must_exist and not os.path.lexists(path):
        raise FileNotFoundError(path)
    return path


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Unsafe or missing artifact: {path}")
    value: dict[str, Any] = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        value["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        value["logical_name"] = logical_name
    return value


def require_record(record: Mapping[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(str(record["path"]))
    if artifact(path) != dict(record):
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def require_named_record(record: Mapping[str, Any], expected_name: str) -> Path:
    if set(record) != {"logical_name", "path", "bytes", "mode", "sha256"}:
        raise ValueError("Named artifact record schema drift")
    if record.get("logical_name") != expected_name:
        raise ValueError("Named artifact logical-name drift")
    path_record = {key: record[key] for key in ("path", "bytes", "mode", "sha256")}
    return require_record(path_record)


def inventory(root: Path) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid evidence root")
    observed: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PermissionError("Nested symlink rejected")
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise PermissionError("Hard-link drift")
            observed.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise PermissionError("Special filesystem entry rejected")
    return observed


def directory_inventory(root: Path) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid evidence root")
    observed: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PermissionError("Nested symlink rejected")
        if path.is_dir():
            observed.add(path.relative_to(root).as_posix())
        elif not path.is_file():
            raise PermissionError("Special filesystem entry rejected")
    return observed


def require_exact_inventory(
    root: Path,
    expected_files: set[str],
    *,
    expected_directories: set[str] | None = None,
) -> None:
    directories = set() if expected_directories is None else expected_directories
    if inventory(root) != expected_files or directory_inventory(root) != directories:
        raise ValueError("Evidence root file or directory inventory drift")


def snapshot_digest(public_root: Path, private_root: Path) -> str:
    records: dict[str, dict[str, Any]] = {}
    for prefix, root in (("public", public_root), ("private", private_root)):
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Source snapshot root drift")
        records[f"{prefix}/"] = {"mode": file_mode(root)}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise PermissionError("Source snapshot symlink drift")
            if path.is_dir():
                records[f"{prefix}/{relative}/"] = {"mode": file_mode(path)}
            elif path.is_file() and path.stat().st_nlink == 1:
                records[f"{prefix}/{relative}"] = {
                    "bytes": path.stat().st_size,
                    "mode": file_mode(path),
                    "sha256": sha256(path),
                }
            else:
                raise PermissionError("Source snapshot entry drift")
    return bytes_sha256(canonical_json_bytes(records))


def ensure_public_root(path: Path) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.mkdir(parents=True, mode=0o755)
    os.chmod(path, 0o755)
    if path.is_symlink() or file_mode(path) != "0755":
        raise PermissionError("Recovery output root mode drift")


def create_json_once(path: Path, value: Any) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    if path.parent.is_symlink() or not path.parent.is_dir() or file_mode(path.parent) != "0755":
        raise PermissionError("Unsafe recovery output parent")
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
    if path.stat().st_nlink != 1 or file_mode(path) != "0644":
        raise PermissionError("Recovery JSON mode or link drift")


def require_exact_json(path: Path, expected: Mapping[str, Any]) -> None:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or file_mode(path) != "0644"
        or require_canonical_json(path) != dict(expected)
    ):
        raise ValueError(f"Recovery JSON prefix drift: {path.name}")


def validate_config(config: Mapping[str, Any]) -> None:
    if set(config) != {
        "schema_version",
        "experiment_id",
        "run_id",
        "source_attempt_id",
        "attempt_id",
        "verification_attempt",
        "registered_at",
        "scope",
        "source_snapshot",
        "incident_evidence",
        "privacy_contract",
        "authorization",
        "resources",
        "outputs",
        "implementation",
        "claim_boundary",
    }:
        raise ValueError("EXP-070 probe recovery config schema drift")
    if (
        config.get("schema_version")
        != "exp-070-formal-probe-verification-attempt-2-config-v1"
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("source_attempt_id") != SOURCE_ATTEMPT_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or config.get("verification_attempt") != VERIFICATION_ATTEMPT
    ):
        raise ValueError("EXP-070 probe recovery identity drift")
    if config.get("scope") != {
        "verification_only": True,
        "source_probe_rerun": False,
        "probe_refit": False,
        "assemble_rerun": False,
        "source_mutation": False,
        "exp071": False,
    }:
        raise ValueError("EXP-070 probe recovery scope drift")
    if config.get("incident_evidence") != {
        "old_verifier_unexecuted": True,
        "blocker": "public_privacy_false_positive_on_exact_claim_boundary_component_disjoint",
        "source_status": "CompletedAwaitingVerification",
        "source_verification_absent": True,
        "source_completion_absent": True,
        "actual_private_data_exposure": False,
    }:
        raise ValueError("EXP-070 probe recovery incident drift")
    if config.get("privacy_contract") != {
        "exact_json_path": "$.claim_boundary",
        "exact_claim_boundary_sha256": EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256,
        "allowed_false_positive_token": "component-disjoint",
        "original_predicate_unchanged": True,
        "component_id_rejection": True,
        "sample_id_rejection": True,
        "private_path_rejection": True,
        "forbidden_key_rejection": True,
        "long_list_minimum": 672,
    }:
        raise ValueError("EXP-070 probe recovery privacy contract drift")
    if config.get("authorization") != {
        "static_preflight": True,
        "formal_verification": True,
        "formal_completion": True,
        "source_file_identity": True,
        "sealed_probability_values": True,
        "label_values": True,
        "threshold_recomputation": True,
        "metrics_recomputation": True,
        "bootstrap_recomputation": True,
        "probe_refit": False,
        "representation_values": False,
        "model_loading": False,
        "forward": False,
        "source_mutation": False,
        "validation": False,
        "test": False,
        "exp071": False,
    }:
        raise PermissionError("EXP-070 probe recovery authorization drift")
    if config.get("resources") != {
        "formal_wall_seconds": 43200,
        "peak_rss_bytes": 8589934592,
        "free_disk_bytes": 536870912,
        "static_test_timeout_seconds": 300,
    }:
        raise ValueError("EXP-070 probe recovery resource contract drift")
    if config.get("outputs") != {
        "source_public_root": SOURCE_PUBLIC_ROOT,
        "source_private_root": SOURCE_PRIVATE_ROOT,
        "static_public_root": STATIC_PUBLIC_ROOT,
        "recovery_public_root": RECOVERY_PUBLIC_ROOT,
        "static_allowlist": STATIC_ALLOWLIST,
        "recovery_allowlist": RECOVERY_ALLOWLIST,
    }:
        raise ValueError("EXP-070 probe recovery output contract drift")
    source = config.get("source_snapshot")
    if not isinstance(source, Mapping) or set(source) != {
        "formal_config",
        "formal_protocol",
        "source_runner",
        "source_verifier",
        "source_tests",
        "run_claim",
        "probe",
        "input_manifest",
        "probe_manifest",
        "fold_artifacts",
    }:
        raise ValueError("EXP-070 probe recovery source record inventory drift")
    folds = source.get("fold_artifacts")
    expected_names = [
        name
        for fold in range(5)
        for name in (f"folds/f{fold}.json", f"folds/f{fold}.npz")
    ]
    if (
        not isinstance(folds, list)
        or len(folds) != 10
        or [item.get("logical_name") for item in folds if isinstance(item, Mapping)]
        != expected_names
    ):
        raise ValueError("EXP-070 probe recovery fold record order drift")
    implementation = config.get("implementation")
    if not isinstance(implementation, Mapping) or set(implementation) != {
        "protocol",
        "verifier",
        "tests",
    }:
        raise ValueError("EXP-070 probe recovery implementation inventory drift")
    if not isinstance(config.get("claim_boundary"), str) or not config["claim_boundary"]:
        raise ValueError("EXP-070 probe recovery claim boundary drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("Recovery requires the frozen default config")
    value = strict_json(path)
    if not isinstance(value, dict):
        raise ValueError("Recovery config root must be an object")
    nonself = {key: item for key, item in value.items() if key != "implementation"}
    if bytes_sha256(canonical_json_bytes(nonself)) != EXPECTED_NONSELF_CONFIG_SHA256:
        raise ValueError("EXP-070 probe recovery non-self config drift")
    validate_config(value)
    return value


def require_implementation_records(config: Mapping[str, Any]) -> dict[str, Path]:
    implementation = config.get("implementation")
    if not isinstance(implementation, Mapping):
        raise ValueError("Recovery implementation inventory missing")
    if implementation.get("protocol") != EXPECTED_PROTOCOL_RECORD:
        raise ValueError("Recovery protocol binding drift")
    if implementation.get("tests") != EXPECTED_TESTS_RECORD:
        raise ValueError("Recovery tests binding drift")
    verifier_record = implementation.get("verifier")
    expected_verifier_path = (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/"
        "verify_exp070_probe_attempt2.py"
    )
    if (
        not isinstance(verifier_record, Mapping)
        or set(verifier_record) != {"path", "bytes", "mode", "sha256"}
        or verifier_record.get("path") != expected_verifier_path
    ):
        raise ValueError("Recovery verifier binding drift")
    protocol_path = require_record(implementation["protocol"])
    tests_path = require_record(implementation["tests"])
    verifier_path = require_record(verifier_record)
    if protocol_path.resolve() != DEFAULT_PROTOCOL.resolve():
        raise ValueError("Recovery protocol path drift")
    if tests_path.resolve() != DEFAULT_TESTS.resolve():
        raise ValueError("Recovery tests path drift")
    if verifier_path.resolve() != Path(__file__).resolve():
        raise ValueError("Recovery verifier self path drift")
    if dict(verifier_record) != artifact(Path(__file__).resolve()):
        raise ValueError("Recovery verifier self identity drift")
    return {
        "implementation_protocol": protocol_path,
        "implementation_tests": tests_path,
        "implementation_verifier": verifier_path,
    }


def require_config_records(config: Mapping[str, Any]) -> dict[str, Path]:
    source = config["source_snapshot"]
    paths = require_implementation_records(config)
    for key in (
        "formal_config",
        "formal_protocol",
        "source_runner",
        "source_verifier",
        "source_tests",
        "run_claim",
        "probe",
        "input_manifest",
        "probe_manifest",
    ):
        paths[key] = require_record(source[key])
    for fold, record in enumerate(source["fold_artifacts"]):
        expected_name = f"folds/f{fold // 2}.{'json' if fold % 2 == 0 else 'npz'}"
        require_named_record(record, expected_name)
    return paths


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def _has_attribute_call(path: Path, attribute: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
        for node in ast.walk(tree)
    )


def require_import_boundaries(paths: Mapping[str, Path]) -> None:
    for key in ("source_verifier", "implementation_verifier", "implementation_tests"):
        imports = _imports(paths[key])
        if imports & FORBIDDEN_MODEL_MODULES:
            raise RuntimeError(f"Forbidden model import in {key}")
    if any(
        "run_exp070_probe" in _imports(paths[key])
        for key in ("source_verifier", "implementation_verifier")
    ):
        raise RuntimeError("A verifier imports the producer")
    if _has_attribute_call(
        paths["implementation_verifier"], "fit"
    ) or _has_attribute_call(paths["source_verifier"], "fit"):
        raise RuntimeError("Probe fitting call found in verifier source")
    imported = {name.split(".")[0] for name in sys.modules}
    if imported & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("Verifier process contains a model library")


def load_source_verifier(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "exp070_probe_attempt2_frozen_source_verifier", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "_public_sensitive", None)):
        raise ValueError("Frozen verifier privacy predicate missing")
    return module


def make_public_sensitive_adapter(
    original: Callable[[Any], bool], expected_claim_boundary: str
) -> Callable[[Any], bool]:
    if (
        type(expected_claim_boundary) is not str
        or bytes_sha256(expected_claim_boundary.encode("utf-8"))
        != EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256
    ):
        raise ValueError("Frozen formal claim boundary identity drift")
    depth = 0
    missing = object()

    def adapter(value: Any) -> bool:
        nonlocal depth
        at_root = depth == 0
        depth += 1
        try:
            candidate = value
            if at_root:
                if not isinstance(value, Mapping):
                    return True
                boundary = value.get("claim_boundary", missing)
                if type(boundary) is not str or boundary != expected_claim_boundary:
                    return True
                if (
                    bytes_sha256(boundary.encode("utf-8"))
                    != EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256
                ):
                    return True
                candidate = dict(value)
                del candidate["claim_boundary"]
            return bool(original(candidate))
        finally:
            depth -= 1

    return adapter


@contextmanager
def patched_public_privacy(
    verifier: Any, expected_claim_boundary: str
) -> Iterator[Callable[[Any], bool]]:
    original = verifier._public_sensitive
    adapter = make_public_sensitive_adapter(original, expected_claim_boundary)
    verifier._public_sensitive = adapter
    try:
        yield adapter
    finally:
        verifier._public_sensitive = original


@contextmanager
def blocked_source_writes(verifier: Any) -> Iterator[None]:
    original = verifier.create_json_once

    def reject_write(_path: Path, _value: Any) -> None:
        raise PermissionError("Recovery replay attempted to write the source attempt")

    verifier.create_json_once = reject_write
    try:
        yield
    finally:
        verifier.create_json_once = original


@contextmanager
def in_memory_artifact(
    verifier: Any, target: Path, value: Mapping[str, Any]
) -> Iterator[None]:
    original = verifier.artifact
    payload = verifier.canonical_json_bytes(dict(value))

    def adapter(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
        if path.resolve() == target.resolve():
            record: dict[str, Any] = {
                "bytes": len(payload),
                "mode": "0644",
                "sha256": bytes_sha256(payload),
            }
            if logical_name is None:
                record["path"] = path.relative_to(PROJECT_ROOT).as_posix()
            else:
                record["logical_name"] = logical_name
            return record
        return original(path, logical_name=logical_name)

    verifier.artifact = adapter
    try:
        yield
    finally:
        verifier.artifact = original


def require_static_runtime(source_config: Mapping[str, Any]) -> Mapping[str, Any]:
    expected = source_config.get("environment")
    if not isinstance(expected, Mapping):
        raise ValueError("Frozen source environment contract missing")
    executable = Path(str(expected.get("python_executable", "")))
    if (
        not executable.is_file()
        or Path(sys.executable).resolve() != executable.resolve()
        or platform.python_version() != expected.get("python_version")
        or platform.machine() != expected.get("architecture")
        or os.environ.get("PYTHONNOUSERSITE") != "1"
    ):
        raise RuntimeError("Static recovery runtime identity drift")
    thread_environment = expected.get("thread_environment")
    if not isinstance(thread_environment, Mapping) or any(
        os.environ.get(str(key)) != str(value)
        for key, value in thread_environment.items()
    ):
        raise RuntimeError("Static recovery thread environment drift")
    packages = expected.get("packages")
    if not isinstance(packages, Mapping) or set(packages) != {
        "numpy",
        "scikit-learn",
        "scipy",
        "joblib",
    }:
        raise RuntimeError("Static recovery package contract drift")
    for distribution, expected_version in packages.items():
        try:
            observed_version = importlib.metadata.version(str(distribution))
        except importlib.metadata.PackageNotFoundError as error:
            raise RuntimeError("Static recovery package identity drift") from error
        if observed_version != expected_version:
            raise RuntimeError("Static recovery package identity drift")
    return expected


def run_synthetic_tests(
    config: Mapping[str, Any],
    tests_path: Path,
    source_environment: Mapping[str, Any],
) -> dict[str, Any]:
    command = [str(source_environment["python_executable"]), str(tests_path)]
    environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        **{
            str(key): str(value)
            for key, value in source_environment["thread_environment"].items()
        },
    }
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=int(config["resources"]["static_test_timeout_seconds"]),
        check=False,
    )
    transcript = completed.stdout + "\n" + completed.stderr
    match = re.search(r"Ran (\d+) tests?", transcript)
    if (
        completed.returncode != 0
        or match is None
        or int(match.group(1)) != SYNTHETIC_TEST_COUNT
        or "OK" not in transcript
    ):
        raise RuntimeError("EXP-070 recovery synthetic regression suite failed")
    return {
        "test_artifact": artifact(tests_path),
        "tests_run": SYNTHETIC_TEST_COUNT,
        "status": "Passed",
        "command_sha256": bytes_sha256(canonical_json_bytes(command)),
    }


def _expected_fold_names() -> list[str]:
    return [
        name
        for fold in range(5)
        for name in (f"folds/f{fold}.json", f"folds/f{fold}.npz")
    ]


def validate_source_identity_only(
    config: Mapping[str, Any], paths: Mapping[str, Path]
) -> dict[str, Any]:
    source_config = strict_json(paths["formal_config"])
    if not isinstance(source_config, Mapping):
        raise ValueError("Frozen formal config root drift")
    expected_implementation = {
        "protocol": config["source_snapshot"]["formal_protocol"],
        "runner": config["source_snapshot"]["source_runner"],
        "verifier": config["source_snapshot"]["source_verifier"],
        "tests": config["source_snapshot"]["source_tests"],
    }
    if source_config.get("implementation") != expected_implementation:
        raise ValueError("Recovery source implementation binding drift")
    source_boundary = source_config.get("claim_boundary")
    if (
        type(source_boundary) is not str
        or bytes_sha256(source_boundary.encode("utf-8"))
        != EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256
        or source_boundary.lower().count("component-") != 1
        or any(
            marker in source_boundary.lower()
            for marker in ("/users/", "phase-b-representation/private/", "sample-")
        )
    ):
        raise ValueError("Recovery source claim-boundary contract drift")
    outputs = source_config.get("outputs")
    if (
        not isinstance(outputs, Mapping)
        or outputs.get("formal_public_root") != SOURCE_PUBLIC_ROOT
        or outputs.get("formal_private_root") != SOURCE_PRIVATE_ROOT
        or outputs.get("formal_public_awaiting_verification_allowlist")
        != ["run-claim.json", "probe.json"]
    ):
        raise ValueError("Recovery source output binding drift")
    public = resolve_project(config["outputs"]["source_public_root"])
    private = resolve_project(config["outputs"]["source_private_root"])
    if file_mode(public) != "0755" or file_mode(private) != "0700":
        raise PermissionError("Recovery source root mode drift")
    require_exact_inventory(public, {"run-claim.json", "probe.json"})
    expected_private = set(outputs.get("formal_private_success_allowlist", []))
    if expected_private != {
        "input-manifest.json",
        "probe-manifest.json",
        *_expected_fold_names(),
    }:
        raise ValueError("Recovery source private inventory drift")
    require_exact_inventory(
        private, expected_private, expected_directories={"folds"}
    )
    if file_mode(private / "folds") != "0700":
        raise PermissionError("Recovery source folds directory mode drift")
    if artifact(public / "run-claim.json") != config["source_snapshot"]["run_claim"]:
        raise ValueError("Recovery run-claim identity drift")
    if artifact(public / "probe.json") != config["source_snapshot"]["probe"]:
        raise ValueError("Recovery probe identity drift")
    if paths["probe"].read_bytes().count(
        b'"status":"CompletedAwaitingVerification"'
    ) != 1:
        raise ValueError("Recovery source status drift")
    if artifact(private / "input-manifest.json") != config["source_snapshot"]["input_manifest"]:
        raise ValueError("Recovery input-manifest identity drift")
    if artifact(private / "probe-manifest.json") != config["source_snapshot"]["probe_manifest"]:
        raise ValueError("Recovery probe-manifest identity drift")
    for name, record in zip(
        _expected_fold_names(), config["source_snapshot"]["fold_artifacts"], strict=True
    ):
        if artifact(private / name) != {
            key: record[key] for key in ("bytes", "mode", "sha256", "path")
        }:
            raise ValueError(f"Recovery fold identity drift: {name}")
    return {
        "source_config": source_config,
        "source_boundary": source_boundary,
        "public": public,
        "private": private,
        "snapshot_sha256": snapshot_digest(public, private),
    }


def build_static_verification(
    config_path: Path,
    config: Mapping[str, Any],
    paths: Mapping[str, Path],
    source: Mapping[str, Any],
    tests: Mapping[str, Any],
) -> dict[str, Any]:
    private_identity_records = [
        {
            "logical_name": record["logical_name"],
            "bytes": record["bytes"],
            "mode": record["mode"],
            "sha256": record["sha256"],
        }
        for record in config["source_snapshot"]["fold_artifacts"]
    ]
    return {
        "schema_version": "exp-070-probe-verification-attempt-2-static-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "stage": "static",
        "status": "Passed",
        "passed_count": len(STATIC_CHECKS),
        "failed_count": 0,
        "checks": STATIC_CHECKS,
        "config": artifact(config_path),
        "source_formal_config": config["source_snapshot"]["formal_config"],
        "source_verifier": config["source_snapshot"]["source_verifier"],
        "source_run_claim": config["source_snapshot"]["run_claim"],
        "source_probe": config["source_snapshot"]["probe"],
        "source_input_manifest": artifact(
            paths["input_manifest"], logical_name="input-manifest.json"
        ),
        "source_probe_manifest": artifact(
            paths["probe_manifest"], logical_name="probe-manifest.json"
        ),
        "fold_artifact_identity_sha256": bytes_sha256(
            canonical_json_bytes(private_identity_records)
        ),
        "source_snapshot_sha256": source["snapshot_sha256"],
        "exact_claim_boundary_sha256": EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256,
        "synthetic_tests": dict(tests),
        "recovery_verification_authorized": True,
        "recovery_completion_authorized": False,
        "formal_probe_complete": False,
        "exp070_complete": False,
        "exp071_authorized": False,
        "runner_imported": False,
        "model_libraries_imported": False,
        "value_libraries_imported": False,
        "access": {
            "source_file_bytes_hashed": True,
            "source_metadata_config_parsed": True,
            "source_status_inspected_without_results": True,
            "source_run_results_parsed": False,
            "label_values_read": False,
            "sealed_probability_values_read": False,
            "representation_values_read": False,
            "thresholds_recomputed": False,
            "metrics_recomputed": False,
            "bootstrap_recomputed": False,
            "probe_refit": False,
            "model_loaded": False,
            "forward_executed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "recovery_claim_boundary": config["claim_boundary"],
        "next_gate": "EXP-070 formal-probe verification attempt 2",
    }


def build_static_completion(
    config_path: Path,
    config: Mapping[str, Any],
    verification_path: Path,
    source_snapshot_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "exp-070-probe-verification-attempt-2-static-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "status": "Complete",
        "config": artifact(config_path),
        "static_verification": artifact(verification_path),
        "source_snapshot_sha256": source_snapshot_sha256,
        "formal_verification_authorized": True,
        "recovery_verification_authorized": True,
        "recovery_completion_authorized": False,
        "formal_probe_complete": False,
        "exp070_complete": False,
        "exp071_authorized": False,
        "label_probability_representation_values_read": False,
        "performance_metrics_computed": False,
        "recovery_claim_boundary": config["claim_boundary"],
        "next_gate": "Run formal-verify in a separate invocation",
    }


def no_result_audit(
    config_path: Path,
    config: Mapping[str, Any],
    *,
    require_recovery_absent: bool,
) -> tuple[dict[str, Any], dict[str, Any], Any, dict[str, Any]]:
    if shutil.disk_usage(PROJECT_ROOT).free < int(config["resources"]["free_disk_bytes"]):
        raise OSError("EXP-070 recovery static free-disk gate failed")
    paths = require_config_records(config)
    require_import_boundaries(paths)
    imported_before = {name.split(".")[0] for name in sys.modules}
    if imported_before & (FORBIDDEN_MODEL_MODULES | STATIC_VALUE_MODULES):
        raise RuntimeError("Static recovery process imported a forbidden library")
    source = validate_source_identity_only(config, paths)
    verifier = load_source_verifier(paths["source_verifier"])
    if verifier._public_sensitive(source["source_boundary"]) is not True:
        raise ValueError("Frozen privacy blocker is no longer reproducible")
    if verifier._public_sensitive({"recovery_claim_boundary": config["claim_boundary"]}):
        raise ValueError("Recovery claim boundary is not public-safe")
    source_environment = require_static_runtime(source["source_config"])
    tests = run_synthetic_tests(
        config, paths["implementation_tests"], source_environment
    )
    imported_after = {name.split(".")[0] for name in sys.modules}
    if imported_after & (FORBIDDEN_MODEL_MODULES | STATIC_VALUE_MODULES):
        raise RuntimeError("Static recovery audit imported a forbidden library")
    if snapshot_digest(source["public"], source["private"]) != source["snapshot_sha256"]:
        raise ValueError("EXP-070 source changed during no-result audit")
    recovery = resolve_project(config["outputs"]["recovery_public_root"], must_exist=False)
    if require_recovery_absent and os.path.lexists(recovery):
        raise FileExistsError("Formal recovery root exists during static gate")
    verification = build_static_verification(config_path, config, paths, source, tests)
    if verifier._public_sensitive(verification):
        raise ValueError("EXP-070 recovery static public privacy drift")
    return verification, source, verifier, paths


def verify_static(config_path: Path, *, complete: bool) -> dict[str, Any]:
    config = load_config(config_path)
    verification, source, verifier, _paths = no_result_audit(
        config_path, config, require_recovery_absent=True
    )
    root = resolve_project(config["outputs"]["static_public_root"], must_exist=False)
    verification_path = root / "static-verification.json"
    completion_path = root / "no-result-complete.json"
    if os.path.lexists(root):
        if root.is_symlink() or not root.is_dir() or file_mode(root) != "0755":
            raise PermissionError("Static recovery root drift")
        observed = inventory(root)
        if directory_inventory(root):
            raise FileExistsError("Static recovery root contains a nested directory")
        allowed_prefixes = (
            {"static-verification.json"},
            set(STATIC_ALLOWLIST),
        )
        if observed not in allowed_prefixes:
            raise FileExistsError("Static recovery root is not an exact prefix")
        require_exact_json(verification_path, verification)
    else:
        if complete:
            raise RuntimeError("Static completion requires Passed static verification")
        ensure_public_root(root)
        create_json_once(verification_path, verification)
    if complete:
        completion = build_static_completion(
            config_path, config, verification_path, source["snapshot_sha256"]
        )
        if verifier._public_sensitive(completion):
            raise ValueError("EXP-070 recovery static completion privacy drift")
        if os.path.lexists(completion_path):
            require_exact_json(completion_path, completion)
        else:
            create_json_once(completion_path, completion)
        require_exact_inventory(root, set(STATIC_ALLOWLIST))
    elif os.path.lexists(completion_path):
        raise RuntimeError("Static verify cannot consume completion")
    else:
        require_exact_inventory(root, {"static-verification.json"})
    return verification


def require_static_completion(
    config_path: Path, config: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], Any, dict[str, Any], Path]:
    verification, source, verifier, paths = no_result_audit(
        config_path, config, require_recovery_absent=False
    )
    root = resolve_project(config["outputs"]["static_public_root"])
    require_exact_inventory(root, set(STATIC_ALLOWLIST))
    verification_path = root / "static-verification.json"
    completion_path = root / "no-result-complete.json"
    require_exact_json(verification_path, verification)
    completion = build_static_completion(
        config_path, config, verification_path, source["snapshot_sha256"]
    )
    require_exact_json(completion_path, completion)
    return verification, source, verifier, paths, completion_path


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def run_source_replay(
    config: Mapping[str, Any],
    verifier: Any,
    paths: Mapping[str, Path],
    source_boundary: str,
    *,
    include_completion: bool,
) -> dict[str, Any]:
    started = time.monotonic()
    original_privacy = verifier._public_sensitive
    original_writer = verifier.create_json_once
    source_config_path = paths["formal_config"]
    source_config = verifier.load_config(source_config_path, kind="formal")
    if source_config.get("claim_boundary") != source_boundary:
        raise ValueError("Frozen formal claim boundary changed before replay")
    implementation_paths = verifier.require_implementation(source_config)
    verifier.require_import_boundaries(implementation_paths, static=False)
    static_completion = verifier.require_static_completion(source_config)
    environment = verifier.require_environment(source_config)
    verifier.require_private_ignore()
    public, private, public_files = verifier._validate_formal_roots(source_config)
    expected_public = set(
        source_config["outputs"]["formal_public_awaiting_verification_allowlist"]
    )
    if public_files != expected_public:
        raise ValueError("Source formal root left awaiting-verification state")
    before = verifier.source_identity_snapshot(source_config)
    sources = verifier.require_frozen_sources(source_config)
    if verifier.source_identity_snapshot(source_config) != before:
        raise ValueError("Source identity changed during frozen-source replay")
    verifier._validate_claim_and_input(
        source_config_path,
        source_config,
        static_completion,
        sources,
        before,
        environment,
        public,
        private,
    )
    public_rows = verifier._public_fold_rows(source_config)
    verifier.prevalidate_fold_structures(source_config, before, public_rows)
    labels = verifier.load_labels(source_config, public_rows)
    recomputed = verifier.recompute_results(source_config, labels, public_rows, before)
    del labels
    with blocked_source_writes(verifier), patched_public_privacy(
        verifier, source_boundary
    ):
        _source_manifest, source_report = verifier._validate_manifests_and_report(
            source_config_path, source_config, public, private, before, recomputed
        )
        final_source = verifier.source_identity_snapshot(source_config)
        if (
            final_source != before
            or verifier.recovery_snapshot_digest() != verifier.SOURCE_SNAPSHOT_SHA256
        ):
            raise ValueError("Source changed during recovery verifier replay")
        source_verification = verifier._formal_verification(
            source_config_path,
            source_config,
            public,
            private,
            static_completion,
            before,
            recomputed,
        )
        source_completion = None
        if include_completion:
            virtual_path = public / "verification.json"
            with in_memory_artifact(verifier, virtual_path, source_verification):
                source_completion = verifier._formal_completion(
                    source_config,
                    public,
                    private,
                    static_completion,
                    virtual_path,
                    recomputed["results"],
                )
    if verifier._public_sensitive is not original_privacy:
        raise AssertionError("Frozen privacy predicate was not restored")
    if verifier.create_json_once is not original_writer:
        raise AssertionError("Frozen source writer was not restored")
    elapsed = time.monotonic() - started
    if elapsed > float(config["resources"]["formal_wall_seconds"]):
        raise TimeoutError("EXP-070 recovery verifier wall-time ceiling exceeded")
    if _peak_rss_bytes() > int(config["resources"]["peak_rss_bytes"]):
        raise MemoryError("EXP-070 recovery verifier peak-RSS ceiling exceeded")
    imported = {name.split(".")[0] for name in sys.modules}
    if imported & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("EXP-070 recovery imported a model library")
    if any(name.endswith("run_exp070_probe") for name in sys.modules):
        raise RuntimeError("EXP-070 recovery imported the producer")
    return {
        "source_verification": source_verification,
        "source_completion": source_completion,
        "results": recomputed["results"],
        "source_report_resources": source_report["resources"],
        "elapsed_seconds": elapsed,
        "peak_rss_bytes": _peak_rss_bytes(),
    }


def build_snapshot_claim(
    config_path: Path,
    config: Mapping[str, Any],
    source: Mapping[str, Any],
    static_completion_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "exp-070-probe-verification-attempt-2-snapshot-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "status": "Claimed",
        "config": artifact(config_path),
        "static_completion": artifact(static_completion_path),
        "source_run_claim": config["source_snapshot"]["run_claim"],
        "source_probe": config["source_snapshot"]["probe"],
        "source_snapshot_sha256": source["snapshot_sha256"],
        "source_original_verifier_unexecuted": True,
        "source_mutated": False,
        "claim_boundary": source["source_boundary"],
        "recovery_claim_boundary": config["claim_boundary"],
    }


def build_recovery_verification(
    config_path: Path,
    config: Mapping[str, Any],
    source: Mapping[str, Any],
    claim_path: Path,
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    source_verification = replay["source_verification"]
    access = source_verification.get("access", {})
    if (
        source_verification.get("status") != "Passed"
        or source_verification.get("failed_count") != 0
        or source_verification.get("probe_refit") is not False
        or source_verification.get("runner_imported") is not False
        or source_verification.get("model_libraries_imported") is not False
        or access.get("representation_values_read") is not False
        or access.get("probe_refit") is not False
        or access.get("validation_accessed") is not False
        or access.get("test_accessed") is not False
        or access.get("model_loaded") is not False
        or access.get("forward_executed") is not False
    ):
        raise ValueError("Frozen formal verification replay contract drift")
    checks = list(source_verification["checks"]) + RECOVERY_CHECKS
    return {
        "schema_version": "exp-070-probe-verification-attempt-2-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "stage": "formal",
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "config": artifact(config_path),
        "source_snapshot_claim": artifact(claim_path),
        "source_snapshot_sha256": source["snapshot_sha256"],
        "source_snapshot_unchanged": True,
        "source_run_claim": config["source_snapshot"]["run_claim"],
        "source_probe": config["source_snapshot"]["probe"],
        "source_probe_manifest": artifact(
            resolve_project(config["source_snapshot"]["probe_manifest"]["path"]),
            logical_name="probe-manifest.json",
        ),
        "source_verifier": config["source_snapshot"]["source_verifier"],
        "source_verification_payload_sha256": bytes_sha256(
            canonical_json_bytes(source_verification)
        ),
        "results_sha256": source_verification["results_sha256"],
        "negative_control_failure": source_verification["negative_control_failure"],
        "representation_state": source_verification["representation_state"],
        "representation_state_label": source_verification[
            "representation_state_label"
        ],
        "probability_only_verification": True,
        "formal_probe_complete": False,
        "exp070_complete": False,
        "exp071_authorized": False,
        "probe_refit": False,
        "runner_imported": False,
        "model_libraries_imported": False,
        "source_original_verifier_unexecuted": True,
        "source_mutated": False,
        "privacy_adapter": {
            "exact_json_path": "$.claim_boundary",
            "exact_claim_boundary_sha256": EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256,
            "original_predicate_restored": True,
        },
        "source_report_resources": replay["source_report_resources"],
        "access": dict(access),
        "claim_boundary": source["source_boundary"],
        "recovery_claim_boundary": config["claim_boundary"],
    }


def build_recovery_completion(
    config_path: Path,
    config: Mapping[str, Any],
    source: Mapping[str, Any],
    claim_path: Path,
    verification_path: Path,
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    source_completion = replay.get("source_completion")
    results = replay["results"]
    if (
        not isinstance(source_completion, Mapping)
        or source_completion.get("status") != "Complete"
        or source_completion.get("formal_probe_complete") is not True
        or source_completion.get("exp070_complete") is not True
        or source_completion.get("exp071_authorized") is not False
        or source_completion.get("model_loaded") is not False
        or source_completion.get("forward_executed") is not False
        or source_completion.get("source_mutated") is not False
        or source_completion.get("verifier_refit_probe") is not False
    ):
        raise ValueError("Frozen formal completion replay contract drift")
    return {
        "schema_version": "exp-070-probe-complete-v2",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "status": "Complete",
        "completed_via": ATTEMPT_ID,
        "formal_probe_complete": True,
        "exp070_complete": True,
        "exp071_authorized": False,
        "performance_metrics_computed": True,
        "negative_control_failure": results["negative_control_failure"],
        "representation_state_assignment_valid": not bool(
            results["negative_control_failure"]
        ),
        "representation_state": results["representation_state"],
        "representation_state_label": results["representation_state_label"],
        "model_loaded": False,
        "forward_executed": False,
        "source_mutated": False,
        "verifier_refit_probe": False,
        "source_original_verifier_unexecuted": True,
        "config": artifact(config_path),
        "source_snapshot_claim": artifact(claim_path),
        "verification": artifact(verification_path),
        "source_completion_payload_sha256": bytes_sha256(
            canonical_json_bytes(source_completion)
        ),
        "source_snapshot_sha256": source["snapshot_sha256"],
        "claim_boundary": source["source_boundary"],
        "recovery_claim_boundary": config["claim_boundary"],
        "next_gate": "EXP-070 Complete; EXP-071 unauthorized",
    }


def prepare_formal_prefix(
    root: Path,
    claim: Mapping[str, Any],
    *,
    complete: bool,
) -> tuple[Path, Path, Path]:
    claim_path = root / "source-snapshot-claim.json"
    verification_path = root / "verification.json"
    completion_path = root / "probe-complete.json"
    if not os.path.lexists(root):
        if complete:
            raise RuntimeError("Formal completion requires Passed recovery verification")
        ensure_public_root(root)
        create_json_once(claim_path, claim)
        return claim_path, verification_path, completion_path
    if root.is_symlink() or not root.is_dir() or file_mode(root) != "0755":
        raise PermissionError("Formal recovery root drift")
    observed = inventory(root)
    if directory_inventory(root):
        raise FileExistsError("Formal recovery root contains a nested directory")
    valid = (
        {"source-snapshot-claim.json"},
        {"source-snapshot-claim.json", "verification.json"},
        set(RECOVERY_ALLOWLIST),
    )
    if observed not in valid:
        raise FileExistsError("Formal recovery root is not an exact prefix")
    require_exact_json(claim_path, claim)
    if complete:
        if "verification.json" not in observed:
            raise RuntimeError("Formal completion requires Passed recovery verification")
        prefix = require_canonical_json(verification_path)
        if (
            verification_path.is_symlink()
            or not verification_path.is_file()
            or verification_path.stat().st_nlink != 1
            or file_mode(verification_path) != "0644"
            or not isinstance(prefix, Mapping)
            or prefix.get("status") != "Passed"
            or prefix.get("failed_count") != 0
        ):
            raise RuntimeError("Formal completion requires a Passed recovery prefix")
    elif "verification.json" in observed:
        raise RuntimeError("Formal verify cannot consume an existing verification")
    return claim_path, verification_path, completion_path


def verify_formal(config_path: Path, *, complete: bool) -> dict[str, Any]:
    config = load_config(config_path)
    _static, source, verifier, paths, static_completion_path = require_static_completion(
        config_path, config
    )
    root = resolve_project(config["outputs"]["recovery_public_root"], must_exist=False)
    claim = build_snapshot_claim(
        config_path, config, source, static_completion_path
    )
    with patched_public_privacy(verifier, source["source_boundary"]):
        if verifier._public_sensitive(claim):
            raise ValueError("EXP-070 recovery snapshot claim privacy drift")
    claim_path, verification_path, completion_path = prepare_formal_prefix(
        root, claim, complete=complete
    )
    before = source["snapshot_sha256"]
    replay = run_source_replay(
        config,
        verifier,
        paths,
        source["source_boundary"],
        include_completion=complete,
    )
    after = snapshot_digest(source["public"], source["private"])
    if after != before:
        raise ValueError("EXP-070 source changed during recovery replay")
    verification = build_recovery_verification(
        config_path, config, source, claim_path, replay
    )
    with patched_public_privacy(verifier, source["source_boundary"]):
        if verifier._public_sensitive(verification):
            raise ValueError("EXP-070 recovery verification public privacy drift")
    if os.path.lexists(verification_path):
        require_exact_json(verification_path, verification)
    elif complete:
        raise RuntimeError("Formal completion requires exact Passed verification")
    else:
        create_json_once(verification_path, verification)
    if complete:
        completion = build_recovery_completion(
            config_path,
            config,
            source,
            claim_path,
            verification_path,
            replay,
        )
        with patched_public_privacy(verifier, source["source_boundary"]):
            if verifier._public_sensitive(completion):
                raise ValueError("EXP-070 recovery completion public privacy drift")
        if os.path.lexists(completion_path):
            require_exact_json(completion_path, completion)
        else:
            create_json_once(completion_path, completion)
        require_exact_inventory(root, set(RECOVERY_ALLOWLIST))
    elif os.path.lexists(completion_path):
        raise RuntimeError("Formal verify cannot consume completion")
    else:
        require_exact_inventory(
            root, {"source-snapshot-claim.json", "verification.json"}
        )
    return verification


def record_recovery_failure(
    stage: str, config_path: Path, error: BaseException
) -> None:
    try:
        if stage not in {"static-verify", "formal-verify"}:
            return
        if config_path.resolve() != DEFAULT_CONFIG.resolve():
            return
        config = strict_json(config_path)
        if not isinstance(config, Mapping):
            return
        validate_config(config)
        nonself = {key: value for key, value in config.items() if key != "implementation"}
        if bytes_sha256(canonical_json_bytes(nonself)) != EXPECTED_NONSELF_CONFIG_SHA256:
            return
        require_implementation_records(config)
        verifier_path = require_record(config["source_snapshot"]["source_verifier"])
        verifier = load_source_verifier(verifier_path)
        if stage == "static-verify":
            root = resolve_project(config["outputs"]["static_public_root"], must_exist=False)
            value = {
                "schema_version": "exp-070-probe-verification-attempt-2-static-failure-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "source_attempt_id": SOURCE_ATTEMPT_ID,
                "attempt_id": ATTEMPT_ID,
                "verification_attempt": VERIFICATION_ATTEMPT,
                "stage": "static",
                "status": "Failed",
                "technical_failure": True,
                "error_type": type(error).__name__,
                "config": artifact(config_path),
                "formal_verification_authorized": False,
                "formal_probe_complete": False,
                "exp070_complete": False,
                "exp071_authorized": False,
                "recovery_claim_boundary": config["claim_boundary"],
            }
            if verifier._public_sensitive(value):
                return
            if not os.path.lexists(root):
                ensure_public_root(root)
            elif root.is_symlink() or not root.is_dir() or file_mode(root) != "0755":
                return
            if inventory(root) or directory_inventory(root):
                return
            create_json_once(root / "static-verification.json", value)
            return

        root = resolve_project(config["outputs"]["recovery_public_root"], must_exist=False)
        if (
            not root.is_dir()
            or root.is_symlink()
            or file_mode(root) != "0755"
            or inventory(root) != {"source-snapshot-claim.json"}
            or directory_inventory(root)
        ):
            return
        claim_path = root / "source-snapshot-claim.json"
        claim = require_canonical_json(claim_path)
        if (
            not isinstance(claim, Mapping)
            or claim.get("status") != "Claimed"
            or claim.get("config") != artifact(config_path)
        ):
            return
        source_config = strict_json(
            require_record(config["source_snapshot"]["formal_config"])
        )
        source_boundary = source_config.get("claim_boundary")
        if (
            type(source_boundary) is not str
            or bytes_sha256(source_boundary.encode("utf-8"))
            != EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256
        ):
            return
        value = {
            "schema_version": "exp-070-probe-verification-attempt-2-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "source_attempt_id": SOURCE_ATTEMPT_ID,
            "attempt_id": ATTEMPT_ID,
            "verification_attempt": VERIFICATION_ATTEMPT,
            "stage": "formal",
            "status": "Failed",
            "technical_failure": True,
            "error_type": type(error).__name__,
            "config": artifact(config_path),
            "source_snapshot_claim": artifact(claim_path),
            "formal_probe_complete": False,
            "exp070_complete": False,
            "exp071_authorized": False,
            "probe_refit": False,
            "recovery_wrote_source": False,
            "source_original_verifier_unexecuted": True,
            "claim_boundary": source_boundary,
            "recovery_claim_boundary": config["claim_boundary"],
        }
        with patched_public_privacy(verifier, source_boundary):
            if verifier._public_sensitive(value):
                return
        create_json_once(root / "verification.json", value)
    except Exception:
        return


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("static-verify", "static-complete", "formal-verify", "formal-complete"),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    kind, phase = args.stage.split("-", 1)
    try:
        result = (
            verify_static(args.config, complete=phase == "complete")
            if kind == "static"
            else verify_formal(args.config, complete=phase == "complete")
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:
        record_recovery_failure(args.stage, args.config, error)
        print(f"{type(error).__name__}: recovery verification failed", file=sys.stderr)
        return 1
    print(json.dumps({"stage": args.stage, "status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

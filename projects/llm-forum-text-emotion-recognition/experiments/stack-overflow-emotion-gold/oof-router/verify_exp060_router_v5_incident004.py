#!/usr/bin/env python3
"""Minimal Incident-004 snapshot adapter for EXP-060 final verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from types import ModuleType
from typing import Any


INCIDENT_ID = "004"
RECOVERY_ATTEMPT = 2
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "configs" / (
    "exp-062-seed-44-router-replication-router-formal-attempt-1-incident-003.json"
)
V4_RUNNER_PATH = SCRIPT_DIR / "run_exp060_router_v4_incident003.py"
V4_VERIFIER_PATH = SCRIPT_DIR / "verify_exp060_router_v4_incident003.py"

CONFIG_BYTES = 20500
CONFIG_SHA256 = "87fec24aefceb18b84fbd8d71da44b68bda84b0c0e09269329d27cb82002ca18"
V4_RUNNER_BYTES = 72713
V4_RUNNER_SHA256 = "2bd8d0d9e06915f6123d5edee733b75d9a3c21314dfff88436f550cc1f0960f0"
V4_VERIFIER_BYTES = 69514
V4_VERIFIER_SHA256 = "fd196ed83b6b76ea6e4e9a370f899194f86d4df8d3705a346c20b6fe92cef127"


def _stat_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _held_payload(path: Path, expected_bytes: int, expected_sha256: str) -> bytes:
    canonical = path.resolve()
    if canonical != path or not os.path.lexists(path):
        raise ValueError(f"Pinned path drift: {path}")
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise PermissionError(f"Pinned file mode/type/link drift: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    if _stat_signature(before) != _stat_signature(after):
        raise RuntimeError(f"Pinned file changed while held: {path}")
    if len(payload) != expected_bytes or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError(f"Pinned file content drift: {path}")
    return payload


def _held_module(path: Path, expected_bytes: int, expected_sha256: str, name: str) -> ModuleType:
    payload = _held_payload(path, expected_bytes, expected_sha256)
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    exec(compile(payload.decode("utf-8"), str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def _typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _typed_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _typed_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _expected_raw_keys(config: dict[str, Any]) -> set[str]:
    attempt2 = config["preflight_recovery"]["attempt_2"]
    return (
        {"config", "pyc", "input", "absent"}
        | {f"implementation.{name}" for name in config["implementation"]}
        | {f"prerequisites.{name}" for name in config["prerequisites"]}
        | {
            f"attempt1.{name}"
            for name in config["preflight_recovery"]["attempt_1"]
        }
        | {f"attempt2.{name}" for name in attempt2 if name != "frozen_sources"}
        | {f"frozen.{name}" for name in attempt2["frozen_sources"]}
    )


def normalize_snapshot(raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != _expected_raw_keys(config):
        raise ValueError("Incident004 verifier snapshot inventory drift")
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        if key == "input":
            target = "input.paired_oof"
        elif key == "absent":
            target = "canonical_absent"
        elif key.startswith("attempt1."):
            target = f"recovery.{key}"
        elif key.startswith("attempt2."):
            target = f"recovery.{key}"
        elif key.startswith("frozen."):
            target = f"recovery.{key}"
        else:
            target = key
        if target in normalized:
            raise ValueError(f"Incident004 snapshot key collision: {target}")
        normalized[target] = value
    if len(normalized) != len(raw):
        raise ValueError("Incident004 snapshot mapping is not bijective")
    return normalized


def _prepare(config_path: Path) -> tuple[ModuleType, ModuleType, Path, dict[str, Any], str]:
    canonical = config_path.resolve()
    if canonical != CONFIG_PATH:
        raise ValueError("Incident004 requires the frozen seed-44 formal config")
    _held_payload(CONFIG_PATH, CONFIG_BYTES, CONFIG_SHA256)
    runner = _held_module(
        V4_RUNNER_PATH, V4_RUNNER_BYTES, V4_RUNNER_SHA256, "_incident004_v4_runner"
    )
    verifier = _held_module(
        V4_VERIFIER_PATH,
        V4_VERIFIER_BYTES,
        V4_VERIFIER_SHA256,
        "_incident004_v4_verifier",
    )
    runner_path, runner_config = runner.validate_launch_contract(
        canonical, runner._load_verified_v3()
    )
    verifier_path, verifier_config = verifier.validate_launch_contract(
        canonical, verifier._load_verified_v3()
    )
    if runner_path != verifier_path or not _typed_equal(runner_config, verifier_config):
        raise ValueError("Incident004 runner/verifier launch contract drift")
    runner._validate_completed_stage("run", canonical, runner_config)
    runner_snapshot = runner._immutable_snapshot(canonical, runner_config)
    verifier_snapshot = normalize_snapshot(
        verifier._immutable_snapshot(canonical, verifier_config), verifier_config
    )
    if not _typed_equal(verifier_snapshot, runner_snapshot):
        raise ValueError("Incident004 normalized snapshot differs from runner snapshot")
    digest = runner._canonical_digest(runner_snapshot)
    run_terminal = json.loads(
        runner._secure_read(runner._stage_path("run", "terminal"), 0o644)[0].decode("utf-8")
    )
    if (
        run_terminal.get("immutable_before_sha256") != digest
        or run_terminal.get("immutable_after_sha256") != digest
    ):
        raise ValueError("Incident004 normalized snapshot does not reproduce the run seal")
    return runner, verifier, canonical, runner_config, digest


def _execute_loaded(
    runner: ModuleType,
    verifier: ModuleType,
    canonical: Path,
    config: dict[str, Any],
    scope: str,
) -> dict[str, Any]:
    original_snapshot = verifier._immutable_snapshot
    calls = 0

    def canonical_snapshot(path: Path, value: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        normalized = normalize_snapshot(original_snapshot(path, value), value)
        expected = runner._immutable_snapshot(path, value)
        if not _typed_equal(normalized, expected):
            raise ValueError("Incident004 runtime snapshot parity drift")
        return normalized

    try:
        verifier._immutable_snapshot = canonical_snapshot
        result = verifier.execute(canonical, scope)
    finally:
        verifier._immutable_snapshot = original_snapshot
    if verifier._immutable_snapshot is not original_snapshot or calls <= 0:
        raise RuntimeError("Incident004 snapshot patch/call/restore drift")
    if (
        not isinstance(result, dict)
        or result.get("status") != "Passed"
        or type(result.get("passed_count")) is not int
        or result["passed_count"] <= 0
        or type(result.get("failed_count")) is not int
        or result["failed_count"] != 0
    ):
        raise RuntimeError("Incident004 verifier did not return a full pass")
    if os.path.lexists(runner.SELECTION_PATH):
        raise RuntimeError("Incident004 selection boundary violated")
    return result


def execute(config_path: Path, scope: str) -> dict[str, Any]:
    if scope not in {"final", "completion"}:
        raise ValueError("Incident004 supports final/completion verification only")
    runner, verifier, canonical, config, _ = _prepare(config_path)
    previous = ("run",) if scope == "final" else ("run", "final", "complete")
    for stage in previous:
        runner._validate_completed_stage(stage, canonical, config)
    return _execute_loaded(runner, verifier, canonical, config, scope)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scope", choices=("final", "completion"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = execute(args.config, args.scope)
    print(
        json.dumps(
            {
                "attempt": RECOVERY_ATTEMPT,
                "failed_count": result["failed_count"],
                "incident_id": INCIDENT_ID,
                "passed_count": result["passed_count"],
                "scope": args.scope,
                "status": result["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()


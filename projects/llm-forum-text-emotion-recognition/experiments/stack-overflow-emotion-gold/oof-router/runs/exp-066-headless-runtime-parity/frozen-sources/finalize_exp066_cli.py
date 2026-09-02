#!/usr/bin/env python3
"""Activate the thin EXP-066 CLI only after independent parity passes."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


EXPERIMENT_ID = "EXP-066"
RUN_ID = "exp-066-headless-runtime-parity"


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
RUN_DIR = PROJECT_ROOT / BASE / "runs" / RUN_ID
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-066-headless-runtime-parity.json"
DEFAULT_CLI = PROJECT_ROOT / BASE / "phase_a_predict.py"
COMPLETION = RUN_DIR / "runtime-complete.json"
CLAIM_BOUNDARY = (
    "A verified 32-row checkpoint-to-headless-runtime parity result for the frozen seed-42 "
    "local development stack only; no classification performance, independent-test, latency, "
    "production, forum-generalization, or emotion-mechanism claim."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path) -> dict[str, Any]:
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise ValueError(f"EXP-066 finalizer file mode/type drift: {path}")
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "bytes": metadata.st_size,
        "sha256": sha256(path),
        "mode": "0644",
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def validate_cli(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            function = node.func
            if isinstance(function, ast.Name):
                calls.append(function.id)
            elif isinstance(function, ast.Attribute):
                calls.append(function.attr)
    if "runtime_exp066" not in imports:
        raise ValueError("EXP-066 CLI must delegate to runtime_exp066")
    if "runtime-complete.json" not in source or "status" not in source or "Complete" not in source:
        raise ValueError("EXP-066 CLI completion gate missing")
    forbidden_calls = {
        "write", "write_text", "write_bytes", "open", "touch", "mkdir", "makedirs",
        "replace", "rename", "remove", "unlink",
    }
    if set(calls) & forbidden_calls:
        raise ValueError(f"EXP-066 CLI persistent-write call detected: {set(calls) & forbidden_calls}")
    if "include_diagnostics=False" not in source or "allow_qwen=args.allow_qwen" not in source:
        raise ValueError("EXP-066 CLI predict delegation drift")


def _create(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o644)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, 0o644)


def finalize(config_path: Path, cli_path: Path) -> dict[str, Any]:
    if config_path.resolve() != DEFAULT_CONFIG.resolve() or cli_path.resolve() != DEFAULT_CLI.resolve():
        raise ValueError("EXP-066 finalizer requires frozen config/CLI paths")
    if os.path.lexists(COMPLETION):
        raise FileExistsError("EXP-066 runtime completion already exists")
    config = load_json(config_path)
    run = load_json(RUN_DIR / "run.json")
    verification = load_json(RUN_DIR / "verification.json")
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("cli_gate") != "closed_pending_independent_parity"
        or verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
        or verification.get("cli_gate") != "ready_for_activation"
    ):
        raise ValueError("EXP-066 parity is not eligible for CLI activation")
    validate_cli(cli_path)
    cli_record = record(cli_path)
    value = {
        "schema_version": "exp-066-runtime-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "run": record(RUN_DIR / "run.json"),
        "verification": record(RUN_DIR / "verification.json"),
        "verification_summary": record(RUN_DIR / "VERIFICATION-SUMMARY.md"),
        "cli": cli_record,
        "cli_gate": "open",
        "ordinary_request_persistence": False,
        "diagnostics_default": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _create(COMPLETION, canonical_json(value))
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cli", type=Path, default=DEFAULT_CLI)
    args = parser.parse_args()
    print(json.dumps(finalize(args.config, args.cli), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

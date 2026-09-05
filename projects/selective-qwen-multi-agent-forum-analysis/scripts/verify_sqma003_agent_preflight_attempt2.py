#!/usr/bin/env python3
"""Attempt-2 entrypoint for the independent SQMA-003 verifier.

The verified logic is reused from the model-free attempt-1 verifier.  This
wrapper fixes every mutable identity to attempt 2 before delegating and never
opens, names, or imports the attempt-1 private run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any


sys.dont_write_bytecode = True
REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ATTEMPT2_CONFIG = (
    PROJECT_ROOT / "configs/sqma-003-classifier-free-agent-preflight-attempt-2.json"
)
ATTEMPT2_CONFIG_RELATIVE = ATTEMPT2_CONFIG.relative_to(REPO_ROOT).as_posix()
ATTEMPT2_RUNNER_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
    "run_sqma003_agent_preflight_attempt2.py"
)
ATTEMPT2_VERIFIER_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
    "verify_sqma003_agent_preflight_attempt2.py"
)
ATTEMPT2_PROMPT_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/prompts/"
    "agent-bundle-v2-classifier-free.json"
)
ATTEMPT2_PUBLIC_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/runs/"
    "sqma-003-classifier-free-agent-preflight/attempt-2"
)
ATTEMPT2_PRIVATE_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/private/"
    "sqma-003-classifier-free-agent-preflight/attempt-2"
)
BASE_VERIFIER = PROJECT_ROOT / "scripts/verify_sqma003_agent_preflight.py"
BASE_VERIFIER_SHA256 = "5e32fe65bd1b5c37e7c1eac7e3f629933e0870a70a8c80f35f7e71f7a0251ef8"
FORBIDDEN_IMPORT_ROOTS = {"mlx", "mlx_lm", "torch", "transformers"}


class Attempt2VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Attempt2VerificationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def regular_file(path: Path, label: str) -> None:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(
        stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode),
        f"invalid {label}",
    )


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_file(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Attempt2VerificationError(f"invalid {label}") from exc
    require(isinstance(value, dict), f"{label} root drift")
    return value


def validate_attempt2_config(path: Path) -> dict[str, Any]:
    supplied = path.expanduser().resolve()
    require(supplied == ATTEMPT2_CONFIG.resolve(), "noncanonical attempt-2 config")
    config = read_json(supplied, "attempt-2 config")
    require(config.get("experiment_id") == "SQMA-003", "experiment identity drift")
    implementation = config.get("implementation")
    outputs = config.get("outputs")
    require(isinstance(implementation, dict) and isinstance(outputs, dict), "contract missing")
    require(
        implementation.get("runner", {}).get("path") == ATTEMPT2_RUNNER_RELATIVE,
        "attempt-2 runner identity drift",
    )
    require(
        implementation.get("verifier", {}).get("path") == ATTEMPT2_VERIFIER_RELATIVE,
        "attempt-2 verifier identity drift",
    )
    require(
        implementation.get("prompt_bundle", {}).get("path") == ATTEMPT2_PROMPT_RELATIVE,
        "attempt-2 prompt identity drift",
    )
    require(
        outputs.get("public_attempt_dir") == ATTEMPT2_PUBLIC_RELATIVE
        and outputs.get("private_attempt_dir") == ATTEMPT2_PRIVATE_RELATIVE,
        "attempt-2 output identity drift",
    )
    encoded = json.dumps(outputs, ensure_ascii=True, sort_keys=True)
    require("attempt-1" not in encoded, "attempt-2 output references attempt 1")
    return config


def load_base_verifier() -> Any:
    regular_file(BASE_VERIFIER, "base verifier")
    require(sha256(BASE_VERIFIER) == BASE_VERIFIER_SHA256, "base verifier identity drift")
    module_name = "sqma003_attempt1_verifier_logic_for_attempt2"
    spec = importlib.util.spec_from_file_location(module_name, BASE_VERIFIER)
    require(spec is not None and spec.loader is not None, "base verifier import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    require(
        "run_sqma003_agent_preflight" not in sys.modules
        and not (FORBIDDEN_IMPORT_ROOTS & set(sys.modules)),
        "base verifier crossed the runner/model import boundary",
    )
    return module


def verify(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_attempt2_config(config_path)
    base = load_base_verifier()
    original_config = base.CONFIG_PATH
    original_file = base.__file__
    base.CONFIG_PATH = ATTEMPT2_CONFIG
    # The base verifier checks that the config-bound verifier is the executing
    # entrypoint.  Point only that identity check at this frozen wrapper.
    base.__file__ = str(Path(__file__).resolve())
    try:
        try:
            base_verification, base_complete = base.verify(ATTEMPT2_CONFIG.resolve())
        except base.VerificationError as exc:
            raise Attempt2VerificationError(str(exc)) from exc
    finally:
        base.CONFIG_PATH = original_config
        base.__file__ = original_file
    public_root = REPO_ROOT / ATTEMPT2_PUBLIC_RELATIVE
    verification = read_json(public_root / "verification.json", "attempt-2 verification")
    complete = read_json(public_root / "complete.json", "attempt-2 completion")
    require(
        verification == base_verification and complete == base_complete,
        "delegated attempt-2 output drift",
    )
    return verification, complete


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    arguments = parser.parse_args()
    supplied = Path(arguments.config).expanduser().resolve()
    verification, complete = verify(supplied)
    print(
        json.dumps(
            {
                "experiment_id": "SQMA-003",
                "verification_attempt": 2,
                "status": verification.get("status"),
                "sqma003_complete": complete.get("sqma003_complete"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, Attempt2VerificationError) as exc:
        print(f"SQMA-003 attempt-2 verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

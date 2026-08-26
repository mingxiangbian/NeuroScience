#!/usr/bin/env python3
"""Thin CLI for the verified EXP-066 headless runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True

import runtime_exp066


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


CLI_PATH = Path(__file__).resolve()
PROJECT_ROOT = _project_root(CLI_PATH)
RUN_DIR = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/oof-router/runs/"
    / "exp-066-headless-runtime-parity/attempt-2"
)
COMPLETION = RUN_DIR / "runtime-complete.json"
FROZEN_CONFIG = RUN_DIR / "frozen-sources/config.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _completion_gate() -> dict:
    if not COMPLETION.is_file():
        raise RuntimeError("EXP-066 runtime is not Complete")
    completion = json.loads(COMPLETION.read_text(encoding="utf-8"))
    if (
        completion.get("status") != "Complete"
        or completion.get("cli_gate") != "open"
        or completion.get("ordinary_request_persistence") is not False
        or completion.get("diagnostics_default") is not False
    ):
        raise RuntimeError("EXP-066 runtime completion gate failed")
    cli = completion.get("cli", {})
    metadata = CLI_PATH.stat()
    if (
        cli.get("path") != str(CLI_PATH.relative_to(PROJECT_ROOT))
        or cli.get("bytes") != metadata.st_size
        or cli.get("sha256") != _sha256(CLI_PATH)
        or cli.get("mode") != "0644"
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise RuntimeError("EXP-066 CLI identity drift")
    return completion


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the verified local Phase A predictor")
    parser.add_argument("--text", required=True)
    parser.add_argument("--no-qwen", dest="allow_qwen", action="store_false")
    parser.set_defaults(allow_qwen=True)
    args = parser.parse_args()
    try:
        args.text.encode("utf-8", errors="strict")
        _completion_gate()
        config = json.loads(FROZEN_CONFIG.read_text(encoding="utf-8"))
        runtime = runtime_exp066.build_real_runtime(config, PROJECT_ROOT)
        result = runtime.predict(args.text, allow_qwen=args.allow_qwen, include_diagnostics=False)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {"status": "error", "error_type": type(error).__name__},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

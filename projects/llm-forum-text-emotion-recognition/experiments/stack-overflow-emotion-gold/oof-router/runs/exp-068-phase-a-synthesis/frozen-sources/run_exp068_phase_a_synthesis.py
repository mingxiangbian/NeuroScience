#!/usr/bin/env python3
"""Run the read-only EXP-068 Phase A terminal synthesis."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


EXPERIMENT_ID = "EXP-068"
RUN_ID = "exp-068-phase-a-synthesis"
CONFIG_SCHEMA = "exp-068-phase-a-synthesis-config-v1"
CLAIM_BOUNDARY = (
    "Phase A produced a verified seed-42 headless/CLI research demo, but the preregistered "
    "steady-state efficiency benchmark did not complete; therefore no deployment-efficiency, "
    "production, independent-test, forum-generalization, or emotion-mechanism claim is supported."
)
SENSITIVE_KEYS = {
    "text", "raw_text", "sample_id", "sample_ids", "component_id", "component_ids",
    "ordinal", "ordinals", "probabilities", "prediction", "predictions", "features",
    "route_mask", "timing_rows", "memory_samples", "private_path",
}


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-068-phase-a-synthesis.json"
RUN_REL = BASE / "runs" / RUN_ID
RUN_DIR = PROJECT_ROOT / RUN_REL


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _resolve_public(value: str | Path) -> Path:
    relative = Path(value)
    lowered = {part.lower() for part in relative.parts}
    if (
        relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
        or "private" in lowered
        or "validation" in lowered
        or "test" in lowered
    ):
        raise PermissionError(f"EXP-068 non-public source path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"EXP-068 source traverses symlink: {value}")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("EXP-068 source escapes project")
    return path


def artifact(path: Path) -> dict[str, Any]:
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise ValueError(f"EXP-068 public source mode/type drift: {path}")
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "bytes": metadata.st_size,
        "sha256": sha256(path),
        "mode": "0644",
    }


def require_record(value: dict[str, Any]) -> Path:
    if set(value) != {"path", "bytes", "sha256", "mode"}:
        raise ValueError("EXP-068 source record schema drift")
    path = _resolve_public(value["path"])
    if artifact(path) != value:
        raise ValueError(f"EXP-068 source identity drift: {value['path']}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def decide(
    core_complete: bool,
    runtime_verified: bool,
    benchmark_complete: bool,
    efficiency_level: str | None,
    efficiency_gates_passed: bool,
) -> dict[str, Any]:
    if core_complete and runtime_verified and benchmark_complete and efficiency_gates_passed and efficiency_level in {"Strong", "Moderate"}:
        state = "Verified local development inference prototype"
    elif core_complete and runtime_verified and benchmark_complete:
        state = "Retained as research demo"
    else:
        state = "Failed or incomplete"
    return {
        "state": state,
        "verified_headless_cli_research_demo": bool(core_complete and runtime_verified),
        "formal_efficiency_benchmark_complete": benchmark_complete,
        "deployment_efficiency_claim_supported": bool(
            state == "Verified local development inference prototype"
        ),
    }


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in SENSITIVE_KEYS:
                output.append(path)
            output.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return output


def load_config(path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    path = path.resolve()
    if path != DEFAULT_CONFIG.resolve():
        raise ValueError("EXP-068 requires frozen config path")
    if artifact(path)["mode"] != "0644":
        raise ValueError("EXP-068 config mode drift")
    config = load_json(path)
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("claim_boundary") != CLAIM_BOUNDARY
        or config.get("output_dir") != str(RUN_REL)
    ):
        raise ValueError("EXP-068 config identity drift")
    sources: dict[str, Path] = {"config": path}
    for section in ("inputs", "implementation"):
        for name, value in config[section].items():
            sources[name] = require_record(value)
    return config, sources


def compute_synthesis(config: dict[str, Any], sources: dict[str, Path]) -> dict[str, Any]:
    exp064_completion = load_json(sources["exp064_completion"])
    exp064_verification = load_json(sources["exp064_verification"])
    exp065_completion = load_json(sources["exp065_completion"])
    exp065_verification = load_json(sources["exp065_verification"])
    exp066_completion = load_json(sources["exp066_completion"])
    exp066_verification = load_json(sources["exp066_verification"])
    exp067_attempt1 = load_json(sources["exp067_attempt1_run"])
    exp067_attempt2 = load_json(sources["exp067_attempt2_run"])
    core_complete = all(
        (
            exp064_completion.get("status") == "Complete",
            exp064_verification.get("status") == "Passed",
            exp065_completion.get("status") == "Complete",
            exp065_verification.get("status") == "Passed",
        )
    )
    runtime_verified = bool(
        exp066_completion.get("status") == "Complete"
        and exp066_completion.get("cli_gate") == "open"
        and exp066_verification.get("status") == "Passed"
        and exp066_verification.get("failed_count") == 0
    )
    benchmark_complete = False
    if exp067_attempt1.get("status") != "Failed" or exp067_attempt2.get("status") != "Failed":
        raise ValueError("EXP-068 EXP-067 terminal state drift")
    decision = decide(core_complete, runtime_verified, benchmark_complete, None, False)
    if decision["state"] != config["decision_rules"]["expected_current_state"]:
        raise ValueError("EXP-068 preregistered current-state decision drift")
    return {
        "schema_version": "exp-068-phase-a-synthesis-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "CompletedAwaitingVerification",
        "components": {
            "EXP-064": {"status": "Complete", "verification": "Passed"},
            "EXP-065": {"status": "Complete", "verification": "Passed", "selected_attempt": "attempt-2"},
            "EXP-066": {
                "status": "Complete",
                "verification": "Passed",
                "selected_attempt": "attempt-2",
                "cli_gate": "open",
            },
            "EXP-067": {
                "attempt_1_status": "Failed",
                "attempt_2_status": "Failed",
                "formal_benchmark_complete": False,
                "aggregate_available": False,
                "verification_available": False,
            },
        },
        "decision": decision,
        "supported_claim": (
            "The frozen seed-42 bundle, label-free projection, headless runtime, checkpoint parity, "
            "and thin CLI are verified as a local research demo."
        ),
        "unsupported_claims": [
            "steady-state latency reduction",
            "deployment-efficiency benefit",
            "production readiness",
            "independent-data or test benefit",
            "cross-seed deployment generalization",
        ],
        "next_action": (
            "Archive Phase A as incomplete for deployment efficiency; retain the verified CLI as a "
            "research demo and do not infer latency benefit from partial EXP-067 workers."
        ),
        "inputs": config["inputs"],
        "access_attestation": {
            "public_aggregate_records_only": True,
            "private_accessed": False,
            "raw_text_accessed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "model_or_checkpoint_accessed": False,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _create(path: Path, payload: bytes, mode: int = 0o644) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, mode)


def freeze_sources(sources: dict[str, Path]) -> dict[str, Any]:
    frozen = RUN_DIR / "frozen-sources"
    frozen.mkdir(mode=0o755)
    output: dict[str, Any] = {}
    for name in ("config", "protocol", "runner", "verifier", "tests"):
        source = sources[name]
        target = frozen / ("config.json" if name == "config" else source.name)
        _create(target, source.read_bytes())
        output[name] = artifact(target)
    return output


def execute(path: Path) -> dict[str, Any]:
    config, sources = load_config(path)
    if os.path.lexists(RUN_DIR):
        raise FileExistsError("EXP-068 output exists")
    synthesis = compute_synthesis(config, sources)
    if public_sensitive_paths(synthesis):
        raise RuntimeError("EXP-068 synthesis privacy drift")
    RUN_DIR.mkdir(mode=0o755)
    implementation = freeze_sources(sources)
    _create(
        RUN_DIR / "run-claim.json",
        canonical_json(
            {
                "schema_version": "exp-068-run-claim-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "status": "Claimed",
                "claimed_at_utc": utc_now(),
                "config": artifact(path.resolve()),
                "read_only": True,
            }
        ),
    )
    synthesis_path = RUN_DIR / "phase-a-synthesis.json"
    _create(synthesis_path, canonical_json(synthesis))
    run = {
        "schema_version": "exp-068-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "tier": "Major",
        "rq_id": "RQ-S3",
        "status": "CompletedAwaitingVerification",
        "completed_at_utc": utc_now(),
        "implementation": implementation,
        "synthesis": artifact(synthesis_path),
        "decision": synthesis["decision"],
        "access_attestation": synthesis["access_attestation"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if public_sensitive_paths(run):
        raise RuntimeError("EXP-068 run privacy drift")
    _create(RUN_DIR / "run.json", canonical_json(run))
    return run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(execute(args.config), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Independently verify the read-only EXP-068 Phase A synthesis."""

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
RUN_DIR = PROJECT_ROOT / BASE / "runs/exp-068-phase-a-synthesis"


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


def _resolve(value: str | Path) -> Path:
    relative = Path(value)
    lowered = {part.lower() for part in relative.parts}
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts) or "private" in lowered:
        raise PermissionError("EXP-068 verifier non-public path")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError("EXP-068 verifier symlink path")
    return (PROJECT_ROOT / relative).resolve()


def _regular(path: Path) -> os.stat_result:
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise ValueError("EXP-068 verifier file mode/type drift")
    return metadata


def record(path: Path) -> dict[str, Any]:
    metadata = _regular(path)
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "bytes": metadata.st_size,
        "sha256": sha256(path),
        "mode": "0644",
    }


def require_record(value: dict[str, Any]) -> Path:
    path = _resolve(value["path"])
    if record(path) != value:
        raise ValueError("EXP-068 verifier source identity drift")
    return path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def decision(
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


def _typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def load_config(path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    path = path.resolve()
    if path != DEFAULT_CONFIG.resolve():
        raise ValueError("EXP-068 verifier requires frozen config")
    config = load_json(path)
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("EXP-068 verifier config drift")
    sources: dict[str, Path] = {"config": path}
    for section in ("inputs", "implementation"):
        for name, value in config[section].items():
            sources[name] = require_record(value)
    return config, sources


def expected_synthesis(config: dict[str, Any], sources: dict[str, Path]) -> dict[str, Any]:
    values = {name: load_json(sources[name]) for name in config["inputs"]}
    core = bool(
        values["exp064_completion"].get("status") == "Complete"
        and values["exp064_verification"].get("status") == "Passed"
        and values["exp065_completion"].get("status") == "Complete"
        and values["exp065_verification"].get("status") == "Passed"
    )
    runtime = bool(
        values["exp066_completion"].get("status") == "Complete"
        and values["exp066_completion"].get("cli_gate") == "open"
        and values["exp066_verification"].get("status") == "Passed"
    )
    if values["exp067_attempt1_run"].get("status") != "Failed" or values["exp067_attempt2_run"].get("status") != "Failed":
        raise ValueError("EXP-068 verifier EXP-067 state drift")
    result = decision(core, runtime, False, None, False)
    return {
        "schema_version": "exp-068-phase-a-synthesis-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "CompletedAwaitingVerification",
        "components": {
            "EXP-064": {"status": "Complete", "verification": "Passed"},
            "EXP-065": {"status": "Complete", "verification": "Passed", "selected_attempt": "attempt-2"},
            "EXP-066": {
                "status": "Complete", "verification": "Passed",
                "selected_attempt": "attempt-2", "cli_gate": "open",
            },
            "EXP-067": {
                "attempt_1_status": "Failed", "attempt_2_status": "Failed",
                "formal_benchmark_complete": False, "aggregate_available": False,
                "verification_available": False,
            },
        },
        "decision": result,
        "supported_claim": (
            "The frozen seed-42 bundle, label-free projection, headless runtime, checkpoint parity, "
            "and thin CLI are verified as a local research demo."
        ),
        "unsupported_claims": [
            "steady-state latency reduction", "deployment-efficiency benefit",
            "production readiness", "independent-data or test benefit",
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


def verify(path: Path) -> dict[str, Any]:
    config, sources = load_config(path)
    if stat.S_IMODE(os.lstat(RUN_DIR).st_mode) != 0o755:
        raise ValueError("EXP-068 run dir mode drift")
    for name in ("verification.json", "VERIFICATION-SUMMARY.md", "phase-a-complete.json"):
        if os.path.lexists(RUN_DIR / name):
            raise FileExistsError("EXP-068 verifier output exists")
    claim = load_json(RUN_DIR / "run-claim.json")
    run = load_json(RUN_DIR / "run.json")
    synthesis = load_json(RUN_DIR / "phase-a-synthesis.json")
    for name in ("run-claim.json", "run.json", "phase-a-synthesis.json"):
        _regular(RUN_DIR / name)
    if (
        claim.get("status") != "Claimed"
        or claim.get("read_only") is not True
        or run.get("status") != "CompletedAwaitingVerification"
        or public_sensitive_paths(claim)
        or public_sensitive_paths(run)
        or public_sensitive_paths(synthesis)
    ):
        raise ValueError("EXP-068 public state/privacy drift")
    frozen = run["implementation"]
    source_map = {"config": path.resolve()}
    source_map.update({name: sources[name] for name in ("protocol", "runner", "verifier", "tests")})
    if set(frozen) != set(source_map):
        raise ValueError("EXP-068 frozen source set drift")
    for name, original in source_map.items():
        frozen_path = require_record(frozen[name])
        if frozen_path.read_bytes() != original.read_bytes():
            raise ValueError("EXP-068 frozen source bytes drift")
    expected = expected_synthesis(config, sources)
    if not _typed_equal(synthesis, expected):
        raise ValueError("EXP-068 synthesis replay mismatch")
    if run.get("decision") != expected["decision"] or run.get("synthesis") != record(RUN_DIR / "phase-a-synthesis.json"):
        raise ValueError("EXP-068 run cross-record drift")
    checks = [
        "config_identity", "source_records", "public_only_paths", "output_modes",
        "append_only_terminal_absence", "run_claim_state", "public_privacy",
        "frozen_sources", "exp064_complete", "exp065_complete", "exp066_complete",
        "exp066_cli_open", "exp067_attempt1_failed", "exp067_attempt2_failed",
        "benchmark_incomplete", "decision_rule", "supported_claim_boundary",
        "unsupported_claims", "access_attestation", "synthesis_exact_replay",
    ]
    result = {
        "schema_version": "exp-068-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Passed",
        "verified_at_utc": utc_now(),
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "decision": expected["decision"],
        "access_attestation": expected["access_attestation"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    summary = (
        "# EXP-068 Phase A Synthesis Verification\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(checks)}/{len(checks)}`\n"
        f"- Phase A state: `{result['decision']['state']}`\n"
        "- Verified headless/CLI research demo: `true`\n"
        "- Formal efficiency benchmark complete: `false`\n"
        "- Deployment-efficiency claim supported: `false`\n"
        "- Private/test/model access: `false/false/false`\n\n"
        f"Claim boundary: {CLAIM_BOUNDARY}\n"
    ).encode("utf-8")
    _create(RUN_DIR / "VERIFICATION-SUMMARY.md", summary)
    _create(RUN_DIR / "verification.json", canonical_json(result))
    completion = {
        "schema_version": "exp-068-phase-a-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "run": record(RUN_DIR / "run.json"),
        "synthesis": record(RUN_DIR / "phase-a-synthesis.json"),
        "verification": record(RUN_DIR / "verification.json"),
        "decision": expected["decision"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _create(RUN_DIR / "phase-a-complete.json", canonical_json(completion))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(verify(args.config), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

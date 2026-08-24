#!/usr/bin/env python3
"""Run the read-only EXP-063 prospective router replication synthesis."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import time
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
RUN_ID = "exp-063-router-replication-synthesis"
ATTEMPT_ID = "attempt-1"
NAMESPACE = PROJECT_ROOT / BASE / "runs" / RUN_ID
ATTEMPT = NAMESPACE / ATTEMPT_ID
SELECTION = NAMESPACE / "selected-attempt.json"
SYNTHESIS_PATH = ATTEMPT / "replication-synthesis.json"
RUN_PATH = ATTEMPT / "run.json"
PROTOCOL_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-063-router-replication-synthesis.md"
)
DECISION_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/dec-so-router-replication-v1.md"
)
DISCOVERY = {
    "operating_point": BASE / "runs/exp-060-pre-qwen-router/selected-operating-point.json",
    "verification": BASE / "runs/exp-060-pre-qwen-router/verification.json",
}
PROSPECTIVE = (
    {
        "experiment_id": "EXP-061",
        "model_seed": 43,
        "run_id": "exp-061-seed-43-router-replication",
        "selection": BASE / "runs/exp-061-seed-43-router-replication/selected-attempt.json",
        "operating_point": BASE / (
            "runs/exp-061-seed-43-router-replication/attempt-1/router/"
            "selected-operating-point.json"
        ),
        "bootstrap": BASE / (
            "runs/exp-061-seed-43-router-replication/attempt-1/router/bootstrap.json"
        ),
        "verification": BASE / (
            "runs/exp-061-seed-43-router-replication/attempt-1/router/"
            "verification-attempt-3.json"
        ),
    },
    {
        "experiment_id": "EXP-062",
        "model_seed": 44,
        "run_id": "exp-062-seed-44-router-replication",
        "selection": BASE / "runs/exp-062-seed-44-router-replication/selected-attempt.json",
        "operating_point": BASE / (
            "runs/exp-062-seed-44-router-replication/attempt-1/router/"
            "selected-operating-point.json"
        ),
        "bootstrap": BASE / (
            "runs/exp-062-seed-44-router-replication/attempt-1/router/bootstrap.json"
        ),
        "verification": BASE / (
            "runs/exp-062-seed-44-router-replication/attempt-1/router/verification.json"
        ),
    },
)
LABELS = ("anger", "fear", "joy", "love", "sadness", "surprise")
CLAIM_BOUNDARY = (
    "The frozen pre-Qwen logistic router replicated across two prospective "
    "training seeds on the same DATA-SO-TASK-V1 train data at the meta level; "
    "this is not independent-data validation, deployment benefit, latency, "
    "forum generality, or an emotion-mechanism claim."
)


def _resolve_public(value: Path | str) -> Path:
    relative = Path(value)
    lowered = {part.lower() for part in relative.parts}
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or "private" in lowered
        or "validation" in lowered
        or "test" in lowered
    ):
        raise PermissionError(f"EXP-063 non-public input path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"EXP-063 input traverses symlink: {value}")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"EXP-063 input escapes project root: {value}")
    return path


def _read_public(value: Path | str) -> bytes:
    path = _resolve_public(value)
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise PermissionError(f"EXP-063 public artifact mode/type drift: {value}")
    payload = path.read_bytes()
    after = os.lstat(path)
    if (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise RuntimeError(f"EXP-063 artifact changed while reading: {value}")
    return payload


def artifact(value: Path | str) -> dict[str, Any]:
    relative = Path(value)
    payload = _read_public(relative)
    return {
        "path": str(relative),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def load_json(value: Path | str) -> dict[str, Any]:
    result = json.loads(_read_public(value).decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"EXP-063 expected object: {value}")
    return result


def _vote(spec: dict[str, Any]) -> dict[str, Any]:
    selection = load_json(spec["selection"])
    point = load_json(spec["operating_point"])
    bootstrap = load_json(spec["bootstrap"])
    verification = load_json(spec["verification"])
    if (
        selection.get("experiment_id") != spec["experiment_id"]
        or selection.get("run_id") != spec["run_id"]
        or selection.get("attempt_id") != ATTEMPT_ID
        or selection.get("model_seed") != spec["model_seed"]
        or selection.get("status") != "Selected"
        or selection.get("primary_policy") != "logistic_router"
        or selection.get("primary_nominal_call_rate") != 0.15
        or type(selection.get("primary_gate_passed")) is not bool
        or selection.get("decision")
        != ("Pass" if selection["primary_gate_passed"] else "Fail")
    ):
        raise ValueError(f"EXP-063 selection identity/gate drift: {spec['experiment_id']}")
    if (
        point.get("experiment_id") != spec["experiment_id"]
        or point.get("run_id") != spec["run_id"]
        or point.get("attempt_id") != ATTEMPT_ID
        or point.get("model_seed") != spec["model_seed"]
        or point.get("primary_policy") != "logistic_router"
        or point.get("primary_nominal_call_rate") != 0.15
        or point.get("overall", {}).get("selected_policy") != "logistic_router"
    ):
        raise ValueError(f"EXP-063 operating-point drift: {spec['experiment_id']}")
    policy = point.get("policies", {}).get("logistic_router")
    candidate = point.get("overall", {}).get("selected_candidate")
    baseline = point.get("baseline")
    if (
        not isinstance(policy, dict)
        or not isinstance(candidate, dict)
        or not isinstance(baseline, dict)
        or policy.get("candidate") != candidate
        or policy.get("passed") is not selection["primary_gate_passed"]
        or point["overall"].get("decision") != selection["decision"]
        or set(policy.get("gates", {}))
        != {
            "hamming_loss_not_worse",
            "maximum_actual_qwen_call_rate",
            "minimum_five_label_macro_f1_gain",
            "minimum_non_surprise_label_f1_gain",
            "minimum_six_label_macro_f1_gain",
        }
    ):
        raise ValueError(f"EXP-063 primary policy drift: {spec['experiment_id']}")
    if (
        verification.get("status") != "Passed"
        or type(verification.get("failed_count")) is not int
        or verification["failed_count"] != 0
        or type(verification.get("passed_count")) is not int
        or verification["passed_count"] <= 0
    ):
        raise ValueError(f"EXP-063 verifier status drift: {spec['experiment_id']}")
    intervals = bootstrap.get("policy_candidates", {}).get("logistic_router")
    if (
        bootstrap.get("repetitions") != 2000
        or bootstrap.get("overall_selected_policy") != "logistic_router"
        or not isinstance(intervals, dict)
        or intervals.get("target_call_rate") != 0.15
        or intervals.get("actual_call_rate") != candidate.get("actual_call_rate")
    ):
        raise ValueError(f"EXP-063 bootstrap drift: {spec['experiment_id']}")
    per_label = {
        label: candidate[f"f1_{label}"] - baseline["per_label"][label]["f1"]
        for label in LABELS
    }
    return {
        "experiment_id": spec["experiment_id"],
        "model_seed": spec["model_seed"],
        "run_id": spec["run_id"],
        "attempt_id": ATTEMPT_ID,
        "verification_status": "Passed",
        "verification_passed_count": verification["passed_count"],
        "primary_policy": "logistic_router",
        "primary_nominal_call_rate": 0.15,
        "primary_gate_passed": selection["primary_gate_passed"],
        "gate_decision": selection["decision"],
        "actual_call_rate": candidate["actual_call_rate"],
        "six_label_macro_f1_gain": candidate["six_label_macro_f1_gain"],
        "five_label_macro_f1_gain": candidate["five_label_macro_f1_gain"],
        "hamming_loss_delta": candidate["hamming_loss_delta"],
        "maximum_non_surprise_label_f1_gain": candidate[
            "maximum_non_surprise_label_f1_gain"
        ],
        "per_label_f1_delta": per_label,
        "gain_driven_only_by_surprise": (
            per_label["surprise"] > 0
            and max(per_label[label] for label in LABELS if label != "surprise") <= 0
        ),
        "gate_checks": policy["gates"],
        "bootstrap_95": intervals["intervals"],
        "source_artifacts": {
            "selection": artifact(spec["selection"]),
            "operating_point": artifact(spec["operating_point"]),
            "bootstrap": artifact(spec["bootstrap"]),
            "verification": artifact(spec["verification"]),
        },
    }


def compute_synthesis() -> dict[str, Any]:
    discovery_point = load_json(DISCOVERY["operating_point"])
    discovery_verification = load_json(DISCOVERY["verification"])
    if discovery_verification.get("status") != "Passed":
        raise ValueError("EXP-063 discovery background is not verified")
    votes = [_vote(spec) for spec in PROSPECTIVE]
    if [vote["model_seed"] for vote in votes] != [43, 44]:
        raise ValueError("EXP-063 prospective vote order/cardinality drift")
    pass_count = sum(int(vote["primary_gate_passed"]) for vote in votes)
    if pass_count == 2:
        result = "2/2 pass"
        system_decision = "promote_same_train_cross_seed_meta_replication"
    elif pass_count == 1:
        result = "1/2 pass"
        system_decision = "seed_sensitive_do_not_promote"
    else:
        result = "0/2 pass"
        system_decision = "seed42_discovery_not_prospectively_replicated"
    return {
        "schema_version": "exp-063-router-replication-synthesis-v1",
        "experiment_id": "EXP-063",
        "rq_id": "RQ-S3",
        "decision_id": "DEC-SO-ROUTER-REPLICATION-V1",
        "attempt_id": ATTEMPT_ID,
        "status": "CompletedAwaitingVerification",
        "data_contract": "DATA-SO-TASK-V1-train",
        "discovery_background": {
            "experiment_id": discovery_point.get("experiment_id", "EXP-060"),
            "vote_eligible": False,
            "decision": discovery_point.get("overall", {}).get("decision"),
            "source_artifacts": {
                "operating_point": artifact(DISCOVERY["operating_point"]),
                "verification": artifact(DISCOVERY["verification"]),
            },
        },
        "prospective_inputs": [
            {"experiment_id": row["experiment_id"], "model_seed": row["model_seed"]}
            for row in PROSPECTIVE
        ],
        "votes": votes,
        "decision": {
            "pass_count": pass_count,
            "eligible_seed_count": 2,
            "result": result,
            "system_decision": system_decision,
        },
        "input_artifacts": {
            "decision_protocol": artifact(DECISION_REL),
            "synthesis_protocol": artifact(PROTOCOL_REL),
            "seed43_selection": artifact(PROSPECTIVE[0]["selection"]),
            "seed44_selection": artifact(PROSPECTIVE[1]["selection"]),
        },
        "execution_claims": {
            "aggregate_public_only": True,
            "private_accessed": False,
            "row_level_accessed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "model_loaded_or_forward_run": False,
            "threshold_or_router_refit": False,
        },
        "resources": {
            "api_cost_usd": 0,
            "gpu_cost_usd": 0,
            "model_forward_runs": 0,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _create_json_once(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        os.write(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def execute() -> dict[str, Any]:
    started = time.monotonic()
    if os.path.lexists(NAMESPACE) or os.path.lexists(SELECTION):
        raise FileExistsError("EXP-063 namespace or selection already exists")
    synthesis = compute_synthesis()
    NAMESPACE.mkdir(mode=0o755)
    ATTEMPT.mkdir(mode=0o755)
    _create_json_once(SYNTHESIS_PATH, synthesis)
    resources = {
        "wall_seconds": time.monotonic() - started,
        "peak_process_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9,
        "api_cost_usd": 0,
        "gpu_cost_usd": 0,
        "model_forward_runs": 0,
    }
    run = {
        "schema_version": "exp-063-router-replication-run-v1",
        "experiment_id": "EXP-063",
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "CompletedAwaitingVerification",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": synthesis["decision"],
        "input_artifacts": synthesis["input_artifacts"],
        "output": artifact(SYNTHESIS_PATH.relative_to(PROJECT_ROOT)),
        "resources": resources,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _create_json_once(RUN_PATH, run)
    return run


def main() -> None:
    run = execute()
    print(json.dumps({"decision": run["decision"]["result"], "status": run["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()


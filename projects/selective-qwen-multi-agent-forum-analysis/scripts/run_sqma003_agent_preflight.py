#!/usr/bin/env python3
"""Run the classifier-free SQMA-003 Agent-Dev capability preflight."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import resource
import stat
import sys
import time
from typing import Any, Iterable


sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-003-classifier-free-agent-preflight.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
SHA_RE = __import__("re").compile(r"[0-9a-f]{64}\Z")
OUTPUT_CONTRACTS = {
    "evidence_appraisal": (
        'Return exactly: {"schema_version":"evidence-appraisal-v2",'
        '"candidate_emotions":[],"evidence_spans":[],"expression_type":"explicit|implicit|mixed|none|unclear",'
        '"insufficient_evidence":true,"appraisal":{"goal_obstruction":"present|absent|unclear",'
        '"responsibility":"self|other|shared|situational|none|unclear","control":"high|low|mixed|unclear",'
        '"certainty":"high|low|mixed|unclear","expectation_violation":"present|absent|unclear",'
        '"loss_or_threat":"loss|threat|both|none|unclear"}}. Replace enum alternatives with one value.'
    ),
    "pragmatics_critic": (
        'Return exactly: {"schema_version":"pragmatics-critic-v2","reading":"emotion|technical_stance|mixed|unclear",'
        '"negation":"none|relevant|unclear","sarcasm":"unlikely|possible|likely|unclear",'
        '"emotion_evidence":"sufficient|weak|absent|unclear","recommended_emotions":[],"challenged_emotions":[],'
        '"warning_flags":[]}. Replace enum alternatives with one value.'
    ),
    "judge": (
        'Return exactly: {"schema_version":"judge-v2","action":"decide_labels|abstain",'
        '"emotions":[],"evidence_refs":[],"reason_flags":[]}. Replace action alternatives with one value.'
    ),
    "single_agent": (
        'Return exactly one {"schema_version":"single-agent-v2","evidence_appraisal":<EvidenceAppraisal>,'
        '"pragmatics":<PragmaticsCritic>,"decision":<Judge>} object using the same field contracts.'
    ),
}


class PreflightError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PreflightError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), "relative path required")
    path = (root / relative).resolve()
    require(path == root.resolve() or root.resolve() in path.parents, "path escapes root")
    return path


def regular(path: Path, *, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), "required file missing")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), "file type drift")
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, "file mode drift")
    return observed


def read_json(path: Path) -> dict[str, Any]:
    regular(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON root drift")
    return value


def artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve().relative_to(REPO_ROOT)), "bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_record(record: dict[str, Any]) -> Path:
    require(set(record) >= {"path", "bytes", "sha256"}, "artifact schema drift")
    require(type(record["bytes"]) is int and record["bytes"] > 0, "artifact bytes drift")
    require(isinstance(record["sha256"], str) and SHA_RE.fullmatch(record["sha256"]), "artifact hash drift")
    path = checked_path(REPO_ROOT, record["path"])
    observed = regular(path)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "artifact identity drift")
    return path


def load_module(name: str, record: dict[str, Any]) -> Any:
    path = verify_record(record)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "module spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def seed_for(namespace: str, system_id: str, sample_id: str, role: str, call_index: int) -> int:
    material = f"{namespace}|{system_id}|{sample_id}|{role}|{call_index}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big", signed=False)


def component_rank(namespace: str, component_id: str) -> str:
    return hashlib.sha256(f"{namespace}|{component_id}".encode()).hexdigest()


def select_rows(rows: Iterable[dict[str, Any]], namespace: str) -> list[dict[str, Any]]:
    by_component: dict[str, dict[str, Any]] = {}
    for row in rows:
        require(set(row) == {"schema_version", "protocol_id", "sample_id", "component_id", "fold_id", "source_ordinal", "text"}, "input schema drift")
        require(row["schema_version"] == "sqma-gold-free-inference-snapshot-v1", "input identity drift")
        prior = by_component.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]:
            by_component[row["component_id"]] = row
    require(len(by_component) == 1963, "Agent-Dev component count drift")
    selected = sorted(by_component.values(), key=lambda row: component_rank(namespace, row["component_id"]))[:32]
    for index, row in enumerate(selected):
        row["selection_rank"] = index
        row["selection_stratum"] = "shakedown" if index < 8 else "locked"
    return selected


def read_inputs(config: dict[str, Any]) -> list[dict[str, Any]]:
    root = checked_path(REPO_ROOT, config["inputs"]["private_root"])
    rows: list[dict[str, Any]] = []
    for record in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(root, record["path"])
        observed = regular(path, mode="0600")
        require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "input identity drift")
        with path.open("r", encoding="utf-8") as source:
            values = [json.loads(line) for line in source]
        require(len(values) == record["rows"], "input row count drift")
        rows.extend(values)
    return rows


def fallback_evidence() -> dict[str, Any]:
    return {
        "schema_version": "evidence-appraisal-v2",
        "candidate_emotions": [],
        "evidence_spans": [],
        "expression_type": "unclear",
        "insufficient_evidence": True,
        "appraisal": {
            "goal_obstruction": "unclear", "responsibility": "unclear", "control": "unclear",
            "certainty": "unclear", "expectation_violation": "unclear", "loss_or_threat": "unclear",
        },
    }


def fallback_critic() -> dict[str, Any]:
    return {
        "schema_version": "pragmatics-critic-v2", "reading": "unclear", "negation": "unclear",
        "sarcasm": "unclear", "emotion_evidence": "unclear", "recommended_emotions": [],
        "challenged_emotions": [], "warning_flags": [],
    }


def render_prompt(tokenizer: Any, bundle: dict[str, Any], role: str, context: dict[str, Any]) -> list[int]:
    role_spec = bundle["roles"][role]
    require(set(context) == set(role_spec["visible_fields"]), "role context allowlist drift")
    output_contract = OUTPUT_CONTRACTS[role]
    if role == "single_agent":
        output_contract += "\nNested contracts:\n" + "\n".join(
            OUTPUT_CONTRACTS[name] for name in ("evidence_appraisal", "pragmatics_critic", "judge")
        )
    system = "\n".join(bundle["shared_rules"] + [role_spec["system"], output_contract])
    user = "Input JSON:\n" + json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    ids = tokenizer.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if isinstance(ids, dict):
        ids = ids["input_ids"]
    ids = list(ids)
    require(len(ids) <= 4096, "constructed prompt exceeds context cap")
    return ids


def truncate_analysis_text(tokenizer: Any, text: str, cap: int) -> tuple[str, dict[str, Any]]:
    ids = list(tokenizer.encode(text, add_special_tokens=False))
    if len(ids) <= cap:
        return text, {"original_tokens": len(ids), "analysis_tokens": len(ids), "was_truncated": False}
    shortened = tokenizer.decode(ids[:cap], skip_special_tokens=True)
    return shortened, {"original_tokens": len(ids), "analysis_tokens": cap, "was_truncated": True}


def numeric_summary(values: list[float]) -> dict[str, float]:
    require(values, "empty numeric summary")
    ordered = sorted(values)
    def q(p: float) -> float:
        return ordered[min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)]
    return {"min": ordered[0], "median": q(0.5), "p95": q(0.95), "max": ordered[-1], "mean": sum(ordered) / len(ordered)}


def atomic_json(path: Path, value: Any, mode: int) -> None:
    tmp = path.with_name(path.name + ".tmp")
    require(not os.path.lexists(tmp), "temporary output exists")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    tmp.replace(path)
    os.chmod(path, mode)


def atomic_jsonl(path: Path, rows: list[dict[str, Any]], mode: int) -> None:
    tmp = path.with_name(path.name + ".tmp")
    require(not os.path.lexists(tmp), "temporary output exists")
    with tmp.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    os.chmod(tmp, mode)
    tmp.replace(path)
    os.chmod(path, mode)


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * p) - 1))]


def run(config_arg: str) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = utc_now()
    supplied = Path(config_arg).resolve()
    require(supplied == CONFIG_PATH.resolve(), "noncanonical config path")
    config = read_json(supplied)
    for section in ("implementation", "prerequisites"):
        for record in config[section].values():
            verify_record(record)
    require(config["authorization"]["gold_access"] is False and config["authorization"]["model_training"] is False, "authorization drift")
    require(config["model"]["adapter"] is None, "adapter drift")
    bundle = read_json(verify_record(config["implementation"]["prompt_bundle"]))
    validator = load_module("sqma003_validator_v2", config["implementation"]["validator"])
    rows = read_inputs(config)
    selected = select_rows(rows, config["selection"]["namespace"])

    public_dir = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"])
    private_dir = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"])
    require(not os.path.lexists(public_dir) and not os.path.lexists(private_dir), "output target exists")
    require(__import__("shutil").disk_usage(REPO_ROOT).free >= config["resources"]["minimum_free_disk_bytes"], "insufficient disk")
    public_dir.mkdir(parents=True, mode=0o755)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    claim = {
        "schema_version": "sqma-003-run-claim-v1", "experiment_id": "SQMA-003",
        "status": "ClaimedBeforeModelLoad", "config": artifact(supplied),
        "classifier_free": True, "gold_access": False, "model_training": False,
        "planned_calls": config["call_plan"]["physical_call_cap"],
    }
    atomic_json(public_dir / "run-claim.json", claim, 0o644)

    selection_private = {
        "schema_version": "sqma-003-selection-v1", "namespace": config["selection"]["namespace"],
        "rows": [
            {key: row[key] for key in ("selection_rank", "selection_stratum", "sample_id", "component_id", "fold_id", "source_ordinal")}
            for row in selected
        ],
    }
    atomic_json(private_dir / "selection.json", selection_private, 0o600)

    archive_root = Path(os.environ.get(config["model"]["archive_root_env"], config["model"]["audited_archive_root"])).resolve()
    model_path = checked_path(archive_root, config["model"]["relative_path"])
    manifest = checked_path(archive_root, config["model"]["manifest_path"])
    require(sha256(manifest) == config["model"]["manifest_sha256"], "model manifest drift")
    require(Path(sys.executable).resolve() == Path(config["runtime"]["executable"]).resolve(), "runtime executable drift")

    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    mx.reset_peak_memory()
    load_started = time.perf_counter()
    model, tokenizer = load(str(model_path), lazy=False)
    model_load_seconds = time.perf_counter() - load_started
    sampler = make_sampler(temp=0.6, top_p=0.95, top_k=20)
    ontology = {"label_order": list(LABEL_ORDER), "instruction": bundle["ontology"]["instruction"]}
    calls: list[dict[str, Any]] = []
    fallback_rows: set[int] = set()

    def generate_call(row: dict[str, Any], system_id: str, role: str, call_index: int, context: dict[str, Any]) -> tuple[str, dict[str, Any] | None, str | None]:
        analysis_text, text_meta = truncate_analysis_text(tokenizer, row["text"], config["generation"]["analysis_text_token_cap"])
        local_context = dict(context)
        local_context["analysis_text"] = analysis_text
        local_context["ontology"] = ontology
        prompt_ids = render_prompt(tokenizer, bundle, role, local_context)
        seed = seed_for(config["generation"]["seed_namespace"], system_id, row["sample_id"], role, call_index)
        mx.random.seed(seed)
        responses = []
        call_started = time.perf_counter()
        for response in stream_generate(model, tokenizer, prompt_ids, max_tokens=config["generation"]["max_new_tokens"][role], sampler=sampler):
            responses.append(response)
        latency = time.perf_counter() - call_started
        raw = "".join(response.text for response in responses)
        last = responses[-1]
        parsed = None
        error = None
        try:
            parsed = validator.validate_output(role, raw, local_context)
        except validator.AgentOutputError as exc:
            error = exc.code
        final_labels = validator.final_labels_from_validated(role, parsed) if parsed is not None and role in {"judge", "single_agent"} else []
        record = {
            "selection_rank": row["selection_rank"], "selection_stratum": row["selection_stratum"],
            "sample_id": row["sample_id"], "component_id": row["component_id"], "source_ordinal": row["source_ordinal"],
            "system_id": system_id, "role": role, "call_index": call_index, "seed": seed,
            "prompt_sha256": canonical_digest(prompt_ids), "prefill_tokens": len(prompt_ids),
            "generated_tokens": int(last.generation_tokens), "finish_reason": last.finish_reason,
            "latency_seconds": latency, "peak_memory_gb": float(last.peak_memory),
            "raw_output": raw, "parsed_output": parsed, "validation_error": error,
            "final_labels": final_labels, "text_meta": text_meta,
        }
        calls.append(record)
        return raw, parsed, error

    for row in selected:
        base_context: dict[str, Any] = {}
        _, evidence, evidence_error = generate_call(row, "S3", "evidence_appraisal", 0, base_context)
        evidence_context = evidence if evidence is not None else fallback_evidence()
        _, critic, critic_error = generate_call(row, "S3", "pragmatics_critic", 1, {"evidence_appraisal": evidence_context})
        critic_context = critic if critic is not None else fallback_critic()
        _, _, judge_error = generate_call(
            row, "S3", "judge", 2,
            {"evidence_appraisal": evidence_context, "pragmatics_critic": critic_context},
        )
        if evidence_error or critic_error or judge_error:
            fallback_rows.add(row["selection_rank"])

    single_rows = [row for row in selected if 8 <= row["selection_rank"] <= 15]
    for system_id in ("single_pool", "provisional_s2b"):
        for row in single_rows:
            for call_index in range(3):
                generate_call(row, system_id, "single_agent", call_index, {})

    require(len(calls) == config["call_plan"]["physical_call_cap"], "physical call count drift")
    require(
        sum(call["generated_tokens"] for call in calls)
        <= config["resources"]["maximum_generated_tokens"],
        "generated-token budget exceeded",
    )
    atomic_jsonl(private_dir / "calls.jsonl", calls, 0o600)
    private_manifest = {
        "schema_version": "sqma-003-private-manifest-v1", "calls": len(calls),
        "selection": artifact(private_dir / "selection.json"), "calls_artifact": artifact(private_dir / "calls.jsonl"),
        "input_snapshot_sha256": [record["sha256"] for record in config["inputs"]["gold_free_snapshots"]],
        "gold_accessed": False, "classifier_fields_present": False,
    }
    atomic_json(private_dir / "private-manifest.json", private_manifest, 0o600)
    private_bytes = sum(path.stat().st_size for path in private_dir.iterdir() if path.is_file())
    require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private output budget exceeded")

    locked_calls = [call for call in calls if call["selection_stratum"] == "locked"]
    valid_rate = sum(call["validation_error"] is None for call in locked_calls) / len(locked_calls)
    per_role = {}
    for role in ("evidence_appraisal", "pragmatics_critic", "judge", "single_agent"):
        subset = [call for call in locked_calls if call["role"] == role]
        per_role[role] = sum(call["validation_error"] is None for call in subset) / len(subset) if subset else 1.0
    cap_hits = sum(call["finish_reason"] == "length" for call in calls)
    stability_values = []
    for row in single_rows:
        subset = [call for call in calls if call["system_id"] == "single_pool" and call["selection_rank"] == row["selection_rank"]]
        counts = Counter(tuple(call["final_labels"]) for call in subset)
        stability_values.append(max(counts.values()) / 3)
    stability = sum(stability_values) / len(stability_values)
    latencies_by_role = {
        role: numeric_summary([call["latency_seconds"] for call in calls if call["role"] == role])
        for role in ("evidence_appraisal", "pragmatics_critic", "judge", "single_agent")
    }
    tokens_by_role = {
        role: {
            "prefill": numeric_summary([float(call["prefill_tokens"]) for call in calls if call["role"] == role]),
            "generated": numeric_summary([float(call["generated_tokens"]) for call in calls if call["role"] == role]),
        }
        for role in ("evidence_appraisal", "pragmatics_critic", "judge", "single_agent")
    }
    projected = 1.25 * 672 * (
        latencies_by_role["evidence_appraisal"]["p95"] + latencies_by_role["pragmatics_critic"]["p95"]
        + latencies_by_role["judge"]["p95"] + 3 * latencies_by_role["single_agent"]["p95"]
    ) + model_load_seconds
    gate = {
        "planned_calls_complete": len(calls) == 144,
        "raw_schema_valid_rate": valid_rate,
        "per_role_valid_rate": per_role,
        "technical_fallback_rows": len([rank for rank in fallback_rows if rank >= 8]),
        "token_cap_hits": cap_hits,
        "mean_modal_exact_label_set_agreement": stability,
        "full_tune_projected_wall_seconds": projected,
    }
    gate_passed = (
        valid_rate >= config["pass_gate"]["raw_schema_valid_rate_overall_minimum"]
        and all(value >= config["pass_gate"]["raw_schema_valid_rate_per_role_minimum"] for value in per_role.values())
        and gate["technical_fallback_rows"] <= config["pass_gate"]["maximum_locked_S3_technical_fallback_rows"]
        and cap_hits == 0 and stability >= config["pass_gate"]["mean_modal_exact_label_set_agreement_minimum"]
        and projected <= config["resources"]["maximum_full_tune_projected_wall_seconds"]
    )
    elapsed = time.perf_counter() - started
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform.startswith("linux"):
        rss *= 1024
    mlx_peak = int(mx.get_peak_memory())
    require(elapsed <= config["resources"]["maximum_wall_seconds"], "wall cap exceeded")
    require(rss <= config["resources"]["maximum_process_rss_bytes"], "RSS cap exceeded")
    require(mlx_peak <= config["resources"]["maximum_mlx_peak_bytes"], "MLX cap exceeded")

    run_payload = {
        "schema_version": "sqma-003-run-v1", "experiment_id": "SQMA-003", "tier": "Minor",
        "stage": config["stage"], "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at, "completed_at_utc": utc_now(), "config": artifact(supplied),
        "classifier_free": True, "selection": {"components": 32, "shakedown": 8, "locked": 24, "selection_sha256": sha256(private_dir / "selection.json")},
        "calls": {"physical": len(calls), "by_role": dict(Counter(call["role"] for call in calls))},
        "gate": gate, "gate_passed": gate_passed, "latency_seconds": latencies_by_role,
        "tokens": tokens_by_role,
        "resources": {"wall_seconds": elapsed, "model_load_seconds": model_load_seconds, "peak_rss_bytes": rss, "mlx_peak_bytes": mlx_peak, "private_output_bytes": private_bytes},
        "access": {"gold_accessed": False, "classifier_outputs_accessed": False, "adapter_loaded": False, "model_training": False, "network_accessed": False, "fold3_accessed": False, "fold4_accessed": False, "validation_accessed": False, "test_accessed": False},
        "next_gate": "independent_preflight_verification" if gate_passed else "stop_capability_gate_failed",
    }
    atomic_json(public_dir / "run.json", run_payload, 0o644)
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = run(args.config)
    print(json.dumps({"experiment_id": "SQMA-003", "status": result["status"], "gate_passed": result["gate_passed"], "next_gate": result["next_gate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, PreflightError) as exc:
        print(f"SQMA-003 preflight Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

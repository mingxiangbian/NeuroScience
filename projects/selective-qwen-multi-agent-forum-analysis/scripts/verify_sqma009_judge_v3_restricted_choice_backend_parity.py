#!/usr/bin/env python3
"""Independent model-free verifier contracts for SQMA-009."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-009-judge-v3-restricted-choice-backend-parity.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
GENERATION_NAMESPACE = "SQMA-009-judge-v3-restricted-choice-v1"
PRIVATE_ALLOWED = ["token-seal.json", "calls.jsonl", "assemblies.jsonl", "private-manifest.json"]
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text", "candidate_mapping", "component_id", "component_ids",
    "evidence", "critic", "ordinary_v2_labels", "option_mapping", "raw_output",
    "response_token", "sample_id", "sample_ids", "selected_evidence_id",
    "selected_symbol", "target_label", "text",
}
CALL_FIELDS = {
    "schema_version", "call_ordinal", "row_ordinal", "selection_rank",
    "sample_id", "component_id", "source_ordinal", "target_label", "seed",
    "analysis_text_sha256", "context_sha256", "messages_sha256",
    "prompt_ids_sha256", "candidate_mapping", "allowed_token_ids",
    "processor_instance_id", "processor_invocations", "response_count",
    "response_token", "generated_tokens", "finish_reason", "generated_text_sha256",
    "selected_symbol", "selected_evidence_id", "terminal_valid",
    "selected_token_allowed", "selected_eos_token", "post_mask_valid",
    "prefill_tokens", "latency_seconds", "mlx_peak_bytes",
}
ASSEMBLY_FIELDS = {
    "schema_version", "row_ordinal", "selection_rank", "sample_id", "component_id",
    "source_ordinal", "allowed_evidence_ids", "v3_slots", "v3_labels",
    "ordinary_v2_labels", "exact_label_set_parity", "per_label_parity",
    "assembly_diagnostics",
}
FALLBACK_EVIDENCE = {"schema_version": "evidence-v3", "candidate_emotions": [], "evidence_spans": [], "insufficient_evidence": True}
FALLBACK_CRITIC = {"schema_version": "critic-v3", "recommended_emotions": [], "challenged_emotions": [], "warning_flags": []}


class SQMA009VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SQMA009VerificationError(message)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def seed_for(sample_id: str, target_label: str) -> int:
    value = f"{GENERATION_NAMESPACE}|{sample_id}|{target_label}".encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:4], "big", signed=False)


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping): return any(contains_placeholder(child) for child in value.values())
    if isinstance(value, (list, tuple)): return any(contains_placeholder(child) for child in value)
    return isinstance(value, str) and value.startswith("PLACEHOLDER_")


def validate_static_config(config: Mapping[str, Any]) -> dict[str, Any]:
    require(config.get("schema_version") == "sqma-009-judge-v3-restricted-choice-backend-parity-v1" and config.get("experiment_id") == "SQMA-009", "config identity drift")
    require(config.get("design_status") in {"StaticDesignAwaitingImplementation", "FrozenReady"}, "design status drift")
    if config.get("design_status") == "FrozenReady":
        require(config.get("authorization", {}).get("execution_authorized") is True and not contains_placeholder(config), "ready profile drift")
    else:
        require(all(value is False for value in config.get("authorization", {}).values()), "static authorization drift")
    require(config.get("outputs", {}).get("private_allowed_files") == PRIVATE_ALLOWED, "private inventory drift")
    require(config.get("generation", {}).get("physical_calls") == 96, "call plan drift")
    return {"schema_version": "sqma-009-static-verification-v1", "experiment_id": "SQMA-009", "status": "Passed", "execution_authorized": config["authorization"]["execution_authorized"], "private_accessed": False, "model_loaded": False, "model_logits_recomputed": False, "next_gate": config.get("next_gate")}


def c1_call_groups(calls: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    require(len(calls) == 48, "C1 call count drift")
    groups = [list(calls[index : index + 3]) for index in range(0, 48, 3)]
    for rank, group in enumerate(groups):
        require([call.get("role") for call in group] == ["evidence", "critic", "judge"] and all(call.get("selection_rank") == rank for call in group), "C1 schedule drift")
    return groups


def replay_c1_rows(selection: Mapping[str, Any], calls: Sequence[Mapping[str, Any]], validator_v4: Any) -> list[dict[str, Any]]:
    rows = selection.get("rows"); require(isinstance(rows, list) and len(rows) == 16, "C1 selection drift")
    output = []
    for ordinal, (selected, group) in enumerate(zip(rows, c1_call_groups(calls), strict=True)):
        evidence_call, critic_call, judge_call = group; analysis = evidence_call.get("analysis_text"); require(isinstance(analysis, str) and all(call.get("analysis_text") == analysis for call in group), "C1 analysis drift")
        base = {"analysis_text": analysis, "ontology": validator_v4.ONTOLOGY}
        try: evidence = validator_v4.validate_evidence(evidence_call["raw_output"], base)
        except validator_v4.AgentOutputError: evidence = FALLBACK_EVIDENCE
        try: critic = validator_v4.validate_critic(critic_call["raw_output"], {**base, "evidence": evidence})
        except validator_v4.AgentOutputError: critic = FALLBACK_CRITIC
        allowed = list(range(len(evidence["evidence_spans"]))); judge = validator_v4.judge_contract_result(judge_call["raw_output"], {**base, "evidence": evidence, "critic": critic, "allowed_evidence_ids": allowed}); require(judge["rendered_contract_valid"] is True, "C1 Judge drift")
        output.append({"row_ordinal": ordinal, "selection_rank": selected["selection_rank"], "sample_id": selected["sample_id"], "component_id": selected["component_id"], "source_ordinal": selected["source_ordinal"], "analysis_text": analysis, "evidence": evidence, "critic": critic, "allowed_evidence_ids": allowed, "ordinary_v2_labels": list(judge["derived_labels"])})
    return output


def planned_calls(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(rows) == 16, "row count drift")
    return [{"call_ordinal": ordinal * 6 + index, "row_ordinal": ordinal, "selection_rank": row["selection_rank"], "sample_id": row["sample_id"], "component_id": row["component_id"], "source_ordinal": row["source_ordinal"], "target_label": label, "seed": seed_for(row["sample_id"], label)} for ordinal, row in enumerate(rows) for index, label in enumerate(LABEL_ORDER)]


def judge_context(row: Mapping[str, Any], label: str, mapping: Sequence[Mapping[str, Any]], ontology: Mapping[str, Any]) -> dict[str, Any]:
    return {"analysis_text": row["analysis_text"], "ontology": dict(ontology), "evidence": row["evidence"], "critic": row["critic"], "target_label": label, "allowed_evidence_ids": row["allowed_evidence_ids"], "option_mapping": list(mapping)}


def validate_calls(calls: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], seal: Mapping[str, Any], validator: Any) -> None:
    validator.validate_token_seal(seal); plan = planned_calls(rows); require(len(calls) == len(plan) == 96, "call count drift"); processors = set()
    for call, expected in zip(calls, plan, strict=True):
        require(isinstance(call, Mapping) and set(call) == CALL_FIELDS and all(call[key] == value for key, value in expected.items()), "call schema/plan drift")
        row = rows[call["row_ordinal"]]; mapping = validator.build_candidate_mapping(row["allowed_evidence_ids"], seal); context = judge_context(row, call["target_label"], mapping, validator.ONTOLOGY)
        require(call["analysis_text_sha256"] == text_sha256(row["analysis_text"]) and call["context_sha256"] == canonical_digest(context), "call context drift")
        require(call["candidate_mapping"] == mapping and call["allowed_token_ids"] == [item["token_id"] for item in mapping], "mapping drift")
        terminal = {"response_count": call["response_count"], "token": call["response_token"], "generation_tokens": call["generated_tokens"], "finish_reason": call["finish_reason"]}; validator.validate_generation_terminal(terminal, mapping); choice = validator.choice_from_terminal(terminal, mapping)
        require(call["selected_symbol"] == choice["symbol"] and call["selected_evidence_id"] == choice["evidence_id"] and call["terminal_valid"] is True, "selected token drift")
        require(call["selected_token_allowed"] is True and call["selected_eos_token"] is False and call["post_mask_valid"] is True, "mask/token diagnostic drift")
        require(type(call["processor_invocations"]) is int and call["processor_invocations"] >= 1 and call["processor_instance_id"] not in processors, "processor drift"); processors.add(call["processor_instance_id"])


def verify_assemblies(assemblies: Sequence[Mapping[str, Any]], calls: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], seal: Mapping[str, Any], validator: Any) -> None:
    require(len(assemblies) == 16, "assembly count drift")
    for ordinal, (assembly, row) in enumerate(zip(assemblies, rows, strict=True)):
        require(isinstance(assembly, Mapping) and set(assembly) == ASSEMBLY_FIELDS, "assembly schema drift"); group = calls[ordinal * 6 : ordinal * 6 + 6]
        terminals = {call["target_label"]: {"response_count": call["response_count"], "token": call["response_token"], "generation_tokens": call["generated_tokens"], "finish_reason": call["finish_reason"]} for call in group}; expected = validator.assemble_judge_slots(terminals, allowed_evidence_ids=row["allowed_evidence_ids"], token_seal=seal); labels = list(expected["derived_labels"]); ordinary = list(row["ordinary_v2_labels"])
        require(assembly["row_ordinal"] == ordinal and assembly["sample_id"] == row["sample_id"] and assembly["v3_slots"] == expected["per_label_refs"] and assembly["v3_labels"] == labels and assembly["ordinary_v2_labels"] == ordinary, "assembly replay drift")
        require(assembly["exact_label_set_parity"] is (labels == ordinary) and assembly["per_label_parity"] == {label: (label in labels) == (label in ordinary) for label in LABEL_ORDER}, "parity replay drift")


def technical_metrics(calls: Sequence[Mapping[str, Any]], assemblies: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    latency = [float(call["latency_seconds"]) for call in calls]; prefill = [int(call["prefill_tokens"]) for call in calls]
    return {
        "calls": len(calls), "assemblies": len(assemblies),
        "terminal_valid_calls": sum(call["terminal_valid"] is True for call in calls),
        "response_count_one": sum(call["response_count"] == 1 for call in calls),
        "generation_tokens_one": sum(call["generated_tokens"] == 1 for call in calls),
        "finish_reason_length": sum(call["finish_reason"] == "length" for call in calls),
        "processor_invocations_total": sum(call["processor_invocations"] for call in calls),
        "processor_invocations_minimum": min(call["processor_invocations"] for call in calls),
        "unique_processor_instances": len({call["processor_instance_id"] for call in calls}),
        "assembly_valid": sum(assembly["assembly_diagnostics"]["illegal_reference_ids_constructed"] == 0 for assembly in assemblies),
        "selected_token_escape": sum(call["selected_token_allowed"] is not True for call in calls),
        "selected_eos_tokens": sum(call["selected_eos_token"] is True for call in calls),
        "post_mask_dead_end_or_nonfinite": sum(call["post_mask_valid"] is not True for call in calls),
        "semantic_repair_events": sum(assembly["assembly_diagnostics"]["semantic_repair_events"] for assembly in assemblies),
        "unhandled_failures": 0,
        "latency_seconds": {"mean": sum(latency) / len(latency), "max": max(latency)},
        "prefill_tokens": {"mean": sum(prefill) / len(prefill), "max": max(prefill)},
        "mlx_peak_bytes": max(call["mlx_peak_bytes"] for call in calls),
        "v2_v3_exact_label_set_parity_report_only": sum(assembly["exact_label_set_parity"] for assembly in assemblies) / 16,
        "v2_v3_per_label_parity_report_only": {label: sum(assembly["per_label_parity"][label] for assembly in assemblies) / 16 for label in LABEL_ORDER},
    }


def technical_gate(metrics: Mapping[str, Any]) -> bool:
    return metrics["calls"] == 96 and metrics["assemblies"] == 16 and metrics["terminal_valid_calls"] == 96 and metrics["response_count_one"] == 96 and metrics["generation_tokens_one"] == 96 and metrics["finish_reason_length"] == 96 and metrics["processor_invocations_minimum"] >= 1 and metrics["unique_processor_instances"] == 96 and metrics["assembly_valid"] == 16 and metrics["selected_token_escape"] == 0 and metrics["selected_eos_tokens"] == 0 and metrics["post_mask_dead_end_or_nonfinite"] == 0 and metrics["semantic_repair_events"] == 0 and metrics["unhandled_failures"] == 0


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"; violations.extend([path] if key in PUBLIC_SENSITIVE_KEYS else []); violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value): violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (value.startswith("sample-") or value.startswith("component-")): violations.append(prefix)
    return violations


def verify_payloads(c1_selection: Mapping[str, Any], c1_calls: Sequence[Mapping[str, Any]], seal: Mapping[str, Any], calls: Sequence[Mapping[str, Any]], assemblies: Sequence[Mapping[str, Any]], validator_v4: Any, validator_v5: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = replay_c1_rows(c1_selection, c1_calls, validator_v4); validate_calls(calls, rows, seal, validator_v5); verify_assemblies(assemblies, calls, rows, seal, validator_v5); metrics = technical_metrics(calls, assemblies); require(technical_gate(metrics), "technical gate failed")
    verification = {"schema_version": "sqma-009-verification-v1", "experiment_id": "SQMA-009", "status": "Passed", "technical_gate": metrics, "c1_sources_replayed": True, "token_seal_replayed": True, "model_logits_recomputed": False, "selected_tokens_checked_against_allowlist": True, "next_gate": "complete_sqma009"}
    complete = {"schema_version": "sqma-009-complete-v1", "experiment_id": "SQMA-009", "status": "Complete", "sqma009_complete": True, "technical_gate": "Passed", "accuracy_scored": False, "parity_report_only": True, "automatic_next_stage": False, "next_gate": "register_followup"}
    return verification, complete


def write_pass_only(public_root: Path, verification: Mapping[str, Any], complete: Mapping[str, Any]) -> None:
    require(verification.get("status") == "Passed" and complete.get("sqma009_complete") is True, "non-pass write forbidden"); require(not public_sensitive_paths(verification) and not public_sensitive_paths(complete), "public leak")
    for name, value in (("verification.json", verification), ("complete.json", complete)):
        path = public_root / name; require(not os.path.lexists(path), "terminal exists"); descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "w") as target: json.dump(value, target, sort_keys=True, indent=2); target.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute() and ".." not in Path(relative).parts, f"unsafe {label} path"); root = root.resolve(); path = (root / relative).resolve(); require(path == root or root in path.parents, f"{label} escapes root"); return path


def regular_file(path: Path, label: str, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}"); observed = os.lstat(path); require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode) and observed.st_uid == os.getuid() and observed.st_nlink == 1, f"{label} identity drift")
    if mode is not None: require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_file(path, label); value = json.loads(path.read_text()); require(isinstance(value, dict), f"{label} root drift"); return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    regular_file(path, label); values = [json.loads(line) for line in path.read_text().splitlines()]; require(all(isinstance(value, dict) for value in values), f"{label} rows drift"); return values


def verify_record(record: Mapping[str, Any], label: str) -> Path:
    require({"path", "bytes", "sha256"} <= set(record) and type(record["bytes"]) is int, f"{label} record drift"); path = checked_path(REPO_ROOT, record["path"], label); observed = regular_file(path, label); require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} hash drift"); return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name); spec = importlib.util.spec_from_file_location(name, path); require(spec is not None and spec.loader is not None, f"{name} import unavailable"); module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


def artifact(path: Path) -> dict[str, Any]:
    return {"path": path.resolve().relative_to(REPO_ROOT.resolve()).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_execution(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    require(config_path.resolve() == CONFIG_PATH.resolve(), "noncanonical config"); config = read_json(config_path.resolve(), "config"); validate_static_config(config); require(config["design_status"] == "FrozenReady", "config not ready")
    for section in ("implementation", "prerequisites"):
        for name, record in config[section].items(): verify_record(record, f"{section}.{name}")
    validator_v4 = load_module("sqma009_v4_verifier", config["implementation"]["validator_v4_lineage"]); validator_v5 = load_module("sqma009_v5_verifier", config["implementation"]["validator_v5"])
    c1 = config["sealed_c1_private_input"]; c1_root = checked_path(REPO_ROOT, c1["base_dir"], "C1 root"); c1_paths = {}
    for name, record in c1["artifacts"].items():
        path = checked_path(c1_root, record["path"], f"C1 {name}"); observed = regular_file(path, f"C1 {name}", record["mode"]); require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"C1 {name} drift"); c1_paths[name] = path
    c1_selection = read_json(c1_paths["selection"], "C1 selection"); c1_calls = read_jsonl(c1_paths["calls"], "C1 calls")
    private = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private"); public = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public"); require(private.is_dir() and public.is_dir(), "output roots missing")
    require(sorted(path.name for path in private.iterdir()) == PRIVATE_ALLOWED and sorted(path.name for path in public.iterdir()) == ["run-claim.json", "run.json"], "output inventory drift")
    for path in private.iterdir(): regular_file(path, path.name, "0600")
    for path in public.iterdir(): regular_file(path, path.name, "0644")
    seal = read_json(private / "token-seal.json", "token seal"); calls = read_jsonl(private / "calls.jsonl", "calls"); assemblies = read_jsonl(private / "assemblies.jsonl", "assemblies"); manifest = read_json(private / "private-manifest.json", "manifest"); run = read_json(public / "run.json", "run"); claim = read_json(public / "run-claim.json", "claim")
    verification, complete = verify_payloads(c1_selection, c1_calls, seal, calls, assemblies, validator_v4, validator_v5); metrics = verification["technical_gate"]
    require(run.get("schema_version") == "sqma-009-run-v1" and run.get("experiment_id") == "SQMA-009" and run.get("status") == "CompletedAwaitingVerification" and run.get("config") == artifact(config_path.resolve()) and run.get("technical_gate") == metrics and run.get("technical_gate_passed") is True and run.get("next_gate") == "independent_verification", "run replay drift")
    require(claim.get("schema_version") == "sqma-009-run-claim-v1" and claim.get("config") == artifact(config_path.resolve()) and claim.get("judge_calls") == 96 and claim.get("evidence_critic_generation_calls") == 0 and claim.get("gold_access") is False and claim.get("classifier_access") is False, "claim drift")
    require(manifest.get("schema_version") == "sqma-009-private-manifest-v1" and manifest.get("status") == "SealedAwaitingVerification" and manifest.get("technical_gate_passed") is True and manifest.get("next_gate") == "independent_verification", "manifest drift")
    resources = run["resources"]; limits = config["resources"]; require(resources["generated_tokens"] == 96 and resources["physical_calls"] == 96 and resources["wall_seconds"] <= limits["maximum_wall_seconds"] and resources["peak_rss_bytes"] <= limits["maximum_process_rss_bytes"] and resources["mlx_peak_bytes"] <= limits["maximum_mlx_peak_bytes"] and resources["private_output_bytes"] <= limits["maximum_private_output_bytes"], "resource drift")
    require(not public_sensitive_paths(run) and not public_sensitive_paths(claim), "public leak"); verification["artifacts"] = {"config": artifact(config_path.resolve()), "claim": artifact(public / "run-claim.json"), "run": artifact(public / "run.json"), "token_seal": artifact(private / "token-seal.json"), "calls": artifact(private / "calls.jsonl"), "assemblies": artifact(private / "assemblies.jsonl"), "manifest": artifact(private / "private-manifest.json")}; write_pass_only(public, verification, complete); return verification, complete


def verify_static(path: Path) -> dict[str, Any]:
    require(path.resolve() == CONFIG_PATH.resolve(), "noncanonical config"); value = json.loads(path.read_text()); require(isinstance(value, dict), "config root drift"); return validate_static_config(value)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); parser.add_argument("--static-only", action="store_true"); arguments = parser.parse_args()
    if arguments.static_only: result = verify_static(Path(arguments.config))
    else:
        verification, complete = verify_execution(Path(arguments.config)); result = {"experiment_id": "SQMA-009", "status": verification["status"], "sqma009_complete": complete["sqma009_complete"]}
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, SQMA009VerificationError) as exc:
        print(f"SQMA-009 verification blocked: {type(exc).__name__}: {exc}", file=sys.stderr); raise SystemExit(1)

#!/usr/bin/env python3
"""Independent model-free contract verifier for SQMA-008 Dev-C2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Iterable, Mapping, Sequence


sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-008-dev-c2-locked-acceptance.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
INPUT_FIELDS = {"schema_version", "protocol_id", "sample_id", "component_id", "fold_id", "source_ordinal", "text"}
EXCLUSION_PLAN = (
    ("SQMA-003-agent-dev-random-v1", 32),
    ("SQMA-006-d1-fresh-agent-dev-random-v1", 32),
    ("SQMA-007-dev-c1-visible-shakedown-v1", 16),
)
SELECTION_NAMESPACE = "SQMA-008-dev-c2-locked-acceptance-v1"
GENERATION_NAMESPACE = "SQMA-008-dev-c2-generation-v1"
ROLE_ORDER = ("evidence", "critic", "judge")
JSON_FENCE = re.compile(r"\A```json\r?\n(?P<body>[\s\S]*?)\r?\n```\Z")
JUDGE_DIAGNOSTIC_FIELDS = {
    "raw_json_parse", "exact_six_keys", "missing_or_extra_keys",
    "non_array_values", "non_integer_references", "illegal_reference_ids",
    "rendered_valid", "semantic_repair_events", "normalization_ambiguity_events",
    "reference_normalization_events", "duplicate_references_removed",
    "reference_order_normalized_slots", "rendered_labels",
}
PUBLIC_SENSITIVE_KEYS = {"analysis_text", "allowed_evidence_ids", "component_id", "component_ids", "evidence_spans", "raw_output", "rendered_labels", "sample_id", "sample_ids", "source_ordinal", "source_ordinals", "text"}
CALL_FIELDS = {"schema_version", "call_ordinal", "selection_rank", "selection_stratum", "sample_id", "component_id", "source_ordinal", "system_id", "role", "call_index", "temperature", "seed", "analysis_text", "text_meta", "context_sha256", "messages_sha256", "prompt_ids_sha256", "terminal", "finish_reason", "token_cap_hit", "raw_output", "raw_output_sha256", "canonical_valid", "validation_error", "used_sentinel", "allowed_evidence_ids", "judge_contract", "unhandled_failure", "prefill_tokens", "generated_tokens", "latency_seconds"}
FALLBACK_EVIDENCE = {"schema_version": "evidence-v3", "candidate_emotions": [], "evidence_spans": [], "insufficient_evidence": True}
FALLBACK_CRITIC = {"schema_version": "critic-v3", "recommended_emotions": [], "challenged_emotions": [], "warning_flags": []}
TOP_LEVEL_FIELDS = {
    "schema_version", "experiment_id", "tier", "stage", "design_status",
    "registered_at", "authorization", "claim_boundary", "prerequisites",
    "implementation", "inputs", "selection", "frozen_c1_method",
    "role_context_allowlist", "judge_contract", "call_plan", "acceptance_gate",
    "claim_language", "resources", "outputs", "failure_policy", "commands",
    "next_gate",
}
FROZEN_SECTION_DIGESTS = {
    "claim_boundary": "e4ac5c7a29e8374d4b1097a795b13e991679bb94505dbba04b03e96b319b2902",
    "prerequisites": "e94f250f20a959a159b46a3b0df6eda433803f392cda66d5770ac5e5073e9543",
    "inputs": "99bac7b9f328a44bfcde62364e99674e28eab1cf6a2560e323d989b161ff6b42",
    "selection": "c780255c6c02bf4fcbda4896e038990694646fe610acf5c69145b1b76ca200c3",
    "frozen_c1_method": "deccf6a16ff903fdc11aea06c68af054e22241b2a24f7462c8fc5b5df6f3b17a",
    "role_context_allowlist": "877d12989bfd6d33e5398572e3e8c2cb4d439103a3babf857dfde2cba021b727",
    "judge_contract": "8fe622ac038aee682eff7de07cd975195e9b162cc27f9e8e4e6aa1a056438688",
    "call_plan": "b3eb5e048817ab201f2bbe1038e58b8e92da46f5d3dadaec4ab99753e57a970c",
    "acceptance_gate": "c963a3334a2dc99aa94633ea4074db6dc0d3adcc8e2ced8deec35651ffbc01e9",
    "claim_language": "a0a0c8fe126c265371cf33062efae119678b1c059106ac9f2fc3817edcb5ed0f",
    "resources": "6c55ac00f2acff50c2679cf64cb70fc193315c7626fa7d774d5d6f95897e81f2",
    "outputs": "dfa86da097a4937ea7649b0ce054f4ee281825148e03814d95058d7201fe7816",
    "failure_policy": "e28f3a5450c59daed817b3c05f40bc40d2a9688521604da943f877b103a33dd6",
    "commands": "3d6b541af099d73bf8538e7af2491b1b91f8c6426560b5e7d89f3c8b8ab0692c",
}
IMPLEMENTATION_PATHS = {
    "protocol": "projects/selective-qwen-multi-agent-forum-analysis/protocols/sqma-008-dev-c2-locked-acceptance.md",
    "prompt_bundle": "projects/selective-qwen-multi-agent-forum-analysis/prompts/agent-bundle-v4-judge-evidence-slots.json",
    "output_schema": "projects/selective-qwen-multi-agent-forum-analysis/schemas/agent-output-v4-judge-evidence-slots.schema.json",
    "validator_renderer": "projects/selective-qwen-multi-agent-forum-analysis/scripts/validate_agent_output_v4.py",
    "v3_prompt_dependency": "projects/selective-qwen-multi-agent-forum-analysis/prompts/agent-bundle-v3-classifier-free.json",
    "v3_schema_dependency": "projects/selective-qwen-multi-agent-forum-analysis/schemas/agent-output-v3.schema.json",
    "v3_validator_dependency": "projects/selective-qwen-multi-agent-forum-analysis/scripts/validate_agent_output_v3.py",
    "validator_tests": "projects/selective-qwen-multi-agent-forum-analysis/tests/test_validate_agent_output_v4.py",
    "runner": "projects/selective-qwen-multi-agent-forum-analysis/scripts/run_sqma008_dev_c2_locked_acceptance.py",
    "verifier": "projects/selective-qwen-multi-agent-forum-analysis/scripts/verify_sqma008_dev_c2_locked_acceptance.py",
    "tests": "projects/selective-qwen-multi-agent-forum-analysis/tests/test_sqma008_dev_c2_locked_acceptance.py",
}
STATIC_AUTH_SHA256 = "de237807efac6d47e5821a17281eaf687b4b76467a965220529ea65ff9a3a682"
READY_AUTH_SHA256 = "38f5f0920ccbcb1ec59f09a2c0396d23c75c4289d1dd14dff8dc2a1cf75fab38"
CLAIM_FIELDS = {
    "schema_version", "experiment_id", "status", "claimed_at_utc", "config",
    "locked_rows", "planned_calls", "gold_access", "classifier_access",
    "locked_raw_human_access", "next_gate",
}
RUN_FIELDS = {
    "schema_version", "experiment_id", "status", "selection", "calls",
    "acceptance_gate", "acceptance_checks", "acceptance_passed", "resources",
    "identities", "access", "next_gate",
}
MANIFEST_FIELDS = {
    "schema_version", "experiment_id", "status", "input_snapshot_sha256",
    "selection", "calls_artifact", "model_identity", "access",
    "acceptance_passed", "next_gate",
}
FROZEN_RUN_ACCESS = {
    "locked_raw_human_accessed": False, "gold_accessed": False,
    "classifier_accessed": False, "model_loaded": True,
    "training_executed": False, "fold3_accessed": False,
    "fold4_accessed": False, "validation_accessed": False,
    "test_accessed": False, "network_accessed": False,
}


class C2VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition: raise C2VerificationError(message)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def component_rank(namespace: str, component_id: str) -> str:
    return hashlib.sha256(f"{namespace}|{component_id}".encode()).hexdigest()


def seed_for(system: str, sample: str, role: str, call_index: int) -> int:
    value = f"{GENERATION_NAMESPACE}|{system}|{sample}|{role}|{call_index}".encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:4], "big", signed=False)


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping): return any(contains_placeholder(child) for child in value.values())
    if isinstance(value, (list, tuple)): return any(contains_placeholder(child) for child in value)
    return isinstance(value, str) and value.startswith("PLACEHOLDER_")


def validate_static_config(config: Mapping[str, Any]) -> dict[str, Any]:
    require(set(config) == TOP_LEVEL_FIELDS, "config top-level inventory drift")
    require(
        (config.get("schema_version"), config.get("experiment_id"), config.get("tier"), config.get("stage"), config.get("registered_at"))
        == ("sqma-008-dev-c2-locked-acceptance-v1", "SQMA-008", "Minor", "dev-c2-locked-acceptance", "2026-09-04"),
        "frozen scalar drift",
    )
    for key, digest in FROZEN_SECTION_DIGESTS.items():
        require(canonical_digest(config.get(key)) == digest, f"frozen section drift: {key}")
    implementation = config.get("implementation")
    require(isinstance(implementation, Mapping) and set(implementation) == set(IMPLEMENTATION_PATHS), "implementation inventory drift")
    for key, path in IMPLEMENTATION_PATHS.items():
        record = implementation[key]
        require(isinstance(record, Mapping) and set(record) == {"path", "bytes", "sha256"} and record["path"] == path, f"implementation path/schema drift: {key}")
        require(type(record["bytes"]) is int and record["bytes"] > 0 and isinstance(record["sha256"], str) and len(record["sha256"]) == 64 and set(record["sha256"]) <= set("0123456789abcdef"), f"implementation identity drift: {key}")
    require(config.get("schema_version") == "sqma-008-dev-c2-locked-acceptance-v1" and config.get("experiment_id") == "SQMA-008", "config identity drift")
    require(config.get("design_status") in {"StaticDesignAwaitingImplementationPinning", "FrozenReady"}, "design status drift")
    authorization = config.get("authorization", {}); observed_auth = canonical_digest(authorization)
    if config.get("design_status") == "FrozenReady":
        require(observed_auth == READY_AUTH_SHA256 and config.get("next_gate") == "execute_locked_c2" and not contains_placeholder(config), "ready authorization/next drift")
    else:
        require(observed_auth == STATIC_AUTH_SHA256 and config.get("next_gate") == "pin_complete_config_in_runner_and_verifier_then_static_verify", "static authorization/next drift")
    require(config.get("inputs", {}).get("forbidden_folds") == [3, 4], "fold boundary drift")
    selection = config.get("selection", {})
    require(
        [(item.get("namespace"), item.get("components")) for item in selection.get("sequential_exclusions", [])] == list(EXCLUSION_PLAN)
        and selection.get("new_namespace") == SELECTION_NAMESPACE
        and selection.get("components") == 24 and selection.get("stratum") == "locked_acceptance",
        "selection contract drift",
    )
    require(config.get("call_plan", {}).get("physical_calls") == 72 and config["call_plan"].get("all_rows_locked") is True, "call plan drift")
    require(config.get("failure_policy", {}).get("inspect_locked_row_content_for_same_experiment_revision") is False, "locked access policy drift")
    return {"schema_version": "sqma-008-static-verification-v1", "experiment_id": "SQMA-008", "status": "Passed", "execution_authorized": authorization.get("execution_authorized"), "private_accessed": False, "model_loaded": False, "locked_raw_human_accessed": False, "next_gate": "execute_locked_c2" if authorization.get("execution_authorized") else "pin_complete_config_in_runner_and_verifier_then_static_verify"}


def representatives(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source in rows:
        require(isinstance(source, Mapping) and set(source) == INPUT_FIELDS, "input schema drift")
        require(source["schema_version"] == "sqma-gold-free-inference-snapshot-v1" and source["fold_id"] in {0, 1, 2}, "input fold drift")
        row = dict(source); prior = result.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]: result[row["component_id"]] = row
    return result


def select_c2_rows(rows: Iterable[Mapping[str, Any]], *, expected_components: int | None = 1963) -> tuple[list[dict[str, Any]], list[set[str]]]:
    by_component = representatives(rows)
    if expected_components is not None: require(len(by_component) == expected_components, "component count drift")
    require(len(by_component) >= 104, "insufficient components")
    excluded: set[str] = set(); sets: list[set[str]] = []
    for namespace, count in EXCLUSION_PLAN:
        chosen = sorted((row for row in by_component.values() if row["component_id"] not in excluded), key=lambda row: (component_rank(namespace, row["component_id"]), row["component_id"]))[:count]
        ids = {row["component_id"] for row in chosen}; require(len(ids) == count and not ids & excluded, "exclusion overlap")
        sets.append(ids); excluded |= ids
    chosen = sorted((row for row in by_component.values() if row["component_id"] not in excluded), key=lambda row: (component_rank(SELECTION_NAMESPACE, row["component_id"]), row["component_id"]))[:24]
    ids = {row["component_id"] for row in chosen}; require(len(ids) == 24 and not ids & excluded, "C2 overlap")
    return [{**row, "selection_rank": rank, "selection_stratum": "locked_acceptance"} for rank, row in enumerate(chosen)], sets


def expected_slots(selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(selected) == 24, "selection count drift")
    slots = [{"call_ordinal": row["selection_rank"] * 3 + index, "selection_rank": row["selection_rank"], "selection_stratum": "locked_acceptance", "system_id": "S3", "role": role, "call_index": index, "temperature": 0.0 if role == "judge" else 0.6} for row in selected for index, role in enumerate(ROLE_ORDER)]
    require(len(slots) == 72, "call plan drift"); return slots


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("duplicate key")
        result[key] = value
    return result


def judge_diagnostics(raw_output: Any, allowed_evidence_ids: Sequence[int]) -> dict[str, Any]:
    result = {"raw_json_parse": False, "exact_six_keys": False, "missing_or_extra_keys": True, "non_array_values": True, "non_integer_references": True, "illegal_reference_ids": True, "rendered_valid": False, "semantic_repair_events": 0, "normalization_ambiguity_events": 0, "reference_normalization_events": 0, "duplicate_references_removed": 0, "reference_order_normalized_slots": 0, "rendered_labels": []}
    if not isinstance(raw_output, str): return result
    payload = raw_output.strip(); bare = not (payload.startswith("```") or payload.endswith("```"))
    if not bare:
        match = JSON_FENCE.fullmatch(payload)
        if match is None: return result
        payload = match.group("body").strip()
    try: value = json.loads(payload, object_pairs_hook=strict_pairs)
    except (json.JSONDecodeError, ValueError): return result
    result["raw_json_parse"] = bare
    if not isinstance(value, dict): return result
    exact = set(value) == set(LABEL_ORDER) and len(value) == 6; result["exact_six_keys"] = exact; result["missing_or_extra_keys"] = not exact
    if not exact: return result
    arrays = all(isinstance(value[label], list) for label in LABEL_ORDER); result["non_array_values"] = not arrays
    if not arrays: return result
    integers = all(type(item) is int for label in LABEL_ORDER for item in value[label]); result["non_integer_references"] = not integers
    if not integers: return result
    allowed = set(allowed_evidence_ids); legal = all(item in allowed for label in LABEL_ORDER for item in value[label]); result["illegal_reference_ids"] = not legal
    if not legal: return result
    result["reference_normalization_events"] = sum(sorted(set(value[label])) != value[label] for label in LABEL_ORDER)
    result["duplicate_references_removed"] = sum(len(value[label]) - len(dict.fromkeys(value[label])) for label in LABEL_ORDER)
    result["reference_order_normalized_slots"] = sum(list(dict.fromkeys(value[label])) != sorted(dict.fromkeys(value[label])) for label in LABEL_ORDER)
    result["rendered_valid"] = True; result["rendered_labels"] = [label for label in LABEL_ORDER if value[label]]; return result


def percentile(values: Sequence[float], probability: float) -> float:
    require(bool(values), "empty percentile"); ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * probability) - 1))]


def derive_acceptance_metrics(calls: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]], *, model_load_seconds: float) -> dict[str, Any]:
    slots = expected_slots(selected); require(len(calls) == 72, "call count drift")
    evidence = []; critic = []; fallback = set(); judges = []; token_hits = unhandled = 0; latency = {role: [] for role in ROLE_ORDER}
    for call, slot in zip(calls, slots, strict=True):
        require(all(call.get(key) == value for key, value in slot.items()), "schedule drift"); require(call.get("terminal") is True, "nonterminal call")
        token_hits += int(call.get("token_cap_hit") is True); unhandled += int(call.get("unhandled_failure") is True); latency[call["role"]].append(float(call["latency_seconds"]))
        if call["role"] == "evidence":
            valid = call.get("canonical_valid") is True; evidence.append(valid)
            if not valid: fallback.add(call["selection_rank"])
        elif call["role"] == "critic":
            valid = call.get("canonical_valid") is True; critic.append(valid)
            if not valid: fallback.add(call["selection_rank"])
        else:
            observed = call.get("judge_contract"); require(isinstance(observed, Mapping) and set(observed) == JUDGE_DIAGNOSTIC_FIELDS and observed == judge_diagnostics(call.get("raw_output"), call.get("allowed_evidence_ids", [])), "Judge replay drift"); judges.append(observed)
    count = lambda key: sum(item[key] is True for item in judges); projection = 1.25 * 672 * sum(percentile(latency[role], .95) for role in ROLE_ORDER) + float(model_load_seconds)
    return {"terminal_calls": 72, "judge_raw_json_parse": count("raw_json_parse"), "judge_exact_six_keys": count("exact_six_keys"), "judge_missing_or_extra_key_rows": sum(item["missing_or_extra_keys"] for item in judges), "judge_non_array_value_rows": sum(item["non_array_values"] for item in judges), "judge_non_integer_reference_rows": sum(item["non_integer_references"] for item in judges), "judge_illegal_reference_id_rows": sum(item["illegal_reference_ids"] for item in judges), "judge_rendered_valid": count("rendered_valid"), "semantic_repair_events": sum(item["semantic_repair_events"] for item in judges), "normalization_ambiguity_events": sum(item["normalization_ambiguity_events"] for item in judges), "unhandled_failures": unhandled, "contract_errors": sum(not item["rendered_valid"] for item in judges), "evidence_validator_valid_rate": sum(evidence) / 24, "critic_validator_valid_rate": sum(critic) / 24, "system_fallback_rows": len(fallback), "token_cap_hits": token_hits, "full_projection_seconds": projection, "reference_normalization_events_report_only": sum(item["reference_normalization_events"] for item in judges), "duplicate_references_removed_report_only": sum(item["duplicate_references_removed"] for item in judges), "reference_order_normalized_slots_report_only": sum(item["reference_order_normalized_slots"] for item in judges)}


def acceptance_checks(metrics: Mapping[str, Any]) -> dict[str, bool]:
    return {"terminal": metrics["terminal_calls"] == 72, "raw_parse": metrics["judge_raw_json_parse"] == 24, "exact_keys": metrics["judge_exact_six_keys"] == 24, "no_key_errors": metrics["judge_missing_or_extra_key_rows"] == 0, "arrays": metrics["judge_non_array_value_rows"] == 0, "integer_refs": metrics["judge_non_integer_reference_rows"] == 0, "allowed_ids": metrics["judge_illegal_reference_id_rows"] == 0, "rendered": metrics["judge_rendered_valid"] == 24, "no_semantic_repair": metrics["semantic_repair_events"] == 0, "no_normalization_ambiguity": metrics["normalization_ambiguity_events"] == 0, "no_unhandled": metrics["unhandled_failures"] == 0, "no_contract_errors": metrics["contract_errors"] == 0, "evidence_valid": metrics["evidence_validator_valid_rate"] >= .95, "critic_valid": metrics["critic_validator_valid_rate"] >= .95, "fallback": metrics["system_fallback_rows"] <= 1, "token_hits": metrics["token_cap_hits"] == 0, "projection": metrics["full_projection_seconds"] <= 172800.0}


def acceptance_passes(metrics: Mapping[str, Any]) -> bool:
    return all(acceptance_checks(metrics).values())


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"; violations.extend([path] if key in PUBLIC_SENSITIVE_KEYS else []); violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value): violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (
        value.startswith("sample-") or value.startswith("component-")
    ):
        violations.append(prefix)
    return violations


def verify_payloads(rows: Sequence[Mapping[str, Any]], selection: Mapping[str, Any], calls: Sequence[Mapping[str, Any]], run: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    selected, prior_sets = select_c2_rows(rows)
    expected_selection = {"schema_version": "sqma-008-selection-v1", "experiment_id": "SQMA-008", "prior_exclusion_sha256": [canonical_digest(sorted(values)) for values in prior_sets], "namespace": SELECTION_NAMESPACE, "rows": [{key: row[key] for key in ("selection_rank", "selection_stratum", "sample_id", "component_id", "fold_id", "source_ordinal")} for row in selected]}
    require(selection == expected_selection, "selection replay drift")
    metrics = derive_acceptance_metrics(calls, selected, model_load_seconds=run["resources"]["model_load_seconds"])
    checks = acceptance_checks(metrics); require(acceptance_passes(metrics), "locked acceptance gate failed")
    require(run.get("acceptance_gate") == metrics and run.get("acceptance_checks") == checks and run.get("acceptance_passed") is True, "public aggregate drift")
    require(not public_sensitive_paths(run), "public locked-row leak")
    verification = {"schema_version": "sqma-008-verification-v1", "experiment_id": "SQMA-008", "status": "Passed", "calls_verified": 72, "locked_rows_verified_by_process": 24, "locked_raw_human_accessed": False, "acceptance_gate": metrics, "acceptance_checks": checks, "next_gate": "complete_sqma008"}
    complete = {"schema_version": "sqma-008-complete-v1", "experiment_id": "SQMA-008", "status": "Complete", "sqma008_complete": True, "locked_acceptance_gate": "Passed", "accuracy_scored": False, "locked_raw_human_accessed": False, "automatic_next_stage": False, "next_gate": "register_followup"}
    return verification, complete


def write_pass_only(public_root: Path, verification: Mapping[str, Any], complete: Mapping[str, Any]) -> None:
    require(verification.get("status") == "Passed" and complete.get("sqma008_complete") is True, "non-pass terminal write forbidden")
    require(not public_sensitive_paths(verification) and not public_sensitive_paths(complete), "public terminal leak")
    for name, value in (("verification.json", verification), ("complete.json", complete)):
        path = public_root / name; require(not os.path.lexists(path), "terminal file exists")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as target: json.dump(value, target, sort_keys=True, indent=2); target.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute() and ".." not in Path(relative).parts, f"unsafe {label} path")
    root = root.resolve(); path = (root / relative).resolve(); require(path == root or root in path.parents, f"{label} escapes root"); return path


def regular_file(path: Path, label: str, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}"); observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode) and observed.st_uid == os.getuid() and observed.st_nlink == 1, f"{label} identity drift")
    if mode is not None: require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def regular_directory(path: Path, label: str, mode: str) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(
        stat.S_ISDIR(observed.st_mode) and not stat.S_ISLNK(observed.st_mode)
        and observed.st_uid == os.getuid()
        and f"{stat.S_IMODE(observed.st_mode):04o}" == mode,
        f"{label} directory identity drift",
    )
    return observed


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_file(path, label); value = json.loads(path.read_text()); require(isinstance(value, dict), f"{label} root drift"); return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    regular_file(path, label); values = [json.loads(line) for line in path.read_text().splitlines()]; require(all(isinstance(value, dict) for value in values), f"{label} rows drift"); return values


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(REPO_ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def private_artifact(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def verify_record(record: Any, label: str) -> Path:
    require(isinstance(record, Mapping) and {"path", "bytes", "sha256"} <= set(record) and type(record["bytes"]) is int, f"{label} record drift")
    path = checked_path(REPO_ROOT, record["path"], label); observed = regular_file(path, label); require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} hash drift"); return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name); spec = importlib.util.spec_from_file_location(name, path); require(spec is not None and spec.loader is not None, f"{name} import unavailable"); module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


def read_inputs(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    root = checked_path(REPO_ROOT, config["inputs"]["private_root"], "input root"); rows = []
    for record in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(root, record["path"], "snapshot"); observed = regular_file(path, "snapshot", "0600"); require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "snapshot drift"); values = read_jsonl(path, "snapshot"); require(len(values) == record["rows"], "snapshot rows drift"); rows.extend(values)
    return rows


def prompt_messages(bundle: Mapping[str, Any], role: str, context: Mapping[str, Any]) -> list[dict[str, str]]:
    spec = bundle["roles"][role]; example = bundle["judge_format_example"] if role == "judge" else bundle["format_examples"][role]; system = "\n".join([*bundle["shared_rules"], spec["system"], "Format example for JSON shape and value types only: " + json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]); return [{"role": "system", "content": system}, {"role": "user", "content": "Input JSON:\n" + json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))}]


def replay_calls(calls: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]], v3_bundle: Mapping[str, Any], v4_bundle: Mapping[str, Any], validator: Any) -> None:
    slots = expected_slots(selected); by_rank = {row["selection_rank"]: row for row in selected}; values: dict[int, dict[str, Any]] = {rank: {} for rank in range(24)}
    for call, slot in zip(calls, slots, strict=True):
        require(isinstance(call, Mapping) and set(call) == CALL_FIELDS and all(call[key] == value for key, value in slot.items()), "call schema/schedule drift"); row = by_rank[call["selection_rank"]]
        require((call["sample_id"], call["component_id"], call["source_ordinal"]) == (row["sample_id"], row["component_id"], row["source_ordinal"]), "call source drift")
        require(call["seed"] == seed_for("S3", call["sample_id"], call["role"], call["call_index"]), "seed drift")
        metadata = call["text_meta"]
        require(
            isinstance(metadata, Mapping)
            and metadata.get("original_sha256") == hashlib.sha256(row["text"].encode()).hexdigest()
            and metadata.get("analysis_sha256") == hashlib.sha256(call["analysis_text"].encode()).hexdigest(),
            "text metadata drift",
        )
        context: dict[str, Any] = {"analysis_text": call["analysis_text"], "ontology": validator.ONTOLOGY}
        if call["role"] in {"critic", "judge"}: context["evidence"] = values[call["selection_rank"]].get("evidence", FALLBACK_EVIDENCE)
        if call["role"] == "judge": context["critic"] = values[call["selection_rank"]].get("critic", FALLBACK_CRITIC); context["allowed_evidence_ids"] = list(range(len(context["evidence"]["evidence_spans"])))
        require(call["context_sha256"] == canonical_digest(context), "context drift"); bundle = v4_bundle if call["role"] == "judge" else v3_bundle; require(call["messages_sha256"] == canonical_digest(prompt_messages(bundle, call["role"], context)), "messages drift"); require(call["raw_output_sha256"] == hashlib.sha256(call["raw_output"].encode()).hexdigest(), "raw hash drift")
        require(call["terminal"] is True and call["token_cap_hit"] is (call["finish_reason"] == "length"), "terminal/token-cap drift")
        if call["role"] in {"evidence", "critic"}:
            parsed = None; error = None
            try: parsed = validator.validate_evidence(call["raw_output"], context) if call["role"] == "evidence" else validator.validate_critic(call["raw_output"], context)
            except validator.AgentOutputError as exc: error = exc.code
            if call["token_cap_hit"]: parsed = None; error = "token_cap_hit"
            expected_sentinel = call["role"] == "critic" and "evidence" not in values[call["selection_rank"]]
            require(call["canonical_valid"] is (parsed is not None) and call["validation_error"] == error and call["judge_contract"] is None and call["used_sentinel"] is expected_sentinel, "role replay drift")
            if parsed is not None: values[call["selection_rank"]][call["role"]] = parsed
        else:
            rendered = validator.judge_contract_result(call["raw_output"], context); diagnostic = judge_diagnostics(call["raw_output"], context["allowed_evidence_ids"]); valid = rendered["rendered_contract_valid"] and not call["token_cap_hit"]
            expected_sentinel = "evidence" not in values[call["selection_rank"]] or "critic" not in values[call["selection_rank"]]
            require(call["allowed_evidence_ids"] == context["allowed_evidence_ids"] and call["canonical_valid"] is valid and call["judge_contract"] == diagnostic and diagnostic["rendered_labels"] == rendered["derived_labels"] and call["used_sentinel"] is expected_sentinel, "Judge replay drift")


def validate_sealed_contract(
    config: Mapping[str, Any], claim: Mapping[str, Any], run: Mapping[str, Any],
    manifest: Mapping[str, Any], *, config_record: Mapping[str, Any],
    claim_record: Mapping[str, Any], selection_record: Mapping[str, Any],
    calls_record: Mapping[str, Any], manifest_record: Mapping[str, Any],
    expected_model: Mapping[str, Any], input_hashes: Sequence[str],
    generated_sum: int, private_bytes: int, public_bytes: int,
) -> None:
    require(set(claim) == CLAIM_FIELDS, "claim field inventory drift")
    require(
        claim["schema_version"] == "sqma-008-run-claim-v1"
        and claim["experiment_id"] == "SQMA-008"
        and claim["status"] == "ClaimedBeforeLockedInputOrModelLoad"
        and isinstance(claim["claimed_at_utc"], str)
        and claim["config"] == config_record
        and claim["locked_rows"] == 24 and claim["planned_calls"] == 72
        and claim["gold_access"] is False and claim["classifier_access"] is False
        and claim["locked_raw_human_access"] is False
        and claim["next_gate"] == "locked_c2_producer",
        "claim contract drift",
    )
    require(set(run) == RUN_FIELDS, "run field inventory drift")
    require(
        run["schema_version"] == "sqma-008-run-v1"
        and run["experiment_id"] == "SQMA-008"
        and run["status"] == "CompletedAwaitingVerification"
        and run["next_gate"] == "independent_verification"
        and run["acceptance_passed"] is True,
        "run terminal contract drift",
    )
    require(
        run["selection"] == {"components": 24, "locked": 24, "prior_excluded": 80}
        and run["calls"]
        == {"physical": 72, "by_role": {"evidence": 24, "critic": 24, "judge": 24}},
        "run selection/call aggregate drift",
    )
    require(set(manifest) == MANIFEST_FIELDS, "manifest field inventory drift")
    require(
        manifest["schema_version"] == "sqma-008-private-manifest-v1"
        and manifest["experiment_id"] == "SQMA-008"
        and manifest["status"] == "SealedAwaitingVerification"
        and manifest["input_snapshot_sha256"] == list(input_hashes)
        and manifest["selection"] == selection_record
        and manifest["calls_artifact"] == calls_record
        and manifest["model_identity"] == expected_model
        and manifest["acceptance_passed"] is True
        and manifest["next_gate"] == "independent_verification",
        "manifest contract drift",
    )
    require(run["access"] == FROZEN_RUN_ACCESS and manifest["access"] == FROZEN_RUN_ACCESS, "access boundary drift")
    require(
        run["identities"]
        == {
            "config": config_record, "run_claim": claim_record,
            "model": expected_model, "selection_sha256": selection_record["sha256"],
            "calls_sha256": calls_record["sha256"],
            "manifest_sha256": manifest_record["sha256"],
        },
        "run artifact identity drift",
    )
    resources = run["resources"]
    require(
        set(resources)
        == {
            "wall_seconds", "peak_rss_bytes", "mlx_peak_bytes", "generated_tokens",
            "model_load_seconds", "private_output_bytes", "free_disk_bytes_before",
            "critical_memory_events", "oom_or_kill_events", "orphan_processes_after_exit",
        },
        "resource field inventory drift",
    )
    limits = config["resources"]
    require(
        resources["wall_seconds"] <= limits["maximum_wall_seconds"]
        and resources["peak_rss_bytes"] <= limits["maximum_process_rss_bytes"]
        and resources["mlx_peak_bytes"] <= limits["maximum_mlx_peak_bytes"]
        and resources["generated_tokens"] == generated_sum
        and generated_sum <= limits["maximum_generated_tokens"]
        and resources["private_output_bytes"] == private_bytes
        and private_bytes <= limits["maximum_private_output_bytes"]
        and public_bytes <= limits["maximum_public_output_bytes"]
        and resources["free_disk_bytes_before"] >= limits["minimum_free_disk_bytes"]
        and resources["critical_memory_events"] == 0
        and resources["oom_or_kill_events"] == 0
        and resources["orphan_processes_after_exit"] == 0,
        "resource boundary drift",
    )
    require(not public_sensitive_paths(claim) and not public_sensitive_paths(run), "public privacy drift")


def verify_execution(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    require(config_path.resolve() == CONFIG_PATH.resolve(), "noncanonical config"); config = read_json(config_path.resolve(), "config"); validate_static_config(config); require(config["design_status"] == "FrozenReady", "config not ready")
    for section in ("implementation", "prerequisites"):
        for name, record in config[section].items(): verify_record(record, f"{section}.{name}")
    v3_bundle = read_json(verify_record(config["implementation"]["v3_prompt_dependency"], "v3 prompt"), "v3 prompt"); v4_bundle = read_json(verify_record(config["implementation"]["prompt_bundle"], "v4 prompt"), "v4 prompt"); validator = load_module("sqma008_v4_verifier", config["implementation"]["validator_renderer"])
    public = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public"); private = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private")
    regular_directory(public, "public", "0755"); regular_directory(private, "private", "0700")
    require(
        sorted(path.name for path in public.iterdir()) == ["run-claim.json", "run.json"]
        and sorted(path.name for path in private.iterdir()) == sorted(config["outputs"]["private_allowed_files"]),
        "pre-verification inventory drift",
    )
    for path in public.iterdir(): regular_file(path, path.name, "0644")
    for path in private.iterdir(): regular_file(path, path.name, "0600")
    rows = read_inputs(config); selected, prior = select_c2_rows(rows)
    selection_path = private / "selection.json"; calls_path = private / "calls.jsonl"; manifest_path = private / "private-manifest.json"
    claim_path = public / "run-claim.json"; run_path = public / "run.json"
    selection = read_json(selection_path, "selection"); calls = read_jsonl(calls_path, "calls")
    manifest = read_json(manifest_path, "manifest"); claim = read_json(claim_path, "claim"); run = read_json(run_path, "run")
    expected = {"schema_version": "sqma-008-selection-v1", "experiment_id": "SQMA-008", "prior_exclusion_sha256": [canonical_digest(sorted(values)) for values in prior], "namespace": SELECTION_NAMESPACE, "rows": [{key: row[key] for key in ("selection_rank", "selection_stratum", "sample_id", "component_id", "fold_id", "source_ordinal")} for row in selected]}; require(selection == expected, "selection drift")
    c1_config = read_json(verify_record(config["prerequisites"]["sqma007_config"], "SQMA-007 config"), "SQMA-007 config")
    expected_model = {
        "repo_id": c1_config["model"]["repo_id"], "revision": c1_config["model"]["revision"],
        "manifest_sha256": c1_config["model"]["manifest_sha256"],
        "file_count": c1_config["model"]["file_count"],
        "total_bytes": c1_config["model"]["total_bytes"], "adapter": None,
    }
    config_record = artifact(config_path.resolve()); claim_record = artifact(claim_path)
    selection_record = private_artifact(selection_path, private)
    calls_record = private_artifact(calls_path, private)
    manifest_record = private_artifact(manifest_path, private)
    private_bytes = sum(path.stat().st_size for path in private.iterdir())
    public_bytes = sum(path.stat().st_size for path in public.iterdir())
    validate_sealed_contract(
        config, claim, run, manifest, config_record=config_record,
        claim_record=claim_record, selection_record=selection_record,
        calls_record=calls_record, manifest_record=manifest_record,
        expected_model=expected_model,
        input_hashes=[record["sha256"] for record in config["inputs"]["gold_free_snapshots"]],
        generated_sum=sum(call["generated_tokens"] for call in calls),
        private_bytes=private_bytes, public_bytes=public_bytes,
    )
    replay_calls(calls, selected, v3_bundle, v4_bundle, validator)
    verification, complete = verify_payloads(rows, selection, calls, run)
    verification["artifacts"] = {
        "config": config_record, "claim": claim_record, "run": artifact(run_path),
        "selection": selection_record, "calls": calls_record,
        "manifest": manifest_record,
    }
    write_pass_only(public, verification, complete)
    return verification, complete


def verify_static(path: Path) -> dict[str, Any]:
    require(path.resolve() == CONFIG_PATH.resolve(), "noncanonical config")
    value = json.loads(path.read_text()); require(isinstance(value, dict), "config root drift")
    result = validate_static_config(value)
    for section in ("implementation", "prerequisites"):
        for name, record in value[section].items():
            verify_record(record, f"{section}.{name}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); parser.add_argument("--static-only", action="store_true"); arguments = parser.parse_args()
    if arguments.static_only: result = verify_static(Path(arguments.config))
    else:
        verification, complete = verify_execution(Path(arguments.config)); result = {"experiment_id": "SQMA-008", "status": verification["status"], "sqma008_complete": complete["sqma008_complete"]}
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, C2VerificationError) as exc:
        print(f"SQMA-008 verification blocked: {type(exc).__name__}: {exc}", file=sys.stderr); raise SystemExit(1)

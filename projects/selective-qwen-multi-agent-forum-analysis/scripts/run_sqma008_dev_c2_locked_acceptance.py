#!/usr/bin/env python3
"""Execution-ready producer for SQMA-008 Dev-C2 locked acceptance.

Importing this module performs no I/O; the frozen config gates all private
input access and model loading inside ``run``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import stat
import sys
import time
from typing import Any, Iterable, Mapping, Sequence


sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-008-dev-c2-locked-acceptance.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
INPUT_FIELDS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "fold_id",
    "source_ordinal", "text",
}
EXCLUSION_PLAN = (
    ("SQMA-003-agent-dev-random-v1", 32),
    ("SQMA-006-d1-fresh-agent-dev-random-v1", 32),
    ("SQMA-007-dev-c1-visible-shakedown-v1", 16),
)
SELECTION_NAMESPACE = "SQMA-008-dev-c2-locked-acceptance-v1"
GENERATION_NAMESPACE = "SQMA-008-dev-c2-generation-v1"
ROLE_ORDER = ("evidence", "critic", "judge")
EXPECTED_ROWS = 24
EXPECTED_CALLS = 72
JSON_FENCE = re.compile(r"\A```json\r?\n(?P<body>[\s\S]*?)\r?\n```\Z")
JUDGE_DIAGNOSTIC_FIELDS = {
    "raw_json_parse", "exact_six_keys", "missing_or_extra_keys",
    "non_array_values", "non_integer_references", "illegal_reference_ids",
    "rendered_valid", "semantic_repair_events", "normalization_ambiguity_events",
    "reference_normalization_events", "duplicate_references_removed",
    "reference_order_normalized_slots", "rendered_labels",
}
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text", "allowed_evidence_ids", "component_id", "component_ids",
    "evidence_spans", "raw_output", "rendered_labels", "sample_id", "sample_ids",
    "source_ordinal", "source_ordinals", "text",
}
CALL_FIELDS = {
    "schema_version", "call_ordinal", "selection_rank", "selection_stratum",
    "sample_id", "component_id", "source_ordinal", "system_id", "role",
    "call_index", "temperature", "seed", "analysis_text", "text_meta",
    "context_sha256", "messages_sha256", "prompt_ids_sha256", "terminal",
    "finish_reason", "token_cap_hit", "raw_output", "raw_output_sha256",
    "canonical_valid", "validation_error", "used_sentinel",
    "allowed_evidence_ids", "judge_contract", "unhandled_failure",
    "prefill_tokens", "generated_tokens", "latency_seconds",
}
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


class C2AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise C2AcceptanceError(message)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def component_rank(namespace: str, component_id: str) -> str:
    return hashlib.sha256(f"{namespace}|{component_id}".encode("utf-8")).hexdigest()


def seed_for(system: str, sample: str, role: str, call_index: int) -> int:
    value = f"{GENERATION_NAMESPACE}|{system}|{sample}|{role}|{call_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest()[:4], "big", signed=False)


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(contains_placeholder(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_placeholder(child) for child in value)
    return isinstance(value, str) and value.startswith("PLACEHOLDER_")


def validate_static_config(config: Mapping[str, Any]) -> None:
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
    require(config.get("schema_version") == "sqma-008-dev-c2-locked-acceptance-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-008" and config.get("stage") == "dev-c2-locked-acceptance", "experiment/stage drift")
    require(config.get("design_status") in {"StaticDesignAwaitingImplementationPinning", "FrozenReady"}, "design status drift")
    authorization = config.get("authorization", {})
    observed_auth = canonical_digest(authorization)
    if config.get("design_status") == "FrozenReady":
        require(observed_auth == READY_AUTH_SHA256 and config.get("next_gate") == "execute_locked_c2", "ready authorization/next drift")
        require(not contains_placeholder(config), "ready placeholders remain")
    else:
        require(observed_auth == STATIC_AUTH_SHA256 and config.get("next_gate") == "pin_complete_config_in_runner_and_verifier_then_static_verify", "static authorization/next drift")
    require(config.get("inputs", {}).get("forbidden_folds") == [3, 4], "input fold boundary drift")
    selection = config.get("selection", {})
    require(
        [(item.get("namespace"), item.get("components")) for item in selection.get("sequential_exclusions", [])]
        == list(EXCLUSION_PLAN)
        and selection.get("excluded_components_total") == 80
        and selection.get("new_namespace") == SELECTION_NAMESPACE
        and selection.get("components") == 24
        and selection.get("stratum") == "locked_acceptance"
        and selection.get("visible_shakedown_rows") == 0,
        "selection contract drift",
    )
    require(config.get("call_plan", {}).get("physical_calls") == 72 and config["call_plan"].get("all_rows_locked") is True, "call plan drift")
    require(config.get("acceptance_gate", {}).get("judge_raw_json_parse_required") == 24, "acceptance gate drift")
    require(config.get("failure_policy", {}).get("inspect_locked_row_content_for_same_experiment_revision") is False, "locked inspection policy drift")


def assert_execution_ready(config: Mapping[str, Any]) -> None:
    require(config.get("authorization", {}).get("execution_authorized") is True, "SQMA-008 execution is not authorized")
    require(not contains_placeholder(config), "SQMA-008 identities/resources remain unresolved")
    require(config.get("design_status") == "FrozenReady", "SQMA-008 config is not FrozenReady")


def representatives(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source in rows:
        require(isinstance(source, Mapping) and set(source) == INPUT_FIELDS, "input row schema drift")
        require(source["schema_version"] == "sqma-gold-free-inference-snapshot-v1" and source["fold_id"] in {0, 1, 2}, "input identity/fold drift")
        require(type(source["source_ordinal"]) is int, "source ordinal drift")
        row = dict(source); prior = result.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]:
            result[row["component_id"]] = row
    return result


def select_c2_rows(
    rows: Iterable[Mapping[str, Any]], *, expected_components: int | None = 1963
) -> tuple[list[dict[str, Any]], list[set[str]]]:
    by_component = representatives(rows)
    if expected_components is not None:
        require(len(by_component) == expected_components, "Agent-Dev component count drift")
    require(len(by_component) >= 104, "insufficient components for four disjoint selections")
    excluded: set[str] = set(); prior_sets: list[set[str]] = []
    for namespace, count in EXCLUSION_PLAN:
        selected = sorted(
            (row for row in by_component.values() if row["component_id"] not in excluded),
            key=lambda row: (component_rank(namespace, row["component_id"]), row["component_id"]),
        )[:count]
        current = {row["component_id"] for row in selected}
        require(len(current) == count and not current & excluded, "sequential exclusion drift")
        prior_sets.append(current); excluded |= current
    c2 = sorted(
        (row for row in by_component.values() if row["component_id"] not in excluded),
        key=lambda row: (component_rank(SELECTION_NAMESPACE, row["component_id"]), row["component_id"]),
    )[:24]
    c2_ids = {row["component_id"] for row in c2}
    require(len(c2_ids) == 24 and not c2_ids & excluded, "C2 selection overlap")
    return [
        {**row, "selection_rank": rank, "selection_stratum": "locked_acceptance"}
        for rank, row in enumerate(c2)
    ], prior_sets


def planned_call_slots(selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(selected) == 24, "C2 selection count drift")
    slots = [
        {
            "call_ordinal": row["selection_rank"] * 3 + index,
            "selection_rank": row["selection_rank"],
            "selection_stratum": "locked_acceptance", "system_id": "S3",
            "role": role, "call_index": index,
            "temperature": 0.0 if role == "judge" else 0.6,
        }
        for row in selected
        for index, role in enumerate(ROLE_ORDER)
    ]
    require(len(slots) == 72, "C2 call plan drift")
    return slots


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def judge_diagnostics(raw_output: Any, allowed_evidence_ids: Sequence[int]) -> dict[str, Any]:
    result = {
        "raw_json_parse": False, "exact_six_keys": False,
        "missing_or_extra_keys": True, "non_array_values": True,
        "non_integer_references": True, "illegal_reference_ids": True,
        "rendered_valid": False, "semantic_repair_events": 0,
        "normalization_ambiguity_events": 0,
        "reference_normalization_events": 0, "duplicate_references_removed": 0,
        "reference_order_normalized_slots": 0, "rendered_labels": [],
    }
    if not isinstance(raw_output, str):
        return result
    payload = raw_output.strip()
    if payload.startswith("```") or payload.endswith("```"):
        match = JSON_FENCE.fullmatch(payload)
        if match is None:
            return result
        payload = match.group("body").strip()
        raw_bare = False
    else:
        raw_bare = True
    try:
        value = json.loads(payload, object_pairs_hook=strict_pairs)
    except (json.JSONDecodeError, ValueError):
        return result
    result["raw_json_parse"] = raw_bare
    if not isinstance(value, dict):
        return result
    exact = set(value) == set(LABEL_ORDER) and len(value) == 6
    result["exact_six_keys"] = exact; result["missing_or_extra_keys"] = not exact
    if not exact:
        return result
    arrays = all(isinstance(value[label], list) for label in LABEL_ORDER)
    result["non_array_values"] = not arrays
    if not arrays:
        return result
    integers = all(type(item) is int for label in LABEL_ORDER for item in value[label])
    result["non_integer_references"] = not integers
    if not integers:
        return result
    allowed = set(allowed_evidence_ids)
    legal = all(item in allowed for label in LABEL_ORDER for item in value[label])
    result["illegal_reference_ids"] = not legal
    if not legal:
        return result
    result["reference_normalization_events"] = sum(sorted(set(value[label])) != value[label] for label in LABEL_ORDER)
    result["duplicate_references_removed"] = sum(len(value[label]) - len(dict.fromkeys(value[label])) for label in LABEL_ORDER)
    result["reference_order_normalized_slots"] = sum(list(dict.fromkeys(value[label])) != sorted(dict.fromkeys(value[label])) for label in LABEL_ORDER)
    result["rendered_valid"] = True
    result["rendered_labels"] = [label for label in LABEL_ORDER if value[label]]
    return result


def percentile(values: Sequence[float], probability: float) -> float:
    require(bool(values), "empty percentile")
    ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * probability) - 1))]


def derive_acceptance_metrics(
    calls: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]],
    *, model_load_seconds: float,
) -> dict[str, Any]:
    slots = planned_call_slots(selected); require(len(calls) == 72, "C2 call count drift")
    evidence_valid: list[bool] = []; critic_valid: list[bool] = []
    fallback_rows: set[int] = set(); judges: list[Mapping[str, Any]] = []
    token_hits = unhandled = 0; latency = {role: [] for role in ROLE_ORDER}
    for call, slot in zip(calls, slots, strict=True):
        require(all(call.get(key) == value for key, value in slot.items()), "call schedule drift")
        require(call.get("terminal") is True, "nonterminal call")
        token_hits += int(call.get("token_cap_hit") is True)
        unhandled += int(call.get("unhandled_failure") is True)
        latency[call["role"]].append(float(call["latency_seconds"]))
        if call["role"] == "evidence":
            valid = call.get("canonical_valid") is True; evidence_valid.append(valid)
            if not valid: fallback_rows.add(call["selection_rank"])
        elif call["role"] == "critic":
            valid = call.get("canonical_valid") is True; critic_valid.append(valid)
            if not valid: fallback_rows.add(call["selection_rank"])
        else:
            observed = call.get("judge_contract")
            require(isinstance(observed, Mapping) and set(observed) == JUDGE_DIAGNOSTIC_FIELDS, "Judge diagnostic schema drift")
            require(observed == judge_diagnostics(call.get("raw_output"), call.get("allowed_evidence_ids", [])), "Judge diagnostic replay drift")
            judges.append(observed)
    count = lambda key: sum(item[key] is True for item in judges)
    errors = sum(not item["rendered_valid"] for item in judges)
    projection = 1.25 * 672 * sum(percentile(latency[role], .95) for role in ROLE_ORDER) + float(model_load_seconds)
    return {
        "terminal_calls": 72,
        "judge_raw_json_parse": count("raw_json_parse"),
        "judge_exact_six_keys": count("exact_six_keys"),
        "judge_missing_or_extra_key_rows": sum(item["missing_or_extra_keys"] for item in judges),
        "judge_non_array_value_rows": sum(item["non_array_values"] for item in judges),
        "judge_non_integer_reference_rows": sum(item["non_integer_references"] for item in judges),
        "judge_illegal_reference_id_rows": sum(item["illegal_reference_ids"] for item in judges),
        "judge_rendered_valid": count("rendered_valid"),
        "semantic_repair_events": sum(item["semantic_repair_events"] for item in judges),
        "normalization_ambiguity_events": sum(item["normalization_ambiguity_events"] for item in judges),
        "unhandled_failures": unhandled, "contract_errors": errors,
        "evidence_validator_valid_rate": sum(evidence_valid) / 24,
        "critic_validator_valid_rate": sum(critic_valid) / 24,
        "system_fallback_rows": len(fallback_rows), "token_cap_hits": token_hits,
        "full_projection_seconds": projection,
        "reference_normalization_events_report_only": sum(item["reference_normalization_events"] for item in judges),
        "duplicate_references_removed_report_only": sum(item["duplicate_references_removed"] for item in judges),
        "reference_order_normalized_slots_report_only": sum(item["reference_order_normalized_slots"] for item in judges),
    }


def acceptance_checks(metrics: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "terminal": metrics["terminal_calls"] == 72,
        "raw_parse": metrics["judge_raw_json_parse"] == 24,
        "exact_keys": metrics["judge_exact_six_keys"] == 24,
        "no_key_errors": metrics["judge_missing_or_extra_key_rows"] == 0,
        "arrays": metrics["judge_non_array_value_rows"] == 0,
        "integer_refs": metrics["judge_non_integer_reference_rows"] == 0,
        "allowed_ids": metrics["judge_illegal_reference_id_rows"] == 0,
        "rendered": metrics["judge_rendered_valid"] == 24,
        "no_semantic_repair": metrics["semantic_repair_events"] == 0,
        "no_normalization_ambiguity": metrics["normalization_ambiguity_events"] == 0,
        "no_unhandled": metrics["unhandled_failures"] == 0,
        "no_contract_errors": metrics["contract_errors"] == 0,
        "evidence_valid": metrics["evidence_validator_valid_rate"] >= 0.95,
        "critic_valid": metrics["critic_validator_valid_rate"] >= 0.95,
        "fallback": metrics["system_fallback_rows"] <= 1,
        "token_hits": metrics["token_cap_hits"] == 0,
        "projection": metrics["full_projection_seconds"] <= 172800.0,
    }


def acceptance_passes(metrics: Mapping[str, Any]) -> bool:
    return all(acceptance_checks(metrics).values())


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS: violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value): violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def public_run_payload(metrics: Mapping[str, Any], resources: Mapping[str, Any], identities: Mapping[str, Any]) -> dict[str, Any]:
    passed = acceptance_passes(metrics)
    value = {
        "schema_version": "sqma-008-run-v1", "experiment_id": "SQMA-008",
        "status": "CompletedAwaitingVerification" if passed else "Failed",
        "selection": {"components": 24, "locked": 24, "prior_excluded": 80},
        "calls": {"physical": 72, "by_role": {"evidence": 24, "critic": 24, "judge": 24}},
        "acceptance_gate": dict(metrics), "acceptance_checks": acceptance_checks(metrics),
        "acceptance_passed": passed, "resources": dict(resources),
        "identities": dict(identities),
        "access": {"locked_raw_human_accessed": False, "gold_accessed": False, "classifier_accessed": False},
        "next_gate": "independent_verification" if passed else "stop_failed_incident_required",
    }
    require(not public_sensitive_paths(value), "public row-level leak")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute() and ".." not in Path(relative).parts, f"unsafe {label} path")
    root = root.resolve(); path = (root / relative).resolve(); require(path == root or root in path.parents, f"{label} escapes root")
    current = root
    for part in Path(relative).parts:
        current /= part
        if os.path.lexists(current): require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} symlink drift")
    return path


def regular_file(path: Path, label: str, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}"); observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode) and observed.st_uid == os.getuid() and observed.st_nlink == 1, f"{label} identity drift")
    if mode is not None: require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_file(path, label); value = json.loads(path.read_text(encoding="utf-8")); require(isinstance(value, dict), f"{label} root drift"); return value


def artifact(path: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    return {"path": path.resolve().relative_to(root.resolve()).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_record(record: Any, label: str) -> Path:
    require(isinstance(record, Mapping) and {"path", "bytes", "sha256"} <= set(record) and type(record["bytes"]) is int, f"{label} record drift")
    path = checked_path(REPO_ROOT, record["path"], label); observed = regular_file(path, label)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} hash drift"); return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name); spec = importlib.util.spec_from_file_location(name, path); require(spec is not None and spec.loader is not None, f"{name} import unavailable")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


def write_json(path: Path, value: Mapping[str, Any], mode: int) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(); descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as target: target.write(payload); target.flush(); os.fsync(target.fileno())
    path.chmod(mode)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]], mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        for row in rows: target.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        target.flush(); os.fsync(target.fileno())
    path.chmod(mode)


def read_inputs(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    root = checked_path(REPO_ROOT, config["inputs"]["private_root"], "input root"); rows = []; hashes = []
    for record in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(root, record["path"], "snapshot"); observed = regular_file(path, "snapshot", "0600")
        require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "snapshot identity drift")
        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]; require(len(values) == record["rows"], "snapshot rows drift"); rows.extend(values); hashes.append(record["sha256"])
    require(len(rows) == 2016, "Agent-Dev row count drift"); return rows, hashes


def verify_model(model: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    archive = Path(model["audited_archive_root"]).resolve(); manifest_path = checked_path(archive, model["manifest_path"], "model manifest")
    observed = regular_file(manifest_path, "model manifest"); require(observed.st_size == model["manifest_bytes"] and sha256(manifest_path) == model["manifest_sha256"], "model manifest drift")
    manifest = read_json(manifest_path, "model manifest"); inventory = manifest["mlx_bf16"]["files"]; model_root = checked_path(archive, model["relative_path"], "model root"); total = 0
    for record in inventory:
        path = checked_path(model_root, record["path"], "model file"); file_stat = regular_file(path, "model file"); require(file_stat.st_size == record["bytes"] and sha256(path) == record["sha256"], "model file drift"); total += record["bytes"]
    require(total == model["total_bytes"], "model bytes drift")
    return model_root, {"repo_id": model["repo_id"], "revision": model["revision"], "manifest_sha256": model["manifest_sha256"], "file_count": len(inventory), "total_bytes": total, "adapter": None}


def truncate_text(tokenizer: Any, text: str, cap: int) -> tuple[str, dict[str, Any]]:
    ids = list(tokenizer.encode(text, add_special_tokens=False)); analysis = text if len(ids) <= cap else tokenizer.decode(ids[:cap], skip_special_tokens=True); analysis_ids = list(tokenizer.encode(analysis, add_special_tokens=False))
    require(bool(analysis) and len(analysis_ids) <= cap, "analysis text drift")
    return analysis, {"original_sha256": hashlib.sha256(text.encode()).hexdigest(), "analysis_sha256": hashlib.sha256(analysis.encode()).hexdigest(), "original_token_count": len(ids), "analysis_token_count": len(analysis_ids), "was_truncated": len(ids) > cap, "model_free_truncation_replay": len(ids) <= cap}


def prompt_messages(bundle: Mapping[str, Any], role: str, context: Mapping[str, Any]) -> list[dict[str, str]]:
    spec = bundle["roles"][role]; example = bundle["judge_format_example"] if role == "judge" else bundle["format_examples"][role]
    system = "\n".join([*bundle["shared_rules"], spec["system"], "Format example for JSON shape and value types only: " + json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":"))])
    return [{"role": "system", "content": system}, {"role": "user", "content": "Input JSON:\n" + json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))}]


def render_prompt(tokenizer: Any, bundle: Mapping[str, Any], role: str, context: Mapping[str, Any], cap: int, max_new: int) -> tuple[list[int], list[dict[str, str]]]:
    messages = prompt_messages(bundle, role, context); ids = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False)
    if isinstance(ids, Mapping): ids = ids["input_ids"]
    values = [int(item) for item in ids]; require(values and len(values) + max_new <= cap, "prompt cap drift"); return values, messages


def resource_snapshot(started: float, mx: Any, generated: int) -> dict[str, Any]:
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform.startswith("linux"): rss *= 1024
    return {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": rss, "mlx_peak_bytes": int(mx.get_peak_memory()), "generated_tokens": generated}


def check_resources(config: Mapping[str, Any], observed: Mapping[str, Any]) -> None:
    limits = config["resources"]
    for key, limit in (("wall_seconds", "maximum_wall_seconds"), ("peak_rss_bytes", "maximum_process_rss_bytes"), ("mlx_peak_bytes", "maximum_mlx_peak_bytes"), ("generated_tokens", "maximum_generated_tokens")):
        require(observed[key] <= limits[limit], f"resource cap drift: {key}")


def run(config_argument: str) -> dict[str, Any]:
    started = time.monotonic(); started_at = utc_now()
    supplied = Path(config_argument).expanduser().resolve()
    require(supplied == CONFIG_PATH.resolve(), "noncanonical SQMA-008 config")
    config = read_json(supplied, "config"); validate_static_config(config); assert_execution_ready(config)
    for section in ("implementation", "prerequisites"):
        for name, record in config[section].items(): verify_record(record, f"{section}.{name}")
    c1_config = read_json(verify_record(config["prerequisites"]["sqma007_config"], "SQMA-007 config"), "SQMA-007 config")
    complete = read_json(verify_record(config["prerequisites"]["sqma007_complete"], "SQMA-007 complete"), "SQMA-007 complete")
    verification = read_json(verify_record(config["prerequisites"]["sqma007_verification"], "SQMA-007 verification"), "SQMA-007 verification")
    require(complete.get("sqma007_complete") is True and complete.get("ordinary_decoding_c1_gate") == "Passed" and verification.get("status") == "Passed", "SQMA-007 prerequisite gate drift")
    method = config["frozen_c1_method"]; require(method["model"] == {key: c1_config["model"][key] for key in ("repo_id", "revision", "format", "adapter")}, "C1 model drift")
    v3_bundle = read_json(verify_record(config["implementation"]["v3_prompt_dependency"], "v3 prompt"), "v3 prompt")
    v4_bundle = read_json(verify_record(config["implementation"]["prompt_bundle"], "v4 prompt"), "v4 prompt")
    validator = load_module("sqma008_validator_v4", config["implementation"]["validator_renderer"])
    public_dir = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public output"); private_dir = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private output")
    require(not os.path.lexists(public_dir) and not os.path.lexists(private_dir), "output namespace exists")
    free_disk = __import__("shutil").disk_usage(REPO_ROOT).free; require(free_disk >= config["resources"]["minimum_free_disk_bytes"], "disk gate failed")
    public_dir.mkdir(parents=True, mode=0o755, exist_ok=False)
    claim = {"schema_version": "sqma-008-run-claim-v1", "experiment_id": "SQMA-008", "status": "ClaimedBeforeLockedInputOrModelLoad", "claimed_at_utc": utc_now(), "config": artifact(supplied), "locked_rows": 24, "planned_calls": 72, "gold_access": False, "classifier_access": False, "locked_raw_human_access": False, "next_gate": "locked_c2_producer"}
    require(not public_sensitive_paths(claim), "claim leak"); write_json(public_dir / "run-claim.json", claim, 0o644)
    rows, input_hashes = read_inputs(config); selected, prior_sets = select_c2_rows(rows)
    selection = {"schema_version": "sqma-008-selection-v1", "experiment_id": "SQMA-008", "prior_exclusion_sha256": [canonical_digest(sorted(values)) for values in prior_sets], "namespace": SELECTION_NAMESPACE, "rows": [{key: row[key] for key in ("selection_rank", "selection_stratum", "sample_id", "component_id", "fold_id", "source_ordinal")} for row in selected]}
    private_dir.mkdir(parents=True, mode=0o700, exist_ok=False); private_dir.chmod(0o700); write_json(private_dir / "selection.json", selection, 0o600)
    model_path, model_identity = verify_model(c1_config["model"]); runtime = c1_config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve() and platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime drift")
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    for package, version in runtime["packages"].items(): require(importlib.metadata.version(package) == version, f"package drift: {package}")
    mx.reset_peak_memory(); load_started = time.monotonic(); model, tokenizer = load(str(model_path), adapter_path=None, lazy=False); model_load_seconds = time.monotonic() - load_started
    generation = method["generation"]
    samplers = {"evidence": make_sampler(temp=.6, top_p=.95, top_k=20), "critic": make_sampler(temp=.6, top_p=.95, top_k=20), "judge": make_sampler(temp=0.0)}
    calls: list[dict[str, Any]] = []; generated_total = 0

    def one_call(row: Mapping[str, Any], role: str, analysis_text: str, text_meta: Mapping[str, Any], fields: Mapping[str, Any], used_sentinel: bool) -> tuple[dict[str, Any], Any]:
        nonlocal generated_total
        context = {"analysis_text": analysis_text, "ontology": validator.ONTOLOGY, **fields}; bundle = v4_bundle if role == "judge" else v3_bundle; settings = generation[role]
        prompt_ids, messages = render_prompt(tokenizer, bundle, role, context, generation["context_token_cap"], settings["max_new_tokens"])
        seed = seed_for("S3", row["sample_id"], role, ROLE_ORDER.index(role)); mx.random.seed(seed); parts = []; final = None
        stream = stream_generate(model, tokenizer, prompt_ids, max_tokens=settings["max_new_tokens"], sampler=samplers[role]); call_started = time.monotonic()
        try:
            for response in stream:
                parts.append(response.text); final = {"finish_reason": response.finish_reason, "prompt_tokens": int(response.prompt_tokens), "generated_tokens": int(response.generation_tokens)}; check_resources(config, resource_snapshot(started, mx, generated_total))
        finally: stream.close()
        latency = time.monotonic() - call_started; require(final is not None and final["finish_reason"] is not None and final["prompt_tokens"] == len(prompt_ids), "terminal metadata drift")
        generated_total += final["generated_tokens"]; check_resources(config, resource_snapshot(started, mx, generated_total)); raw = "".join(parts); cap_hit = final["finish_reason"] == "length"; parsed = None; error = None; diagnostic = None; allowed = list(fields.get("allowed_evidence_ids", []))
        if role in {"evidence", "critic"}:
            try: parsed = validator.validate_evidence(raw, context) if role == "evidence" else validator.validate_critic(raw, context)
            except validator.AgentOutputError as exc: error = exc.code
            if cap_hit: parsed = None; error = "token_cap_hit"
            valid = parsed is not None
        else:
            rendered = validator.judge_contract_result(raw, context); diagnostic = judge_diagnostics(raw, allowed); valid = rendered["rendered_contract_valid"] and not cap_hit; error = "token_cap_hit" if cap_hit else rendered["diagnostics"]["error_code"]
            require(diagnostic["rendered_valid"] is rendered["rendered_contract_valid"] and diagnostic["rendered_labels"] == rendered["derived_labels"], "renderer disagreement"); parsed = rendered if valid else None
        slot = planned_call_slots(selected)[len(calls)]
        record = {"schema_version": "sqma-008-call-v1", **slot, "sample_id": row["sample_id"], "component_id": row["component_id"], "source_ordinal": row["source_ordinal"], "seed": seed, "analysis_text": analysis_text, "text_meta": dict(text_meta), "context_sha256": canonical_digest(context), "messages_sha256": canonical_digest(messages), "prompt_ids_sha256": canonical_digest(prompt_ids), "terminal": True, "finish_reason": final["finish_reason"], "token_cap_hit": cap_hit, "raw_output": raw, "raw_output_sha256": hashlib.sha256(raw.encode()).hexdigest(), "canonical_valid": valid, "validation_error": error, "used_sentinel": used_sentinel, "allowed_evidence_ids": allowed, "judge_contract": diagnostic, "unhandled_failure": False, "prefill_tokens": len(prompt_ids), "generated_tokens": final["generated_tokens"], "latency_seconds": latency}
        require(set(record) == CALL_FIELDS, "call record schema drift"); calls.append(record); return record, parsed

    for row in selected:
        analysis, meta = truncate_text(tokenizer, row["text"], generation["analysis_text_token_cap"]); evidence_call, evidence_value = one_call(row, "evidence", analysis, meta, {}, False); evidence = evidence_value or FALLBACK_EVIDENCE
        critic_call, critic_value = one_call(row, "critic", analysis, meta, {"evidence": evidence}, evidence_value is None); critic = critic_value or FALLBACK_CRITIC; allowed = list(range(len(evidence["evidence_spans"])))
        one_call(row, "judge", analysis, meta, {"evidence": evidence, "critic": critic, "allowed_evidence_ids": allowed}, evidence_value is None or critic_value is None); gc.collect(); mx.clear_cache()
    metrics = derive_acceptance_metrics(calls, selected, model_load_seconds=model_load_seconds); passed = acceptance_passes(metrics); write_jsonl(private_dir / "calls.jsonl", calls, 0o600)
    selection_record = artifact(private_dir / "selection.json", private_dir); calls_record = artifact(private_dir / "calls.jsonl", private_dir)
    access = {"locked_raw_human_accessed": False, "gold_accessed": False, "classifier_accessed": False, "model_loaded": True, "training_executed": False, "fold3_accessed": False, "fold4_accessed": False, "validation_accessed": False, "test_accessed": False, "network_accessed": False}
    manifest = {"schema_version": "sqma-008-private-manifest-v1", "experiment_id": "SQMA-008", "status": "SealedAwaitingVerification" if passed else "Failed", "input_snapshot_sha256": input_hashes, "selection": selection_record, "calls_artifact": calls_record, "model_identity": model_identity, "access": access, "acceptance_passed": passed, "next_gate": "independent_verification" if passed else "stop_failed_incident_required"}
    write_json(private_dir / "private-manifest.json", manifest, 0o600); private_bytes = sum(path.stat().st_size for path in private_dir.iterdir()); require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private output cap drift")
    resources = resource_snapshot(started, mx, generated_total); check_resources(config, resources)
    run_payload = public_run_payload(metrics, {**resources, "model_load_seconds": model_load_seconds, "private_output_bytes": private_bytes, "free_disk_bytes_before": free_disk, "critical_memory_events": 0, "oom_or_kill_events": 0, "orphan_processes_after_exit": 0}, {"config": artifact(supplied), "run_claim": artifact(public_dir / "run-claim.json"), "model": model_identity, "selection_sha256": sha256(private_dir / "selection.json"), "calls_sha256": sha256(private_dir / "calls.jsonl"), "manifest_sha256": sha256(private_dir / "private-manifest.json")})
    write_json(public_dir / "run.json", run_payload, 0o644); return run_payload


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True)
    result = run(parser.parse_args().config); print(json.dumps({"experiment_id": "SQMA-008", "status": result["status"], "acceptance_passed": result["acceptance_passed"], "next_gate": result["next_gate"]}, sort_keys=True)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, C2AcceptanceError) as exc:
        print(f"SQMA-008 blocked: {type(exc).__name__}: {exc}", file=sys.stderr); raise SystemExit(1)

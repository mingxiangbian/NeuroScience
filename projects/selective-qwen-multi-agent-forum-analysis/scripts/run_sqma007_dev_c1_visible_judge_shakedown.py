#!/usr/bin/env python3
"""Execution-ready producer for SQMA-007 Dev-C1 visible shakedown.

The frozen config binds separate v3 Evidence/Critic and v4 Judge prompt sources,
the disjoint selection, 48-call schedule, Judge contract, and Gate 1. Importing
this module performs no I/O or model loading; execution begins through ``run``.
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
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-007-dev-c1-visible-judge-shakedown.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
INPUT_FIELDS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "fold_id",
    "source_ordinal", "text",
}
OLD_NAMESPACE = "SQMA-003-agent-dev-random-v1"
SQMA006_NAMESPACE = "SQMA-006-d1-fresh-agent-dev-random-v1"
SQMA007_NAMESPACE = "SQMA-007-dev-c1-visible-shakedown-v1"
GENERATION_NAMESPACE = "SQMA-007-dev-c1-generation-v1"
EXPECTED_COMPONENTS = 1963
EXPECTED_SELECTION = 16
EXPECTED_CALLS = 48
ROLE_ORDER = ("evidence", "critic", "judge")
ROLE_CONTEXT_ALLOWLIST = {
    "evidence": ["analysis_text", "ontology"],
    "critic": ["analysis_text", "ontology", "evidence"],
    "judge": [
        "analysis_text", "ontology", "evidence", "critic", "allowed_evidence_ids",
    ],
}
JSON_FENCE = re.compile(r"\A```json\r?\n(?P<body>[\s\S]*?)\r?\n```\Z")
JUDGE_DIAGNOSTIC_FIELDS = {
    "raw_json_parse", "exact_six_fields", "no_extra_or_missing_keys",
    "all_reference_values_are_arrays", "all_reference_items_are_integers",
    "all_reference_ids_allowed", "semantic_repair_used", "rendered_valid",
    "rendered_labels", "reference_normalization_events",
    "duplicate_references_removed", "reference_order_normalized_slots",
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
FALLBACK_EVIDENCE = {
    "schema_version": "evidence-v3", "candidate_emotions": [],
    "evidence_spans": [], "insufficient_evidence": True,
}
FALLBACK_CRITIC = {
    "schema_version": "critic-v3", "recommended_emotions": [],
    "challenged_emotions": [], "warning_flags": [],
}
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text", "allowed_evidence_ids", "component_id", "component_ids",
    "evidence_spans", "judge_contract", "raw_output", "sample_id", "sample_ids",
    "source_ordinal", "source_ordinals", "text",
}
GATE1 = {
    "terminal_calls_required": 48,
    "judge_raw_json_parse_required": 16,
    "judge_exact_six_fields_required": 16,
    "judge_no_extra_or_missing_keys_required": 16,
    "judge_reference_arrays_required": 16,
    "judge_integer_reference_items_required": 16,
    "judge_allowed_reference_ids_required": 16,
    "semantic_repair_calls": 0,
    "unhandled_failures": 0,
    "judge_rendered_valid_required": 16,
    "token_cap_hits": 0,
    "maximum_full_projection_seconds": 172800.0,
}
TOP_LEVEL_FIELDS = {
    "schema_version", "experiment_id", "tier", "stage", "design_status",
    "registered_at", "authorization", "implementation", "prerequisites", "inputs",
    "selection", "model", "runtime", "generation", "role_context_allowlist",
    "call_plan", "gate1", "resources", "failure_policy", "outputs", "commands",
    "next_gate",
}
FROZEN_SCALARS = {
    "schema_version": "sqma-007-dev-c1-visible-judge-shakedown-v1",
    "experiment_id": "SQMA-007", "tier": "Minor",
    "stage": "dev-c1-visible-judge-shakedown",
    "design_status": "FrozenExecutionReady", "registered_at": "2026-09-04",
    "next_gate": "execute_visible_c1",
}
FROZEN_SECTION_DIGESTS = {
    "authorization": "472affcab3bf5be62928b02c9ba1749900a80bb195b09464daee308f300d493f",
    "prerequisites": "1f274fb3164d0cd035473275bf13d91a33607e005908c047053dbedf1021d7ee",
    "inputs": "4a0f32e8206988d007dc0fc26088694768ae4316d542df7c046d020705c39095",
    "selection": "7eefef811e58437d716455c8e656ddc6a1b2f564ffe318ccb74bf778aba87e43",
    "model": "c3cc2d0f5a33d938a85b6a421da041a4480df64f39683678047194261ea60bd2",
    "runtime": "ad02c64e9ee1e136f3216d8fa977cdcb79bb48a5a03491f38f138b947c129061",
    "generation": "b969440ee6b039c7a9e7751aaeaefb3db94fd01955b05958cd9eca73ade92de5",
    "role_context_allowlist": "877d12989bfd6d33e5398572e3e8c2cb4d439103a3babf857dfde2cba021b727",
    "call_plan": "e693139b398ad88e86b9aa9eb0b01f566459f798c44f40ebf61f6f2b6f63ef7e",
    "gate1": "9f1608204aed774c4405f50688c8159cb605ebf7d39538eb071985378e51a169",
    "resources": "9b81c22816c1c51775609a7b259e2d2f52e5de2f61fcb0dcb298199a52dd17e4",
    "failure_policy": "8a9e40a6ab9be6a6c7b84130202347aecc0512f647ead06622de41f6f8e83052",
    "outputs": "1bf305c9f721177235948ac37a7badbf99aa42359e9fec7855772d246e57d278",
    "commands": "716636194d2f2b8a917f21e2b25dcd41ec20c11d7fdeffa3a1725ac1b14cd5a5",
}
IMPLEMENTATION_PATHS = {
    "protocol": "projects/selective-qwen-multi-agent-forum-analysis/protocols/sqma-007-dev-c1-visible-judge-shakedown.md",
    "evidence_critic_prompt_v3": "projects/selective-qwen-multi-agent-forum-analysis/prompts/agent-bundle-v3-classifier-free.json",
    "judge_prompt_v4": "projects/selective-qwen-multi-agent-forum-analysis/prompts/agent-bundle-v4-judge-evidence-slots.json",
    "judge_schema_v4": "projects/selective-qwen-multi-agent-forum-analysis/schemas/agent-output-v4-judge-evidence-slots.schema.json",
    "validator_v4": "projects/selective-qwen-multi-agent-forum-analysis/scripts/validate_agent_output_v4.py",
    "validator_tests_v4": "projects/selective-qwen-multi-agent-forum-analysis/tests/test_validate_agent_output_v4.py",
    "runner": "projects/selective-qwen-multi-agent-forum-analysis/scripts/run_sqma007_dev_c1_visible_judge_shakedown.py",
    "verifier": "projects/selective-qwen-multi-agent-forum-analysis/scripts/verify_sqma007_dev_c1_visible_judge_shakedown.py",
    "tests": "projects/selective-qwen-multi-agent-forum-analysis/tests/test_sqma007_dev_c1_visible_judge_shakedown.py",
}


class C1DesignError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise C1DesignError(message)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def component_rank(namespace: str, component_id: str) -> str:
    return hashlib.sha256(f"{namespace}|{component_id}".encode("utf-8")).hexdigest()


def seed_for(namespace: str, system: str, sample: str, role: str, call_index: int) -> int:
    value = f"{namespace}|{system}|{sample}|{role}|{call_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest()[:4], "big", signed=False)


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(contains_placeholder(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_placeholder(child) for child in value)
    return isinstance(value, str) and value.startswith("PLACEHOLDER_")


def validate_static_config(config: Mapping[str, Any]) -> None:
    require(set(config) == TOP_LEVEL_FIELDS, "config top-level inventory drift")
    for key, expected in FROZEN_SCALARS.items():
        require(config.get(key) == expected, f"frozen scalar drift: {key}")
    for key, digest in FROZEN_SECTION_DIGESTS.items():
        require(canonical_digest(config.get(key)) == digest, f"frozen section drift: {key}")
    implementation = config.get("implementation")
    require(isinstance(implementation, Mapping) and set(implementation) == set(IMPLEMENTATION_PATHS), "implementation inventory drift")
    for key, path in IMPLEMENTATION_PATHS.items():
        record = implementation[key]
        keys = {"path", "bytes", "sha256", "api"} if key == "validator_v4" else {"path", "bytes", "sha256"}
        require(isinstance(record, Mapping) and set(record) == keys and record["path"] == path, f"implementation path/schema drift: {key}")
        require(type(record["bytes"]) is int and record["bytes"] > 0 and isinstance(record["sha256"], str) and len(record["sha256"]) == 64 and set(record["sha256"]) <= set("0123456789abcdef"), f"implementation identity drift: {key}")
    require(implementation["validator_v4"]["api"] == "validate_evidence; validate_critic; judge_contract_result; validate_output; final_labels_or_empty", "v4 API drift")
    require(config.get("schema_version") == "sqma-007-dev-c1-visible-judge-shakedown-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-007" and config.get("stage") == "dev-c1-visible-judge-shakedown", "experiment/stage drift")
    require(config.get("design_status") in {"StaticDesignAwaitingJudgeV2V4Identity", "FrozenExecutionReady"}, "design status drift")
    authorization = config.get("authorization", {})
    enabled = {"execution_authorized", "private_input_access", "model_loading", "generation", "visible_c1_content_access"}
    forbidden = set(authorization) - enabled
    require(all(authorization.get(key) is False for key in forbidden), "forbidden authorization drift")
    if config.get("design_status") == "FrozenExecutionReady":
        require(all(authorization.get(key) is True for key in enabled), "execution authorization drift")
        require(not contains_placeholder(config.get("implementation", {})), "execution-ready placeholders remain")
    else:
        require(all(value is False for value in authorization.values()), "static authorization drift")
        require(contains_placeholder(config.get("implementation", {})), "JudgeV2/v4 placeholders missing")
    inputs = config.get("inputs", {})
    require(
        [record.get("fold_id") for record in inputs.get("gold_free_snapshots", [])] == [0, 1, 2]
        and inputs.get("forbidden_folds") == [3, 4]
        and inputs.get("allowed_fields") == sorted(INPUT_FIELDS),
        "Agent-Dev input boundary drift",
    )
    selection = config.get("selection", {})
    require(
        selection.get("excluded_namespaces") == [OLD_NAMESPACE, SQMA006_NAMESPACE]
        and selection.get("excluded_component_counts") == [32, 32]
        and selection.get("new_namespace") == SQMA007_NAMESPACE
        and selection.get("components") == 16
        and selection.get("stratum") == "visible_shakedown"
        and selection.get("locked_rows") == 0,
        "C1 selection contract drift",
    )
    require(
        config.get("call_plan")
        == {
            "rows": 16, "roles_per_row": ["evidence", "critic", "judge"],
            "calls_per_row": 3, "physical_calls": 48,
            "evidence_temperature": 0.6, "critic_temperature": 0.6,
            "judge_temperature": 0.0, "judge_decoding": "greedy",
            "locked_calls": 0,
        },
        "C1 call plan drift",
    )
    require(config.get("role_context_allowlist") == ROLE_CONTEXT_ALLOWLIST, "role context drift")
    require(config.get("gate1") == GATE1, "Gate 1 drift")
    require(
        config.get("failure_policy")
        == {
            "judge_contract_error": "ordinary_decoding_c1_failed",
            "next_decision": "constrained_decoding_decision",
            "automatic_prompt_revision": False,
            "automatic_next_stage": False,
        },
        "failure policy drift",
    )


def assert_execution_ready(config: Mapping[str, Any]) -> None:
    require(config.get("authorization", {}).get("execution_authorized") is True, "SQMA-007 execution is not authorized")
    require(not contains_placeholder(config.get("implementation", {})), "JudgeV2/v4 identities unresolved")
    require(config.get("design_status") == "FrozenExecutionReady", "SQMA-007 is not frozen execution-ready")


def representatives(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source in rows:
        require(isinstance(source, Mapping) and set(source) == INPUT_FIELDS, "input row schema drift")
        require(source["schema_version"] == "sqma-gold-free-inference-snapshot-v1", "input identity drift")
        require(source["fold_id"] in {0, 1, 2}, "held-out fold entered C1 selection")
        require(type(source["source_ordinal"]) is int, "source ordinal drift")
        row = dict(source)
        prior = result.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]:
            result[row["component_id"]] = row
    return result


def select_c1_rows(
    rows: Iterable[Mapping[str, Any]], *, expected_components: int | None = EXPECTED_COMPONENTS
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    by_component = representatives(rows)
    if expected_components is not None:
        require(len(by_component) == expected_components, "Agent-Dev component count drift")
    require(len(by_component) >= 80, "insufficient components for three disjoint selections")
    old = sorted(
        by_component.values(),
        key=lambda row: (component_rank(OLD_NAMESPACE, row["component_id"]), row["component_id"]),
    )[:32]
    old_ids = {row["component_id"] for row in old}
    sqma006 = sorted(
        (row for row in by_component.values() if row["component_id"] not in old_ids),
        key=lambda row: (component_rank(SQMA006_NAMESPACE, row["component_id"]), row["component_id"]),
    )[:32]
    sqma006_ids = {row["component_id"] for row in sqma006}
    c1 = sorted(
        (
            row for row in by_component.values()
            if row["component_id"] not in old_ids | sqma006_ids
        ),
        key=lambda row: (component_rank(SQMA007_NAMESPACE, row["component_id"]), row["component_id"]),
    )[:16]
    require(len(c1) == 16, "C1 selection count drift")
    c1_ids = {row["component_id"] for row in c1}
    require(not (old_ids & sqma006_ids or old_ids & c1_ids or sqma006_ids & c1_ids), "selection overlap")
    return [
        {**row, "selection_rank": rank, "selection_stratum": "visible_shakedown"}
        for rank, row in enumerate(c1)
    ], old_ids, sqma006_ids


def planned_call_slots(selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(selected) == 16, "C1 selection count drift")
    slots = [
        {
            "call_ordinal": row["selection_rank"] * 3 + index,
            "selection_rank": row["selection_rank"],
            "selection_stratum": "visible_shakedown",
            "system_id": "S3", "role": role, "call_index": index,
            "temperature": 0.0 if role == "judge" else 0.6,
        }
        for row in selected
        for index, role in enumerate(ROLE_ORDER)
    ]
    require(len(slots) == 48, "C1 call count drift")
    return slots


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def judge_contract_diagnostics(raw_output: Any, allowed_evidence_ids: Sequence[int]) -> dict[str, Any]:
    diagnostics = {
        "raw_json_parse": False,
        "exact_six_fields": False,
        "no_extra_or_missing_keys": False,
        "all_reference_values_are_arrays": False,
        "all_reference_items_are_integers": False,
        "all_reference_ids_allowed": False,
        "semantic_repair_used": False,
        "rendered_valid": False,
        "rendered_labels": [],
        "reference_normalization_events": 0,
        "duplicate_references_removed": 0,
        "reference_order_normalized_slots": 0,
    }
    if not isinstance(raw_output, str):
        return diagnostics
    payload = raw_output.strip()
    used_fence = payload.startswith("```") or payload.endswith("```")
    if used_fence:
        match = JSON_FENCE.fullmatch(payload)
        if match is None:
            return diagnostics
        payload = match.group("body").strip()
    try:
        value = json.loads(payload, object_pairs_hook=strict_pairs)
    except (json.JSONDecodeError, ValueError):
        return diagnostics
    diagnostics["raw_json_parse"] = not used_fence
    if not isinstance(value, dict):
        return diagnostics
    keys = list(value)
    exact = set(keys) == set(LABEL_ORDER) and len(keys) == 6
    diagnostics["exact_six_fields"] = exact
    diagnostics["no_extra_or_missing_keys"] = set(keys) == set(LABEL_ORDER) and len(keys) == 6
    if not diagnostics["no_extra_or_missing_keys"]:
        return diagnostics
    arrays = all(isinstance(value[label], list) for label in LABEL_ORDER)
    diagnostics["all_reference_values_are_arrays"] = arrays
    if not arrays:
        return diagnostics
    integer_items = all(
        type(item) is int for label in LABEL_ORDER for item in value[label]
    )
    diagnostics["all_reference_items_are_integers"] = integer_items
    if not integer_items:
        return diagnostics
    allowed = set(allowed_evidence_ids)
    ids_allowed = all(item in allowed for label in LABEL_ORDER for item in value[label])
    diagnostics["all_reference_ids_allowed"] = ids_allowed
    if exact and ids_allowed:
        diagnostics["reference_normalization_events"] = sum(
            sorted(set(value[label])) != value[label] for label in LABEL_ORDER
        )
        diagnostics["duplicate_references_removed"] = sum(
            len(value[label]) - len(dict.fromkeys(value[label])) for label in LABEL_ORDER
        )
        diagnostics["reference_order_normalized_slots"] = sum(
            list(dict.fromkeys(value[label])) != sorted(dict.fromkeys(value[label]))
            for label in LABEL_ORDER
        )
        diagnostics["rendered_valid"] = True
        diagnostics["rendered_labels"] = [label for label in LABEL_ORDER if value[label]]
    return diagnostics


def percentile(values: Sequence[float], probability: float) -> float:
    require(bool(values), "empty percentile")
    ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * probability) - 1))]


def derive_gate1(
    calls: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]],
    *, model_load_seconds: float,
) -> dict[str, Any]:
    slots = planned_call_slots(selected)
    require(len(calls) == 48, "C1 physical call drift")
    judge_diagnostics: list[Mapping[str, Any]] = []
    evidence_valid: list[bool] = []
    critic_valid: list[bool] = []
    token_hits = unhandled = semantic_repairs = 0
    latency = {role: [] for role in ROLE_ORDER}
    for call, slot in zip(calls, slots, strict=True):
        require(all(call.get(key) == value for key, value in slot.items()), "C1 call schedule drift")
        require(call.get("terminal") is True, "nonterminal C1 call")
        require(type(call.get("token_cap_hit")) is bool, "token-cap type drift")
        require(type(call.get("unhandled_failure")) is bool, "unhandled type drift")
        require(
            type(call.get("latency_seconds")) in (int, float)
            and not isinstance(call.get("latency_seconds"), bool)
            and math.isfinite(call["latency_seconds"])
            and call["latency_seconds"] >= 0,
            "latency drift",
        )
        token_hits += int(call["token_cap_hit"])
        unhandled += int(call["unhandled_failure"])
        latency[call["role"]].append(float(call["latency_seconds"]))
        if call["role"] == "evidence":
            evidence_valid.append(call.get("canonical_valid") is True)
        elif call["role"] == "critic":
            critic_valid.append(call.get("canonical_valid") is True)
        else:
            observed = call.get("judge_contract")
            require(isinstance(observed, Mapping) and set(observed) == JUDGE_DIAGNOSTIC_FIELDS, "Judge diagnostic schema drift")
            expected = judge_contract_diagnostics(call.get("raw_output"), call.get("allowed_evidence_ids", []))
            require(observed == expected, "Judge diagnostic replay drift")
            judge_diagnostics.append(observed)
            semantic_repairs += int(observed["semantic_repair_used"])
    projection = 1.25 * 672 * sum(percentile(latency[role], .95) for role in ROLE_ORDER) + float(model_load_seconds)
    count = lambda key: sum(item[key] is True for item in judge_diagnostics)
    return {
        "terminal_calls": sum(call.get("terminal") is True for call in calls),
        "judge_raw_json_parse": count("raw_json_parse"),
        "judge_exact_six_fields": count("exact_six_fields"),
        "judge_no_extra_or_missing_keys": count("no_extra_or_missing_keys"),
        "judge_reference_arrays": count("all_reference_values_are_arrays"),
        "judge_integer_reference_items": count("all_reference_items_are_integers"),
        "judge_allowed_reference_ids": count("all_reference_ids_allowed"),
        "semantic_repair_calls": semantic_repairs,
        "unhandled_failures": unhandled,
        "judge_rendered_valid": count("rendered_valid"),
        "token_cap_hits": token_hits,
        "full_projection_seconds": projection,
        "evidence_canonical_valid_rate_report_only": sum(evidence_valid) / 16,
        "critic_canonical_valid_rate_report_only": sum(critic_valid) / 16,
        "reference_normalization_events_report_only": sum(
            item["reference_normalization_events"] for item in judge_diagnostics
        ),
        "duplicate_references_removed_report_only": sum(
            item["duplicate_references_removed"] for item in judge_diagnostics
        ),
        "reference_order_normalized_slots_report_only": sum(
            item["reference_order_normalized_slots"] for item in judge_diagnostics
        ),
    }


def gate1_checks(metrics: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "terminal": metrics["terminal_calls"] == 48,
        "judge_raw_json": metrics["judge_raw_json_parse"] == 16,
        "judge_exact_fields": metrics["judge_exact_six_fields"] == 16,
        "judge_keys": metrics["judge_no_extra_or_missing_keys"] == 16,
        "judge_arrays": metrics["judge_reference_arrays"] == 16,
        "judge_integer_refs": metrics["judge_integer_reference_items"] == 16,
        "judge_allowed_ids": metrics["judge_allowed_reference_ids"] == 16,
        "no_semantic_repair": metrics["semantic_repair_calls"] == 0,
        "no_unhandled": metrics["unhandled_failures"] == 0,
        "judge_rendered": metrics["judge_rendered_valid"] == 16,
        "no_token_hits": metrics["token_cap_hits"] == 0,
        "projection": metrics["full_projection_seconds"] <= 172800.0,
    }


def gate1_passes(metrics: Mapping[str, Any]) -> bool:
    return all(gate1_checks(metrics).values())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), f"invalid {label} path")
    require(".." not in Path(relative).parts and not any(c in relative for c in "*?[]{}"), f"unsafe {label} path")
    root = root.resolve(); path = (root / relative).resolve()
    require(path == root or root in path.parents, f"{label} path escapes root")
    current = root
    for part in Path(relative).parts:
        current /= part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains symlink")
    return path


def regular_file(path: Path, label: str, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(
        stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode)
        and observed.st_uid == os.getuid() and observed.st_nlink == 1,
        f"{label} identity drift",
    )
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_file(path, label)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{label} root drift")
    return value


def artifact(path: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size, "sha256": sha256(path),
    }


def verify_record(record: Any, label: str) -> Path:
    require(
        isinstance(record, Mapping) and set(record) >= {"path", "bytes", "sha256"}
        and type(record["bytes"]) is int and record["bytes"] > 0,
        f"{label} record drift",
    )
    path = checked_path(REPO_ROOT, record["path"], label)
    observed = regular_file(path, label)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} hash drift")
    return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"{name} import unavailable")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: Mapping[str, Any], mode: int) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload); target.flush(); os.fsync(target.fileno())
    path.chmod(mode)


def write_jsonl(path: Path, values: Sequence[Mapping[str, Any]], mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
        for value in values:
            target.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        target.flush(); os.fsync(target.fileno())
    path.chmod(mode)


def public_safe(value: Any, prefix: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            require(key not in PUBLIC_SENSITIVE_KEYS, f"public sensitive key at {prefix}.{key}")
            public_safe(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            public_safe(child, f"{prefix}[{index}]")
    elif isinstance(value, str):
        require(not value.startswith("sample-") and not value.startswith("component-"), f"public identity leak at {prefix}")


def read_inputs(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    root = checked_path(REPO_ROOT, config["inputs"]["private_root"], "SQMA-002 private root")
    rows: list[dict[str, Any]] = []; hashes: list[str] = []
    for record in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(root, record["path"], "gold-free snapshot")
        observed = regular_file(path, "gold-free snapshot", "0600")
        require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "input snapshot drift")
        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        require(len(values) == record["rows"] and all(row.get("fold_id") == record["fold_id"] for row in values), "input row/fold drift")
        rows.extend(values); hashes.append(record["sha256"])
    require(len(rows) == 2016, "Agent-Dev row count drift")
    return rows, hashes


def verify_model(config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    model = config["model"]
    archive = Path(os.environ.get(model["archive_root_env"], model["audited_archive_root"])).expanduser().resolve()
    manifest_path = checked_path(archive, model["manifest_path"], "model manifest")
    observed = regular_file(manifest_path, "model manifest")
    require(observed.st_size == model["manifest_bytes"] and sha256(manifest_path) == model["manifest_sha256"], "model manifest drift")
    manifest = read_json(manifest_path, "model manifest")
    inventory = manifest.get("mlx_bf16", {}).get("files")
    require(manifest.get("repo_id") == model["repo_id"] and manifest.get("revision") == model["revision"] and isinstance(inventory, list) and len(inventory) == model["file_count"], "model identity drift")
    model_root = checked_path(archive, model["relative_path"], "model root"); total = 0
    for record in inventory:
        path = checked_path(model_root, record["path"], "model file"); file_stat = regular_file(path, "model file")
        require(file_stat.st_size == record["bytes"] and sha256(path) == record["sha256"], "model file drift")
        total += record["bytes"]
    require(total == model["total_bytes"], "model bytes drift")
    return model_root, {"repo_id": model["repo_id"], "revision": model["revision"], "manifest_sha256": model["manifest_sha256"], "file_count": len(inventory), "total_bytes": total, "adapter": None}


def truncate_text(tokenizer: Any, text: str, cap: int) -> tuple[str, dict[str, Any]]:
    ids = list(tokenizer.encode(text, add_special_tokens=False))
    analysis = text if len(ids) <= cap else tokenizer.decode(ids[:cap], skip_special_tokens=True)
    analysis_ids = list(tokenizer.encode(analysis, add_special_tokens=False))
    require(bool(analysis) and len(analysis_ids) <= cap, "analysis truncation drift")
    return analysis, {
        "original_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "analysis_sha256": hashlib.sha256(analysis.encode()).hexdigest(),
        "original_token_count": len(ids), "analysis_token_count": len(analysis_ids),
        "was_truncated": len(ids) > cap, "model_free_truncation_replay": len(ids) <= cap,
    }


def prompt_messages(bundle: Mapping[str, Any], role: str, context: Mapping[str, Any]) -> list[dict[str, str]]:
    spec = bundle["roles"][role]
    require(spec["visible_fields"] == ROLE_CONTEXT_ALLOWLIST[role] and set(context) == set(spec["visible_fields"]), "role context drift")
    if role == "judge":
        example = bundle["judge_format_example"]
    else:
        example = bundle["format_examples"][role]
    contract = "Format example for JSON shape and value types only: " + json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    system = "\n".join([*bundle["shared_rules"], spec["system"], contract])
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "Input JSON:\n" + json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))},
    ]


def render_prompt(tokenizer: Any, bundle: Mapping[str, Any], role: str, context: Mapping[str, Any], cap: int, max_new: int) -> tuple[list[int], list[dict[str, str]]]:
    messages = prompt_messages(bundle, role, context)
    prompt_ids = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False)
    if isinstance(prompt_ids, Mapping): prompt_ids = prompt_ids["input_ids"]
    ids = [int(value) for value in prompt_ids]
    require(bool(ids) and len(ids) + max_new <= cap, "prompt context cap drift")
    return ids, messages


def resource_snapshot(started: float, mx: Any, generated: int) -> dict[str, Any]:
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform.startswith("linux"): rss *= 1024
    return {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": rss, "mlx_peak_bytes": int(mx.get_peak_memory()), "generated_tokens": generated}


def check_resources(config: Mapping[str, Any], observed: Mapping[str, Any]) -> None:
    limits = config["resources"]
    require(observed["wall_seconds"] <= limits["maximum_wall_seconds"], "wall cap exceeded")
    require(observed["peak_rss_bytes"] <= limits["maximum_process_rss_bytes"], "RSS cap exceeded")
    require(observed["mlx_peak_bytes"] <= limits["maximum_mlx_peak_bytes"], "MLX cap exceeded")
    require(observed["generated_tokens"] <= limits["maximum_generated_tokens"], "token cap exceeded")


def run(config_argument: str) -> dict[str, Any]:
    started = time.monotonic(); started_at = utc_now()
    supplied = Path(config_argument).expanduser().resolve()
    require(supplied == CONFIG_PATH.resolve(), "noncanonical SQMA-007 config")
    config = read_json(supplied, "SQMA-007 config")
    validate_static_config(config); assert_execution_ready(config)
    for section in ("implementation", "prerequisites"):
        for name, record in config[section].items():
            verify_record(record, f"{section}.{name}")
    v3_bundle = read_json(verify_record(config["implementation"]["evidence_critic_prompt_v3"], "v3 prompt"), "v3 prompt")
    v4_bundle = read_json(verify_record(config["implementation"]["judge_prompt_v4"], "v4 prompt"), "v4 prompt")
    validator = load_module("sqma007_validator_v4", config["implementation"]["validator_v4"])
    require(v3_bundle.get("schema_version") == "sqma-agent-prompt-bundle-v3-classifier-free", "v3 prompt drift")
    require(v4_bundle.get("schema_version") == "sqma-agent-prompt-bundle-v4-judge-evidence-slots", "v4 prompt drift")
    require(
        v3_bundle["roles"]["evidence"]["visible_fields"] == ROLE_CONTEXT_ALLOWLIST["evidence"]
        and v3_bundle["roles"]["critic"]["visible_fields"] == ROLE_CONTEXT_ALLOWLIST["critic"]
        and v4_bundle["roles"]["judge"]["visible_fields"] == ROLE_CONTEXT_ALLOWLIST["judge"],
        "execution prompt source/context drift",
    )

    public_dir = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public output")
    private_dir = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private output")
    require(not os.path.lexists(public_dir) and not os.path.lexists(private_dir), "SQMA-007 output namespace exists")
    free_disk = __import__("shutil").disk_usage(REPO_ROOT).free
    require(free_disk >= config["resources"]["minimum_free_disk_bytes"], "insufficient disk")
    public_dir.mkdir(parents=True, mode=0o755, exist_ok=False)
    claim = {
        "schema_version": "sqma-007-run-claim-v1", "experiment_id": "SQMA-007",
        "status": "ClaimedBeforePrivateInputOrModelLoad", "claimed_at_utc": utc_now(),
        "config": artifact(supplied), "planned_calls": 48,
        "fresh_visible_selection": True, "locked_rows": 0,
        "gold_access": False, "classifier_access": False, "training": False,
        "next_gate": "visible_c1_producer",
    }
    public_safe(claim); write_json(public_dir / "run-claim.json", claim, 0o644)
    rows, input_hashes = read_inputs(config)
    selected, old_ids, sqma006_ids = select_c1_rows(rows)
    selection = {
        "schema_version": "sqma-007-selection-v1", "experiment_id": "SQMA-007",
        "old_top32_sha256": canonical_digest(sorted(old_ids)),
        "sqma006_fresh32_sha256": canonical_digest(sorted(sqma006_ids)),
        "namespace": SQMA007_NAMESPACE,
        "rows": [
            {key: row[key] for key in ("selection_rank", "selection_stratum", "sample_id", "component_id", "fold_id", "source_ordinal")}
            for row in selected
        ],
    }
    private_dir.mkdir(parents=True, mode=0o700, exist_ok=False); private_dir.chmod(0o700)
    write_json(private_dir / "selection.json", selection, 0o600)
    model_path, model_identity = verify_model(config)
    runtime = config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve(), "runtime executable drift")
    require(platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime platform drift")
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    for package, version in runtime["packages"].items():
        require(importlib.metadata.version(package) == version, f"runtime package drift: {package}")
    mx.reset_peak_memory(); load_started = time.monotonic()
    model, tokenizer = load(str(model_path), adapter_path=None, lazy=False)
    model_load_seconds = time.monotonic() - load_started
    samplers = {
        "evidence": make_sampler(temp=0.6, top_p=config["generation"]["top_p"], top_k=config["generation"]["top_k"]),
        "critic": make_sampler(temp=0.6, top_p=config["generation"]["top_p"], top_k=config["generation"]["top_k"]),
        "judge": make_sampler(temp=0.0),
    }
    calls: list[dict[str, Any]] = []; generated_total = 0

    def generate_call(
        row: Mapping[str, Any], role: str, analysis_text: str, text_meta: Mapping[str, Any],
        context_fields: Mapping[str, Any], used_sentinel: bool,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        nonlocal generated_total
        context = {"analysis_text": analysis_text, "ontology": validator.ONTOLOGY, **context_fields}
        bundle = v4_bundle if role == "judge" else v3_bundle
        generation = config["generation"][role]
        prompt_ids, messages = render_prompt(tokenizer, bundle, role, context, config["generation"]["context_token_cap"], generation["max_new_tokens"])
        seed = seed_for(GENERATION_NAMESPACE, "S3", row["sample_id"], role, ROLE_ORDER.index(role))
        mx.random.seed(seed); pieces: list[str] = []; final = None
        stream = stream_generate(model, tokenizer, prompt_ids, max_tokens=generation["max_new_tokens"], sampler=samplers[role])
        call_started = time.monotonic()
        try:
            for response in stream:
                pieces.append(response.text)
                final = {"finish_reason": response.finish_reason, "prompt_tokens": int(response.prompt_tokens), "generated_tokens": int(response.generation_tokens)}
                check_resources(config, resource_snapshot(started, mx, generated_total))
        finally:
            stream.close()
        latency = time.monotonic() - call_started
        require(final is not None and final["finish_reason"] is not None and final["prompt_tokens"] == len(prompt_ids), "terminal metadata drift")
        generated_total += final["generated_tokens"]; check_resources(config, resource_snapshot(started, mx, generated_total))
        raw = "".join(pieces); cap_hit = final["finish_reason"] == "length"
        parsed = None; error = None; judge_contract = None; allowed_ids = list(context_fields.get("allowed_evidence_ids", []))
        if role in {"evidence", "critic"}:
            try:
                parsed = validator.validate_evidence(raw, context) if role == "evidence" else validator.validate_critic(raw, context)
            except validator.AgentOutputError as exc:
                error = exc.code
            if cap_hit:
                parsed = None; error = "token_cap_hit"
            canonical_valid = parsed is not None
        else:
            v4_result = validator.judge_contract_result(raw, context)
            judge_contract = judge_contract_diagnostics(raw, allowed_ids)
            require(
                judge_contract["rendered_valid"] is v4_result["rendered_contract_valid"]
                and judge_contract["rendered_labels"] == v4_result["derived_labels"]
                and all(
                    judge_contract[key] == v4_result["diagnostics"][key]
                    for key in (
                        "reference_normalization_events", "duplicate_references_removed",
                        "reference_order_normalized_slots",
                    )
                ),
                "Judge consumer disagreement",
            )
            canonical_valid = bool(v4_result["rendered_contract_valid"]) and not cap_hit
            error = "token_cap_hit" if cap_hit else v4_result["diagnostics"]["error_code"]
            parsed = v4_result if canonical_valid else None
        slot = planned_call_slots(selected)[len(calls)]
        record = {
            "schema_version": "sqma-007-call-v1", **slot,
            "sample_id": row["sample_id"], "component_id": row["component_id"], "source_ordinal": row["source_ordinal"],
            "seed": seed, "analysis_text": analysis_text, "text_meta": dict(text_meta),
            "context_sha256": canonical_digest(context), "messages_sha256": canonical_digest(messages),
            "prompt_ids_sha256": canonical_digest(prompt_ids), "terminal": True,
            "finish_reason": final["finish_reason"], "token_cap_hit": cap_hit,
            "raw_output": raw, "raw_output_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "canonical_valid": canonical_valid, "validation_error": error,
            "used_sentinel": used_sentinel, "allowed_evidence_ids": allowed_ids,
            "judge_contract": judge_contract, "unhandled_failure": False,
            "prefill_tokens": len(prompt_ids), "generated_tokens": final["generated_tokens"],
            "latency_seconds": latency,
        }
        require(set(record) == CALL_FIELDS, "call record drift"); calls.append(record)
        return record, parsed

    for row in selected:
        analysis_text, text_meta = truncate_text(tokenizer, row["text"], config["generation"]["analysis_text_token_cap"])
        evidence_call, evidence_value = generate_call(row, "evidence", analysis_text, text_meta, {}, False)
        evidence = evidence_value if evidence_value is not None else FALLBACK_EVIDENCE
        critic_call, critic_value = generate_call(row, "critic", analysis_text, text_meta, {"evidence": evidence}, evidence_value is None)
        critic = critic_value if critic_value is not None else FALLBACK_CRITIC
        allowed_ids = list(range(len(evidence["evidence_spans"])))
        generate_call(row, "judge", analysis_text, text_meta, {"evidence": evidence, "critic": critic, "allowed_evidence_ids": allowed_ids}, evidence_value is None or critic_value is None)
        gc.collect(); mx.clear_cache()
    metrics = derive_gate1(calls, selected, model_load_seconds=model_load_seconds)
    passed = gate1_passes(metrics)
    write_jsonl(private_dir / "calls.jsonl", calls, 0o600)
    selection_record = artifact(private_dir / "selection.json", private_dir)
    calls_record = artifact(private_dir / "calls.jsonl", private_dir)
    access = {"visible_c1_content_accessed": True, "locked_content_accessed": False, "gold_accessed": False, "classifier_accessed": False, "adapter_loaded": False, "model_loaded": True, "training_executed": False, "network_accessed": False, "fold3_accessed": False, "fold4_accessed": False, "validation_accessed": False, "test_accessed": False}
    manifest = {
        "schema_version": "sqma-007-private-manifest-v1", "experiment_id": "SQMA-007",
        "status": "SealedAwaitingVerification" if passed else "SealedOrdinaryDecodingC1Failed",
        "input_snapshot_sha256": input_hashes, "selection": selection_record,
        "calls_artifact": calls_record, "model_identity": model_identity,
        "prompt_identity": {"evidence_critic_v3": config["implementation"]["evidence_critic_prompt_v3"]["sha256"], "judge_v4": config["implementation"]["judge_prompt_v4"]["sha256"], "validator_v4": config["implementation"]["validator_v4"]["sha256"]},
        "access": access, "gate1_passed": passed,
        "next_gate": "independent_verification" if passed else "constrained_decoding_decision",
    }
    write_json(private_dir / "private-manifest.json", manifest, 0o600)
    require(sorted(path.name for path in private_dir.iterdir()) == sorted(config["outputs"]["private_allowed_files"]), "private inventory drift")
    private_bytes = sum(path.stat().st_size for path in private_dir.iterdir()); require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private bytes exceeded")
    resources = resource_snapshot(started, mx, generated_total); check_resources(config, resources)
    run_payload = {
        "schema_version": "sqma-007-run-v1", "experiment_id": "SQMA-007", "tier": config["tier"], "stage": config["stage"],
        "status": "CompletedAwaitingVerification" if passed else "CompletedOrdinaryDecodingC1Failed",
        "started_at_utc": started_at, "completed_at_utc": utc_now(), "config": artifact(supplied), "run_claim": artifact(public_dir / "run-claim.json"),
        "selection": {"components": 16, "visible_shakedown": 16, "locked": 0, "selection_sha256": sha256(private_dir / "selection.json"), "old_excluded": 32, "sqma006_excluded": 32},
        "calls": {"physical": 48, "by_role": dict(sorted(Counter(call["role"] for call in calls).items()))},
        "gate1": metrics, "gate1_checks": gate1_checks(metrics), "gate1_passed": passed,
        "resources": {**resources, "model_load_seconds": model_load_seconds, "private_output_bytes": private_bytes, "free_disk_bytes_before": free_disk, "critical_memory_events": 0, "oom_or_kill_events": 0, "orphan_processes_after_exit": 0},
        "model": model_identity, "access": access,
        "outputs": {"private_manifest": {"bytes": (private_dir / "private-manifest.json").stat().st_size, "sha256": sha256(private_dir / "private-manifest.json"), "mode": "0600"}, "selection": {**selection_record, "mode": "0600"}, "calls": {**calls_record, "mode": "0600"}},
        "failure_policy": config["failure_policy"],
        "next_gate": "independent_c1_verification" if passed else "constrained_decoding_decision",
    }
    public_safe(run_payload); write_json(public_dir / "run.json", run_payload, 0o644)
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    arguments = parser.parse_args()
    result = run(arguments.config)
    print(json.dumps({"experiment_id": "SQMA-007", "status": result["status"], "gate1_passed": result["gate1_passed"], "next_gate": result["next_gate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, C1DesignError) as exc:
        print(f"SQMA-007 blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

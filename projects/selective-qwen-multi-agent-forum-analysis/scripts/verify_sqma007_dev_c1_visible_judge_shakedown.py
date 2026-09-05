#!/usr/bin/env python3
"""Independent model-free static and artifact verifier for SQMA-007 Dev-C1."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-007-dev-c1-visible-judge-shakedown.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
INPUT_FIELDS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "fold_id",
    "source_ordinal", "text",
}
OLD_NAMESPACE = "SQMA-003-agent-dev-random-v1"
SQMA006_NAMESPACE = "SQMA-006-d1-fresh-agent-dev-random-v1"
SQMA007_NAMESPACE = "SQMA-007-dev-c1-visible-shakedown-v1"
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
FALLBACK_EVIDENCE = {"schema_version": "evidence-v3", "candidate_emotions": [], "evidence_spans": [], "insufficient_evidence": True}
FALLBACK_CRITIC = {"schema_version": "critic-v3", "recommended_emotions": [], "challenged_emotions": [], "warning_flags": []}
PUBLIC_SENSITIVE_KEYS = {"analysis_text", "allowed_evidence_ids", "component_id", "component_ids", "evidence_spans", "judge_contract", "raw_output", "sample_id", "sample_ids", "source_ordinal", "source_ordinals", "text"}
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


class C1VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise C1VerificationError(message)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def component_rank(namespace: str, component_id: str) -> str:
    return hashlib.sha256(f"{namespace}|{component_id}".encode("utf-8")).hexdigest()


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(contains_placeholder(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_placeholder(child) for child in value)
    return isinstance(value, str) and value.startswith("PLACEHOLDER_")


def validate_static_config(config: Mapping[str, Any]) -> dict[str, Any]:
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
    require(all(authorization.get(key) is False for key in set(authorization) - enabled), "forbidden authorization drift")
    if config.get("design_status") == "FrozenExecutionReady":
        require(all(authorization.get(key) is True for key in enabled), "execution authorization drift")
        require(not contains_placeholder(config.get("implementation", {})), "execution-ready placeholders remain")
    else:
        require(all(value is False for value in authorization.values()), "static authorization drift")
        require(contains_placeholder(config.get("implementation", {})), "v4 placeholders missing")
    require(config.get("inputs", {}).get("forbidden_folds") == [3, 4], "fold boundary drift")
    selection = config.get("selection", {})
    require(
        selection.get("excluded_namespaces") == [OLD_NAMESPACE, SQMA006_NAMESPACE]
        and selection.get("excluded_component_counts") == [32, 32]
        and selection.get("new_namespace") == SQMA007_NAMESPACE
        and selection.get("components") == 16
        and selection.get("stratum") == "visible_shakedown"
        and selection.get("locked_rows") == 0,
        "selection contract drift",
    )
    require(config.get("role_context_allowlist") == ROLE_CONTEXT_ALLOWLIST, "role context drift")
    require(config.get("gate1") == GATE1, "Gate 1 drift")
    require(config.get("call_plan", {}).get("physical_calls") == 48, "call plan drift")
    require(
        config.get("failure_policy", {}).get("next_decision") == "constrained_decoding_decision"
        and config["failure_policy"].get("automatic_prompt_revision") is False,
        "failure policy drift",
    )
    return {
        "schema_version": "sqma-007-static-verification-v1",
        "experiment_id": "SQMA-007", "status": "Passed",
        "execution_authorized": authorization.get("execution_authorized"), "private_accessed": False,
        "model_loaded": False, "locked_content_accessed": False,
        "next_gate": "execute_visible_c1" if authorization.get("execution_authorized") else "freeze_judge_v2_v4_identities",
    }


def representatives(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source in rows:
        require(isinstance(source, Mapping) and set(source) == INPUT_FIELDS, "input schema drift")
        require(source["schema_version"] == "sqma-gold-free-inference-snapshot-v1", "input identity drift")
        require(source["fold_id"] in {0, 1, 2}, "held-out fold entered C1")
        require(type(source["source_ordinal"]) is int, "source ordinal drift")
        row = dict(source); prior = result.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]:
            result[row["component_id"]] = row
    return result


def select_c1_rows(
    rows: Iterable[Mapping[str, Any]], *, expected_components: int | None = 1963
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    by_component = representatives(rows)
    if expected_components is not None:
        require(len(by_component) == expected_components, "component count drift")
    require(len(by_component) >= 80, "insufficient components")
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
        (row for row in by_component.values() if row["component_id"] not in old_ids | sqma006_ids),
        key=lambda row: (component_rank(SQMA007_NAMESPACE, row["component_id"]), row["component_id"]),
    )[:16]
    ids = {row["component_id"] for row in c1}
    require(len(c1) == 16 and not (old_ids & sqma006_ids or old_ids & ids or sqma006_ids & ids), "selection overlap")
    return [
        {**row, "selection_rank": rank, "selection_stratum": "visible_shakedown"}
        for rank, row in enumerate(c1)
    ], old_ids, sqma006_ids


def expected_slots(selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(selected) == 16, "selection count drift")
    slots = [
        {
            "call_ordinal": row["selection_rank"] * 3 + index,
            "selection_rank": row["selection_rank"],
            "selection_stratum": "visible_shakedown", "system_id": "S3",
            "role": role, "call_index": index,
            "temperature": 0.0 if role == "judge" else 0.6,
        }
        for row in selected
        for index, role in enumerate(ROLE_ORDER)
    ]
    require(len(slots) == 48, "call plan drift")
    return slots


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def judge_contract_diagnostics(raw_output: Any, allowed_evidence_ids: Sequence[int]) -> dict[str, Any]:
    result = {
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
        return result
    payload = raw_output.strip()
    used_fence = payload.startswith("```") or payload.endswith("```")
    if used_fence:
        match = JSON_FENCE.fullmatch(payload)
        if match is None:
            return result
        payload = match.group("body").strip()
    try:
        value = json.loads(payload, object_pairs_hook=strict_pairs)
    except (json.JSONDecodeError, ValueError):
        return result
    result["raw_json_parse"] = not used_fence
    if not isinstance(value, dict):
        return result
    keys = list(value)
    result["exact_six_fields"] = set(keys) == set(LABEL_ORDER) and len(keys) == 6
    result["no_extra_or_missing_keys"] = set(keys) == set(LABEL_ORDER) and len(keys) == 6
    if not result["no_extra_or_missing_keys"]:
        return result
    result["all_reference_values_are_arrays"] = all(isinstance(value[label], list) for label in LABEL_ORDER)
    if not result["all_reference_values_are_arrays"]:
        return result
    result["all_reference_items_are_integers"] = all(
        type(item) is int for label in LABEL_ORDER for item in value[label]
    )
    if not result["all_reference_items_are_integers"]:
        return result
    allowed = set(allowed_evidence_ids)
    result["all_reference_ids_allowed"] = all(
        item in allowed for label in LABEL_ORDER for item in value[label]
    )
    if result["exact_six_fields"] and result["all_reference_ids_allowed"]:
        result["reference_normalization_events"] = sum(
            sorted(set(value[label])) != value[label] for label in LABEL_ORDER
        )
        result["duplicate_references_removed"] = sum(
            len(value[label]) - len(dict.fromkeys(value[label])) for label in LABEL_ORDER
        )
        result["reference_order_normalized_slots"] = sum(
            list(dict.fromkeys(value[label])) != sorted(dict.fromkeys(value[label]))
            for label in LABEL_ORDER
        )
        result["rendered_valid"] = True
        result["rendered_labels"] = [label for label in LABEL_ORDER if value[label]]
    return result


def percentile(values: Sequence[float], probability: float) -> float:
    require(bool(values), "empty percentile")
    ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * probability) - 1))]


def derive_gate1(
    calls: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]],
    *, model_load_seconds: float,
) -> dict[str, Any]:
    slots = expected_slots(selected)
    require(len(calls) == 48, "call count drift")
    diagnostics: list[Mapping[str, Any]] = []
    evidence_valid: list[bool] = []; critic_valid: list[bool] = []
    token_hits = unhandled = semantic_repairs = 0
    latency = {role: [] for role in ROLE_ORDER}
    for call, slot in zip(calls, slots, strict=True):
        require(all(call.get(key) == value for key, value in slot.items()), "call schedule drift")
        require(call.get("terminal") is True, "nonterminal call")
        token_hits += int(call.get("token_cap_hit") is True)
        unhandled += int(call.get("unhandled_failure") is True)
        latency[call["role"]].append(float(call["latency_seconds"]))
        if call["role"] == "evidence":
            evidence_valid.append(call.get("canonical_valid") is True)
        elif call["role"] == "critic":
            critic_valid.append(call.get("canonical_valid") is True)
        else:
            observed = call.get("judge_contract")
            require(isinstance(observed, Mapping) and set(observed) == JUDGE_DIAGNOSTIC_FIELDS, "Judge diagnostic schema drift")
            require(observed == judge_contract_diagnostics(call.get("raw_output"), call.get("allowed_evidence_ids", [])), "Judge replay drift")
            diagnostics.append(observed); semantic_repairs += int(observed["semantic_repair_used"])
    count = lambda key: sum(item[key] is True for item in diagnostics)
    projection = 1.25 * 672 * sum(percentile(latency[role], .95) for role in ROLE_ORDER) + float(model_load_seconds)
    return {
        "terminal_calls": 48,
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
            item["reference_normalization_events"] for item in diagnostics
        ),
        "duplicate_references_removed_report_only": sum(
            item["duplicate_references_removed"] for item in diagnostics
        ),
        "reference_order_normalized_slots_report_only": sum(
            item["reference_order_normalized_slots"] for item in diagnostics
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


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    regular_file(path, label); values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]; require(all(isinstance(value, dict) for value in values), f"{label} rows drift"); return values


def artifact(path: Path) -> dict[str, Any]:
    return {"path": path.resolve().relative_to(REPO_ROOT.resolve()).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_record(record: Any, label: str) -> Path:
    require(isinstance(record, Mapping) and set(record) >= {"path", "bytes", "sha256"} and type(record["bytes"]) is int, f"{label} record drift")
    path = checked_path(REPO_ROOT, record["path"], label); observed = regular_file(path, label)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} hash drift"); return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name); spec = importlib.util.spec_from_file_location(name, path); require(spec is not None and spec.loader is not None, f"{name} import unavailable")
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


def read_inputs(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    root = checked_path(REPO_ROOT, config["inputs"]["private_root"], "input root"); rows = []; hashes = []
    for record in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(root, record["path"], "snapshot"); observed = regular_file(path, "snapshot", "0600")
        require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "snapshot drift")
        values = read_jsonl(path, "snapshot"); require(len(values) == record["rows"], "snapshot rows drift"); rows.extend(values); hashes.append(record["sha256"])
    require(len(rows) == 2016, "Agent-Dev rows drift"); return rows, hashes


def expected_selection(selected: Sequence[Mapping[str, Any]], old_ids: set[str], sqma006_ids: set[str]) -> dict[str, Any]:
    return {
        "schema_version": "sqma-007-selection-v1", "experiment_id": "SQMA-007",
        "old_top32_sha256": canonical_digest(sorted(old_ids)),
        "sqma006_fresh32_sha256": canonical_digest(sorted(sqma006_ids)),
        "namespace": SQMA007_NAMESPACE,
        "rows": [{key: row[key] for key in ("selection_rank", "selection_stratum", "sample_id", "component_id", "fold_id", "source_ordinal")} for row in selected],
    }


def prompt_messages(bundle: Mapping[str, Any], role: str, context: Mapping[str, Any]) -> list[dict[str, str]]:
    spec = bundle["roles"][role]; require(spec["visible_fields"] == ROLE_CONTEXT_ALLOWLIST[role] and set(context) == set(spec["visible_fields"]), "prompt context drift")
    example = bundle["judge_format_example"] if role == "judge" else bundle["format_examples"][role]
    system = "\n".join([*bundle["shared_rules"], spec["system"], "Format example for JSON shape and value types only: " + json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":"))])
    return [{"role": "system", "content": system}, {"role": "user", "content": "Input JSON:\n" + json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))}]


def replay_calls(calls: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]], v3_bundle: Mapping[str, Any], v4_bundle: Mapping[str, Any], validator: Any) -> None:
    slots = expected_slots(selected); require(len(calls) == 48, "call count drift"); by_rank = {row["selection_rank"]: row for row in selected}
    role_values: dict[int, dict[str, Any]] = {rank: {} for rank in range(16)}
    for call, slot in zip(calls, slots, strict=True):
        require(isinstance(call, Mapping) and set(call) == CALL_FIELDS and all(call[key] == value for key, value in slot.items()), "call schema/schedule drift")
        row = by_rank[call["selection_rank"]]; require((call["sample_id"], call["component_id"], call["source_ordinal"]) == (row["sample_id"], row["component_id"], row["source_ordinal"]), "call source drift")
        metadata = call["text_meta"]; require(metadata["original_sha256"] == hashlib.sha256(row["text"].encode()).hexdigest() and metadata["analysis_sha256"] == hashlib.sha256(call["analysis_text"].encode()).hexdigest(), "text identity drift")
        context: dict[str, Any] = {"analysis_text": call["analysis_text"], "ontology": validator.ONTOLOGY}
        if call["role"] in {"critic", "judge"}: context["evidence"] = role_values[call["selection_rank"]].get("evidence", FALLBACK_EVIDENCE)
        if call["role"] == "judge":
            context["critic"] = role_values[call["selection_rank"]].get("critic", FALLBACK_CRITIC)
            context["allowed_evidence_ids"] = list(range(len(context["evidence"]["evidence_spans"])))
        require(call["context_sha256"] == canonical_digest(context), "context replay drift")
        bundle = v4_bundle if call["role"] == "judge" else v3_bundle
        require(call["messages_sha256"] == canonical_digest(prompt_messages(bundle, call["role"], context)), "messages replay drift")
        require(call["raw_output_sha256"] == hashlib.sha256(call["raw_output"].encode()).hexdigest(), "raw hash drift")
        require(call["terminal"] is True and call["token_cap_hit"] is (call["finish_reason"] == "length"), "terminal drift")
        if call["role"] in {"evidence", "critic"}:
            parsed = None; error = None
            try: parsed = validator.validate_evidence(call["raw_output"], context) if call["role"] == "evidence" else validator.validate_critic(call["raw_output"], context)
            except validator.AgentOutputError as exc: error = exc.code
            if call["token_cap_hit"]: parsed = None; error = "token_cap_hit"
            require(call["canonical_valid"] is (parsed is not None) and call["validation_error"] == error and call["judge_contract"] is None, "role replay drift")
            if parsed is not None: role_values[call["selection_rank"]][call["role"]] = parsed
        else:
            result = validator.judge_contract_result(call["raw_output"], context); diagnostics = judge_contract_diagnostics(call["raw_output"], context["allowed_evidence_ids"])
            valid = result["rendered_contract_valid"] and not call["token_cap_hit"]
            error = "token_cap_hit" if call["token_cap_hit"] else result["diagnostics"]["error_code"]
            require(
                call["allowed_evidence_ids"] == context["allowed_evidence_ids"]
                and call["canonical_valid"] is valid and call["validation_error"] == error
                and call["judge_contract"] == diagnostics
                and diagnostics["rendered_labels"] == result["derived_labels"]
                and all(
                    diagnostics[key] == result["diagnostics"][key]
                    for key in (
                        "reference_normalization_events", "duplicate_references_removed",
                        "reference_order_normalized_slots",
                    )
                ),
                "Judge replay drift",
            )


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"; violations.extend([path] if key in PUBLIC_SENSITIVE_KEYS else []); violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value): violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(); descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as target: target.write(payload); target.flush(); os.fsync(target.fileno())


def verify_execution(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    require(config_path.resolve() == CONFIG_PATH.resolve(), "noncanonical SQMA-007 config")
    config = read_json(config_path.resolve(), "config"); validate_static_config(config); require(config["design_status"] == "FrozenExecutionReady", "config not execution-ready")
    for section in ("implementation", "prerequisites"):
        for name, record in config[section].items(): verify_record(record, f"{section}.{name}")
    v3_bundle = read_json(verify_record(config["implementation"]["evidence_critic_prompt_v3"], "v3 prompt"), "v3 prompt")
    v4_bundle = read_json(verify_record(config["implementation"]["judge_prompt_v4"], "v4 prompt"), "v4 prompt")
    validator = load_module("sqma007_v4_independent", config["implementation"]["validator_v4"])
    public = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public"); private = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private")
    require(public.is_dir() and private.is_dir() and not (public / "verification.json").exists() and not (public / "complete.json").exists(), "run/verification namespace drift")
    require(sorted(path.name for path in private.iterdir()) == sorted(config["outputs"]["private_allowed_files"]), "private inventory drift")
    total = 0
    for path in private.iterdir(): total += regular_file(path, path.name, "0600").st_size
    selection = read_json(private / "selection.json", "selection"); calls = read_jsonl(private / "calls.jsonl", "calls"); manifest = read_json(private / "private-manifest.json", "manifest")
    rows, input_hashes = read_inputs(config); selected, old_ids, sqma006_ids = select_c1_rows(rows)
    require(selection == expected_selection(selected, old_ids, sqma006_ids), "selection replay drift")
    replay_calls(calls, selected, v3_bundle, v4_bundle, validator)
    run = read_json(public / "run.json", "run"); claim = read_json(public / "run-claim.json", "claim")
    metrics = derive_gate1(calls, selected, model_load_seconds=run["resources"]["model_load_seconds"]); checks = gate1_checks(metrics)
    require(gate1_passes(metrics) and run["gate1"] == metrics and run["gate1_checks"] == checks and run["gate1_passed"] is True, "independent Gate 1 failed")
    require(run["config"] == artifact(config_path.resolve()) and run["status"] == "CompletedAwaitingVerification" and run["next_gate"] == "independent_c1_verification", "run identity drift")
    require(claim["config"] == artifact(config_path.resolve()) and claim["planned_calls"] == 48 and claim["locked_rows"] == 0, "claim drift")
    require(manifest["input_snapshot_sha256"] == input_hashes and manifest["gate1_passed"] is True and manifest["next_gate"] == "independent_verification", "manifest drift")
    require(run["resources"]["private_output_bytes"] == total and not public_sensitive_paths(run) and not public_sensitive_paths(claim), "resource/privacy drift")
    verification = {"schema_version": "sqma-007-verification-v1", "experiment_id": "SQMA-007", "status": "Passed", "verified_at_utc": utc_now(), "config": artifact(config_path.resolve()), "run": artifact(public / "run.json"), "calls_verified": 48, "visible_rows_verified": 16, "locked_rows_accessed": 0, "gate1": metrics, "gate1_checks": checks, "next_gate": "complete_sqma007"}
    complete = {"schema_version": "sqma-007-complete-v1", "experiment_id": "SQMA-007", "status": "Complete", "sqma007_complete": True, "ordinary_decoding_c1_gate": "Passed", "accuracy_scored": False, "gold_accessed": False, "automatic_prompt_revision": False, "automatic_next_stage": False, "next_gate": "register_next_d1_stage"}
    write_json(public / "verification.json", verification); write_json(public / "complete.json", complete); return verification, complete


def verify_static(path: Path) -> dict[str, Any]:
    require(path.expanduser().resolve() == CONFIG_PATH.resolve(), "noncanonical SQMA-007 config")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "config root drift")
    result = validate_static_config(value)
    if value.get("design_status") == "FrozenExecutionReady":
        for section in ("implementation", "prerequisites"):
            for name, record in value[section].items():
                verify_record(record, f"{section}.{name}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--static-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.static_only:
        result = verify_static(Path(arguments.config))
    else:
        verification, complete = verify_execution(Path(arguments.config))
        result = {"experiment_id": "SQMA-007", "status": verification["status"], "sqma007_complete": complete["sqma007_complete"]}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, C1VerificationError) as exc:
        print(f"SQMA-007 static verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

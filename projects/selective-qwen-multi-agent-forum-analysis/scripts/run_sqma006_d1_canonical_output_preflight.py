#!/usr/bin/env python3
"""Execution-ready producer for the fresh SQMA-006 D1 preflight.

The frozen config binds the v3 prompt, schema, canonicalizer, grammar contract,
fresh selection, 120-call plan, resources, and gate. Importing this module
performs no I/O or model loading; execution begins only through ``run``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import importlib
import importlib.metadata
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
from typing import Any, Iterable, Mapping, Sequence


sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-006-d1-canonical-output-preflight.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
INPUT_FIELDS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "fold_id",
    "source_ordinal", "text",
}
OLD_SELECTION_NAMESPACE = "SQMA-003-agent-dev-random-v1"
NEW_SELECTION_NAMESPACE = "SQMA-006-d1-fresh-agent-dev-random-v1"
GENERATION_NAMESPACE = "SQMA-006-d1-generation-v1"
EXPECTED_INPUT_ROWS = 2016
EXPECTED_COMPONENTS = 1963
EXPECTED_SELECTION = 32
EXPECTED_CALLS = 120
EXPECTED_GENERATED_TOKEN_CAP = 27_648
S3_ROLES = ("evidence", "critic", "judge")
ROLE_CONTEXT_ALLOWLIST = {
    "evidence": ["analysis_text", "ontology"],
    "critic": ["analysis_text", "ontology", "evidence"],
    "judge": ["analysis_text", "ontology", "evidence", "critic"],
    "single": ["analysis_text", "ontology"],
}
CALL_FIELDS = {
    "schema_version", "call_ordinal", "selection_rank", "selection_stratum",
    "sample_id", "component_id", "source_ordinal", "system_id", "role",
    "call_index", "seed", "analysis_text", "analysis_text_sha256", "text_meta",
    "context_sha256", "messages_sha256", "prompt_ids_sha256", "terminal",
    "finish_reason", "token_cap_hit", "raw_output", "raw_output_sha256", "raw_strict_valid",
    "raw_strict_error", "canonical_valid", "canonical_error", "canonical_output",
    "final_labels", "evidence_spans_total", "evidence_spans_exact",
    "out_of_ontology_labels", "prefill_tokens", "generated_tokens",
    "latency_seconds",
}
TEXT_META_FIELDS = {
    "original_sha256", "analysis_sha256", "original_token_count",
    "analysis_token_count", "was_truncated", "model_free_truncation_replay",
}
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text", "canonical_output", "component_id", "component_ids",
    "evidence_spans", "final_labels", "gold", "labels", "raw_output",
    "sample_id", "sample_ids", "source_ordinal", "source_ordinals", "text",
}
FALLBACK_EVIDENCE = {
    "schema_version": "evidence-v3", "candidate_emotions": [],
    "evidence_spans": [], "insufficient_evidence": True,
}
FALLBACK_CRITIC = {
    "schema_version": "critic-v3", "recommended_emotions": [],
    "challenged_emotions": [], "warning_flags": [],
}
PASS_GATE = {
    "canonical_system_output_valid_rate_overall_minimum": 0.98,
    "canonical_system_output_valid_rate_per_role_minimum": 0.95,
    "maximum_locked_s3_fallback_rows": 1,
    "maximum_token_cap_hits": 0,
    "evidence_exact_substring_rate": 1.0,
    "out_of_ontology_labels": 0,
    "mean_modal_exact_label_set_agreement_minimum": 0.85,
    "maximum_full_tune_projected_wall_seconds": 172800.0,
}
TOP_LEVEL_FIELDS = {
    "schema_version", "experiment_id", "tier", "stage", "design_status",
    "registered_at", "authorization", "implementation", "prerequisites", "inputs",
    "selection", "model", "runtime", "generation", "canonicalization",
    "role_context_allowlist", "call_plan", "diagnostics", "pass_gate", "resources",
    "outputs", "commands", "next_gate",
}
FROZEN_SCALARS = {
    "schema_version": "sqma-006-d1-canonical-output-preflight-v1",
    "experiment_id": "SQMA-006", "tier": "Minor",
    "stage": "d1-fresh-canonical-output-preflight",
    "design_status": "FrozenExecutionReady", "registered_at": "2026-09-04",
    "next_gate": "execute_fresh_gold_free_preflight",
}
FROZEN_SECTION_DIGESTS = {
    "authorization": "6efd2ebc9d23cb89b891add55ed2fe95676270118d3aaf19d8c381fc684b6c3e",
    "prerequisites": "1f274fb3164d0cd035473275bf13d91a33607e005908c047053dbedf1021d7ee",
    "inputs": "bd73abcc075b6ac3e35dd926698bdbbd72515d9861a6844e959372eb28b7d2bb",
    "selection": "ce5211ad4b37564375a646a00bbdb0c58cf3743f0f7560a95ca9d674ae0cc175",
    "model": "c3cc2d0f5a33d938a85b6a421da041a4480df64f39683678047194261ea60bd2",
    "runtime": "ad02c64e9ee1e136f3216d8fa977cdcb79bb48a5a03491f38f138b947c129061",
    "generation": "e8198a87f654fc33e7c878c66c03240ac2b0d2e83b0216933d503f9df90cc3bf",
    "canonicalization": "f225f38d1c132e742481e988b1716bd20e9b7915cca3d3489f6e9de351eef34d",
    "call_plan": "4036a000665c91198223953157299130c3cddff518136bc57758abc397817743",
    "role_context_allowlist": "61b05447f551192be9d934a70221e43ef178716b639ffc24ef37c44571c83649",
    "diagnostics": "5ddf64085603e51d6bf1ba4aa71a9376c0726c4510992ebad20052fedf062141",
    "pass_gate": "5307b72e67b7f8948464d48c7d2c149f3f1b9ca7675e0ecacaa6c0c839ca00fc",
    "resources": "c262f35089ed96696996d22eac8cc23d70036e83c834fc3a1e0cfabe7367e93f",
    "outputs": "1e26ed54fc428fe2f6fd9e65f2a0d0f876e5619725a2ef98f17f58e94715b461",
    "commands": "89ba33dc4127b17d0c479abc1e318af2991a0c8356b8f789184cacdec1ec172d",
}
IMPLEMENTATION_PATHS = {
    "protocol": "projects/selective-qwen-multi-agent-forum-analysis/protocols/sqma-006-d1-canonical-output-preflight.md",
    "prompt_bundle_v3": "projects/selective-qwen-multi-agent-forum-analysis/prompts/agent-bundle-v3-classifier-free.json",
    "output_schema_v3": "projects/selective-qwen-multi-agent-forum-analysis/schemas/agent-output-v3.schema.json",
    "canonicalizer_v3": "projects/selective-qwen-multi-agent-forum-analysis/scripts/validate_agent_output_v3.py",
    "runner": "projects/selective-qwen-multi-agent-forum-analysis/scripts/run_sqma006_d1_canonical_output_preflight.py",
    "verifier": "projects/selective-qwen-multi-agent-forum-analysis/scripts/verify_sqma006_d1_canonical_output_preflight.py",
    "tests": "projects/selective-qwen-multi-agent-forum-analysis/tests/test_sqma006_d1_canonical_output_preflight.py",
    "validator_tests_v3": "projects/selective-qwen-multi-agent-forum-analysis/tests/test_validate_agent_output_v3.py",
}


class D1PreflightError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise D1PreflightError(message)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def component_rank(namespace: str, component_id: str) -> str:
    return hashlib.sha256(f"{namespace}|{component_id}".encode("utf-8")).hexdigest()


def seed_for(namespace: str, system: str, sample: str, role: str, call_index: int) -> int:
    material = f"{namespace}|{system}|{sample}|{role}|{call_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big", signed=False)


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
    for key, expected_digest in FROZEN_SECTION_DIGESTS.items():
        require(canonical_digest(config.get(key)) == expected_digest, f"frozen section drift: {key}")
    implementation = config.get("implementation")
    require(
        isinstance(implementation, Mapping)
        and set(implementation) == {*IMPLEMENTATION_PATHS, "grammar_v3"},
        "implementation inventory drift",
    )
    for key, expected_path in IMPLEMENTATION_PATHS.items():
        record = implementation[key]
        expected_keys = {"path", "bytes", "sha256", "api"} if key == "canonicalizer_v3" else {"path", "bytes", "sha256"}
        require(isinstance(record, Mapping) and set(record) == expected_keys, f"implementation record drift: {key}")
        require(
            record["path"] == expected_path and type(record["bytes"]) is int
            and record["bytes"] > 0 and isinstance(record["sha256"], str)
            and len(record["sha256"]) == 64
            and set(record["sha256"]) <= set("0123456789abcdef"),
            f"implementation identity drift: {key}",
        )
    require(
        implementation["canonicalizer_v3"]["api"]
        == "validation_result(role,raw_output,context); diagnostics_from_raw(role,raw_output,context); final_labels_from_validated(role,value)",
        "canonicalizer API drift",
    )
    require(
        isinstance(implementation["grammar_v3"], Mapping)
        and set(implementation["grammar_v3"]) == {"mode", "implementation", "version", "sha256"},
        "grammar implementation record drift",
    )
    require(config.get("schema_version") == "sqma-006-d1-canonical-output-preflight-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-006", "experiment identity drift")
    require(config.get("stage") == "d1-fresh-canonical-output-preflight", "stage drift")
    require(
        config.get("design_status")
        in {"StaticDesignAwaitingV3IdentityBinding", "FrozenExecutionReady"},
        "design status drift",
    )
    authorization = config.get("authorization", {})
    enabled = {"execution_authorized", "private_input_access", "model_loading", "generation"}
    forbidden = {
        "gold_access", "classifier_access", "adapter_loading", "training",
        "validation_access", "test_access", "fold3_access", "fold4_access",
        "network", "automatic_next_stage",
    }
    require(all(authorization.get(key) is False for key in forbidden), "forbidden authorization drift")
    if config.get("design_status") == "FrozenExecutionReady":
        require(all(authorization.get(key) is True for key in enabled), "execution authorization drift")
        require(not contains_placeholder(config.get("implementation", {})), "execution-ready implementation has placeholders")
    else:
        require(all(authorization.get(key) is False for key in enabled), "static authorization drift")
        require(contains_placeholder(config.get("implementation", {})), "v3 placeholders unexpectedly absent")

    inputs = config.get("inputs", {})
    records = inputs.get("gold_free_snapshots", [])
    require(
        len(records) == 3
        and [record.get("fold_id") for record in records] == [0, 1, 2]
        and sum(record.get("rows", 0) for record in records) == EXPECTED_INPUT_ROWS,
        "Agent-Dev input scope drift",
    )
    require(inputs.get("forbidden_folds") == [3, 4], "held-out fold boundary drift")
    require(inputs.get("allowed_fields") == sorted(INPUT_FIELDS), "input field allowlist drift")

    selection = config.get("selection", {})
    require(
        selection.get("old_namespace_exclusion") == OLD_SELECTION_NAMESPACE
        and selection.get("old_namespace_exclusion_count") == 32
        and selection.get("fresh_namespace") == NEW_SELECTION_NAMESPACE
        and selection.get("components") == EXPECTED_SELECTION
        and selection.get("shakedown_ranks") == [0, 7]
        and selection.get("locked_ranks") == [8, 31]
        and selection.get("single_pool_locked_ranks") == [8, 15]
        and selection.get("row_per_component") == "minimum_source_ordinal"
        and selection.get("text_gold_or_model_features_used") is False,
        "fresh selection contract drift",
    )

    call_plan = config.get("call_plan", {})
    require(
        call_plan
        == {
            "S3_rows": 32, "S3_calls_per_row": 3, "S3_calls": 96,
            "single_pool_rows": 8, "single_pool_calls_per_row": 3,
            "single_pool_calls": 24, "physical_call_cap": 120,
            "S1_reuses_first_single_pool_call": True,
            "SC_reuses_all_three_single_pool_calls": True,
            "extra_single_or_provisional_system_calls": 0,
            "accuracy_or_method_comparison": False,
        },
        "120-call plan drift",
    )
    require(config.get("pass_gate") == PASS_GATE, "canonical gate drift")
    require(config.get("diagnostics", {}).get("raw_strict_validity") == "report_only_not_a_gate", "raw diagnostic boundary drift")
    require(config.get("role_context_allowlist") == ROLE_CONTEXT_ALLOWLIST, "role context allowlist drift")
    grammar = config.get("implementation", {}).get("grammar_v3", {})
    require(
        grammar.get("mode") == "no_native_grammar_exact_json_fence_canonicalizer_v1"
        and grammar.get("implementation") == "validate_agent_output_v3.validation_result",
        "v3 grammar mode drift",
    )
    require(
        grammar.get("sha256")
        == canonical_digest(
            {
                "mode": grammar.get("mode"),
                "implementation": grammar.get("implementation"),
                "version": grammar.get("version"),
            }
        ),
        "v3 grammar identity drift",
    )
    require(config.get("generation", {}).get("seed_namespace") == GENERATION_NAMESPACE, "generation namespace drift")
    require(config.get("resources", {}).get("maximum_generated_tokens") == EXPECTED_GENERATED_TOKEN_CAP, "token budget drift")


def assert_execution_ready(config: Mapping[str, Any]) -> None:
    require(config.get("authorization", {}).get("execution_authorized") is True, "SQMA-006 execution is not authorized")
    require(not contains_placeholder(config.get("implementation", {})), "v3 identities remain unresolved")
    require(config.get("design_status") == "FrozenExecutionReady", "SQMA-006 config is not execution-ready")


def representatives(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    by_component: dict[str, dict[str, Any]] = {}
    for source in rows:
        require(isinstance(source, Mapping) and set(source) == INPUT_FIELDS, "input row schema drift")
        require(
            source["schema_version"] == "sqma-gold-free-inference-snapshot-v1"
            and source["fold_id"] in {0, 1, 2}
            and isinstance(source["sample_id"], str)
            and isinstance(source["component_id"], str)
            and type(source["source_ordinal"]) is int
            and isinstance(source["text"], str),
            "input row value drift",
        )
        row = dict(source)
        prior = by_component.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]:
            by_component[row["component_id"]] = row
    return by_component


def select_fresh_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    old_namespace: str = OLD_SELECTION_NAMESPACE,
    fresh_namespace: str = NEW_SELECTION_NAMESPACE,
    count: int = EXPECTED_SELECTION,
    expected_components: int | None = EXPECTED_COMPONENTS,
) -> tuple[list[dict[str, Any]], set[str]]:
    require(old_namespace != fresh_namespace and count > 0, "selection namespace drift")
    by_component = representatives(rows)
    if expected_components is not None:
        require(len(by_component) == expected_components, "Agent-Dev component count drift")
    require(len(by_component) >= count * 2, "insufficient components for disjoint selection")
    ordered_old = sorted(
        by_component.values(),
        key=lambda row: (component_rank(old_namespace, row["component_id"]), row["component_id"]),
    )
    excluded = {row["component_id"] for row in ordered_old[:count]}
    eligible = [row for row in by_component.values() if row["component_id"] not in excluded]
    selected = sorted(
        eligible,
        key=lambda row: (component_rank(fresh_namespace, row["component_id"]), row["component_id"]),
    )[:count]
    require(len(selected) == count and not ({row["component_id"] for row in selected} & excluded), "fresh selection overlap")
    output = []
    for rank, row in enumerate(selected):
        output.append(
            {
                **row,
                "selection_rank": rank,
                "selection_stratum": "shakedown" if rank < 8 else "locked",
            }
        )
    return output, excluded


def selection_payload(selected: Sequence[Mapping[str, Any]], excluded: set[str]) -> dict[str, Any]:
    require(len(selected) == EXPECTED_SELECTION and len(excluded) == 32, "selection payload count drift")
    return {
        "schema_version": "sqma-006-selection-v1",
        "experiment_id": "SQMA-006",
        "old_namespace": OLD_SELECTION_NAMESPACE,
        "old_top32_exclusion_sha256": canonical_digest(sorted(excluded)),
        "fresh_namespace": NEW_SELECTION_NAMESPACE,
        "rows": [
            {
                key: row[key]
                for key in (
                    "selection_rank", "selection_stratum", "sample_id", "component_id",
                    "fold_id", "source_ordinal",
                )
            }
            for row in selected
        ],
    }


def planned_call_slots(selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(selected) == EXPECTED_SELECTION, "selection count drift")
    slots: list[dict[str, Any]] = []
    for row in selected:
        rank = row["selection_rank"]
        require(rank == len(slots) // 3, "selection rank drift")
        for call_index, role in enumerate(S3_ROLES):
            slots.append(
                {
                    "selection_rank": rank, "selection_stratum": row["selection_stratum"],
                    "system_id": "S3", "role": role, "call_index": call_index,
                }
            )
    for row in selected[8:16]:
        for call_index in range(3):
            slots.append(
                {
                    "selection_rank": row["selection_rank"], "selection_stratum": "locked",
                    "system_id": "single_pool", "role": "single",
                    "call_index": call_index,
                }
            )
    require(len(slots) == EXPECTED_CALLS, "physical call plan drift")
    return slots


def percentile(values: Sequence[float], probability: float) -> float:
    require(bool(values), "empty percentile input")
    ordered = sorted(float(value) for value in values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * probability) - 1))]


def validate_labels(labels: Any) -> list[str]:
    require(isinstance(labels, list), "final labels must be a list")
    require(labels == sorted(set(labels), key=LABEL_ORDER.index), "final label drift")
    return labels


def assessment_from_v3(
    validator: Any, role: str, raw_output: str, context: Mapping[str, Any],
    *, token_cap_hit: bool = False,
) -> dict[str, Any]:
    """Translate the frozen v3 validator result into the call-record contract."""

    result = validator.validation_result(role, raw_output, dict(context))
    require(
        isinstance(result, Mapping)
        and set(result)
        == {"raw_valid", "canonical_valid", "canonical_json", "value", "error_code", "error_path"},
        "v3 validation-result schema drift",
    )
    canonical_valid = bool(result["canonical_valid"]) and not token_cap_hit
    value = result["value"] if canonical_valid else None
    error = "token_cap_hit" if token_cap_hit else (
        None if canonical_valid else f"{result['error_code']}:{result['error_path']}"
    )
    labels = (
        validator.final_labels_from_validated(role, value)
        if canonical_valid and role in {"judge", "single"}
        else []
    )
    diagnostics = validator.diagnostics_from_raw(role, raw_output, context)
    require(
        isinstance(diagnostics, Mapping)
        and set(diagnostics)
        == {"out_of_ontology_labels", "evidence_spans_total", "evidence_spans_exact"}
        and all(type(child) is int and child >= 0 for child in diagnostics.values())
        and diagnostics["evidence_spans_exact"] <= diagnostics["evidence_spans_total"],
        "v3 diagnostics schema drift",
    )
    return {
        "raw_strict_valid": bool(result["raw_valid"]),
        "raw_strict_error": None if result["raw_valid"] else "not_bare_strict_v3_output",
        "canonical_valid": canonical_valid,
        "canonical_error": error,
        "canonical_output": value,
        "final_labels": list(labels),
        **dict(diagnostics),
    }


def derive_metrics(
    calls: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    *,
    model_load_seconds: float,
    seed_namespace: str = GENERATION_NAMESPACE,
) -> dict[str, Any]:
    slots = planned_call_slots(selected)
    require(len(calls) == EXPECTED_CALLS, "call count drift")
    selected_by_rank = {row["selection_rank"]: row for row in selected}
    canonical_by_role: dict[str, list[bool]] = {role: [] for role in (*S3_ROLES, "single")}
    raw_by_role: dict[str, list[bool]] = {role: [] for role in (*S3_ROLES, "single")}
    s3_valid: dict[int, list[bool]] = {rank: [] for rank in range(8, 32)}
    single_votes: dict[int, list[tuple[str, ...]]] = {rank: [] for rank in range(8, 16)}
    evidence_total = evidence_exact = ontology_errors = token_hits = 0
    latencies: dict[str, list[float]] = {role: [] for role in (*S3_ROLES, "single")}

    for ordinal, (record, slot) in enumerate(zip(calls, slots, strict=True)):
        require(isinstance(record, Mapping) and set(record) == CALL_FIELDS, "call schema drift")
        require(record["schema_version"] == "sqma-006-call-v1" and record["call_ordinal"] == ordinal, "call ordinal drift")
        require(all(record[key] == slot[key] for key in slot), "call slot drift")
        source = selected_by_rank[record["selection_rank"]]
        require(
            record["sample_id"] == source["sample_id"]
            and record["component_id"] == source["component_id"]
            and record["source_ordinal"] == source["source_ordinal"],
            "call selection identity drift",
        )
        require(
            record["seed"] == seed_for(
                seed_namespace, record["system_id"], record["sample_id"],
                record["role"], record["call_index"],
            ),
            "call seed drift",
        )
        for key in ("terminal", "token_cap_hit", "raw_strict_valid", "canonical_valid"):
            require(type(record[key]) is bool, f"{key} type drift")
        require(record["terminal"] is True, "nonterminal call")
        require(not record["token_cap_hit"] or record["canonical_valid"] is False, "token-cap call cannot be canonical-valid")
        require(
            isinstance(record["analysis_text"], str)
            and bool(record["analysis_text"])
            and record["analysis_text_sha256"]
            == hashlib.sha256(record["analysis_text"].encode("utf-8")).hexdigest(),
            "analysis text identity drift",
        )
        require(isinstance(record["text_meta"], Mapping), "text metadata drift")
        for key in ("context_sha256", "messages_sha256", "prompt_ids_sha256"):
            require(
                isinstance(record[key], str) and len(record[key]) == 64
                and set(record[key]) <= set("0123456789abcdef"),
                f"{key} drift",
            )
        require(
            isinstance(record["raw_output"], str)
            and record["raw_output_sha256"]
            == hashlib.sha256(record["raw_output"].encode("utf-8")).hexdigest(),
            "raw output identity drift",
        )
        require(
            (record["raw_strict_error"] is None) is record["raw_strict_valid"]
            and (record["canonical_error"] is None) is record["canonical_valid"],
            "call validity/error drift",
        )
        labels = validate_labels(record["final_labels"])
        if not record["canonical_valid"]:
            require(record["canonical_output"] is None and labels == [], "invalid canonical output must be empty")
        else:
            require(isinstance(record["canonical_output"], Mapping), "canonical output missing")
        require(
            type(record["evidence_spans_total"]) is int
            and type(record["evidence_spans_exact"]) is int
            and 0 <= record["evidence_spans_exact"] <= record["evidence_spans_total"],
            "evidence diagnostic drift",
        )
        require(type(record["out_of_ontology_labels"]) is int and record["out_of_ontology_labels"] >= 0, "ontology diagnostic drift")
        require(type(record["prefill_tokens"]) is int and record["prefill_tokens"] >= 0, "prefill token drift")
        require(type(record["generated_tokens"]) is int and record["generated_tokens"] >= 0, "generated token drift")
        require(
            type(record["latency_seconds"]) in (int, float)
            and not isinstance(record["latency_seconds"], bool)
            and math.isfinite(record["latency_seconds"])
            and record["latency_seconds"] >= 0,
            "latency drift",
        )
        role = record["role"]
        latencies[role].append(float(record["latency_seconds"]))
        token_hits += int(record["token_cap_hit"])
        if record["selection_stratum"] == "locked":
            canonical_by_role[role].append(record["canonical_valid"])
            raw_by_role[role].append(record["raw_strict_valid"])
            evidence_total += record["evidence_spans_total"]
            evidence_exact += record["evidence_spans_exact"]
            ontology_errors += record["out_of_ontology_labels"]
            if record["system_id"] == "S3":
                s3_valid[record["selection_rank"]].append(record["canonical_valid"])
            else:
                single_votes[record["selection_rank"]].append(tuple(labels))

    locked_canonical = [value for values in canonical_by_role.values() for value in values]
    locked_raw = [value for values in raw_by_role.values() for value in values]
    agreements = [max(Counter(single_votes[rank]).values()) / 3 for rank in range(8, 16)]
    projection = 1.25 * 672 * (
        percentile(latencies["evidence"], 0.95)
        + percentile(latencies["critic"], 0.95)
        + percentile(latencies["judge"], 0.95)
        + 3 * percentile(latencies["single"], 0.95)
    ) + float(model_load_seconds)
    require(sum(record["generated_tokens"] for record in calls) <= EXPECTED_GENERATED_TOKEN_CAP, "generated-token budget drift")
    return {
        "planned_calls_complete": True,
        "planned_call_terminal_rate": 1.0,
        "canonical_system_output_valid_rate": sum(locked_canonical) / len(locked_canonical),
        "canonical_system_output_valid_rate_per_role": {
            role: sum(values) / len(values) for role, values in canonical_by_role.items()
        },
        "locked_s3_fallback_rows": sum(not all(values) for values in s3_valid.values()),
        "token_cap_hits": token_hits,
        "evidence_exact_substring_rate": 1.0 if evidence_total == 0 else evidence_exact / evidence_total,
        "out_of_ontology_labels": ontology_errors,
        "mean_modal_exact_label_set_agreement": sum(agreements) / len(agreements),
        "full_tune_projected_wall_seconds": projection,
        "raw_strict_valid_rate_report_only": sum(locked_raw) / len(locked_raw),
        "raw_strict_valid_rate_per_role_report_only": {
            role: sum(values) / len(values) for role, values in raw_by_role.items()
        },
    }


def gate_checks(metrics: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "planned_calls": metrics.get("planned_calls_complete") is True
        and metrics.get("planned_call_terminal_rate") == 1.0,
        "canonical_overall": metrics["canonical_system_output_valid_rate"]
        >= PASS_GATE["canonical_system_output_valid_rate_overall_minimum"],
        "canonical_per_role": all(
            value >= PASS_GATE["canonical_system_output_valid_rate_per_role_minimum"]
            for value in metrics["canonical_system_output_valid_rate_per_role"].values()
        ),
        "s3_fallback": metrics["locked_s3_fallback_rows"]
        <= PASS_GATE["maximum_locked_s3_fallback_rows"],
        "token_hits": metrics["token_cap_hits"] <= PASS_GATE["maximum_token_cap_hits"],
        "evidence_exact": metrics["evidence_exact_substring_rate"]
        == PASS_GATE["evidence_exact_substring_rate"],
        "ontology": metrics["out_of_ontology_labels"] == PASS_GATE["out_of_ontology_labels"],
        "agreement": metrics["mean_modal_exact_label_set_agreement"]
        >= PASS_GATE["mean_modal_exact_label_set_agreement_minimum"],
        "projection": metrics["full_tune_projected_wall_seconds"]
        <= PASS_GATE["maximum_full_tune_projected_wall_seconds"],
    }


def gate_passes(metrics: Mapping[str, Any]) -> bool:
    return all(gate_checks(metrics).values())


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
    resolved_root = root.resolve()
    path = (root / relative).resolve()
    require(path == resolved_root or resolved_root in path.parents, f"{label} path escapes root")
    current = root
    for part in Path(relative).parts:
        current /= part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains symlink")
    return path


def regular_file(path: Path, label: str, *, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(
        stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode)
        and observed.st_uid == os.getuid() and observed.st_nlink == 1,
        f"{label} file identity drift",
    )
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def read_json(path: Path, label: str = "JSON") -> dict[str, Any]:
    regular_file(path, label)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "config root drift")
    return value


def artifact(path: Path, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def verify_record(record: Any, label: str) -> Path:
    require(
        isinstance(record, Mapping) and set(record) >= {"path", "bytes", "sha256"}
        and type(record["bytes"]) is int and record["bytes"] > 0,
        f"{label} artifact record drift",
    )
    path = checked_path(REPO_ROOT, record["path"], label)
    observed = regular_file(path, label)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} artifact identity drift")
    return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"{name} import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json_exclusive(path: Path, value: Mapping[str, Any], mode: int) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload); target.flush(); os.fsync(target.fileno())
    path.chmod(mode)


def write_jsonl_exclusive(path: Path, values: Sequence[Mapping[str, Any]], mode: int) -> None:
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


def verify_implementation_and_prerequisites(config: Mapping[str, Any]) -> tuple[Path, Any]:
    implementation = config["implementation"]
    for key, record in implementation.items():
        if key != "grammar_v3":
            verify_record(record, f"implementation.{key}")
    for key, record in config["prerequisites"].items():
        verify_record(record, f"prerequisite.{key}")
    prompt_path = verify_record(implementation["prompt_bundle_v3"], "v3 prompt")
    validator = load_module("sqma006_validator_v3", implementation["canonicalizer_v3"])
    return prompt_path, validator


def read_inputs(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    private_root = checked_path(REPO_ROOT, config["inputs"]["private_root"], "SQMA-002 private root")
    rows: list[dict[str, Any]] = []
    hashes: list[str] = []
    for record in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(private_root, record["path"], "gold-free snapshot")
        observed = regular_file(path, "gold-free snapshot", mode="0600")
        require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "gold-free snapshot identity drift")
        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        require(len(values) == record["rows"] and all(row.get("fold_id") == record["fold_id"] for row in values), "snapshot row/fold drift")
        rows.extend(values); hashes.append(record["sha256"])
    require(len(rows) == EXPECTED_INPUT_ROWS, "Agent-Dev row count drift")
    return rows, hashes


def verify_model(config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    model = config["model"]
    archive = Path(os.environ.get(model["archive_root_env"], model["audited_archive_root"])).expanduser().resolve()
    require(archive.is_dir(), "model archive unavailable")
    manifest_path = checked_path(archive, model["manifest_path"], "model manifest")
    observed = regular_file(manifest_path, "model manifest")
    require(observed.st_size == model["manifest_bytes"] and sha256(manifest_path) == model["manifest_sha256"], "model manifest identity drift")
    manifest = read_json(manifest_path, "model manifest")
    require(manifest.get("repo_id") == model["repo_id"] and manifest.get("revision") == model["revision"], "model revision drift")
    inventory = manifest.get("mlx_bf16", {}).get("files")
    require(isinstance(inventory, list) and len(inventory) == model["file_count"], "model inventory drift")
    model_root = checked_path(archive, model["relative_path"], "model root")
    total = 0
    for record in inventory:
        path = checked_path(model_root, record["path"], "model file")
        file_stat = regular_file(path, "model file")
        require(file_stat.st_size == record["bytes"] and sha256(path) == record["sha256"], "model file identity drift")
        total += record["bytes"]
    require(total == model["total_bytes"], "model byte total drift")
    return model_root, {
        "repo_id": model["repo_id"], "revision": model["revision"],
        "manifest_sha256": model["manifest_sha256"], "file_count": len(inventory),
        "total_bytes": total, "adapter": None,
    }


def truncate_analysis_text(tokenizer: Any, text: str, cap: int) -> tuple[str, dict[str, Any]]:
    token_ids = list(tokenizer.encode(text, add_special_tokens=False))
    if len(token_ids) <= cap:
        analysis = text
    else:
        analysis = tokenizer.decode(token_ids[:cap], skip_special_tokens=True)
    require(isinstance(analysis, str) and bool(analysis), "analysis-text truncation failed")
    analysis_ids = list(tokenizer.encode(analysis, add_special_tokens=False))
    require(len(analysis_ids) <= cap, "analysis text exceeds cap")
    truncated = len(token_ids) > cap
    return analysis, {
        "original_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "analysis_sha256": hashlib.sha256(analysis.encode("utf-8")).hexdigest(),
        "original_token_count": len(token_ids), "analysis_token_count": len(analysis_ids),
        "was_truncated": truncated, "model_free_truncation_replay": not truncated,
    }


def prompt_messages(bundle: Mapping[str, Any], role: str, context: Mapping[str, Any]) -> list[dict[str, str]]:
    spec = bundle["roles"][role]
    require(spec["visible_fields"] == ROLE_CONTEXT_ALLOWLIST[role] and set(context) == set(spec["visible_fields"]), "role context allowlist drift")
    example = json.dumps(bundle["format_examples"][role], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    system = "\n".join([
        *bundle["shared_rules"], spec["system"],
        "Format example for JSON shape and value types only: " + example,
    ])
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "Input JSON:\n" + json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))},
    ]


def render_prompt(tokenizer: Any, bundle: Mapping[str, Any], role: str, context: Mapping[str, Any], context_cap: int, max_new: int) -> tuple[list[int], list[dict[str, str]]]:
    messages = prompt_messages(bundle, role, context)
    prompt_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, return_dict=False, add_generation_prompt=True,
        enable_thinking=False,
    )
    if isinstance(prompt_ids, Mapping):
        prompt_ids = prompt_ids["input_ids"]
    ids = [int(value) for value in prompt_ids]
    require(bool(ids) and len(ids) + max_new <= context_cap, "prompt exceeds context cap")
    return ids, messages


def numeric_summary(values: Sequence[float]) -> dict[str, float]:
    require(bool(values), "empty numeric summary")
    ordered = sorted(float(value) for value in values)
    return {
        "min": ordered[0], "median": percentile(ordered, .5),
        "p95": percentile(ordered, .95), "max": ordered[-1],
        "mean": sum(ordered) / len(ordered),
    }


def resource_snapshot(started: float, mx: Any, generated_tokens: int) -> dict[str, Any]:
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform.startswith("linux"):
        rss *= 1024
    return {
        "wall_seconds": time.monotonic() - started,
        "peak_rss_bytes": rss, "mlx_peak_bytes": int(mx.get_peak_memory()),
        "generated_tokens": generated_tokens,
    }


def check_resources(config: Mapping[str, Any], observed: Mapping[str, Any]) -> None:
    limits = config["resources"]
    require(observed["wall_seconds"] <= limits["maximum_wall_seconds"], "wall budget exceeded")
    require(observed["peak_rss_bytes"] <= limits["maximum_process_rss_bytes"], "RSS budget exceeded")
    require(observed["mlx_peak_bytes"] <= limits["maximum_mlx_peak_bytes"], "MLX budget exceeded")
    require(observed["generated_tokens"] <= limits["maximum_generated_tokens"], "generated-token budget exceeded")


def run(config_argument: str) -> dict[str, Any]:
    started = time.monotonic()
    started_at = utc_now()
    supplied = Path(config_argument).expanduser().resolve()
    require(supplied == CONFIG_PATH.resolve(), "noncanonical SQMA-006 config")
    config = read_json(supplied, "SQMA-006 config")
    validate_static_config(config)
    assert_execution_ready(config)
    prompt_path, validator = verify_implementation_and_prerequisites(config)
    bundle = read_json(prompt_path, "v3 prompt bundle")
    require(
        bundle.get("schema_version") == "sqma-agent-prompt-bundle-v3-classifier-free"
        and bundle.get("roles", {}).keys() == ROLE_CONTEXT_ALLOWLIST.keys()
        and bundle.get("ontology", {}).get("label_order") == validator.ONTOLOGY["label_order"]
        and bundle.get("ontology", {}).get("instruction") == validator.ONTOLOGY["instruction"],
        "v3 prompt/validator identity drift",
    )

    outputs = config["outputs"]
    public_dir = checked_path(REPO_ROOT, outputs["public_attempt_dir"], "public output")
    private_dir = checked_path(REPO_ROOT, outputs["private_attempt_dir"], "private output")
    require(not os.path.lexists(public_dir) and not os.path.lexists(private_dir), "SQMA-006 output namespace exists")
    free_disk = __import__("shutil").disk_usage(REPO_ROOT).free
    require(free_disk >= config["resources"]["minimum_free_disk_bytes"], "insufficient free disk")
    public_dir.mkdir(parents=True, mode=0o755, exist_ok=False)
    claim = {
        "schema_version": "sqma-006-run-claim-v1", "experiment_id": "SQMA-006",
        "status": "ClaimedBeforePrivateInputOrModelLoad", "claimed_at_utc": utc_now(),
        "config": artifact(supplied), "planned_calls": EXPECTED_CALLS,
        "fresh_selection": True, "classifier_free": True, "gold_access": False,
        "training": False, "grammar_mode": config["implementation"]["grammar_v3"]["mode"],
        "next_gate": "fresh_gold_free_preflight_producer",
    }
    public_safe(claim)
    write_json_exclusive(public_dir / "run-claim.json", claim, 0o644)

    rows, input_hashes = read_inputs(config)
    selected, excluded = select_fresh_rows(rows)
    selection = selection_payload(selected, excluded)
    private_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    private_dir.chmod(0o700)
    write_json_exclusive(private_dir / "selection.json", selection, 0o600)

    model_path, model_identity = verify_model(config)
    runtime = config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve(), "runtime executable drift")
    require(platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime platform drift")
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
        }
    )
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    for package, version in runtime["packages"].items():
        require(importlib.metadata.version(package) == version, f"runtime package drift: {package}")
    mx.reset_peak_memory()
    load_started = time.monotonic()
    model, tokenizer = load(str(model_path), adapter_path=None, lazy=False)
    model_load_seconds = time.monotonic() - load_started
    sampler = make_sampler(
        temp=config["generation"]["temperature"], top_p=config["generation"]["top_p"],
        top_k=config["generation"]["top_k"],
    )
    ontology = validator.ONTOLOGY
    calls: list[dict[str, Any]] = []
    row_analysis: dict[int, tuple[str, dict[str, Any]]] = {}
    generated_total = 0

    def generate_call(
        row: Mapping[str, Any], system: str, role: str, call_index: int,
        context_fields: Mapping[str, Any],
    ) -> dict[str, Any]:
        nonlocal generated_total
        analysis_text, text_meta = row_analysis[row["selection_rank"]]
        context = {"analysis_text": analysis_text, "ontology": ontology, **context_fields}
        max_new = config["generation"]["max_new_tokens"][role]
        prompt_ids, messages = render_prompt(
            tokenizer, bundle, role, context,
            config["generation"]["context_token_cap"], max_new,
        )
        seed = seed_for(
            config["generation"]["seed_namespace"], system, row["sample_id"], role,
            call_index,
        )
        mx.random.seed(seed)
        pieces: list[str] = []
        final_meta: dict[str, Any] | None = None
        stream = stream_generate(
            model, tokenizer, prompt_ids, max_tokens=max_new, sampler=sampler
        )
        call_started = time.monotonic()
        try:
            for response in stream:
                pieces.append(response.text)
                final_meta = {
                    "finish_reason": response.finish_reason,
                    "prompt_tokens": int(response.prompt_tokens),
                    "generated_tokens": int(response.generation_tokens),
                }
                check_resources(config, resource_snapshot(started, mx, generated_total))
        finally:
            stream.close()
        latency = time.monotonic() - call_started
        require(final_meta is not None and final_meta["finish_reason"] is not None, "generation lacks terminal metadata")
        require(final_meta["prompt_tokens"] == len(prompt_ids), "prompt token accounting drift")
        generated_total += final_meta["generated_tokens"]
        check_resources(config, resource_snapshot(started, mx, generated_total))
        raw_output = "".join(pieces)
        token_cap_hit = final_meta["finish_reason"] == "length"
        assessment = assessment_from_v3(
            validator, role, raw_output, context, token_cap_hit=token_cap_hit
        )
        record = {
            "schema_version": "sqma-006-call-v1", "call_ordinal": len(calls),
            "selection_rank": row["selection_rank"],
            "selection_stratum": row["selection_stratum"],
            "sample_id": row["sample_id"], "component_id": row["component_id"],
            "source_ordinal": row["source_ordinal"], "system_id": system,
            "role": role, "call_index": call_index, "seed": seed,
            "analysis_text": analysis_text,
            "analysis_text_sha256": hashlib.sha256(analysis_text.encode("utf-8")).hexdigest(),
            "text_meta": text_meta, "context_sha256": canonical_digest(context),
            "messages_sha256": canonical_digest(messages),
            "prompt_ids_sha256": canonical_digest(prompt_ids), "terminal": True,
            "finish_reason": final_meta["finish_reason"], "token_cap_hit": token_cap_hit,
            "raw_output": raw_output,
            "raw_output_sha256": hashlib.sha256(raw_output.encode("utf-8")).hexdigest(),
            **assessment, "prefill_tokens": len(prompt_ids),
            "generated_tokens": final_meta["generated_tokens"],
            "latency_seconds": latency,
        }
        require(set(record) == CALL_FIELDS, "producer call schema drift")
        calls.append(record)
        return record

    for row in selected:
        row_analysis[row["selection_rank"]] = truncate_analysis_text(
            tokenizer, row["text"], config["generation"]["analysis_text_token_cap"]
        )
        evidence_call = generate_call(row, "S3", "evidence", 0, {})
        evidence = evidence_call["canonical_output"] if evidence_call["canonical_valid"] else FALLBACK_EVIDENCE
        critic_call = generate_call(row, "S3", "critic", 1, {"evidence": evidence})
        critic = critic_call["canonical_output"] if critic_call["canonical_valid"] else FALLBACK_CRITIC
        generate_call(row, "S3", "judge", 2, {"evidence": evidence, "critic": critic})
        gc.collect(); mx.clear_cache()

    for row in selected[8:16]:
        for call_index in range(3):
            generate_call(row, "single_pool", "single", call_index, {})
        gc.collect(); mx.clear_cache()

    require(len(calls) == EXPECTED_CALLS, "physical call count drift")
    metrics = derive_metrics(
        calls, selected, model_load_seconds=model_load_seconds,
        seed_namespace=config["generation"]["seed_namespace"],
    )
    passed = gate_passes(metrics)
    write_jsonl_exclusive(private_dir / "calls.jsonl", calls, 0o600)
    selection_record = artifact(private_dir / "selection.json", root=private_dir)
    calls_record = artifact(private_dir / "calls.jsonl", root=private_dir)
    access = {
        "gold_accessed": False, "classifier_accessed": False,
        "adapter_loaded": False, "model_loaded": True, "training_executed": False,
        "network_accessed": False, "fold3_accessed": False, "fold4_accessed": False,
        "validation_accessed": False, "test_accessed": False,
    }
    manifest = {
        "schema_version": "sqma-006-private-manifest-v1", "experiment_id": "SQMA-006",
        "status": "SealedAwaitingVerification" if passed else "SealedCapabilityGateFailed",
        "input_snapshot_sha256": input_hashes,
        "old_top32_exclusion_sha256": selection["old_top32_exclusion_sha256"],
        "selection": selection_record, "calls_artifact": calls_record,
        "model_identity": model_identity,
        "prompt_identity": {
            "bundle_sha256": config["implementation"]["prompt_bundle_v3"]["sha256"],
            "schema_sha256": config["implementation"]["output_schema_v3"]["sha256"],
            "validator_sha256": config["implementation"]["canonicalizer_v3"]["sha256"],
            "grammar_contract_sha256": config["implementation"]["grammar_v3"]["sha256"],
        },
        "call_plan": {"physical_calls": EXPECTED_CALLS, "S3_calls": 96, "single_pool_calls": 24},
        "access": access, "gate_passed": passed,
        "next_gate": "independent_verification" if passed else "stop_capability_gate_failed",
    }
    write_json_exclusive(private_dir / "private-manifest.json", manifest, 0o600)
    private_files = sorted(path.name for path in private_dir.iterdir() if path.is_file())
    require(private_files == sorted(outputs["private_allowed_files"]), "private inventory drift")
    private_bytes = sum(path.stat().st_size for path in private_dir.iterdir() if path.is_file())
    require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private output budget exceeded")
    resources = resource_snapshot(started, mx, generated_total)
    check_resources(config, resources)
    role_counts = dict(sorted(Counter(call["role"] for call in calls).items()))
    run_payload = {
        "schema_version": "sqma-006-run-v1", "experiment_id": "SQMA-006",
        "tier": config["tier"], "stage": config["stage"],
        "status": "CompletedAwaitingVerification" if passed else "CompletedCapabilityGateFailed",
        "started_at_utc": started_at, "completed_at_utc": utc_now(),
        "config": artifact(supplied), "run_claim": artifact(public_dir / "run-claim.json"),
        "claim_boundary": "Fresh classifier-free gold-free D1 preflight only; no gold, classifier, adapter, training, held-out folds, validation, test, network, native grammar, or semantic repair.",
        "selection": {
            "components": 32, "shakedown": 8, "locked": 24,
            "old_top32_excluded": 32,
            "old_top32_exclusion_sha256": selection["old_top32_exclusion_sha256"],
            "selection_sha256": sha256(private_dir / "selection.json"),
        },
        "calls": {"physical": len(calls), "by_role": role_counts, "S1_reused": True, "SC_reused": True},
        "gate": metrics, "gate_checks": gate_checks(metrics), "gate_passed": passed,
        "resources": {
            **resources, "model_load_seconds": model_load_seconds,
            "private_output_bytes": private_bytes, "free_disk_bytes_before": free_disk,
            "critical_memory_events": 0, "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "model": model_identity, "access": access,
        "outputs": {
            "private_manifest": {
                "bytes": (private_dir / "private-manifest.json").stat().st_size,
                "sha256": sha256(private_dir / "private-manifest.json"), "mode": "0600",
            },
            "calls": {**calls_record, "mode": "0600"},
            "selection": {**selection_record, "mode": "0600"},
        },
        "next_gate": "independent_preflight_verification" if passed else "stop_capability_gate_failed",
    }
    public_safe(run_payload)
    public_size = sum(path.stat().st_size for path in public_dir.iterdir() if path.is_file())
    encoded = len((json.dumps(run_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    require(public_size + encoded <= config["resources"]["maximum_public_output_bytes"], "public output budget exceeded")
    write_json_exclusive(public_dir / "run.json", run_payload, 0o644)
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    arguments = parser.parse_args()
    result = run(arguments.config)
    print(
        json.dumps(
            {
                "experiment_id": "SQMA-006", "status": result["status"],
                "gate_passed": result["gate_passed"], "next_gate": result["next_gate"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, D1PreflightError) as exc:
        print(f"SQMA-006 blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

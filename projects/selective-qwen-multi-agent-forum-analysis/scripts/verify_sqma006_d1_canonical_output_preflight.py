#!/usr/bin/env python3
"""Independent model-free static and artifact verifier for SQMA-006 D1.

Static-only verification checks the frozen execution-ready identities without
resolving private inputs. After a producer run, artifact verification replays
fresh selection, v3 canonicalization, the 120-call plan, and every gate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
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
ASSESSMENT_FIELDS = {
    "raw_strict_valid", "raw_strict_error", "canonical_valid", "canonical_error",
    "canonical_output", "final_labels", "evidence_spans_total",
    "evidence_spans_exact", "out_of_ontology_labels",
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


class D1VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise D1VerificationError(message)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def validate_static_config(config: Mapping[str, Any]) -> dict[str, Any]:
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
        require(not contains_placeholder(config.get("implementation", {})), "execution-ready placeholders remain")
    else:
        require(all(authorization.get(key) is False for key in enabled), "static authorization drift")
        require(contains_placeholder(config.get("implementation", {})), "static placeholders missing")
    selection = config.get("selection", {})
    require(
        selection.get("old_namespace_exclusion") == OLD_SELECTION_NAMESPACE
        and selection.get("old_namespace_exclusion_count") == 32
        and selection.get("fresh_namespace") == NEW_SELECTION_NAMESPACE
        and selection.get("components") == 32
        and selection.get("shakedown_ranks") == [0, 7]
        and selection.get("locked_ranks") == [8, 31]
        and selection.get("single_pool_locked_ranks") == [8, 15],
        "selection contract drift",
    )
    require(
        config.get("call_plan")
        == {
            "S3_rows": 32, "S3_calls_per_row": 3, "S3_calls": 96,
            "single_pool_rows": 8, "single_pool_calls_per_row": 3,
            "single_pool_calls": 24, "physical_call_cap": 120,
            "S1_reuses_first_single_pool_call": True,
            "SC_reuses_all_three_single_pool_calls": True,
            "extra_single_or_provisional_system_calls": 0,
            "accuracy_or_method_comparison": False,
        },
        "call plan drift",
    )
    require(config.get("pass_gate") == PASS_GATE, "pass gate drift")
    require(config.get("diagnostics", {}).get("raw_strict_validity") == "report_only_not_a_gate", "raw validity became a gate")
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
    require(config.get("resources", {}).get("maximum_generated_tokens") == EXPECTED_GENERATED_TOKEN_CAP, "token cap drift")
    return {
        "schema_version": "sqma-006-static-verification-v1",
        "experiment_id": "SQMA-006",
        "status": "Passed",
        "execution_authorized": authorization.get("execution_authorized"),
        "v3_identities_resolved": not contains_placeholder(config.get("implementation", {})),
        "private_accessed": False,
        "model_loaded": False,
        "next_gate": (
            "execute_fresh_gold_free_preflight"
            if authorization.get("execution_authorized")
            else "bind_v3_immutable_identities_and_run_static_verification"
        ),
    }


def representatives(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source in rows:
        require(isinstance(source, Mapping) and set(source) == INPUT_FIELDS, "input schema drift")
        require(source["schema_version"] == "sqma-gold-free-inference-snapshot-v1", "input identity drift")
        require(source["fold_id"] in {0, 1, 2}, "held-out fold entered Agent-Dev selection")
        require(type(source["source_ordinal"]) is int, "source ordinal drift")
        row = dict(source)
        prior = result.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]:
            result[row["component_id"]] = row
    return result


def select_fresh_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    expected_components: int | None = EXPECTED_COMPONENTS,
) -> tuple[list[dict[str, Any]], set[str]]:
    by_component = representatives(rows)
    if expected_components is not None:
        require(len(by_component) == expected_components, "component count drift")
    require(len(by_component) >= 64, "insufficient disjoint components")
    old = sorted(
        by_component.values(),
        key=lambda row: (component_rank(OLD_SELECTION_NAMESPACE, row["component_id"]), row["component_id"]),
    )[:32]
    excluded = {row["component_id"] for row in old}
    fresh = sorted(
        (row for row in by_component.values() if row["component_id"] not in excluded),
        key=lambda row: (component_rank(NEW_SELECTION_NAMESPACE, row["component_id"]), row["component_id"]),
    )[:32]
    require(len(fresh) == 32 and not ({row["component_id"] for row in fresh} & excluded), "fresh selection overlap")
    return [
        {**row, "selection_rank": rank, "selection_stratum": "shakedown" if rank < 8 else "locked"}
        for rank, row in enumerate(fresh)
    ], excluded


def expected_slots(selected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(selected) == 32, "selection count drift")
    slots = [
        {
            "selection_rank": row["selection_rank"],
            "selection_stratum": row["selection_stratum"],
            "system_id": "S3", "role": role, "call_index": index,
        }
        for row in selected
        for index, role in enumerate(S3_ROLES)
    ]
    slots.extend(
        {
            "selection_rank": row["selection_rank"], "selection_stratum": "locked",
            "system_id": "single_pool", "role": "single", "call_index": index,
        }
        for row in selected[8:16]
        for index in range(3)
    )
    require(len(slots) == EXPECTED_CALLS, "120-call plan drift")
    return slots


def validate_labels(value: Any) -> list[str]:
    require(isinstance(value, list), "labels must be a list")
    require(value == sorted(set(value), key=LABEL_ORDER.index), "label order drift")
    return value


def fallback_evidence() -> dict[str, Any]:
    return {
        "schema_version": "evidence-v3", "candidate_emotions": [],
        "evidence_spans": [], "insufficient_evidence": True,
    }


def fallback_critic() -> dict[str, Any]:
    return {
        "schema_version": "critic-v3", "recommended_emotions": [],
        "challenged_emotions": [], "warning_flags": [],
    }


def assessment_from_v3(
    validator: Any, role: str, raw_output: str, context: Mapping[str, Any],
    *, token_cap_hit: bool,
) -> dict[str, Any]:
    result = validator.validation_result(role, raw_output, dict(context))
    require(
        isinstance(result, Mapping)
        and set(result)
        == {"raw_valid", "canonical_valid", "canonical_json", "value", "error_code", "error_path"},
        "v3 validation-result schema drift",
    )
    canonical_valid = bool(result["canonical_valid"]) and not token_cap_hit
    value = result["value"] if canonical_valid else None
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
        "canonical_error": "token_cap_hit" if token_cap_hit else (
            None if canonical_valid else f"{result['error_code']}:{result['error_path']}"
        ),
        "canonical_output": value,
        "final_labels": list(labels),
        **dict(diagnostics),
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


def replay_canonical_calls(
    calls: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    canonicalizer: Any,
    bundle: Mapping[str, Any] | None = None,
) -> None:
    """Independently replay v3 canonicalization once its interface is frozen.

    The v3 module must export ONTOLOGY, validation_result, and
    final_labels_from_validated.
    """

    slots = expected_slots(selected)
    require(len(calls) == EXPECTED_CALLS, "call count drift")
    by_rank = {row["selection_rank"]: row for row in selected}
    s3_outputs: dict[int, dict[str, Any]] = {rank: {} for rank in range(32)}
    for ordinal, (record, slot) in enumerate(zip(calls, slots, strict=True)):
        require(isinstance(record, Mapping) and set(record) == CALL_FIELDS, "call field drift")
        require(record["schema_version"] == "sqma-006-call-v1" and record["call_ordinal"] == ordinal, "call ordinal drift")
        require(all(record[key] == value for key, value in slot.items()), "call slot drift")
        row = by_rank[record["selection_rank"]]
        require(
            (record["sample_id"], record["component_id"], record["source_ordinal"])
            == (row["sample_id"], row["component_id"], row["source_ordinal"]),
            "call source drift",
        )
        require(record["analysis_text_sha256"] == text_sha256(record["analysis_text"]), "analysis hash drift")
        metadata = record["text_meta"]
        require(isinstance(metadata, Mapping) and set(metadata) == TEXT_META_FIELDS, "text metadata schema drift")
        require(
            metadata["original_sha256"] == text_sha256(row["text"])
            and metadata["analysis_sha256"] == record["analysis_text_sha256"],
            "text metadata identity drift",
        )
        require(
            type(metadata["original_token_count"]) is int
            and type(metadata["analysis_token_count"]) is int
            and type(metadata["was_truncated"]) is bool
            and metadata["model_free_truncation_replay"] is (not metadata["was_truncated"]),
            "text metadata type drift",
        )
        if not metadata["was_truncated"]:
            require(record["analysis_text"] == row["text"], "untruncated text replay drift")
        require(record["raw_output_sha256"] == text_sha256(record["raw_output"]), "raw hash drift")
        require(
            record["seed"] == seed_for(
                GENERATION_NAMESPACE, record["system_id"], record["sample_id"],
                record["role"], record["call_index"],
            ),
            "seed drift",
        )
        context: dict[str, Any] = {
            "analysis_text": record["analysis_text"], "ontology": canonicalizer.ONTOLOGY,
        }
        if record["system_id"] == "S3" and record["role"] in {"critic", "judge"}:
            context["evidence"] = s3_outputs[record["selection_rank"]].get(
                "evidence", fallback_evidence()
            )
        if record["system_id"] == "S3" and record["role"] == "judge":
            context["critic"] = s3_outputs[record["selection_rank"]].get(
                "critic", fallback_critic()
            )
        require(record["context_sha256"] == canonical_digest(context), "context replay drift")
        if bundle is not None:
            require(
                record["messages_sha256"]
                == canonical_digest(prompt_messages(bundle, record["role"], context)),
                "messages replay drift",
            )
        require(
            isinstance(record["prompt_ids_sha256"], str)
            and len(record["prompt_ids_sha256"]) == 64
            and set(record["prompt_ids_sha256"]) <= set("0123456789abcdef"),
            "prompt token identity drift",
        )
        require(
            record["terminal"] is True
            and isinstance(record["finish_reason"], str)
            and record["token_cap_hit"] is (record["finish_reason"] == "length"),
            "terminal/token-cap drift",
        )
        for key in ("prefill_tokens", "generated_tokens"):
            require(type(record[key]) is int and record[key] >= 0, f"{key} drift")
        require(
            type(record["latency_seconds"]) in (int, float)
            and not isinstance(record["latency_seconds"], bool)
            and math.isfinite(record["latency_seconds"])
            and record["latency_seconds"] >= 0,
            "latency drift",
        )
        assessment = assessment_from_v3(
            canonicalizer, record["role"], record["raw_output"], context,
            token_cap_hit=record["token_cap_hit"],
        )
        require(isinstance(assessment, Mapping) and set(assessment) == ASSESSMENT_FIELDS, "v3 assessment schema drift")
        for key in ASSESSMENT_FIELDS:
            require(record[key] == assessment[key], f"canonical replay drift: {key}")
        validate_labels(record["final_labels"])
        require(
            (record["canonical_valid"] and isinstance(record["canonical_output"], Mapping))
            or (not record["canonical_valid"] and record["canonical_output"] is None and record["final_labels"] == []),
            "canonical output/final-label drift",
        )
        if record["system_id"] == "S3" and record["canonical_valid"]:
            s3_outputs[record["selection_rank"]][record["role"]] = record["canonical_output"]


def percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    require(bool(ordered), "empty percentile")
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * probability) - 1))]


def derive_metrics(
    calls: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    *,
    model_load_seconds: float,
) -> dict[str, Any]:
    slots = expected_slots(selected)
    require(len(calls) == EXPECTED_CALLS, "call count drift")
    canonical: dict[str, list[bool]] = {role: [] for role in (*S3_ROLES, "single")}
    raw: dict[str, list[bool]] = {role: [] for role in (*S3_ROLES, "single")}
    s3: dict[int, list[bool]] = {rank: [] for rank in range(8, 32)}
    votes: dict[int, list[tuple[str, ...]]] = {rank: [] for rank in range(8, 16)}
    latency: dict[str, list[float]] = {role: [] for role in (*S3_ROLES, "single")}
    exact = total = ontology = token_hits = 0
    for ordinal, (record, slot) in enumerate(zip(calls, slots, strict=True)):
        require(isinstance(record, Mapping) and set(record) == CALL_FIELDS, "call schema drift")
        require(record["call_ordinal"] == ordinal and all(record[key] == value for key, value in slot.items()), "call plan replay drift")
        validate_labels(record["final_labels"])
        role = record["role"]
        latency[role].append(float(record["latency_seconds"]))
        token_hits += int(record["token_cap_hit"])
        if record["selection_stratum"] == "locked":
            canonical[role].append(record["canonical_valid"])
            raw[role].append(record["raw_strict_valid"])
            exact += record["evidence_spans_exact"]
            total += record["evidence_spans_total"]
            ontology += record["out_of_ontology_labels"]
            if record["system_id"] == "S3":
                s3[record["selection_rank"]].append(record["canonical_valid"])
            else:
                votes[record["selection_rank"]].append(tuple(record["final_labels"]))
    flattened = [value for values in canonical.values() for value in values]
    raw_flattened = [value for values in raw.values() for value in values]
    agreements = [max(Counter(votes[rank]).values()) / 3 for rank in range(8, 16)]
    projection = 1.25 * 672 * (
        percentile(latency["evidence"], .95)
        + percentile(latency["critic"], .95)
        + percentile(latency["judge"], .95)
        + 3 * percentile(latency["single"], .95)
    ) + float(model_load_seconds)
    require(sum(record["generated_tokens"] for record in calls) <= EXPECTED_GENERATED_TOKEN_CAP, "generated-token budget drift")
    return {
        "planned_calls_complete": True, "planned_call_terminal_rate": 1.0,
        "canonical_system_output_valid_rate": sum(flattened) / len(flattened),
        "canonical_system_output_valid_rate_per_role": {
            role: sum(values) / len(values) for role, values in canonical.items()
        },
        "locked_s3_fallback_rows": sum(not all(values) for values in s3.values()),
        "token_cap_hits": token_hits,
        "evidence_exact_substring_rate": 1.0 if total == 0 else exact / total,
        "out_of_ontology_labels": ontology,
        "mean_modal_exact_label_set_agreement": sum(agreements) / len(agreements),
        "full_tune_projected_wall_seconds": projection,
        "raw_strict_valid_rate_report_only": sum(raw_flattened) / len(raw_flattened),
        "raw_strict_valid_rate_per_role_report_only": {
            role: sum(values) / len(values) for role, values in raw.items()
        },
    }


def gate_checks(metrics: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "planned_calls": metrics["planned_calls_complete"] is True
        and metrics["planned_call_terminal_rate"] == 1.0,
        "canonical_overall": metrics["canonical_system_output_valid_rate"] >= 0.98,
        "canonical_per_role": all(
            value >= 0.95
            for value in metrics["canonical_system_output_valid_rate_per_role"].values()
        ),
        "s3_fallback": metrics["locked_s3_fallback_rows"] <= 1,
        "token_hits": metrics["token_cap_hits"] == 0,
        "evidence_exact": metrics["evidence_exact_substring_rate"] == 1.0,
        "ontology": metrics["out_of_ontology_labels"] == 0,
        "agreement": metrics["mean_modal_exact_label_set_agreement"] >= 0.85,
        "projection": metrics["full_tune_projected_wall_seconds"] <= 172800.0,
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
    root = root.resolve(); path = (root / relative).resolve()
    require(path == root or root in path.parents, f"{label} path escapes root")
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


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    regular_file(path, label)
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    require(all(isinstance(value, dict) for value in values), f"{label} row drift")
    return values


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(REPO_ROOT.resolve()).as_posix(),
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


def verify_private_record(record: Any, root: Path, name: str) -> Path:
    require(isinstance(record, Mapping) and set(record) == {"path", "bytes", "sha256"}, f"private {name} record drift")
    require(record["path"] == name, f"private {name} path drift")
    path = root / name
    observed = regular_file(path, name, mode="0600")
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"private {name} hash drift")
    return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"{name} import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_implementations(config: Mapping[str, Any]) -> tuple[dict[str, Any], Any]:
    for key, record in config["implementation"].items():
        if key != "grammar_v3":
            verify_record(record, f"implementation.{key}")
    for key, record in config["prerequisites"].items():
        verify_record(record, f"prerequisite.{key}")
    bundle = read_json(
        verify_record(config["implementation"]["prompt_bundle_v3"], "v3 prompt"),
        "v3 prompt",
    )
    validator = load_module("sqma006_v3_for_independent_verifier", config["implementation"]["canonicalizer_v3"])
    require(
        bundle.get("schema_version") == "sqma-agent-prompt-bundle-v3-classifier-free"
        and bundle.get("ontology", {}).get("label_order") == validator.ONTOLOGY["label_order"]
        and bundle.get("ontology", {}).get("instruction") == validator.ONTOLOGY["instruction"],
        "v3 prompt/validator drift",
    )
    return bundle, validator


def read_inputs(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    root = checked_path(REPO_ROOT, config["inputs"]["private_root"], "SQMA-002 private root")
    rows: list[dict[str, Any]] = []; hashes: list[str] = []
    for record in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(root, record["path"], "gold-free snapshot")
        observed = regular_file(path, "gold-free snapshot", mode="0600")
        require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "input identity drift")
        values = read_jsonl(path, "gold-free snapshot")
        require(len(values) == record["rows"] and all(row.get("fold_id") == record["fold_id"] for row in values), "input fold/row drift")
        rows.extend(values); hashes.append(record["sha256"])
    require(len(rows) == 2016, "Agent-Dev row count drift")
    return rows, hashes


def expected_selection_payload(selected: Sequence[Mapping[str, Any]], excluded: set[str]) -> dict[str, Any]:
    return {
        "schema_version": "sqma-006-selection-v1", "experiment_id": "SQMA-006",
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


def validate_private_tree(root: Path, allowed: Sequence[str], maximum_bytes: int) -> int:
    observed = os.lstat(root)
    require(stat.S_ISDIR(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), "private root type drift")
    require(observed.st_uid == os.getuid() and f"{stat.S_IMODE(observed.st_mode):04o}" == "0700", "private root permission drift")
    files = sorted(path.name for path in root.iterdir() if path.is_file())
    require(files == sorted(allowed) and all(not path.is_dir() for path in root.iterdir()), "private inventory drift")
    total = 0
    for path in root.iterdir():
        total += regular_file(path, path.name, mode="0600").st_size
    require(total <= maximum_bytes, "private output byte cap drift")
    return total


def verify_model_inventory(config: Mapping[str, Any]) -> dict[str, Any]:
    model = config["model"]
    archive = Path(os.environ.get(model["archive_root_env"], model["audited_archive_root"])).expanduser().resolve()
    require(archive.is_dir(), "model archive unavailable")
    manifest_path = checked_path(archive, model["manifest_path"], "model manifest")
    observed = regular_file(manifest_path, "model manifest")
    require(observed.st_size == model["manifest_bytes"] and sha256(manifest_path) == model["manifest_sha256"], "model manifest drift")
    manifest = read_json(manifest_path, "model manifest")
    inventory = manifest.get("mlx_bf16", {}).get("files")
    require(manifest.get("repo_id") == model["repo_id"] and manifest.get("revision") == model["revision"], "model identity drift")
    require(isinstance(inventory, list) and len(inventory) == model["file_count"], "model inventory count drift")
    model_root = checked_path(archive, model["relative_path"], "model root")
    total = 0
    for record in inventory:
        path = checked_path(model_root, record["path"], "model file")
        file_stat = regular_file(path, "model file")
        require(file_stat.st_size == record["bytes"] and sha256(path) == record["sha256"], "model file drift")
        total += record["bytes"]
    require(total == model["total_bytes"], "model total-byte drift")
    return {
        "repo_id": model["repo_id"], "revision": model["revision"],
        "manifest_sha256": model["manifest_sha256"], "file_count": len(inventory),
        "total_bytes": total, "adapter": None,
    }


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (value.startswith("sample-") or value.startswith("component-")):
        violations.append(prefix)
    return violations


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload); target.flush(); os.fsync(target.fileno())


def verify_execution(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    supplied = config_path.expanduser().resolve()
    require(supplied == CONFIG_PATH.resolve(), "noncanonical SQMA-006 config")
    config = read_json(supplied, "SQMA-006 config")
    validate_static_config(config)
    require(config.get("design_status") == "FrozenExecutionReady", "config is not frozen execution-ready")
    bundle, validator = verify_implementations(config)
    model_identity = verify_model_inventory(config)
    public_root = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public root")
    private_root = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private root")
    require(public_root.is_dir() and private_root.is_dir(), "run roots missing")
    require(not (public_root / "verification.json").exists() and not (public_root / "complete.json").exists(), "verification namespace exists")
    require(
        sorted(path.name for path in public_root.iterdir() if path.is_file())
        == ["run-claim.json", "run.json"]
        and all(not path.is_dir() for path in public_root.iterdir()),
        "pre-verification public inventory drift",
    )
    private_bytes = validate_private_tree(
        private_root, config["outputs"]["private_allowed_files"],
        config["resources"]["maximum_private_output_bytes"],
    )
    selection_path = private_root / "selection.json"
    calls_path = private_root / "calls.jsonl"
    manifest_path = private_root / "private-manifest.json"
    selection = read_json(selection_path, "selection")
    calls = read_jsonl(calls_path, "calls")
    manifest = read_json(manifest_path, "private manifest")
    rows, input_hashes = read_inputs(config)
    selected, excluded = select_fresh_rows(rows)
    require(selection == expected_selection_payload(selected, excluded), "fresh selection replay drift")
    require(
        set(manifest)
        == {
            "schema_version", "experiment_id", "status", "input_snapshot_sha256",
            "old_top32_exclusion_sha256", "selection", "calls_artifact",
            "model_identity", "prompt_identity", "call_plan", "access",
            "gate_passed", "next_gate",
        }
        and manifest["schema_version"] == "sqma-006-private-manifest-v1"
        and manifest["experiment_id"] == "SQMA-006"
        and manifest["status"] == "SealedAwaitingVerification",
        "private manifest drift",
    )
    verify_private_record(manifest["selection"], private_root, "selection.json")
    verify_private_record(manifest["calls_artifact"], private_root, "calls.jsonl")
    require(manifest["input_snapshot_sha256"] == input_hashes, "input lineage drift")
    require(manifest["old_top32_exclusion_sha256"] == selection["old_top32_exclusion_sha256"], "old exclusion identity drift")
    require(manifest["model_identity"] == model_identity, "private model identity drift")
    require(
        manifest["call_plan"]
        == {"physical_calls": 120, "S3_calls": 96, "single_pool_calls": 24}
        and manifest["next_gate"] == "independent_verification",
        "private call plan/next gate drift",
    )
    require(
        manifest["prompt_identity"]
        == {
            "bundle_sha256": config["implementation"]["prompt_bundle_v3"]["sha256"],
            "schema_sha256": config["implementation"]["output_schema_v3"]["sha256"],
            "validator_sha256": config["implementation"]["canonicalizer_v3"]["sha256"],
            "grammar_contract_sha256": config["implementation"]["grammar_v3"]["sha256"],
        },
        "private prompt identity drift",
    )
    expected_access = {
        "gold_accessed": False, "classifier_accessed": False,
        "adapter_loaded": False, "model_loaded": True, "training_executed": False,
        "network_accessed": False, "fold3_accessed": False, "fold4_accessed": False,
        "validation_accessed": False, "test_accessed": False,
    }
    require(manifest["access"] == expected_access and manifest["gate_passed"] is True, "private access/gate drift")
    replay_canonical_calls(calls, selected, validator, bundle)
    run = read_json(public_root / "run.json", "public run")
    claim = read_json(public_root / "run-claim.json", "run claim")
    metrics = derive_metrics(calls, selected, model_load_seconds=run["resources"]["model_load_seconds"])
    checks = gate_checks(metrics)
    require(gate_passes(metrics), "independent canonical capability gate failed")
    require(
        run.get("schema_version") == "sqma-006-run-v1"
        and run.get("experiment_id") == "SQMA-006"
        and run.get("tier") == config["tier"]
        and run.get("stage") == config["stage"]
        and run.get("status") == "CompletedAwaitingVerification"
        and run.get("config") == artifact(supplied)
        and run.get("run_claim") == artifact(public_root / "run-claim.json")
        and run.get("gate") == metrics
        and run.get("gate_checks") == checks
        and run.get("gate_passed") is True
        and run.get("next_gate") == "independent_preflight_verification",
        "public run replay drift",
    )
    require(
        claim.get("schema_version") == "sqma-006-run-claim-v1"
        and claim.get("experiment_id") == "SQMA-006"
        and claim.get("status") == "ClaimedBeforePrivateInputOrModelLoad"
        and claim.get("config") == artifact(supplied)
        and claim.get("planned_calls") == EXPECTED_CALLS
        and claim.get("grammar_mode") == config["implementation"]["grammar_v3"]["mode"]
        and claim.get("fresh_selection") is True
        and claim.get("classifier_free") is True
        and claim.get("gold_access") is False
        and claim.get("training") is False
        and claim.get("next_gate") == "fresh_gold_free_preflight_producer",
        "run claim drift",
    )
    require(run.get("access") == expected_access and run.get("model") == model_identity, "public access/model drift")
    require(
        run.get("selection")
        == {
            "components": 32, "shakedown": 8, "locked": 24,
            "old_top32_excluded": 32,
            "old_top32_exclusion_sha256": selection["old_top32_exclusion_sha256"],
            "selection_sha256": sha256(selection_path),
        },
        "public selection aggregate drift",
    )
    require(
        run.get("calls")
        == {
            "physical": 120,
            "by_role": {"critic": 32, "evidence": 32, "judge": 32, "single": 24},
            "S1_reused": True, "SC_reused": True,
        },
        "public call aggregate drift",
    )
    resources = run["resources"]
    require(
        resources["private_output_bytes"] == private_bytes
        and resources["generated_tokens"] == sum(record["generated_tokens"] for record in calls)
        and resources["wall_seconds"] <= config["resources"]["maximum_wall_seconds"]
        and resources["peak_rss_bytes"] <= config["resources"]["maximum_process_rss_bytes"]
        and resources["mlx_peak_bytes"] <= config["resources"]["maximum_mlx_peak_bytes"]
        and resources["critical_memory_events"] == 0
        and resources["oom_or_kill_events"] == 0
        and resources["orphan_processes_after_exit"] == 0,
        "resource replay drift",
    )
    require(
        run.get("outputs")
        == {
            "private_manifest": {
                "bytes": manifest_path.stat().st_size,
                "sha256": sha256(manifest_path), "mode": "0600",
            },
            "calls": {**manifest["calls_artifact"], "mode": "0600"},
            "selection": {**manifest["selection"], "mode": "0600"},
        },
        "public output identity drift",
    )
    require(not public_sensitive_paths(claim) and not public_sensitive_paths(run), "public row-level leak")
    verification = {
        "schema_version": "sqma-006-verification-v1", "experiment_id": "SQMA-006",
        "status": "Passed", "verified_at_utc": utc_now(),
        "config": artifact(supplied), "run": artifact(public_root / "run.json"),
        "calls_verified": 120, "fresh_selection_verified": True,
        "canonical_replay_verified": True, "gate": metrics, "gate_checks": checks,
        "access": {
            "runner_imported": False, "model_framework_imported": False,
            "gold_accessed": False, "classifier_accessed": False,
            "fold3_accessed": False, "fold4_accessed": False,
        },
        "next_gate": "complete_sqma006",
    }
    complete = {
        "schema_version": "sqma-006-complete-v1", "experiment_id": "SQMA-006",
        "status": "Complete", "sqma006_complete": True,
        "d1_canonical_preflight_verified": True, "capability_gate": "Passed",
        "accuracy_scored": False, "gold_accessed": False,
        "model_training_executed": False, "automatic_next_stage": False,
        "next_gate": "register_d1_agent_tune_matched_comparison",
    }
    require(not public_sensitive_paths(verification) and not public_sensitive_paths(complete), "verification public leak")
    write_json_exclusive(public_root / "verification.json", verification)
    write_json_exclusive(public_root / "complete.json", complete)
    return verification, complete


def verify_static(path: Path) -> dict[str, Any]:
    require(path.expanduser().resolve() == CONFIG_PATH.resolve(), "noncanonical SQMA-006 config")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "config root drift")
    result = validate_static_config(value)
    if value.get("design_status") == "FrozenExecutionReady":
        verify_implementations(value)
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
        result = {
            "experiment_id": "SQMA-006", "status": verification["status"],
            "sqma006_complete": complete["sqma006_complete"],
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, D1VerificationError) as exc:
        print(f"SQMA-006 static verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

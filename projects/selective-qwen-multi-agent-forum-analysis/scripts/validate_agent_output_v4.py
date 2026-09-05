#!/usr/bin/env python3
"""Validate frozen v3 Evidence/Critic and Judge V2 evidence-slot outputs."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
V3_VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v3.py"
V3_VALIDATOR_SHA256 = "0901c046936ca217cb210aec1f48d815d1e64b9f4db88f52c0f93ae8dc1ad07d"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
JUDGE_KEYS = frozenset(LABEL_ORDER)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_pinned_v3() -> Any:
    if not V3_VALIDATOR_PATH.is_file() or _sha256(V3_VALIDATOR_PATH) != V3_VALIDATOR_SHA256:
        raise RuntimeError("frozen v3 validator identity drift")
    module_name = "sqma_v4_pinned_validator_v3"
    spec = importlib.util.spec_from_file_location(module_name, V3_VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("frozen v3 validator import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if Path(module.__file__).resolve() != V3_VALIDATOR_PATH.resolve():
        raise RuntimeError("frozen v3 validator import path drift")
    return module


V3 = _load_pinned_v3()
AgentOutputError = V3.AgentOutputError
ONTOLOGY = V3.ONTOLOGY
ONTOLOGY_INSTRUCTION = V3.ONTOLOGY_INSTRUCTION


def fail(code: str, path: str) -> None:
    raise AgentOutputError(code, path)


def validate_evidence(raw: str, context: dict[str, Any]) -> dict[str, Any]:
    """Validate Evidence through the hash-pinned frozen v3 implementation."""

    return V3.validate_output("evidence", raw, context)


def validate_critic(raw: str, context: dict[str, Any]) -> dict[str, Any]:
    """Validate Critic through the hash-pinned frozen v3 implementation."""

    return V3.validate_output("critic", raw, context)


def _validate_judge_context(context: Any) -> tuple[dict[str, Any], dict[str, Any], list[int]]:
    value = V3.exact_object(
        context,
        {"analysis_text", "ontology", "evidence", "critic", "allowed_evidence_ids"},
        "context",
    )
    _, analysis_text = V3.validate_context(
        {"analysis_text": value["analysis_text"], "ontology": value["ontology"]},
        {"analysis_text", "ontology"},
    )
    evidence = V3.validate_evidence(value["evidence"], analysis_text, "context.evidence")
    critic = V3.validate_critic(value["critic"], "context.critic")
    allowed = value["allowed_evidence_ids"]
    if not isinstance(allowed, list) or any(type(item) is not int for item in allowed):
        fail("allowed_evidence_ids_type", "context.allowed_evidence_ids")
    expected = list(range(len(evidence["evidence_spans"])))
    if allowed != expected:
        fail("allowed_evidence_ids_drift", "context.allowed_evidence_ids")
    return evidence, critic, allowed


def _normalize_slots(
    value: Any, allowed_evidence_ids: list[int]
) -> tuple[dict[str, list[int]], dict[str, int]]:
    if not isinstance(value, dict):
        fail("judge_not_object", "$")
    if set(value) != JUDGE_KEYS:
        fail("judge_keys", "$")
    allowed = set(allowed_evidence_ids)
    normalized: dict[str, list[int]] = {}
    changed_slots = 0
    duplicate_refs_removed = 0
    reordered_slots = 0
    for label in LABEL_ORDER:
        refs = value[label]
        path = f"$.{label}"
        if not isinstance(refs, list):
            fail("reference_array", path)
        if any(type(item) is not int for item in refs):
            fail("reference_type", path)
        if any(item not in allowed for item in refs):
            fail("reference_range", path)
        deduplicated = list(dict.fromkeys(refs))
        sorted_refs = sorted(set(refs))
        removed = len(refs) - len(deduplicated)
        reordered = deduplicated != sorted(deduplicated)
        if sorted_refs != refs:
            changed_slots += 1
        duplicate_refs_removed += removed
        reordered_slots += int(reordered)
        if bool(sorted_refs) != bool(refs):
            fail("slot_emptiness_changed", path)
        normalized[label] = sorted_refs
    return normalized, {
        "reference_normalization_events": changed_slots,
        "duplicate_references_removed": duplicate_refs_removed,
        "reference_order_normalized_slots": reordered_slots,
    }


def judge_contract_result(raw: str, context: dict[str, Any]) -> dict[str, Any]:
    """Render a Judge V2 result without repairing keys, IDs, types, or slots."""

    raw_contract_valid = False
    stripped = raw.strip() if isinstance(raw, str) else ""
    used_json_fence = stripped.startswith("```")
    try:
        _, _, allowed = _validate_judge_context(context)
        value = V3.extract_unique_json_object(raw)
        normalized, normalization = _normalize_slots(value, allowed)
        raw_contract_valid = not used_json_fence
    except AgentOutputError as exc:
        return {
            "raw_contract_valid": False,
            "rendered_contract_valid": False,
            "derived_labels": [],
            "per_label_refs": {},
            "diagnostics": {
                "used_json_fence": used_json_fence,
                "reference_normalization_events": 0,
                "duplicate_references_removed": 0,
                "reference_order_normalized_slots": 0,
                "error_code": exc.code,
                "error_path": exc.path,
            },
        }
    derived = [label for label in LABEL_ORDER if normalized[label]]
    return {
        "raw_contract_valid": raw_contract_valid,
        "rendered_contract_valid": True,
        "derived_labels": derived,
        "per_label_refs": normalized,
        "diagnostics": {
            "used_json_fence": used_json_fence,
            **normalization,
            "error_code": None,
            "error_path": None,
        },
    }


def validate_output(role: str, raw: str, context: dict[str, Any]) -> dict[str, Any]:
    if role == "evidence":
        return validate_evidence(raw, context)
    if role == "critic":
        return validate_critic(raw, context)
    if role != "judge":
        fail("unknown_role", "role")
    result = judge_contract_result(raw, context)
    if not result["rendered_contract_valid"]:
        diagnostics = result["diagnostics"]
        fail(diagnostics["error_code"], diagnostics["error_path"])
    return result


def final_labels_or_empty(raw: str, context: dict[str, Any]) -> list[str]:
    result = judge_contract_result(raw, context)
    return list(result["derived_labels"]) if result["rendered_contract_valid"] else []

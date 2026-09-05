#!/usr/bin/env python3
"""Canonicalize and validate the minimal classifier-free SQMA v3 outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping, Sequence


LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
LABEL_INDEX = {label: index for index, label in enumerate(LABEL_ORDER)}
ONTOLOGY_INSTRUCTION = (
    "Identify every emotion expressed by the writer in the target text. Use only these labels, "
    "in this fixed order: love, joy, surprise, anger, sadness, fear. Labels are not mutually "
    "exclusive. Return an empty list when none apply. Do not infer a reader reaction, stance, "
    "or general sentiment unless the writer expresses one of the allowed emotions."
)
ONTOLOGY = {"label_order": list(LABEL_ORDER), "instruction": ONTOLOGY_INSTRUCTION}
WARNING_FLAGS = {
    "ontology_overlap",
    "weak_emotion_boundary",
    "implicit_emotion",
    "stance_emotion_confusion",
    "sarcasm_or_irony",
    "negation_scope",
    "multi_label_underprediction",
}
JSON_FENCE = re.compile(r"\A```json\r?\n(?P<body>[\s\S]*?)\r?\n```\Z")


class AgentOutputError(ValueError):
    def __init__(self, code: str, path: str) -> None:
        super().__init__(f"{code}:{path}")
        self.code = code
        self.path = path


def fail(code: str, path: str) -> None:
    raise AgentOutputError(code, path)


def strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            fail("duplicate_key", key)
        value[key] = child
    return value


def _reject_nonfinite(value: str) -> None:
    fail("nonfinite_number", "$")


def _unwrap(raw: str) -> tuple[str, bool]:
    if not isinstance(raw, str):
        fail("raw_not_string", "$")
    stripped = raw.strip()
    if not stripped:
        fail("json_object_missing", "$")
    if stripped.startswith("```") or stripped.endswith("```"):
        match = JSON_FENCE.fullmatch(stripped)
        if match is None:
            fail("invalid_code_fence", "$")
        body = match.group("body").strip()
        if body.startswith("```") or body.endswith("```"):
            fail("nested_code_fence", "$")
        return body, True
    return stripped, False


def _parse_one_object(payload: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload,
            object_pairs_hook=strict_object_pairs,
            parse_constant=_reject_nonfinite,
        )
    except AgentOutputError:
        raise
    except json.JSONDecodeError:
        fail("json_decode", "$")
    if not isinstance(value, dict):
        fail("root_not_object", "$")
    return value


def extract_unique_json_object(raw: str) -> dict[str, Any]:
    """Accept a bare object or one exact JSON fence, never arbitrary prose."""

    payload, _ = _unwrap(raw)
    return _parse_one_object(payload)


def canonicalize_output(raw: str) -> str:
    """Remove wrappers and serialize the extracted object without semantic edits."""

    value = extract_unique_json_object(raw)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AgentOutputError("canonical_json", "$") from exc


def canonicalized_value(raw: str) -> tuple[dict[str, Any], str]:
    payload, _ = _unwrap(raw)
    value = _parse_one_object(payload)
    try:
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AgentOutputError("canonical_json", "$") from exc
    return value, canonical


def diagnostics_from_raw(
    role: str, raw: str, context: Mapping[str, Any]
) -> dict[str, int]:
    """Count selected raw-output diagnostics without repairing or validating it.

    Only an object accepted by the strict bare/exact-fence syntax boundary is
    scanned.  A syntax failure returns zero counts and remains the canonical
    validator's responsibility.
    """

    label_fields = {
        "evidence": ("candidate_emotions",),
        "critic": ("recommended_emotions", "challenged_emotions"),
        "judge": ("emotions",),
        "single": ("emotions",),
    }
    span_fields = {
        "evidence": ("evidence_spans",),
        "critic": (),
        "judge": (),
        "single": ("evidence_spans",),
    }
    if role not in label_fields:
        fail("unknown_role", "role")
    result = {
        "out_of_ontology_labels": 0,
        "evidence_spans_total": 0,
        "evidence_spans_exact": 0,
    }
    try:
        value = extract_unique_json_object(raw)
    except AgentOutputError:
        return result

    for field in label_fields[role]:
        observed = value.get(field)
        if isinstance(observed, list):
            result["out_of_ontology_labels"] += sum(
                isinstance(item, str) and item not in LABEL_INDEX for item in observed
            )

    analysis_text = context.get("analysis_text") if isinstance(context, Mapping) else None
    for field in span_fields[role]:
        observed = value.get(field)
        if not isinstance(observed, list):
            continue
        result["evidence_spans_total"] += len(observed)
        if isinstance(analysis_text, str):
            result["evidence_spans_exact"] += sum(
                isinstance(item, str)
                and 1 <= len(item) <= 160
                and item in analysis_text
                for item in observed
            )
    return result


def exact_object(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("not_object", path)
    if set(value) != expected:
        fail("object_keys", path)
    return value


def label_array(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or len(value) > len(LABEL_ORDER):
        fail("label_array", path)
    if any(not isinstance(item, str) or item not in LABEL_INDEX for item in value):
        fail("label_item", path)
    if len(set(value)) != len(value):
        fail("label_duplicate", path)
    if value != sorted(value, key=LABEL_INDEX.__getitem__):
        fail("label_order", path)
    return value


def evidence_spans(value: Any, analysis_text: str, path: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 3:
        fail("evidence_array", path)
    for index, span in enumerate(value):
        span_path = f"{path}[{index}]"
        if not isinstance(span, str):
            fail("evidence_type", span_path)
        if not 1 <= len(span) <= 160:
            fail("evidence_length", span_path)
        if span not in analysis_text:
            fail("evidence_substring", span_path)
    if len(set(value)) != len(value):
        fail("evidence_duplicate", path)
    return value


def validate_ontology(value: Any, path: str) -> dict[str, Any]:
    ontology = exact_object(value, {"label_order", "instruction"}, path)
    if ontology["label_order"] != list(LABEL_ORDER):
        fail("ontology_order", f"{path}.label_order")
    if ontology["instruction"] != ONTOLOGY_INSTRUCTION:
        fail("ontology_instruction", f"{path}.instruction")
    return ontology


def validate_context(
    value: Any, expected_keys: set[str], path: str = "context"
) -> tuple[dict[str, Any], str]:
    context = exact_object(value, expected_keys, path)
    analysis_text = context["analysis_text"]
    if not isinstance(analysis_text, str) or not analysis_text:
        fail("analysis_text", f"{path}.analysis_text")
    validate_ontology(context["ontology"], f"{path}.ontology")
    return context, analysis_text


def validate_evidence(value: Any, analysis_text: str, path: str = "$") -> dict[str, Any]:
    output = exact_object(
        value,
        {"schema_version", "candidate_emotions", "evidence_spans", "insufficient_evidence"},
        path,
    )
    if output["schema_version"] != "evidence-v3":
        fail("schema_version", f"{path}.schema_version")
    labels = label_array(output["candidate_emotions"], f"{path}.candidate_emotions")
    spans = evidence_spans(output["evidence_spans"], analysis_text, f"{path}.evidence_spans")
    if type(output["insufficient_evidence"]) is not bool:
        fail("insufficient_type", f"{path}.insufficient_evidence")
    if output["insufficient_evidence"] and (labels or spans):
        fail("insufficient_nonempty", path)
    if labels and not spans:
        fail("labels_without_evidence", path)
    if not labels and spans:
        fail("evidence_without_labels", path)
    return output


def validate_critic(value: Any, path: str = "$") -> dict[str, Any]:
    output = exact_object(
        value,
        {"schema_version", "recommended_emotions", "challenged_emotions", "warning_flags"},
        path,
    )
    if output["schema_version"] != "critic-v3":
        fail("schema_version", f"{path}.schema_version")
    recommended = label_array(output["recommended_emotions"], f"{path}.recommended_emotions")
    challenged = label_array(output["challenged_emotions"], f"{path}.challenged_emotions")
    if set(recommended) & set(challenged):
        fail("critic_overlap", path)
    flags = output["warning_flags"]
    if not isinstance(flags, list) or len(flags) > len(WARNING_FLAGS):
        fail("warning_array", f"{path}.warning_flags")
    if any(not isinstance(flag, str) or flag not in WARNING_FLAGS for flag in flags):
        fail("warning_item", f"{path}.warning_flags")
    if len(set(flags)) != len(flags):
        fail("warning_duplicate", f"{path}.warning_flags")
    return output


def validate_judge(
    value: Any, evidence: Mapping[str, Any], path: str = "$"
) -> dict[str, Any]:
    output = exact_object(value, {"schema_version", "emotions", "evidence_refs"}, path)
    if output["schema_version"] != "judge-v3":
        fail("schema_version", f"{path}.schema_version")
    labels = label_array(output["emotions"], f"{path}.emotions")
    refs = output["evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 3:
        fail("reference_array", f"{path}.evidence_refs")
    if any(type(item) is not int for item in refs):
        fail("reference_type", f"{path}.evidence_refs")
    if len(set(refs)) != len(refs):
        fail("reference_duplicate", f"{path}.evidence_refs")
    span_count = len(evidence["evidence_spans"])
    if any(item < 0 or item >= span_count for item in refs):
        fail("reference_range", f"{path}.evidence_refs")
    if labels and not refs:
        fail("labels_without_reference", path)
    if not labels and refs:
        fail("reference_without_labels", path)
    return output


def validate_single(value: Any, analysis_text: str, path: str = "$") -> dict[str, Any]:
    output = exact_object(value, {"schema_version", "emotions", "evidence_spans"}, path)
    if output["schema_version"] != "single-v3":
        fail("schema_version", f"{path}.schema_version")
    labels = label_array(output["emotions"], f"{path}.emotions")
    spans = evidence_spans(output["evidence_spans"], analysis_text, f"{path}.evidence_spans")
    if labels and not spans:
        fail("labels_without_evidence", path)
    if not labels and spans:
        fail("evidence_without_labels", path)
    return output


def _validate_value(role: str, value: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    expected_context = {
        "evidence": {"analysis_text", "ontology"},
        "critic": {"analysis_text", "ontology", "evidence"},
        "judge": {"analysis_text", "ontology", "evidence", "critic"},
        "single": {"analysis_text", "ontology"},
    }
    if role not in expected_context:
        fail("unknown_role", "role")
    checked, analysis_text = validate_context(context, expected_context[role])
    if role == "evidence":
        return validate_evidence(value, analysis_text)
    if role == "critic":
        validate_evidence(checked["evidence"], analysis_text, "context.evidence")
        return validate_critic(value)
    if role == "judge":
        evidence = validate_evidence(checked["evidence"], analysis_text, "context.evidence")
        validate_critic(checked["critic"], "context.critic")
        return validate_judge(value, evidence)
    return validate_single(value, analysis_text)


def validate_output(role: str, raw: str, context: dict[str, Any]) -> dict[str, Any]:
    value, _ = canonicalized_value(raw)
    return _validate_value(role, value, context)


def validation_result(role: str, raw: str, context: dict[str, Any]) -> dict[str, Any]:
    """Return separate bare-raw and allowed-canonical validation statuses."""

    raw_valid = False
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped and not stripped.startswith("```") and not stripped.endswith("```"):
            try:
                raw_value = _parse_one_object(stripped)
                _validate_value(role, raw_value, context)
                raw_valid = True
            except AgentOutputError:
                raw_valid = False
    try:
        value, canonical = canonicalized_value(raw)
        validated = _validate_value(role, value, context)
    except AgentOutputError as exc:
        return {
            "raw_valid": raw_valid,
            "canonical_valid": False,
            "canonical_json": None,
            "value": None,
            "error_code": exc.code,
            "error_path": exc.path,
        }
    return {
        "raw_valid": raw_valid,
        "canonical_valid": True,
        "canonical_json": canonical,
        "value": validated,
        "error_code": None,
        "error_path": None,
    }


def final_labels_from_validated(role: str, value: Mapping[str, Any]) -> list[str]:
    if role not in {"judge", "single"}:
        fail("role_has_no_final_labels", "role")
    return list(value["emotions"])


def final_labels_or_empty(role: str, raw: str, context: dict[str, Any]) -> list[str]:
    if role not in {"judge", "single"}:
        return []
    try:
        value = validate_output(role, raw, context)
    except AgentOutputError:
        return []
    return final_labels_from_validated(role, value)


def aggregate_label_votes(votes: Sequence[Iterable[str] | None]) -> list[str]:
    if not isinstance(votes, Sequence) or isinstance(votes, (str, bytes)) or not votes:
        fail("votes_empty", "votes")
    normalized: list[set[str]] = []
    for index, vote in enumerate(votes):
        if vote is None:
            normalized.append(set())
            continue
        if isinstance(vote, (str, bytes)):
            fail("vote_type", f"votes[{index}]")
        try:
            values = list(vote)
        except TypeError:
            fail("vote_type", f"votes[{index}]")
        label_array(values, f"votes[{index}]")
        normalized.append(set(values))
    threshold = len(normalized) / 2
    return [label for label in LABEL_ORDER if sum(label in vote for vote in normalized) > threshold]

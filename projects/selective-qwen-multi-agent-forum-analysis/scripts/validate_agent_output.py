#!/usr/bin/env python3
"""Strict runtime validation for the frozen SQMA v1 Agent outputs."""

from __future__ import annotations

import json
from typing import Any


LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
LABEL_INDEX = {label: index for index, label in enumerate(LABEL_ORDER)}


class AgentOutputError(ValueError):
    def __init__(self, code: str, path: str) -> None:
        super().__init__(f"{code}:{path}")
        self.code = code
        self.path = path


def fail(code: str, path: str) -> None:
    raise AgentOutputError(code, path)


def strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            fail("duplicate_key", key)
        output[key] = value
    return output


def parse_strict_json(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        fail("raw_not_string", "$")
    try:
        value = json.loads(raw, object_pairs_hook=strict_object_pairs)
    except AgentOutputError:
        raise
    except json.JSONDecodeError:
        fail("json_decode", "$")
    if not isinstance(value, dict):
        fail("root_not_object", "$")
    return value


def exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail("not_object", path)
    actual = set(value)
    if actual != expected:
        fail("object_keys", path)
    return value


def enum_string(value: Any, allowed: set[str], path: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        fail("enum", path)
    return value


def string_array(
    value: Any,
    allowed: set[str],
    path: str,
    *,
    maximum: int,
    canonical_order: bool = False,
) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        fail("array", path)
    if any(not isinstance(item, str) or item not in allowed for item in value):
        fail("array_item", path)
    if len(set(value)) != len(value):
        fail("array_duplicate", path)
    if canonical_order and value != sorted(value, key=LABEL_INDEX.__getitem__):
        fail("label_order", path)
    return value


def labels(value: Any, path: str) -> list[str]:
    return string_array(value, set(LABEL_ORDER), path, maximum=6, canonical_order=True)


def validate_classifier_result(value: Any, path: str = "classifier_result") -> dict[str, Any]:
    result = exact_keys(value, {"final_labels", "m1_labels", "m3_labels"}, path)
    labels(result["final_labels"], f"{path}.final_labels")
    labels(result["m1_labels"], f"{path}.m1_labels")
    if result["m3_labels"] is not None:
        labels(result["m3_labels"], f"{path}.m3_labels")
    return result


def validate_evidence_appraisal(value: Any, analysis_text: str, path: str = "$") -> dict[str, Any]:
    result = exact_keys(
        value,
        {
            "schema_version",
            "candidate_emotions",
            "evidence_spans",
            "expression_type",
            "insufficient_evidence",
            "appraisal",
        },
        path,
    )
    if result["schema_version"] != "evidence-appraisal-v1":
        fail("schema_version", f"{path}.schema_version")
    labels(result["candidate_emotions"], f"{path}.candidate_emotions")
    spans = result["evidence_spans"]
    if not isinstance(spans, list) or len(spans) > 3:
        fail("array", f"{path}.evidence_spans")
    for index, span in enumerate(spans):
        span_path = f"{path}.evidence_spans[{index}]"
        if not isinstance(span, str) or not 1 <= len(span) <= 160:
            fail("evidence_length", span_path)
        if span not in analysis_text:
            fail("evidence_substring", span_path)
    if len(set(spans)) != len(spans):
        fail("array_duplicate", f"{path}.evidence_spans")
    if type(result["insufficient_evidence"]) is not bool:
        fail("not_boolean", f"{path}.insufficient_evidence")
    if result["insufficient_evidence"] and spans:
        fail("insufficient_with_evidence", f"{path}.evidence_spans")
    if not result["insufficient_evidence"] and not spans:
        fail("sufficient_without_evidence", f"{path}.evidence_spans")
    enum_string(
        result["expression_type"],
        {"explicit", "implicit", "mixed", "none", "unclear"},
        f"{path}.expression_type",
    )
    appraisal = exact_keys(
        result["appraisal"],
        {
            "goal_obstruction",
            "responsibility",
            "control",
            "certainty",
            "expectation_violation",
            "loss_or_threat",
        },
        f"{path}.appraisal",
    )
    enum_string(appraisal["goal_obstruction"], {"present", "absent", "unclear"}, f"{path}.appraisal.goal_obstruction")
    enum_string(appraisal["responsibility"], {"self", "other", "shared", "situational", "none", "unclear"}, f"{path}.appraisal.responsibility")
    enum_string(appraisal["control"], {"high", "low", "mixed", "unclear"}, f"{path}.appraisal.control")
    enum_string(appraisal["certainty"], {"high", "low", "mixed", "unclear"}, f"{path}.appraisal.certainty")
    enum_string(appraisal["expectation_violation"], {"present", "absent", "unclear"}, f"{path}.appraisal.expectation_violation")
    enum_string(appraisal["loss_or_threat"], {"loss", "threat", "both", "none", "unclear"}, f"{path}.appraisal.loss_or_threat")
    return result


def validate_pragmatics_critic(value: Any, path: str = "$") -> dict[str, Any]:
    result = exact_keys(
        value,
        {
            "schema_version",
            "reading",
            "negation",
            "sarcasm",
            "emotion_evidence",
            "recommended_emotions",
            "challenged_emotions",
            "warning_flags",
        },
        path,
    )
    if result["schema_version"] != "pragmatics-critic-v1":
        fail("schema_version", f"{path}.schema_version")
    enum_string(result["reading"], {"emotion", "technical_stance", "mixed", "unclear"}, f"{path}.reading")
    enum_string(result["negation"], {"none", "relevant", "unclear"}, f"{path}.negation")
    enum_string(result["sarcasm"], {"unlikely", "possible", "likely", "unclear"}, f"{path}.sarcasm")
    enum_string(result["emotion_evidence"], {"sufficient", "weak", "absent", "unclear"}, f"{path}.emotion_evidence")
    recommended = labels(result["recommended_emotions"], f"{path}.recommended_emotions")
    challenged = labels(result["challenged_emotions"], f"{path}.challenged_emotions")
    if set(recommended) & set(challenged):
        fail("critic_emotion_overlap", path)
    string_array(
        result["warning_flags"],
        {
            "ontology_overlap",
            "weak_emotion_boundary",
            "implicit_emotion",
            "stance_emotion_confusion",
            "sarcasm_or_irony",
            "negation_scope",
            "multi_label_underprediction",
        },
        f"{path}.warning_flags",
        maximum=7,
    )
    return result


def validate_judge(
    value: Any,
    classifier_result: dict[str, Any],
    evidence_appraisal: dict[str, Any],
    path: str = "$",
) -> dict[str, Any]:
    result = exact_keys(value, {"schema_version", "action", "emotions", "evidence_refs", "reason_flags"}, path)
    if result["schema_version"] != "judge-v1":
        fail("schema_version", f"{path}.schema_version")
    action = enum_string(result["action"], {"accept_baseline", "revise_labels", "abstain"}, f"{path}.action")
    output_labels = labels(result["emotions"], f"{path}.emotions")
    baseline = labels(classifier_result["final_labels"], "classifier_result.final_labels")
    refs = result["evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 3 or any(type(item) is not int for item in refs):
        fail("evidence_refs", f"{path}.evidence_refs")
    if len(set(refs)) != len(refs):
        fail("array_duplicate", f"{path}.evidence_refs")
    span_count = len(evidence_appraisal["evidence_spans"])
    if any(item < 0 or item >= span_count for item in refs):
        fail("evidence_ref_range", f"{path}.evidence_refs")
    string_array(
        result["reason_flags"],
        {
            "baseline_supported",
            "evidence_supported",
            "appraisal_supported",
            "pragmatics_correction",
            "role_conflict",
            "insufficient_evidence",
        },
        f"{path}.reason_flags",
        maximum=3,
    )
    if action == "accept_baseline" and output_labels != baseline:
        fail("accept_mismatch", f"{path}.emotions")
    if action == "revise_labels":
        if output_labels == baseline:
            fail("revision_unchanged", f"{path}.emotions")
        if output_labels and not refs:
            fail("revision_without_evidence", f"{path}.evidence_refs")
    if action == "abstain" and (output_labels or refs):
        fail("abstain_nonempty", path)
    return result


def validate_single_agent(
    value: Any,
    analysis_text: str,
    classifier_result: dict[str, Any],
    path: str = "$",
) -> dict[str, Any]:
    result = exact_keys(value, {"schema_version", "evidence_appraisal", "pragmatics", "decision"}, path)
    if result["schema_version"] != "single-agent-v1":
        fail("schema_version", f"{path}.schema_version")
    evidence = validate_evidence_appraisal(result["evidence_appraisal"], analysis_text, f"{path}.evidence_appraisal")
    validate_pragmatics_critic(result["pragmatics"], f"{path}.pragmatics")
    validate_judge(result["decision"], classifier_result, evidence, f"{path}.decision")
    return result


def validate_output(role: str, raw: str, context: dict[str, Any]) -> dict[str, Any]:
    if role not in {"evidence_appraisal", "pragmatics_critic", "judge", "single_agent"}:
        fail("unknown_role", "role")
    analysis_text = context.get("analysis_text")
    if not isinstance(analysis_text, str):
        fail("analysis_text", "context.analysis_text")
    value = parse_strict_json(raw)
    if role == "evidence_appraisal":
        return validate_evidence_appraisal(value, analysis_text)
    if role == "pragmatics_critic":
        return validate_pragmatics_critic(value)
    classifier = validate_classifier_result(context.get("classifier_result"))
    if role == "single_agent":
        return validate_single_agent(value, analysis_text, classifier)
    evidence = validate_evidence_appraisal(context.get("evidence_appraisal"), analysis_text, "context.evidence_appraisal")
    return validate_judge(value, classifier, evidence)

#!/usr/bin/env python3
"""Independent verifier for the sealed SQMA-005 Agent-Tune comparison.

This module does not import the producer, scorer, tokenizer, or a model
framework. Importing it performs no I/O. The CLI is intended to run only after
the classifier-free producer and the gold consumer scorer have both sealed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import stat
import sys
from typing import Any, Iterable, Mapping, Sequence
import zipfile


sys.dont_write_bytecode = True
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
SYSTEMS = ("s1", "s2a", "s2b", "s3")
EXPECTED_ROWS = 672
EXPECTED_COMPONENTS = 657
EXPECTED_CALLS = 4032
EXPECTED_GENERATED_CEILING = 1_161_216
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260903
BOOTSTRAP_NAMESPACE = "SQMA-D0-component-bootstrap-v1"
BOOTSTRAP_ALGORITHM = "python_random_mt19937_component_resampling_v1"
INPUT_FIELDS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "fold_id",
    "source_ordinal", "text",
}
TEXT_META_FIELDS = {
    "original_sha256", "analysis_sha256", "original_token_count",
    "analysis_token_count", "was_truncated", "model_free_truncation_replay",
}
CALL_FIELDS = {
    "schema_version", "call_ordinal", "row_ordinal", "sample_id", "component_id",
    "source_ordinal", "system_id", "role", "call_index", "seed", "analysis_text",
    "analysis_text_sha256", "text_meta", "context_sha256", "messages_sha256",
    "prompt_ids_sha256", "prefill_tokens", "max_new_tokens", "finish_reason",
    "generated_tokens", "latency_seconds", "prompt_tps", "generation_tps",
    "mlx_peak_bytes", "raw_output_sha256", "raw_output", "valid", "error_code",
    "parsed_output", "final_labels", "abstained", "token_cap_hit",
}
GOLD_ARRAYS = {"sample_ids", "component_ids", "fold_ids", "source_ordinals", "gold"}
SYSTEM_ARRAYS = {
    "sample_ids", "component_ids", "fold_ids", "source_ordinals",
    "s1", "s2a", "s2b", "s3", "single_valid", "role_valid",
    "single_abstained", "judge_abstained", "s2b_k", "s3_ceiling_tokens",
    "s2b_ceiling_tokens", "s2b_ceiling_utilization", "s3_actual_tokens",
    "s2b_actual_tokens",
}
TUNE_GATE = {
    "s3_minus_s2b_six_point_minimum": 0.010,
    "s3_minus_s2b_six_q05_strictly_greater_than": 0.0,
    "s3_minus_s2b_five_point_minimum": -0.005,
    "s3_minus_s2b_hamming_q95_maximum": 0.0025,
    "s3_minus_s2a_six_q05_minimum": -0.005,
    "s3_minus_s2a_hamming_q95_maximum": 0.0025,
}
PUBLIC_SENSITIVE_KEYS = {
    "sample_id", "sample_ids", "component_id", "component_ids", "source_ordinal",
    "source_ordinals", "gold", "text", "analysis_text", "raw_output",
    "parsed_output", "final_labels",
}
MAX_NEW_TOKENS = {
    "evidence_appraisal": 256,
    "pragmatics_critic": 192,
    "judge": 128,
    "single_agent": 384,
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def seed_for(namespace: str, system: str, sample: str, role: str, call_index: int) -> int:
    material = f"{namespace}|{system}|{sample}|{role}|{call_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big", signed=False)


def fallback_evidence() -> dict[str, Any]:
    return {
        "schema_version": "evidence-appraisal-v2",
        "candidate_emotions": [],
        "evidence_spans": [],
        "expression_type": "unclear",
        "insufficient_evidence": True,
        "appraisal": {
            "goal_obstruction": "unclear", "responsibility": "unclear",
            "control": "unclear", "certainty": "unclear",
            "expectation_violation": "unclear", "loss_or_threat": "unclear",
        },
    }


def fallback_critic() -> dict[str, Any]:
    return {
        "schema_version": "pragmatics-critic-v2", "reading": "unclear",
        "negation": "unclear", "sarcasm": "unclear", "emotion_evidence": "unclear",
        "recommended_emotions": [], "challenged_emotions": [], "warning_flags": [],
    }


def expected_call_slots(rows: int = EXPECTED_ROWS) -> list[tuple[int, int, str, str, int]]:
    require(rows > 0, "row count drift")
    order = (
        ("S3", "evidence_appraisal", 0),
        ("S3", "pragmatics_critic", 1),
        ("S3", "judge", 2),
        ("single_pool", "single_agent", 0),
        ("single_pool", "single_agent", 1),
        ("single_pool", "single_agent", 2),
    )
    return [
        (row * 6 + offset, row, system, role, call_index)
        for row in range(rows)
        for offset, (system, role, call_index) in enumerate(order)
    ]


def strict_majority(votes: Sequence[Sequence[str]]) -> list[int]:
    require(bool(votes), "empty vote pool")
    for vote in votes:
        require(list(vote) == sorted(set(vote), key=LABEL_ORDER.index), "vote drift")
    threshold = len(votes) / 2
    return [int(sum(label in vote for vote in votes) > threshold) for label in LABEL_ORDER]


def label_vector(labels: Iterable[str]) -> list[int]:
    values = list(labels)
    require(values == sorted(set(values), key=LABEL_ORDER.index), "label set/order drift")
    return [int(label in values) for label in LABEL_ORDER]


def choose_s2b_k(
    s3_ceiling_tokens: int, single_call_ceiling_tokens: int, tolerance: float = 0.10
) -> int:
    require(
        s3_ceiling_tokens > 0 and single_call_ceiling_tokens > 0 and 0 <= tolerance < 1,
        "S2b input drift",
    )
    for candidate in (3, 2):
        used = candidate * single_call_ceiling_tokens
        if used <= s3_ceiling_tokens and used / s3_ceiling_tokens >= 1 - tolerance:
            return candidate
    raise VerificationError("no whole-call S2b allocation satisfies the frozen ceiling")


def validate_input_rows(rows: Sequence[Mapping[str, Any]], expected_rows: int) -> None:
    require(len(rows) == expected_rows, "input row count drift")
    for row in rows:
        require(isinstance(row, Mapping) and set(row) == INPUT_FIELDS, "input row schema drift")
        require(
            row["schema_version"] == "sqma-gold-free-inference-snapshot-v1"
            and row["fold_id"] == 3
            and isinstance(row["sample_id"], str)
            and isinstance(row["component_id"], str)
            and type(row["source_ordinal"]) is int
            and isinstance(row["text"], str)
            and bool(row["text"]),
            "input row value drift",
        )
    require(len({row["sample_id"] for row in rows}) == expected_rows, "input sample duplicate")
    ordinals = [row["source_ordinal"] for row in rows]
    require(ordinals == sorted(ordinals) and len(set(ordinals)) == expected_rows, "input order drift")


def validate_text_meta(record: Mapping[str, Any], row: Mapping[str, Any]) -> None:
    analysis_text = record["analysis_text"]
    metadata = record["text_meta"]
    require(isinstance(analysis_text, str) and bool(analysis_text), "analysis text drift")
    require(isinstance(metadata, Mapping) and set(metadata) == TEXT_META_FIELDS, "text metadata schema drift")
    require(metadata["original_sha256"] == text_sha256(row["text"]), "source text identity drift")
    require(
        metadata["analysis_sha256"] == text_sha256(analysis_text)
        and record["analysis_text_sha256"] == metadata["analysis_sha256"],
        "analysis text identity drift",
    )
    require(
        type(metadata["original_token_count"]) is int
        and type(metadata["analysis_token_count"]) is int
        and metadata["original_token_count"] > 0
        and metadata["analysis_token_count"] > 0
        and metadata["analysis_token_count"] <= metadata["original_token_count"],
        "text token metadata drift",
    )
    require(
        type(metadata["was_truncated"]) is bool
        and metadata["model_free_truncation_replay"] is (not metadata["was_truncated"]),
        "truncation replay boundary drift",
    )
    if metadata["was_truncated"]:
        require(
            metadata["original_token_count"] > metadata["analysis_token_count"]
            and metadata["analysis_token_count"] <= 1024,
            "truncated text metadata drift",
        )
    else:
        require(
            analysis_text == row["text"]
            and metadata["original_token_count"] == metadata["analysis_token_count"],
            "untruncated text replay drift",
        )


def build_output_contracts(bundle: Mapping[str, Any]) -> dict[str, str]:
    examples = bundle.get("concrete_output_examples")
    require(isinstance(examples, Mapping), "prompt examples missing")
    contracts: dict[str, str] = {}
    for role in MAX_NEW_TOKENS:
        require(role in examples and isinstance(examples[role], Mapping), f"prompt example drift: {role}")
        encoded = json.dumps(examples[role], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        require("|" not in encoded, "prompt placeholder drift")
        contracts[role] = (
            "Use this example only for JSON shape and value types; its semantic values are not a "
            "default answer. Return exactly one JSON object with the same keys and types. "
            "evidence_spans contains exact-substring strings only; evidence_refs contains zero-based "
            "integers only. Concrete valid JSON example: " + encoded
        )
    return contracts


def expected_messages(
    bundle: Mapping[str, Any], contracts: Mapping[str, str], role: str,
    context: Mapping[str, Any],
) -> list[dict[str, str]]:
    role_spec = bundle["roles"][role]
    require(set(context) == set(role_spec["visible_fields"]), "role-visible context drift")
    system = "\n".join([*bundle["shared_rules"], role_spec["system"], contracts[role]])
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "Input JSON:\n" + json.dumps(
                context, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            ),
        },
    ]


def is_abstained(role: str, parsed: Mapping[str, Any] | None) -> bool:
    if parsed is None:
        return False
    decision = parsed if role == "judge" else parsed.get("decision") if role == "single_agent" else None
    return isinstance(decision, Mapping) and decision.get("action") == "abstain"


def reconstruct_systems(
    calls: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    validator: Any,
    bundle: Mapping[str, Any],
    *,
    seed_namespace: str,
    matching_tolerance: float = 0.10,
) -> dict[str, Any]:
    """Replay all calls and derive the exact classifier-free system arrays."""

    validate_input_rows(rows, len(rows))
    require(len(calls) == len(rows) * 6, "call count drift")
    slots = expected_call_slots(len(rows))
    contracts = build_output_contracts(bundle)
    ontology = {"label_order": list(LABEL_ORDER), "instruction": bundle["ontology"]["instruction"]}
    require(ontology == validator.ONTOLOGY, "prompt/validator ontology drift")
    outputs: dict[str, list[Any]] = {name: [] for name in SYSTEM_ARRAYS}

    for row_ordinal, row in enumerate(rows):
        row_calls = calls[row_ordinal * 6 : row_ordinal * 6 + 6]
        parsed_roles: dict[str, dict[str, Any]] = {}
        final_sets: list[list[str]] = []
        valid_roles: list[int] = []
        valid_single: list[int] = []
        abstained_single: list[int] = []
        first_text_identity: tuple[str, str] | None = None

        for record, slot in zip(
            row_calls, slots[row_ordinal * 6 : row_ordinal * 6 + 6], strict=True
        ):
            require(isinstance(record, Mapping) and set(record) == CALL_FIELDS, "call schema drift")
            call_ordinal, expected_row, system, role, call_index = slot
            require(record["schema_version"] == "sqma-005-call-v1", "call schema identity drift")
            require(
                (
                    record["call_ordinal"], record["row_ordinal"], record["system_id"],
                    record["role"], record["call_index"],
                ) == (call_ordinal, expected_row, system, role, call_index),
                "call slot drift",
            )
            require(
                record["sample_id"] == row["sample_id"]
                and record["component_id"] == row["component_id"]
                and record["source_ordinal"] == row["source_ordinal"],
                "call row identity drift",
            )
            validate_text_meta(record, row)
            text_identity = (record["analysis_text_sha256"], canonical_digest(record["text_meta"]))
            if first_text_identity is None:
                first_text_identity = text_identity
            require(text_identity == first_text_identity, "within-row analysis text drift")

            context: dict[str, Any] = {
                "analysis_text": record["analysis_text"], "ontology": ontology,
            }
            if role in {"pragmatics_critic", "judge"}:
                context["evidence_appraisal"] = parsed_roles.get(
                    "evidence_appraisal", fallback_evidence()
                )
            if role == "judge":
                context["pragmatics_critic"] = parsed_roles.get(
                    "pragmatics_critic", fallback_critic()
                )
            require(record["context_sha256"] == canonical_digest(context), "context digest drift")
            require(
                record["messages_sha256"]
                == canonical_digest(expected_messages(bundle, contracts, role, context)),
                "messages digest drift",
            )
            require(
                record["seed"] == seed_for(
                    seed_namespace, system, row["sample_id"], role, call_index
                ),
                "seed drift",
            )
            require(
                isinstance(record["prompt_ids_sha256"], str)
                and len(record["prompt_ids_sha256"]) == 64
                and set(record["prompt_ids_sha256"]) <= set("0123456789abcdef"),
                "prompt token identity drift",
            )
            require(record["max_new_tokens"] == MAX_NEW_TOKENS[role], "max-new-token drift")
            require(isinstance(record["finish_reason"], str), "finish-reason drift")
            for key in ("prefill_tokens", "generated_tokens", "mlx_peak_bytes"):
                require(type(record[key]) is int and record[key] >= 0, f"{key} drift")
            require(record["prefill_tokens"] > 0, "empty prompt drift")
            require(record["generated_tokens"] <= record["max_new_tokens"], "generated-token drift")
            for key in ("latency_seconds", "prompt_tps", "generation_tps"):
                require(
                    type(record[key]) in (int, float)
                    and not isinstance(record[key], bool)
                    and math.isfinite(record[key])
                    and record[key] >= 0,
                    f"{key} drift",
                )
            require(
                isinstance(record["raw_output"], str)
                and record["raw_output_sha256"] == text_sha256(record["raw_output"]),
                "raw output drift",
            )

            parsed = None
            error_code = None
            try:
                parsed = validator.validate_output(role, record["raw_output"], context)
            except validator.AgentOutputError as exc:
                error_code = exc.code
            token_cap_hit = record["finish_reason"] == "length"
            if token_cap_hit:
                parsed = None
                error_code = "token_cap_hit"
            require(
                record["token_cap_hit"] is token_cap_hit
                and record["valid"] is (parsed is not None)
                and record["error_code"] == error_code
                and record["parsed_output"] == parsed,
                "semantic replay drift",
            )
            labels = (
                validator.final_labels_from_validated(role, parsed)
                if parsed is not None and role in {"judge", "single_agent"}
                else []
            )
            abstained = is_abstained(role, parsed)
            require(
                record["final_labels"] == labels and record["abstained"] is abstained,
                "final/abstain replay drift",
            )
            if system == "S3":
                valid_roles.append(int(parsed is not None))
                if parsed is not None:
                    parsed_roles[role] = parsed
            else:
                valid_single.append(int(parsed is not None))
                abstained_single.append(int(abstained))
                final_sets.append(labels)

        require(len(valid_roles) == len(valid_single) == len(final_sets) == 3, "row grouping drift")
        judge_call = row_calls[2]
        s3_labels = judge_call["final_labels"] if all(valid_roles) and not judge_call["abstained"] else []
        s3_ceiling = sum(call["prefill_tokens"] + call["max_new_tokens"] for call in row_calls[:3])
        single_ceilings = [
            call["prefill_tokens"] + call["max_new_tokens"] for call in row_calls[3:]
        ]
        require(len(set(single_ceilings)) == 1, "single-call ceiling drift")
        k = choose_s2b_k(s3_ceiling, single_ceilings[0], matching_tolerance)
        s2b_ceiling = k * single_ceilings[0]
        values = {
            "sample_ids": row["sample_id"], "component_ids": row["component_id"],
            "fold_ids": 3, "source_ordinals": row["source_ordinal"],
            "s1": label_vector(final_sets[0]),
            "s2a": strict_majority(final_sets),
            "s2b": strict_majority(final_sets[:k]),
            "s3": label_vector(s3_labels),
            "single_valid": valid_single, "role_valid": valid_roles,
            "single_abstained": abstained_single,
            "judge_abstained": int(judge_call["abstained"]), "s2b_k": k,
            "s3_ceiling_tokens": s3_ceiling, "s2b_ceiling_tokens": s2b_ceiling,
            "s2b_ceiling_utilization": s2b_ceiling / s3_ceiling,
            "s3_actual_tokens": sum(
                call["prefill_tokens"] + call["generated_tokens"] for call in row_calls[:3]
            ),
            "s2b_actual_tokens": sum(
                call["prefill_tokens"] + call["generated_tokens"]
                for call in row_calls[3 : 3 + k]
            ),
        }
        for name, value in values.items():
            outputs[name].append(value)
    return outputs


def safe_f1(tp: int, fp: int, fn: int) -> float:
    denominator = 2 * tp + fp + fn
    return 0.0 if denominator == 0 else 2 * tp / denominator


def metric_bundle(
    truth: Sequence[Sequence[int]], predicted: Sequence[Sequence[int]]
) -> dict[str, Any]:
    require(len(truth) == len(predicted) and bool(truth), "metric rows drift")
    f1s: list[float] = []
    per_label: dict[str, Any] = {}
    total_tp = total_fp = total_fn = mismatches = exact_rows = 0
    for index, label in enumerate(LABEL_ORDER):
        tp = fp = fn = support = predicted_positive = 0
        for target, output in zip(truth, predicted, strict=True):
            actual = int(target[index]); guess = int(output[index])
            support += actual; predicted_positive += guess
            tp += actual & guess; fp += (1 - actual) & guess; fn += actual & (1 - guess)
        precision = 0.0 if tp + fp == 0 else tp / (tp + fp)
        recall = 0.0 if tp + fn == 0 else tp / (tp + fn)
        f1 = safe_f1(tp, fp, fn)
        f1s.append(f1); total_tp += tp; total_fp += fp; total_fn += fn
        per_label[label] = {
            "precision": precision, "recall": recall, "f1": f1,
            "support": support, "predicted_positive": predicted_positive,
        }
    for target, output in zip(truth, predicted, strict=True):
        mismatches += sum(int(a) != int(b) for a, b in zip(target, output, strict=True))
        exact_rows += int(list(target) == list(output))
    return {
        "six_label_macro_f1": sum(f1s) / 6,
        "five_label_macro_f1_without_surprise": sum(
            value for index, value in enumerate(f1s) if index != 2
        ) / 5,
        "hamming_loss": mismatches / (len(truth) * 6),
        "micro_f1": safe_f1(total_tp, total_fp, total_fn),
        "subset_accuracy": exact_rows / len(truth),
        "per_label": per_label,
    }


def nearest_rank(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(probability * len(ordered)) - 1))
    return ordered[index]


def distribution_summary(values: Sequence[float]) -> dict[str, float]:
    require(bool(values), "empty bootstrap distribution")
    return {
        "q025": nearest_rank(values, 0.025), "q05": nearest_rank(values, 0.05),
        "median": nearest_rank(values, 0.5), "q95": nearest_rank(values, 0.95),
        "q975": nearest_rank(values, 0.975),
    }


def independent_score(
    truth: Sequence[Sequence[int]],
    predictions: Mapping[str, Sequence[Sequence[int]]],
    components: Sequence[str],
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    require(replicates > 0 and len(truth) == len(components), "bootstrap contract drift")
    point = {system: metric_bundle(truth, predictions[system]) for system in SYSTEMS}
    component_order = list(dict.fromkeys(components))
    rows_by_component = {
        component: [index for index, value in enumerate(components) if value == component]
        for component in component_order
    }
    rng = random.Random(seed)
    metric_names = (
        "six_label_macro_f1", "five_label_macro_f1_without_surprise", "hamming_loss",
        "micro_f1", "subset_accuracy",
    )
    system_values = {
        system: {metric: [] for metric in metric_names} for system in SYSTEMS
    }
    contrast_values = {
        name: {metric: [] for metric in metric_names}
        for name in ("s3_minus_s2a", "s3_minus_s2b")
    }
    for _ in range(replicates):
        sampled = [
            component_order[rng.randrange(len(component_order))] for _ in component_order
        ]
        indices = [index for component in sampled for index in rows_by_component[component]]
        sampled_truth = [truth[index] for index in indices]
        current: dict[str, dict[str, Any]] = {}
        for system in SYSTEMS:
            current[system] = metric_bundle(
                sampled_truth, [predictions[system][index] for index in indices]
            )
            for metric in metric_names:
                system_values[system][metric].append(current[system][metric])
        for baseline in ("s2a", "s2b"):
            name = f"s3_minus_{baseline}"
            for metric in metric_names:
                contrast_values[name][metric].append(
                    current["s3"][metric] - current[baseline][metric]
                )
    systems = {
        system: {
            "point": point[system],
            "bootstrap": {
                metric: distribution_summary(values)
                for metric, values in system_values[system].items()
            },
        }
        for system in SYSTEMS
    }
    contrasts: dict[str, Any] = {}
    for baseline in ("s2a", "s2b"):
        name = f"s3_minus_{baseline}"
        contrasts[name] = {
            "point": {
                metric: point["s3"][metric] - point[baseline][metric]
                for metric in metric_names
            },
            "bootstrap": {
                metric: distribution_summary(values)
                for metric, values in contrast_values[name].items()
            },
        }
    return {"systems": systems, "contrasts": contrasts}


def evaluate_gate(
    contrasts: Mapping[str, Any], integrity: Mapping[str, bool]
) -> dict[str, Any]:
    s2b = contrasts["s3_minus_s2b"]
    s2a = contrasts["s3_minus_s2a"]
    checks = {
        "all_schema_budget_resource_checks": bool(integrity)
        and all(value is True for value in integrity.values()),
        "s3_minus_s2b_six_point": s2b["point"]["six_label_macro_f1"] >= 0.010,
        "s3_minus_s2b_six_q05": s2b["bootstrap"]["six_label_macro_f1"]["q05"] > 0,
        "s3_minus_s2b_five_point": s2b["point"]["five_label_macro_f1_without_surprise"] >= -0.005,
        "s3_minus_s2b_hamming_q95": s2b["bootstrap"]["hamming_loss"]["q95"] <= 0.0025,
        "s3_minus_s2a_six_q05": s2a["bootstrap"]["six_label_macro_f1"]["q05"] >= -0.005,
        "s3_minus_s2a_hamming_q95": s2a["bootstrap"]["hamming_loss"]["q95"] <= 0.0025,
    }
    return {
        "passed": all(checks.values()), "checks": checks, "thresholds": dict(TUNE_GATE),
        "failure_action": "stop_without_confirm_or_selective",
    }


def numeric_summary(values: Sequence[float]) -> dict[str, float]:
    require(bool(values), "numeric summary requires values")
    ordered = sorted(float(value) for value in values)
    return {
        "min": ordered[0], "median": nearest_rank(ordered, 0.5),
        "p95": nearest_rank(ordered, 0.95), "max": ordered[-1],
        "mean": sum(ordered) / len(ordered),
    }


def recompute_aggregates(
    calls: Sequence[Mapping[str, Any]], systems: Mapping[str, Sequence[Any]]
) -> dict[str, Any]:
    roles = ("evidence_appraisal", "pragmatics_critic", "judge", "single_agent")
    per_role = {}
    for role in roles:
        selected = [call for call in calls if call["role"] == role]
        per_role[role] = {
            "calls": len(selected),
            "valid": sum(call["valid"] is True for call in selected),
            "invalid": sum(call["valid"] is False for call in selected),
            "abstained": sum(call["abstained"] is True for call in selected),
            "prefill_tokens": numeric_summary([call["prefill_tokens"] for call in selected]),
            "generated_tokens": numeric_summary([call["generated_tokens"] for call in selected]),
            "latency_seconds": numeric_summary([call["latency_seconds"] for call in selected]),
        }
    return {
        "per_role": per_role,
        "token_cap_hits": sum(call["token_cap_hit"] is True for call in calls),
        "s2b_k_counts": {
            str(key): value for key, value in sorted(Counter(systems["s2b_k"]).items())
        },
        "s2b_ceiling_utilization": numeric_summary(systems["s2b_ceiling_utilization"]),
    }


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (
        value.startswith("sample-") or value.startswith("component-")
    ):
        violations.append(prefix)
    return violations


def regular_private_file(path: Path, label: str) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(
        stat.S_ISREG(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and observed.st_nlink == 1
        and observed.st_uid == os.getuid()
        and f"{stat.S_IMODE(observed.st_mode):04o}" == "0600",
        f"{label} privacy drift",
    )
    return observed


def verify_record(record: Any, path: Path, label: str) -> None:
    require(
        isinstance(record, Mapping)
        and set(record) >= {"path", "bytes", "sha256"}
        and record["path"] == path.name,
        f"{label} record drift",
    )
    require(
        record["bytes"] == path.stat().st_size and record["sha256"] == sha256(path),
        f"{label} identity drift",
    )


def validate_manifest_and_run(
    manifest: Mapping[str, Any],
    producer_run: Mapping[str, Any],
    *,
    input_seal_path: Path,
    calls_path: Path,
    systems_path: Path,
    prompt_bundle_path: Path,
    output_schema_path: Path,
    validator_path: Path,
    calls: Sequence[Mapping[str, Any]],
    systems: Mapping[str, Sequence[Any]],
) -> dict[str, bool]:
    require(
        manifest.get("schema_version") == "sqma-005-private-manifest-v1"
        and manifest.get("experiment_id") == "SQMA-005"
        and manifest.get("status") == "SealedAwaitingScore",
        "private manifest identity drift",
    )
    verify_record(manifest.get("input_seal"), input_seal_path, "input seal")
    verify_record(manifest.get("calls_artifact"), calls_path, "calls")
    verify_record(manifest.get("systems_artifact"), systems_path, "systems")
    prompt_identities = manifest.get("prompt_identities", {})
    require(
        prompt_identities
        == {
            "bundle_sha256": sha256(prompt_bundle_path),
            "schema_sha256": sha256(output_schema_path),
            "validator_sha256": sha256(validator_path),
        },
        "prompt identity drift",
    )
    plan = manifest.get("call_plan", {})
    require(
        plan.get("rows") == EXPECTED_ROWS and plan.get("calls_per_row") == 6
        and plan.get("physical_calls") == EXPECTED_CALLS
        and plan.get("single_pool_shared") is True,
        "manifest call plan drift",
    )
    require(
        manifest.get("score_authorized") is False
        and manifest.get("next_gate") == "independent_gold_consumer_scoring",
        "producer/consumer boundary drift",
    )
    access = manifest.get("access", {})
    require(access.get("model_loaded") is True, "producer model-load record drift")
    for key in (
        "gold_accessed", "classifier_accessed", "adapter_loaded", "training_executed",
        "optimizer_executed", "network_accessed", "validation_accessed", "test_accessed",
        "fold4_accessed",
    ):
        require(access.get(key) is False, f"producer access drift: {key}")

    require(
        producer_run.get("schema_version") == "sqma-005-producer-run-v1"
        and producer_run.get("experiment_id") == "SQMA-005"
        and producer_run.get("status") == "CompletedAwaitingScore",
        "producer run identity drift",
    )
    require(producer_run.get("access") == access, "public/private access drift")
    require(producer_run.get("model") == manifest.get("model_identity"), "model identity drift")
    require(
        producer_run.get("calls", {}).get("physical") == EXPECTED_CALLS
        and producer_run["calls"].get("per_row") == 6
        and producer_run["calls"].get("system_accounted")
        == {
            "S1": EXPECTED_ROWS, "S2a": EXPECTED_ROWS * 3,
            "S2b": sum(systems["s2b_k"]), "S3": EXPECTED_ROWS * 3,
        },
        "public call accounting drift",
    )
    aggregates = recompute_aggregates(calls, systems)
    require(producer_run.get("aggregates") == aggregates, "public aggregate replay drift")
    generated = sum(call["generated_tokens"] for call in calls)
    require(
        generated <= EXPECTED_GENERATED_CEILING
        and manifest.get("aggregate_cost", {}).get("generated_tokens") == generated
        and producer_run.get("resources", {}).get("generated_tokens") == generated,
        "generated-token budget drift",
    )
    require(
        manifest.get("aggregate_cost", {}).get("s2b_k_counts")
        == {str(key): value for key, value in sorted(Counter(systems["s2b_k"]).items())},
        "manifest S2b aggregate drift",
    )
    resources = producer_run.get("resources", {})
    for key in ("critical_memory_events", "oom_or_kill_events", "orphan_processes_after_exit"):
        require(resources.get(key) == 0, f"resource drift: {key}")
    require(
        resources.get("mlx_peak_bytes") == max(call["mlx_peak_bytes"] for call in calls),
        "MLX peak replay drift",
    )
    return {"schema": True, "budget": True, "resource": True}


def load_module(path: Path) -> Any:
    name = "sqma005_validator_for_independent_verifier"
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "validator import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON root drift")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    require(all(isinstance(value, dict) for value in values), "JSONL row drift")
    return values


def load_npz(path: Path, expected: set[str], expected_rows: int) -> dict[str, Any]:
    import numpy as np

    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "NPZ duplicate member")
        require(set(names) == {f"{name}.npy" for name in expected}, "NPZ member drift")
    with np.load(path, allow_pickle=False) as source:
        require(set(source.files) == expected, "NPZ inventory drift")
        arrays = {name: np.asarray(source[name]) for name in source.files}
    if expected == GOLD_ARRAYS:
        layout = {
            "sample_ids": ((expected_rows,), "U"),
            "component_ids": ((expected_rows,), "U"),
            "fold_ids": ((expected_rows,), "int8"),
            "source_ordinals": ((expected_rows,), "int32"),
            "gold": ((expected_rows, 6), "uint8"),
        }
    else:
        layout = {
            "sample_ids": ((expected_rows,), "U"),
            "component_ids": ((expected_rows,), "U"),
            "fold_ids": ((expected_rows,), "int8"),
            "source_ordinals": ((expected_rows,), "int32"),
            **{system: ((expected_rows, 6), "uint8") for system in SYSTEMS},
            "single_valid": ((expected_rows, 3), "uint8"),
            "role_valid": ((expected_rows, 3), "uint8"),
            "single_abstained": ((expected_rows, 3), "uint8"),
            "judge_abstained": ((expected_rows,), "uint8"),
            "s2b_k": ((expected_rows,), "uint8"),
            "s3_ceiling_tokens": ((expected_rows,), "int32"),
            "s2b_ceiling_tokens": ((expected_rows,), "int32"),
            "s2b_ceiling_utilization": ((expected_rows,), "float64"),
            "s3_actual_tokens": ((expected_rows,), "int32"),
            "s2b_actual_tokens": ((expected_rows,), "int32"),
        }
    for name, (shape, dtype) in layout.items():
        observed = arrays[name]
        require(observed.shape == shape, f"{name} NPZ shape drift")
        if dtype == "U":
            require(observed.dtype.kind == "U", f"{name} NPZ dtype drift")
        else:
            require(str(observed.dtype) == dtype, f"{name} NPZ dtype drift")
    require(bool(np.all(arrays["fold_ids"] == 3)), "NPZ fold drift")
    ordinals = arrays["source_ordinals"].tolist()
    require(ordinals == sorted(ordinals) and len(set(ordinals)) == expected_rows, "NPZ order drift")
    bit_arrays = ["gold"] if expected == GOLD_ARRAYS else [
        *SYSTEMS, "single_valid", "role_valid", "single_abstained", "judge_abstained",
    ]
    for name in bit_arrays:
        require(bool(np.all((arrays[name] == 0) | (arrays[name] == 1))), f"{name} NPZ bit drift")
    if expected == SYSTEM_ARRAYS:
        require(bool(np.all((arrays["s2b_k"] == 2) | (arrays["s2b_k"] == 3))), "S2b K drift")
    return arrays


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload); target.flush(); os.fsync(target.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--input-seal", required=True)
    parser.add_argument("--calls", required=True)
    parser.add_argument("--systems", required=True)
    parser.add_argument("--producer-manifest", required=True)
    parser.add_argument("--producer-run", required=True)
    parser.add_argument("--consumer-gold", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--prompt-bundle", required=True)
    parser.add_argument("--output-schema", required=True)
    parser.add_argument("--validator", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed-namespace", required=True)
    parser.add_argument("--replicates", type=int, default=BOOTSTRAP_REPLICATES)
    arguments = parser.parse_args()

    input_path = Path(arguments.input).resolve()
    input_seal_path = Path(arguments.input_seal).resolve()
    calls_path = Path(arguments.calls).resolve()
    systems_path = Path(arguments.systems).resolve()
    for path, label in (
        (input_path, "input snapshot"), (input_seal_path, "input seal"), (calls_path, "calls"),
        (systems_path, "systems"), (Path(arguments.producer_manifest).resolve(), "manifest"),
        (Path(arguments.consumer_gold).resolve(), "consumer gold"),
    ):
        regular_private_file(path, label)

    rows = load_jsonl(input_path)
    validate_input_rows(rows, EXPECTED_ROWS)
    input_seal = load_json(input_seal_path)
    require(
        input_seal.get("schema_version") == "sqma-005-input-seal-v1"
        and input_seal.get("snapshot", {}).get("sha256") == sha256(input_path)
        and input_seal["snapshot"].get("rows") == EXPECTED_ROWS
        and input_seal["snapshot"].get("components") == EXPECTED_COMPONENTS
        and input_seal["snapshot"].get("fold_id") == 3
        and input_seal.get("sample_order_sha256")
        == canonical_digest([row["sample_id"] for row in rows])
        and input_seal.get("row_membership_sha256")
        == canonical_digest(
            [(row["sample_id"], row["component_id"], row["source_ordinal"]) for row in rows]
        )
        and input_seal.get("gold_present") is False,
        "input seal replay drift",
    )

    calls = load_jsonl(calls_path)
    bundle = load_json(Path(arguments.prompt_bundle).resolve())
    validator = load_module(Path(arguments.validator).resolve())
    reconstructed = reconstruct_systems(
        calls, rows, validator, bundle,
        seed_namespace=arguments.seed_namespace,
    )
    persisted = load_npz(systems_path, SYSTEM_ARRAYS, EXPECTED_ROWS)
    for key, value in reconstructed.items():
        require(value == persisted[key].tolist(), f"systems replay drift: {key}")

    manifest = load_json(Path(arguments.producer_manifest).resolve())
    producer_run = load_json(Path(arguments.producer_run).resolve())
    integrity = validate_manifest_and_run(
        manifest, producer_run,
        input_seal_path=input_seal_path, calls_path=calls_path, systems_path=systems_path,
        prompt_bundle_path=Path(arguments.prompt_bundle).resolve(),
        output_schema_path=Path(arguments.output_schema).resolve(),
        validator_path=Path(arguments.validator).resolve(),
        calls=calls, systems=reconstructed,
    )
    gold = load_npz(Path(arguments.consumer_gold).resolve(), GOLD_ARRAYS, EXPECTED_ROWS)
    require(
        gold["sample_ids"].tolist() == reconstructed["sample_ids"]
        and gold["component_ids"].tolist() == reconstructed["component_ids"]
        and gold["fold_ids"].tolist() == reconstructed["fold_ids"]
        and gold["source_ordinals"].tolist() == reconstructed["source_ordinals"],
        "consumer gold identity drift",
    )
    result = independent_score(
        gold["gold"].tolist(),
        {system: reconstructed[system] for system in SYSTEMS},
        reconstructed["component_ids"],
        arguments.replicates,
    )
    score = load_json(Path(arguments.score).resolve())
    require(
        score.get("schema_version") == "sqma-005-score-v1"
        and score.get("rows") == EXPECTED_ROWS
        and score.get("components") == EXPECTED_COMPONENTS
        and score.get("label_order") == list(LABEL_ORDER)
        and score.get("systems") == result["systems"]
        and score.get("contrasts") == result["contrasts"]
        and score.get("integrity") == integrity,
        "score replay drift",
    )
    expected_score_inputs = {
        "consumer_gold": {
            "bytes": Path(arguments.consumer_gold).stat().st_size,
            "sha256": sha256(Path(arguments.consumer_gold).resolve()),
        },
        "systems": {"bytes": systems_path.stat().st_size, "sha256": sha256(systems_path)},
        "producer_manifest": {
            "bytes": Path(arguments.producer_manifest).stat().st_size,
            "sha256": sha256(Path(arguments.producer_manifest).resolve()),
        },
        "producer_run": {
            "bytes": Path(arguments.producer_run).stat().st_size,
            "sha256": sha256(Path(arguments.producer_run).resolve()),
        },
    }
    require(score.get("inputs") == expected_score_inputs, "score input identity drift")
    expected_bootstrap = {
        "unit": "duplicate_component_id", "replicates": arguments.replicates,
        "seed": BOOTSTRAP_SEED, "namespace": BOOTSTRAP_NAMESPACE,
        "algorithm": BOOTSTRAP_ALGORITHM, "paired_multiplicities": True,
        "zero_division": 0,
    }
    require(score.get("bootstrap") == expected_bootstrap, "bootstrap identity drift")
    gate = evaluate_gate(result["contrasts"], integrity)
    require(score.get("tune_gate") == gate, "Tune gate drift")

    output = {
        "schema_version": "sqma-005-verification-v1", "experiment_id": "SQMA-005",
        "status": "Passed", "calls": EXPECTED_CALLS, "rows": EXPECTED_ROWS,
        "components": EXPECTED_COMPONENTS, "systems": result["systems"],
        "contrasts": result["contrasts"], "tune_gate": gate,
        "bootstrap": expected_bootstrap,
        "replay": {
            "call_order": True, "seed_schedule": True, "context_hashes": True,
            "messages_hashes": True, "raw_validation": True, "system_aggregation": True,
            "budget_and_resources": True, "prompt_token_ids_hash_recomputed": False,
            "truncated_bpe_boundary_recomputed": False,
        },
        "access": {
            "producer_imported": False, "scorer_imported": False,
            "model_framework_imported": False, "gold_read_by_verifier": True,
            "classifier_accessed": False, "adapter_loaded": False,
        },
    }
    require(not public_sensitive_paths(output), "public verification leak")
    write_json_exclusive(Path(arguments.output).resolve(), output)
    print(json.dumps({"status": "Passed", "tune_gate_passed": gate["passed"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        KeyError, TypeError, ValueError, OSError, ImportError, zipfile.BadZipFile,
        VerificationError
    ) as exc:
        print(
            f"SQMA-005 verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        raise SystemExit(1)

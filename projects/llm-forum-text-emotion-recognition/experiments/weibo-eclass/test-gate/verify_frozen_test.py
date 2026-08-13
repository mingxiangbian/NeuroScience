#!/usr/bin/env python3
"""Independently verify the completed EXP-049 frozen test evaluation."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import stat
import statistics
import subprocess
from typing import Any, Iterable, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "configs" / "exp-049-test-ready.json"
CONDITIONS = (
    "m0-majority",
    "m1-target-only",
    "encoder-seed-42",
    "encoder-seed-43",
    "encoder-seed-44",
    "qwen-reference",
    "qwen-lora-seed-42",
    "qwen-lora-seed-43",
    "qwen-lora-seed-44",
)
BASELINE_CONDITIONS = CONDITIONS[:5]
QWEN_CONDITIONS = CONDITIONS[5:]
INVALID_LABEL = "__invalid__"
ATOL = 1e-12


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"bytes": path.stat().st_size, "path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def verify_spec(spec: dict[str, Any]) -> Path:
    path = project_path(spec["path"])
    if path.stat().st_size != int(spec["bytes"]) or sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen artifact drift: {spec['path']}")
    return path


def compare(actual: Any, expected: Any, name: str, mismatches: list[str]) -> None:
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), expected, rel_tol=1e-10, abs_tol=ATOL
        ):
            mismatches.append(f"{name}: {actual!r} != {expected!r}")
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            mismatches.append(f"{name}: dictionary keys/type differ")
            return
        for key in expected:
            compare(actual[key], expected[key], f"{name}.{key}", mismatches)
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            mismatches.append(f"{name}: list length/type differs")
            return
        for index, value in enumerate(expected):
            compare(actual[index], value, f"{name}[{index}]", mismatches)
        return
    if actual != expected:
        mismatches.append(f"{name}: {actual!r} != {expected!r}")


def load_inputs(contract: dict[str, Any]) -> list[dict[str, Any]]:
    spec = contract["data"]["test_inputs"]
    path = project_path(spec["path"])
    if path.stat().st_size != spec["bytes"] or sha256_file(path) != spec["sha256"]:
        raise ValueError("Test-input hash drift")
    rows = read_jsonl(path)
    expected_keys = {
        "ambiguous_target",
        "context_available",
        "group_id",
        "protocol_id",
        "sample_id",
        "schema_version",
        "views",
    }
    seen = set()
    for index, row in enumerate(rows):
        if set(row) != expected_keys or "label" in row:
            raise ValueError(f"Test-input schema drift at row {index}")
        if row["protocol_id"] != contract["data"]["protocol_id"]:
            raise ValueError(f"Test-input protocol drift at row {index}")
        if row["sample_id"] in seen:
            raise ValueError("Duplicate test sample_id")
        seen.add(row["sample_id"])
        target = row["views"]["target_only"]["target"]
        paired = row["views"]["previous_context"]
        if not target or paired["target"] != target:
            raise ValueError(f"Test view-pair drift at row {index}")
        if bool(paired["previous"]) != bool(row["context_available"]):
            raise ValueError(f"Test context flag drift at row {index}")
    if len(rows) != spec["rows"]:
        raise ValueError("Test-input row-count drift")
    return rows


def load_labels(contract: dict[str, Any]) -> list[dict[str, Any]]:
    spec = contract["data"]["test_labels"]
    path = project_path(spec["path"])
    if path.stat().st_size != spec["bytes"] or sha256_file(path) != spec["sha256"]:
        raise ValueError("Sealed-label hash drift")
    rows = read_jsonl(path)
    expected_keys = {"label", "protocol_id", "sample_id", "schema_version"}
    seen = set()
    for index, row in enumerate(rows):
        if set(row) != expected_keys:
            raise ValueError(f"Test-label schema drift at row {index}")
        if row["protocol_id"] != contract["data"]["protocol_id"]:
            raise ValueError(f"Test-label protocol drift at row {index}")
        if row["label"] not in contract["labels"]:
            raise ValueError(f"Test-label ontology drift at row {index}")
        if row["sample_id"] in seen:
            raise ValueError("Duplicate test-label sample_id")
        seen.add(row["sample_id"])
    if len(rows) != spec["rows"]:
        raise ValueError("Test-label row-count drift")
    return rows


def divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def metrics(gold: Sequence[str], predicted: Sequence[str], labels: Sequence[str]) -> dict[str, Any]:
    if len(gold) != len(predicted) or not gold:
        raise ValueError("Metric rows are not aligned")
    per_class = {}
    f1_values = []
    precision_values = []
    recall_values = []
    weighted = 0.0
    for label in labels:
        tp = sum(left == label and right == label for left, right in zip(gold, predicted))
        fp = sum(left != label and right == label for left, right in zip(gold, predicted))
        fn = sum(left == label and right != label for left, right in zip(gold, predicted))
        support = sum(left == label for left in gold)
        predicted_support = sum(right == label for right in predicted)
        precision = divide(tp, tp + fp)
        recall = divide(tp, tp + fn)
        f1 = divide(2 * precision * recall, precision + recall)
        per_class[label] = {
            "f1": f1,
            "precision": precision,
            "predicted_support": predicted_support,
            "recall": recall,
            "support": support,
        }
        f1_values.append(f1)
        precision_values.append(precision)
        recall_values.append(recall)
        weighted += f1 * support
    columns = list(labels) + [INVALID_LABEL]
    matrix = [
        [
            sum(left == gold_label and right == predicted_label for left, right in zip(gold, predicted))
            for predicted_label in columns
        ]
        for gold_label in labels
    ]
    return {
        "accuracy": sum(left == right for left, right in zip(gold, predicted)) / len(gold),
        "confusion_columns": columns,
        "confusion_matrix": matrix,
        "macro_f1": statistics.fmean(f1_values),
        "macro_precision": statistics.fmean(precision_values),
        "macro_recall": statistics.fmean(recall_values),
        "per_class": per_class,
        "rows": len(gold),
        "weighted_f1": weighted / len(gold),
    }


def slice_metrics(
    rows: Sequence[dict[str, Any]],
    gold: Sequence[str],
    predicted: Sequence[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    long_tail = set(contract["evaluation"]["long_tail_labels"])
    masks = {
        "all": [True] * len(rows),
        "context_available": [bool(row["context_available"]) for row in rows],
        "first_clause": [not bool(row["context_available"]) for row in rows],
        "ambiguous_target": [bool(row["ambiguous_target"]) for row in rows],
        "unambiguous_target": [not bool(row["ambiguous_target"]) for row in rows],
        "no_emotion": [label == "no_emotion" for label in gold],
        "emotion_label": [label != "no_emotion" for label in gold],
        "long_tail_label": [label in long_tail for label in gold],
    }
    if list(masks) != contract["evaluation"]["slices"]:
        raise ValueError("Frozen slice registry drift")
    return {
        name: metrics(
            [value for value, keep in zip(gold, mask) if keep],
            [value for value, keep in zip(predicted, mask) if keep],
            contract["labels"],
        )
        for name, mask in masks.items()
    }


def macro_f1_fast(gold: Sequence[str], predicted: Sequence[str], labels: Sequence[str]) -> float:
    support = Counter(gold)
    predicted_support = Counter(predicted)
    true_positive = Counter(left for left, right in zip(gold, predicted) if left == right)
    f1 = []
    for label in labels:
        tp = true_positive[label]
        fp = predicted_support[label] - tp
        fn = support[label] - tp
        f1.append(divide(2 * tp, 2 * tp + fp + fn))
    return statistics.fmean(f1)


def quantile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_contrast(
    rows: Sequence[dict[str, Any]],
    gold: Sequence[str],
    predictions: dict[str, Sequence[str]],
    candidate_units: Sequence[str],
    reference_units: Sequence[str],
    labels: Sequence[str],
    repeats: int,
    namespace: str,
) -> dict[str, Any]:
    group_indices: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        group_indices.setdefault(row["group_id"], []).append(index)
    groups = sorted(group_indices)
    randomizer = random.Random(int(sha256_text(namespace)[:16], 16))

    def family_score(indices: Sequence[int], units: Sequence[str]) -> float:
        sampled_gold = [gold[index] for index in indices]
        return statistics.fmean(
            macro_f1_fast(
                sampled_gold,
                [predictions[unit][index] for index in indices],
                labels,
            )
            for unit in units
        )

    deltas = []
    for _ in range(repeats):
        sampled_groups = [randomizer.choice(groups) for _ in groups]
        indices = [index for group in sampled_groups for index in group_indices[group]]
        deltas.append(family_score(indices, candidate_units) - family_score(indices, reference_units))
    all_indices = list(range(len(rows)))
    observed = family_score(all_indices, candidate_units) - family_score(all_indices, reference_units)
    return {
        "candidate_units": list(candidate_units),
        "ci95": [quantile(deltas, 0.025), quantile(deltas, 0.975)],
        "groups": len(groups),
        "observed_delta": observed,
        "probability_delta_gt_zero": sum(value > 0 for value in deltas) / len(deltas),
        "reference_units": list(reference_units),
        "repeats": repeats,
        "resampling_unit": "group_id",
    }


def decision(delta: float, threshold: float) -> str:
    if delta >= threshold:
        return "material_improvement"
    if delta <= -threshold:
        return "material_degradation"
    return "practical_tie"


def independent_parse(output: str, labels: Sequence[str]) -> dict[str, Any]:
    if not isinstance(output, str) or not output.strip():
        return {
            "canonical_output": None,
            "error": "empty_output",
            "label": None,
            "opening_marker_found": False,
            "thinking_boundary_found": False,
            "valid": False,
        }
    opening = "<think>" in output
    close_count = output.count("</think>")

    def invalid(error: str, boundary: bool = False, opening_found: bool = opening) -> dict[str, Any]:
        return {
            "canonical_output": None,
            "error": error,
            "label": None,
            "opening_marker_found": opening_found,
            "thinking_boundary_found": boundary,
            "valid": False,
        }

    if close_count != 1:
        return invalid("missing_thinking_boundary" if close_count == 0 else "multiple_thinking_boundaries")
    prefix, candidate = output.split("</think>", maxsplit=1)
    if prefix.count("<think>") > 1:
        return invalid("multiple_opening_markers", True, True)
    if opening and not prefix.lstrip().startswith("<think>"):
        return invalid("misplaced_opening_marker", True, True)
    candidate = candidate.strip()
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        return invalid("invalid_json", True)
    if not isinstance(decoded, dict):
        return invalid("json_not_object", True)
    if set(decoded) != {"label"}:
        return invalid("schema_keys_mismatch", True)
    label = decoded["label"]
    if not isinstance(label, str):
        return invalid("label_not_string", True)
    if label not in labels:
        return invalid("unknown_label", True)
    return {
        "canonical_output": json.dumps({"label": label}, ensure_ascii=True, separators=(",", ":")),
        "error": None,
        "label": label,
        "opening_marker_found": opening,
        "thinking_boundary_found": True,
        "valid": True,
    }


def number_summary(values: Sequence[float | int]) -> dict[str, float | int]:
    ordered = sorted(float(value) for value in values)
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "p95": quantile(ordered, 0.95),
        "sum": sum(values),
    }


def build_messages(contract: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in contract["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions, output_schema=prompt["output_schema"]
    )
    user = prompt["target_only_template"].format(target=row["views"]["target_only"]["target"])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def message_hash(messages: list[dict[str, str]]) -> str:
    return sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def verify_prediction_records(
    contract: dict[str, Any], rows: Sequence[dict[str, Any]], mismatches: list[str]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[str]], dict[str, Any]]:
    private = project_path(contract["outputs"]["private_dir"])
    records: dict[str, list[dict[str, Any]]] = {}
    predictions: dict[str, list[str]] = {}
    qwen_reconstruction = {}
    prompt = load_json(verify_spec(contract["frozen_sources"]["prompt"]))
    model_path = project_path(contract["qwen"]["model"]["local_path"])
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    for condition in CONDITIONS:
        path = private / f"condition-{condition}-predictions.jsonl"
        condition_rows = read_jsonl(path)
        if len(condition_rows) != len(rows):
            mismatches.append(f"{condition}: prediction row count")
            continue
        observed_predictions = []
        for index, (record, source) in enumerate(zip(condition_rows, rows)):
            if (
                record.get("condition") != condition
                or record.get("row_index") != index
                or record.get("sample_id") != source["sample_id"]
                or record.get("group_id") != source["group_id"]
                or record.get("context_available") != bool(source["context_available"])
                or record.get("ambiguous_target") != bool(source["ambiguous_target"])
                or record.get("view") != "target_only"
                or "gold_label" in record
            ):
                mismatches.append(f"{condition}: identity/schema row {index}")
                break
            prediction = record.get("prediction")
            if prediction not in set(contract["labels"]) | {INVALID_LABEL}:
                mismatches.append(f"{condition}: invalid prediction row {index}")
                break
            observed_predictions.append(prediction)
            if condition in BASELINE_CONDITIONS:
                scores = record.get("scores")
                if condition == "m0-majority":
                    if scores is not None or prediction != "no_emotion" or record.get("score_type") != "constant":
                        mismatches.append(f"{condition}: frozen constant row {index}")
                        break
                else:
                    if not isinstance(scores, dict) or list(scores) != contract["labels"]:
                        mismatches.append(f"{condition}: score ontology row {index}")
                        break
                    values = [scores[label] for label in contract["labels"]]
                    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
                        mismatches.append(f"{condition}: nonfinite score row {index}")
                        break
                    expected_prediction = contract["labels"][max(range(len(values)), key=values.__getitem__)]
                    if prediction != expected_prediction:
                        mismatches.append(f"{condition}: argmax prediction row {index}")
                        break
                    if condition.startswith("encoder-"):
                        if record.get("score_type") != "probability" or not math.isclose(
                            sum(values), 1.0, rel_tol=0, abs_tol=1e-5
                        ):
                            mismatches.append(f"{condition}: probability row {index}")
                            break
                    elif record.get("score_type") != "decision":
                        mismatches.append(f"{condition}: decision score row {index}")
                        break
            else:
                raw_output = record.get("raw_output")
                if not isinstance(raw_output, str):
                    mismatches.append(f"{condition}: missing raw output row {index}")
                    break
                messages = build_messages(contract, prompt, source)
                prompt_ids = list(
                    tokenizer.apply_chat_template(
                        messages,
                        add_generation_prompt=True,
                        enable_thinking=True,
                        tokenize=True,
                        return_dict=False,
                    )
                )
                generated_tokens = len(tokenizer.encode(raw_output, add_special_tokens=False))
                if "</think>" in raw_output:
                    thinking, final = raw_output.split("</think>", maxsplit=1)
                    thinking_tokens = len(tokenizer.encode(thinking, add_special_tokens=False))
                    final_tokens = len(tokenizer.encode(final, add_special_tokens=False))
                else:
                    thinking_tokens, final_tokens = generated_tokens, 0
                parsed = independent_parse(raw_output, contract["labels"])
                expected = {
                    "final_tokens": final_tokens,
                    "generated_tokens": generated_tokens,
                    "likely_truncated": generated_tokens
                    >= contract["qwen"]["generation"]["max_new_tokens"] - 2,
                    "message_sha256": message_hash(messages),
                    "parse": parsed,
                    "prediction": parsed["label"] if parsed["valid"] else INVALID_LABEL,
                    "prompt_sha256": sha256_text(json.dumps(prompt_ids, separators=(",", ":"))),
                    "prompt_tokens": len(prompt_ids),
                    "raw_output_sha256": sha256_text(raw_output),
                    "thinking_tokens": thinking_tokens,
                }
                for key, value in expected.items():
                    if record.get(key) != value:
                        mismatches.append(f"{condition}: {key} row {index}")
                        break
                if len(prompt_ids) > contract["qwen"]["generation"]["max_input_tokens"]:
                    mismatches.append(f"{condition}: prompt token budget row {index}")
                    break
                if not isinstance(record.get("generation_seconds"), (int, float)) or record["generation_seconds"] <= 0:
                    mismatches.append(f"{condition}: timing row {index}")
                    break
        records[condition] = condition_rows
        predictions[condition] = observed_predictions
        if condition in QWEN_CONDITIONS and len(observed_predictions) == len(rows):
            valid = sum(bool(record["parse"]["valid"]) for record in condition_rows)
            qwen_reconstruction[condition] = {
                "generation": {
                    "active_generation_seconds": sum(record["generation_seconds"] for record in condition_rows),
                    "final_tokens": number_summary([record["final_tokens"] for record in condition_rows]),
                    "generated_tokens": number_summary([record["generated_tokens"] for record in condition_rows]),
                    "generation_seconds": number_summary([record["generation_seconds"] for record in condition_rows]),
                    "prompt_tokens": number_summary([record["prompt_tokens"] for record in condition_rows]),
                    "thinking_tokens": number_summary([record["thinking_tokens"] for record in condition_rows]),
                },
                "parser": {
                    "error_counts": dict(
                        sorted(Counter(record["parse"]["error"] for record in condition_rows if record["parse"]["error"]).items())
                    ),
                    "likely_truncated_count": sum(bool(record["likely_truncated"]) for record in condition_rows),
                    "valid_count": valid,
                    "valid_rate": valid / len(condition_rows),
                },
            }
    return records, predictions, qwen_reconstruction


def verify_csv_artifacts(
    contract: dict[str, Any],
    condition: str,
    rebuilt: dict[str, Any],
    mismatches: list[str],
) -> None:
    root = project_path(contract["outputs"]["public_dir"]) / "conditions" / condition
    per_class_path = root / "per-class-metrics.csv"
    with per_class_path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    expected_rows = []
    for slice_name, values in rebuilt["slices"].items():
        for label in contract["labels"]:
            value = values["per_class"][label]
            expected_rows.append(
                {
                    "slice": slice_name,
                    "label": label,
                    "precision": str(value["precision"]),
                    "recall": str(value["recall"]),
                    "f1": str(value["f1"]),
                    "support": str(value["support"]),
                    "predicted_support": str(value["predicted_support"]),
                }
            )
    if rows != expected_rows:
        mismatches.append(f"{condition}: per-class CSV")
    confusion_path = root / "confusion-matrix.csv"
    with confusion_path.open("r", encoding="utf-8", newline="") as source:
        confusion = list(csv.DictReader(source))
    expected_confusion = []
    all_metrics = rebuilt["slices"]["all"]
    for label, values in zip(contract["labels"], all_metrics["confusion_matrix"]):
        row = {"gold_label": label}
        row.update({column: str(value) for column, value in zip(all_metrics["confusion_columns"], values)})
        expected_confusion.append(row)
    if confusion != expected_confusion:
        mismatches.append(f"{condition}: confusion CSV")


def verify_outputs(contract: dict[str, Any], mismatches: list[str]) -> dict[str, Any]:
    public = project_path(contract["outputs"]["public_dir"])
    private = project_path(contract["outputs"]["private_dir"])
    run = load_json(public / "run.json")
    aggregate = load_json(public / "aggregate-metrics.json")
    label_opening = load_json(public / "label-opening.json")
    inputs = load_inputs(contract)
    label_rows = load_labels(contract)
    if [row["sample_id"] for row in inputs] != [row["sample_id"] for row in label_rows]:
        mismatches.append("test input/label alignment")
    gold = [row["label"] for row in label_rows]
    records, predictions, qwen_reconstruction = verify_prediction_records(contract, inputs, mismatches)
    if any(len(predictions.get(condition, ())) != len(inputs) for condition in CONDITIONS):
        return {"rows": len(inputs)}

    rebuilt_metrics = {}
    for condition in CONDITIONS:
        rebuilt = {
            "condition": condition,
            "experiment_id": "EXP-049",
            "slices": slice_metrics(inputs, gold, predictions[condition], contract),
        }
        rebuilt_metrics[condition] = rebuilt
        stored = load_json(public / "conditions" / condition / "metrics.json")
        compare(stored, rebuilt, f"{condition}.metrics", mismatches)
        compare(aggregate["units"][condition]["metrics"], rebuilt, f"aggregate.{condition}.metrics", mismatches)
        verify_csv_artifacts(contract, condition, rebuilt, mismatches)

    for condition in QWEN_CONDITIONS:
        summary = load_json(public / f"condition-{condition}.json")
        compare(summary.get("parser"), qwen_reconstruction[condition]["parser"], f"{condition}.parser", mismatches)
        for key, expected in qwen_reconstruction[condition]["generation"].items():
            compare(summary["generation"].get(key), expected, f"{condition}.generation.{key}", mismatches)
        if (
            summary["generation"].get("api_cost_usd") != 0
            or summary["generation"].get("batch_size") != 1
            or summary.get("performance_metrics_computed") is not False
            or summary.get("test_labels_accessed") is not False
        ):
            mismatches.append(f"{condition}: pre-label summary boundary")
        maximum = contract["resource_budget"][
            "qwen_reference_hours_max" if condition == "qwen-reference" else "qwen_lora_hours_max_per_unit"
        ] * 3600
        if qwen_reconstruction[condition]["generation"]["active_generation_seconds"] > maximum:
            mismatches.append(f"{condition}: resource budget")
    for condition in BASELINE_CONDITIONS:
        summary = load_json(public / f"condition-{condition}.json")
        if summary.get("performance_metrics_computed") is not False or summary.get("test_labels_accessed") is not False:
            mismatches.append(f"{condition}: pre-label summary boundary")

    rebuilt_families = {}
    for family_id, family in contract["families"].items():
        result = {"family": family["name"], "unit_ids": family["unit_ids"], "unit_count": len(family["unit_ids"])}
        for metric_name in ("macro_f1", "accuracy", "macro_precision", "macro_recall", "weighted_f1"):
            values = [rebuilt_metrics[unit]["slices"]["all"][metric_name] for unit in family["unit_ids"]]
            result[metric_name] = {
                "mean": statistics.fmean(values),
                "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
                "values": values,
            }
        rebuilt_families[family_id] = result
    compare(aggregate.get("families"), rebuilt_families, "aggregate.families", mismatches)

    rebuilt_contrasts = {}
    for contrast_id, contrast in contract["evaluation"]["contrasts"].items():
        result = bootstrap_contrast(
            inputs,
            gold,
            predictions,
            contrast["candidate_units"],
            contrast["reference_units"],
            contract["labels"],
            contract["evaluation"]["bootstrap_repeats"],
            f"{contract['evaluation']['bootstrap_seed_namespace']}:{contrast_id}",
        )
        result["decision"] = decision(result["observed_delta"], contract["evaluation"]["practical_tie_macro_f1"])
        rebuilt_contrasts[contrast_id] = result
    compare(aggregate.get("contrasts"), rebuilt_contrasts, "aggregate.contrasts", mismatches)

    scored = read_jsonl(private / "scored-predictions.jsonl")
    if len(scored) != len(inputs):
        mismatches.append("private scored prediction row count")
    else:
        for index, (record, source) in enumerate(zip(scored, inputs)):
            expected = {
                "gold_label": gold[index],
                "group_id": source["group_id"],
                "predictions": {condition: predictions[condition][index] for condition in CONDITIONS},
                "row_index": index,
                "sample_id": source["sample_id"],
            }
            if record != expected:
                mismatches.append(f"private scored prediction row {index}")
                break

    with (public / "unit-results.csv").open("r", encoding="utf-8", newline="") as source:
        unit_rows = list(csv.DictReader(source))
    if [row["condition"] for row in unit_rows] != list(CONDITIONS):
        mismatches.append("unit-results condition order")
    else:
        for row in unit_rows:
            condition = row["condition"]
            values = rebuilt_metrics[condition]["slices"]["all"]
            expected_numeric = {
                "accuracy": values["accuracy"],
                "dev_macro_f1": contract["unit_registry"][condition]["dev_macro_f1"],
                "macro_f1": values["macro_f1"],
                "macro_precision": values["macro_precision"],
                "macro_recall": values["macro_recall"],
                "weighted_f1": values["weighted_f1"],
            }
            for key, expected in expected_numeric.items():
                if not math.isclose(float(row[key]), expected, rel_tol=1e-10, abs_tol=ATOL):
                    mismatches.append(f"unit-results {condition} {key}")

    if (
        label_opening.get("status") != "Consumed"
        or label_opening.get("all_nine_prediction_files_complete_before_open") is not True
        or label_opening.get("model_calls_after_open") != 0
        or label_opening.get("rows") != len(inputs)
        or label_opening.get("labels_opened_at_utc") != aggregate.get("label_opened_at_utc")
        or run.get("label_opening", {}).get("status") != "consumed"
        or run.get("test_inputs_accessed") is not True
        or run.get("test_labels_accessed") is not True
    ):
        mismatches.append("single label-opening state transition")
    opening_time = aggregate.get("label_opened_at_utc", "")
    for condition in CONDITIONS:
        stage = run.get("stages", {}).get(f"infer__{condition}", {})
        if stage.get("status") != "Completed" or stage.get("completed_at_utc", "") > opening_time:
            mismatches.append(f"run stage before label opening: {condition}")
        expected_prediction_artifact = artifact(private / f"condition-{condition}-predictions.jsonl")
        if stage.get("private_predictions") != expected_prediction_artifact:
            mismatches.append(f"run private artifact: {condition}")

    expected_baseline_seconds = sum(
        float(load_json(public / f"condition-{condition}.json")["total_seconds"])
        for condition in BASELINE_CONDITIONS
    )
    expected_qwen_seconds = sum(
        qwen_reconstruction[condition]["generation"]["active_generation_seconds"]
        for condition in QWEN_CONDITIONS
    )
    expected_resource = {
        "baseline_encoder_seconds": expected_baseline_seconds,
        "qwen_active_generation_seconds": expected_qwen_seconds,
    }
    compare(aggregate.get("resource"), expected_resource, "aggregate.resource", mismatches)
    if expected_baseline_seconds > contract["resource_budget"]["baseline_encoder_hours_max_total"] * 3600:
        mismatches.append("baseline/encoder total resource budget")
    if expected_qwen_seconds > contract["resource_budget"]["qwen_total_hours_max"] * 3600:
        mismatches.append("Qwen total resource budget")

    public_files = [path for path in public.rglob("*") if path.is_file()]
    public_text = "\n".join(path.read_text(encoding="utf-8") for path in public_files)
    leaked_ids = [
        value
        for value in {*(row["sample_id"] for row in inputs), *(row["group_id"] for row in inputs)}
        if value in public_text
    ]
    text_candidates = set()
    for row in inputs:
        target = row["views"]["target_only"]["target"]
        previous = row["views"]["previous_context"]["previous"]
        if len(target) >= 12:
            text_candidates.add(target)
        if isinstance(previous, str) and len(previous) >= 12:
            text_candidates.add(previous)
    leaked_text = [value for value in text_candidates if value in public_text]
    if leaked_ids or leaked_text:
        mismatches.append(f"public privacy leak ids={len(leaked_ids)} text={len(leaked_text)}")

    if stat.S_IMODE(private.stat().st_mode) != 0o700:
        mismatches.append("private directory mode")
    for path in private.rglob("*"):
        mode = stat.S_IMODE(path.stat().st_mode)
        if path.is_dir() and mode != 0o700:
            mismatches.append(f"private directory mode: {display_path(path)}")
        elif path.is_file() and mode != 0o600:
            mismatches.append(f"private file mode: {display_path(path)}")
    relative_private = private.relative_to(REPO_ROOT)
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(relative_private)], cwd=REPO_ROOT, check=False
    ).returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(relative_private)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    ).returncode == 0
    if not ignored or tracked:
        mismatches.append("private Git boundary")

    return {
        "aggregate": aggregate,
        "contrasts": rebuilt_contrasts,
        "families": rebuilt_families,
        "metrics": rebuilt_metrics,
        "privacy": {
            "private_files_checked": sum(path.is_file() for path in private.rglob("*")),
            "private_gitignored": ignored,
            "private_tracked": tracked,
            "public_files_scanned": len(public_files),
            "raw_text_leak_count": len(leaked_text),
            "source_id_leak_count": len(leaked_ids),
        },
        "prediction_files": len(records),
        "prediction_rows": sum(len(value) for value in records.values()),
        "qwen_reconstruction": qwen_reconstruction,
        "rows": len(inputs),
    }


def verify_contract(contract: dict[str, Any], mismatches: list[str]) -> None:
    if (
        contract.get("contract_id") != "EXP-049-TEST-READY-V1"
        or contract.get("experiment_id") != "EXP-049"
        or contract.get("status") != "Frozen TEST-READY"
        or tuple(contract.get("condition_order", ())) != CONDITIONS
        or contract.get("test_policy", {}).get("all_predictions_before_label_open") is not True
        or contract.get("test_policy", {}).get("allow_post_result_tuning") is not False
    ):
        mismatches.append("frozen contract scientific registry")
    for spec in contract["implementation"].values():
        try:
            verify_spec(spec)
        except (OSError, ValueError) as error:
            mismatches.append(str(error))
    try:
        authorization = load_json(verify_spec(contract["authorization"]))
        if (
            authorization.get("status") != "Authorized"
            or tuple(authorization.get("authorized_conditions_in_order", ())) != CONDITIONS
            or authorization.get("authorized_formal_test_units") != 9
        ):
            mismatches.append("authorization registry")
        ready = load_json(project_path(contract["test_ready_verification_path"]))
        if (
            ready.get("status") != "Passed"
            or ready.get("test_inputs_opened") is not False
            or ready.get("test_labels_opened") is not False
            or ready.get("contract", {}).get("sha256") != sha256_file(CONTRACT_PATH)
        ):
            mismatches.append("TEST-READY verification")
    except (OSError, ValueError) as error:
        mismatches.append(str(error))
    for item in contract["upstream_verifications"]:
        try:
            value = load_json(verify_spec(item["artifact"]))
            if value.get("status") != item["expected_status"]:
                mismatches.append(f"upstream status {item['artifact']['path']}")
            for key, expected in item.get("required_fields", {}).items():
                if value.get(key) != expected:
                    mismatches.append(f"upstream boundary {item['artifact']['path']}:{key}")
        except (OSError, ValueError) as error:
            mismatches.append(str(error))


def mark_verified(contract: dict[str, Any], recalculated: dict[str, Any]) -> dict[str, Any]:
    public = project_path(contract["outputs"]["public_dir"])
    aggregate_path = public / "aggregate-metrics.json"
    report_path = public / "REPORT.md"
    run_path = public / "run.json"
    aggregate = load_json(aggregate_path)
    run = load_json(run_path)
    aggregate["status"] = "Verified"
    run["status"] = "Verified"
    report = report_path.read_text(encoding="utf-8").replace(
        "Status: Completed; pending independent verification.",
        "Status: Verified by an independent metric and privacy reconstruction.",
    )
    atomic_json(aggregate_path, aggregate)
    atomic_text(report_path, report)
    run["stages"]["finalize"]["aggregate"] = artifact(aggregate_path)
    run["stages"]["finalize"]["report"] = artifact(report_path)
    atomic_json(run_path, run)
    return {
        "aggregate": artifact(aggregate_path),
        "report": artifact(report_path),
        "run": artifact(run_path),
    }


def main() -> None:
    contract = load_json(CONTRACT_PATH)
    public = project_path(contract["outputs"]["public_dir"])
    output = public / "verification.json"
    if output.exists():
        raise FileExistsError("EXP-049 verification is append-only")
    mismatches: list[str] = []
    verify_contract(contract, mismatches)
    recalculated = verify_outputs(contract, mismatches)
    checks = [
        "frozen contract, authorization, implementation and upstream evidence",
        "1,273 test inputs and sealed labels by registered hashes and ordered IDs",
        "nine private prediction files and exact row alignment",
        "baseline decision/probability semantics without post-label model calls",
        "independent Qwen prompt-token, parser, output-hash and token reconstruction",
        "all aggregate, slice, per-label and confusion metrics",
        "three-seed family means and sample standard deviations",
        "three deterministic group-level paired bootstrap contrasts",
        "single label-opening transition after all nine prediction files",
        "resource budgets, private permissions, Git ignore and public privacy",
    ]
    if mismatches:
        report = {
            "check_count": len(checks),
            "checks": checks,
            "completed_at_utc": utc_now(),
            "contract": artifact(CONTRACT_PATH),
            "experiment_id": "EXP-049",
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "status": "Failed",
            "test_inputs_accessed": True,
            "test_labels_accessed": True,
            "verification_id": "EXP-049-FROZEN-TEST-VERIFY-V1",
        }
        atomic_json(output, report)
        raise SystemExit(json.dumps(report, sort_keys=True))

    final_artifacts = mark_verified(contract, recalculated)
    verification = {
        "check_count": len(checks),
        "checks": checks,
        "completed_at_utc": utc_now(),
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": "EXP-049",
        "final_artifacts": final_artifacts,
        "independent_implementation": True,
        "mismatch_count": 0,
        "mismatches": [],
        "recalculated": {
            "contrasts": recalculated["contrasts"],
            "families": recalculated["families"],
            "privacy": recalculated["privacy"],
            "prediction_files": recalculated["prediction_files"],
            "prediction_rows": recalculated["prediction_rows"],
            "rows": recalculated["rows"],
        },
        "status": "Verified",
        "test_inputs_accessed": True,
        "test_labels_accessed": True,
        "verification_id": "EXP-049-FROZEN-TEST-VERIFY-V1",
    }
    atomic_json(output, verification)
    print(
        json.dumps(
            {
                "mismatch_count": 0,
                "status": "Verified",
                "verification": display_path(output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

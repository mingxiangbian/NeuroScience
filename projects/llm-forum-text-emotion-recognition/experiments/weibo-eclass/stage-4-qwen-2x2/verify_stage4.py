#!/usr/bin/env python3
"""Independent verifier for EXP-043; does not import runner or parser code."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
from typing import Any, Sequence


MODULE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_DIR = MODULE_ROOT / "runs" / "exp-043-frozen-qwen-2x2"
INVALID_LABEL = "__invalid__"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
        raise ValueError(f"Path escapes project root: {value}")
    return path


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def quantile(values: Sequence[float | int], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def independent_parse(output: str, thinking: bool, labels: Sequence[str]) -> dict[str, Any]:
    result = {
        "canonical_output": None,
        "error": None,
        "label": None,
        "opening_marker_found": False,
        "thinking_boundary_found": False,
        "valid": False,
    }
    if not isinstance(output, str) or not output.strip():
        result["error"] = "empty_output"
        return result
    opening = "<think>" in output
    closes = output.count("</think>")
    result["opening_marker_found"] = opening
    if thinking:
        if closes != 1:
            result["error"] = "missing_thinking_boundary" if closes == 0 else "multiple_thinking_boundaries"
            return result
        result["thinking_boundary_found"] = True
        prefix, candidate = output.split("</think>", 1)
        if prefix.count("<think>") > 1:
            result["error"] = "multiple_opening_markers"
            return result
        if opening and not prefix.lstrip().startswith("<think>"):
            result["error"] = "misplaced_opening_marker"
            return result
    else:
        if opening or closes:
            result["error"] = "thinking_marker_in_nonthinking_output"
            result["thinking_boundary_found"] = bool(closes)
            return result
        candidate = output
    try:
        decoded = json.loads(candidate.strip())
    except json.JSONDecodeError:
        result["error"] = "invalid_json"
        return result
    if not isinstance(decoded, dict):
        result["error"] = "json_not_object"
        return result
    if set(decoded) != {"label"}:
        result["error"] = "schema_keys_mismatch"
        return result
    label = decoded["label"]
    if not isinstance(label, str):
        result["error"] = "label_not_string"
        return result
    if label not in labels:
        result["error"] = "unknown_label"
        return result
    result.update(
        {
            "canonical_output": json.dumps({"label": label}, ensure_ascii=True, separators=(",", ":")),
            "label": label,
            "valid": True,
        }
    )
    return result


def render_messages(config: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any], view: str) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions,
        output_schema=prompt["output_schema"],
    )
    target = row["views"]["target_only"]["target"]
    if view == "target_only":
        user = prompt["target_only_template"].format(target=target)
    else:
        previous = row["views"]["previous_context"]["previous"]
        user = (
            prompt["previous_context_template"].format(previous=previous, target=target)
            if previous
            else prompt["target_only_template"].format(target=target)
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def message_hash(messages: list[dict[str, str]]) -> str:
    return sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def metrics(gold: Sequence[str], predictions: Sequence[str], labels: Sequence[str]) -> dict[str, Any]:
    per_class = {}
    precisions = []
    recalls = []
    f1s = []
    weighted = 0.0
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, predictions))
        fp = sum(g != label and p == label for g, p in zip(gold, predictions))
        fn = sum(g == label and p != label for g, p in zip(gold, predictions))
        support = sum(g == label for g in gold)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"f1": f1, "precision": precision, "recall": recall, "support": support}
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        weighted += f1 * support
    columns = list(labels) + [INVALID_LABEL]
    matrix = [
        [sum(g == row and p == column for g, p in zip(gold, predictions)) for column in columns]
        for row in labels
    ]
    return {
        "accuracy": sum(g == p for g, p in zip(gold, predictions)) / len(gold),
        "confusion_columns": columns,
        "confusion_matrix": matrix,
        "macro_f1": statistics.fmean(f1s),
        "macro_precision": statistics.fmean(precisions),
        "macro_recall": statistics.fmean(recalls),
        "per_class": per_class,
        "rows": len(gold),
        "weighted_f1": weighted / len(gold),
    }


def metrics_by_slice(records: Sequence[dict[str, Any]], labels: Sequence[str]) -> dict[str, Any]:
    selections = {
        "all": list(records),
        "context_available": [row for row in records if row["context_available"]],
        "first_clause": [row for row in records if not row["context_available"]],
    }
    return {
        name: metrics(
            [row["gold_label"] for row in values],
            [row["prediction"] for row in values],
            labels,
        )
        for name, values in selections.items()
    }


def macro_f1(gold: Sequence[str], predictions: Sequence[str], labels: Sequence[str]) -> float:
    return metrics(gold, predictions, labels)["macro_f1"]


def effects(scores: dict[str, float]) -> dict[str, float]:
    return {
        "context_reasoning_off_B_minus_A": scores["B"] - scores["A"],
        "context_reasoning_on_D_minus_C": scores["D"] - scores["C"],
        "reasoning_target_only_C_minus_A": scores["C"] - scores["A"],
        "reasoning_context_D_minus_B": scores["D"] - scores["B"],
        "interaction_D_minus_C_minus_B_minus_A": (scores["D"] - scores["C"]) - (scores["B"] - scores["A"]),
        "average_context_effect": ((scores["B"] - scores["A"]) + (scores["D"] - scores["C"])) / 2,
        "average_reasoning_effect": ((scores["C"] - scores["A"]) + (scores["D"] - scores["B"])) / 2,
    }


def bootstrap(records: dict[str, Sequence[dict[str, Any]]], labels: Sequence[str], repeats: int, namespace: str) -> dict[str, Any]:
    gold = [row["gold_label"] for row in records["A"]]
    predictions = {name: [row["prediction"] for row in values] for name, values in records.items()}
    observed_scores = {name: macro_f1(gold, values, labels) for name, values in predictions.items()}
    observed = effects(observed_scores)
    rng = random.Random(int(sha256_text(namespace)[:16], 16))
    distributions = {name: [] for name in observed}
    for _ in range(repeats):
        indices = [rng.randrange(len(gold)) for _ in gold]
        sampled_gold = [gold[index] for index in indices]
        sampled_scores = {
            name: macro_f1(sampled_gold, [values[index] for index in indices], labels)
            for name, values in predictions.items()
        }
        for name, value in effects(sampled_scores).items():
            distributions[name].append(value)
    return {
        name: {
            "ci95_percentile": [quantile(distributions[name], 0.025), quantile(distributions[name], 0.975)],
            "observed": value,
        }
        for name, value in observed.items()
    }


def select(scores: dict[str, float], conditions: dict[str, dict[str, Any]], durations: dict[str, float], tie: float) -> str:
    best = max(scores.values())
    candidates = [name for name, score in scores.items() if best - score < tie]
    return min(
        candidates,
        key=lambda name: (
            bool(conditions[name]["reasoning"]),
            conditions[name]["view"] != "target_only",
            durations[name],
            name,
        ),
    )


def compare(actual: Any, expected: Any, path: str, mismatches: list[str], tolerance: float = 1e-12) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            mismatches.append(f"{path}: key/type mismatch")
            return
        for key in expected:
            compare(actual[key], expected[key], f"{path}.{key}", mismatches, tolerance)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            mismatches.append(f"{path}: list mismatch")
            return
        for index, value in enumerate(expected):
            compare(actual[index], value, f"{path}[{index}]", mismatches, tolerance)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance):
            mismatches.append(f"{path}: {actual!r} != {expected!r}")
    elif actual != expected:
        mismatches.append(f"{path}: {actual!r} != {expected!r}")


def forbidden_public_keys(value: Any, path: str, findings: list[str]) -> None:
    forbidden = {"raw_output", "sample_id", "gold_label", "prediction", "message_sha256"}
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden:
                findings.append(f"{path}.{key}")
            forbidden_public_keys(child, f"{path}.{key}", findings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            forbidden_public_keys(child, f"{path}[{index}]", findings)


def main() -> None:
    if (RUN_DIR / "verification.json").exists():
        raise FileExistsError("Verification output already exists")
    config = json.loads((RUN_DIR / "frozen-config.json").read_text(encoding="utf-8"))
    run = json.loads((RUN_DIR / "run.json").read_text(encoding="utf-8"))
    aggregate = json.loads((RUN_DIR / "aggregate_metrics.json").read_text(encoding="utf-8"))
    prompt = json.loads((RUN_DIR / "frozen-prompt-v1.json").read_text(encoding="utf-8"))
    mismatches: list[str] = []
    checks: list[str] = []

    frozen_mapping = {
        "runner": "frozen-runner.py",
        "verifier": "frozen-verifier.py",
        "test": "frozen-test.py",
        "parser": "frozen-label-parser.py",
        "prompt": "frozen-prompt-v1.json",
        "requirements": "frozen-requirements-lock.txt",
    }
    for name, filename in frozen_mapping.items():
        expected = config["implementation"][f"{name}_sha256"]
        if sha256_file(RUN_DIR / filename) != expected:
            mismatches.append(f"frozen {name} hash")
    checks.append("frozen source hashes")

    validation_path = resolve_project_path(config["data"]["validation_path"])
    if sha256_file(validation_path) != config["data"]["validation_sha256"]:
        mismatches.append("validation hash")
    validation = read_jsonl(validation_path)
    if len(validation) != config["data"]["validation_rows"]:
        mismatches.append("validation rows")
    checks.append("validation identity")

    labels = config["data"]["labels"]
    records: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for condition, spec in config["conditions"].items():
        private_path = resolve_project_path(config["private_root"]) / f"condition-{condition}-predictions.jsonl"
        rows = read_jsonl(private_path)
        records[condition] = rows
        summary = json.loads((RUN_DIR / f"condition-{condition}.json").read_text(encoding="utf-8"))
        summaries[condition] = summary
        if len(rows) != len(validation) or sha256_file(private_path) != summary["private_predictions_sha256"]:
            mismatches.append(f"condition {condition} rows/hash")
            continue
        for index, (record, source) in enumerate(zip(rows, validation)):
            if (
                record["row_index"] != index
                or record["sample_id"] != source["sample_id"]
                or record["gold_label"] != source["label"]
                or record["context_available"] != bool(source["context_available"])
                or record["view"] != spec["view"]
                or record["reasoning"] != spec["reasoning"]
            ):
                mismatches.append(f"condition {condition} row identity {index}")
                break
            messages = render_messages(config, prompt, source, spec["view"])
            if message_hash(messages) != record["message_sha256"]:
                mismatches.append(f"condition {condition} message hash {index}")
                break
            parsed = independent_parse(record["raw_output"], spec["reasoning"], labels)
            prediction = parsed["label"] if parsed["valid"] else INVALID_LABEL
            if parsed != record["parse"] or prediction != record["prediction"]:
                mismatches.append(f"condition {condition} parser {index}")
                break
        rebuilt = metrics_by_slice(rows, labels)
        compare(summary["metrics"], rebuilt, f"condition {condition} metrics", mismatches)
        errors = dict(sorted(Counter(row["parse"]["error"] for row in rows if row["parse"]["error"]).items()))
        parser_expected = {
            "error_counts": errors,
            "likely_truncated_count": sum(row["likely_truncated"] for row in rows),
            "valid_count": sum(row["parse"]["valid"] for row in rows),
            "valid_rate": sum(row["parse"]["valid"] for row in rows) / len(rows),
        }
        compare(summary["parser"], parser_expected, f"condition {condition} parser summary", mismatches)
        batches: dict[int, dict[str, Any]] = {}
        for record in rows:
            batches.setdefault(record["batch_index"], record["batch_stats"])
        batch_values = list(batches.values())
        resource_expected = {
            "batches": len(batch_values),
            "peak_memory_gb_max": max(value["peak_memory"] for value in batch_values),
            "total_batch_elapsed_seconds": sum(value["batch_elapsed_seconds"] for value in batch_values),
            "total_generation_tokens": sum(value["generation_tokens"] for value in batch_values),
            "total_prompt_tokens": sum(value["prompt_tokens"] for value in batch_values),
        }
        for key, expected in resource_expected.items():
            compare(summary["generation"][key], expected, f"condition {condition} resource {key}", mismatches)
    checks.append("four private prediction sets")
    checks.append("independent strict parsing and prompt hashes")
    checks.append("condition metrics and parser summaries")
    checks.append("batch resource accounting")

    expected_condition_metrics = {condition: summaries[condition]["metrics"] for condition in config["conditions"]}
    compare(aggregate["condition_metrics"], expected_condition_metrics, "aggregate condition metrics", mismatches)
    rebuilt_effects = bootstrap(
        records,
        labels,
        config["evaluation"]["bootstrap_repeats"],
        config["evaluation"]["bootstrap_seed_namespace"],
    )
    compare(aggregate["factorial_effects"], rebuilt_effects, "factorial effects", mismatches)
    checks.append("paired bootstrap factorial effects")

    first_indices = [index for index, row in enumerate(validation) if not row["context_available"]]
    off_raw_equal = sum(records["A"][index]["raw_output"] == records["B"][index]["raw_output"] for index in first_indices)
    on_raw_equal = sum(records["C"][index]["raw_output"] == records["D"][index]["raw_output"] for index in first_indices)
    first_expected = {
        "prediction_equal_count_reasoning_off": sum(records["A"][index]["prediction"] == records["B"][index]["prediction"] for index in first_indices),
        "prediction_equal_count_reasoning_on": sum(records["C"][index]["prediction"] == records["D"][index]["prediction"] for index in first_indices),
        "prompt_hash_match": {
            "reasoning_off_A_equals_B": all(records["A"][index]["message_sha256"] == records["B"][index]["message_sha256"] for index in first_indices),
            "reasoning_on_C_equals_D": all(records["C"][index]["message_sha256"] == records["D"][index]["message_sha256"] for index in first_indices),
        },
        "raw_output_equal_count_reasoning_off": off_raw_equal,
        "raw_output_equal_count_reasoning_on": on_raw_equal,
        "raw_output_equal_rate_reasoning_off": off_raw_equal / len(first_indices),
        "raw_output_equal_rate_reasoning_on": on_raw_equal / len(first_indices),
        "rows": len(first_indices),
    }
    compare(aggregate["first_clause_determinism"], first_expected, "first-clause determinism", mismatches)
    checks.append("identical first-clause prompt control")

    scores = {condition: summaries[condition]["metrics"]["all"]["macro_f1"] for condition in config["conditions"]}
    durations = {
        condition: summaries[condition]["generation"]["total_batch_elapsed_seconds"]
        for condition in config["conditions"]
    }
    selected = select(scores, config["conditions"], durations, config["evaluation"]["practical_tie_macro_f1"])
    if selected != aggregate["selection"]["selected_condition"]:
        mismatches.append("selection rule")
    reference_path = resolve_project_path(config["stage3_reference"]["aggregate_path"])
    if sha256_file(reference_path) != config["stage3_reference"]["aggregate_sha256"]:
        mismatches.append("EXP-042 reference hash")
    reference = json.loads(reference_path.read_text(encoding="utf-8"))["m2_primary_view_selection"]["target_mean_macro_f1"]
    expected_delta = scores[selected] - reference
    if not math.isclose(expected_delta, aggregate["qwen_vs_exp042_m2_target"]["delta_macro_f1"], abs_tol=1e-12):
        mismatches.append("Qwen vs EXP-042 delta")
    if aggregate["resource_usage"]["formal_generations"] != len(validation) * len(config["conditions"]):
        mismatches.append("formal generation count")
    if aggregate["resource_usage"]["formal_elapsed_seconds"] > config["resource_budget"]["formal_wall_time_seconds_max"]:
        mismatches.append("formal wall-time budget")
    checks.append("selection and frozen encoder reference")

    public_jsons = [
        RUN_DIR / "initialize.json",
        RUN_DIR / "smoke.json",
        *(RUN_DIR / f"condition-{name}.json" for name in config["conditions"]),
        RUN_DIR / "aggregate_metrics.json",
        RUN_DIR / "run.json",
    ]
    privacy_findings: list[str] = []
    for path in public_jsons:
        forbidden_public_keys(json.loads(path.read_text(encoding="utf-8")), path.name, privacy_findings)
    if privacy_findings:
        mismatches.extend(f"public private field: {value}" for value in privacy_findings)
    if run["test_split_accessed"] or aggregate["test_split_accessed"] or "test" in run["accessed_splits"]:
        mismatches.append("test access")
    if run["model"]["adapter_loaded"] is not False:
        mismatches.append("adapter loaded")
    checks.append("public privacy, no adapter and sealed test")

    verification = {
        "check_count": len(checks),
        "checks": checks,
        "experiment_id": config["experiment_id"],
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "status": "Verified" if not mismatches else "Failed",
        "test_split_accessed": False,
        "verified_at_utc": utc_now(),
    }
    atomic_json(RUN_DIR / "verification.json", verification)
    if mismatches:
        raise RuntimeError(f"EXP-043 verification failed with {len(mismatches)} mismatches")
    run["status"] = "Verified"
    run["verification"] = {
        "bytes": (RUN_DIR / "verification.json").stat().st_size,
        "path": str((RUN_DIR / "verification.json").relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(RUN_DIR / "verification.json"),
    }
    atomic_json(RUN_DIR / "run.json", run)
    print(json.dumps({"check_count": len(checks), "experiment_id": config["experiment_id"], "mismatch_count": 0, "status": "Verified"}))


if __name__ == "__main__":
    main()

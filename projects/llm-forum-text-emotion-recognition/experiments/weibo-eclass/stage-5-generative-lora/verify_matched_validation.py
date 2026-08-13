#!/usr/bin/env python3
"""Independently verify the authorized EXP-047 matched validation."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import stat
import statistics
import subprocess
from typing import Any, Sequence


EXPERIMENT_ID = "EXP-047"
CONTRACT_ID = "EXP-047-MATCHED-VALIDATION-V1"
VERIFICATION_ID = "EXP-047-MATCHED-VALIDATION-VERIFY-V1"
CONDITIONS = ("reference", "seed-42", "seed-43", "seed-44")
INVALID_LABEL = "__invalid__"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-047-matched-validation-contract-v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Recompute without modifying artifacts")
    return parser.parse_args()


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


def canonical_digest(value: Any) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def artifact(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": display_path(path), "sha256": sha256_file(path)}


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def compare(actual: Any, expected: Any, path: str, mismatches: list[str], tolerance: float = 1e-12) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            mismatches.append(f"{path}: key/type mismatch")
            return
        for key, value in expected.items():
            compare(actual[key], value, f"{path}.{key}", mismatches, tolerance)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            mismatches.append(f"{path}: list mismatch")
            return
        for index, value in enumerate(expected):
            compare(actual[index], value, f"{path}[{index}]", mismatches, tolerance)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), float(expected), rel_tol=0, abs_tol=tolerance
        ):
            mismatches.append(f"{path}: {actual!r} != {expected!r}")
    elif actual != expected:
        mismatches.append(f"{path}: {actual!r} != {expected!r}")


def verify_spec(spec: dict[str, Any], mismatches: list[str], name: str) -> Path:
    path = resolve_project_path(spec["path"])
    if not path.is_file():
        mismatches.append(f"{name}: missing")
        return path
    observed = artifact(path)
    if observed != spec:
        mismatches.append(f"{name}: artifact drift")
    return path


def quantile(values: Sequence[float | int], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot summarize an empty sequence")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("Cannot summarize an empty sequence")
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "p95": quantile(values, 0.95),
        "sum": sum(values),
    }


def metrics(gold: Sequence[str], predictions: Sequence[str], labels: Sequence[str]) -> dict[str, Any]:
    if len(gold) != len(predictions) or not gold:
        raise ValueError("Metrics require equal non-empty vectors")
    per_class: dict[str, Any] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
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
            [row["gold_label"] for row in rows], [row["prediction"] for row in rows], labels
        )
        for name, rows in selections.items()
    }


def macro_f1(records: Sequence[dict[str, Any]], labels: Sequence[str]) -> float:
    return metrics(
        [row["gold_label"] for row in records],
        [row["prediction"] for row in records],
        labels,
    )["macro_f1"]


def bootstrap_pairwise(
    reference: Sequence[dict[str, Any]],
    candidate: Sequence[dict[str, Any]],
    labels: Sequence[str],
    repeats: int,
    namespace: str,
) -> dict[str, Any]:
    groups_to_indices: dict[str, list[int]] = {}
    for index, row in enumerate(reference):
        groups_to_indices.setdefault(row["group_id"], []).append(index)
    groups = sorted(groups_to_indices)
    rng = random.Random(int(sha256_text(namespace)[:16], 16))
    deltas: list[float] = []
    for _ in range(repeats):
        sampled = [rng.choice(groups) for _ in groups]
        indices = [index for group in sampled for index in groups_to_indices[group]]
        deltas.append(
            macro_f1([candidate[index] for index in indices], labels)
            - macro_f1([reference[index] for index in indices], labels)
        )
    return {
        "ci95": [quantile(deltas, 0.025), quantile(deltas, 0.975)],
        "groups": len(groups),
        "observed_delta": macro_f1(candidate, labels) - macro_f1(reference, labels),
        "probability_delta_gt_zero": sum(value > 0 for value in deltas) / len(deltas),
        "repeats": repeats,
        "resampling_unit": "group_id",
    }


def independent_parse(output: str, labels: Sequence[str]) -> dict[str, Any]:
    opening = "<think>" in output
    close_count = output.count("</think>")
    base = {
        "canonical_output": None,
        "label": None,
        "opening_marker_found": opening,
        "thinking_boundary_found": close_count == 1,
        "valid": False,
    }
    if close_count != 1:
        base["error"] = "missing_thinking_boundary" if close_count == 0 else "multiple_thinking_boundaries"
        base["thinking_boundary_found"] = False
        return base
    prefix, candidate = output.split("</think>", maxsplit=1)
    if prefix.count("<think>") > 1:
        return {**base, "error": "multiple_opening_markers", "thinking_boundary_found": True}
    if opening and not prefix.lstrip().startswith("<think>"):
        return {**base, "error": "misplaced_opening_marker", "thinking_boundary_found": True}
    try:
        decoded = json.loads(candidate.strip())
    except json.JSONDecodeError:
        return {**base, "error": "invalid_json", "thinking_boundary_found": True}
    if not isinstance(decoded, dict):
        return {**base, "error": "json_not_object", "thinking_boundary_found": True}
    if set(decoded) != {"label"}:
        return {**base, "error": "schema_keys_mismatch", "thinking_boundary_found": True}
    label = decoded["label"]
    if not isinstance(label, str):
        return {**base, "error": "label_not_string", "thinking_boundary_found": True}
    if label not in labels:
        return {**base, "error": "unknown_label", "thinking_boundary_found": True}
    return {
        "canonical_output": json.dumps({"label": label}, ensure_ascii=True, separators=(",", ":")),
        "error": None,
        "label": label,
        "opening_marker_found": opening,
        "thinking_boundary_found": True,
        "valid": True,
    }


def render_messages(contract: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in contract["labels"]
    )
    return [
        {
            "role": "system",
            "content": prompt["system_template"].format(
                label_definitions=definitions, output_schema=prompt["output_schema"]
            ),
        },
        {
            "role": "user",
            "content": prompt["target_only_template"].format(
                target=row["views"]["target_only"]["target"]
            ),
        },
    ]


def message_hash(messages: list[dict[str, str]]) -> str:
    return canonical_digest(messages)


def forbidden_public_keys(value: Any, path: str, findings: list[str]) -> None:
    forbidden = {
        "gold_label",
        "group_id",
        "message_sha256",
        "prediction",
        "prompt_sha256",
        "raw_output",
        "sample_id",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden:
                findings.append(f"{path}.{key}")
            forbidden_public_keys(child, f"{path}.{key}", findings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            forbidden_public_keys(child, f"{path}[{index}]", findings)


def primary_decision(delta: float, threshold: float) -> str:
    if delta >= threshold:
        return "material_improvement"
    if delta <= -threshold:
        return "material_degradation"
    return "practical_tie"


def verify_contract_and_gates(contract: dict[str, Any], mismatches: list[str]) -> dict[str, Any]:
    if (
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or tuple(contract.get("condition_order", ())) != CONDITIONS
        or contract.get("accessed_splits") != ["validation"]
        or contract.get("test_split_accessed") is not False
    ):
        mismatches.append("contract identity/boundary")
    for section in ("implementation", "frozen_artifacts"):
        for name, spec in contract[section].items():
            verify_spec(spec, mismatches, f"{section}.{name}")
    for condition in CONDITIONS[1:]:
        for name in ("adapter", "adapter_config"):
            verify_spec(contract["conditions"][condition][name], mismatches, f"{condition}.{name}")
    packages = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in contract["runtime"]["packages"]
    }
    if packages != contract["runtime"]["packages"]:
        mismatches.append("runtime package versions")
    python = Path(contract["runtime"]["python_executable"])
    if not python.is_file() or not Path(os.sys.executable).samefile(python):
        mismatches.append("runtime Python executable")
    authorization = load_json(resolve_project_path(contract["frozen_artifacts"]["authorization"]["path"]))
    if (
        authorization.get("authorization_id") != "EXP-047-MATCHED-VALIDATION-AUTH-V1"
        or authorization.get("status") != "Authorized"
        or tuple(authorization.get("authorized_conditions_in_order", ())) != CONDITIONS
        or authorization.get("authorized_generations") != 5088
        or authorization.get("authorized_split") != "validation"
        or authorization.get("boundaries", {}).get("sealed_test_access") is not False
    ):
        mismatches.append("authorization")
    train = read_jsonl(resolve_project_path(contract["data"]["train_path"]))
    if len(train) != contract["data"]["train_rows"]:
        mismatches.append("frozen train rows")
    gate_ids: dict[str, Any] = {}
    for condition in CONDITIONS[1:]:
        seed = int(condition.split("-")[1])
        gate = contract["gates"][condition]
        training_path = verify_spec(
            gate["training_verification"], mismatches, f"{condition}.training_verification"
        )
        replay_path = verify_spec(
            gate["replay_verification"], mismatches, f"{condition}.replay_verification"
        )
        training = load_json(training_path)
        replay = load_json(replay_path)
        if (
            training.get("verification_id") != gate["training_verification_id"]
            or training.get("seed") != seed
            or training.get("status") != "Passed"
            or training.get("formal_training_verified") is not True
            or training.get("validation_split_accessed") is not False
            or training.get("test_split_accessed") is not False
            or training.get("recalculated", {}).get("adapter", {}).get("weights")
            != contract["conditions"][condition]["adapter"]
            or training.get("recalculated", {}).get("adapter", {}).get("config")
            != contract["conditions"][condition]["adapter_config"]
        ):
            mismatches.append(f"{condition} training gate")
        expected_comparison = {
            "final_label_equal_count": 16,
            "parser_state_equal_count": 16,
            "raw_output_equal_count": 16,
            "rows": 16,
        }
        if (
            replay.get("verification_id") != gate["replay_verification_id"]
            or replay.get("seed") != seed
            or replay.get("status") != "Passed"
            or replay.get("recalculated", {}).get("comparison") != expected_comparison
            or replay.get("validation_split_accessed") is not False
            or replay.get("test_split_accessed") is not False
        ):
            mismatches.append(f"{condition} replay gate")
        gate_ids[condition] = {
            "replay": replay.get("verification_id"),
            "training": training.get("verification_id"),
        }
    return gate_ids


def verify_model(contract: dict[str, Any], mismatches: list[str]) -> dict[str, int]:
    manifest = load_json(resolve_project_path(contract["frozen_artifacts"]["model_manifest"]["path"]))
    if (
        manifest.get("repo_id") != contract["model"]["repo_id"]
        or manifest.get("revision") != contract["model"]["revision"]
    ):
        mismatches.append("model identity")
    root = resolve_project_path(contract["model"]["local_path"])
    files = manifest["mlx_bf16"]["files"]
    total = 0
    for expected in files:
        path = root / expected["path"]
        total += expected["bytes"]
        if not path.is_file() or path.stat().st_size != expected["bytes"] or sha256_file(path) != expected["sha256"]:
            mismatches.append(f"model file {expected['path']}")
    return {"file_count": len(files), "total_bytes": total}


def verify_outputs(contract: dict[str, Any], mismatches: list[str]) -> dict[str, Any]:
    public = resolve_project_path(contract["outputs"]["public_dir"])
    private = resolve_project_path(contract["outputs"]["private_dir"])
    run = load_json(public / "run.json")
    aggregate = load_json(public / "aggregate.json")
    validation_path = resolve_project_path(contract["data"]["validation_path"])
    validation = read_jsonl(validation_path)
    if sha256_file(validation_path) != contract["data"]["validation_sha256"]:
        mismatches.append("validation hash")
    if len(validation) != contract["data"]["validation_rows"]:
        mismatches.append("validation rows")
    if len({row.get("sample_id") for row in validation}) != len(validation):
        mismatches.append("validation sample IDs")
    prompt = load_json(resolve_project_path(contract["frozen_artifacts"]["prompt"]["path"]))
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(resolve_project_path(contract["model"]["local_path"])), local_files_only=True
    )
    labels = contract["labels"]
    expected_keys = {
        "condition",
        "context_available",
        "final_tokens",
        "generated_tokens",
        "generation_seconds",
        "gold_label",
        "group_id",
        "likely_truncated",
        "message_sha256",
        "parse",
        "prediction",
        "prompt_sha256",
        "prompt_tokens",
        "raw_output",
        "raw_output_sha256",
        "reasoning",
        "row_index",
        "sample_id",
        "thinking_tokens",
        "view",
    }
    records: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    rebuilt_metrics: dict[str, Any] = {}
    for condition in CONDITIONS:
        private_path = private / f"condition-{condition}-predictions.jsonl"
        rows = read_jsonl(private_path)
        records[condition] = rows
        summary_path = public / f"condition-{condition}.json"
        summary = load_json(summary_path)
        summaries[condition] = summary
        if len(rows) != len(validation) or sha256_file(private_path) != summary.get("private_predictions_sha256"):
            mismatches.append(f"{condition} private rows/hash")
            continue
        if stat.S_IMODE(private_path.stat().st_mode) != 0o600:
            mismatches.append(f"{condition} private file mode")
        for index, (record, source) in enumerate(zip(rows, validation)):
            if set(record) != expected_keys:
                mismatches.append(f"{condition} record keys {index}")
                break
            if (
                record["condition"] != condition
                or record["row_index"] != index
                or record["sample_id"] != source["sample_id"]
                or record["group_id"] != source["group_id"]
                or record["gold_label"] != source["label"]
                or record["context_available"] is not bool(source["context_available"])
                or record["reasoning"] is not True
                or record["view"] != "target_only"
            ):
                mismatches.append(f"{condition} row identity {index}")
                break
            messages = render_messages(contract, prompt, source)
            prompt_ids = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                enable_thinking=True,
                tokenize=True,
                return_dict=False,
            )
            generated_tokens = len(tokenizer.encode(record["raw_output"], add_special_tokens=False))
            if "</think>" in record["raw_output"]:
                thinking, final = record["raw_output"].split("</think>", maxsplit=1)
                thinking_tokens = len(tokenizer.encode(thinking, add_special_tokens=False))
                final_tokens = len(tokenizer.encode(final, add_special_tokens=False))
            else:
                thinking_tokens, final_tokens = generated_tokens, 0
            parsed = independent_parse(record["raw_output"], labels)
            prediction = parsed["label"] if parsed["valid"] else INVALID_LABEL
            expected_fields = {
                "final_tokens": final_tokens,
                "generated_tokens": generated_tokens,
                "likely_truncated": generated_tokens >= contract["generation"]["max_new_tokens"] - 2,
                "message_sha256": message_hash(messages),
                "parse": parsed,
                "prediction": prediction,
                "prompt_sha256": sha256_text(json.dumps(list(prompt_ids), separators=(",", ":"))),
                "prompt_tokens": len(prompt_ids),
                "raw_output_sha256": sha256_text(record["raw_output"]),
                "thinking_tokens": thinking_tokens,
            }
            for key, expected in expected_fields.items():
                if record[key] != expected:
                    mismatches.append(f"{condition} {key} {index}")
                    break
            if record["prompt_tokens"] > contract["generation"]["max_input_tokens"]:
                mismatches.append(f"{condition} prompt budget {index}")
                break
            if not isinstance(record["generation_seconds"], (int, float)) or record["generation_seconds"] <= 0:
                mismatches.append(f"{condition} timing {index}")
                break
        rebuilt = metrics_by_slice(rows, labels)
        rebuilt_metrics[condition] = rebuilt
        compare(summary.get("metrics"), rebuilt, f"{condition}.metrics", mismatches)
        valid = sum(bool(row["parse"]["valid"]) for row in rows)
        parser_summary = {
            "error_counts": dict(
                sorted(Counter(row["parse"]["error"] for row in rows if row["parse"]["error"]).items())
            ),
            "likely_truncated_count": sum(bool(row["likely_truncated"]) for row in rows),
            "valid_count": valid,
            "valid_rate": valid / len(rows),
        }
        compare(summary.get("parser"), parser_summary, f"{condition}.parser", mismatches)
        generation = summary.get("generation", {})
        expected_generation = {
            "final_tokens": numeric_summary([row["final_tokens"] for row in rows]),
            "generated_tokens": numeric_summary([row["generated_tokens"] for row in rows]),
            "generation_seconds": numeric_summary([row["generation_seconds"] for row in rows]),
            "prompt_tokens": numeric_summary([row["prompt_tokens"] for row in rows]),
            "thinking_tokens": numeric_summary([row["thinking_tokens"] for row in rows]),
            "throughput_generated_tokens_per_second": sum(row["generated_tokens"] for row in rows)
            / sum(row["generation_seconds"] for row in rows),
        }
        for key, expected in expected_generation.items():
            compare(generation.get(key), expected, f"{condition}.generation.{key}", mismatches)
        if (
            generation.get("api_cost_usd") != 0
            or generation.get("batch_size") != 1
            or not isinstance(generation.get("command_elapsed_seconds"), (int, float))
            or generation["command_elapsed_seconds"] <= 0
            or generation["command_elapsed_seconds"]
            > contract["resource_budget"]["per_condition_hours_max"] * 3600
            or not isinstance(generation.get("peak_memory_gb"), (int, float))
            or generation["peak_memory_gb"] > contract["resource_budget"]["peak_memory_gb_max"]
        ):
            mismatches.append(f"{condition} generation boundary")
        expected_summary_fields = {
            "accessed_splits": ["validation"],
            "adapter": contract["conditions"][condition].get("adapter"),
            "condition": condition,
            "experiment_id": EXPERIMENT_ID,
            "raw_outputs_stored_publicly": False,
            "reasoning": True,
            "rows": len(validation),
            "status": "Passed",
            "test_split_accessed": False,
            "validation_split_accessed": True,
            "view": "target_only",
        }
        for key, expected in expected_summary_fields.items():
            if summary.get(key) != expected:
                mismatches.append(f"{condition} summary {key}")
    for condition in CONDITIONS[1:]:
        if any(
            left[key] != right[key]
            for left, right in zip(records["reference"], records[condition])
            for key in ("sample_id", "group_id", "gold_label")
        ):
            mismatches.append(f"{condition} alignment")
    expected_pairwise = {
        condition: bootstrap_pairwise(
            records["reference"],
            records[condition],
            labels,
            contract["evaluation"]["bootstrap_repeats"],
            f"{contract['evaluation']['bootstrap_seed_namespace']}:{condition}",
        )
        for condition in CONDITIONS[1:]
    }
    compare(aggregate.get("bootstrap_pairwise"), expected_pairwise, "aggregate.bootstrap", mismatches)
    macro_scores = {condition: rebuilt_metrics[condition]["all"]["macro_f1"] for condition in CONDITIONS}
    lora_scores = [macro_scores[condition] for condition in CONDITIONS[1:]]
    lora_mean = statistics.fmean(lora_scores)
    mean_delta = lora_mean - macro_scores["reference"]
    expected_primary = {
        "decision": primary_decision(mean_delta, contract["evaluation"]["practical_tie_macro_f1"]),
        "lora_macro_f1_mean": lora_mean,
        "lora_macro_f1_sample_std": statistics.stdev(lora_scores),
        "mean_delta": mean_delta,
        "reference_macro_f1": macro_scores["reference"],
        "rule": "mean(seed-42,seed-43,seed-44)-reference",
        "threshold": contract["evaluation"]["practical_tie_macro_f1"],
    }
    compare(aggregate.get("primary_contrast"), expected_primary, "aggregate.primary", mismatches)
    if aggregate.get("conditions") != summaries:
        mismatches.append("aggregate condition summaries")
    if aggregate.get("historical_comparators") != contract["evaluation"]["historical_comparators"]:
        mismatches.append("aggregate historical comparators")
    expected_resource = {
        "api_cost_usd": 0,
        "condition_command_elapsed_seconds": {
            condition: summaries[condition]["generation"]["command_elapsed_seconds"]
            for condition in CONDITIONS
        },
        "peak_memory_gb_max": max(
            summaries[condition]["generation"]["peak_memory_gb"] for condition in CONDITIONS
        ),
        "total_command_elapsed_seconds": sum(
            summaries[condition]["generation"]["command_elapsed_seconds"] for condition in CONDITIONS
        ),
    }
    compare(aggregate.get("resource"), expected_resource, "aggregate.resource", mismatches)
    if expected_resource["total_command_elapsed_seconds"] > contract["resource_budget"]["total_inference_hours_max"] * 3600:
        mismatches.append("total inference budget")
    for source_name, spec in contract["evaluation"]["historical_sources"].items():
        source = load_json(resolve_project_path(spec["path"]))
        if source_name == "exp042_m2_target":
            observed = source["m2_primary_view_selection"]["target_mean_macro_f1"]
        elif source_name == "exp043_a_batch8":
            observed = source["condition_metrics"]["A"]["all"]["macro_f1"]
        elif source_name == "exp043_c_batch8":
            observed = source["condition_metrics"]["C"]["all"]["macro_f1"]
        else:
            mismatches.append(f"unknown historical source {source_name}")
            continue
        if not math.isclose(
            observed,
            contract["evaluation"]["historical_comparators"][source_name]["macro_f1"],
            rel_tol=0,
            abs_tol=1e-15,
        ):
            mismatches.append(f"historical comparator {source_name}")
    public_sources = [
        public / "initialize.json",
        public / "run.json",
        *(public / f"condition-{condition}.json" for condition in CONDITIONS),
        public / "aggregate.json",
    ]
    privacy_findings: list[str] = []
    for path in public_sources:
        forbidden_public_keys(load_json(path), path.name, privacy_findings)
    report_text = (public / "REPORT.md").read_text(encoding="utf-8")
    if any(row["sample_id"] in report_text for row in validation):
        privacy_findings.append("REPORT.md sample_id")
    if privacy_findings:
        mismatches.extend(f"public privacy: {finding}" for finding in privacy_findings)
    if stat.S_IMODE(private.stat().st_mode) != 0o700:
        mismatches.append("private directory mode")
    relative_private = private.relative_to(REPO_ROOT)
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(relative_private)], cwd=REPO_ROOT, check=False
    ).returncode == 0
    if not ignored:
        mismatches.append("private directory is not gitignored")
    if (
        run.get("test_split_accessed") is not False
        or aggregate.get("test_split_accessed") is not False
        or run.get("accessed_splits") != ["validation"]
        or aggregate.get("accessed_splits") != ["validation"]
    ):
        mismatches.append("sealed test boundary")
    for condition in CONDITIONS:
        stage = run.get("stages", {}).get(f"infer_{condition}", {})
        if stage.get("status") != "Passed" or stage.get("artifact") != artifact(public / f"condition-{condition}.json"):
            mismatches.append(f"run stage {condition}")
    aggregate_stage = run.get("stages", {}).get("aggregate", {})
    if (
        aggregate_stage.get("status") != "Passed"
        or aggregate_stage.get("artifact") != artifact(public / "aggregate.json")
        or aggregate_stage.get("report") != artifact(public / "REPORT.md")
    ):
        mismatches.append("run aggregate stage")
    initialize_stage = run.get("stages", {}).get("initialize", {})
    if (
        initialize_stage.get("status") != "Passed"
        or initialize_stage.get("artifact") != artifact(public / "initialize.json")
        or run.get("status") not in {"Completed; pending independent verification", "Verified"}
        or aggregate.get("status") not in {"Completed; pending independent verification", "Verified"}
    ):
        mismatches.append("run initialization/status")
    return {
        "bootstrap_sha256": canonical_digest(expected_pairwise),
        "condition_metrics_sha256": canonical_digest(rebuilt_metrics),
        "formal_generations": sum(len(rows) for rows in records.values()),
        "macro_f1": macro_scores,
        "primary_contrast": expected_primary,
        "private_prediction_files": len(records),
        "private_prediction_rows": sum(len(rows) for rows in records.values()),
        "public_source_files_scanned": len(public_sources),
        "validation_rows": len(validation),
    }


def run_verification() -> tuple[list[str], list[str], dict[str, Any]]:
    contract = load_json(CONTRACT_PATH)
    mismatches: list[str] = []
    checks = [
        "contract, frozen source and runtime identity",
        "explicit validation authorization and train-only gates",
        "model manifest and local BF16 files",
        "1,272 ordered records for each of four fresh-process conditions",
        "independent prompt, token, parser and prediction reconstruction",
        "metrics, slices, confusion matrices and parser accounting",
        "group-level paired bootstrap and frozen primary decision",
        "historical comparator provenance and resource budget",
        "private file modes, gitignore and public privacy",
        "validation-only split boundary and sealed test",
    ]
    gate_ids = verify_contract_and_gates(contract, mismatches)
    model_files = verify_model(contract, mismatches)
    recalculated = verify_outputs(contract, mismatches)
    recalculated["gate_verification_ids"] = gate_ids
    recalculated["model_files"] = model_files
    return checks, mismatches, recalculated


def main() -> None:
    args = parse_args()
    contract = load_json(CONTRACT_PATH)
    public = resolve_project_path(contract["outputs"]["public_dir"])
    verification_path = public / "verification.json"
    checks, mismatches, recalculated = run_verification()
    stable = {
        "check_count": len(checks),
        "checks": checks,
        "experiment_id": EXPERIMENT_ID,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "recalculated": recalculated,
        "status": "Passed" if not mismatches else "Failed",
        "test_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }
    if args.check:
        observed = load_json(verification_path)
        expected = {**stable, "verified_at_utc": observed.get("verified_at_utc")}
        if observed != expected:
            raise RuntimeError("Stored EXP-047 verification no longer matches independent reconstruction")
        run = load_json(public / "run.json")
        if run.get("status") != "Verified" or run.get("verification") != artifact(verification_path):
            raise RuntimeError("Verified run metadata drift")
        print(json.dumps({"check_count": len(checks), "status": "Passed", "verification_id": VERIFICATION_ID}))
        return
    if verification_path.exists():
        raise FileExistsError("EXP-047 matched-validation verification already exists")
    if mismatches:
        raise RuntimeError(f"EXP-047 verification failed: {mismatches[:5]}")
    aggregate_path = public / "aggregate.json"
    aggregate = load_json(aggregate_path)
    aggregate["status"] = "Verified"
    atomic_json(aggregate_path, aggregate)
    report_path = public / "REPORT.md"
    report = report_path.read_text(encoding="utf-8").replace(
        "Independent verification is required before this aggregate becomes Verified evidence.",
        "Independent verification passed with zero mismatch.",
    )
    report_path.write_text(report, encoding="utf-8")
    verification = {**stable, "verified_at_utc": utc_now()}
    atomic_json(verification_path, verification)
    run = load_json(public / "run.json")
    run["stages"]["aggregate"]["artifact"] = artifact(aggregate_path)
    run["stages"]["aggregate"]["report"] = artifact(report_path)
    run["status"] = "Verified"
    run["verification"] = artifact(verification_path)
    atomic_json(public / "run.json", run)
    print(json.dumps({"check_count": len(checks), "status": "Passed", "verification_id": VERIFICATION_ID}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Independently verify EXP-023 resource, parser, and privacy artifacts."""

from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import verify_resource_parser_trial as exp022_verify


PROJECT_ROOT = SCRIPT_DIR.parents[2]
RUN_DIR = SCRIPT_DIR / "runs" / "exp-023-label-id-parser-trial"
RUN_PATH = RUN_DIR / "run.json"
SUMMARY_PATH = RUN_DIR / "summary.json"
SELECTED_PATH = RUN_DIR / "selected-samples.json"
RESULTS_PATH = RUN_DIR / "sample-results.jsonl"
OUTPUT_PATH = RUN_DIR / "verification.json"
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-023-label-id-parser-trial.json"
PROMPT_PATH = SCRIPT_DIR / "prompts" / "exp-023-label-id-v1.json"
RUNNER_PATH = SCRIPT_DIR / "run_label_id_parser_trial.py"
PARENT_RUNNER_PATH = SCRIPT_DIR / "run_resource_parser_trial.py"
PARENT_VERIFIER_PATH = SCRIPT_DIR / "verify_resource_parser_trial.py"
PARENT_SELECTED_PATH = (
    SCRIPT_DIR
    / "runs"
    / "exp-022-resource-parser-trial"
    / "selected-samples.json"
)
TRAIN_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "train.tsv"
LABELS_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "emotions.txt"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
MODEL_MANIFEST_PATH = PROJECT_ROOT / "models" / "qwen3-1.7b" / "manifest.json"

EXPECTED_HASHES = {
    CONFIG_PATH: "53ed7eafd5c227e97c0dde197644b35fff1ba6d7d7f1d4986e39d6ab525e2e93",
    PROMPT_PATH: "09079207271900b84db7ab0f209bf884a22f67f2f2872a2e3ea88cab9c5f2516",
    RUNNER_PATH: "0e4c77ef39d79fc07266bdc67db9ee615eb86e8a81cfc10c48eea6fb53dd9add",
    PARENT_RUNNER_PATH: "d2051f5c621190117cb5c874e5d8c3a128aee262a1a070b038c5254d90b40e5e",
    PARENT_VERIFIER_PATH: "02c88592fd968eba5e58ebba84b8d83e228c8725d9f0f6a1842a950f1e0fa20d",
    TRAIN_PATH: "1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5",
    LABELS_PATH: "45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89",
    MODEL_MANIFEST_PATH: "7c1e0e53e6340d5ce33c366569a07763be41546045017870cc149a8f50d1e877",
}
EXPECTED_SELECTION_DIGEST = (
    "7dcdbe002627948d6e1c5ed4eceb950085585ad0c726333ba3012515dbd8c525"
)
CONDITIONS = ("zero-shot", "few-shot-synthetic-3")
RESULT_FIELDS = {
    "canonical_output",
    "condition",
    "finish_reason",
    "generated_tokens",
    "generation_seconds",
    "generation_tps",
    "length_stratum",
    "output_character_count",
    "output_sha256",
    "parsed_label_ids",
    "parser_error",
    "parser_valid",
    "peak_memory_gb",
    "prompt_tokens",
    "prompt_tps",
    "raw_output_stored",
    "sample_index",
    "text_character_count",
}
SELECTED_FIELDS = {
    "data_rows_scanned",
    "gold_labels_retained_or_used",
    "raw_comment_ids_stored",
    "raw_text_stored",
    "sample_count",
    "samples",
    "selection_digest_sha256",
    "strata",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{label} mismatch: {actual} != {expected}")


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def read_results() -> list[dict[str, Any]]:
    results = []
    with RESULTS_PATH.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            record = json.loads(line)
            if set(record) != RESULT_FIELDS:
                raise ValueError(f"Unexpected fields in result line {line_number}")
            if record["raw_output_stored"] is not False:
                raise ValueError("A result claims unrestricted output was stored")
            if record["condition"] not in CONDITIONS:
                raise ValueError("Unknown result condition")
            if (
                not isinstance(record["output_sha256"], str)
                or len(record["output_sha256"]) != 64
                or not isinstance(record["output_character_count"], int)
                or record["output_character_count"] < 1
            ):
                raise ValueError("Invalid output hash or size metadata")
            numeric_fields = (
                "generated_tokens",
                "generation_seconds",
                "generation_tps",
                "peak_memory_gb",
                "prompt_tokens",
                "prompt_tps",
            )
            if any(
                not isinstance(record[field], (int, float))
                or isinstance(record[field], bool)
                or not math.isfinite(float(record[field]))
                or float(record[field]) < 0
                for field in numeric_fields
            ):
                raise ValueError("Invalid numeric resource measurement")

            if record["parser_valid"]:
                canonical = record["canonical_output"]
                if not isinstance(canonical, str):
                    raise ValueError("Valid parser record lacks canonical JSON")
                decoded = json.loads(canonical)
                if not isinstance(decoded, dict) or set(decoded) != {"label_ids"}:
                    raise ValueError("Canonical parser record has the wrong schema")
                values = decoded["label_ids"]
                if values != record["parsed_label_ids"]:
                    raise ValueError("Canonical parser record mismatch")
                if not isinstance(values, list) or not values:
                    raise ValueError("Canonical label IDs are not a non-empty list")
                if not all(type(value) is int for value in values):
                    raise ValueError("Canonical label IDs contain a non-integer")
                if len(values) != len(set(values)):
                    raise ValueError("Canonical output contains duplicate label IDs")
                if any(value < 0 or value > 27 for value in values):
                    raise ValueError("Canonical output contains an out-of-range label ID")
                if 27 in values and len(values) > 1:
                    raise ValueError("Canonical output combines neutral with an emotion")
                expected_canonical = json.dumps(
                    {"label_ids": values}, separators=(",", ":")
                )
                if canonical != expected_canonical or record["parser_error"] is not None:
                    raise ValueError("Valid parser record is not canonical")
            else:
                if (
                    record["canonical_output"] is not None
                    or record["parsed_label_ids"]
                    or not isinstance(record["parser_error"], str)
                    or not record["parser_error"]
                ):
                    raise ValueError("Invalid parser record exposes unexpected content")
            results.append(record)
    return results


def verify_condition_summary(
    condition: str,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    full_dev_rows: int,
) -> dict[str, Any]:
    latencies = [float(row["generation_seconds"]) for row in rows]
    prompt_tokens = [float(row["prompt_tokens"]) for row in rows]
    generated_tokens = [float(row["generated_tokens"]) for row in rows]
    prompt_tps = [float(row["prompt_tps"]) for row in rows]
    generation_tps = [float(row["generation_tps"]) for row in rows]
    valid_count = sum(bool(row["parser_valid"]) for row in rows)
    expected = {
        "estimated_full_dev_hours": statistics.mean(latencies)
        * full_dev_rows
        / 3600,
        "generated_mean": statistics.mean(generated_tokens),
        "generated_p95": percentile(generated_tokens, 0.95),
        "generated_total": int(sum(generated_tokens)),
        "latency_mean": statistics.mean(latencies),
        "latency_median": statistics.median(latencies),
        "latency_p95": percentile(latencies, 0.95),
        "latency_total": sum(latencies),
        "generation_tps_mean": statistics.mean(generation_tps),
        "generation_tps_median": statistics.median(generation_tps),
        "peak_memory": max(float(row["peak_memory_gb"]) for row in rows),
        "prompt_mean": statistics.mean(prompt_tokens),
        "prompt_p95": percentile(prompt_tokens, 0.95),
        "prompt_total": int(sum(prompt_tokens)),
        "prompt_tps_mean": statistics.mean(prompt_tps),
        "prompt_tps_median": statistics.median(prompt_tps),
        "valid_rate": valid_count / len(rows),
    }
    assert_close(
        summary["estimated_full_dev_hours"],
        expected["estimated_full_dev_hours"],
        f"{condition} full-dev estimate",
    )
    assert_close(
        summary["generated_tokens"]["mean"],
        expected["generated_mean"],
        f"{condition} generated mean",
    )
    assert_close(
        summary["generated_tokens"]["p95"],
        expected["generated_p95"],
        f"{condition} generated p95",
    )
    assert_close(
        summary["generation_seconds"]["mean"],
        expected["latency_mean"],
        f"{condition} latency mean",
    )
    assert_close(
        summary["generation_seconds"]["median"],
        expected["latency_median"],
        f"{condition} latency median",
    )
    assert_close(
        summary["generation_seconds"]["p95"],
        expected["latency_p95"],
        f"{condition} latency p95",
    )
    assert_close(
        summary["generation_seconds"]["total"],
        expected["latency_total"],
        f"{condition} latency total",
    )
    assert_close(
        summary["generation_tps"]["mean"],
        expected["generation_tps_mean"],
        f"{condition} generation tps mean",
    )
    assert_close(
        summary["generation_tps"]["median"],
        expected["generation_tps_median"],
        f"{condition} generation tps median",
    )
    assert_close(
        summary["peak_memory_gb_max"],
        expected["peak_memory"],
        f"{condition} peak memory",
    )
    assert_close(
        summary["prompt_tokens"]["mean"],
        expected["prompt_mean"],
        f"{condition} prompt mean",
    )
    assert_close(
        summary["prompt_tokens"]["p95"],
        expected["prompt_p95"],
        f"{condition} prompt p95",
    )
    assert_close(
        summary["prompt_tps"]["mean"],
        expected["prompt_tps_mean"],
        f"{condition} prompt tps mean",
    )
    assert_close(
        summary["prompt_tps"]["median"],
        expected["prompt_tps_median"],
        f"{condition} prompt tps median",
    )
    assert_close(
        summary["parser_valid_rate"],
        expected["valid_rate"],
        f"{condition} parser valid rate",
    )
    exact_checks = {
        "finish_reasons": dict(
            sorted(Counter(row["finish_reason"] for row in rows).items())
        ),
        "generated_total": expected["generated_total"],
        "length_terminated": sum(row["finish_reason"] == "length" for row in rows),
        "parser_errors": dict(
            sorted(
                Counter(
                    row["parser_error"] for row in rows if row["parser_error"]
                ).items()
            )
        ),
        "prompt_total": expected["prompt_total"],
        "sample_count": len(rows),
        "valid_count": valid_count,
    }
    if summary["finish_reasons"] != exact_checks["finish_reasons"]:
        raise ValueError(f"{condition} finish reasons mismatch")
    if summary["generated_tokens"]["total"] != exact_checks["generated_total"]:
        raise ValueError(f"{condition} generated total mismatch")
    if summary["length_terminated"] != exact_checks["length_terminated"]:
        raise ValueError(f"{condition} length count mismatch")
    if summary["parser_errors"] != exact_checks["parser_errors"]:
        raise ValueError(f"{condition} parser error counts mismatch")
    if summary["prompt_tokens"]["total"] != exact_checks["prompt_total"]:
        raise ValueError(f"{condition} prompt total mismatch")
    if summary["sample_count"] != exact_checks["sample_count"]:
        raise ValueError(f"{condition} sample count mismatch")
    if summary["parser_valid_count"] != exact_checks["valid_count"]:
        raise ValueError(f"{condition} parser valid count mismatch")
    return exact_checks


def main() -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite: {OUTPUT_PATH}")
    for path, expected_hash in EXPECTED_HASHES.items():
        actual = exp022_verify.sha256_file(path)
        if actual != expected_hash:
            raise ValueError(f"Frozen hash mismatch for {path}: {actual}")
    if TEST_PATH.exists():
        raise ValueError("GoEmotions test split is present during EXP-023 verification")

    config = load_json(CONFIG_PATH)
    prompt = load_json(PROMPT_PATH)
    run = load_json(RUN_PATH)
    summary = load_json(SUMMARY_PATH)
    selected = load_json(SELECTED_PATH)
    parent_selected = load_json(PARENT_SELECTED_PATH)

    if config["experiment_id"] != "EXP-023" or config["parent_experiment"] != "EXP-022":
        raise ValueError("EXP-023 config identity mismatch")
    if config["output_schema"] != {
        "exact_key": "label_ids",
        "label_id_max": 27,
        "label_id_min": 0,
        "neutral_label_id": 27,
        "silent_repairs": False,
        "synonym_mapping": False,
    }:
        raise ValueError("EXP-023 output schema changed")
    if prompt["prompt_id"] != "EXP-023-label-id-v1":
        raise ValueError("EXP-023 prompt identity mismatch")
    if run["status"] != "Completed" or run["experiment_id"] != "EXP-023":
        raise ValueError("EXP-023 run is not completed")
    if run["parent_experiment"] != "EXP-022" or run["accessed_splits"] != ["train"]:
        raise ValueError("EXP-023 parent or split access mismatch")
    if run["validation_split_accessed"] or run["test_split_accessed"]:
        raise ValueError("EXP-023 reports dev/test access")
    if run["data"]["gold_labels_retained_or_used"]:
        raise ValueError("EXP-023 reports gold-label use")
    if run["parser"] != {
        "label_id_range": [0, 27],
        "neutral_label_id": 27,
        "retries": 0,
        "schema": {"label_ids": "non-empty unique integer array"},
        "silent_repairs": False,
        "synonym_mapping": False,
    }:
        raise ValueError("EXP-023 run reports an unexpected parser policy")

    if set(selected) != SELECTED_FIELDS:
        raise ValueError("Selected-samples artifact has unexpected fields")
    reconstructed = exp022_verify.reconstruct_selection(config)
    if selected != parent_selected:
        raise ValueError("EXP-023 sample artifact differs from EXP-022")
    if selected["samples"] != reconstructed["samples"]:
        raise ValueError("Selected anonymous sample metadata mismatch")
    if selected["strata"] != reconstructed["strata"]:
        raise ValueError("Length-stratum metadata mismatch")
    if (
        selected["selection_digest_sha256"]
        != reconstructed["selection_digest_sha256"]
        or selected["selection_digest_sha256"] != EXPECTED_SELECTION_DIGEST
    ):
        raise ValueError("Selection digest mismatch")
    if (
        selected["raw_text_stored"]
        or selected["raw_comment_ids_stored"]
        or selected["gold_labels_retained_or_used"]
    ):
        raise ValueError("Selected-samples artifact violates the privacy boundary")

    results = read_results()
    if len(results) != config["resource_budget"]["measured_generations"]:
        raise ValueError("Measured generation count mismatch")
    expected_order = []
    for sample_index in range(config["data"]["sample_count"]):
        condition_order = list(CONDITIONS)
        if sample_index % 2:
            condition_order.reverse()
        expected_order.extend((sample_index, condition) for condition in condition_order)
    actual_order = [
        (record["sample_index"], record["condition"]) for record in results
    ]
    if actual_order != expected_order:
        raise ValueError("EXP-023 sample-condition order differs from EXP-022")
    sample_metadata = {
        row["sample_index"]: row for row in selected["samples"]
    }
    for record in results:
        expected = sample_metadata[record["sample_index"]]
        if (
            record["length_stratum"] != expected["length_stratum"]
            or record["text_character_count"] != expected["text_character_count"]
        ):
            raise ValueError("Result sample metadata mismatch")

    full_dev_rows = config["data"]["dev_rows_for_linear_estimate"]
    condition_checks = {}
    for condition in CONDITIONS:
        rows = [row for row in results if row["condition"] == condition]
        condition_checks[condition] = verify_condition_summary(
            condition,
            rows,
            summary["conditions"][condition],
            full_dev_rows,
        )

    budget = config["resource_budget"]
    gate_rules = config["success_gate"]
    recomputed_gate = {
        "full_dev_estimate_within_budget": all(
            summary["conditions"][condition]["estimated_full_dev_hours"]
            <= budget["full_dev_estimate_hours_per_condition_max"]
            for condition in CONDITIONS
        ),
        "generation_failures_within_budget": summary["generation_failures"]
        <= gate_rules["generation_failures_max"],
        "length_termination_within_budget": all(
            summary["conditions"][condition]["length_terminated"]
            <= gate_rules["length_terminated_max_per_condition"]
            for condition in CONDITIONS
        ),
        "peak_memory_within_budget": summary["overall_peak_memory_gb"]
        <= budget["peak_mlx_memory_gb_max"],
        "strict_parser_rate_within_budget": all(
            summary["conditions"][condition]["parser_valid_rate"]
            >= gate_rules["strict_parser_valid_rate_min_per_condition"]
            for condition in CONDITIONS
        ),
        "wall_time_within_budget": summary["total_seconds"]
        <= budget["wall_time_minutes_max"] * 60,
    }
    if recomputed_gate != summary["gate_checks"]:
        raise ValueError("Gate checks do not reproduce")
    gate_status = "Passed" if all(recomputed_gate.values()) else "Failed"
    if gate_status != summary["gate_status"] or gate_status != run["gate_status"]:
        raise ValueError("Gate status mismatch")

    for artifact_name in (
        "config",
        "parent_runner",
        "parent_selected_samples",
        "prompt",
        "runner",
        "sample_results",
        "selected_samples",
        "summary",
    ):
        artifact = run["artifacts"][artifact_name]
        path = PROJECT_ROOT / artifact["path"]
        if exp022_verify.sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"Run artifact hash mismatch: {artifact_name}")

    report = {
        "checks": {
            "condition_checks": condition_checks,
            "data_rows_scanned": run["data"]["data_rows_scanned"],
            "dev_accessed": False,
            "gate_checks": recomputed_gate,
            "gate_status": gate_status,
            "gold_labels_retained_or_used": False,
            "measured_generations": len(results),
            "parent_sample_match": True,
            "privacy_boundary": "passed",
            "sample_count": selected["sample_count"],
            "selection_digest_sha256": reconstructed[
                "selection_digest_sha256"
            ],
            "test_accessed": False,
        },
        "experiment_id": "EXP-023",
        "status": "Verified",
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "gate_status": gate_status,
                "measured_generations": len(results),
                "status": "Verified",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

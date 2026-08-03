#!/usr/bin/env python3
"""Independently verify EXP-022 resource, privacy, and gate artifacts."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
RUN_DIR = SCRIPT_DIR / "runs" / "exp-022-resource-parser-trial"
RUN_PATH = RUN_DIR / "run.json"
SUMMARY_PATH = RUN_DIR / "summary.json"
SELECTED_PATH = RUN_DIR / "selected-samples.json"
RESULTS_PATH = RUN_DIR / "sample-results.jsonl"
OUTPUT_PATH = RUN_DIR / "verification.json"
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-022-resource-parser-trial.json"
PROMPT_PATH = SCRIPT_DIR / "prompts" / "exp-022-resource-v1.json"
TRAIN_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "train.tsv"
LABELS_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "emotions.txt"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
MODEL_MANIFEST_PATH = PROJECT_ROOT / "models" / "qwen3-1.7b" / "manifest.json"
EXPECTED_HASHES = {
    CONFIG_PATH: "58fce1005e1dc8a61fcb122ea4748df1ecf9d0916d29dd3557ced2bfbfb0e10e",
    PROMPT_PATH: "2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c",
    TRAIN_PATH: "1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5",
    LABELS_PATH: "45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89",
    MODEL_MANIFEST_PATH: "7c1e0e53e6340d5ce33c366569a07763be41546045017870cc149a8f50d1e877",
}
SELECTION_SALT = "EXP-022-selection-v1:"
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
    "parser_error",
    "parser_valid",
    "parsed_labels",
    "peak_memory_gb",
    "prompt_tokens",
    "prompt_tps",
    "raw_output_stored",
    "sample_index",
    "text_character_count",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def reconstruct_selection(config: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with TRAIN_PATH.open("r", encoding="utf-8", newline="") as source:
        for row_number, row in enumerate(csv.reader(source, delimiter="\t"), start=1):
            if len(row) != 3:
                raise ValueError(f"Malformed train row {row_number}")
            text, _discarded_gold_labels, comment_id = row
            rows.append(
                {
                    "comment_id": comment_id,
                    "id_hash": sha256_text(comment_id),
                    "row_number": row_number,
                    "selector_hash": sha256_text(SELECTION_SALT + comment_id),
                    "text_character_count": len(text),
                }
            )
    expected_rows = config["data"]["expected_train_rows"]
    if len(rows) != expected_rows:
        raise ValueError("Verifier train row count mismatch")
    ranked = sorted(
        rows,
        key=lambda row: (
            row["text_character_count"],
            row["id_hash"],
            row["row_number"],
        ),
    )
    strata: list[list[dict[str, Any]]] = [[] for _ in range(4)]
    for rank, row in enumerate(ranked):
        stratum = min(3, (rank * 4) // expected_rows)
        row["length_stratum"] = stratum
        strata[stratum].append(row)
    selected = []
    per_stratum = config["data"]["selection"]["per_stratum"]
    for values in strata:
        selected.extend(
            sorted(values, key=lambda row: (row["selector_hash"], row["row_number"]))[
                :per_stratum
            ]
        )
    selected.sort(
        key=lambda row: (
            row["length_stratum"],
            row["selector_hash"],
            row["row_number"],
        )
    )
    selection_material = "\n".join(
        f"{row['row_number']}:{row['comment_id']}" for row in selected
    )
    return {
        "samples": [
            {
                "length_stratum": row["length_stratum"],
                "sample_index": index,
                "text_character_count": row["text_character_count"],
            }
            for index, row in enumerate(selected)
        ],
        "selection_digest_sha256": sha256_text(selection_material),
        "strata": [
            {
                "length_max": max(row["text_character_count"] for row in values),
                "length_min": min(row["text_character_count"] for row in values),
                "population": len(values),
                "selected": per_stratum,
                "stratum": index,
            }
            for index, values in enumerate(strata)
        ],
    }


def read_results(labels: tuple[str, ...]) -> list[dict[str, Any]]:
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
            if record["parser_valid"]:
                canonical = record["canonical_output"]
                decoded = json.loads(canonical)
                if set(decoded) != {"labels"} or decoded["labels"] != record["parsed_labels"]:
                    raise ValueError("Canonical parser record mismatch")
                if not decoded["labels"] or len(decoded["labels"]) != len(set(decoded["labels"])):
                    raise ValueError("Invalid canonical label list")
                if any(label not in labels for label in decoded["labels"]):
                    raise ValueError("Canonical output contains an unknown label")
                if "neutral" in decoded["labels"] and len(decoded["labels"]) > 1:
                    raise ValueError("Canonical output combines neutral with an emotion")
                if record["parser_error"] is not None:
                    raise ValueError("Valid parser record contains an error")
                # The model output may contain harmless surrounding whitespace;
                # only canonical label JSON is retained in public artifacts.
            else:
                if (
                    record["canonical_output"] is not None
                    or record["parsed_labels"]
                    or not record["parser_error"]
                ):
                    raise ValueError("Invalid parser record exposes unexpected content")
            results.append(record)
    return results


def verify_condition_summary(
    condition: str,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    latencies = [float(row["generation_seconds"]) for row in rows]
    prompt_tokens = [float(row["prompt_tokens"]) for row in rows]
    generated_tokens = [float(row["generated_tokens"]) for row in rows]
    prompt_tps = [float(row["prompt_tps"]) for row in rows]
    generation_tps = [float(row["generation_tps"]) for row in rows]
    valid_count = sum(bool(row["parser_valid"]) for row in rows)
    expected = {
        "estimated_full_dev_hours": statistics.mean(latencies) * 5426 / 3600,
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
    assert_close(summary["estimated_full_dev_hours"], expected["estimated_full_dev_hours"], f"{condition} full-dev estimate")
    assert_close(summary["generated_tokens"]["mean"], expected["generated_mean"], f"{condition} generated mean")
    assert_close(summary["generated_tokens"]["p95"], expected["generated_p95"], f"{condition} generated p95")
    assert_close(summary["generation_seconds"]["mean"], expected["latency_mean"], f"{condition} latency mean")
    assert_close(summary["generation_seconds"]["median"], expected["latency_median"], f"{condition} latency median")
    assert_close(summary["generation_seconds"]["p95"], expected["latency_p95"], f"{condition} latency p95")
    assert_close(summary["generation_seconds"]["total"], expected["latency_total"], f"{condition} latency total")
    assert_close(summary["generation_tps"]["mean"], expected["generation_tps_mean"], f"{condition} generation tps mean")
    assert_close(summary["generation_tps"]["median"], expected["generation_tps_median"], f"{condition} generation tps median")
    assert_close(summary["peak_memory_gb_max"], expected["peak_memory"], f"{condition} peak memory")
    assert_close(summary["prompt_tokens"]["mean"], expected["prompt_mean"], f"{condition} prompt mean")
    assert_close(summary["prompt_tokens"]["p95"], expected["prompt_p95"], f"{condition} prompt p95")
    assert_close(summary["prompt_tps"]["mean"], expected["prompt_tps_mean"], f"{condition} prompt tps mean")
    assert_close(summary["prompt_tps"]["median"], expected["prompt_tps_median"], f"{condition} prompt tps median")
    assert_close(summary["parser_valid_rate"], expected["valid_rate"], f"{condition} parser valid rate")
    exact_checks = {
        "finish_reasons": dict(sorted(Counter(row["finish_reason"] for row in rows).items())),
        "generated_total": expected["generated_total"],
        "length_terminated": sum(row["finish_reason"] == "length" for row in rows),
        "parser_errors": dict(sorted(Counter(row["parser_error"] for row in rows if row["parser_error"]).items())),
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
        actual = sha256_file(path)
        if actual != expected_hash:
            raise ValueError(f"Frozen hash mismatch for {path}: {actual}")
    if TEST_PATH.exists():
        raise ValueError("GoEmotions test split is present during EXP-022 verification")

    config = load_json(CONFIG_PATH)
    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    run = load_json(RUN_PATH)
    summary = load_json(SUMMARY_PATH)
    selected = load_json(SELECTED_PATH)
    if run["status"] != "Completed" or run["experiment_id"] != "EXP-022":
        raise ValueError("EXP-022 run is not completed")
    if run["accessed_splits"] != ["train"]:
        raise ValueError("EXP-022 accessed an unexpected split")
    if run["validation_split_accessed"] or run["test_split_accessed"]:
        raise ValueError("EXP-022 reports dev/test access")
    if run["data"]["gold_labels_retained_or_used"]:
        raise ValueError("EXP-022 reports gold-label use")

    reconstructed = reconstruct_selection(config)
    if selected["samples"] != reconstructed["samples"]:
        raise ValueError("Selected anonymous sample metadata mismatch")
    if selected["strata"] != reconstructed["strata"]:
        raise ValueError("Length-stratum metadata mismatch")
    if selected["selection_digest_sha256"] != reconstructed["selection_digest_sha256"]:
        raise ValueError("Selection digest mismatch")
    if (
        selected["raw_text_stored"]
        or selected["raw_comment_ids_stored"]
        or selected["gold_labels_retained_or_used"]
    ):
        raise ValueError("Selected-samples artifact violates the privacy boundary")

    results = read_results(labels)
    if len(results) != config["resource_budget"]["measured_generations"]:
        raise ValueError("Measured generation count mismatch")
    expected_pairs = {
        (sample_index, condition)
        for sample_index in range(config["data"]["sample_count"])
        for condition in CONDITIONS
    }
    actual_pairs = {(row["sample_index"], row["condition"]) for row in results}
    if actual_pairs != expected_pairs or len(actual_pairs) != len(results):
        raise ValueError("Sample-condition coverage is not exactly one-to-one")

    condition_checks = {}
    for condition in CONDITIONS:
        rows = [row for row in results if row["condition"] == condition]
        condition_checks[condition] = verify_condition_summary(
            condition,
            rows,
            summary["conditions"][condition],
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

    for artifact_name in ("config", "prompt", "sample_results", "selected_samples", "summary"):
        artifact = run["artifacts"][artifact_name]
        path = PROJECT_ROOT / artifact["path"]
        if sha256_file(path) != artifact["sha256"]:
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
            "privacy_boundary": "passed",
            "sample_count": selected["sample_count"],
            "selection_digest_sha256": reconstructed["selection_digest_sha256"],
            "test_accessed": False,
        },
        "experiment_id": "EXP-022",
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

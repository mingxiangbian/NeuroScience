#!/usr/bin/env python3
"""Independently verify EXP-024 constrained JSON trial artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import verify_resource_parser_trial as exp022_verify


PROJECT_ROOT = SCRIPT_DIR.parents[2]
RUN_DIR = SCRIPT_DIR / "runs" / "exp-024-constrained-json-trial"
RUN_PATH = RUN_DIR / "run.json"
SUMMARY_PATH = RUN_DIR / "summary.json"
SELECTED_PATH = RUN_DIR / "selected-samples.json"
RESULTS_PATH = RUN_DIR / "sample-results.jsonl"
OUTPUT_PATH = RUN_DIR / "verification.json"
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-024-constrained-json-trial.json"
PROMPT_PATH = SCRIPT_DIR / "prompts" / "exp-022-resource-v1.json"
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint.py"
RUNNER_PATH = SCRIPT_DIR / "run_constrained_json_trial.py"
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
    CONFIG_PATH: "b16d3cda88d06e4bc89f8201471118be797f1ef668ad0df06f322a6c49e64494",
    PROMPT_PATH: "2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c",
    CONSTRAINT_PATH: "6e4d1d21d79d2fed3c8a5d118748591db6e72cfcfefb74386f913fb5fd164efa",
    RUNNER_PATH: "f004b584a528bb969042f4689a8528c6751c2d53ebd9d2650267e8f8eede7b02",
    PARENT_RUNNER_PATH: "d2051f5c621190117cb5c874e5d8c3a128aee262a1a070b038c5254d90b40e5e",
    PARENT_VERIFIER_PATH: "02c88592fd968eba5e58ebba84b8d83e228c8725d9f0f6a1842a950f1e0fa20d",
    TRAIN_PATH: "1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5",
    LABELS_PATH: "45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89",
    MODEL_MANIFEST_PATH: "7c1e0e53e6340d5ce33c366569a07763be41546045017870cc149a8f50d1e877",
}
EXPECTED_SELECTION_DIGEST = (
    "7dcdbe002627948d6e1c5ed4eceb950085585ad0c726333ba3012515dbd8c525"
)
EXPECTED_CANDIDATE_TOKEN_COUNT = 14215
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
                if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
                    raise ValueError("Canonical parser record has the wrong schema")
                values = decoded["labels"]
                if values != record["parsed_labels"]:
                    raise ValueError("Canonical parser record mismatch")
                if not isinstance(values, list) or not values:
                    raise ValueError("Canonical labels are not a non-empty list")
                if not all(isinstance(value, str) for value in values):
                    raise ValueError("Canonical labels contain a non-string")
                if len(values) != len(set(values)):
                    raise ValueError("Canonical output contains duplicate labels")
                if any(value not in labels for value in values):
                    raise ValueError("Canonical output contains an unknown label")
                if "neutral" in values and len(values) > 1:
                    raise ValueError("Canonical output combines neutral with an emotion")
                expected_canonical = json.dumps(
                    {"labels": values}, separators=(",", ":")
                )
                if canonical != expected_canonical or record["parser_error"] is not None:
                    raise ValueError("Valid parser record is not canonical")
            else:
                if (
                    record["canonical_output"] is not None
                    or record["parsed_labels"]
                    or not isinstance(record["parser_error"], str)
                    or not record["parser_error"]
                ):
                    raise ValueError("Invalid parser record exposes unexpected content")
            results.append(record)
    return results


def main() -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite: {OUTPUT_PATH}")
    for path, expected_hash in EXPECTED_HASHES.items():
        actual = exp022_verify.sha256_file(path)
        if actual != expected_hash:
            raise ValueError(f"Frozen hash mismatch for {path}: {actual}")
    if TEST_PATH.exists():
        raise ValueError("GoEmotions test split is present during EXP-024 verification")

    config = load_json(CONFIG_PATH)
    prompt = load_json(PROMPT_PATH)
    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    run = load_json(RUN_PATH)
    summary = load_json(SUMMARY_PATH)
    selected = load_json(SELECTED_PATH)
    parent_selected = load_json(PARENT_SELECTED_PATH)

    if config["experiment_id"] != "EXP-024" or config["parent_experiment"] != "EXP-022":
        raise ValueError("EXP-024 config identity mismatch")
    if config["output_schema"] != {
        "exact_key": "labels",
        "label_names_from_frozen_ontology_only": True,
        "neutral_combination_allowed": False,
        "silent_repairs": False,
        "synonym_mapping": False,
    }:
        raise ValueError("EXP-024 output schema changed")
    if prompt["prompt_id"] != "EXP-022-resource-v1":
        raise ValueError("EXP-024 does not use the frozen EXP-022 prompt")
    if run["status"] != "Completed" or run["experiment_id"] != "EXP-024":
        raise ValueError("EXP-024 run is not completed")
    if run["parent_experiment"] != "EXP-022" or run["accessed_splits"] != ["train"]:
        raise ValueError("EXP-024 parent or split access mismatch")
    if run["validation_split_accessed"] or run["test_split_accessed"]:
        raise ValueError("EXP-024 reports dev/test access")
    if run["data"]["gold_labels_retained_or_used"]:
        raise ValueError("EXP-024 reports gold-label use")
    expected_decoder = {
        "candidate_token_count": EXPECTED_CANDIDATE_TOKEN_COUNT,
        "constraint": "finite-state label-name JSON token mask",
        "fallback_to_unrestricted_generation": False,
        "retries": 0,
        "silent_repairs": False,
        "synonym_mapping": False,
    }
    if run["decoder"] != expected_decoder:
        raise ValueError("EXP-024 run reports an unexpected decoder policy")

    if set(selected) != SELECTED_FIELDS:
        raise ValueError("Selected-samples artifact has unexpected fields")
    reconstructed = exp022_verify.reconstruct_selection(config)
    if selected != parent_selected:
        raise ValueError("EXP-024 sample artifact differs from EXP-022")
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

    results = read_results(labels)
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
        raise ValueError("EXP-024 sample-condition order differs from EXP-022")
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

    condition_checks = {}
    for condition in CONDITIONS:
        rows = [row for row in results if row["condition"] == condition]
        condition_checks[condition] = exp022_verify.verify_condition_summary(
            condition,
            rows,
            summary["conditions"][condition],
        )

    if summary["constraint_candidate_token_count"] != EXPECTED_CANDIDATE_TOKEN_COUNT:
        raise ValueError("Constraint candidate-token count mismatch")
    if (
        not isinstance(summary["constraint_init_seconds"], (int, float))
        or not math.isfinite(float(summary["constraint_init_seconds"]))
        or summary["constraint_init_seconds"] <= 0
    ):
        raise ValueError("Invalid constraint initialization time")

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
        "constraint",
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
            "constraint_candidate_token_count": EXPECTED_CANDIDATE_TOKEN_COUNT,
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
        "experiment_id": "EXP-024",
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

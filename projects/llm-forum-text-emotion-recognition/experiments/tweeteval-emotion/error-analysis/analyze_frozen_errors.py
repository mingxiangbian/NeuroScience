#!/usr/bin/env python3
"""Aggregate EXP-016 predictions and select a frozen qualitative error sample."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-017-frozen-error-analysis.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def verify_file(spec: dict[str, Any]) -> Path:
    path = project_path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != spec["sha256"]:
        raise ValueError(
            f"Hash mismatch for {path}: expected {spec['sha256']}, observed {observed}"
        )
    return path


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_prediction_rows(
    condition_id: str,
    condition_results: list[dict[str, Any]],
    label_names: list[str],
) -> list[dict[int, dict[str, Any]]]:
    loaded_runs: list[dict[int, dict[str, Any]]] = []
    for result in condition_results:
        artifact = result["artifacts"]["predictions"]
        path = project_path(artifact["path"])
        observed_hash = sha256_file(path)
        if observed_hash != artifact["sha256"]:
            raise ValueError(
                f"Prediction hash mismatch for {condition_id}: {path}"
            )

        rows: dict[int, dict[str, Any]] = {}
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "row_id",
                "gold_id",
                "gold_label",
                "prediction_id",
                "prediction_label",
            }
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f"Missing prediction columns in {path}")
            for raw in reader:
                row_id = int(raw["row_id"])
                if row_id in rows:
                    raise ValueError(f"Duplicate row_id {row_id} in {path}")
                gold_id = int(raw["gold_id"])
                prediction_id = int(raw["prediction_id"])
                if raw["gold_label"] != label_names[gold_id]:
                    raise ValueError(f"Gold mapping mismatch in {path}, row {row_id}")
                if raw["prediction_label"] != label_names[prediction_id]:
                    raise ValueError(
                        f"Prediction mapping mismatch in {path}, row {row_id}"
                    )

                score_prefix = (
                    "prob_" if f"prob_{label_names[0]}" in raw else "decision_"
                )
                scores = {
                    name: float(raw[f"{score_prefix}{name}"]) for name in label_names
                }
                rows[row_id] = {
                    "row_id": row_id,
                    "gold_id": gold_id,
                    "gold_label": raw["gold_label"],
                    "prediction_id": prediction_id,
                    "prediction_label": raw["prediction_label"],
                    "scores": scores,
                    "score_type": (
                        "probability" if score_prefix == "prob_" else "decision"
                    ),
                    "seed": result.get("seed"),
                }
        loaded_runs.append(rows)
    return loaded_runs


def mode_or_tie(values: list[str]) -> tuple[str, bool]:
    counts = Counter(values)
    maximum = max(counts.values())
    winners = sorted(key for key, count in counts.items() if count == maximum)
    return ("|".join(winners), len(winners) > 1)


def build_records(
    predictions: dict[str, list[dict[int, dict[str, Any]]]],
    label_names: list[str],
    sample_count: int,
) -> list[dict[str, Any]]:
    expected_ids = set(range(sample_count))
    for condition_id, runs in predictions.items():
        for rows in runs:
            if set(rows) != expected_ids:
                raise ValueError(f"Unexpected row IDs for {condition_id}")

    records: list[dict[str, Any]] = []
    reference_condition = next(iter(predictions))
    for row_id in range(sample_count):
        reference = predictions[reference_condition][0][row_id]
        record: dict[str, Any] = {
            "row_id": row_id,
            "gold_id": reference["gold_id"],
            "gold_label": reference["gold_label"],
            "conditions": {},
        }
        for condition_id, runs in predictions.items():
            rows = [run[row_id] for run in runs]
            if any(
                row["gold_id"] != reference["gold_id"]
                or row["gold_label"] != reference["gold_label"]
                for row in rows
            ):
                raise ValueError(
                    f"Gold label disagreement for {condition_id}, row {row_id}"
                )
            prediction_labels = [row["prediction_label"] for row in rows]
            modal_label, modal_tied = mode_or_tie(prediction_labels)
            mean_scores = {
                label: statistics.fmean(row["scores"][label] for row in rows)
                for label in label_names
            }
            record["conditions"][condition_id] = {
                "run_count": len(rows),
                "correct_count": sum(
                    row["prediction_id"] == reference["gold_id"] for row in rows
                ),
                "prediction_labels": prediction_labels,
                "prediction_labels_by_run": "|".join(prediction_labels),
                "modal_label": modal_label,
                "modal_tied": modal_tied,
                "unanimous_label": (
                    prediction_labels[0]
                    if len(set(prediction_labels)) == 1
                    else ""
                ),
                "mean_scores": mean_scores,
                "mean_gold_score": mean_scores[reference["gold_label"]],
                "score_type": rows[0]["score_type"],
            }
        records.append(record)
    return records


def build_condition_stability(
    records: list[dict[str, Any]],
    condition_ids: list[str],
    label_names: list[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for condition_id in condition_ids:
        for label in ["ALL", *label_names]:
            subset = (
                records if label == "ALL" else [r for r in records if r["gold_label"] == label]
            )
            run_count = subset[0]["conditions"][condition_id]["run_count"]
            all_correct = sum(
                r["conditions"][condition_id]["correct_count"] == run_count
                for r in subset
            )
            all_wrong = sum(
                r["conditions"][condition_id]["correct_count"] == 0 for r in subset
            )
            mixed = len(subset) - all_correct - all_wrong
            output.append(
                {
                    "condition_id": condition_id,
                    "gold_label": label,
                    "row_count": len(subset),
                    "runs_per_row": run_count,
                    "all_runs_correct": all_correct,
                    "all_runs_wrong": all_wrong,
                    "mixed_outcome": mixed,
                    "all_runs_correct_rate": f"{all_correct / len(subset):.12f}",
                    "all_runs_wrong_rate": f"{all_wrong / len(subset):.12f}",
                    "mixed_outcome_rate": f"{mixed / len(subset):.12f}",
                }
            )
    return output


def build_seed_confusions(
    records: list[dict[str, Any]],
    condition_ids: list[str],
    label_names: list[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for condition_id in condition_ids:
        run_count = records[0]["conditions"][condition_id]["run_count"]
        for gold in label_names:
            gold_records = [r for r in records if r["gold_label"] == gold]
            denominator = len(gold_records) * run_count
            counts = Counter(
                prediction
                for record in gold_records
                for prediction in record["conditions"][condition_id][
                    "prediction_labels"
                ]
            )
            for predicted in label_names:
                count = counts[predicted]
                output.append(
                    {
                        "condition_id": condition_id,
                        "gold_label": gold,
                        "prediction_label": predicted,
                        "seed_sample_count": count,
                        "gold_seed_sample_count": denominator,
                        "rate_within_gold": f"{count / denominator:.12f}",
                    }
                )
    return output


def transition_category(before: int, after: int, run_count: int) -> str:
    if before == 0 and after == run_count:
        return "stable_recovery"
    if before == run_count and after == 0:
        return "stable_regression"
    if after > before:
        return "more_correct_seeds"
    if after < before:
        return "fewer_correct_seeds"
    return "unchanged_correct_seed_count"


def build_pairwise_transitions(
    records: list[dict[str, Any]],
    comparisons: list[tuple[str, str, str]],
    label_names: list[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    categories = [
        "stable_recovery",
        "stable_regression",
        "more_correct_seeds",
        "fewer_correct_seeds",
        "unchanged_correct_seed_count",
    ]
    for comparison_id, before_id, after_id in comparisons:
        run_count = records[0]["conditions"][before_id]["run_count"]
        for label in ["ALL", *label_names]:
            subset = (
                records if label == "ALL" else [r for r in records if r["gold_label"] == label]
            )
            observed = Counter(
                transition_category(
                    r["conditions"][before_id]["correct_count"],
                    r["conditions"][after_id]["correct_count"],
                    run_count,
                )
                for r in subset
            )
            for category in categories:
                count = observed[category]
                output.append(
                    {
                        "comparison_id": comparison_id,
                        "before_condition": before_id,
                        "after_condition": after_id,
                        "gold_label": label,
                        "transition": category,
                        "row_count": count,
                        "stratum_count": len(subset),
                        "rate": f"{count / len(subset):.12f}",
                    }
                )
    return output


def deterministic_key(seed: int, role: str, row_id: int) -> str:
    value = f"{seed}:{role}:{row_id}".encode("ascii")
    return hashlib.sha256(value).hexdigest()


def take_per_stratum(
    candidates: list[dict[str, Any]],
    stratum_key: str,
    strata: list[str],
    per_stratum: int,
    selected_ids: set[int],
    sort_key: Any,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for stratum in strata:
        eligible = [
            candidate
            for candidate in candidates
            if candidate[stratum_key] == stratum
            and candidate["row_id"] not in selected_ids
        ]
        for candidate in sorted(eligible, key=sort_key)[:per_stratum]:
            selected.append(candidate)
            selected_ids.add(candidate["row_id"])
    return selected


def select_cases(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    label_names: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    final_id = "exp-015-twitter-roberta-label-smoothing"
    generic_id = "exp-014-generic-roberta-label-smoothing"
    seed = config["sampling"]["fixed_seed"]
    selected_ids: set[int] = set()
    selections: list[dict[str, Any]] = []
    realized: dict[str, Any] = {}

    high_candidates: list[dict[str, Any]] = []
    for record in records:
        final = record["conditions"][final_id]
        if (
            final["correct_count"] == 0
            and final["unanimous_label"]
            and final["unanimous_label"] != record["gold_label"]
        ):
            high_candidates.append(
                {
                    **record,
                    "predicted_stratum": final["unanimous_label"],
                    "confidence": final["mean_scores"][final["unanimous_label"]],
                    "selection_reason": (
                        "EXP-015 unanimous wrong prediction; ranked by mean "
                        "probability assigned to that class"
                    ),
                }
            )
    high_fn = take_per_stratum(
        high_candidates,
        "gold_label",
        label_names,
        2,
        selected_ids,
        lambda row: (-row["confidence"], row["row_id"]),
    )
    high_fp = take_per_stratum(
        high_candidates,
        "predicted_stratum",
        label_names,
        2,
        selected_ids,
        lambda row: (-row["confidence"], row["row_id"]),
    )
    for case in [*high_fn, *high_fp]:
        case["role"] = "final_high_confidence_errors"
        selections.append(case)
    realized["final_high_confidence_errors"] = {
        "candidate_count": len(high_candidates),
        "selected_count": len(high_fn) + len(high_fp),
        "false_negative_slots_filled": len(high_fn),
        "false_positive_slots_filled": len(high_fp),
    }

    domain_candidates: dict[str, list[dict[str, Any]]] = {
        "domain_recoveries": [],
        "domain_regressions": [],
    }
    for record in records:
        before = record["conditions"][generic_id]
        after = record["conditions"][final_id]
        delta = after["mean_gold_score"] - before["mean_gold_score"]
        enriched = {
            **record,
            "domain_gold_probability_delta": delta,
        }
        if before["correct_count"] == 0 and after["correct_count"] == 3:
            enriched["selection_reason"] = (
                "EXP-014 0/3 correct to EXP-015 3/3 correct; ranked by "
                "descending gold-probability change"
            )
            domain_candidates["domain_recoveries"].append(enriched)
        if before["correct_count"] == 3 and after["correct_count"] == 0:
            enriched["selection_reason"] = (
                "EXP-014 3/3 correct to EXP-015 0/3 correct; ranked by "
                "ascending gold-probability change"
            )
            domain_candidates["domain_regressions"].append(enriched)

    for role in ["domain_recoveries", "domain_regressions"]:
        reverse = role == "domain_recoveries"
        chosen = take_per_stratum(
            domain_candidates[role],
            "gold_label",
            label_names,
            2,
            selected_ids,
            (
                (lambda row: (-row["domain_gold_probability_delta"], row["row_id"]))
                if reverse
                else (
                    lambda row: (
                        row["domain_gold_probability_delta"],
                        row["row_id"],
                    )
                )
            ),
        )
        for case in chosen:
            case["role"] = role
            selections.append(case)
        realized[role] = {
            "candidate_count": len(domain_candidates[role]),
            "selected_count": len(chosen),
        }

    shared_candidates = [
        {
            **record,
            "selection_reason": (
                "EXP-007 wrong and all seeds wrong for EXP-011, EXP-014, "
                "and EXP-015; deterministic stratified sample"
            ),
        }
        for record in records
        if record["conditions"]["exp-007-linear-svm"]["correct_count"] == 0
        and all(
            record["conditions"][condition_id]["correct_count"] == 0
            for condition_id in [
                "exp-011-generic-roberta",
                "exp-014-generic-roberta-label-smoothing",
                final_id,
            ]
        )
    ]
    shared = take_per_stratum(
        shared_candidates,
        "gold_label",
        label_names,
        2,
        selected_ids,
        lambda row: (
            deterministic_key(seed, "shared_errors", row["row_id"]),
            row["row_id"],
        ),
    )
    for case in shared:
        case["role"] = "shared_errors"
        selections.append(case)
    realized["shared_errors"] = {
        "candidate_count": len(shared_candidates),
        "selected_count": len(shared),
    }

    ordinary_candidates = [
        {
            **record,
            "selection_reason": (
                "EXP-015 at most 1/3 correct; deterministic stratified sample "
                "after earlier roles"
            ),
        }
        for record in records
        if record["conditions"][final_id]["correct_count"] <= 1
    ]
    ordinary = take_per_stratum(
        ordinary_candidates,
        "gold_label",
        label_names,
        2,
        selected_ids,
        lambda row: (
            deterministic_key(seed, "ordinary_final_errors", row["row_id"]),
            row["row_id"],
        ),
    )
    for case in ordinary:
        case["role"] = "ordinary_final_errors"
        selections.append(case)
    realized["ordinary_final_errors"] = {
        "candidate_count": len(ordinary_candidates),
        "selected_count": len(ordinary),
    }

    maximum = config["sampling"]["maximum_unique_cases"]
    if len(selections) > maximum or len(selected_ids) != len(selections):
        raise ValueError("Sampling budget or uniqueness violation")
    for rank, case in enumerate(selections, start=1):
        case["sample_rank"] = rank
    realized["total"] = {
        "maximum": maximum,
        "selected_count": len(selections),
    }
    return selections, realized


def manifest_rows(selections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    condition_ids = [
        "exp-007-linear-svm",
        "exp-011-generic-roberta",
        "exp-014-generic-roberta-label-smoothing",
        "exp-015-twitter-roberta-label-smoothing",
    ]
    rows: list[dict[str, Any]] = []
    for case in selections:
        row: dict[str, Any] = {
            "sample_rank": case["sample_rank"],
            "role": case["role"],
            "row_id": case["row_id"],
            "gold_id": case["gold_id"],
            "gold_label": case["gold_label"],
            "selection_reason": case["selection_reason"],
        }
        for condition_id in condition_ids:
            short = {
                "exp-007-linear-svm": "exp007",
                "exp-011-generic-roberta": "exp011",
                "exp-014-generic-roberta-label-smoothing": "exp014",
                "exp-015-twitter-roberta-label-smoothing": "exp015",
            }[condition_id]
            values = case["conditions"][condition_id]
            row[f"{short}_correct_count"] = values["correct_count"]
            row[f"{short}_run_count"] = values["run_count"]
            row[f"{short}_predictions"] = values["prediction_labels_by_run"]
        final = case["conditions"]["exp-015-twitter-roberta-label-smoothing"]
        generic = case["conditions"][
            "exp-014-generic-roberta-label-smoothing"
        ]
        row["exp015_mean_gold_probability"] = f"{final['mean_gold_score']:.12f}"
        unanimous = final["unanimous_label"]
        row["exp015_unanimous_prediction"] = unanimous
        row["exp015_mean_unanimous_probability"] = (
            f"{final['mean_scores'][unanimous]:.12f}" if unanimous else ""
        )
        row["exp015_minus_exp014_gold_probability"] = (
            f"{final['mean_gold_score'] - generic['mean_gold_score']:.12f}"
        )
        rows.append(row)
    return rows


def artifact_record(path: Path, contains_raw_text: bool = False) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "contains_raw_text": contains_raw_text,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
        "tracked": not contains_raw_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    started = time.perf_counter()
    started_at = datetime.now().astimezone().isoformat()
    config_path = args.config.resolve()
    config = read_json(config_path)
    output_dir = project_path(config["output_dir"])
    if output_dir.exists():
        raise FileExistsError(
            f"Output directory already exists and is append-only: {output_dir}"
        )

    source_run_path = verify_file(config["source_test_gate"]["run"])
    source_verification_path = verify_file(
        config["source_test_gate"]["verification"]
    )
    test_labels_path = verify_file(config["data"]["test_labels"])
    test_text_path = verify_file(config["data"]["test_text"])
    source_run = read_json(source_run_path)
    source_verification = read_json(source_verification_path)
    if source_run["experiment_id"] != "EXP-016":
        raise ValueError("Unexpected source experiment")
    if source_verification.get("status") != "Verified":
        raise ValueError("EXP-016 verification is not Verified")

    label_mapping = config["data"]["label_mapping"]
    label_names = [label_mapping[str(index)] for index in range(len(label_mapping))]
    expected_condition_ids = [item["id"] for item in config["conditions"]]
    if set(source_run["condition_results"]) != set(expected_condition_ids):
        raise ValueError("EXP-016 condition set does not match EXP-017 config")

    predictions: dict[str, list[dict[int, dict[str, Any]]]] = {}
    for condition in config["conditions"]:
        results = source_run["condition_results"][condition["id"]]
        if len(results) != condition["expected_runs"]:
            raise ValueError(f"Unexpected run count for {condition['id']}")
        predictions[condition["id"]] = load_prediction_rows(
            condition["id"], results, label_names
        )

    sample_count = config["data"]["test_sample_count"]
    records = build_records(predictions, label_names, sample_count)
    with test_labels_path.open(encoding="utf-8") as handle:
        test_labels = [int(line.strip()) for line in handle if line.strip()]
    if len(test_labels) != sample_count:
        raise ValueError("Unexpected test-label count")
    for record, label_id in zip(records, test_labels):
        if record["gold_id"] != label_id:
            raise ValueError(f"Official label mismatch at row {record['row_id']}")

    stability = build_condition_stability(
        records, expected_condition_ids, label_names
    )
    confusions = build_seed_confusions(records, expected_condition_ids, label_names)
    comparisons = [
        (
            "exp014_minus_exp011",
            "exp-011-generic-roberta",
            "exp-014-generic-roberta-label-smoothing",
        ),
        (
            "exp015_minus_exp014",
            "exp-014-generic-roberta-label-smoothing",
            "exp-015-twitter-roberta-label-smoothing",
        ),
    ]
    transitions = build_pairwise_transitions(
        records, comparisons, label_names
    )
    selections, realized_sampling = select_cases(records, config, label_names)

    output_dir.mkdir(parents=True)
    private_dir = output_dir / "private"
    private_dir.mkdir()

    stability_path = output_dir / "condition_stability.csv"
    write_csv(
        stability_path,
        [
            "condition_id",
            "gold_label",
            "row_count",
            "runs_per_row",
            "all_runs_correct",
            "all_runs_wrong",
            "mixed_outcome",
            "all_runs_correct_rate",
            "all_runs_wrong_rate",
            "mixed_outcome_rate",
        ],
        stability,
    )
    confusions_path = output_dir / "seed_confusions.csv"
    write_csv(
        confusions_path,
        [
            "condition_id",
            "gold_label",
            "prediction_label",
            "seed_sample_count",
            "gold_seed_sample_count",
            "rate_within_gold",
        ],
        confusions,
    )
    transitions_path = output_dir / "pairwise_transitions.csv"
    write_csv(
        transitions_path,
        [
            "comparison_id",
            "before_condition",
            "after_condition",
            "gold_label",
            "transition",
            "row_count",
            "stratum_count",
            "rate",
        ],
        transitions,
    )
    manifest = manifest_rows(selections)
    manifest_path = output_dir / "sample_manifest.csv"
    write_csv(manifest_path, list(manifest[0]), manifest)

    # Raw text is opened only after the protocol-driven sample is fixed.
    with test_text_path.open(encoding="utf-8") as handle:
        texts = [line.rstrip("\n") for line in handle]
    if len(texts) != sample_count:
        raise ValueError("Unexpected test-text count")
    private_path = private_dir / "selected_text.private.jsonl"
    with private_path.open("w", encoding="utf-8") as handle:
        for case in selections:
            payload = {
                "gold_label": case["gold_label"],
                "role": case["role"],
                "row_id": case["row_id"],
                "sample_rank": case["sample_rank"],
                "text": texts[case["row_id"]],
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    shared_error_count = sum(
        record["conditions"]["exp-007-linear-svm"]["correct_count"] == 0
        and all(
            record["conditions"][condition_id]["correct_count"] == 0
            for condition_id in [
                "exp-011-generic-roberta",
                "exp-014-generic-roberta-label-smoothing",
                "exp-015-twitter-roberta-label-smoothing",
            ]
        )
        for record in records
    )
    summary = {
        "experiment_id": config["experiment_id"],
        "labels": label_names,
        "row_count": sample_count,
        "sampling": realized_sampling,
        "shared_error_rows": shared_error_count,
        "source_experiment_id": source_run["experiment_id"],
        "test_policy": config["test_policy"],
    }
    summary_path = output_dir / "aggregate_summary.json"
    write_json(summary_path, summary)

    log_lines = [
        f"experiment_id={config['experiment_id']}",
        f"row_count={sample_count}",
        f"selected_count={len(selections)}",
        f"shared_error_rows={shared_error_count}",
        "new_model_inference=0",
        "status=sampling_completed",
    ]
    stdout_path = output_dir / "stdout.log"
    stdout_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    artifacts = {
        "aggregate_summary": artifact_record(summary_path),
        "condition_stability": artifact_record(stability_path),
        "pairwise_transitions": artifact_record(transitions_path),
        "sample_manifest": artifact_record(manifest_path),
        "seed_confusions": artifact_record(confusions_path),
        "selected_text_private": artifact_record(
            private_path, contains_raw_text=True
        ),
        "stdout_log": artifact_record(stdout_path),
    }
    run = {
        "accessed_splits": ["test"],
        "artifacts": artifacts,
        "authorization": config["authorization"],
        "command": " ".join([sys.executable, *sys.argv]),
        "completed_at": datetime.now().astimezone().isoformat(),
        "config": {
            "path": str(config_path.relative_to(PROJECT_ROOT)),
            "sha256": sha256_file(config_path),
        },
        "data": config["data"],
        "environment": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
        },
        "experiment_id": config["experiment_id"],
        "git": {
            "commit": git_value("rev-parse", "HEAD"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "new_model_inference": False,
        "protocol": config["protocol"],
        "sampling": realized_sampling,
        "source_test_gate": config["source_test_gate"],
        "stage": config["stage"],
        "started_at": started_at,
        "status": "sampling_completed",
        "test_split_accessed": True,
        "test_use": "preregistered descriptive error analysis only",
        "tier": config["tier"],
        "validation_split_accessed": False,
        "wall_time_seconds": time.perf_counter() - started,
        "working_directory": str(REPO_ROOT),
    }
    write_json(output_dir / "run.json", run)
    print("\n".join(log_lines))
    print(f"private_text_path={private_path}")


if __name__ == "__main__":
    main()

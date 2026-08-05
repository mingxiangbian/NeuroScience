#!/usr/bin/env python3
"""Independently recompute EXP-036 from frozen inputs and private rater records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_config_path(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path.resolve()
    return resolve_project_path(value).resolve()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def parse_label_ids(value: str) -> list[int]:
    stripped = value.strip()
    return [] if not stripped else [int(item) for item in stripped.split("|")]


def set_f1(left: set[int], right: set[int]) -> float:
    if not left and not right:
        return 1.0
    return 2.0 * len(left & right) / (len(left) + len(right))


def jaccard(left: set[int], right: set[int]) -> float:
    union = left | right
    return 1.0 if not union else len(left & right) / len(union)


def exact(left: set[int], right: set[int]) -> float:
    return float(left == right)


def recursively_find_true_test_access(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower()
            if "test" in normalized and "access" in normalized and nested is True:
                return True
            if recursively_find_true_test_access(nested):
                return True
    elif isinstance(value, list):
        return any(recursively_find_true_test_access(item) for item in value)
    return False


def verify_implementation(config: dict[str, Any]) -> None:
    for name, record in config["implementation"].items():
        if sha256_file(resolve_project_path(record["path"])) != record["sha256"]:
            raise RuntimeError(f"Implementation hash changed: {name}")


def load_dev(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[list[int]]]:
    selection = config["selection"]
    dev_path = resolve_project_path(selection["dev_path"])
    labels_path = resolve_project_path(selection["labels_path"])
    test_path = resolve_project_path(selection["simplified_test_path"])
    if test_path.exists():
        raise RuntimeError("Simplified test.tsv exists")
    if sha256_file(dev_path) != selection["dev_sha256"]:
        raise RuntimeError("Frozen dev hash changed")
    if sha256_file(labels_path) != selection["labels_sha256"]:
        raise RuntimeError("Frozen labels hash changed")
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if labels != config["labels"] or labels.index("neutral") != 27:
        raise RuntimeError("Frozen label order changed")

    selected: list[dict[str, Any]] = []
    all_gold: list[list[int]] = []
    with dev_path.open("r", encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.reader(handle, delimiter="\t"), start=1):
            if len(row) != 3:
                raise RuntimeError(f"Malformed dev row {row_number}")
            text, encoded, comment_id = row
            label_ids = [int(value) for value in encoded.split(",")]
            all_gold.append(label_ids)
            if 27 in label_ids and len(label_ids) > 1:
                selected.append(
                    {
                        "comment_id": comment_id,
                        "example_hash": sha256_text(comment_id),
                        "gold_label_ids": label_ids,
                        "source_dev_row": row_number,
                        "text_sha256": sha256_text(text),
                    }
                )
    row_hash = sha256_text(",".join(str(row["source_dev_row"]) for row in selected))
    if (
        len(all_gold) != selection["dev_rows"]
        or len(selected) != selection["expected_rows"]
        or row_hash != selection["source_dev_rows_sha256"]
    ):
        raise RuntimeError("Frozen dev selection changed")
    return selected, all_gold


def load_private_records(
    path: Path, selected: list[dict[str, Any]], label_count: int
) -> list[dict[str, Any]]:
    target_by_row = {row["source_dev_row"]: row for row in selected}
    records: list[dict[str, Any]] = []
    allowed_keys = {
        "example_hash",
        "label_ids",
        "rater_hash",
        "source_dev_row",
        "source_file",
        "source_line",
        "text_sha256",
        "unclear",
    }
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = json.loads(line)
            if set(record) != allowed_keys:
                raise RuntimeError(f"Private schema changed at line {line_number}")
            target = target_by_row.get(record["source_dev_row"])
            if target is None:
                raise RuntimeError("Private record is outside frozen dev allowlist")
            if (
                record["example_hash"] != target["example_hash"]
                or record["text_sha256"] != target["text_sha256"]
                or len(record["rater_hash"]) != 64
                or record["label_ids"] != sorted(set(record["label_ids"]))
                or any(value < 0 or value >= label_count for value in record["label_ids"])
                or not isinstance(record["unclear"], bool)
            ):
                raise RuntimeError(f"Private record integrity mismatch at line {line_number}")
            records.append(record)
    return records


def rebuild_rater_view(
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
    label_count: int,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    pairs: set[tuple[str, str]] = set()
    duplicates = 0
    for record in records:
        pair = (record["example_hash"], record["rater_hash"])
        duplicates += int(pair in pairs)
        pairs.add(pair)
        by_row[record["source_dev_row"]].append(record)

    structures: list[dict[str, Any]] = []
    view: dict[int, dict[str, Any]] = {}
    rater_counts: Counter[int] = Counter()
    clear_counts: Counter[int] = Counter()
    unclear_rows = 0
    same_rater_rows = 0
    mismatches = 0
    clear_empty = 0
    for target in selected:
        row_number = target["source_dev_row"]
        annotations = by_row.get(row_number, [])
        if not annotations:
            raise RuntimeError(f"Missing private annotations for dev row {row_number}")
        votes = [0] * label_count
        for annotation in annotations:
            for label_id in annotation["label_ids"]:
                votes[label_id] += 1
        derived = [label_id for label_id, count in enumerate(votes) if count >= 2]
        derived_matches = derived == target["gold_label_ids"]
        mismatches += int(not derived_matches)
        clear_sets = [set(row["label_ids"]) for row in annotations if not row["unclear"]]
        all_labeled_sets = [set(row["label_ids"]) for row in annotations if row["label_ids"]]
        clear_empty += sum(int(not row["label_ids"]) for row in annotations if not row["unclear"])
        if not clear_sets or any(not labels for labels in clear_sets) or not all_labeled_sets:
            raise RuntimeError(f"Invalid scoring raters at dev row {row_number}")
        same_rater_count = sum(
            int(27 in set(row["label_ids"]) and bool(set(row["label_ids"]) - {27}))
            for row in annotations
        )
        unclear_count = sum(int(row["unclear"]) for row in annotations)
        same_rater_rows += int(same_rater_count > 0)
        unclear_rows += int(unclear_count > 0)
        rater_counts[len(annotations)] += 1
        clear_counts[len(clear_sets)] += 1
        structures.append(
            {
                "aggregation_only": same_rater_count == 0,
                "clear_rater_count": len(clear_sets),
                "derived_labels_match": derived_matches,
                "example_hash": target["example_hash"],
                "gold_cardinality": len(target["gold_label_ids"]),
                "gold_label_ids": "|".join(str(value) for value in target["gold_label_ids"]),
                "labeled_rater_count": len(all_labeled_sets),
                "rater_count": len(annotations),
                "same_rater_coselection_count": same_rater_count,
                "source_dev_row": row_number,
                "unclear_count": unclear_count,
            }
        )
        view[row_number] = {
            "all_labeled_sets": all_labeled_sets,
            "clear_sets": clear_sets,
            "gold": set(target["gold_label_ids"]),
        }
    if len(by_row) != len(selected) or duplicates or mismatches or clear_empty:
        raise RuntimeError("Rater reconstruction integrity failed")
    summary = {
        "aggregation_only_rate": (len(selected) - same_rater_rows) / len(selected),
        "aggregation_only_rows": len(selected) - same_rater_rows,
        "any_unclear_rate": unclear_rows / len(selected),
        "any_unclear_rows": unclear_rows,
        "clear_empty_annotations": clear_empty,
        "clear_rater_count_distribution": dict(sorted(clear_counts.items())),
        "duplicate_comment_rater_pairs": duplicates,
        "matched_annotation_rows": len(records),
        "official_threshold_reproduction_mismatches": mismatches,
        "rater_count_distribution": dict(sorted(rater_counts.items())),
        "rows": len(selected),
        "same_rater_coselection_rate": same_rater_rows / len(selected),
        "same_rater_coselection_rows": same_rater_rows,
    }
    return structures, view, summary


def load_predictions(
    config: dict[str, Any], all_gold: list[list[int]], selected_rows: set[int]
) -> tuple[dict[str, dict[int, set[int]]], list[dict[str, Any]]]:
    predictions: dict[str, dict[int, set[int]]] = {}
    manifests: list[dict[str, Any]] = []
    for spec in config["predictions"]:
        path = resolve_project_path(spec["path"])
        verification_path = resolve_project_path(spec["verification_path"])
        if sha256_file(path) != spec["sha256"]:
            raise RuntimeError(f"Prediction hash changed: {spec['run_id']}")
        if sha256_file(verification_path) != spec["verification_sha256"]:
            raise RuntimeError(f"Upstream verification hash changed: {spec['run_id']}")
        upstream = read_json(verification_path)
        if upstream.get("status") != spec["verification_status"] or recursively_find_true_test_access(upstream):
            raise RuntimeError(f"Upstream verification invalid: {spec['run_id']}")
        selected_predictions: dict[int, set[int]] = {}
        row_count = 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not {
                "row_number",
                "gold_label_ids",
                "predicted_label_ids",
            }.issubset(reader.fieldnames):
                raise RuntimeError(f"Prediction schema changed: {spec['run_id']}")
            for expected_row, row in enumerate(reader, start=1):
                row_count = expected_row
                row_number = int(row["row_number"])
                gold = parse_label_ids(row["gold_label_ids"])
                predicted = parse_label_ids(row["predicted_label_ids"])
                if row_number != expected_row or gold != all_gold[row_number - 1]:
                    raise RuntimeError(f"Prediction alignment failed: {spec['run_id']}")
                if predicted != sorted(set(predicted)) or any(
                    value < 0 or value >= len(config["labels"]) for value in predicted
                ):
                    raise RuntimeError(f"Prediction labels invalid: {spec['run_id']}")
                if row_number in selected_rows:
                    selected_predictions[row_number] = set(predicted)
        if row_count != config["selection"]["dev_rows"] or len(selected_predictions) != len(selected_rows):
            raise RuntimeError(f"Prediction count failed: {spec['run_id']}")
        predictions[spec["run_id"]] = selected_predictions
        manifests.append(
            {
                "condition": spec["condition"],
                "path": spec["path"],
                "rows": row_count,
                "run_id": spec["run_id"],
                "seed": spec["seed"],
                "sha256": spec["sha256"],
                "verification_path": spec["verification_path"],
                "verification_sha256": spec["verification_sha256"],
                "verification_status": spec["verification_status"],
            }
        )
    return predictions, manifests


PER_EXAMPLE_METRICS = [
    "official_set_f1",
    "official_jaccard",
    "official_exact",
    "clear_rater_expected_set_f1",
    "clear_rater_expected_jaccard",
    "clear_rater_expected_exact",
    "any_clear_rater_exact",
    "best_clear_rater_set_f1",
    "all_labeled_rater_expected_set_f1",
]


def score_runs(
    config: dict[str, Any],
    selected: list[dict[str, Any]],
    view: dict[int, dict[str, Any]],
    predictions: dict[str, dict[int, set[int]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[int, dict[str, float]]]]:
    per_example: list[dict[str, Any]] = []
    run_metrics: list[dict[str, Any]] = []
    score_index: dict[str, dict[int, dict[str, float]]] = {}
    for spec in config["predictions"]:
        run_id = spec["run_id"]
        score_index[run_id] = {}
        run_rows: list[dict[str, Any]] = []
        for target in selected:
            row_number = target["source_dev_row"]
            prediction = predictions[run_id][row_number]
            gold = view[row_number]["gold"]
            clear_sets = view[row_number]["clear_sets"]
            all_labeled_sets = view[row_number]["all_labeled_sets"]
            scores = {
                "official_set_f1": set_f1(prediction, gold),
                "official_jaccard": jaccard(prediction, gold),
                "official_exact": exact(prediction, gold),
                "clear_rater_expected_set_f1": statistics.mean(
                    set_f1(prediction, labels) for labels in clear_sets
                ),
                "clear_rater_expected_jaccard": statistics.mean(
                    jaccard(prediction, labels) for labels in clear_sets
                ),
                "clear_rater_expected_exact": statistics.mean(
                    exact(prediction, labels) for labels in clear_sets
                ),
                "any_clear_rater_exact": max(exact(prediction, labels) for labels in clear_sets),
                "best_clear_rater_set_f1": max(set_f1(prediction, labels) for labels in clear_sets),
                "all_labeled_rater_expected_set_f1": statistics.mean(
                    set_f1(prediction, labels) for labels in all_labeled_sets
                ),
            }
            score_index[run_id][row_number] = scores
            row = {
                "condition": spec["condition"],
                "example_hash": target["example_hash"],
                "gold_cardinality": len(gold),
                "predicted_cardinality": len(prediction),
                "predicted_neutral_emotion": 27 in prediction and len(prediction) > 1,
                "run_id": run_id,
                "seed": spec["seed"],
                "source_dev_row": row_number,
                **scores,
            }
            per_example.append(row)
            run_rows.append(row)
        summary = {
            "condition": spec["condition"],
            "empty_prediction_count": sum(int(row["predicted_cardinality"] == 0) for row in run_rows),
            "mean_predicted_cardinality": statistics.mean(row["predicted_cardinality"] for row in run_rows),
            "neutral_emotion_prediction_count": sum(
                int(row["predicted_neutral_emotion"]) for row in run_rows
            ),
            "rows": len(run_rows),
            "run_id": run_id,
            "seed": spec["seed"],
        }
        for metric in PER_EXAMPLE_METRICS:
            summary[metric] = statistics.mean(float(row[metric]) for row in run_rows)
        summary["rater_minus_official_set_f1"] = (
            summary["clear_rater_expected_set_f1"] - summary["official_set_f1"]
        )
        run_metrics.append(summary)
    return per_example, run_metrics, score_index


def summarize_families(run_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in run_metrics:
        grouped[row["condition"]].append(row)
    output: list[dict[str, Any]] = []
    metrics = [
        "official_set_f1",
        "official_exact",
        "clear_rater_expected_set_f1",
        "clear_rater_expected_exact",
        "any_clear_rater_exact",
        "rater_minus_official_set_f1",
        "mean_predicted_cardinality",
    ]
    for condition, rows in sorted(grouped.items()):
        summary: dict[str, Any] = {
            "condition": condition,
            "run_count": len(rows),
            "seeds": "|".join(str(row["seed"]) for row in sorted(rows, key=lambda item: item["seed"])),
        }
        for metric in metrics:
            values = [float(row[metric]) for row in rows]
            summary[f"{metric}_mean"] = statistics.mean(values)
            summary[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else None
        output.append(summary)
    return output


def percentile(sorted_values: list[float], quantile: float) -> float:
    position = (len(sorted_values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def paired_bootstrap(
    official_delta: list[float], rater_delta: list[float], iterations: int, seed: int
) -> dict[str, tuple[float, float]]:
    rng = random.Random(seed)
    count = len(official_delta)
    distributions = {"official": [], "rater": [], "shift": []}
    for _ in range(iterations):
        official_total = 0.0
        rater_total = 0.0
        for _ in range(count):
            index = rng.randrange(count)
            official_total += official_delta[index]
            rater_total += rater_delta[index]
        official_mean = official_total / count
        rater_mean = rater_total / count
        distributions["official"].append(official_mean)
        distributions["rater"].append(rater_mean)
        distributions["shift"].append(rater_mean - official_mean)
    result: dict[str, tuple[float, float]] = {}
    for name, values in distributions.items():
        values.sort()
        result[name] = (percentile(values, 0.025), percentile(values, 0.975))
    return result


def operand_scores(
    operand: dict[str, Any],
    config: dict[str, Any],
    score_index: dict[str, dict[int, dict[str, float]]],
    selected_rows: list[int],
) -> dict[int, dict[str, float]]:
    specs = [
        spec
        for spec in config["predictions"]
        if spec["condition"] == operand["condition"] and spec["seed"] in operand["seeds"]
    ]
    if len(specs) != len(operand["seeds"]):
        raise RuntimeError("Incomplete comparison operand")
    return {
        row_number: {
            metric: statistics.mean(
                score_index[spec["run_id"]][row_number][metric] for spec in specs
            )
            for metric in ("official_set_f1", "clear_rater_expected_set_f1")
        }
        for row_number in selected_rows
    }


def compare_models(
    config: dict[str, Any],
    score_index: dict[str, dict[int, dict[str, float]]],
    selected_rows: list[int],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    tie = config["statistics"]["practical_tie_threshold"]
    material = config["statistics"]["material_shift_threshold"]
    iterations = config["statistics"]["bootstrap_iterations"]
    base_seed = config["statistics"]["bootstrap_seed"]
    for comparison in config["comparisons"]:
        candidate = operand_scores(comparison["candidate"], config, score_index, selected_rows)
        reference = operand_scores(comparison["reference"], config, score_index, selected_rows)
        official_delta = [
            candidate[row]["official_set_f1"] - reference[row]["official_set_f1"]
            for row in selected_rows
        ]
        rater_delta = [
            candidate[row]["clear_rater_expected_set_f1"]
            - reference[row]["clear_rater_expected_set_f1"]
            for row in selected_rows
        ]
        seed = int(sha256_text(f"{base_seed}:{comparison['comparison_id']}")[:16], 16)
        cis = paired_bootstrap(official_delta, rater_delta, iterations, seed)
        official_mean = statistics.mean(official_delta)
        rater_mean = statistics.mean(rater_delta)
        shift = rater_mean - official_mean
        if rater_mean <= -tie and cis["rater"][1] < 0:
            decision = "gap_remains"
        elif rater_mean >= tie and cis["rater"][0] > 0:
            decision = "candidate_advantage"
        else:
            decision = "practical_tie_or_uncertain"
        output.append(
            {
                "aggregation_materially_shifts_comparison": shift >= material and cis["shift"][0] > 0,
                "bootstrap_iterations": iterations,
                "bootstrap_seed": seed,
                "candidate": comparison["candidate"]["label"],
                "comparison_id": comparison["comparison_id"],
                "decision": decision,
                "official_set_f1_delta": official_mean,
                "official_set_f1_delta_ci_high": cis["official"][1],
                "official_set_f1_delta_ci_low": cis["official"][0],
                "rater_example_losses": sum(int(value < 0) for value in rater_delta),
                "rater_example_ties": sum(int(value == 0) for value in rater_delta),
                "rater_example_wins": sum(int(value > 0) for value in rater_delta),
                "rater_set_f1_delta": rater_mean,
                "rater_set_f1_delta_ci_high": cis["rater"][1],
                "rater_set_f1_delta_ci_low": cis["rater"][0],
                "reference": comparison["reference"]["label"],
                "rater_vs_official_shift": shift,
                "rater_vs_official_shift_ci_high": cis["shift"][1],
                "rater_vs_official_shift_ci_low": cis["shift"][0],
                "rows": len(selected_rows),
            }
        )
    return output


def csv_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.12f}"
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def verify_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        observed = list(reader)
        if reader.fieldnames != fieldnames:
            raise RuntimeError(f"CSV schema differs: {path.name}")
    expected = [{key: csv_value(row.get(key)) for key in fieldnames} for row in rows]
    if observed != expected:
        raise RuntimeError(f"CSV content differs: {path.name}")
    return len(observed)


def normalize_json(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def render_report(
    structure: dict[str, Any],
    families: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> str:
    family_lines = [
        "| Condition | Runs | Official set-F1 | Clear-rater expected set-F1 | Any-rater exact |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in families:
        family_lines.append(
            "| {condition} | {run_count} | {official:.6f} | {rater:.6f} | {any_exact:.6f} |".format(
                condition=row["condition"],
                run_count=row["run_count"],
                official=row["official_set_f1_mean"],
                rater=row["clear_rater_expected_set_f1_mean"],
                any_exact=row["any_clear_rater_exact_mean"],
            )
        )
    comparison_lines = [
        "| Comparison (candidate - reference) | Official delta | Rater-aware delta | Relative shift | Decision |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in comparisons:
        comparison_lines.append(
            "| {comparison_id} | {official:+.6f} | {rater:+.6f} | {shift:+.6f} | {decision} |".format(
                comparison_id=row["comparison_id"],
                official=row["official_set_f1_delta"],
                rater=row["rater_set_f1_delta"],
                shift=row["rater_vs_official_shift"],
                decision=row["decision"],
            )
        )
    primary = comparisons[0]
    return "\n".join(
        [
            "# EXP-036: Dev Rater-aware Frozen-prediction Diagnostic",
            "",
            "## Boundary",
            "",
            "This validation-only diagnostic rescored seven frozen prediction files on the 174",
            "GoEmotions dev rows whose official target contains `neutral` plus another emotion.",
            "It performed no training, inference, checkpoint selection, or test access.",
            "",
            "## Annotation Integrity",
            "",
            f"- Rows joined and reproduced: {structure['rows']}; official aggregation mismatches: "
            f"{structure['official_threshold_reproduction_mismatches']}.",
            f"- Matched per-rater annotations: {structure['matched_annotation_rows']}.",
            f"- Aggregation-only rows: {structure['aggregation_only_rows']} "
            f"({structure['aggregation_only_rate']:.6f}).",
            f"- Rows with unclear annotations: {structure['any_unclear_rows']} "
            f"({structure['any_unclear_rate']:.6f}).",
            "",
            "## Frozen Predictions",
            "",
            *family_lines,
            "",
            "The clear-rater score is the expected set-F1 against a randomly selected annotator",
            "who did not mark the example unclear. It is not a replacement ground truth and is not",
            "comparable to full-dev Macro-F1.",
            "",
            "## Paired Comparisons",
            "",
            *comparison_lines,
            "",
            f"Primary classification: `{primary['decision']}`. Aggregation materially shifts the",
            f"primary comparison under the frozen rule: "
            f"`{str(primary['aggregation_materially_shifts_comparison']).lower()}`.",
            "",
            "## Limits",
            "",
            "- The analysis is restricted to a purposively defined 174-row label-conflict slice.",
            "- Annotator agreement is not semantic truth, and original raters saw only one comment.",
            "- Bootstrap intervals resample examples, not training seeds.",
            "- Official full-dev metrics remain the primary model-performance evidence.",
            "- The result is behavioral evidence and does not identify an internal model mechanism.",
            "",
            "Status: completed, pending independent artifact verification.",
            "",
        ]
    )


def verify_source_manifest(
    path: Path,
    config: dict[str, Any],
    records: list[dict[str, Any]],
    prediction_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    matched_counts = Counter(row["source_file"] for row in records)
    sources = [
        {
            "bytes": source["content_length"],
            "etag": source["etag"],
            "last_modified": source["last_modified"],
            "matched_annotation_rows": matched_counts[source["name"]],
            "md5_base64": source["md5_base64"],
            "name": source["name"],
            "raw_annotation_rows": source["raw_annotation_rows"],
            "sha256": source["sha256"],
            "url": source["url"],
        }
        for source in config["raw_sources"]
    ]
    expected = {
        "full_archive_transport": True,
        "nonmatching_raw_records_persisted": 0,
        "official_repository_revision": config["official_source"]["revision"],
        "prediction_files": prediction_manifest,
        "retained_annotation_rows": len(records),
        "retained_dev_rows": config["selection"]["expected_rows"],
        "simplified_test_accessed": False,
        "simplified_test_exists": False,
        "sources": sources,
    }
    if read_json(path) != expected:
        raise RuntimeError("Source manifest differs from frozen identities")
    return expected


def verify_artifacts(run: dict[str, Any]) -> int:
    for record in run["artifacts"]:
        path = resolve_project_path(record["path"])
        if artifact_record(path) != record:
            raise RuntimeError(f"Artifact identity differs: {record['path']}")
    return len(run["artifacts"])


def verify_privacy(run_dir: Path, selected: list[dict[str, Any]]) -> dict[str, Any]:
    public_names = [
        "REPORT.md",
        "aggregate-summary.json",
        "family-summary.csv",
        "pairwise-comparisons.csv",
        "per-example-scores.csv",
        "row-structure.csv",
        "run-metrics.csv",
        "source-manifest.json",
        "stdout.log",
    ]
    leaked_ids = 0
    for name in public_names:
        content = (run_dir / name).read_text(encoding="utf-8")
        leaked_ids += sum(int(row["comment_id"] in content) for row in selected)
    if leaked_ids:
        raise RuntimeError("Upstream comment ID leaked into public artifacts")
    return {
        "public_raw_text_fields": 0,
        "public_upstream_comment_id_matches": leaked_ids,
        "raw_rater_ids_persisted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    config_path = resolve_config_path(args.config)
    if sha256_file(config_path) != args.config_sha256:
        raise RuntimeError("Config SHA-256 does not match frozen command")
    config = read_json(config_path)
    verify_implementation(config)
    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    verification_path = run_dir / "verification.json"

    selected, all_gold = load_dev(config)
    private_path = run_dir / "private" / "matched-annotations.private.jsonl"
    records = load_private_records(private_path, selected, len(config["labels"]))
    structures, view, structure_summary = rebuild_rater_view(
        selected, records, len(config["labels"])
    )
    selected_rows = [row["source_dev_row"] for row in selected]
    predictions, prediction_manifest = load_predictions(config, all_gold, set(selected_rows))
    per_example, run_metrics, score_index = score_runs(config, selected, view, predictions)
    families = summarize_families(run_metrics)
    comparisons = compare_models(config, score_index, selected_rows)

    row_fields = [
        "source_dev_row",
        "example_hash",
        "gold_label_ids",
        "gold_cardinality",
        "rater_count",
        "clear_rater_count",
        "labeled_rater_count",
        "unclear_count",
        "same_rater_coselection_count",
        "aggregation_only",
        "derived_labels_match",
    ]
    per_example_fields = [
        "condition",
        "run_id",
        "seed",
        "source_dev_row",
        "example_hash",
        "gold_cardinality",
        "predicted_cardinality",
        "predicted_neutral_emotion",
        *PER_EXAMPLE_METRICS,
    ]
    run_fields = [
        "condition",
        "run_id",
        "seed",
        "rows",
        "empty_prediction_count",
        "neutral_emotion_prediction_count",
        "mean_predicted_cardinality",
        *PER_EXAMPLE_METRICS,
        "rater_minus_official_set_f1",
    ]
    family_fields = ["condition", "run_count", "seeds"]
    for metric in (
        "official_set_f1",
        "official_exact",
        "clear_rater_expected_set_f1",
        "clear_rater_expected_exact",
        "any_clear_rater_exact",
        "rater_minus_official_set_f1",
        "mean_predicted_cardinality",
    ):
        family_fields.extend([f"{metric}_mean", f"{metric}_std"])
    comparison_fields = [
        "comparison_id",
        "candidate",
        "reference",
        "rows",
        "bootstrap_iterations",
        "bootstrap_seed",
        "official_set_f1_delta",
        "official_set_f1_delta_ci_low",
        "official_set_f1_delta_ci_high",
        "rater_set_f1_delta",
        "rater_set_f1_delta_ci_low",
        "rater_set_f1_delta_ci_high",
        "rater_vs_official_shift",
        "rater_vs_official_shift_ci_low",
        "rater_vs_official_shift_ci_high",
        "rater_example_wins",
        "rater_example_ties",
        "rater_example_losses",
        "aggregation_materially_shifts_comparison",
        "decision",
    ]

    checked_rows = {
        "family_summary": verify_csv(run_dir / "family-summary.csv", families, family_fields),
        "pairwise_comparisons": verify_csv(
            run_dir / "pairwise-comparisons.csv", comparisons, comparison_fields
        ),
        "per_example_scores": verify_csv(
            run_dir / "per-example-scores.csv", per_example, per_example_fields
        ),
        "row_structure": verify_csv(run_dir / "row-structure.csv", structures, row_fields),
        "run_metrics": verify_csv(run_dir / "run-metrics.csv", run_metrics, run_fields),
    }

    aggregate = {
        "comparisons": comparisons,
        "family_summary": families,
        "metric_semantics": {
            "primary_diagnostic": "example-weighted expected set-F1 against a clear individual rater",
            "replacement_ground_truth": False,
            "selection_use_authorized": False,
        },
        "run_metrics": run_metrics,
        "structure": structure_summary,
        "test_accessed": False,
        "test_exists": False,
    }
    stored_aggregate = read_json(run_dir / "aggregate-summary.json")
    if stored_aggregate != normalize_json(aggregate):
        raise RuntimeError("Aggregate summary differs from independent recomputation")
    if (run_dir / "REPORT.md").read_text(encoding="utf-8") != render_report(
        structure_summary, families, comparisons
    ):
        raise RuntimeError("REPORT.md does not regenerate exactly")
    source_manifest = verify_source_manifest(
        run_dir / "source-manifest.json", config, records, prediction_manifest
    )
    privacy = verify_privacy(run_dir, selected)

    run = read_json(run_dir / "run.json")
    if (
        run["status"] != "CompletedAwaitingVerification"
        or run["accessed_splits"] != ["validation"]
        or run["training_performed"]
        or run["model_inference_performed"]
        or run["test_accessed"]
        or run["test_exists"]
        or run["result_summary"] != stored_aggregate
        or run["config"] != artifact_record(config_path)
    ):
        raise RuntimeError("run.json discipline or result differs")
    artifacts_checked = verify_artifacts(run)

    existing = read_json(verification_path) if args.check else None
    verified_at = existing["verified_at_utc"] if existing else datetime.now(timezone.utc).isoformat()
    verification = {
        "artifacts_checked": artifacts_checked,
        "bootstrap_comparisons_recomputed": len(comparisons),
        "config": artifact_record(config_path),
        "csv_rows_recomputed": checked_rows,
        "experiment_id": config["experiment_id"],
        "implementation_files_checked": len(config["implementation"]),
        "matched_annotation_rows_recomputed": len(records),
        "max_absolute_numeric_difference": 0.0,
        "prediction_files_recomputed": len(predictions),
        "privacy": privacy,
        "report_regenerated_exactly": True,
        "source_objects_checked": len(source_manifest["sources"]),
        "status": "Verified",
        "test_accessed": False,
        "test_absent": not resolve_project_path(config["selection"]["simplified_test_path"]).exists(),
        "verified_at_utc": verified_at,
        "verifier": artifact_record(Path(__file__).resolve()),
    }
    if args.check:
        if existing != verification:
            raise RuntimeError("Stored verification differs from independent recomputation")
    else:
        write_json(verification_path, verification)
    print(json.dumps({"experiment_id": config["experiment_id"], "status": "Verified"}, sort_keys=True))


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Validate EXP-017 annotations and produce public aggregate review artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import analyze_frozen_errors as analysis


DEFAULT_CONFIG = (
    analysis.SCRIPT_DIR / "configs" / "exp-017-frozen-error-analysis.json"
)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_annotations(
    manifest: list[dict[str, str]],
    annotations: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    forbidden_columns = {
        "text",
        "tweet",
        "content",
        "raw_text",
        "note",
        "notes",
        "rationale",
    }
    if forbidden_columns.intersection(manifest[0]) or forbidden_columns.intersection(
        annotations[0]
    ):
        raise ValueError("A public CSV contains a forbidden raw-text column")
    if len(manifest) != len(annotations):
        raise ValueError("Manifest and annotation row counts differ")

    manifest_identity = [
        (row["sample_rank"], row["role"], row["row_id"], row["gold_label"])
        for row in manifest
    ]
    annotation_identity = [
        (row["sample_rank"], row["role"], row["row_id"], row["gold_label"])
        for row in annotations
    ]
    if annotation_identity != manifest_identity:
        raise ValueError("Annotation identities or ordering differ from the manifest")

    allowed_flags = set(config["annotation"]["allowed_evidence_flags"])
    allowed_sources = set(config["annotation"]["allowed_primary_sources"])
    allowed_confidence = set(config["annotation"]["confidence_levels"])
    for row in annotations:
        flags = row["evidence_flags"].split("|") if row["evidence_flags"] else []
        if not flags or len(flags) != len(set(flags)):
            raise ValueError(f"Missing or duplicate flags for row {row['row_id']}")
        if not set(flags).issubset(allowed_flags):
            raise ValueError(f"Unknown evidence flag for row {row['row_id']}")
        if row["primary_possible_source"] not in allowed_sources:
            raise ValueError(f"Unknown primary source for row {row['row_id']}")
        if row["reviewer_confidence"] not in allowed_confidence:
            raise ValueError(f"Unknown confidence for row {row['row_id']}")
        has_minority_flag = "minority_class" in flags
        if has_minority_flag != (row["gold_label"] == "optimism"):
            raise ValueError(f"Minority-class flag mismatch for row {row['row_id']}")


def count_rows(
    annotations: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    denominator = len(annotations)

    def append_counts(
        dimension: str,
        group: str,
        counter: Counter[str],
        group_denominator: int,
    ) -> None:
        for value in sorted(counter):
            count = counter[value]
            output.append(
                {
                    "dimension": dimension,
                    "group": group,
                    "value": value,
                    "count": count,
                    "denominator": group_denominator,
                    "proportion": f"{count / group_denominator:.12f}",
                }
            )

    overall_flags = Counter(
        flag
        for row in annotations
        for flag in row["evidence_flags"].split("|")
    )
    overall_sources = Counter(row["primary_possible_source"] for row in annotations)
    overall_confidence = Counter(row["reviewer_confidence"] for row in annotations)
    roles = Counter(row["role"] for row in annotations)
    gold_labels = Counter(row["gold_label"] for row in annotations)
    append_counts("evidence_flag", "ALL", overall_flags, denominator)
    append_counts("primary_possible_source", "ALL", overall_sources, denominator)
    append_counts("reviewer_confidence", "ALL", overall_confidence, denominator)
    append_counts("role", "ALL", roles, denominator)
    append_counts("gold_label", "ALL", gold_labels, denominator)

    for role in sorted(roles):
        subset = [row for row in annotations if row["role"] == role]
        append_counts(
            "evidence_flag_by_role",
            role,
            Counter(
                flag
                for row in subset
                for flag in row["evidence_flags"].split("|")
            ),
            len(subset),
        )
        append_counts(
            "primary_source_by_role",
            role,
            Counter(row["primary_possible_source"] for row in subset),
            len(subset),
        )

    summary = {
        "annotation_count": denominator,
        "evidence_flag_counts": dict(sorted(overall_flags.items())),
        "gold_label_counts": dict(sorted(gold_labels.items())),
        "primary_possible_source_counts": dict(sorted(overall_sources.items())),
        "reviewer_confidence_counts": dict(sorted(overall_confidence.items())),
        "role_counts": dict(sorted(roles.items())),
    }
    return output, summary


def build_stable_error_overlaps(
    records: list[dict[str, Any]],
    condition_ids: list[str],
    label_names: list[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    short_names = {
        "exp-007-linear-svm": "exp007",
        "exp-011-generic-roberta": "exp011",
        "exp-014-generic-roberta-label-smoothing": "exp014",
        "exp-015-twitter-roberta-label-smoothing": "exp015",
    }
    for label in ["ALL", *label_names]:
        subset = (
            records if label == "ALL" else [r for r in records if r["gold_label"] == label]
        )
        patterns: Counter[tuple[bool, ...]] = Counter()
        for record in subset:
            pattern = tuple(
                record["conditions"][condition_id]["correct_count"] == 0
                for condition_id in condition_ids
            )
            patterns[pattern] += 1
        for pattern in sorted(patterns):
            count = patterns[pattern]
            row: dict[str, Any] = {
                "gold_label": label,
                "row_count": count,
                "stratum_count": len(subset),
                "rate": f"{count / len(subset):.12f}",
            }
            for condition_id, stable_wrong in zip(condition_ids, pattern):
                row[f"{short_names[condition_id]}_stable_wrong"] = int(stable_wrong)
            output.append(row)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    started = time.perf_counter()
    config_path = args.config.resolve()
    config = analysis.read_json(config_path)
    output_dir = analysis.project_path(config["output_dir"])
    manifest_path = output_dir / "sample_manifest.csv"
    annotations_path = output_dir / "manual_annotations.csv"
    targets = [
        output_dir / "qualitative_counts.csv",
        output_dir / "qualitative_summary.json",
        output_dir / "stable_error_overlaps.csv",
        output_dir / "manual_review.json",
    ]
    if any(path.exists() for path in targets):
        raise FileExistsError("A manual-review output already exists")

    manifest = load_csv(manifest_path)
    annotations = load_csv(annotations_path)
    validate_annotations(manifest, annotations, config)
    qualitative_counts, qualitative_summary = count_rows(annotations)

    source_run_path = analysis.verify_file(config["source_test_gate"]["run"])
    analysis.verify_file(config["source_test_gate"]["verification"])
    source_run = analysis.read_json(source_run_path)
    label_mapping = config["data"]["label_mapping"]
    label_names = [label_mapping[str(index)] for index in range(len(label_mapping))]
    condition_ids = [item["id"] for item in config["conditions"]]
    predictions: dict[str, list[dict[int, dict[str, Any]]]] = {}
    for condition in config["conditions"]:
        results = source_run["condition_results"][condition["id"]]
        predictions[condition["id"]] = analysis.load_prediction_rows(
            condition["id"], results, label_names
        )
    records = analysis.build_records(
        predictions, label_names, config["data"]["test_sample_count"]
    )
    overlaps = build_stable_error_overlaps(records, condition_ids, label_names)

    qualitative_counts_path = output_dir / "qualitative_counts.csv"
    analysis.write_csv(
        qualitative_counts_path,
        ["dimension", "group", "value", "count", "denominator", "proportion"],
        qualitative_counts,
    )
    qualitative_summary.update(
        {
            "experiment_id": config["experiment_id"],
            "interpretation": (
                "Purposive single-reviewer sample; counts describe only the "
                "frozen 42-case sample and are not full-test prevalence estimates."
            ),
            "reviewers": config["annotation"]["reviewers"],
        }
    )
    qualitative_summary_path = output_dir / "qualitative_summary.json"
    analysis.write_json(qualitative_summary_path, qualitative_summary)
    overlaps_path = output_dir / "stable_error_overlaps.csv"
    analysis.write_csv(
        overlaps_path,
        [
            "gold_label",
            "exp007_stable_wrong",
            "exp011_stable_wrong",
            "exp014_stable_wrong",
            "exp015_stable_wrong",
            "row_count",
            "stratum_count",
            "rate",
        ],
        overlaps,
    )

    review = {
        "artifacts": {
            "manual_annotations": analysis.artifact_record(annotations_path),
            "qualitative_counts": analysis.artifact_record(qualitative_counts_path),
            "qualitative_summary": analysis.artifact_record(
                qualitative_summary_path
            ),
            "stable_error_overlaps": analysis.artifact_record(overlaps_path),
        },
        "completed_at": datetime.now().astimezone().isoformat(),
        "config": {
            "path": str(config_path.relative_to(analysis.PROJECT_ROOT)),
            "sha256": analysis.sha256_file(config_path),
        },
        "experiment_id": config["experiment_id"],
        "limitations": [
            "One reviewer; no inter-rater reliability estimate.",
            "Purposive sample; qualitative proportions are not full-test prevalence.",
            "Possible context dependency cannot be verified from isolated TweetEval text.",
            "Annotations are possible explanations, not relabeled ground truth or causal mechanisms.",
        ],
        "manifest": analysis.artifact_record(manifest_path),
        "raw_text_in_tracked_outputs": False,
        "reviewer_count": config["annotation"]["reviewers"],
        "status": "manual_review_completed",
        "wall_time_seconds": time.perf_counter() - started,
    }
    analysis.write_json(output_dir / "manual_review.json", review)
    print(f"annotation_count={len(annotations)}")
    print("status=manual_review_completed")


if __name__ == "__main__":
    main()

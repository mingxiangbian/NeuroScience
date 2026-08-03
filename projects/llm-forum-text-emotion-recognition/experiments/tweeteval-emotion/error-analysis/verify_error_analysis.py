#!/usr/bin/env python3
"""Independently verify EXP-017 aggregates, sample selection, and privacy."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import analyze_frozen_errors as analysis
import summarize_review as review


DEFAULT_CONFIG = (
    analysis.SCRIPT_DIR / "configs" / "exp-017-frozen-error-analysis.json"
)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{key: str(value) for key, value in row.items()} for row in rows]


def assert_csv_equal(path: Path, expected: list[dict[str, Any]]) -> None:
    observed = load_csv(path)
    normalized = normalize_rows(expected)
    if observed != normalized:
        raise ValueError(f"Recomputed CSV differs: {path}")


def verify_artifact_records(
    artifact_records: dict[str, dict[str, Any]],
) -> int:
    checked = 0
    for name, artifact in artifact_records.items():
        path = analysis.project_path(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Missing artifact {name}: {path}")
        if path.stat().st_size != artifact["bytes"]:
            raise ValueError(f"Byte-size mismatch for {name}")
        if analysis.sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"Hash mismatch for {name}")
        checked += 1
    return checked


def verify_private_boundary(
    output_dir: Path,
    private_path: Path,
    selections: list[dict[str, Any]],
    test_text_path: Path,
) -> dict[str, Any]:
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(private_path)],
        cwd=analysis.REPO_ROOT,
        check=False,
    ).returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(private_path)],
        cwd=analysis.REPO_ROOT,
        check=False,
        capture_output=True,
    ).returncode == 0
    if not ignored or tracked:
        raise ValueError("Private selected text is not correctly gitignored")

    with test_text_path.open(encoding="utf-8") as handle:
        test_texts = [line.rstrip("\n") for line in handle]
    with private_path.open(encoding="utf-8") as handle:
        private_rows = [json.loads(line) for line in handle]
    expected_private = [
        {
            "gold_label": case["gold_label"],
            "role": case["role"],
            "row_id": case["row_id"],
            "sample_rank": case["sample_rank"],
            "text": test_texts[case["row_id"]],
        }
        for case in selections
    ]
    if private_rows != expected_private:
        raise ValueError("Private selected text differs from frozen selection")

    public_files = [
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.suffix in {".csv", ".json", ".md", ".log"}
    ]
    public_payload = "\n".join(
        path.read_text(encoding="utf-8") for path in public_files
    )
    leaked_rows = [
        row["row_id"]
        for row in private_rows
        if len(row["text"]) >= 8 and row["text"] in public_payload
    ]
    if leaked_rows:
        raise ValueError(f"Raw selected text leaked into public artifacts: {leaked_rows}")
    return {
        "private_file_gitignored": ignored,
        "private_file_tracked": tracked,
        "private_rows_verified": len(private_rows),
        "public_files_scanned": len(public_files),
        "raw_text_leak_count": len(leaked_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = analysis.read_json(config_path)
    output_dir = analysis.project_path(config["output_dir"])
    verification_path = output_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError("Verification output already exists")

    source_run_path = analysis.verify_file(config["source_test_gate"]["run"])
    source_verification_path = analysis.verify_file(
        config["source_test_gate"]["verification"]
    )
    test_labels_path = analysis.verify_file(config["data"]["test_labels"])
    test_text_path = analysis.verify_file(config["data"]["test_text"])
    source_run = analysis.read_json(source_run_path)
    source_verification = analysis.read_json(source_verification_path)
    if source_verification.get("status") != "Verified":
        raise ValueError("Pinned EXP-016 verification is not Verified")

    label_mapping = config["data"]["label_mapping"]
    label_names = [label_mapping[str(index)] for index in range(len(label_mapping))]
    condition_ids = [item["id"] for item in config["conditions"]]
    predictions: dict[str, list[dict[int, dict[str, Any]]]] = {}
    prediction_artifacts_checked = 0
    for condition in config["conditions"]:
        results = source_run["condition_results"][condition["id"]]
        if len(results) != condition["expected_runs"]:
            raise ValueError(f"Unexpected run count for {condition['id']}")
        predictions[condition["id"]] = analysis.load_prediction_rows(
            condition["id"], results, label_names
        )
        prediction_artifacts_checked += len(results)

    records = analysis.build_records(
        predictions, label_names, config["data"]["test_sample_count"]
    )
    with test_labels_path.open(encoding="utf-8") as handle:
        official_labels = [int(line.strip()) for line in handle if line.strip()]
    if len(official_labels) != len(records):
        raise ValueError("Official label row count differs")
    if any(
        record["row_id"] != row_id or record["gold_id"] != official_labels[row_id]
        for row_id, record in enumerate(records)
    ):
        raise ValueError("Prediction rows do not align with official labels")

    expected_stability = analysis.build_condition_stability(
        records, condition_ids, label_names
    )
    expected_confusions = analysis.build_seed_confusions(
        records, condition_ids, label_names
    )
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
    expected_transitions = analysis.build_pairwise_transitions(
        records, comparisons, label_names
    )
    selections, realized_sampling = analysis.select_cases(
        records, config, label_names
    )
    expected_manifest = analysis.manifest_rows(selections)

    assert_csv_equal(output_dir / "condition_stability.csv", expected_stability)
    assert_csv_equal(output_dir / "seed_confusions.csv", expected_confusions)
    assert_csv_equal(output_dir / "pairwise_transitions.csv", expected_transitions)
    assert_csv_equal(output_dir / "sample_manifest.csv", expected_manifest)

    aggregate_summary = analysis.read_json(output_dir / "aggregate_summary.json")
    if aggregate_summary["row_count"] != len(records):
        raise ValueError("Aggregate row count differs")
    if aggregate_summary["sampling"] != realized_sampling:
        raise ValueError("Realized sampling summary differs")
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
    if aggregate_summary["shared_error_rows"] != shared_error_count:
        raise ValueError("Shared-error count differs")

    run = analysis.read_json(output_dir / "run.json")
    run_artifacts_checked = verify_artifact_records(run["artifacts"])
    manifest = load_csv(output_dir / "sample_manifest.csv")
    annotations = load_csv(output_dir / "manual_annotations.csv")
    review.validate_annotations(manifest, annotations, config)
    qualitative_counts, qualitative_summary = review.count_rows(annotations)
    assert_csv_equal(output_dir / "qualitative_counts.csv", qualitative_counts)
    observed_qualitative_summary = analysis.read_json(
        output_dir / "qualitative_summary.json"
    )
    for key, value in qualitative_summary.items():
        if observed_qualitative_summary.get(key) != value:
            raise ValueError(f"Qualitative summary differs for {key}")

    expected_overlaps = review.build_stable_error_overlaps(
        records, condition_ids, label_names
    )
    assert_csv_equal(output_dir / "stable_error_overlaps.csv", expected_overlaps)
    manual_review = analysis.read_json(output_dir / "manual_review.json")
    manual_artifacts_checked = verify_artifact_records(manual_review["artifacts"])

    private_spec = run["artifacts"]["selected_text_private"]
    private_path = analysis.project_path(private_spec["path"])
    privacy = verify_private_boundary(
        output_dir, private_path, selections, test_text_path
    )

    report_path = output_dir / "REPORT.md"
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    report_text = report_path.read_text(encoding="utf-8")
    required_report_terms = [
        "1,421",
        "155",
        "Eighty-seven",
        "42",
        "Optimism",
        "single reviewer",
        "must not be reported as test-set prevalence",
    ]
    missing_terms = [term for term in required_report_terms if term not in report_text]
    if missing_terms:
        raise ValueError(f"Report is missing required findings: {missing_terms}")

    public_artifacts = {
        path.name: {
            "bytes": path.stat().st_size,
            "sha256": analysis.sha256_file(path),
        }
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "verification.json"
    }
    payload = {
        "artifact_records_checked": (
            run_artifacts_checked + manual_artifacts_checked
        ),
        "checks": {
            "aggregate_row_count": len(records),
            "annotation_rows": len(annotations),
            "deterministic_sample_rows": len(selections),
            "official_label_rows": len(official_labels),
            "prediction_artifacts": prediction_artifacts_checked,
            "prediction_rows": prediction_artifacts_checked * len(records),
            "shared_error_rows": shared_error_count,
        },
        "completed_at": datetime.now().astimezone().isoformat(),
        "experiment_id": config["experiment_id"],
        "privacy": privacy,
        "public_artifacts": public_artifacts,
        "status": "Verified",
        "verification_scope": [
            "Pinned source and data hashes",
            "Ten prediction artifacts and row-label alignment",
            "Full-split stability, confusion, transition, and overlap recomputation",
            "Deterministic preregistered sample membership",
            "Manual annotation identity and allowed schema",
            "Qualitative aggregate recomputation",
            "Recorded artifact hashes",
            "Gitignore and raw-text leakage boundary",
            "Required report findings and limitations",
        ],
    }
    analysis.write_json(verification_path, payload)
    print("status=Verified")
    print(f"prediction_rows={payload['checks']['prediction_rows']}")
    print(f"sample_rows={len(selections)}")
    print(f"annotation_rows={len(annotations)}")
    print(f"raw_text_leak_count={privacy['raw_text_leak_count']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Independently verify EXP-030 aggregates, sampling, review, and privacy."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import analyze_frozen_dev_errors as analysis
import summarize_review as review


DEFAULT_CONFIG = analysis.DEFAULT_CONFIG


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


def assert_json_equal(path: Path, expected: Any) -> None:
    observed = analysis.read_json(path)
    if observed != expected:
        raise ValueError(f"Recomputed JSON differs: {path}")


def verify_artifact_records(records: dict[str, dict[str, Any]]) -> int:
    checked = 0
    for name, artifact in records.items():
        path = analysis.project_path(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Missing artifact {name}: {path}")
        if path.stat().st_size != artifact["bytes"]:
            raise ValueError(f"Byte-size mismatch for {name}")
        if analysis.sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"Hash mismatch for {name}")
        checked += 1
    return checked


def rebuild_aggregate(
    config: dict[str, Any],
    records: list[dict[str, Any]],
    labels: list[str],
    support: dict[int, int],
    long_tail_ids: set[int],
    neutral_id: int,
    stability_rows: list[dict[str, Any]],
    error_mode_rows: list[dict[str, Any]],
    slice_rows: list[dict[str, Any]],
    per_label_summaries: dict[str, dict[str, Any]],
    transition_rows: list[dict[str, Any]],
    sampling_summary: dict[str, Any],
) -> dict[str, Any]:
    condition_ids = [condition["id"] for condition in config["conditions"]]
    condition_summary = {
        condition_id: analysis.summarize_condition(
            condition_id,
            stability_rows,
            error_mode_rows,
            slice_rows,
            per_label_summaries[condition_id],
        )
        for condition_id in condition_ids
    }
    transition_summary: dict[str, dict[str, int]] = {}
    for comparison_id in {row["comparison_id"] for row in transition_rows}:
        counts: Counter[str] = Counter()
        for row in transition_rows:
            if row["comparison_id"] == comparison_id:
                counts[row["transition"]] += int(row["row_count"])
        transition_summary[comparison_id] = dict(sorted(counts.items()))
    return {
        "condition_summary": condition_summary,
        "experiment_id": config["experiment_id"],
        "gold_cardinality_mean": statistics.fmean(
            len(record["gold_ids"]) for record in records
        ),
        "long_tail_labels": {
            labels[label_id]: support[label_id] for label_id in sorted(long_tail_ids)
        },
        "neutral_cooccurrence_rows": sum(
            neutral_id in record["gold_ids"] and len(record["gold_ids"]) > 1
            for record in records
        ),
        "row_count": len(records),
        "sampling": sampling_summary,
        "shared_stable_error_rows": sum(
            record["conditions"]["exp-020-bert"]["correct_count"] == 0
            and record["conditions"]["exp-025-frozen-qwen"]["correct_count"] == 0
            and record["conditions"]["exp-029-lora-qwen"]["correct_count"] == 0
            for record in records
        ),
        "split": "dev",
        "test_accessed": False,
        "transition_summary": transition_summary,
    }


def verify_private_boundary(
    output_dir: Path,
    private_path: Path,
    selections: list[dict[str, Any]],
    labels: list[str],
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

    with private_path.open(encoding="utf-8") as handle:
        private_rows = [json.loads(line) for line in handle]
    expected = []
    for sample_rank, selection in enumerate(selections, start=1):
        record = selection["record"]
        expected.append(
            {
                "gold_labels": analysis.label_string(record["gold_ids"], labels),
                "role": selection["role"],
                "row_number": record["row_number"],
                "sample_rank": sample_rank,
                "text": record["text"],
            }
        )
    if private_rows != expected:
        raise ValueError("Private selected text differs from deterministic selection")

    public_files = [
        path
        for path in output_dir.iterdir()
        if path.is_file() and path.suffix in {".csv", ".json", ".md", ".log"}
    ]
    public_payload = "\n".join(path.read_text(encoding="utf-8") for path in public_files)
    leaked_rows = [
        row["row_number"]
        for row in private_rows
        if len(row["text"]) >= 8 and row["text"] in public_payload
    ]
    if leaked_rows:
        raise ValueError(f"Raw selected text leaked into public artifacts: {leaked_rows}")

    forbidden_headers = {
        "text",
        "comment",
        "comment_id",
        "content",
        "raw_text",
        "note",
        "notes",
        "rationale",
    }
    scanned_csvs = 0
    for path in output_dir.glob("*.csv"):
        with path.open(encoding="utf-8", newline="") as handle:
            fields = set(csv.DictReader(handle).fieldnames or [])
        if fields & forbidden_headers:
            raise ValueError(f"Forbidden public CSV column in {path}")
        scanned_csvs += 1
    return {
        "private_file_gitignored": ignored,
        "private_file_tracked": tracked,
        "private_rows_verified": len(private_rows),
        "public_csvs_scanned": scanned_csvs,
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
    test_path = analysis.project_path(config["data"]["test_path"])
    if test_path.exists():
        raise ValueError("GoEmotions test file unexpectedly exists")

    protocol_path = analysis.project_path(config["protocol"]["path"])
    if not protocol_path.is_file():
        raise FileNotFoundError(protocol_path)
    source_verifications = analysis.validate_sources(config)
    labels_path = analysis.verify_file(config["data"]["labels"])
    dev_path = analysis.verify_file(config["data"]["dev"])
    labels = analysis.load_labels(labels_path, config["data"]["labels"]["count"])
    dev_rows = analysis.load_dev(dev_path, labels, config["data"]["dev"]["rows"])
    support = Counter(label_id for row in dev_rows for label_id in row["gold_ids"])
    long_tail_ids = {
        label_id
        for label_id, count in support.items()
        if count < config["sampling"]["long_tail_support_below"]
    }
    neutral_id = labels.index("neutral")

    predictions: dict[str, list[dict[int, dict[str, Any]]]] = {}
    prediction_files_checked = 0
    for condition in config["conditions"]:
        predictions[condition["id"]] = [
            analysis.load_prediction_run(spec, labels, config["data"]["dev"]["rows"])
            for spec in condition["runs"]
        ]
        prediction_files_checked += len(condition["runs"])
    records = analysis.build_records(dev_rows, predictions)
    condition_ids = [condition["id"] for condition in config["conditions"]]

    stability_rows = analysis.build_condition_stability(records, condition_ids, labels)
    error_mode_rows = analysis.build_error_modes(records, config["conditions"])
    slice_rows = analysis.build_slice_metrics(
        records, config["conditions"], neutral_id, long_tail_ids
    )
    per_label_rows, per_label_summaries = analysis.build_per_label_metrics(
        records,
        config["conditions"],
        labels,
        config["official_reference"]["per_label_f1"],
    )
    pair_rows = analysis.build_missed_spurious_pairs(records, config["conditions"], labels)
    transition_rows = analysis.build_pairwise_transitions(
        records,
        [
            ("bert_to_lora", "exp-020-bert", "exp-029-lora-qwen"),
            ("frozen_qwen_to_lora", "exp-025-frozen-qwen", "exp-029-lora-qwen"),
        ],
    )
    agreement_rows = analysis.build_seed_agreement(records, config["conditions"])
    selections, sampling_summary = analysis.select_cases(
        records, config, labels, support, long_tail_ids, neutral_id
    )
    manifest_rows = analysis.manifest_rows(selections, labels, support)

    expected_csvs = {
        "condition_stability.csv": stability_rows,
        "error_modes.csv": error_mode_rows,
        "slice_metrics.csv": slice_rows,
        "per_label_metrics.csv": per_label_rows,
        "missed_spurious_pairs.csv": pair_rows,
        "pairwise_transitions.csv": transition_rows,
        "seed_agreement.csv": agreement_rows,
        "sample_manifest.csv": manifest_rows,
    }
    for filename, expected in expected_csvs.items():
        assert_csv_equal(output_dir / filename, expected)

    expected_aggregate = rebuild_aggregate(
        config,
        records,
        labels,
        support,
        long_tail_ids,
        neutral_id,
        stability_rows,
        error_mode_rows,
        slice_rows,
        per_label_summaries,
        transition_rows,
        sampling_summary,
    )
    assert_json_equal(output_dir / "aggregate_summary.json", expected_aggregate)
    expected_official = {
        **config["official_reference"],
        "local_exp020_dev_macro_f1_mean": expected_aggregate["condition_summary"][
            "exp-020-bert"
        ]["macro_f1_mean"],
        "local_exp020_dev_macro_f1_sample_std": expected_aggregate["condition_summary"][
            "exp-020-bert"
        ]["macro_f1_sample_std"],
        "local_dev_minus_official_test_macro_f1_reference": expected_aggregate[
            "condition_summary"
        ]["exp-020-bert"]["macro_f1_mean"]
        - config["official_reference"]["test_macro_f1"],
        "official_validation_comparison_available": False,
    }
    assert_json_equal(output_dir / "official_reference.json", expected_official)

    manifest = load_csv(output_dir / "sample_manifest.csv")
    annotations = load_csv(output_dir / "manual_annotations.csv")
    review.validate_annotations(manifest, annotations, config, labels, support)
    qualitative_rows, qualitative_summary = review.count_annotations(annotations)
    assert_csv_equal(output_dir / "qualitative_counts.csv", qualitative_rows)
    assert_json_equal(output_dir / "qualitative_summary.json", qualitative_summary)

    expected_report = review.render_report(
        expected_aggregate,
        expected_official,
        load_csv(output_dir / "slice_metrics.csv"),
        load_csv(output_dir / "per_label_metrics.csv"),
        load_csv(output_dir / "missed_spurious_pairs.csv"),
        load_csv(output_dir / "pairwise_transitions.csv"),
        qualitative_summary,
    )
    if (output_dir / "REPORT.md").read_text(encoding="utf-8") != expected_report:
        raise ValueError("REPORT.md differs from independently regenerated report")

    private_path = output_dir / "private" / "selected_text.private.jsonl"
    privacy = verify_private_boundary(output_dir, private_path, selections, labels)

    analysis_manifest = analysis.read_json(output_dir / "analysis_manifest.json")
    if analysis_manifest.get("status") != "AwaitingManualReview":
        raise ValueError("Unexpected analysis manifest status")
    if analysis_manifest["config"] != analysis.artifact_record(config_path):
        raise ValueError("Analysis manifest config record differs")
    if analysis_manifest["protocol"] != analysis.artifact_record(protocol_path):
        raise ValueError("Analysis manifest protocol record differs")
    if analysis_manifest["source_verifications"] != source_verifications:
        raise ValueError("Analysis manifest source verification records differ")
    for name, artifact in analysis_manifest["artifacts"].items():
        if name == "manual_annotations.csv":
            continue
        verify_artifact_records({name: artifact})

    manual_review = analysis.read_json(output_dir / "manual_review.json")
    if manual_review.get("status") != "Completed":
        raise ValueError("Manual review did not complete")
    if manual_review["qualitative_summary"] != qualitative_summary:
        raise ValueError("Manual review summary differs")
    manual_artifacts_checked = verify_artifact_records(manual_review["artifacts"])

    run = analysis.read_json(output_dir / "run.json")
    if run.get("status") != "CompletedAwaitingVerification":
        raise ValueError("Run is not ready for verification")
    if run.get("test_split_accessed") or run.get("accessed_splits") != ["dev"]:
        raise ValueError("Run split discipline differs")
    if run.get("reviewed_rows") != len(annotations):
        raise ValueError("Run reviewed-row count differs")
    public_artifacts_checked = verify_artifact_records(run["artifacts"])
    if run["privacy"]["private_selected_text"] != analysis.artifact_record(private_path):
        raise ValueError("Run private-text record differs")
    if run["privacy"]["public_raw_text"] or run["privacy"]["public_upstream_comment_ids"]:
        raise ValueError("Run privacy declaration differs")

    verification = {
        "analysis_rows": len(records),
        "annotation_rows": len(annotations),
        "artifacts": {
            "report": analysis.artifact_record(output_dir / "REPORT.md"),
            "run": analysis.artifact_record(output_dir / "run.json"),
        },
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": analysis.artifact_record(config_path),
        "experiment_id": config["experiment_id"],
        "manual_artifacts_checked": manual_artifacts_checked,
        "max_absolute_numeric_difference": 0.0,
        "prediction_files_checked": prediction_files_checked,
        "privacy": privacy,
        "protocol": analysis.artifact_record(protocol_path),
        "public_artifacts_checked": public_artifacts_checked,
        "recomputed_csvs": sorted(expected_csvs),
        "recomputed_jsons": [
            "aggregate_summary.json",
            "official_reference.json",
            "qualitative_summary.json",
        ],
        "report_regenerated_exactly": True,
        "sample_selection_deterministic": True,
        "source_verifications": source_verifications,
        "split": "dev",
        "status": "Verified",
        "test_absent": not test_path.exists(),
        "test_accessed": False,
        "verifier": analysis.artifact_record(Path(__file__).resolve()),
    }
    analysis.write_json(verification_path, verification)
    print(
        json.dumps(
            {
                "experiment_id": config["experiment_id"],
                "prediction_files_checked": prediction_files_checked,
                "status": verification["status"],
                "test_absent": verification["test_absent"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

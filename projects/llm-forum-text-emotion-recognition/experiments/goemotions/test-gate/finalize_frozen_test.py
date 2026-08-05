#!/usr/bin/env python3
"""Aggregate all completed EXP-038 test units without selecting on test."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import statistics
from typing import Any

from test_gate_common import (
    artifact,
    load_config,
    read_json,
    resolve_project_path,
    write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-038-frozen-test.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256", required=True)
    return parser.parse_args()


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)) if len(values) > 1 else 0.0,
        "values": [float(value) for value in values],
    }


def main() -> None:
    args = parse_args()
    config, config_sha256 = load_config(args.config.resolve(), args.config_sha256)
    output_root = resolve_project_path(config["output_dir"])
    run_path = output_root / "run.json"
    if run_path.exists():
        raise FileExistsError("EXP-038 final run already exists")
    for worker_name in ("classical-bert-worker.json", "qwen-worker.json"):
        worker = read_json(output_root / worker_name)
        if worker.get("status") != "Completed; pending independent verification":
            raise ValueError(f"Incomplete worker: {worker_name}")

    unit_rows: list[dict[str, Any]] = []
    unit_metrics: dict[str, dict[str, Any]] = {}
    for unit in config["units"]:
        unit_dir = output_root / unit["id"]
        unit_run = read_json(unit_dir / "run.json")
        metrics = read_json(unit_dir / "metrics.json")
        if unit_run.get("status") != "Completed; pending independent verification":
            raise ValueError(f"Incomplete test unit: {unit['id']}")
        if unit_run.get("config_sha256") != config_sha256:
            raise ValueError(f"Config mismatch for test unit: {unit['id']}")
        unit_metrics[unit["id"]] = metrics
        unit_rows.append(
            {
                "family": unit["family"],
                "historical_ontology_alignment": unit["historical_ontology_alignment"],
                "macro_f1": metrics["macro"]["f1"],
                "macro_precision": metrics["macro"]["precision"],
                "macro_recall": metrics["macro"]["recall"],
                "micro_f1": metrics["micro"]["f1"],
                "seed": "" if unit.get("seed") is None else unit["seed"],
                "subset_accuracy": metrics["subset_accuracy"],
                "unit_id": unit["id"],
                "validation_macro_f1": unit["validation_macro_f1"],
                "weighted_f1": metrics["weighted"]["f1"],
            }
        )

    with (output_root / "unit-results.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(unit_rows[0]))
        writer.writeheader()
        writer.writerows(unit_rows)

    aggregate: dict[str, Any] = {}
    for group in config["report_groups"]:
        rows = [unit_metrics[unit_id] for unit_id in group["unit_ids"]]
        aggregate[group["id"]] = {
            "family": group["family"],
            "historical_ontology_alignment": group["historical_ontology_alignment"],
            "macro_f1": summarize([row["macro"]["f1"] for row in rows]),
            "macro_precision": summarize([row["macro"]["precision"] for row in rows]),
            "macro_recall": summarize([row["macro"]["recall"] for row in rows]),
            "micro_f1": summarize([row["micro"]["f1"] for row in rows]),
            "samples_f1": summarize([row["samples"]["f1"] for row in rows]),
            "subset_accuracy": summarize([row["subset_accuracy"] for row in rows]),
            "unit_ids": group["unit_ids"],
            "weighted_f1": summarize([row["weighted"]["f1"] for row in rows]),
        }
    ranking = sorted(
        (
            {"group_id": group_id, "test_macro_f1_mean": values["macro_f1"]["mean"]}
            for group_id, values in aggregate.items()
        ),
        key=lambda row: row["test_macro_f1_mean"],
        reverse=True,
    )
    comparisons = {
        "exp020_minus_official_paper_bert": aggregate["exp020-bert"]["macro_f1"]["mean"]
        - float(config["external_reference"]["paper_bert_test_macro_f1"]),
        "exp029_minus_exp020": aggregate["exp029-qwen-lora-legacy"]["macro_f1"]["mean"]
        - aggregate["exp020-bert"]["macro_f1"]["mean"],
        "exp033_minus_exp020": aggregate["exp033-qwen-target-aligned"]["macro_f1"]["mean"]
        - aggregate["exp020-bert"]["macro_f1"]["mean"],
        "exp033_minus_exp029_seed42_descriptive": aggregate[
            "exp033-qwen-target-aligned"
        ]["macro_f1"]["mean"]
        - unit_metrics["exp029-qwen-seed42"]["macro"]["f1"],
    }
    write_json(
        output_root / "aggregate-metrics.json",
        {
            "comparisons": comparisons,
            "conditions": aggregate,
            "experiment_id": "EXP-038",
            "ranking": ranking,
        },
    )
    with (output_root / "condition-summary.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        fields = [
            "condition",
            "family",
            "ontology_alignment",
            "seed_count",
            "macro_f1_mean",
            "macro_f1_sample_std",
            "macro_precision_mean",
            "macro_recall_mean",
            "micro_f1_mean",
            "weighted_f1_mean",
            "samples_f1_mean",
            "subset_accuracy_mean",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for group_id, values in aggregate.items():
            writer.writerow(
                {
                    "condition": group_id,
                    "family": values["family"],
                    "ontology_alignment": values["historical_ontology_alignment"],
                    "seed_count": values["macro_f1"]["count"],
                    "macro_f1_mean": format(values["macro_f1"]["mean"], ".17g"),
                    "macro_f1_sample_std": format(
                        values["macro_f1"]["sample_std"], ".17g"
                    ),
                    "macro_precision_mean": format(
                        values["macro_precision"]["mean"], ".17g"
                    ),
                    "macro_recall_mean": format(
                        values["macro_recall"]["mean"], ".17g"
                    ),
                    "micro_f1_mean": format(values["micro_f1"]["mean"], ".17g"),
                    "weighted_f1_mean": format(
                        values["weighted_f1"]["mean"], ".17g"
                    ),
                    "samples_f1_mean": format(
                        values["samples_f1"]["mean"], ".17g"
                    ),
                    "subset_accuracy_mean": format(
                        values["subset_accuracy"]["mean"], ".17g"
                    ),
                }
            )

    generated = {
        path.relative_to(output_root).as_posix(): artifact(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path.name not in {"run.json", "verification.json"}
    }
    write_json(
        run_path,
        {
            "accessed_splits": ["test"],
            "artifacts": generated,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "config": artifact(args.config.resolve()),
            "config_sha256": config_sha256,
            "experiment_id": "EXP-038",
            "external_reference": config["external_reference"],
            "model_selection_after_test": False,
            "post_test_tuning": False,
            "stage": "formal-frozen-test-gate",
            "status": "Completed; pending independent verification",
            "test_rows_accessed": 5427,
            "test_split_accessed": True,
            "tier": "Major",
        },
    )
    print("EXP-038 aggregation completed; independent verification is required")


if __name__ == "__main__":
    main()

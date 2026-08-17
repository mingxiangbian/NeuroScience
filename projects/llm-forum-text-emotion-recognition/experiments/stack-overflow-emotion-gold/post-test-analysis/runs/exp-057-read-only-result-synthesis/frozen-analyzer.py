#!/usr/bin/env python3
"""Build thesis tables from frozen public Stack Overflow aggregates only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[5]
FAMILIES = ("m1", "m2", "m3", "m4")
SEEDS = (42, 43, 44)
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
DISPLAY_NAMES = {
    "m1": "RoBERTa encoder",
    "m2": "Frozen Qwen + linear head",
    "m3": "Qwen Classification LoRA",
    "m4": "Qwen Generative LoRA",
}
METRICS = (
    "macro_f1",
    "five_label_macro_f1_without_surprise",
    "micro_f1",
    "weighted_f1",
    "subset_accuracy",
    "hamming_loss",
    "macro_precision",
    "macro_recall",
    "empty_prediction_rate",
    "predicted_label_cardinality_mean",
)
EXPECTED_CONTRASTS = ("m2-m1", "m3-m1", "m3-m2", "m4-m1", "m4-m3")
EXPECTED_CONTRACT_SHA256 = (
    "bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966"
)
EXPECTED_RESULTS_SHA256 = (
    "d7b966ead7105b819db946c970e3f90b6b25514eac8e8e0b71c4ab3a69928cdd"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    return parser.parse_args()


def resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mean_std(values: Iterable[float]) -> dict[str, Any]:
    materialized = [float(value) for value in values]
    if not materialized:
        raise ValueError("mean_std requires at least one value")
    return {
        "mean": statistics.fmean(materialized),
        "sample_std": statistics.stdev(materialized) if len(materialized) > 1 else 0.0,
        "n": len(materialized),
        "values": materialized,
    }


def source_record(config: dict[str, Any], name: str) -> dict[str, Any]:
    return config["sources"][name]


def verify_record(record: dict[str, Any]) -> Path:
    path_text = str(record["path"])
    lowered = path_text.lower()
    forbidden = ("derived-private", "/private/", ".npz", ".safetensors")
    if any(token in lowered for token in forbidden):
        raise RuntimeError(f"Forbidden source path: {path_text}")
    path = resolve(path_text)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise RuntimeError(f"Byte-size mismatch: {path}")
    if sha256_file(path) != record["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch: {path}")
    return path


def validation_metric_node(payload: dict[str, Any], family: str) -> dict[str, Any]:
    if family in {"m1", "m2", "m3"}:
        return payload["aggregate"]["metrics"]["shared_threshold"]
    return payload["metrics"]


def summary_value(node: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = node.get(key)
    if not isinstance(value, dict) or "mean" not in value:
        return None
    return {
        "mean": float(value["mean"]),
        "sample_std": float(value.get("sample_std", 0.0)),
        "n": int(value.get("n", len(value.get("values", value.get("values_by_seed", {}))))),
    }


def build_validation_rows(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in FAMILIES:
        payload = payloads[family]
        node = validation_metric_node(payload, family)
        if family == "m4":
            node = dict(node)
            node["empty_prediction_rate"] = payload["generation"]["empty_prediction_rate"]
            node["predicted_label_cardinality_mean"] = payload["generation"][
                "predicted_label_cardinality_mean"
            ]
        row: dict[str, Any] = {"family": family, "display_name": DISPLAY_NAMES[family]}
        for metric in METRICS:
            summary = summary_value(node, metric)
            row[f"{metric}_mean"] = "" if summary is None else summary["mean"]
            row[f"{metric}_sample_std"] = "" if summary is None else summary["sample_std"]
        rows.append(row)
    return rows


def build_test_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in FAMILIES:
        unit_ids = [f"{family}-seed-{seed}" for seed in SEEDS]
        row: dict[str, Any] = {"family": family, "display_name": DISPLAY_NAMES[family]}
        for metric in METRICS:
            values = [float(results["unit_results"][unit_id]["metrics"][metric]) for unit_id in unit_ids]
            recomputed = mean_std(values)
            frozen = results["family_results"][family]["metrics"][metric]
            if not math.isclose(recomputed["mean"], float(frozen["mean"]), abs_tol=1e-12):
                raise RuntimeError(f"Frozen mean mismatch: {family} {metric}")
            if not math.isclose(
                recomputed["sample_std"], float(frozen["sample_std"]), abs_tol=1e-12
            ):
                raise RuntimeError(f"Frozen sample SD mismatch: {family} {metric}")
            row[f"{metric}_mean"] = recomputed["mean"]
            row[f"{metric}_sample_std"] = recomputed["sample_std"]
        if family == "m4":
            parser = mean_std(
                results["unit_results"][unit_id]["parser_valid_rate"] for unit_id in unit_ids
            )
            row["parser_valid_rate_mean"] = parser["mean"]
            row["parser_valid_rate_sample_std"] = parser["sample_std"]
        else:
            row["parser_valid_rate_mean"] = ""
            row["parser_valid_rate_sample_std"] = ""
        rows.append(row)
    return rows


def build_per_label_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in FAMILIES:
        for label in LABELS:
            records = [
                results["unit_results"][f"{family}-seed-{seed}"]["metrics"]["per_label"][label]
                for seed in SEEDS
            ]
            support = {int(record["support"]) for record in records}
            if len(support) != 1:
                raise RuntimeError(f"Gold support changed across seeds: {family} {label}")
            f1 = mean_std(record["f1"] for record in records)
            precision = mean_std(record["precision"] for record in records)
            recall = mean_std(record["recall"] for record in records)
            predicted_support = mean_std(record["predicted_support"] for record in records)
            frozen = results["family_results"][family]["per_label_f1"][label]
            if not math.isclose(f1["mean"], float(frozen["mean"]), abs_tol=1e-12):
                raise RuntimeError(f"Frozen per-label mean mismatch: {family} {label}")
            rows.append(
                {
                    "family": family,
                    "display_name": DISPLAY_NAMES[family],
                    "label": label,
                    "gold_support": next(iter(support)),
                    "f1_mean": f1["mean"],
                    "f1_sample_std": f1["sample_std"],
                    "precision_mean": precision["mean"],
                    "precision_sample_std": precision["sample_std"],
                    "recall_mean": recall["mean"],
                    "recall_sample_std": recall["sample_std"],
                    "predicted_support_mean": predicted_support["mean"],
                    "predicted_support_sample_std": predicted_support["sample_std"],
                }
            )
    return rows


def build_contrast_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    if tuple(results["paired_contrasts"].keys()) != EXPECTED_CONTRASTS:
        raise RuntimeError("Unexpected contrast scope or order")
    rows: list[dict[str, Any]] = []
    for contrast in EXPECTED_CONTRASTS:
        bootstrap = results["paired_contrasts"][contrast]["component_bootstrap"]
        six = bootstrap["macro_f1"]
        five = bootstrap["five_label_macro_f1_without_surprise"]
        rows.append(
            {
                "contrast": contrast,
                "orientation": bootstrap["orientation"],
                "unit": bootstrap["unit"],
                "components": int(bootstrap["components"]),
                "replicates": int(bootstrap["replicates"]),
                "macro_f1_delta": float(six["point"]),
                "macro_f1_ci95_lower": float(six["lower"]),
                "macro_f1_ci95_upper": float(six["upper"]),
                "five_label_delta": float(five["point"]),
                "five_label_ci95_lower": float(five["lower"]),
                "five_label_ci95_upper": float(five["upper"]),
            }
        )
    return rows


def truncated_rows(resource: dict[str, Any]) -> int:
    if "truncated_rows" in resource:
        return int(resource["truncated_rows"])
    tokenization = resource.get("tokenization", {})
    return int(tokenization.get("truncated_rows", 0))


def build_resource_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in FAMILIES:
        units = [results["unit_results"][f"{family}-seed-{seed}"] for seed in SEEDS]
        resources = [unit["resource"] for unit in units]
        backends = {resource["backend"] for resource in resources}
        if len(backends) != 1:
            raise RuntimeError(f"Backend changed across seeds: {family}")
        wall_values = [resource["wall_seconds"] for resource in resources if "wall_seconds" in resource]
        peak_values = [resource["peak_memory_gb"] for resource in resources if "peak_memory_gb" in resource]
        head_values = [resource["head_seconds"] for resource in resources if "head_seconds" in resource]
        shared_values = [
            resource["shared_feature_seconds"]
            for resource in resources
            if "shared_feature_seconds" in resource
        ]
        parser_values = [
            unit["parser_valid_rate"] for unit in units if "parser_valid_rate" in unit
        ]
        rows.append(
            {
                "family": family,
                "display_name": DISPLAY_NAMES[family],
                "backend": next(iter(backends)),
                "mean_per_seed_wall_seconds": "" if not wall_values else statistics.fmean(wall_values),
                "shared_feature_seconds": "" if not shared_values else max(shared_values),
                "mean_head_seconds": "" if not head_values else statistics.fmean(head_values),
                "peak_memory_gb_max": "" if not peak_values else max(peak_values),
                "parser_valid_rate_mean": "" if not parser_values else statistics.fmean(parser_values),
                "truncated_rows_total": sum(truncated_rows(resource) for resource in resources),
                "api_cost_usd": 0,
            }
        )
    return rows


def by_family(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["family"]): row for row in rows}


def build_claims(contrasts: list[dict[str, Any]]) -> list[dict[str, str]]:
    indexed = {row["contrast"]: row for row in contrasts}
    m3_m2 = indexed["m3-m2"]
    m3_m1 = indexed["m3-m1"]
    m4_m3 = indexed["m4-m3"]
    return [
        {
            "status": "supported",
            "claim": "M3 outperforms M2 on six-label and five-label test Macro-F1.",
            "basis": "Both frozen component-bootstrap intervals are above zero.",
        },
        {
            "status": "not-established",
            "claim": "M3 robustly outperforms M1.",
            "basis": "The six-label and five-label M3-M1 intervals both cross zero.",
        },
        {
            "status": "supported-with-boundary",
            "claim": "M4 is lower than M3 on the registered six-label primary metric.",
            "basis": "The six-label M4-M3 interval is below zero; the five-label interval crosses zero.",
        },
        {
            "status": "not-supported",
            "claim": "Generation itself caused the M3-M4 difference.",
            "basis": "M3 and M4 differ in objective, output path, parser, and head, so formulation is bundled.",
        },
        {
            "status": "not-supported",
            "claim": "The results reveal an internal or human emotion mechanism.",
            "basis": "The evidence is held-out behavioral performance only.",
        },
    ]


def fmt(value: Any) -> str:
    return "" if value == "" else f"{float(value):.6f}"


def pm(row: dict[str, Any], metric: str) -> str:
    return f"{fmt(row[f'{metric}_mean'])} +/- {fmt(row[f'{metric}_sample_std'])}"


def render_markdown(
    validation_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    per_label_rows: list[dict[str, Any]],
    contrast_rows: list[dict[str, Any]],
    resource_rows: list[dict[str, Any]],
    claims: list[dict[str, str]],
) -> str:
    lines = [
        "# EXP-057 Thesis Tables",
        "",
        "> Read-only synthesis of verified public aggregates. No training, inference,",
        "> threshold selection, private prediction access, or test-label access occurred.",
        "",
        "## Validation",
        "",
        "| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Subset accuracy |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in validation_rows:
        lines.append(
            f"| {row['family'].upper()} {row['display_name']} | {pm(row, 'macro_f1')} | "
            f"{pm(row, 'five_label_macro_f1_without_surprise')} | {pm(row, 'micro_f1')} | "
            f"{pm(row, 'subset_accuracy')} |"
        )
    lines.extend(
        [
            "",
            "## Held-Out Test",
            "",
            "| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Weighted-F1 | Subset accuracy | Hamming loss |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in test_rows:
        lines.append(
            f"| {row['family'].upper()} {row['display_name']} | {pm(row, 'macro_f1')} | "
            f"{pm(row, 'five_label_macro_f1_without_surprise')} | {pm(row, 'micro_f1')} | "
            f"{pm(row, 'weighted_f1')} | {pm(row, 'subset_accuracy')} | {pm(row, 'hamming_loss')} |"
        )
    lines.extend(
        [
            "",
            "## Frozen Test Contrasts",
            "",
            "| Contrast | Macro-F1 delta | 95% CI | Five-label delta | 95% CI |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in contrast_rows:
        lines.append(
            f"| {row['contrast'].upper()} | {fmt(row['macro_f1_delta'])} | "
            f"[{fmt(row['macro_f1_ci95_lower'])}, {fmt(row['macro_f1_ci95_upper'])}] | "
            f"{fmt(row['five_label_delta'])} | "
            f"[{fmt(row['five_label_ci95_lower'])}, {fmt(row['five_label_ci95_upper'])}] |"
        )
    lines.extend(
        [
            "",
            "## Test Per-Label F1",
            "",
            "| Label (support) | M1 | M2 | M3 | M4 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    per_label_index = {(row["family"], row["label"]): row for row in per_label_rows}
    for label in LABELS:
        support = per_label_index[("m1", label)]["gold_support"]
        values = [
            f"{fmt(per_label_index[(family, label)]['f1_mean'])} +/- "
            f"{fmt(per_label_index[(family, label)]['f1_sample_std'])}"
            for family in FAMILIES
        ]
        lines.append(f"| {label} ({support}) | " + " | ".join(values) + " |")
    lines.extend(
        [
            "",
            "## Resource Paths",
            "",
            "| Family | Backend | Mean wall/seed (s) | Shared feature (s) | Peak memory (GB) | Parser-valid |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in resource_rows:
        lines.append(
            f"| {row['family'].upper()} | {row['backend']} | {fmt(row['mean_per_seed_wall_seconds'])} | "
            f"{fmt(row['shared_feature_seconds'])} | {fmt(row['peak_memory_gb_max'])} | "
            f"{fmt(row['parser_valid_rate_mean'])} |"
        )
    lines.extend(["", "## Claim Boundary", ""])
    for claim in claims:
        lines.append(f"- **{claim['status']}**: {claim['claim']} {claim['basis']}")
    lines.extend(
        [
            "",
            "`surprise` has only seven held-out positives. Six-label claims must therefore be",
            "reported together with the five-label sensitivity result.",
            "",
        ]
    )
    return "\n".join(lines)


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    args = parse_args()
    config_path = resolve(args.config)
    config = load_json(config_path)
    if config.get("experiment_id") != "EXP-057":
        raise RuntimeError("Unexpected experiment ID")
    for key in (
        "training_authorized",
        "inference_authorized",
        "private_prediction_access_authorized",
        "test_label_access_authorized",
        "selection_or_tuning_authorized",
    ):
        if config.get(key) is not False:
            raise RuntimeError(f"Read-only boundary is not frozen: {key}")

    source_paths = {name: verify_record(record) for name, record in config["sources"].items()}
    for name in config["verification_sources"]:
        verification = load_json(source_paths[name])
        if verification.get("status") != "Passed" or verification.get("failed_checks", []):
            raise RuntimeError(f"Upstream verification failed: {name}")

    results = load_json(source_paths["exp056_results"])
    if results["contract_sha256"] != EXPECTED_CONTRACT_SHA256:
        raise RuntimeError("EXP-056 contract hash changed")
    if source_record(config, "exp056_results")["sha256"] != EXPECTED_RESULTS_SHA256:
        raise RuntimeError("EXP-056 result hash changed")
    if not results["labels_opened_after_prediction_seal"]:
        raise RuntimeError("Prediction-seal order is not preserved")
    if results["selection_or_tuning_after_test"]:
        raise RuntimeError("Post-test selection was recorded")
    if int(results["test_rows"]) != 720:
        raise RuntimeError("Unexpected test row count")
    if set(results["family_results"]) != set(FAMILIES):
        raise RuntimeError("Unexpected family scope")
    if set(results["unit_results"]) != {
        f"{family}-seed-{seed}" for family in FAMILIES for seed in SEEDS
    }:
        raise RuntimeError("Unexpected unit scope")

    validation_payloads = {
        family: load_json(source_paths[f"exp0{50 + index}_aggregate"])
        for index, family in enumerate(FAMILIES, start=1)
    }
    validation_rows = build_validation_rows(validation_payloads)
    test_rows = build_test_rows(results)
    per_label_rows = build_per_label_rows(results)
    contrast_rows = build_contrast_rows(results)
    resource_rows = build_resource_rows(results)
    claims = build_claims(contrast_rows)

    validation_index = by_family(validation_rows)
    test_index = by_family(test_rows)
    generalization = {
        family: {
            "macro_f1_test_minus_validation": float(test_index[family]["macro_f1_mean"])
            - float(validation_index[family]["macro_f1_mean"]),
            "five_label_test_minus_validation": float(
                test_index[family]["five_label_macro_f1_without_surprise_mean"]
            )
            - float(validation_index[family]["five_label_macro_f1_without_surprise_mean"]),
            "descriptive_only": True,
        }
        for family in FAMILIES
    }

    error_summary = load_json(source_paths["exp055_summary"])
    synthesis = {
        "schema_version": "exp-057-read-only-result-synthesis-v1",
        "experiment_id": "EXP-057",
        "status": "Completed; pending independent verification",
        "source_experiment": "EXP-056",
        "source_test_rows": 720,
        "source_components": 702,
        "families": FAMILIES,
        "seeds": SEEDS,
        "labels": LABELS,
        "validation": validation_rows,
        "test": test_rows,
        "test_per_label": per_label_rows,
        "test_contrasts": contrast_rows,
        "test_resources": resource_rows,
        "validation_to_test": generalization,
        "validation_error_analysis": {
            "source": "EXP-055",
            "rows": error_summary["rows"],
            "qualitative_rows": error_summary["qualitative"]["rows"],
            "reviewer_count": error_summary["qualitative"]["reviewer_count"],
            "router_headroom_gate": error_summary["router_headroom_gate"],
            "claim_boundary": error_summary["claim_boundary"],
        },
        "claims": claims,
        "claim_boundary": {
            "post_test_read_only": True,
            "new_training": False,
            "new_inference": False,
            "private_prediction_access": False,
            "test_label_access": False,
            "selection_or_tuning": False,
            "mechanism_claim": False,
            "surprise_support": 7,
        },
    }

    run_dir = resolve(config["output_dir"])
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError(f"Output directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    validation_fields = ["family", "display_name"] + [
        suffix
        for metric in METRICS
        for suffix in (f"{metric}_mean", f"{metric}_sample_std")
    ]
    test_fields = validation_fields + ["parser_valid_rate_mean", "parser_valid_rate_sample_std"]
    write_csv(run_dir / "validation-family-summary.csv", validation_fields, validation_rows)
    write_csv(run_dir / "test-family-summary.csv", test_fields, test_rows)
    write_csv(
        run_dir / "test-per-label-summary.csv",
        list(per_label_rows[0].keys()),
        per_label_rows,
    )
    write_csv(run_dir / "test-contrast-summary.csv", list(contrast_rows[0].keys()), contrast_rows)
    write_csv(run_dir / "test-resource-summary.csv", list(resource_rows[0].keys()), resource_rows)
    write_json(run_dir / "result-synthesis.json", synthesis)
    (run_dir / "THESIS-TABLES.md").write_text(
        render_markdown(
            validation_rows,
            test_rows,
            per_label_rows,
            contrast_rows,
            resource_rows,
            claims,
        ),
        encoding="utf-8",
    )

    frozen_map = {
        "protocol": "frozen-protocol.md",
        "config": "frozen-config.json",
        "analyzer": "frozen-analyzer.py",
        "verifier": "frozen-verifier.py",
        "tests": "frozen-tests.py",
    }
    for name, target in frozen_map.items():
        source = config_path if name == "config" else verify_record(config["implementation"][name])
        shutil.copyfile(source, run_dir / target)

    artifact_names = [
        "validation-family-summary.csv",
        "test-family-summary.csv",
        "test-per-label-summary.csv",
        "test-contrast-summary.csv",
        "test-resource-summary.csv",
        "result-synthesis.json",
        "THESIS-TABLES.md",
        *frozen_map.values(),
    ]
    run = {
        "schema_version": "exp-057-read-only-result-synthesis-run-v1",
        "experiment_id": "EXP-057",
        "status": "Completed; pending independent verification",
        "tier": "Major",
        "stage": "post-test-read-only-result-synthesis",
        "completed_date": "2026-08-16",
        "rq_ids": ["RQ-S1", "RQ-S2", "RQ-S3"],
        "training_performed": False,
        "inference_performed": False,
        "private_predictions_accessed": False,
        "test_labels_accessed": False,
        "selection_or_tuning_performed": False,
        "source_results_sha256": source_record(config, "exp056_results")["sha256"],
        "source_contract_sha256": results["contract_sha256"],
        "sources": config["sources"],
        "artifacts": {name: artifact_record(run_dir / name) for name in artifact_names},
        "claim_boundary": synthesis["claim_boundary"],
    }
    write_json(run_dir / "run.json", run)


if __name__ == "__main__":
    main()

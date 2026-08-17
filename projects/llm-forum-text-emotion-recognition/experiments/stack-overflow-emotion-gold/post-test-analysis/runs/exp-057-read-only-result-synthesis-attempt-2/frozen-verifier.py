#!/usr/bin/env python3
"""Independent verifier for EXP-057. This module does not import the analyzer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[5]
FAMILIES = ("m1", "m2", "m3", "m4")
SEEDS = (42, 43, 44)
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
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
EXPECTED_RESULTS_SHA256 = (
    "d7b966ead7105b819db946c970e3f90b6b25514eac8e8e0b71c4ab3a69928cdd"
)
EXPECTED_CONTRACT_SHA256 = (
    "bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def mean_std(values: Iterable[float]) -> tuple[float, float]:
    materialized = [float(value) for value in values]
    return (
        statistics.fmean(materialized),
        statistics.stdev(materialized) if len(materialized) > 1 else 0.0,
    )


def close(left: Any, right: Any, tolerance: float = 1e-12) -> bool:
    try:
        return math.isclose(float(left), float(right), abs_tol=tolerance, rel_tol=0.0)
    except (TypeError, ValueError):
        return False


def validation_node(payload: dict[str, Any], family: str) -> dict[str, Any]:
    if family in {"m1", "m2", "m3"}:
        node = dict(payload["aggregate"]["metrics"]["shared_threshold"])
        if "empty_prediction_rate" not in node:
            empty_rows = node["empty_prediction_rows"]
            mean, sample_std = mean_std(float(value) / 720.0 for value in empty_rows["values"])
            node["empty_prediction_rate"] = {
                "mean": mean,
                "sample_std": sample_std,
            }
        return node
    node = dict(payload["metrics"])
    node["empty_prediction_rate"] = payload["generation"]["empty_prediction_rate"]
    node["predicted_label_cardinality_mean"] = payload["generation"][
        "predicted_label_cardinality_mean"
    ]
    return node


def truncated_rows(resource: dict[str, Any]) -> int:
    if "truncated_rows" in resource:
        return int(resource["truncated_rows"])
    return int(resource.get("tokenization", {}).get("truncated_rows", 0))


def main() -> None:
    args = parse_args()
    config_path = resolve(args.config)
    run_dir = resolve(args.run_dir)
    config = load_json(config_path)
    run = load_json(run_dir / "run.json")
    synthesis = load_json(run_dir / "result-synthesis.json")
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str | None = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("experiment_id", config.get("experiment_id") == "EXP-057")
    for key in (
        "training_authorized",
        "inference_authorized",
        "private_prediction_access_authorized",
        "test_label_access_authorized",
        "selection_or_tuning_authorized",
    ):
        check(f"boundary:{key}", config.get(key) is False)
    check("run_training_false", run.get("training_performed") is False)
    check("run_inference_false", run.get("inference_performed") is False)
    check("run_private_predictions_false", run.get("private_predictions_accessed") is False)
    check("run_test_labels_false", run.get("test_labels_accessed") is False)
    check("run_selection_false", run.get("selection_or_tuning_performed") is False)

    sources: dict[str, Path] = {}
    for name, record in config["sources"].items():
        path_text = str(record["path"])
        lowered = path_text.lower()
        allowed = not any(
            token in lowered for token in ("derived-private", "/private/", ".npz", ".safetensors")
        )
        path = resolve(path_text)
        sources[name] = path
        check(f"source_public:{name}", allowed, path_text)
        check(f"source_exists:{name}", path.is_file(), path_text)
        if path.is_file():
            check(f"source_bytes:{name}", path.stat().st_size == int(record["bytes"]))
            check(f"source_hash:{name}", sha256_file(path) == record["sha256"])

    for name in config["verification_sources"]:
        payload = load_json(sources[name])
        check(f"upstream_passed:{name}", payload.get("status") == "Passed")
        check(f"upstream_no_failures:{name}", payload.get("failed_checks", []) == [])

    results = load_json(sources["exp056_results"])
    check("results_hash_frozen", config["sources"]["exp056_results"]["sha256"] == EXPECTED_RESULTS_SHA256)
    check("contract_hash_frozen", results.get("contract_sha256") == EXPECTED_CONTRACT_SHA256)
    check("prediction_before_labels", results.get("labels_opened_after_prediction_seal") is True)
    check("no_post_test_selection", results.get("selection_or_tuning_after_test") is False)
    check("test_rows", results.get("test_rows") == 720)
    check("family_scope", set(results.get("family_results", {})) == set(FAMILIES))
    expected_units = {f"{family}-seed-{seed}" for family in FAMILIES for seed in SEEDS}
    check("unit_scope", set(results.get("unit_results", {})) == expected_units)
    check("contrast_scope", tuple(results.get("paired_contrasts", {})) == EXPECTED_CONTRASTS)

    validation_rows = {row["family"]: row for row in read_csv(run_dir / "validation-family-summary.csv")}
    test_rows = {row["family"]: row for row in read_csv(run_dir / "test-family-summary.csv")}
    per_label_rows = {
        (row["family"], row["label"]): row
        for row in read_csv(run_dir / "test-per-label-summary.csv")
    }
    contrast_rows = {
        row["contrast"]: row for row in read_csv(run_dir / "test-contrast-summary.csv")
    }
    resource_rows = {
        row["family"]: row for row in read_csv(run_dir / "test-resource-summary.csv")
    }
    check("validation_row_scope", set(validation_rows) == set(FAMILIES))
    check("test_row_scope", set(test_rows) == set(FAMILIES))
    check(
        "per_label_row_scope",
        set(per_label_rows) == {(family, label) for family in FAMILIES for label in LABELS},
    )
    check("contrast_row_scope", tuple(contrast_rows) == EXPECTED_CONTRASTS)
    check("resource_row_scope", set(resource_rows) == set(FAMILIES))

    validation_sources = {
        "m1": load_json(sources["exp051_aggregate"]),
        "m2": load_json(sources["exp052_aggregate"]),
        "m3": load_json(sources["exp053_aggregate"]),
        "m4": load_json(sources["exp054_aggregate"]),
    }
    for family in FAMILIES:
        node = validation_node(validation_sources[family], family)
        row = validation_rows[family]
        for metric in METRICS:
            expected = node[metric]
            check(
                f"validation_mean:{family}:{metric}",
                close(row[f"{metric}_mean"], expected["mean"]),
            )
            check(
                f"validation_sd:{family}:{metric}",
                close(row[f"{metric}_sample_std"], expected.get("sample_std", 0.0)),
            )

    for family in FAMILIES:
        row = test_rows[family]
        for metric in METRICS:
            values = [
                results["unit_results"][f"{family}-seed-{seed}"]["metrics"][metric]
                for seed in SEEDS
            ]
            expected_mean, expected_sd = mean_std(values)
            check(f"test_mean:{family}:{metric}", close(row[f"{metric}_mean"], expected_mean))
            check(
                f"test_sd:{family}:{metric}",
                close(row[f"{metric}_sample_std"], expected_sd),
            )
            frozen = results["family_results"][family]["metrics"][metric]
            check(f"frozen_mean:{family}:{metric}", close(expected_mean, frozen["mean"]))
            check(f"frozen_sd:{family}:{metric}", close(expected_sd, frozen["sample_std"]))
        if family == "m4":
            parser_mean, parser_sd = mean_std(
                results["unit_results"][f"m4-seed-{seed}"]["parser_valid_rate"]
                for seed in SEEDS
            )
            check("m4_parser_mean", close(row["parser_valid_rate_mean"], parser_mean))
            check("m4_parser_sd", close(row["parser_valid_rate_sample_std"], parser_sd))
        else:
            check(f"non_generative_parser_blank:{family}", row["parser_valid_rate_mean"] == "")

    support_by_label: dict[str, int] = {}
    for family in FAMILIES:
        for label in LABELS:
            row = per_label_rows[(family, label)]
            records = [
                results["unit_results"][f"{family}-seed-{seed}"]["metrics"]["per_label"][label]
                for seed in SEEDS
            ]
            supports = {int(record["support"]) for record in records}
            check(f"support_stable:{family}:{label}", len(supports) == 1)
            support = next(iter(supports))
            support_by_label.setdefault(label, support)
            check(f"support_cross_family:{family}:{label}", support_by_label[label] == support)
            check(f"support_csv:{family}:{label}", int(row["gold_support"]) == support)
            for source_key, output_key in (
                ("f1", "f1"),
                ("precision", "precision"),
                ("recall", "recall"),
                ("predicted_support", "predicted_support"),
            ):
                expected_mean, expected_sd = mean_std(record[source_key] for record in records)
                check(
                    f"per_label_mean:{family}:{label}:{source_key}",
                    close(row[f"{output_key}_mean"], expected_mean),
                )
                check(
                    f"per_label_sd:{family}:{label}:{source_key}",
                    close(row[f"{output_key}_sample_std"], expected_sd),
                )
    check("surprise_support_seven", support_by_label.get("surprise") == 7)

    for contrast in EXPECTED_CONTRASTS:
        source = results["paired_contrasts"][contrast]["component_bootstrap"]
        row = contrast_rows[contrast]
        check(f"contrast_orientation:{contrast}", row["orientation"] == "second_family_minus_first_family")
        check(f"contrast_unit:{contrast}", row["unit"] == "duplicate_component_id")
        check(f"contrast_components:{contrast}", int(row["components"]) == 702)
        check(f"contrast_replicates:{contrast}", int(row["replicates"]) == 2000)
        for csv_key, source_metric, source_key in (
            ("macro_f1_delta", "macro_f1", "point"),
            ("macro_f1_ci95_lower", "macro_f1", "lower"),
            ("macro_f1_ci95_upper", "macro_f1", "upper"),
            ("five_label_delta", "five_label_macro_f1_without_surprise", "point"),
            ("five_label_ci95_lower", "five_label_macro_f1_without_surprise", "lower"),
            ("five_label_ci95_upper", "five_label_macro_f1_without_surprise", "upper"),
        ):
            check(
                f"contrast_value:{contrast}:{csv_key}",
                close(row[csv_key], source[source_metric][source_key]),
            )

    for family in FAMILIES:
        row = resource_rows[family]
        units = [results["unit_results"][f"{family}-seed-{seed}"] for seed in SEEDS]
        resources = [unit["resource"] for unit in units]
        backends = {resource["backend"] for resource in resources}
        check(f"resource_backend:{family}", len(backends) == 1 and row["backend"] in backends)
        wall = [resource["wall_seconds"] for resource in resources if "wall_seconds" in resource]
        shared = [resource["shared_feature_seconds"] for resource in resources if "shared_feature_seconds" in resource]
        head = [resource["head_seconds"] for resource in resources if "head_seconds" in resource]
        peak = [resource["peak_memory_gb"] for resource in resources if "peak_memory_gb" in resource]
        parser = [unit["parser_valid_rate"] for unit in units if "parser_valid_rate" in unit]
        check(
            f"resource_wall:{family}",
            row["mean_per_seed_wall_seconds"] == ""
            if not wall
            else close(row["mean_per_seed_wall_seconds"], statistics.fmean(wall)),
        )
        check(
            f"resource_shared:{family}",
            row["shared_feature_seconds"] == ""
            if not shared
            else close(row["shared_feature_seconds"], max(shared)),
        )
        check(
            f"resource_head:{family}",
            row["mean_head_seconds"] == ""
            if not head
            else close(row["mean_head_seconds"], statistics.fmean(head)),
        )
        check(
            f"resource_peak:{family}",
            row["peak_memory_gb_max"] == ""
            if not peak
            else close(row["peak_memory_gb_max"], max(peak)),
        )
        check(
            f"resource_parser:{family}",
            row["parser_valid_rate_mean"] == ""
            if not parser
            else close(row["parser_valid_rate_mean"], statistics.fmean(parser)),
        )
        check(
            f"resource_truncation:{family}",
            int(row["truncated_rows_total"]) == sum(truncated_rows(resource) for resource in resources),
        )
        check(f"resource_api_cost:{family}", close(row["api_cost_usd"], 0.0))

    synthesis_validation = {row["family"]: row for row in synthesis["validation"]}
    synthesis_test = {row["family"]: row for row in synthesis["test"]}
    for family in FAMILIES:
        expected_macro = float(synthesis_test[family]["macro_f1_mean"]) - float(
            synthesis_validation[family]["macro_f1_mean"]
        )
        expected_five = float(
            synthesis_test[family]["five_label_macro_f1_without_surprise_mean"]
        ) - float(synthesis_validation[family]["five_label_macro_f1_without_surprise_mean"])
        actual = synthesis["validation_to_test"][family]
        check(f"generalization_macro:{family}", close(actual["macro_f1_test_minus_validation"], expected_macro))
        check(f"generalization_five:{family}", close(actual["five_label_test_minus_validation"], expected_five))
        check(f"generalization_descriptive:{family}", actual["descriptive_only"] is True)

    exp055 = load_json(sources["exp055_summary"])
    error = synthesis["validation_error_analysis"]
    check("error_analysis_rows", error["rows"] == exp055["rows"] == 720)
    check("error_analysis_qualitative_rows", error["qualitative_rows"] == exp055["qualitative"]["rows"])
    check("error_analysis_reviewer", error["reviewer_count"] == exp055["qualitative"]["reviewer_count"] == 1)
    check("router_gate_descriptive", error["router_headroom_gate"] == exp055["router_headroom_gate"])
    check("claim_count", len(synthesis.get("claims", [])) == 5)
    check("mechanism_claim_false", synthesis["claim_boundary"]["mechanism_claim"] is False)
    check("surprise_boundary", synthesis["claim_boundary"]["surprise_support"] == 7)

    for name, record in run["artifacts"].items():
        path = resolve(record["path"])
        check(f"artifact_exists:{name}", path.is_file())
        if path.is_file():
            check(f"artifact_bytes:{name}", path.stat().st_size == int(record["bytes"]))
            check(f"artifact_hash:{name}", sha256_file(path) == record["sha256"])

    frozen_pairs = {
        "frozen-protocol.md": resolve(config["implementation"]["protocol"]["path"]),
        "frozen-config.json": config_path,
        "frozen-analyzer.py": resolve(config["implementation"]["analyzer"]["path"]),
        "frozen-verifier.py": resolve(config["implementation"]["verifier"]["path"]),
        "frozen-tests.py": resolve(config["implementation"]["tests"]["path"]),
    }
    if "amendment" in config["implementation"]:
        frozen_pairs["frozen-amendment.md"] = resolve(
            config["implementation"]["amendment"]["path"]
        )
    for frozen_name, source in frozen_pairs.items():
        check(f"frozen_copy:{frozen_name}", sha256_file(run_dir / frozen_name) == sha256_file(source))

    public_data_files = (
        "validation-family-summary.csv",
        "test-family-summary.csv",
        "test-per-label-summary.csv",
        "test-contrast-summary.csv",
        "test-resource-summary.csv",
        "result-synthesis.json",
        "THESIS-TABLES.md",
        "run.json",
    )
    forbidden_fragments = (
        "derived-private",
        "test.labels",
        "sample_id",
        "source_id",
        "raw_text",
        "forum_text",
    )
    for filename in public_data_files:
        content = (run_dir / filename).read_text(encoding="utf-8").lower()
        check(
            f"public_privacy:{filename}",
            not any(fragment in content for fragment in forbidden_fragments),
        )

    failed = [item for item in checks if not item["passed"]]
    verification = {
        "schema_version": "exp-057-read-only-result-synthesis-verification-v1",
        "experiment_id": "EXP-057",
        "status": "Passed" if not failed else "Failed",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "failed_checks": failed,
        "analyzer_imported": False,
        "private_predictions_opened": False,
        "sealed_test_label_source_reopened": False,
    }
    (run_dir / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = [
        "# EXP-057 Verification Summary",
        "",
        f"- Status: `{verification['status']}`",
        f"- Checks: `{len(checks) - len(failed)}/{len(checks)} Passed`",
        "- Analyzer imported: `false`",
        "- Private predictions opened: `false`",
        "- Sealed test-label source reopened: `false`",
        "",
    ]
    if failed:
        summary.extend(["## Failed Checks", ""])
        summary.extend(f"- `{item['name']}`" for item in failed)
    (run_dir / "VERIFICATION-SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    if failed:
        raise SystemExit(f"EXP-057 verification failed: {len(failed)} checks")


if __name__ == "__main__":
    main()

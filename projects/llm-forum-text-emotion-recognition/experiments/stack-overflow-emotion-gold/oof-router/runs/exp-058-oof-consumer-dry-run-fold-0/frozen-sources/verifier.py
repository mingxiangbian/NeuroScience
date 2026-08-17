#!/usr/bin/env python3
"""Independently verify the EXP-058 fold-0 M1/M3 two-step dry-run."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "EXP-058"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SENSITIVE_KEYS = {
    "component_id",
    "component_ids",
    "gold",
    "labels",
    "logits",
    "prediction",
    "predictions",
    "probabilities",
    "sample_id",
    "sample_ids",
    "text",
}
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-058-oof-consumer-dry-run-fold-0.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def verify_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Artifact drift: {path}")
    return path


def sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in SENSITIVE_KEYS:
                paths.append(path)
            paths.extend(sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(sensitive_paths(child, f"{prefix}[{index}]"))
    return paths


def finite_matrix(value: Any, rows: int, columns: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == rows
        and all(
            isinstance(row, list)
            and len(row) == columns
            and all(type(item) in (int, float) and math.isfinite(float(item)) for item in row)
            for row in value
        )
    )


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def expect(self, name: str, condition: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(condition), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


def verify(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    private_dir = resolve_project(config["outputs"]["private_run_dir"])
    run_path = run_dir / "run.json"
    run = read_json(run_path)
    checks = Checks()

    checks.expect("identity.experiment", config.get("experiment_id") == EXPERIMENT_ID)
    checks.expect("identity.stage", run.get("stage") == config.get("stage"))
    checks.expect("run.status", run.get("status") == "CompletedAwaitingVerification")
    checks.expect("run.static_passed", run["stages"]["static"]["status"] == "Passed")
    checks.expect("run.m1_passed", run["stages"]["m1"]["status"] == "Passed")
    checks.expect("run.m3_passed", run["stages"]["m3"]["status"] == "Passed")
    checks.expect("authorization.fold", config["authorization"]["fold_id"] == 0)
    checks.expect("authorization.seed", config["authorization"]["model_seed"] == 42)
    checks.expect("authorization.no_validation", config["authorization"]["validation_access"] is False)
    checks.expect("authorization.no_test", config["authorization"]["test_access"] is False)
    checks.expect("authorization.no_metrics", config["authorization"]["metrics"] is False)
    checks.expect("authorization.no_full_oof", config["authorization"]["full_oof_training"] is False)
    checks.expect("run.no_validation", run["split_access"]["validation_accessed"] is False)
    checks.expect("run.no_test_inputs", run["split_access"]["test_inputs_accessed"] is False)
    checks.expect("run.no_test_labels", run["split_access"]["test_labels_accessed"] is False)
    checks.expect(
        "run.no_performance_metrics",
        run["model_execution"]["performance_metrics_computed"] is False,
    )
    checks.expect(
        "run.no_full_oof",
        run["model_execution"]["full_oof_training_performed"] is False,
    )
    checks.expect("privacy.public_keys", not sensitive_paths(run), sensitive_paths(run))

    for name, source_record in {"config": artifact(config_path), **config["implementation"]}.items():
        frozen_record = run["artifacts"]["frozen_sources"].get(name)
        checks.expect(f"frozen.{name}.listed", isinstance(frozen_record, dict))
        if not isinstance(frozen_record, dict):
            continue
        try:
            source_path = verify_record(source_record)
            frozen_path = verify_record(frozen_record)
            checks.expect(f"frozen.{name}.content", sha256(source_path) == sha256(frozen_path))
        except Exception as error:
            checks.expect(f"frozen.{name}.valid", False, str(error))

    train_path = verify_record(config["data"]["train"])
    manifest_path = verify_record(config["prerequisites"]["fold_manifest"])
    train_rows = read_jsonl(train_path)
    manifest_rows = read_jsonl(manifest_path)
    assignments = {row["sample_id"]: row for row in manifest_rows}
    checks.expect("data.train_rows", len(train_rows) == 3360)
    checks.expect("data.manifest_rows", len(manifest_rows) == 3360)
    checks.expect("data.manifest_unique", len(assignments) == 3360)
    checks.expect("data.coverage", set(assignments) == {row["sample_id"] for row in train_rows})
    training = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] != 0]
    heldout = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] == 0]
    checks.expect("partition.training_rows", len(training) == 2688)
    checks.expect("partition.heldout_rows", len(heldout) == 672)
    checks.expect(
        "partition.sample_disjoint",
        not ({row["sample_id"] for row in training} & {row["sample_id"] for row in heldout}),
    )
    checks.expect(
        "partition.component_disjoint",
        not ({row["component_id"] for row in training} & {row["component_id"] for row in heldout}),
    )
    training_order = canonical_digest([row["sample_id"] for row in training])
    heldout_order = canonical_digest([row["sample_id"] for row in heldout])
    checks.expect("partition.training_order", training_order == run["data"]["training_order_sha256"])
    checks.expect("partition.heldout_order", heldout_order == run["data"]["heldout_order_sha256"])
    checks.expect("partition.manifest_hash", sha256(manifest_path) == run["data"]["manifest_sha256"])

    private_partition_path = verify_record(run["artifacts"]["private_partition"])
    checks.expect("privacy.partition_mode", private_partition_path.stat().st_mode & 0o777 == 0o600)
    private_partition = read_json(private_partition_path)
    checks.expect("private_partition.training_rows", len(private_partition["training"]) == 2688)
    checks.expect("private_partition.heldout_rows", len(private_partition["heldout"]) == 672)
    checks.expect(
        "private_partition.training_order",
        [row["sample_id"] for row in private_partition["training"]]
        == [row["sample_id"] for row in training],
    )
    checks.expect(
        "private_partition.heldout_order",
        [row["sample_id"] for row in private_partition["heldout"]]
        == [row["sample_id"] for row in heldout],
    )

    evidence: dict[str, dict[str, Any]] = {}
    for family in ("m1", "m3"):
        path = verify_record(run["artifacts"][f"{family}_private_evidence"])
        checks.expect(f"privacy.{family}_mode", path.stat().st_mode & 0o777 == 0o600)
        evidence[family] = read_json(path)
        item = evidence[family]
        checks.expect(f"{family}.fold", item["fold_id"] == 0)
        checks.expect(f"{family}.seed", item["model_seed"] == 42)
        checks.expect(f"{family}.training_source_order", item["training_source_order_sha256"] == training_order)
        checks.expect(f"{family}.heldout_source_order", item["heldout_source_order_sha256"] == heldout_order)
        checks.expect(f"{family}.optimizer_steps", item["optimizer_steps"] == 2)
        checks.expect(f"{family}.loss_count", len(item["losses"]) == 2)
        checks.expect(
            f"{family}.finite_losses",
            all(type(value) in (int, float) and math.isfinite(float(value)) for value in item["losses"]),
        )
        checks.expect(f"{family}.label_order", item["label_order"] == list(LABELS))
        checks.expect(f"{family}.heldout_logits", finite_matrix(item["heldout_logits"], 2, 6))
        checks.expect(f"{family}.heldout_labels_unused", item["heldout_labels_used_for_forward"] is False)
        checks.expect(
            f"{family}.manifest_before",
            item["manifest_sha256_before"] == sha256(manifest_path),
        )
        checks.expect(
            f"{family}.manifest_after",
            item["manifest_sha256_after"] == sha256(manifest_path),
        )
        checks.expect(
            f"{family}.heldout_ids",
            item["heldout_sample_ids"] == [row["sample_id"] for row in heldout[:2]],
        )
        expected_held_components = [row["component_id"] for row in heldout[:2]]
        checks.expect(f"{family}.heldout_components", item["heldout_component_ids"] == expected_held_components)
        train_by_id = {row["sample_id"]: row for row in training}
        checks.expect(
            f"{family}.training_membership",
            all(sample_id in train_by_id for sample_id in item["training_sample_ids"]),
        )
        checks.expect(
            f"{family}.training_components",
            item["training_component_ids"]
            == [train_by_id[sample_id]["component_id"] for sample_id in item["training_sample_ids"]],
        )
        checks.expect(
            f"{family}.train_heldout_disjoint",
            not (set(item["training_sample_ids"]) & set(item["heldout_sample_ids"])),
        )

    m1 = evidence["m1"]
    checks.expect("m1.batch_size", m1["batch_size"] == 16)
    checks.expect("m1.training_row_count", len(m1["training_sample_ids"]) == 32)
    checks.expect(
        "m1.training_ids_digest",
        canonical_digest(m1["training_sample_ids"])
        == config["m1"]["expected_dry_run_training_ids_sha256"],
    )
    checks.expect(
        "m1.epoch_order_digest",
        m1["epoch_1_order_sha256"] == config["m1"]["expected_epoch_1_order_sha256"],
    )
    checks.expect("m1.scheduler", m1["scheduler"] == config["m1"]["expected_schedule"])
    checks.expect(
        "m1.initial_classifier",
        m1["classifier_initial_sha256"] == config["m1"]["expected_classifier_initial_sha256"],
    )
    checks.expect("m1.classifier_updated", m1["classifier_final_sha256"] != m1["classifier_initial_sha256"])
    checks.expect(
        "m1.gradient_norms",
        len(m1["gradient_norms"]) == 2
        and all(math.isfinite(float(value)) and float(value) > 0 for value in m1["gradient_norms"]),
    )
    checks.expect(
        "m1.learning_rates",
        len(m1["learning_rates_after_step"]) == 2
        and all(math.isfinite(float(value)) and float(value) >= 0 for value in m1["learning_rates_after_step"]),
    )

    m3 = evidence["m3"]
    checks.expect("m3.batch_size", m3["batch_size"] == 1)
    checks.expect("m3.training_row_count", len(m3["training_sample_ids"]) == 2)
    checks.expect(
        "m3.training_ids_digest",
        canonical_digest(m3["training_sample_ids"])
        == config["m3"]["expected_dry_run_training_ids_sha256"],
    )
    checks.expect(
        "m3.epoch_order_digest",
        m3["epoch_1_order_sha256"] == config["m3"]["expected_epoch_1_order_sha256"],
    )
    checks.expect("m3.head_initial", m3["head_initial_sha256"] == config["m3"]["expected_head_initial_sha256"])
    checks.expect("m3.head_updated", m3["head_final_sha256"] != m3["head_initial_sha256"])
    checks.expect("m3.lora_initial", m3["lora_initial_sha256"] == config["m3"]["expected_lora_initial_sha256"])
    checks.expect("m3.lora_updated", m3["lora_final_sha256"] != m3["lora_initial_sha256"])
    checks.expect("m3.zero_delta", m3["zero_step_max_abs_logit_difference"] == 0.0)
    checks.expect("m3.insertions", m3["insertion_count"] == 112)
    checks.expect("m3.lora_parameters", m3["lora_parameter_count"] == 7_340_032)
    checks.expect("m3.trainable_parameters", m3["total_trainable_parameter_count"] == 7_355_398)
    checks.expect("m3.nonzero_lora_b", m3["nonzero_lora_b_tensors"] == 112)
    checks.expect("m3.base_unchanged", m3["base_sentinel_before"] == m3["base_sentinel_after"])
    checks.expect(
        "m3.base_expected",
        m3["base_sentinel_before"]["sha256"] == config["m3"]["expected_base_sentinel_sha256"],
    )
    checks.expect("cross_model.same_heldout", m1["heldout_sample_ids"] == m3["heldout_sample_ids"])
    checks.expect(
        "cross_model.heldout_digest",
        canonical_digest(m1["heldout_sample_ids"]) == config["expected_heldout_forward_ids_sha256"],
    )
    checks.expect(
        "resources.m1_memory",
        float(run["stages"]["m1"]["peak_process_rss_gb"])
        <= float(config["resources"]["m1_peak_process_memory_gb"]),
    )
    checks.expect(
        "resources.m3_memory",
        float(run["stages"]["m3"]["peak_mlx_memory_gb"])
        <= float(config["resources"]["m3_peak_mlx_memory_gb"]),
    )

    result = {
        "schema_version": "exp-058-oof-consumer-dry-run-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": config["stage"],
        "status": "Passed" if not checks.failed else "Failed",
        "verified_at_utc": utc_now(),
        "check_count": len(checks.rows),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {
            "model_runner_imported": False,
            "model_libraries_imported": False,
            "train_recomputed": True,
            "validation_opened": False,
            "test_inputs_opened": False,
            "test_labels_opened": False,
        },
        "verified_artifacts": {
            "run": artifact(run_path),
            "config": artifact(config_path),
            "fold_manifest": artifact(manifest_path),
            "m1_private_evidence": run["artifacts"]["m1_private_evidence"],
            "m3_private_evidence": run["artifacts"]["m3_private_evidence"],
        },
        "claim_boundary": (
            "Passing verifies only the fold-0 two-step M1/M3 OOF consumer path. It does not "
            "authorize full OOF, calibration, selective prediction, routing, validation, or test."
        ),
    }
    write_json(run_dir / "verification.json", result)
    summary = "\n".join(
        [
            "# EXP-058 OOF Consumer Dry-Run Verification",
            "",
            f"- Status: `{result['status']}`",
            f"- Checks: `{result['passed_count']}/{result['check_count']}`",
            "- Fold: `0`; model seed: `42`",
            "- M1/M3 optimizer steps: `2/2`",
            "- Held-out forward rows: `2` per model",
            "- Metrics/calibration/oracle/router: `not computed`",
            "- Validation/test access: `false`",
            "",
            result["claim_boundary"],
            "",
        ]
    )
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(summary, encoding="utf-8")
    if checks.failed:
        raise RuntimeError(f"Dry-run verification failed: {len(checks.failed)} checks")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    result = verify(args.config.resolve())
    print(json.dumps({"status": result["status"], "checks": result["check_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()

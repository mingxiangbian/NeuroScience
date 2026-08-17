#!/usr/bin/env python3
"""Independently verify EXP-058 fold or final paired OOF production artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any


EXPERIMENT_ID = "EXP-058"
STAGE = "paired-m1-m3-oof-production"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
PUBLIC_SENSITIVE_KEYS = {
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
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-058-oof-production.json"


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
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Artifact drift: {path}")
    return path


def tree_artifact(path: Path) -> dict[str, Any]:
    files = []
    total = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        size = child.stat().st_size
        total += size
        files.append(
            {
                "path": str(child.relative_to(path)),
                "bytes": size,
                "sha256": sha256(child),
            }
        )
    return {
        "path": display_path(path),
        "file_count": len(files),
        "bytes": total,
        "sha256": canonical_digest(files),
        "files": files,
    }


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def numpy_tensor_digest(items: dict[str, Any]) -> str:
    import numpy as np

    digest = hashlib.sha256()
    for name, tensor in sorted(items.items()):
        array = np.asarray(tensor, dtype=np.float32)
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("stage") != STAGE:
        raise ValueError("Unexpected EXP-058 production config")
    for record in config["implementation"].values():
        require_record(record)
    for record in config["prerequisites"].values():
        require_record(record)
    require_record(config["data"]["train"])
    return config


def source_state(config: dict[str, Any]) -> dict[str, Any]:
    train_path = require_record(config["data"]["train"])
    manifest_path = require_record(config["prerequisites"]["fold_manifest"])
    train_rows = read_jsonl(train_path)
    manifest_rows = read_jsonl(manifest_path)
    if len(train_rows) != 3360 or len(manifest_rows) != 3360:
        raise ValueError("Source row-count drift")
    train_by_id = {row["sample_id"]: row for row in train_rows}
    assignments = {row["sample_id"]: row for row in manifest_rows}
    if len(train_by_id) != 3360 or len(assignments) != 3360 or set(train_by_id) != set(assignments):
        raise ValueError("Source identity coverage drift")
    for sample_id, row in train_by_id.items():
        if assignments[sample_id]["component_id"] != row["component_id"]:
            raise ValueError("Source component identity drift")
    partitions = {}
    for fold_id in range(5):
        heldout = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] == fold_id]
        training = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] != fold_id]
        partitions[fold_id] = {"training": training, "heldout": heldout}
    return {
        "train_path": train_path,
        "manifest_path": manifest_path,
        "train_rows": train_rows,
        "train_by_id": train_by_id,
        "assignments": assignments,
        "partitions": partitions,
    }


def public_run_dir(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["public_run_dir"])


def private_run_dir(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["private_run_dir"])


def fold_dirs(config: dict[str, Any], family: str, fold_id: int) -> tuple[Path, Path]:
    return (
        public_run_dir(config) / f"fold-{fold_id}" / family,
        private_run_dir(config) / f"fold-{fold_id}" / family,
    )


def verify_private_modes(checks: Checks, private_fold: Path, namespace: str) -> None:
    checks.add(f"{namespace}.private_dir_mode", mode(private_fold) == 0o700, oct(mode(private_fold)))
    for child in sorted(private_fold.rglob("*")):
        expected = 0o700 if child.is_dir() else 0o600
        checks.add(
            f"{namespace}.private_mode.{child.relative_to(private_fold)}",
            mode(child) == expected,
            oct(mode(child)),
        )


def verify_fold(config_path: Path, config: dict[str, Any], family: str, fold_id: int) -> dict[str, Any]:
    import numpy as np
    from safetensors.numpy import load_file

    if family not in ("m1", "m3") or fold_id not in range(5):
        raise ValueError("Invalid fold verification target")
    public_fold, private_fold = fold_dirs(config, family, fold_id)
    output_path = public_fold / "verification.json"
    if output_path.exists():
        raise FileExistsError("Refusing to overwrite append-only fold verification")
    run_path = public_fold / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    sources = source_state(config)
    training = sources["partitions"][fold_id]["training"]
    heldout = sources["partitions"][fold_id]["heldout"]
    checks = Checks()
    prefix = f"{family}.fold_{fold_id}"

    checks.add(f"{prefix}.run_status", run.get("status") == "CompletedAwaitingVerification")
    checks.add(f"{prefix}.identity", run.get("family") == family and run.get("fold_id") == fold_id)
    checks.add(f"{prefix}.seed", run.get("model_seed") == 42)
    checks.add(f"{prefix}.training_rows", run.get("data", {}).get("training_rows") == 2688)
    checks.add(f"{prefix}.heldout_rows", run.get("data", {}).get("heldout_rows") == 672)
    checks.add(
        f"{prefix}.training_order",
        run.get("data", {}).get("training_order_sha256")
        == canonical_digest([row["sample_id"] for row in training]),
    )
    checks.add(
        f"{prefix}.heldout_order",
        run.get("data", {}).get("heldout_order_sha256")
        == canonical_digest([row["sample_id"] for row in heldout]),
    )
    checks.add(
        f"{prefix}.manifest",
        run.get("data", {}).get("fold_manifest_sha256") == sha256(sources["manifest_path"]),
    )
    checks.add(f"{prefix}.sample_overlap", run.get("data", {}).get("sample_overlap") == 0)
    checks.add(f"{prefix}.component_overlap", run.get("data", {}).get("component_overlap") == 0)
    split = run.get("split_access", {})
    checks.add(f"{prefix}.train_only", split.get("accessed_splits") == ["train"])
    checks.add(f"{prefix}.no_validation", split.get("validation_accessed") is False)
    checks.add(f"{prefix}.no_test_inputs", split.get("test_inputs_accessed") is False)
    checks.add(f"{prefix}.no_test_labels", split.get("test_labels_accessed") is False)
    checks.add(f"{prefix}.no_metrics", run.get("performance_metrics_computed") is False)
    checks.add(f"{prefix}.public_privacy", not public_sensitive_paths(run), public_sensitive_paths(run))

    history_path = require_record(run["artifacts"]["history"])
    history = list(csv.DictReader(history_path.open(encoding="utf-8")))
    expected_epochs = 4 if family == "m1" else 2
    expected_steps = 672 if family == "m1" else 5376
    checks.add(f"{prefix}.history_epochs", len(history) == expected_epochs, len(history))
    checks.add(
        f"{prefix}.optimizer_steps",
        run.get("training", {}).get("optimizer_steps") == expected_steps,
        run.get("training", {}).get("optimizer_steps"),
    )
    checks.add(
        f"{prefix}.history_final_steps",
        bool(history) and int(history[-1]["optimizer_steps"]) == expected_steps,
    )
    checks.add(
        f"{prefix}.finite_train_losses",
        len(history) == expected_epochs
        and all(math.isfinite(float(row["train_loss"])) for row in history),
    )

    evidence_path = require_record(run["artifacts"]["evidence_private"])
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    batch_orders_path = require_record(run["artifacts"]["batch_orders_private"])
    batch_orders = np.load(batch_orders_path, allow_pickle=False)
    checks.add(
        f"{prefix}.batch_order_shape",
        batch_orders.shape == (expected_epochs, 2688),
        list(batch_orders.shape),
    )
    expected_indices = np.arange(2688, dtype=np.int32)
    for epoch in range(expected_epochs):
        permutation_ok = np.array_equal(np.sort(batch_orders[epoch]), expected_indices)
        checks.add(f"{prefix}.epoch_{epoch + 1}_permutation", permutation_ok)
        if permutation_ok:
            digest = canonical_digest(
                [training[int(index)]["sample_id"] for index in batch_orders[epoch]]
            )
            checks.add(
                f"{prefix}.epoch_{epoch + 1}_order_digest",
                digest == history[epoch]["batch_order_sha256"]
                and digest == evidence["batch_order_sha256"][epoch],
            )
    checks.add(f"{prefix}.labels_not_used_for_forward", evidence.get("heldout_labels_used_for_forward") is False)
    checks.add(
        f"{prefix}.manifest_unchanged",
        evidence.get("manifest_sha256_before") == evidence.get("manifest_sha256_after")
        == sha256(sources["manifest_path"]),
    )

    predictions_path = require_record(run["artifacts"]["heldout_logit_table_private"])
    with np.load(predictions_path, allow_pickle=False) as table:
        required = {
            "sample_ids",
            "component_ids",
            "fold_ids",
            "gold",
            "logits",
            "character_lengths",
            "token_lengths",
        }
        checks.add(f"{prefix}.private_table_schema", set(table.files) == required, sorted(table.files))
        sample_ids = table["sample_ids"].tolist()
        component_ids = table["component_ids"].tolist()
        fold_ids = np.asarray(table["fold_ids"])
        gold = np.asarray(table["gold"], dtype=np.uint8)
        logits = np.asarray(table["logits"], dtype=np.float32)
        character_lengths = np.asarray(table["character_lengths"], dtype=np.int32)
        token_lengths = np.asarray(table["token_lengths"], dtype=np.int32)
    expected_sample_ids = [row["sample_id"] for row in heldout]
    checks.add(f"{prefix}.heldout_identity", sample_ids == expected_sample_ids)
    checks.add(
        f"{prefix}.heldout_components",
        component_ids == [row["component_id"] for row in heldout],
    )
    checks.add(f"{prefix}.fold_ids", fold_ids.shape == (672,) and np.all(fold_ids == fold_id))
    checks.add(
        f"{prefix}.gold",
        gold.shape == (672, 6)
        and np.array_equal(gold, np.asarray([row["labels"] for row in heldout], dtype=np.uint8)),
    )
    checks.add(
        f"{prefix}.logits",
        logits.shape == (672, 6) and np.isfinite(logits).all(),
        list(logits.shape),
    )
    checks.add(
        f"{prefix}.character_lengths",
        np.array_equal(character_lengths, np.asarray([len(row["text"]) for row in heldout], dtype=np.int32)),
    )
    maximum_length = 256 if family == "m1" else 384
    checks.add(
        f"{prefix}.token_lengths",
        token_lengths.shape == (672,) and np.all(token_lengths > 0) and np.all(token_lengths <= maximum_length),
    )
    checks.add(
        f"{prefix}.heldout_not_training",
        not (set(sample_ids) & {row["sample_id"] for row in training}),
    )

    if family == "m1":
        schedule = run.get("training", {}).get("scheduler", {})
        checks.add(
            f"{prefix}.scheduler",
            schedule
            == {
                "steps_per_epoch": 168,
                "planned_scheduler_epochs": 5,
                "scheduler_horizon_steps": 840,
                "warmup_steps": 84,
                "selected_stop_epoch": 4,
                "selected_stop_steps": 672,
            },
        )
        checkpoint_record = run["artifacts"]["final_checkpoint_private"]
        checkpoint_dir = resolve_project(checkpoint_record["path"])
        observed_tree = tree_artifact(checkpoint_dir)
        checks.add(f"{prefix}.checkpoint_tree", observed_tree == checkpoint_record)
        model_path = checkpoint_dir / "model.safetensors"
        checks.add(f"{prefix}.checkpoint_model", model_path.is_file())
        if model_path.is_file():
            tensors = load_file(model_path)
            classifier = {name: value for name, value in tensors.items() if name.startswith("classifier.")}
            classifier_digest = numpy_tensor_digest(classifier)
            checks.add(
                f"{prefix}.classifier_final_digest",
                classifier_digest == run["model"]["classifier_final_sha256"]
                == evidence["classifier_final_sha256"],
            )
        checks.add(
            f"{prefix}.classifier_changed",
            run["model"]["classifier_initial_sha256"]
            == config["m1"]["expected_classifier_initial_sha256"]
            and run["model"]["classifier_final_sha256"]
            != run["model"]["classifier_initial_sha256"],
        )
        checks.add(
            f"{prefix}.memory",
            float(run["resources"]["peak_process_rss_gb"])
            <= float(config["resources"]["m1_peak_process_memory_gb"]),
        )
    else:
        adapter_path = require_record(run["artifacts"]["adapter_private"])
        head_path = require_record(run["artifacts"]["head_private"])
        adapter_digest = numpy_tensor_digest(load_file(adapter_path))
        head_digest = numpy_tensor_digest(load_file(head_path))
        checks.add(
            f"{prefix}.adapter_digest",
            adapter_digest == run["model"]["lora_final_sha256"] == evidence["lora_final_sha256"],
        )
        checks.add(
            f"{prefix}.head_digest",
            head_digest == run["model"]["head_final_sha256"] == evidence["head_final_sha256"],
        )
        checks.add(
            f"{prefix}.initialization",
            run["model"]["head_initial_sha256"] == config["m3"]["expected_head_initial_sha256"]
            and run["model"]["lora_initial_sha256"] == config["m3"]["expected_lora_initial_sha256"]
            and run["model"]["zero_step_max_abs_logit_difference"] == 0.0,
        )
        checks.add(
            f"{prefix}.lora_contract",
            run["model"]["insertion_count"] == 112
            and run["model"]["lora_parameter_count"] == 7_340_032
            and run["model"]["total_trainable_parameter_count"] == 7_355_398
            and run["model"]["nonzero_lora_b_tensors"] == 112
            and run["model"]["base_sentinel_unchanged"] is True
            and run["model"]["trainable_whitelist_passed"] is True,
        )
        checks.add(
            f"{prefix}.memory",
            float(run["resources"]["peak_mlx_memory_gb"])
            <= float(config["resources"]["m3_peak_mlx_memory_gb"]),
        )
        checks.add(
            f"{prefix}.fold_wall",
            float(run["resources"]["wall_seconds"])
            <= float(config["resources"]["m3_per_fold_wall_hours"]) * 3600,
        )
    verify_private_modes(checks, private_fold, prefix)

    result = {
        "schema_version": "exp-058-oof-fold-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": STAGE,
        "scope": "fold",
        "family": family,
        "fold_id": fold_id,
        "verified_at_utc": utc_now(),
        "status": "Passed" if not checks.failed else "Failed",
        "check_count": len(checks.rows),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {
            "runner_imported": False,
            "model_libraries_imported": False,
            "saved_private_table_recomputed": True,
            "saved_model_state_rehashed": True,
        },
        "verified_artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "private_table": artifact(predictions_path),
        },
        "claim_boundary": "Integrity of one train-only OOF fold; no performance claim.",
    }
    atomic_json(output_path, result)
    summary_path = public_fold / "VERIFICATION-SUMMARY.md"
    summary_path.write_text(
        "\n".join(
            [
                f"# EXP-058 {family.upper()} Fold {fold_id} Verification",
                "",
                f"- Status: `{result['status']}`",
                f"- Checks: `{result['passed_count']}/{result['check_count']}`",
                "- Accessed split: `train` only",
                "- Metrics/calibration/oracle/router: `not computed`",
                "",
                result["claim_boundary"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if checks.failed:
        raise RuntimeError(f"Fold verification failed: {len(checks.failed)} checks")
    return result


def verify_final(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    import numpy as np

    run_dir = public_run_dir(config)
    output_path = run_dir / "verification.json"
    if output_path.exists():
        raise FileExistsError("Refusing to overwrite append-only final verification")
    run_path = run_dir / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    summary_path = run_dir / "paired-oof-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    sources = source_state(config)
    checks = Checks()
    checks.add("final.run_status", run.get("status") == "CompletedAwaitingVerification")
    checks.add("final.identity", run.get("experiment_id") == EXPERIMENT_ID and run.get("stage") == STAGE)
    checks.add("final.summary_status", summary.get("status") == "CompletedAwaitingVerification")
    checks.add("final.rows", summary.get("rows") == 3360)
    checks.add("final.fold_counts", summary.get("rows_per_fold") == {str(i): 672 for i in range(5)})
    checks.add("final.no_metrics", summary.get("performance_metrics_computed") is False)
    checks.add("final.no_calibration", summary.get("calibration_performed") is False)
    checks.add("final.no_oracle", summary.get("oracle_analysis_performed") is False)
    checks.add("final.no_router", summary.get("router_training_performed") is False)
    checks.add("final.no_validation", summary.get("validation_accessed") is False)
    checks.add("final.no_test", summary.get("test_accessed") is False)
    split = run.get("split_access", {})
    checks.add("final.train_only", split.get("accessed_splits") == ["train"])
    checks.add("final.run_no_validation", split.get("validation_accessed") is False)
    checks.add("final.run_no_test_inputs", split.get("test_inputs_accessed") is False)
    checks.add("final.run_no_test_labels", split.get("test_labels_accessed") is False)

    fold_tables: dict[str, dict[str, Any]] = {"m1": {}, "m3": {}}
    fold_run_hashes: dict[str, dict[int, str]] = {"m1": {}, "m3": {}}
    family_wall = {"m1": 0.0, "m3": 0.0}
    for family in ("m1", "m3"):
        for fold_id in range(5):
            public_fold, _ = fold_dirs(config, family, fold_id)
            verification_path = public_fold / "verification.json"
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            checks.add(
                f"final.{family}.fold_{fold_id}.verification",
                verification.get("status") == "Passed" and verification.get("failed_count") == 0,
            )
            fold_run_path = public_fold / "run.json"
            fold_run = json.loads(fold_run_path.read_text(encoding="utf-8"))
            fold_run_hashes[family][fold_id] = sha256(fold_run_path)
            family_wall[family] += float(fold_run["resources"]["wall_seconds"])
            table_path = require_record(fold_run["artifacts"]["heldout_logit_table_private"])
            with np.load(table_path, allow_pickle=False) as table:
                for index, sample_id_value in enumerate(table["sample_ids"].tolist()):
                    sample_id = str(sample_id_value)
                    if sample_id in fold_tables[family]:
                        checks.add(f"final.{family}.duplicate_row", False)
                    fold_tables[family][sample_id] = {
                        "component_id": str(table["component_ids"][index]),
                        "fold_id": int(table["fold_ids"][index]),
                        "gold": np.asarray(table["gold"][index], dtype=np.uint8),
                        "logits": np.asarray(table["logits"][index], dtype=np.float32),
                        "character_length": int(table["character_lengths"][index]),
                        "token_length": int(table["token_lengths"][index]),
                    }
    expected_ids = [row["sample_id"] for row in sources["train_rows"]]
    checks.add("final.m1_coverage", set(fold_tables["m1"]) == set(expected_ids))
    checks.add("final.m3_coverage", set(fold_tables["m3"]) == set(expected_ids))

    paired_path = require_record(run["artifacts"]["paired_oof_private"])
    with np.load(paired_path, allow_pickle=False) as paired:
        required = {
            "sample_ids",
            "component_ids",
            "fold_ids",
            "gold",
            "m1_logits",
            "m3_logits",
            "character_lengths",
            "m1_token_lengths",
            "m3_token_lengths",
            "m1_fold_run_sha256",
            "m3_fold_run_sha256",
        }
        checks.add("final.paired_schema", set(paired.files) == required, sorted(paired.files))
        paired_values = {name: np.asarray(paired[name]) for name in paired.files}
    checks.add("final.paired_source_order", paired_values["sample_ids"].tolist() == expected_ids)
    checks.add("final.paired_shapes", paired_values["gold"].shape == (3360, 6) and paired_values["m1_logits"].shape == (3360, 6) and paired_values["m3_logits"].shape == (3360, 6))
    checks.add("final.paired_finite_m1", np.isfinite(paired_values["m1_logits"]).all())
    checks.add("final.paired_finite_m3", np.isfinite(paired_values["m3_logits"]).all())
    checks.add(
        "final.source_order_digest",
        summary.get("source_order_sha256") == canonical_digest(expected_ids),
    )
    for index, row in enumerate(sources["train_rows"]):
        sample_id = row["sample_id"]
        expected_fold = int(sources["assignments"][sample_id]["fold_id"])
        m1 = fold_tables["m1"][sample_id]
        m3 = fold_tables["m3"][sample_id]
        checks.add(f"final.row_{index}.component", str(paired_values["component_ids"][index]) == row["component_id"] == m1["component_id"] == m3["component_id"])
        checks.add(f"final.row_{index}.fold", int(paired_values["fold_ids"][index]) == expected_fold == m1["fold_id"] == m3["fold_id"])
        expected_gold = np.asarray(row["labels"], dtype=np.uint8)
        checks.add(f"final.row_{index}.gold", np.array_equal(paired_values["gold"][index], expected_gold) and np.array_equal(m1["gold"], expected_gold) and np.array_equal(m3["gold"], expected_gold))
        checks.add(f"final.row_{index}.m1", np.array_equal(paired_values["m1_logits"][index], m1["logits"]))
        checks.add(f"final.row_{index}.m3", np.array_equal(paired_values["m3_logits"][index], m3["logits"]))
        checks.add(f"final.row_{index}.length", int(paired_values["character_lengths"][index]) == len(row["text"]) == m1["character_length"] == m3["character_length"])
        checks.add(f"final.row_{index}.m1_run", str(paired_values["m1_fold_run_sha256"][index]) == fold_run_hashes["m1"][expected_fold])
        checks.add(f"final.row_{index}.m3_run", str(paired_values["m3_fold_run_sha256"][index]) == fold_run_hashes["m3"][expected_fold])
    checks.add(
        "final.m1_wall_budget",
        family_wall["m1"] <= float(config["resources"]["m1_total_wall_hours"]) * 3600,
        family_wall["m1"],
    )
    checks.add(
        "final.m3_wall_budget",
        family_wall["m3"] <= float(config["resources"]["m3_total_wall_hours"]) * 3600,
        family_wall["m3"],
    )
    private_root = private_run_dir(config)
    checks.add("final.private_root_mode", mode(private_root) == 0o700, oct(mode(private_root)))
    for child in sorted(private_root.rglob("*")):
        expected_mode = 0o700 if child.is_dir() else 0o600
        checks.add(
            f"final.private_mode.{child.relative_to(private_root)}",
            mode(child) == expected_mode,
            oct(mode(child)),
        )
    privacy_violations = []
    for json_path in sorted(run_dir.rglob("*.json")):
        if json_path.name == "verification.json" and json_path.parent == run_dir:
            continue
        privacy_violations.extend(
            f"{json_path.relative_to(run_dir)}:{path}"
            for path in public_sensitive_paths(json.loads(json_path.read_text(encoding="utf-8")))
        )
    checks.add("final.public_privacy", not privacy_violations, privacy_violations)

    result = {
        "schema_version": "exp-058-oof-final-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": STAGE,
        "scope": "final",
        "verified_at_utc": utc_now(),
        "status": "Passed" if not checks.failed else "Failed",
        "check_count": len(checks.rows),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {
            "runner_imported": False,
            "model_libraries_imported": False,
            "all_fold_tables_recomputed": True,
            "paired_table_recomputed": True,
        },
        "verified_artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "summary": artifact(summary_path),
            "paired_oof_private": artifact(paired_path),
        },
        "claim_boundary": "Verified paired train OOF logits only; calibration and routing remain separate experiments.",
    }
    atomic_json(output_path, result)
    summary_output = run_dir / "VERIFICATION-SUMMARY.md"
    summary_output.write_text(
        "\n".join(
            [
                "# EXP-058 Paired OOF Production Verification",
                "",
                f"- Status: `{result['status']}`",
                f"- Checks: `{result['passed_count']}/{result['check_count']}`",
                "- Paired train rows: `3,360`",
                "- M1/M3 fold runs: `5/5` and `5/5`",
                "- Metrics/calibration/oracle/router: `not computed`",
                "- Validation/test access: `false`",
                "",
                result["claim_boundary"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if checks.failed:
        raise RuntimeError(f"Final OOF verification failed: {len(checks.failed)} checks")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scope", choices=("fold", "final"), required=True)
    parser.add_argument("--family", choices=("m1", "m3"))
    parser.add_argument("--fold", type=int)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    if args.scope == "fold":
        if args.family is None or args.fold not in range(5):
            raise ValueError("Fold scope requires --family and --fold 0..4")
        result = verify_fold(config_path, config, args.family, args.fold)
    else:
        if args.family is not None or args.fold is not None:
            raise ValueError("Final scope does not accept --family/--fold")
        result = verify_final(config_path, config)
    print(json.dumps({"status": result["status"], "checks": result["check_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()

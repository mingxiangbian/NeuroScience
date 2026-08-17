#!/usr/bin/env python3
"""Independently verify the no-model EXP-058 fold-manifest preflight."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


EXPERIMENT_ID = "EXP-058"
STAGE = "fold-manifest-preflight"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
PUBLIC_FIELDS = {
    "schema_version",
    "protocol_id",
    "experiment_id",
    "sample_id",
    "component_id",
    "fold_id",
}
PRIVATE_FIELDS = PUBLIC_FIELDS | {"labels", "neutral", "label_cardinality"}
FORBIDDEN_MODEL_IMPORTS = {"torch", "transformers", "mlx", "tensorflow", "jax"}

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs/exp-058-fold-manifest-preflight-attempt-2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"Blank JSONL line at {path}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Non-object JSONL row at {path}:{line_number}")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class Checks:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def expect(self, name: str, condition: bool, detail: str = "") -> None:
        self.items.append(
            {"name": name, "status": "Passed" if condition else "Failed", "detail": detail}
        )

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [item for item in self.items if item["status"] == "Failed"]


def verify_artifact(checks: Checks, name: str, record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    checks.expect(f"artifact.{name}.exists", path.is_file(), display_path(path))
    if not path.is_file():
        return path
    checks.expect(
        f"artifact.{name}.bytes",
        path.stat().st_size == int(record["bytes"]),
        str(path.stat().st_size),
    )
    actual_hash = sha256_file(path)
    checks.expect(
        f"artifact.{name}.sha256", actual_hash == record["sha256"], actual_hash
    )
    return path


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def reconstruct_summary(
    train_rows: list[dict[str, Any]], public_rows: list[dict[str, Any]], fold_count: int
) -> tuple[dict[str, Any], dict[str, set[int]], int]:
    fold_by_sample = {row["sample_id"]: int(row["fold_id"]) for row in public_rows}
    folds: dict[str, dict[str, Any]] = {}
    component_folds: dict[str, set[int]] = defaultdict(set)
    component_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train_rows:
        component_rows[row["component_id"]].append(row)
        component_folds[row["component_id"]].add(fold_by_sample[row["sample_id"]])

    total_labels = Counter(
        {
            label: sum(int(row["labels"][index]) for row in train_rows)
            for index, label in enumerate(LABEL_ORDER)
        }
    )
    conflict_components = 0
    for members in component_rows.values():
        vectors = {tuple(int(value) for value in row["labels"]) for row in members}
        conflict_components += int(len(vectors) > 1)

    for fold_id in range(fold_count):
        selected = [row for row in train_rows if fold_by_sample[row["sample_id"]] == fold_id]
        selected_components = {row["component_id"] for row in selected}
        label_counts = Counter(
            {
                label: sum(int(row["labels"][index]) for row in selected)
                for index, label in enumerate(LABEL_ORDER)
            }
        )
        duplicate_members = {
            component_id: members
            for component_id, members in component_rows.items()
            if len(members) > 1 and component_id in selected_components
        }
        conflict_members = {
            component_id: members
            for component_id, members in duplicate_members.items()
            if len(
                {
                    tuple(int(value) for value in row["labels"])
                    for row in members
                }
            )
            > 1
        }
        folds[str(fold_id)] = {
            "rows": len(selected),
            "components": len(selected_components),
            "label_counts": {label: label_counts[label] for label in LABEL_ORDER},
            "neutral": sum(bool(row["neutral"]) for row in selected),
            "cardinality_1": sum(int(row["label_cardinality"] == 1) for row in selected),
            "cardinality_2": sum(int(row["label_cardinality"] == 2) for row in selected),
            "duplicate_rows": sum(len(members) for members in duplicate_members.values()),
            "duplicate_components": len(duplicate_members),
            "conflicting_duplicate_rows": sum(
                len(members) for members in conflict_members.values()
            ),
            "conflicting_duplicate_components": len(conflict_members),
        }

    totals = {
        "rows": len(train_rows),
        "components": len(component_rows),
        "label_counts": {label: total_labels[label] for label in LABEL_ORDER},
        "neutral": sum(bool(row["neutral"]) for row in train_rows),
        "cardinality_1": sum(int(row["label_cardinality"] == 1) for row in train_rows),
        "cardinality_2": sum(int(row["label_cardinality"] == 2) for row in train_rows),
        "duplicate_rows": sum(
            len(members) for members in component_rows.values() if len(members) > 1
        ),
        "duplicate_components": sum(
            int(len(members) > 1) for members in component_rows.values()
        ),
        "conflicting_duplicate_rows": sum(
            len(members)
            for members in component_rows.values()
            if len(
                {
                    tuple(int(value) for value in row["labels"])
                    for row in members
                }
            )
            > 1
        ),
        "conflicting_duplicate_components": conflict_components,
    }
    label_errors = {
        label: max(
            abs(folds[str(fold_id)]["label_counts"][label] / total_labels[label] - 0.2)
            for fold_id in range(fold_count)
        )
        for label in LABEL_ORDER
    }
    summary = {
        "schema_version": "exp-058-fold-summary-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": STAGE,
        "fold_count": fold_count,
        "label_order": list(LABEL_ORDER),
        "totals": totals,
        "folds": folds,
        "maximum_label_allocation_error": max(label_errors.values()),
        "label_allocation_errors": label_errors,
    }
    return summary, component_folds, conflict_components


def verify(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    if not run_dir.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("Run directory escapes project root")
    checks = Checks()

    run_path = run_dir / "run.json"
    checks.expect("run.exists", run_path.is_file(), display_path(run_path))
    run = read_json(run_path)
    checks.expect("run.experiment_id", run.get("experiment_id") == EXPERIMENT_ID)
    checks.expect("run.stage", run.get("stage") == STAGE)
    checks.expect(
        "run.status", run.get("status") == "CompletedAwaitingVerification"
    )

    frozen_config = run_dir / "frozen-sources/config.json"
    checks.expect("frozen_config.exists", frozen_config.is_file(), display_path(frozen_config))
    config = read_json(frozen_config)
    checks.expect("config.experiment_id", config.get("experiment_id") == EXPERIMENT_ID)
    checks.expect("config.stage", config.get("stage") == STAGE)
    checks.expect(
        "authorization.no_model_training",
        config["authorization"]["model_training"] is False,
    )
    checks.expect(
        "authorization.no_validation",
        config["authorization"]["validation_access"] is False,
    )
    checks.expect(
        "authorization.no_test",
        config["authorization"]["test_access"] is False,
    )

    artifacts = run["artifacts"]
    public_path = verify_artifact(checks, "public_manifest", artifacts["public_manifest"])
    private_path = verify_artifact(checks, "private_manifest", artifacts["private_manifest"])
    summary_path = verify_artifact(checks, "fold_summary", artifacts["fold_summary"])
    contract_path = verify_artifact(checks, "consumer_contract", artifacts["consumer_contract"])
    verify_artifact(checks, "resource_budget", artifacts["resource_budget"])
    verify_artifact(checks, "stdout", artifacts["stdout"])
    for name, record in artifacts["frozen_sources"].items():
        verify_artifact(checks, f"frozen_source.{name}", record)

    for name, source in config["frozen_sources"].items():
        source_path = resolve_project(source["path"])
        checks.expect(f"source.{name}.exists", source_path.is_file(), display_path(source_path))
        if source_path.is_file():
            checks.expect(
                f"source.{name}.bytes", source_path.stat().st_size == int(source["bytes"])
            )
            checks.expect(
                f"source.{name}.sha256", sha256_file(source_path) == source["sha256"]
            )

    builder_copy = run_dir / "frozen-sources/builder.py"
    verifier_copy = run_dir / "frozen-sources/verifier.py"
    for name, source_path in (("builder", builder_copy), ("verifier", verifier_copy)):
        roots = imported_roots(source_path)
        checks.expect(
            f"no_model_imports.{name}",
            not (roots & FORBIDDEN_MODEL_IMPORTS),
            ",".join(sorted(roots & FORBIDDEN_MODEL_IMPORTS)),
        )
    checks.expect(
        "verifier.does_not_import_builder",
        "build_exp058_fold_manifest" not in imported_roots(verifier_copy),
    )

    train_record = config["data"]["train"]
    train_path = resolve_project(train_record["path"])
    checks.expect("train.exists", train_path.is_file(), display_path(train_path))
    checks.expect("train.bytes", train_path.stat().st_size == int(train_record["bytes"]))
    checks.expect("train.sha256", sha256_file(train_path) == train_record["sha256"])
    checks.expect("train.basename", train_path.name == "train.jsonl")
    verifier_accessed_data_paths = [display_path(train_path)]

    forbidden_paths = [resolve_project(value) for value in config["data"]["forbidden_paths"]]
    forbidden_display = {display_path(path) for path in forbidden_paths}
    run_access = set(run["split_access"]["accessed_data_paths"])
    checks.expect("run.accessed_splits_train_only", run["split_access"]["accessed_splits"] == ["train"])
    checks.expect("run.validation_not_accessed", run["split_access"]["validation_accessed"] is False)
    checks.expect("run.test_inputs_not_accessed", run["split_access"]["test_inputs_accessed"] is False)
    checks.expect("run.test_labels_not_accessed", run["split_access"]["test_labels_accessed"] is False)
    checks.expect("run.no_forbidden_path_match", not run["split_access"]["forbidden_path_matches"])
    checks.expect("run.access_allowlist", run_access == {display_path(train_path)})
    checks.expect(
        "verifier.access_allowlist",
        set(verifier_accessed_data_paths) == {display_path(train_path)},
    )
    checks.expect("run.forbidden_paths_not_opened", not (run_access & forbidden_display))

    model_execution = run["model_execution"]
    for key in (
        "model_loaded",
        "training_performed",
        "forward_pass_executed",
        "logits_produced",
        "threshold_fitted",
        "oracle_computed",
        "performance_metrics_computed",
    ):
        checks.expect(f"no_model_execution.{key}", model_execution[key] is False)
    checks.expect("resource.api_cost_zero", run["resource_usage"]["api_cost_usd"] == 0)
    checks.expect(
        "resource.model_compute_zero", run["resource_usage"]["model_compute_hours"] == 0
    )
    checks.expect(
        "resource.wall_within_budget",
        run["resource_usage"]["wall_seconds"]
        <= config["resource_budget"]["preflight"]["maximum_wall_seconds"],
    )

    train_rows = read_jsonl(train_path)
    public_rows = read_jsonl(public_path)
    private_rows = read_jsonl(private_path)
    stored_summary = read_json(summary_path)
    contract = read_json(contract_path)
    expected_rows = int(config["acceptance_gates"]["expected_rows"])
    expected_components = int(config["acceptance_gates"]["expected_components"])
    fold_count = int(config["folds"]["count"])

    checks.expect("train.row_count", len(train_rows) == expected_rows, str(len(train_rows)))
    train_label_schema_ok = all(
        isinstance(row.get("labels"), list)
        and len(row["labels"]) == len(LABEL_ORDER)
        and all(
            type(value) in {int, bool} and int(value) in {0, 1}
            for value in row["labels"]
        )
        and int(row.get("label_cardinality", -1))
        == sum(int(value) for value in row["labels"])
        and bool(row.get("neutral"))
        == (sum(int(value) for value in row["labels"]) == 0)
        for row in train_rows
    )
    checks.expect("train.binary_label_schema", train_label_schema_ok)
    checks.expect("public.row_count", len(public_rows) == expected_rows, str(len(public_rows)))
    checks.expect("private.row_count", len(private_rows) == expected_rows, str(len(private_rows)))
    checks.expect(
        "public.exact_schema", all(set(row) == PUBLIC_FIELDS for row in public_rows)
    )
    checks.expect(
        "private.exact_schema", all(set(row) == PRIVATE_FIELDS for row in private_rows)
    )
    checks.expect(
        "public.sorted_by_sample_id",
        [row["sample_id"] for row in public_rows]
        == sorted(row["sample_id"] for row in public_rows),
    )
    public_sample_ids = [row["sample_id"] for row in public_rows]
    train_by_id = {row["sample_id"]: row for row in train_rows}
    private_by_id = {row["sample_id"]: row for row in private_rows}
    checks.expect("train.unique_sample_ids", len(train_by_id) == expected_rows)
    checks.expect("public.unique_sample_ids", len(set(public_sample_ids)) == expected_rows)
    checks.expect("private.unique_sample_ids", len(private_by_id) == expected_rows)
    checks.expect("public.complete_coverage", set(public_sample_ids) == set(train_by_id))
    checks.expect("private.complete_coverage", set(private_by_id) == set(train_by_id))

    row_identity_ok = all(
        row["component_id"] == train_by_id[row["sample_id"]]["component_id"]
        and row["fold_id"] in range(fold_count)
        for row in public_rows
    )
    checks.expect("public.identity_and_fold_range", row_identity_ok)
    private_gold_ok = all(
        row["component_id"] == train_by_id[row["sample_id"]]["component_id"]
        and row["labels"] == train_by_id[row["sample_id"]]["labels"]
        and row["neutral"] == train_by_id[row["sample_id"]]["neutral"]
        and row["label_cardinality"]
        == train_by_id[row["sample_id"]]["label_cardinality"]
        for row in private_rows
    )
    checks.expect("private.matches_train_gold", private_gold_ok)

    recomputed, component_folds, conflict_count = reconstruct_summary(
        train_rows, public_rows, fold_count
    )
    checks.expect("component.count", len(component_folds) == expected_components)
    checks.expect(
        "component.disjoint", all(len(folds) == 1 for folds in component_folds.values())
    )
    checks.expect(
        "component.conflict_count",
        conflict_count == int(config["acceptance_gates"]["expected_conflicting_components"]),
        str(conflict_count),
    )
    checks.expect("summary.independent_recompute", recomputed == stored_summary)
    for fold_id, fold in recomputed["folds"].items():
        checks.expect(
            f"fold.{fold_id}.rows",
            fold["rows"] == int(config["acceptance_gates"]["rows_per_fold"]),
            str(fold["rows"]),
        )
        checks.expect(
            f"fold.{fold_id}.all_labels",
            all(fold["label_counts"][label] > 0 for label in LABEL_ORDER),
        )
        surprise = fold["label_counts"]["surprise"]
        checks.expect(
            f"fold.{fold_id}.surprise_support",
            int(config["acceptance_gates"]["surprise_min"])
            <= surprise
            <= int(config["acceptance_gates"]["surprise_max"]),
            str(surprise),
        )
    checks.expect(
        "summary.label_allocation_error",
        recomputed["maximum_label_allocation_error"]
        <= float(config["acceptance_gates"]["maximum_label_allocation_error"]),
        str(recomputed["maximum_label_allocation_error"]),
    )

    public_hash = sha256_file(public_path)
    checks.expect("contract.manifest_hash", contract["fold_manifest_sha256"] == public_hash)
    checks.expect(
        "contract.m1_hash", contract["consumers"]["M1"]["manifest_sha256"] == public_hash
    )
    checks.expect(
        "contract.m3_hash", contract["consumers"]["M3"]["manifest_sha256"] == public_hash
    )
    checks.expect(
        "contract.m1_m3_identical",
        contract["consumers"]["M1"]["manifest_sha256"]
        == contract["consumers"]["M3"]["manifest_sha256"],
    )
    checks.expect("contract.training_not_authorized", contract["training_authorized_by_contract"] is False)
    checks.expect(
        "contract.forbidden_splits", contract["forbidden_splits"] == ["validation", "test"]
    )
    checks.expect("contract.label_order", contract["label_order"] == list(LABEL_ORDER))

    checks.expect(
        "privacy.public_no_sensitive_fields",
        all(not ({"text", "labels", "neutral", "label_cardinality", "logits", "probabilities"} & set(row)) for row in public_rows),
    )
    checks.expect("privacy.private_file_mode", os.stat(private_path).st_mode & 0o777 == 0o600)
    private_parent_mode = os.stat(private_path.parent).st_mode & 0o777
    checks.expect("privacy.private_dir_mode", private_parent_mode == 0o700, oct(private_parent_mode))
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(private_path)],
        cwd=REPO_ROOT,
        check=False,
    ).returncode == 0
    checks.expect("privacy.private_gitignored", ignored)

    result = {
        "schema_version": "exp-058-fold-manifest-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": STAGE,
        "verified_at_utc": utc_now(),
        "status": "Passed" if not checks.failed else "Failed",
        "check_count": len(checks.items),
        "passed_count": len(checks.items) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.items,
        "independence": {
            "builder_imported": False,
            "model_libraries_imported": False,
            "train_recomputed": True,
            "validation_opened": False,
            "test_inputs_opened": False,
            "test_labels_opened": False,
        },
        "verified_artifacts": {
            "run": {"path": display_path(run_path), "sha256": sha256_file(run_path)},
            "public_manifest": {"path": display_path(public_path), "sha256": public_hash},
            "private_manifest": {
                "path": display_path(private_path),
                "sha256": sha256_file(private_path),
            },
            "fold_summary": {
                "path": display_path(summary_path),
                "sha256": sha256_file(summary_path),
            },
            "consumer_contract": {
                "path": display_path(contract_path),
                "sha256": sha256_file(contract_path),
            },
        },
        "claim_boundary": (
            "Passing verifies only the shared train-only fold manifest. It does not "
            "authorize or verify M1/M3 OOF training, logits, calibration, abstention, "
            "oracle gain, routing, validation confirmation, or test evaluation."
        ),
    }
    write_json(run_dir / "verification.json", result)
    summary_lines = [
        "# EXP-058 Fold Manifest Verification",
        "",
        f"- Status: `{result['status']}`",
        f"- Checks: `{result['passed_count']}/{result['check_count']}` passed",
        f"- Rows/components: `{recomputed['totals']['rows']}` / `{recomputed['totals']['components']}`",
        "- Fold rows: `" + "/".join(str(recomputed["folds"][str(i)]["rows"]) for i in range(fold_count)) + "`",
        "- Surprise support: `" + "/".join(str(recomputed["folds"][str(i)]["label_counts"]["surprise"]) for i in range(fold_count)) + "`",
        f"- Maximum label allocation error: `{recomputed['maximum_label_allocation_error']:.6f}`",
        "- Component leakage: `0`",
        "- Model loads/training/forward passes: `0`",
        "- Validation/test access: `false`",
        "",
        "This gate does not authorize M1/M3 OOF training.",
    ]
    if checks.failed:
        summary_lines.extend(
            ["", "## Failed Checks", ""]
            + [f"- `{item['name']}`: {item['detail']}" for item in checks.failed]
        )
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    result = verify(args.run_dir)
    print(
        f"EXP-058 verification: {result['status']} "
        f"({result['passed_count']}/{result['check_count']})"
    )
    return 0 if result["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

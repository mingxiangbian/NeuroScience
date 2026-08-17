#!/usr/bin/env python3
"""Build the train-only EXP-058 five-fold manifest without loading a model."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import time
from typing import Any, Iterable


EXPERIMENT_ID = "EXP-058"
STAGE = "fold-manifest-preflight"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
BALANCE_SLICES = (
    "neutral",
    "cardinality_1",
    "cardinality_2",
    "component_count",
    "duplicate_rows",
    "duplicate_components",
    "conflicting_duplicate_rows",
    "conflicting_duplicate_components",
)
STRATA_ORDER = LABEL_ORDER + BALANCE_SLICES
PUBLIC_FIELDS = (
    "schema_version",
    "protocol_id",
    "experiment_id",
    "sample_id",
    "component_id",
    "fold_id",
)
PRIVATE_FIELDS = PUBLIC_FIELDS + ("labels", "neutral", "label_cardinality")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = (
    SCRIPT_DIR / "configs/exp-058-fold-manifest-preflight-attempt-2.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Non-object JSONL record at {path}:{line_number}")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def write_jsonl(
    path: Path, rows: Iterable[dict[str, Any]], *, private: bool = False
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": display_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def require_source(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"Frozen source byte drift: {path}")
    if sha256_file(path) != record["sha256"]:
        raise ValueError(f"Frozen source SHA-256 drift: {path}")
    return path


def validate_train_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    expected_rows = int(config["data"]["expected_rows"])
    if len(rows) != expected_rows:
        raise ValueError(f"Train row count changed: {len(rows)} != {expected_rows}")

    sample_ids: set[str] = set()
    for index, row in enumerate(rows):
        required = {
            "sample_id",
            "component_id",
            "labels",
            "neutral",
            "label_cardinality",
            "text",
        }
        if not required.issubset(row):
            raise ValueError(f"Train row {index} missing fields: {required - set(row)}")
        sample_id = row["sample_id"]
        component_id = row["component_id"]
        if not isinstance(sample_id, str) or not sample_id.startswith("sample-"):
            raise ValueError(f"Invalid sample ID at train row {index}")
        if not isinstance(component_id, str) or not component_id.startswith("component-"):
            raise ValueError(f"Invalid component ID at train row {index}")
        if sample_id in sample_ids:
            raise ValueError(f"Duplicate sample ID: {sample_id}")
        sample_ids.add(sample_id)

        labels = row["labels"]
        if (
            not isinstance(labels, list)
            or len(labels) != len(LABEL_ORDER)
            or any(type(value) not in {int, bool} or int(value) not in {0, 1} for value in labels)
        ):
            raise ValueError(f"Invalid labels at train row {index}")
        cardinality = sum(int(value) for value in labels)
        if int(row["label_cardinality"]) != cardinality:
            raise ValueError(f"Label cardinality mismatch at train row {index}")
        if bool(row["neutral"]) != (cardinality == 0):
            raise ValueError(f"Neutral flag mismatch at train row {index}")


def build_components(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["component_id"]].append(row)

    components: list[dict[str, Any]] = []
    for component_id, members in grouped.items():
        members = sorted(members, key=lambda row: row["sample_id"])
        vectors = {tuple(int(value) for value in row["labels"]) for row in members}
        conflict = len(vectors) > 1
        size = len(members)
        strata: Counter[str] = Counter()
        for row in members:
            for label, value in zip(LABEL_ORDER, row["labels"], strict=True):
                strata[label] += int(value)
            strata["neutral"] += int(row["neutral"])
            strata[f"cardinality_{row['label_cardinality']}"] += 1
        strata["component_count"] = 1
        strata["duplicate_rows"] = size if size > 1 else 0
        strata["duplicate_components"] = int(size > 1)
        strata["conflicting_duplicate_rows"] = size if conflict else 0
        strata["conflicting_duplicate_components"] = int(conflict)
        components.append(
            {
                "component_id": component_id,
                "rows": members,
                "row_count": size,
                "conflict": conflict,
                "strata": strata,
            }
        )
    return sorted(components, key=lambda value: value["component_id"])


def total_strata(components: list[dict[str, Any]]) -> Counter[str]:
    totals: Counter[str] = Counter()
    for component in components:
        totals.update(component["strata"])
    return totals


def state_cost(
    rows: int,
    strata: Counter[str],
    *,
    target_rows: int,
    totals: Counter[str],
    fold_count: int,
) -> float:
    cost = 4096.0 * ((rows - target_rows) / max(target_rows, 1)) ** 2
    for name in STRATA_ORDER:
        target = totals[name] / fold_count
        if name == "surprise":
            weight = 512.0
        elif name in LABEL_ORDER:
            weight = 48.0
        elif name in {
            "conflicting_duplicate_rows",
            "conflicting_duplicate_components",
        }:
            weight = 128.0
        elif name in {"duplicate_rows", "duplicate_components"}:
            weight = 48.0
        else:
            weight = 24.0
        cost += weight * ((strata[name] - target) / max(target, 2.0)) ** 2
    return cost


def subtract_add(
    current: Counter[str], remove: Counter[str], add: Counter[str]
) -> Counter[str]:
    value = current.copy()
    value.subtract(remove)
    value.update(add)
    return value


def allocate_components(
    components: list[dict[str, Any]], *, fold_count: int, seed: int
) -> dict[str, int]:
    total_rows = sum(component["row_count"] for component in components)
    if total_rows % fold_count:
        raise ValueError("Exact equal folds require row count divisible by fold count")
    target_rows = total_rows // fold_count
    totals = total_strata(components)
    states = {
        fold_id: {"rows": 0, "strata": Counter()} for fold_id in range(fold_count)
    }
    assignments: dict[str, int] = {}

    ordered = sorted(
        components,
        key=lambda component: (
            component["row_count"] == 1,
            -int(component["conflict"]),
            -component["row_count"],
            -sum(
                component["strata"][label] / max(totals[label], 1)
                for label in LABEL_ORDER
            ),
            stable_hash(f"{seed}:order:{component['component_id']}"),
        ),
    )

    for component in ordered:
        candidates: list[tuple[float, str, int]] = []
        for fold_id in range(fold_count):
            state = states[fold_id]
            after_rows = state["rows"] + component["row_count"]
            if after_rows > target_rows:
                continue
            before = state_cost(
                state["rows"],
                state["strata"],
                target_rows=target_rows,
                totals=totals,
                fold_count=fold_count,
            )
            after = state_cost(
                after_rows,
                state["strata"] + component["strata"],
                target_rows=target_rows,
                totals=totals,
                fold_count=fold_count,
            )
            tie = stable_hash(f"{seed}:assign:{component['component_id']}:{fold_id}")
            candidates.append((after - before, tie, fold_id))
        if not candidates:
            raise RuntimeError(
                f"No fold has capacity for component {component['component_id']}"
            )
        _, _, chosen = min(candidates)
        assignments[component["component_id"]] = chosen
        states[chosen]["rows"] += component["row_count"]
        states[chosen]["strata"].update(component["strata"])

    actual_rows = {fold_id: state["rows"] for fold_id, state in states.items()}
    if set(actual_rows.values()) != {target_rows}:
        raise RuntimeError(f"Allocator did not produce exact row counts: {actual_rows}")

    by_size: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for component in components:
        by_size[component["row_count"]].append(component)
    refinable_sizes = [size for size, values in by_size.items() if len(values) >= 2]
    rng = random.Random(seed)
    iterations = min(250_000, max(80_000, len(components) * 60))
    for _ in range(iterations):
        size = rng.choice(refinable_sizes)
        left, right = rng.sample(by_size[size], 2)
        left_fold = assignments[left["component_id"]]
        right_fold = assignments[right["component_id"]]
        if left_fold == right_fold:
            continue
        before = state_cost(
            states[left_fold]["rows"],
            states[left_fold]["strata"],
            target_rows=target_rows,
            totals=totals,
            fold_count=fold_count,
        ) + state_cost(
            states[right_fold]["rows"],
            states[right_fold]["strata"],
            target_rows=target_rows,
            totals=totals,
            fold_count=fold_count,
        )
        left_strata = subtract_add(
            states[left_fold]["strata"], left["strata"], right["strata"]
        )
        right_strata = subtract_add(
            states[right_fold]["strata"], right["strata"], left["strata"]
        )
        after = state_cost(
            states[left_fold]["rows"],
            left_strata,
            target_rows=target_rows,
            totals=totals,
            fold_count=fold_count,
        ) + state_cost(
            states[right_fold]["rows"],
            right_strata,
            target_rows=target_rows,
            totals=totals,
            fold_count=fold_count,
        )
        if after + 1e-12 >= before:
            continue
        assignments[left["component_id"]] = right_fold
        assignments[right["component_id"]] = left_fold
        states[left_fold]["strata"] = left_strata
        states[right_fold]["strata"] = right_strata
    return assignments


def fold_summary(
    components: list[dict[str, Any]], assignments: dict[str, int], fold_count: int
) -> dict[str, Any]:
    totals = total_strata(components)
    summary: dict[str, Any] = {}
    for fold_id in range(fold_count):
        selected = [
            component
            for component in components
            if assignments[component["component_id"]] == fold_id
        ]
        strata: Counter[str] = Counter()
        for component in selected:
            strata.update(component["strata"])
        summary[str(fold_id)] = {
            "rows": sum(component["row_count"] for component in selected),
            "components": len(selected),
            "label_counts": {label: strata[label] for label in LABEL_ORDER},
            "neutral": strata["neutral"],
            "cardinality_1": strata["cardinality_1"],
            "cardinality_2": strata["cardinality_2"],
            "duplicate_rows": strata["duplicate_rows"],
            "duplicate_components": strata["duplicate_components"],
            "conflicting_duplicate_rows": strata["conflicting_duplicate_rows"],
            "conflicting_duplicate_components": strata[
                "conflicting_duplicate_components"
            ],
        }

    label_errors = {
        label: max(
            abs(summary[str(fold_id)]["label_counts"][label] / totals[label] - 0.2)
            for fold_id in range(fold_count)
        )
        for label in LABEL_ORDER
    }
    return {
        "schema_version": "exp-058-fold-summary-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": STAGE,
        "fold_count": fold_count,
        "label_order": list(LABEL_ORDER),
        "totals": {
            "rows": sum(component["row_count"] for component in components),
            "components": len(components),
            "label_counts": {label: totals[label] for label in LABEL_ORDER},
            "neutral": totals["neutral"],
            "cardinality_1": totals["cardinality_1"],
            "cardinality_2": totals["cardinality_2"],
            "duplicate_rows": totals["duplicate_rows"],
            "duplicate_components": totals["duplicate_components"],
            "conflicting_duplicate_rows": totals["conflicting_duplicate_rows"],
            "conflicting_duplicate_components": totals[
                "conflicting_duplicate_components"
            ],
        },
        "folds": summary,
        "maximum_label_allocation_error": max(label_errors.values()),
        "label_allocation_errors": label_errors,
    }


def assert_acceptance(summary: dict[str, Any], config: dict[str, Any]) -> None:
    gates = config["acceptance_gates"]
    expected_rows_per_fold = int(gates["rows_per_fold"])
    for fold_id, fold in summary["folds"].items():
        if fold["rows"] != expected_rows_per_fold:
            raise RuntimeError(f"Fold {fold_id} row gate failed")
        if any(fold["label_counts"][label] <= 0 for label in LABEL_ORDER):
            raise RuntimeError(f"Fold {fold_id} is missing a label")
        surprise = fold["label_counts"]["surprise"]
        if not int(gates["surprise_min"]) <= surprise <= int(gates["surprise_max"]):
            raise RuntimeError(f"Fold {fold_id} surprise support gate failed: {surprise}")
    if summary["totals"]["rows"] != int(gates["expected_rows"]):
        raise RuntimeError("Total row gate failed")
    if summary["totals"]["components"] != int(gates["expected_components"]):
        raise RuntimeError("Total component gate failed")
    if summary["totals"]["conflicting_duplicate_components"] != int(
        gates["expected_conflicting_components"]
    ):
        raise RuntimeError("Conflicting-component count gate failed")
    if summary["maximum_label_allocation_error"] > float(
        gates["maximum_label_allocation_error"]
    ):
        raise RuntimeError("Label allocation error gate failed")


def git_info() -> dict[str, Any]:
    def capture(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    status = capture("status", "--short")
    return {
        "branch": capture("branch", "--show-current"),
        "commit": capture("rev-parse", "HEAD"),
        "dirty": bool(status),
        "dirty_path_count": len(status.splitlines()) if status else 0,
    }


def freeze_sources(
    config_path: Path, config: dict[str, Any], frozen_root: Path
) -> dict[str, Any]:
    frozen_root.mkdir(parents=True, exist_ok=False)
    sources = {"config": config_path}
    sources.update(
        {name: require_source(record) for name, record in config["frozen_sources"].items()}
    )
    output: dict[str, Any] = {}
    for name, source in sources.items():
        suffix = "".join(source.suffixes) or ".txt"
        destination = frozen_root / f"{name}{suffix}"
        shutil.copy2(source, destination)
        output[name] = artifact(destination)
    return output


def build(config_path: Path) -> Path:
    started_at = utc_now()
    started = time.perf_counter()
    config = read_json(config_path)
    if config["experiment_id"] != EXPERIMENT_ID or config["stage"] != STAGE:
        raise ValueError("Wrong experiment or stage in config")
    if config["authorization"]["model_training"]:
        raise ValueError("Manifest preflight config cannot authorize model training")

    train_path = require_source(config["data"]["train"])
    if train_path.name != "train.jsonl":
        raise ValueError("EXP-058 preflight accepts only train.jsonl")
    forbidden = [resolve_project(value) for value in config["data"]["forbidden_paths"]]
    if train_path in forbidden:
        raise ValueError("Train path appears in forbidden path list")

    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    private_dir = resolve_project(config["outputs"]["private_dir"])
    if run_dir.exists() or private_dir.exists():
        raise FileExistsError("EXP-058 output directory already exists")
    run_dir.mkdir(parents=True, mode=0o755)
    private_dir.mkdir(parents=True, mode=0o700)

    accessed_data_paths = [train_path]
    rows = read_jsonl(train_path)
    validate_train_rows(rows, config)
    components = build_components(rows)
    assignments = allocate_components(
        components,
        fold_count=int(config["folds"]["count"]),
        seed=int(config["folds"]["assignment_seed"]),
    )
    summary = fold_summary(components, assignments, int(config["folds"]["count"]))
    assert_acceptance(summary, config)

    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda value: value["sample_id"]):
        base = {
            "schema_version": "exp-058-fold-row-v1",
            "protocol_id": config["data"]["protocol_id"],
            "experiment_id": EXPERIMENT_ID,
            "sample_id": row["sample_id"],
            "component_id": row["component_id"],
            "fold_id": assignments[row["component_id"]],
        }
        public_rows.append(base)
        private_rows.append(
            {
                **base,
                "labels": list(row["labels"]),
                "neutral": bool(row["neutral"]),
                "label_cardinality": int(row["label_cardinality"]),
            }
        )

    public_manifest = run_dir / "fold-manifest.public.jsonl"
    private_manifest = private_dir / "fold-manifest.private.jsonl"
    summary_path = run_dir / "fold-summary.json"
    write_jsonl(public_manifest, public_rows)
    write_jsonl(private_manifest, private_rows, private=True)
    write_json(summary_path, summary)

    manifest_hash = sha256_file(public_manifest)
    consumer_contract = {
        "schema_version": "exp-058-oof-consumer-contract-v1",
        "experiment_id": EXPERIMENT_ID,
        "data_protocol": config["data"]["protocol_id"],
        "train_sha256": config["data"]["train"]["sha256"],
        "fold_manifest_sha256": manifest_hash,
        "fold_count": config["folds"]["count"],
        "fold_assignment_seed": config["folds"]["assignment_seed"],
        "model_seed": config["folds"]["model_seed"],
        "label_order": list(LABEL_ORDER),
        "consumers": {
            "M1": {"manifest_sha256": manifest_hash, "authorized": False},
            "M3": {"manifest_sha256": manifest_hash, "authorized": False},
        },
        "forbidden_splits": ["validation", "test"],
        "training_authorized_by_contract": False,
    }
    contract_path = run_dir / "consumer-contract.json"
    write_json(contract_path, consumer_contract)

    resource_budget_path = run_dir / "resource-budget.json"
    write_json(resource_budget_path, config["resource_budget"])
    stdout_path = run_dir / "stdout.log"
    stdout_path.write_text(
        "\n".join(
            [
                "EXP-058 fold-manifest preflight completed.",
                f"Rows: {summary['totals']['rows']}",
                f"Components: {summary['totals']['components']}",
                f"Public manifest SHA-256: {manifest_hash}",
                "Model loading/training/forward passes: 0",
                "Validation/test access: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    frozen_sources = freeze_sources(config_path, config, run_dir / "frozen-sources")
    completed_at = utc_now()
    elapsed = time.perf_counter() - started
    access_values = [display_path(path) for path in accessed_data_paths]
    forbidden_access = sorted(
        display_path(path) for path in forbidden if path in accessed_data_paths
    )
    run = {
        "schema_version": "exp-058-fold-manifest-preflight-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "tier": "Major infrastructure gate",
        "rq_id": "RQ-S3",
        "stage": STAGE,
        "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "command": config["command"],
        "working_directory": str(REPO_ROOT),
        "git": git_info(),
        "data": {
            "protocol_id": config["data"]["protocol_id"],
            "train": config["data"]["train"],
            "rows": summary["totals"]["rows"],
            "components": summary["totals"]["components"],
            "label_order": list(LABEL_ORDER),
        },
        "folds": {
            "count": config["folds"]["count"],
            "assignment_seed": config["folds"]["assignment_seed"],
            "model_seed": config["folds"]["model_seed"],
            "rows_per_fold": config["acceptance_gates"]["rows_per_fold"],
            "manifest_sha256": manifest_hash,
            "m1_m3_shared_manifest": True,
        },
        "authorization": config["authorization"],
        "model_execution": {
            "model_loaded": False,
            "training_performed": False,
            "forward_pass_executed": False,
            "logits_produced": False,
            "threshold_fitted": False,
            "oracle_computed": False,
            "performance_metrics_computed": False,
        },
        "split_access": {
            "accessed_data_paths": access_values,
            "accessed_splits": ["train"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
            "forbidden_path_matches": forbidden_access,
        },
        "privacy": {
            "public_manifest_fields": list(PUBLIC_FIELDS),
            "private_manifest_fields": list(PRIVATE_FIELDS),
            "public_raw_text": False,
            "public_gold": False,
            "private_mode": "0600",
        },
        "resource_usage": {
            "wall_seconds": elapsed,
            "api_cost_usd": 0,
            "model_compute_hours": 0,
        },
        "resource_budget": config["resource_budget"],
        "artifacts": {
            "public_manifest": artifact(public_manifest),
            "private_manifest": artifact(private_manifest),
            "fold_summary": artifact(summary_path),
            "consumer_contract": artifact(contract_path),
            "resource_budget": artifact(resource_budget_path),
            "stdout": artifact(stdout_path),
            "frozen_sources": frozen_sources,
        },
        "next_gate": "Independent verification; M1/M3 OOF training remains unauthorized",
    }
    write_json(run_dir / "run.json", run)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    run_dir = build(args.config.resolve())
    print(f"EXP-058 fold manifest written to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

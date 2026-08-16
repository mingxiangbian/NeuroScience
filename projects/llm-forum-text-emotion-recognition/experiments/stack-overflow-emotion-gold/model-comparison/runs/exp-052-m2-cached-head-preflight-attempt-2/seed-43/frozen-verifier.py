#!/usr/bin/env python3
"""Independently verify an EXP-052 cached-head preflight or formal run."""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import traceback
from typing import Any, Sequence

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]


def load_sibling(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load sibling module: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_sibling("exp052_cached_runner", "run_exp052_m2_cached_head.py")
prior_verifier = load_sibling("exp052_prior_verifier", "verify_exp052_m2.py")
LABELS = runner.LABELS
TOLERANCE = 1e-12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path)
    return parser.parse_args()


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact(record: dict[str, Any]) -> Path:
    path = runner.resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"Artifact byte-size drift: {path}")
    if sha256_file(path) != record["sha256"]:
        raise ValueError(f"Artifact hash drift: {path}")
    return path


def source_access_audit(path: Path) -> dict[str, bool]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    load_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "load"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "np"
    ]
    mmap_read_only = bool(load_calls) and all(
        any(
            keyword.arg == "mmap_mode"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "r"
            for keyword in call.keywords
        )
        for call in load_calls
    )
    loader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_split_rows"
    )
    loader_source = ast.get_source_segment(source, loader) or ""
    return {
        "explicit_train_validation_allowlist": "split not in ALLOWED_SPLITS" in loader_source,
        "no_test_path_lookup": "test_path" not in source,
        "no_recursive_data_access": ".rglob(" not in loader_source and ".glob(" not in loader_source,
        "no_qwen_or_transformers_import": not any(
            name == "mlx_lm" or name.startswith("transformers") for name in imports
        ),
        "read_only_memmap": mmap_read_only,
    }


def gitignored(path: Path) -> bool:
    return subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False
    ).returncode == 0


def load_split_rows(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in runner.ALLOWED_SPLITS:
        raise PermissionError(f"Cached-head verifier cannot access split: {split}")
    data = shared["data"]
    path = runner.resolve_project(data[f"{split}_path"])
    if sha256_file(path) != data[f"{split}_sha256"]:
        raise ValueError(f"{split} data hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != int(data[f"{split}_rows"]):
        raise ValueError(f"{split} row-count drift")
    return rows


def public_privacy_check(
    run_dir: Path, rows: Sequence[dict[str, Any]]
) -> tuple[bool, bool]:
    sample_ids = {row["sample_id"] for row in rows}
    texts = {row["text"] for row in rows if len(row["text"]) >= 24}
    no_text = True
    no_ids = True
    for path in run_dir.iterdir():
        if not path.is_file() or path.name.startswith("frozen-") or path.suffix == ".npy":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        no_text = no_text and not any(text in content for text in texts)
        no_ids = no_ids and not any(sample_id in content for sample_id in sample_ids)
    return no_text, no_ids


def compare_metrics(
    name: str, observed: dict[str, Any], recorded: dict[str, Any]
) -> None:
    prior_verifier.compare_metrics(name, observed, recorded)


def render_summary(verification: dict[str, Any], run: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {run['stage']} Verification",
            "",
            f"- Status: `{verification['status']}`",
            f"- Checks: `{verification['check_count']}/{verification['check_count']}` passed"
            if verification["status"] == "Passed"
            else f"- Failed checks: `{', '.join(verification['failed_checks'])}`",
            "- Qwen loaded or executed: no",
            "- Test accessed: no",
            "",
        ]
    )


def verify() -> dict[str, Any]:
    args = parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    output = run_dir / "verification.json"
    summary_path = run_dir / "VERIFICATION-SUMMARY.md"
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    run_path = run_dir / "run.json"
    if not run_path.is_file():
        raise FileNotFoundError(run_path)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run.get("status") != "Completed":
        verification = {
            "schema_version": "exp-052-m2-cached-head-verification-v1",
            "experiment_id": "EXP-052",
            "stage": run.get("stage"),
            "seed": run.get("seed"),
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "Failed",
            "check_count": 1,
            "failed_checks": ["run completed"],
            "checks": [{"name": "run completed", "passed": False, "detail": run.get("failure")}],
            "test_split_accessed": run.get("test_split_accessed"),
        }
        atomic_json(output, verification)
        summary_path.write_text(render_summary(verification, run), encoding="utf-8")
        raise ValueError("Cannot verify an incomplete cached-head run")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    shared_path = verify_artifact(config["shared_contract"])
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    check("run completed", run["status"] == "Completed")
    check("experiment identity", run["experiment_id"] == config["experiment_id"] == "EXP-052")
    check("stage identity", run["stage"] == config["stage"])
    check("seed identity", run["seed"] == args.seed == 43)
    check("authorization frozen", run["authorization"] == config["authorization"])
    check("train validation only", run["accessed_splits"] == ["train", "validation"])
    check("test sealed", run["test_split_accessed"] is False and config["authorization"]["test_access"] is False)
    check("seed 44 sealed", config["authorization"]["seed_44_authorized"] is False)
    check("M3 and M4 sealed", config["authorization"]["exp_053_054_authorized"] is False)
    check("Qwen not loaded", run["qwen_model_loaded"] is False)
    check("Qwen forward not executed", run["qwen_forward_executed"] is False)
    check("features not extracted", run["feature_extraction_performed"] is False)
    check("zero model-load time", run["resource_usage"]["model_load_seconds"] == 0)
    check("zero Qwen-forward time", run["resource_usage"]["qwen_forward_seconds"] == 0)
    check("zero feature-extraction time", run["resource_usage"]["feature_extraction_seconds"] == 0)

    frozen_config = run_dir / "frozen-config.json"
    check("frozen config", frozen_config.is_file() and sha256_file(frozen_config) == sha256_file(config_path))
    for name, record in config["implementation"].items():
        source = runner.resolve_project(record["path"])
        check(f"implementation hash: {name}", sha256_file(source) == record["sha256"])
        frozen = run_dir / f"frozen-{name}{source.suffix}"
        check(f"frozen implementation: {name}", frozen.is_file() and sha256_file(frozen) == record["sha256"])
    for name, passed in source_access_audit(run_dir / "frozen-runner.py").items():
        check(f"runner source audit: {name}", passed)

    gate_run_path = verify_artifact(config["cache_reuse_gate"]["run"])
    gate_verification_path = verify_artifact(config["cache_reuse_gate"]["verification"])
    gate_run = json.loads(gate_run_path.read_text(encoding="utf-8"))
    gate_verification = json.loads(gate_verification_path.read_text(encoding="utf-8"))
    check("cache gate completed", gate_run["status"] == "Completed")
    check("cache gate 74/74", gate_verification["status"] == "Passed" and gate_verification["check_count"] == 74 and not gate_verification["failed_checks"])
    check("cache gate test sealed", gate_run["test_split_accessed"] is False and gate_verification["test_split_accessed"] is False)

    train_rows = load_split_rows(shared, "train")
    validation_rows = load_split_rows(shared, "validation")
    check("train row count", len(train_rows) == 3360)
    check("validation row count", len(validation_rows) == 720)
    check("component disjoint", not ({row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}))
    check("sample disjoint", not ({row["sample_id"] for row in train_rows} & {row["sample_id"] for row in validation_rows}))

    arrays: dict[str, np.memmap] = {}
    for split, rows in (("train", train_rows), ("validation", validation_rows)):
        expected = config["feature_cache"][split]
        path = verify_artifact(expected["artifact"])
        array = np.load(path, mmap_mode="r", allow_pickle=False)
        arrays[split] = array
        observed_hash = sha256_file(path)
        record = run["feature_cache"][split]
        gate_artifact = runner.compact_artifact(gate_run["feature_cache"][split])
        check(f"{split} gate artifact", expected["artifact"] == gate_artifact)
        check(f"{split} shape", list(array.shape) == expected["shape"] == record["shape"])
        check(f"{split} dtype", array.dtype == np.float32 and record["dtype"] == "float32")
        check(f"{split} read-only mmap", isinstance(array, np.memmap) and not array.flags.writeable and record["mmap_mode"] == "r")
        check(f"{split} finite", np.isfinite(array).all() and record["all_finite"] is True)
        check(f"{split} order", runner.canonical_digest([row["sample_id"] for row in rows]) == expected["sample_order_sha256"] == record["sample_order_sha256"])
        check(f"{split} token stream", expected["token_id_stream_sha256"] == record["token_id_stream_sha256"])
        check(f"{split} hash before and after", record["sha256_before_use"] == record["sha256_after_use"] == observed_hash)
        check(f"{split} cache Git ignored", gitignored(path))

    expected_head = prior_verifier.head_initial_digest(43, 2560)
    check("head initialization independently reproduced", expected_head == config["execution"]["expected_head_initial_sha256"] == run["model_runtime"]["head_initial_sha256"])
    check("fresh head parameter count", run["model_runtime"]["head_trainable_parameter_count"] == 15366)
    expected_orders = runner.make_batch_orders(43, len(train_rows), 2)
    expected_digests = runner.order_digests(train_rows, expected_orders)
    check("batch-order digests", run["batch_order"]["epoch_sha256"] == expected_digests)

    formal = run["stage"] == runner.FORMAL_STAGE
    check("training flag matches stage", run["training_performed"] is formal)
    check("metric flag matches stage", run["performance_metrics_computed"] is formal)
    if not formal:
        check("preflight authorization seals training", config["authorization"]["training_authorized"] is False)
        check("preflight authorization seals metrics", config["authorization"]["performance_metrics_authorized"] is False)
        check("preflight has no metrics", "metrics" not in run)
        check("preflight has no private output", args.private_dir is None)
    else:
        if args.private_dir is None:
            raise ValueError("Formal verification requires --private-dir")
        private_dir = args.private_dir.resolve()
        check("formal authorization permits training", config["authorization"]["training_authorized"] is True)
        check("formal authorization permits validation metrics", config["authorization"]["performance_metrics_authorized"] is True)
        preflight_run = verify_artifact(config["consumer_preflight"]["run"])
        preflight_verification = verify_artifact(config["consumer_preflight"]["verification"])
        preflight_run_value = json.loads(preflight_run.read_text(encoding="utf-8"))
        preflight_verification_value = json.loads(preflight_verification.read_text(encoding="utf-8"))
        check("consumer preflight completed", preflight_run_value["status"] == "Completed" and preflight_run_value["training_performed"] is False)
        check("consumer preflight verified", preflight_verification_value["status"] == "Passed" and not preflight_verification_value["failed_checks"])
        check("consumer preflight test sealed", preflight_run_value["test_split_accessed"] is False and preflight_verification_value["test_split_accessed"] is False)

        orders_path = verify_artifact(run["artifacts"]["batch_orders_private"])
        orders = np.load(orders_path, allow_pickle=False)
        check("private batch orders", np.array_equal(orders, expected_orders))
        check("two epochs and 6720 updates", run["training"]["epochs"] == 2 and run["training"]["total_optimizer_steps"] == 6720)
        for index, digest in enumerate(expected_digests):
            check(f"epoch {index + 1} order digest", run["training"]["history"][index]["batch_order_sha256"] == digest)

        predictions_path = verify_artifact(run["artifacts"]["validation_predictions_private"])
        predictions = np.load(predictions_path, allow_pickle=False)
        probabilities = predictions["probabilities"]
        gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
        component_ids = [row["component_id"] for row in validation_rows]
        check("probability shape", probabilities.shape == (2, 720, 6))
        check("probabilities finite", np.isfinite(probabilities).all())
        check("private gold", np.array_equal(predictions["gold"], gold))
        check("private sample order", predictions["sample_ids"].tolist() == [row["sample_id"] for row in validation_rows])
        check("private component order", predictions["component_ids"].tolist() == component_ids)

        fixed_threshold = float(shared["evaluation"]["fixed_threshold"])
        epoch_metrics = [
            prior_verifier.metric_bundle(gold, (values >= fixed_threshold).astype(np.uint8))
            for values in probabilities
        ]
        history_path = verify_artifact(run["artifacts"]["history"])
        with history_path.open("r", encoding="utf-8", newline="") as source:
            history = list(csv.DictReader(source))
        check("two history rows", len(history) == 2)
        for index, (metrics, row) in enumerate(zip(epoch_metrics, history), start=1):
            check(f"epoch {index} identity", int(row["epoch"]) == index and int(row["optimizer_steps"]) == index * 3360)
            check(f"epoch {index} Macro-F1", math.isclose(metrics["macro"]["f1"], float(row["fixed_macro_f1"]), rel_tol=0.0, abs_tol=TOLERANCE))
            check(f"epoch {index} finite losses", math.isfinite(float(row["train_loss"])) and math.isfinite(float(row["validation_loss"])))
        selection = prior_verifier.independently_select_checkpoint(
            [metrics["macro"]["f1"] for metrics in epoch_metrics],
            float(shared["evaluation"]["practical_tie_delta"]),
        )
        recorded_selection = json.loads(verify_artifact(run["artifacts"]["selection"]).read_text(encoding="utf-8"))
        check("checkpoint selection", selection == recorded_selection == run["selection"])
        selected_probabilities = probabilities[selection["selected_epoch"] - 1]
        selected_head = verify_artifact(run["artifacts"]["selected_head_private"])
        replay = prior_verifier.replay_head(selected_head, arrays["validation"])
        check("selected head replay", float(np.max(np.abs(replay - selected_probabilities))) <= 1e-7)

        selected_threshold, threshold_rows = prior_verifier.independently_select_threshold(
            gold, selected_probabilities, shared["evaluation"]["shared_threshold_grid"]
        )
        check("shared threshold selection", selected_threshold == run["threshold_selection"]["selected_threshold"])
        threshold_path = verify_artifact(run["artifacts"]["threshold_grid"])
        with threshold_path.open("r", encoding="utf-8", newline="") as source:
            recorded_thresholds = list(csv.DictReader(source))
        check("threshold grid length", len(recorded_thresholds) == len(threshold_rows) == 19)
        recorded_bootstrap = json.loads(verify_artifact(run["artifacts"]["bootstrap"]).read_text(encoding="utf-8"))
        for name, threshold, condition in (
            ("fixed_0.5", fixed_threshold, "fixed-0.5"),
            ("shared_threshold", selected_threshold, f"shared-{selected_threshold:.2f}"),
        ):
            predicted = (selected_probabilities >= threshold).astype(np.uint8)
            observed_metrics = prior_verifier.metric_bundle(gold, predicted)
            compare_metrics(name, observed_metrics, run["metrics"][name])
            metrics_key = "metrics_fixed" if name == "fixed_0.5" else "metrics_shared_threshold"
            compare_metrics(name + ".file", observed_metrics, json.loads(verify_artifact(run["artifacts"][metrics_key]).read_text(encoding="utf-8")))
            observed_bootstrap = prior_verifier.bootstrap_summary(
                gold, predicted, component_ids, 43,
                int(shared["evaluation"]["bootstrap"]["replicates"]),
                shared["evaluation"]["bootstrap"]["seed_namespace"], condition,
            )
            prior_verifier.compare_bootstrap(name, observed_bootstrap, recorded_bootstrap[name])
            for kind in ("per_label", "confusion"):
                table_key = "fixed-0.5" if name == "fixed_0.5" else "shared-threshold"
                verify_artifact(run["artifacts"]["tables"][table_key][kind])
        check("private manifest Git ignored", gitignored(private_dir / "private-manifest.json"))
        check("private predictions Git ignored", gitignored(predictions_path))

    all_rows = [*train_rows, *validation_rows]
    no_text, no_ids = public_privacy_check(run_dir, all_rows)
    check("public artifacts contain no substantive raw text", no_text)
    check("public artifacts contain no row identifiers", no_ids)
    check("zero API cost", run["resource_usage"]["api_cost_usd"] == 0)
    check("test remains sealed after verification", run["test_split_accessed"] is False)

    failed = [item["name"] for item in checks if not item["passed"]]
    verification = {
        "schema_version": "exp-052-m2-cached-head-verification-v1",
        "experiment_id": "EXP-052",
        "stage": run["stage"],
        "seed": args.seed,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "Passed" if not failed else "Failed",
        "check_count": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "test_split_accessed": False,
    }
    atomic_json(output, verification)
    summary_path.write_text(render_summary(verification, run), encoding="utf-8")
    if failed:
        raise ValueError(f"EXP-052 cached-head verification failed: {failed}")
    return verification


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), indent=2, sort_keys=True))
    except Exception:
        traceback.print_exc()
        raise

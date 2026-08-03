#!/usr/bin/env python3
"""Run EXP-031 inference-only neutral-ontology ablation on frozen LoRA adapters."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from typing import Any, Iterator

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-031"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-031-neutral-ontology-inference-ablation.json"
PROTOCOL_PATH = SCRIPT_DIR / "protocols" / "exp-031-neutral-ontology-inference-ablation.md"
PARENT_RUNNER_PATH = SCRIPT_DIR / "run_lora.py"
METRICS_PATH = SCRIPT_DIR / "llm_full_dev_metrics.py"
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint_neutral_cooccurrence.py"
VERIFIER_PATH = SCRIPT_DIR / "verify_neutral_ontology_ablation.py"
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"
DEV_PATH = DATA_ROOT / "dev.tsv"
LABELS_PATH = DATA_ROOT / "emotions.txt"
TEST_PATH = DATA_ROOT / "test.tsv"
MODEL_ROOT = PROJECT_ROOT / "models" / "qwen3-1.7b"
MODEL_DIR = MODEL_ROOT / "mlx-bf16"
MODEL_MANIFEST_PATH = MODEL_ROOT / "manifest.json"
PYTHON = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python")
CONDITIONS = (
    "old-prompt-closed-decoder",
    "old-prompt-open-decoder",
    "aligned-prompt-open-decoder",
)
OPEN_CONDITIONS = CONDITIONS[1:]
HISTORICAL_BASELINE = "exp-029-zero-shot-closed-ontology"

sys.path.insert(0, str(SCRIPT_DIR))
import llm_full_dev_metrics as metric_tools
import run_lora as parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("--seed", type=int, choices=(42,), default=42)
    dev = subparsers.add_parser("dev")
    dev.add_argument("--seed", type=int, required=True)
    dev.add_argument("--resume", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(
        f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}"
    )
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def resolve_project_path(value: str) -> Path:
    return PROJECT_ROOT / value


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Frozen hash mismatch for {path}: {actual} != {expected}")


def verify_model_inventory(config: dict[str, Any]) -> None:
    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    inventory = manifest.get("mlx_bf16", {})
    files = inventory.get("files", [])
    if len(files) != int(inventory.get("file_count", -1)):
        raise ValueError("Model manifest file count differs")
    total_bytes = 0
    for entry in files:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Model manifest contains an unsafe path")
        path = MODEL_DIR / relative
        if path.stat().st_size != int(entry["bytes"]):
            raise ValueError(f"Model file size differs: {path}")
        verify_hash(path, entry["sha256"])
        total_bytes += path.stat().st_size
    if total_bytes != int(inventory.get("total_bytes", -1)):
        raise ValueError("Model manifest total bytes differ")
    if manifest.get("revision") != config["model"]["revision"]:
        raise ValueError("Model revision differs from the frozen config")


def verify_environment(config: dict[str, Any]) -> None:
    expected = config["environment"]
    actual_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    if actual_major_minor != expected["python_major_minor"]:
        raise ValueError("Python major/minor version differs")
    for package, expected_version in expected["packages"].items():
        try:
            actual_version = metadata.version(package)
        except metadata.PackageNotFoundError as error:
            raise ValueError(f"Frozen package is missing: {package}") from error
        if actual_version != expected_version:
            raise ValueError(
                f"Package version differs for {package}: {actual_version} != {expected_version}"
            )


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("tier") != "Major"
        or config.get("status") != "Registered"
    ):
        raise ValueError("EXP-031 must remain a registered Major configuration")
    if "PENDING" in json.dumps(config, sort_keys=True):
        raise ValueError("EXP-031 hashes must be frozen before execution")
    seeds = [int(value) for value in config["resource_budget"]["formal_seeds"]]
    if (
        tuple(config["decoding"]["conditions"]) != CONDITIONS
        or set(config["prompts"]) != set(CONDITIONS)
        or seeds != [42, 43, 44]
        or set(config["adapter_inputs"]) != {str(seed) for seed in seeds}
        or int(config["resource_budget"]["dev_conditions_per_seed"])
        != len(CONDITIONS)
        or tuple(config["evaluation"]["comparisons"])
        != (
            "concurrent-closed-minus-historical-closed",
            "old-open-minus-closed",
            "aligned-open-minus-closed",
            "aligned-open-minus-old-open",
        )
        or config["data"]["test_access"] is not False
        or config["evaluation"]["test_gate"] != "closed"
    ):
        raise ValueError("EXP-031 frozen condition, seed, or test policy differs")
    return config


def verify_static_inputs(
    config: dict[str, Any], *, seed: int, include_dev: bool
) -> tuple[str, ...]:
    if TEST_PATH.exists():
        raise FileExistsError(f"GoEmotions test must remain absent: {TEST_PATH}")
    if not PYTHON.is_file() or not MODEL_DIR.is_dir():
        raise FileNotFoundError("Frozen MLX environment or local model is unavailable")
    implementation = config["implementation"]
    checks = [
        (LABELS_PATH, config["data"]["labels_sha256"]),
        (MODEL_MANIFEST_PATH, config["model"]["manifest_sha256"]),
        (PROTOCOL_PATH, config["protocol_sha256"]),
        (Path(__file__).resolve(), implementation["runner_sha256"]),
        (PARENT_RUNNER_PATH, implementation["parent_runner_sha256"]),
        (METRICS_PATH, implementation["metrics_sha256"]),
        (CONSTRAINT_PATH, implementation["constraint_sha256"]),
        (VERIFIER_PATH, implementation["verifier_sha256"]),
        (
            resolve_project_path(config["parent_inputs"]["config_path"]),
            config["parent_inputs"]["config_sha256"],
        ),
        (
            resolve_project_path(config["parent_inputs"]["constraint_path"]),
            config["parent_inputs"]["constraint_sha256"],
        ),
    ]
    for prompt in config["prompts"].values():
        checks.append((resolve_project_path(prompt["path"]), prompt["sha256"]))
    if include_dev:
        checks.append((DEV_PATH, config["data"]["dev_sha256"]))
    seed_spec = config["adapter_inputs"][str(seed)]
    checks.extend(
        [
            (
                resolve_project_path(seed_spec["adapter_config_path"]),
                seed_spec["adapter_config_sha256"],
            ),
            (resolve_project_path(seed_spec["adapter_path"]), seed_spec["adapter_sha256"]),
            (
                resolve_project_path(seed_spec["historical_predictions_path"]),
                seed_spec["historical_predictions_sha256"],
            ),
            (
                resolve_project_path(seed_spec["parent_verification_path"]),
                seed_spec["parent_verification_sha256"],
            ),
        ]
    )
    for path, expected in checks:
        verify_hash(path, expected)
    verify_model_inventory(config)
    verify_environment(config)
    parent_verification = json.loads(
        resolve_project_path(seed_spec["parent_verification_path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        parent_verification.get("experiment_id") != "EXP-029"
        or parent_verification.get("seed") != seed
        or parent_verification.get("status") != "Passed"
        or parent_verification.get("test_absent") is not True
        or parent_verification.get("test_split_accessed") is not False
    ):
        raise ValueError("Parent EXP-029 seed is not independently verified")
    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    if len(labels) != 28 or len(set(labels)) != len(labels):
        raise ValueError("Frozen GoEmotions ontology differs")
    return labels


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def environment_metadata() -> dict[str, Any]:
    packages = {}
    for name in ("mlx", "mlx-lm", "numpy", "transformers"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "packages": packages,
        "python_executable": str(PYTHON),
        "python_version": sys.version,
    }


def hardware_metadata() -> dict[str, Any]:
    return {
        "logical_cpu_count": os.cpu_count(),
        "machine": platform.machine(),
        "macos_version": platform.mac_ver()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
    }


def load_prompt_specs(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        condition: json.loads(
            resolve_project_path(spec["path"]).read_text(encoding="utf-8")
        )
        for condition, spec in config["prompts"].items()
    }


def build_prompt(
    tokenizer: Any,
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
) -> str:
    messages = [
        {
            "role": "system",
            "content": prompt_spec["system_template"].format(
                allowed_labels=", ".join(labels)
            ),
        },
        {
            "role": "user",
            "content": prompt_spec["user_template"].format(text=text),
        },
    ]
    return tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        enable_thinking=False,
        tokenize=False,
    )


def strict_parse(output: str, labels: tuple[str, ...]) -> dict[str, Any]:
    try:
        decoded = json.loads(output.strip())
    except json.JSONDecodeError:
        return {"canonical_output": None, "error": "invalid-json", "labels": []}
    if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
        return {"canonical_output": None, "error": "wrong-object", "labels": []}
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return {"canonical_output": None, "error": "labels-not-nonempty-list", "labels": []}
    if not all(isinstance(value, str) for value in values):
        return {"canonical_output": None, "error": "non-string-label", "labels": []}
    if len(values) != len(set(values)):
        return {"canonical_output": None, "error": "duplicate-label", "labels": []}
    if any(value not in labels for value in values):
        return {"canonical_output": None, "error": "unknown-label", "labels": []}
    return {
        "canonical_output": json.dumps({"labels": values}, separators=(",", ":")),
        "error": None,
        "labels": values,
    }


def make_record(
    row_number: int,
    condition: str,
    gold_label_ids: list[int],
    labels: tuple[str, ...],
    generated: dict[str, Any],
) -> dict[str, Any]:
    output = generated.pop("output")
    parsed = strict_parse(output, labels)
    parser_error = parsed["error"]
    parser_valid = parser_error is None
    if generated["finish_reason"] != "stop":
        parser_valid = False
        parser_error = "length-terminated"
    predicted_labels = parsed["labels"] if parser_valid else []
    label_to_id = {label: index for index, label in enumerate(labels)}
    return {
        "canonical_output": parsed["canonical_output"] if parser_valid else None,
        "condition": condition,
        "constraint_intervened": generated["constraint_intervened"],
        "finish_reason": generated["finish_reason"],
        "first_blocked_step": generated["first_blocked_step"],
        "first_blocked_token_id": generated["first_blocked_token_id"],
        "generated_tokens": generated["generated_tokens"],
        "generation_seconds": generated["generation_seconds"],
        "generation_tps": generated["generation_tps"],
        "gold_label_ids": gold_label_ids,
        "gold_labels": [labels[value] for value in gold_label_ids],
        "output_character_count": len(output),
        "output_sha256": sha256_text(output),
        "parser_error": parser_error,
        "parser_valid": parser_valid,
        "peak_memory_gb": generated["peak_memory_gb"],
        "predicted_label_ids": [label_to_id[label] for label in predicted_labels],
        "predicted_labels": predicted_labels,
        "prompt_tokens": generated["prompt_tokens"],
        "prompt_tps": generated["prompt_tps"],
        "raw_argmax_blocked_steps": generated["raw_argmax_blocked_steps"],
        "row_number": row_number,
        "sequence_logprob_mean": generated["sequence_logprob_mean"],
        "sequence_logprob_sum": generated["sequence_logprob_sum"],
        "sequence_score_space": "condition-specific constrained label-name JSON",
    }


def condition_order(row_number: int) -> tuple[str, ...]:
    offset = (row_number - 1) % len(CONDITIONS)
    return CONDITIONS[offset:] + CONDITIONS[:offset]


def expected_pairs(row_count: int) -> Iterator[tuple[int, str]]:
    for row_number in range(1, row_count + 1):
        for condition in condition_order(row_number):
            yield row_number, condition


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_record_prefix(
    records: list[dict[str, Any]], gold_ids: list[list[int]], row_count: int
) -> None:
    pairs = list(expected_pairs(row_count))
    if len(records) > len(pairs):
        raise ValueError("Generation checkpoint has too many records")
    for index, record in enumerate(records):
        row_number, condition = pairs[index]
        if (
            record["row_number"] != row_number
            or record["condition"] != condition
            or record["gold_label_ids"] != gold_ids[row_number - 1]
        ):
            raise ValueError(f"Generation checkpoint diverges at record {index + 1}")


def append_log(path: Path, message: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {message}"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def finalize_atomically(
    config: dict[str, Any],
    seed: int,
    run_dir: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    gold: Any,
) -> dict[str, Any]:
    analysis_dir = run_dir / "analysis"
    if analysis_dir.is_dir():
        return json.loads(
            (analysis_dir / "aggregate-metrics.json").read_text(encoding="utf-8")
        )
    if analysis_dir.exists():
        raise FileExistsError("EXP-031 analysis path exists but is not a directory")
    private_root = (
        resolve_project_path(config["artifacts"]["private_finalization_root"])
        / f"seed-{seed}"
    )
    private_root.mkdir(parents=True, exist_ok=True)
    attempt_dir = private_root / f"attempt-{time.time_ns()}"
    attempt_dir.mkdir()
    aggregate = finalize_outputs(config, seed, attempt_dir, records, labels, gold)
    os.replace(attempt_dir, analysis_dir)
    return aggregate


def collect_run_artifacts(run_dir: Path) -> dict[str, dict[str, Any]]:
    excluded = {"run.json", "verification.json"}
    return {
        path.relative_to(run_dir).as_posix(): artifact(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name not in excluded
    }


def transition_counts(gold: Any, baseline: Any, treatment: Any, mask: Any) -> dict[str, int]:
    baseline_correct = (baseline[mask] == gold[mask]).all(axis=1)
    treatment_correct = (treatment[mask] == gold[mask]).all(axis=1)
    return {
        "improved": int((~baseline_correct & treatment_correct).sum()),
        "unchanged_correct": int((baseline_correct & treatment_correct).sum()),
        "unchanged_wrong": int((~baseline_correct & ~treatment_correct).sum()),
        "worsened": int((baseline_correct & ~treatment_correct).sum()),
    }


def slice_rows(
    labels: tuple[str, ...], gold: Any, predictions: dict[str, Any]
) -> list[dict[str, Any]]:
    import numpy as np

    neutral_id = labels.index("neutral")
    gold_cardinality = gold.sum(axis=1)
    masks = {
        "all": np.ones(gold.shape[0], dtype=bool),
        "single_label": gold_cardinality == 1,
        "any_multilabel": gold_cardinality > 1,
        "neutral_cooccurrence": (gold[:, neutral_id] == 1) & (gold_cardinality > 1),
        "without_neutral_cooccurrence": ~(
            (gold[:, neutral_id] == 1) & (gold_cardinality > 1)
        ),
    }
    rows: list[dict[str, Any]] = []
    for condition, predicted in predictions.items():
        predicted_cardinality = predicted.sum(axis=1)
        for slice_name, mask in masks.items():
            metrics, _ = metric_tools.compute_metrics(
                gold[mask], predicted[mask], labels
            )
            rows.append(
                {
                    "condition": condition,
                    "exact_match": metrics["subset_accuracy"],
                    "macro_f1": metrics["macro"]["f1"],
                    "neutral_coprediction_rows": int(
                        (
                            (predicted[mask][:, neutral_id] == 1)
                            & (predicted_cardinality[mask] > 1)
                        ).sum()
                    ),
                    "predicted_cardinality_mean": float(
                        predicted_cardinality[mask].mean()
                    ),
                    "row_count": int(mask.sum()),
                    "samples_f1": metrics["samples"]["f1"],
                    "slice": slice_name,
                }
            )
    return rows


def write_slice_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "condition",
        "slice",
        "row_count",
        "macro_f1",
        "exact_match",
        "samples_f1",
        "predicted_cardinality_mean",
        "neutral_coprediction_rows",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: format(value, ".17g") if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )


def finalize_outputs(
    config: dict[str, Any],
    seed: int,
    run_dir: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    gold: Any,
) -> dict[str, Any]:
    predictions: dict[str, Any] = {}
    task_metrics: dict[str, dict[str, Any]] = {}
    generation_metrics: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        condition_records = [row for row in records if row["condition"] == condition]
        if len(condition_records) != gold.shape[0]:
            raise ValueError(f"{condition} record count is incomplete")
        condition_dir = run_dir / condition
        condition_dir.mkdir(parents=True, exist_ok=False)
        predicted = metric_tools.records_to_prediction_matrix(condition_records, labels)
        metrics, confusion = metric_tools.compute_metrics(gold, predicted, labels)
        generation = metric_tools.summarize_generation(condition_records)
        predictions[condition] = predicted
        task_metrics[condition] = metrics
        generation_metrics[condition] = generation
        metric_tools.write_predictions(condition_dir / "predictions.csv", condition_records)
        metric_tools.write_per_label(condition_dir / "per-label-metrics.csv", metrics, labels)
        metric_tools.write_confusion(
            condition_dir / "multilabel-confusion-matrix.csv", confusion, labels
        )
        write_json(
            condition_dir / "metrics.json",
            {"condition": condition, "generation": generation, "task": metrics},
        )
    metric_tools.write_condition_summary(
        run_dir / "condition-summary.csv",
        CONDITIONS,
        task_metrics,
        generation_metrics,
    )

    seed_spec = config["adapter_inputs"][str(seed)]
    historical_gold, historical_prediction = metric_tools.read_baseline_predictions(
        resolve_project_path(seed_spec["historical_predictions_path"]),
        labels,
        gold.shape[0],
    )
    if not (historical_gold == gold).all():
        raise ValueError("EXP-029 baseline gold differs from EXP-031 dev")
    historical_metrics, _ = metric_tools.compute_metrics(
        gold, historical_prediction, labels
    )
    predictions[HISTORICAL_BASELINE] = historical_prediction
    concurrent_closed = predictions["old-prompt-closed-decoder"]

    named = {
        "historical-closed": historical_prediction,
        "closed": concurrent_closed,
        "old-open": predictions["old-prompt-open-decoder"],
        "aligned-open": predictions["aligned-prompt-open-decoder"],
    }
    comparisons = [
        (
            "concurrent-closed-minus-historical-closed",
            "closed",
            "historical-closed",
        ),
        ("old-open-minus-closed", "old-open", "closed"),
        ("aligned-open-minus-closed", "aligned-open", "closed"),
        ("aligned-open-minus-old-open", "aligned-open", "old-open"),
    ]
    bootstrap = config["evaluation"]["bootstrap"]
    paired = metric_tools.paired_bootstrap_macro_f1(
        gold,
        named,
        comparisons,
        int(bootstrap["replicates"]),
        int(bootstrap["seed"]) + seed,
        float(config["evaluation"]["practical_tie_absolute_macro_f1"]),
    )
    write_json(run_dir / "paired-bootstrap.json", paired)

    rows = slice_rows(labels, gold, predictions)
    write_slice_rows(run_dir / "slice-metrics.csv", rows)
    import numpy as np

    neutral_id = labels.index("neutral")
    neutral_mask = (gold[:, neutral_id] == 1) & (gold.sum(axis=1) > 1)
    all_mask = np.ones(gold.shape[0], dtype=bool)
    ontology_analysis = {
        "baseline_condition": "old-prompt-closed-decoder",
        "conditions": {
            condition: {
                "all_rows_transition": transition_counts(
                    gold, concurrent_closed, predictions[condition], all_mask
                ),
                "neutral_cooccurrence_transition": transition_counts(
                    gold, concurrent_closed, predictions[condition], neutral_mask
                ),
                "predicted_neutral_cooccurrence_rows_all": int(
                    (
                        (predictions[condition][:, neutral_id] == 1)
                        & (predictions[condition].sum(axis=1) > 1)
                    ).sum()
                ),
                "predicted_neutral_cooccurrence_rows_gold_slice": int(
                    (
                        (predictions[condition][neutral_mask][:, neutral_id] == 1)
                        & (predictions[condition][neutral_mask].sum(axis=1) > 1)
                    ).sum()
                ),
            }
            for condition in OPEN_CONDITIONS
        },
        "historical_reproducibility": {
            "different_prediction_rows": int(
                (~(concurrent_closed == historical_prediction).all(axis=1)).sum()
            ),
            "identical_prediction_rate": float(
                (concurrent_closed == historical_prediction).all(axis=1).mean()
            ),
            "macro_f1_difference_concurrent_minus_historical": float(
                task_metrics["old-prompt-closed-decoder"]["macro"]["f1"]
                - historical_metrics["macro"]["f1"]
            ),
        },
        "neutral_cooccurrence_gold_rows": int(neutral_mask.sum()),
        "seed": seed,
    }
    write_json(run_dir / "ontology-analysis.json", ontology_analysis)
    aggregate = {
        "historical_baseline": {
            "condition": HISTORICAL_BASELINE,
            "task": historical_metrics,
        },
        "conditions": {
            condition: {
                "generation": generation_metrics[condition],
                "task": task_metrics[condition],
            }
            for condition in CONDITIONS
        },
        "experiment_id": EXPERIMENT_ID,
        "paired_comparisons": paired,
        "seed": seed,
    }
    write_json(run_dir / "aggregate-metrics.json", aggregate)
    return aggregate


def run_smoke(config: dict[str, Any], seed: int) -> None:
    labels = verify_static_inputs(config, seed=seed, include_dev=False)
    smoke_path = resolve_project_path(config["artifacts"]["smoke_path"])
    if smoke_path.exists():
        raise FileExistsError("Append-only EXP-031 smoke output already exists")
    smoke_path.parent.mkdir(parents=True, exist_ok=True)
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    import mlx.core as mx
    from label_json_constraint import LabelJsonLogitsProcessor
    from label_json_constraint_neutral_cooccurrence import (
        NeutralCooccurrenceLogitsProcessor,
    )

    seed_spec = config["adapter_inputs"][str(seed)]
    adapter_dir = resolve_project_path(seed_spec["adapter_path"]).parent
    started = time.perf_counter()
    model, tokenizer = load(str(MODEL_DIR), adapter_path=str(adapter_dir), lazy=False)
    closed_processor = LabelJsonLogitsProcessor(tokenizer, labels, mx)
    open_processor = NeutralCooccurrenceLogitsProcessor(tokenizer, labels, mx)
    constraints = {
        "old-prompt-closed-decoder": parent.TelemetryConstraint(
            closed_processor, mx
        ),
        "old-prompt-open-decoder": parent.TelemetryConstraint(open_processor, mx),
        "aligned-prompt-open-decoder": parent.TelemetryConstraint(open_processor, mx),
    }
    prompt_specs = load_prompt_specs(config)
    synthetic_texts = (
        "I feel mostly neutral about it, although I am slightly annoyed.",
        "Nothing special happened, but I am glad the task is complete.",
    )
    records = []
    for condition in CONDITIONS:
        for index, text in enumerate(synthetic_texts, start=1):
            generated = parent.generate_one(
                model,
                tokenizer,
                build_prompt(tokenizer, prompt_specs[condition], labels, text),
                int(config["decoding"]["max_new_tokens"]),
                constraints[condition],
                mx,
                stream_generate,
                make_sampler,
            )
            if generated["peak_memory_gb"] > float(
                config["resource_budget"]["peak_mlx_memory_gb_max"]
            ):
                raise MemoryError("EXP-031 smoke exceeded its MLX memory budget")
            parsed = strict_parse(generated["output"], labels)
            if generated["finish_reason"] != "stop" or parsed["error"] is not None:
                raise ValueError(f"Synthetic smoke failed for {condition}")
            records.append(
                {
                    "canonical_output": parsed["canonical_output"],
                    "condition": condition,
                    "generated_tokens": generated["generated_tokens"],
                    "input_id": index,
                    "output_sha256": sha256_text(generated["output"]),
                    "peak_memory_gb": generated["peak_memory_gb"],
                }
            )
    for output in (
        '{"labels":["neutral","joy"]}',
        '{"labels":["anger","neutral","annoyance"]}',
    ):
        if (
            strict_parse(output, labels)["error"] is not None
            or not open_processor.grammar.status(output).complete
            or closed_processor.grammar.status(output).complete
        ):
            raise ValueError("Closed/open neutral grammar contrast failed")
    elapsed = time.perf_counter() - started
    if elapsed > float(config["resource_budget"]["smoke_wall_time_minutes_max"]) * 60:
        raise TimeoutError("EXP-031 smoke exceeded its wall-time gate")
    report = {
        "accessed_splits": [],
        "adapter": artifact(resolve_project_path(seed_spec["adapter_path"])),
        "api_cost_usd": 0,
        "command": [str(PYTHON), project_path(Path(__file__)), "smoke", "--seed", str(seed)],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": artifact(CONFIG_PATH),
        "duration_seconds": elapsed,
        "environment": environment_metadata(),
        "experiment_id": EXPERIMENT_ID,
        "grammar_assertions_passed": 6,
        "hardware": hardware_metadata(),
        "model_manifest": artifact(MODEL_MANIFEST_PATH),
        "protocol": artifact(PROTOCOL_PATH),
        "records": records,
        "seed": seed,
        "status": "Passed",
        "test_absent": not TEST_PATH.exists(),
    }
    write_json(smoke_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def run_dev(config: dict[str, Any], seed: int, resume: bool) -> None:
    labels = verify_static_inputs(config, seed=seed, include_dev=True)
    smoke_path = resolve_project_path(config["artifacts"]["smoke_path"])
    if not smoke_path.is_file() or json.loads(
        smoke_path.read_text(encoding="utf-8")
    ).get("status") != "Passed":
        raise ValueError("EXP-031 synthetic smoke must pass before dev")
    run_dir = resolve_project_path(config["artifacts"]["run_root"]) / f"seed-{seed}"
    run_path = run_dir / "run.json"
    log_path = run_dir / "stdout.log"
    records_path = run_dir / "generation-records.jsonl"
    if resume:
        if not run_path.is_file():
            raise FileNotFoundError("Resume requested without run metadata")
        run = json.loads(run_path.read_text(encoding="utf-8"))
        if run.get("status") not in ("Dev In Progress", "Failed"):
            raise ValueError("Only an incomplete EXP-031 seed may resume")
        if run.get("terminal_failure") is not None:
            raise ValueError("A registered resource-gate failure cannot resume")
        if run.get("error") is not None:
            run.setdefault("attempt_failures", []).append(run.pop("error"))
        run.pop("completed_at_utc", None)
        run["status"] = "Dev In Progress"
        write_json(run_path, run)
    else:
        if run_dir.exists():
            raise FileExistsError("Append-only EXP-031 seed output already exists")
        run_dir.mkdir(parents=True)
        run = {
            "accessed_splits": ["dev"],
            "command": [str(PYTHON), project_path(Path(__file__)), "dev", "--seed", str(seed)],
            "config": artifact(CONFIG_PATH),
            "data": {
                "dev_rows": config["data"]["dev_rows"],
                "dev_sha256": config["data"]["dev_sha256"],
                "labels": list(labels),
                "labels_sha256": config["data"]["labels_sha256"],
                "neutral_cooccurrence_dev_rows": config["data"][
                    "neutral_cooccurrence_dev_rows"
                ],
                "split": "dev",
            },
            "environment": environment_metadata(),
            "experiment_id": EXPERIMENT_ID,
            "git": git_metadata(),
            "hardware": hardware_metadata(),
            "model": config["model"],
            "output_directory": project_path(run_dir),
            "protocol": artifact(PROTOCOL_PATH),
            "reproduction_commands": {
                "dev": [
                    str(PYTHON),
                    project_path(Path(__file__)),
                    "dev",
                    "--seed",
                    str(seed),
                ],
                "verify": [
                    str(PYTHON),
                    project_path(VERIFIER_PATH),
                    "--seed",
                    str(seed),
                ],
            },
            "rq_id": config["rq_id"],
            "seed": seed,
            "stage": config["stage"],
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "Dev In Progress",
            "test_split_accessed": False,
            "tier": "Major",
            "validation_split_accessed": True,
            "working_directory": str(REPO_ROOT),
        }
        write_json(run_path, run)

    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    import mlx.core as mx
    from label_json_constraint import LabelJsonLogitsProcessor
    from label_json_constraint_neutral_cooccurrence import (
        NeutralCooccurrenceLogitsProcessor,
    )

    texts, gold, gold_ids = parent.load_dev(int(config["data"]["dev_rows"]), labels)
    seed_spec = config["adapter_inputs"][str(seed)]
    adapter_path = resolve_project_path(seed_spec["adapter_path"])
    adapter_dir = adapter_path.parent
    append_log(log_path, f"Starting EXP-031 seed {seed} inference-only dev ablation")
    started = time.perf_counter()
    prior_active_seconds = float(run.get("active_duration_seconds", 0.0))
    try:
        mx.reset_peak_memory()
        load_started = time.perf_counter()
        model, tokenizer = load(str(MODEL_DIR), adapter_path=str(adapter_dir), lazy=False)
        model_load_seconds = time.perf_counter() - load_started
        open_processor = NeutralCooccurrenceLogitsProcessor(tokenizer, labels, mx)
        constraints = {
            "old-prompt-closed-decoder": parent.TelemetryConstraint(
                LabelJsonLogitsProcessor(tokenizer, labels, mx), mx
            ),
            "old-prompt-open-decoder": parent.TelemetryConstraint(
                open_processor, mx
            ),
            "aligned-prompt-open-decoder": parent.TelemetryConstraint(
                open_processor, mx
            ),
        }
        prompt_specs = load_prompt_specs(config)
        warmup_peaks: list[float] = []
        for condition in CONDITIONS:
            warmup = parent.generate_one(
                model,
                tokenizer,
                build_prompt(
                    tokenizer,
                    prompt_specs[condition],
                    labels,
                    "I am pleased that the frozen adapter is ready for validation.",
                ),
                int(config["decoding"]["max_new_tokens"]),
                constraints[condition],
                mx,
                stream_generate,
                make_sampler,
            )
            if warmup["finish_reason"] != "stop" or strict_parse(
                warmup["output"], labels
            )["error"] is not None or warmup["peak_memory_gb"] > float(
                config["resource_budget"]["peak_mlx_memory_gb_max"]
            ):
                raise ValueError(f"Warm-up failed for {condition}")
            warmup_peaks.append(float(warmup["peak_memory_gb"]))
        append_log(log_path, f"Model loaded in {model_load_seconds:.3f}s; warm-ups passed")

        records = read_records(records_path) if resume else []
        verify_record_prefix(records, gold_ids, len(texts))
        initial_record_count = len(records)
        prior_active_seconds = max(
            prior_active_seconds,
            sum(float(record["generation_seconds"]) for record in records),
        )
        pairs = list(expected_pairs(len(texts)))
        with records_path.open("a" if resume else "w", encoding="utf-8") as output:
            for pair_index, (row_number, condition) in enumerate(
                pairs[len(records) :], start=len(records) + 1
            ):
                elapsed = time.perf_counter() - started
                cumulative_active = prior_active_seconds + elapsed
                if cumulative_active > float(
                    config["resource_budget"]["dev_wall_time_hours_max_per_seed"]
                ) * 3600:
                    raise TimeoutError("EXP-031 dev exceeded its registered wall time")
                generated = parent.generate_one(
                    model,
                    tokenizer,
                    build_prompt(
                        tokenizer,
                        prompt_specs[condition],
                        labels,
                        texts[row_number - 1],
                    ),
                    int(config["decoding"]["max_new_tokens"]),
                    constraints[condition],
                    mx,
                    stream_generate,
                    make_sampler,
                )
                if generated["peak_memory_gb"] > float(
                    config["resource_budget"]["peak_mlx_memory_gb_max"]
                ):
                    raise MemoryError("EXP-031 dev exceeded its MLX memory budget")
                record = make_record(
                    row_number,
                    condition,
                    gold_ids[row_number - 1],
                    labels,
                    generated,
                )
                output.write(json.dumps(record, sort_keys=True) + "\n")
                output.flush()
                records.append(record)
                if prior_active_seconds + (time.perf_counter() - started) > float(
                    config["resource_budget"]["dev_wall_time_hours_max_per_seed"]
                ) * 3600:
                    raise TimeoutError(
                        "EXP-031 dev exceeded its registered wall time after generation"
                    )
                if pair_index % 50 == 0:
                    os.fsync(output.fileno())
                if pair_index % 100 == 0 or pair_index == len(pairs):
                    elapsed = time.perf_counter() - started
                    rate = (pair_index - initial_record_count) / elapsed
                    remaining = (len(pairs) - pair_index) / rate
                    run["dev_progress"] = {
                        "completed": pair_index,
                        "estimated_remaining_seconds": remaining,
                        "total": len(pairs),
                    }
                    run["active_duration_seconds"] = prior_active_seconds + elapsed
                    write_json(run_path, run)
                    append_log(
                        log_path,
                        f"Dev {pair_index}/{len(pairs)}; elapsed {elapsed / 60:.1f} min; ETA {remaining / 60:.1f} min",
                    )
        verify_record_prefix(records, gold_ids, len(texts))
        if len(records) != len(pairs):
            raise ValueError("EXP-031 generation is incomplete")
        peak_memory = max(
            *warmup_peaks,
            *(float(record["peak_memory_gb"]) for record in records),
        )
        if peak_memory > float(config["resource_budget"]["peak_mlx_memory_gb_max"]):
            raise MemoryError("EXP-031 exceeded its MLX memory budget")
        duration = prior_active_seconds + (time.perf_counter() - started)
        time_limit = (
            float(config["resource_budget"]["dev_wall_time_hours_max_per_seed"])
            * 3600
        )
        if duration > time_limit:
            raise TimeoutError("EXP-031 exceeded its registered wall time before finalization")
        aggregate = finalize_atomically(config, seed, run_dir, records, labels, gold)
        duration = prior_active_seconds + (time.perf_counter() - started)
        if duration > time_limit:
            raise TimeoutError("EXP-031 exceeded its registered wall time during finalization")
        append_log(
            log_path,
            "Completed dev: "
            + ", ".join(
                f"{condition} Macro-F1={aggregate['conditions'][condition]['task']['macro']['f1']:.6f}"
                for condition in CONDITIONS
            ),
        )
        artifacts = collect_run_artifacts(run_dir)
        run.update(
            {
                "adapter": artifact(adapter_path),
                "adapter_config": artifact(
                    resolve_project_path(seed_spec["adapter_config_path"])
                ),
                "api_cost_usd": 0,
                "artifacts": artifacts,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "active_duration_seconds": duration,
                "dev_duration_seconds": duration,
                "dev_generation_pairs": len(records),
                "dev_model_load_seconds": model_load_seconds,
                "dev_peak_mlx_memory_gb": peak_memory,
                "raw_comment_ids_stored": False,
                "raw_input_text_stored": False,
                "status": "Completed",
                "test_rows_accessed": 0,
                "warnings": [
                    "This is dev-only inference policy evidence, not a test result.",
                    "The adapters were trained with neutral removed from co-occurring targets.",
                    "Inference-only failure does not show that target-aligned retraining would fail.",
                ],
            }
        )
        write_json(run_path, run)
    except BaseException as error:
        active_duration = prior_active_seconds + (time.perf_counter() - started)
        terminal_resource_violation = isinstance(error, (MemoryError, TimeoutError))
        failure = {
            "message": str(error),
            "terminal_resource_violation": terminal_resource_violation,
            "traceback": traceback.format_exc(),
            "type": type(error).__name__,
        }
        run.update(
            {
                "active_duration_seconds": active_duration,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": failure,
                "status": "Failed",
            }
        )
        if terminal_resource_violation:
            run["terminal_failure"] = failure
        write_json(run_path, run)
        append_log(log_path, f"FAILED: {error}")
        raise


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.command == "smoke":
        run_smoke(config, args.seed)
    elif args.command == "dev":
        run_dev(config, args.seed, args.resume)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()

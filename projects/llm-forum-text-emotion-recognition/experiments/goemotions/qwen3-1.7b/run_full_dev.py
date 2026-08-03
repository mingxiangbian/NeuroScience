#!/usr/bin/env python3
"""Run the frozen EXP-025/026 GoEmotions full-dev generation experiments."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
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
os.environ["TRANSFORMERS_OFFLINE"] = "1"

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler
import numpy as np

import llm_full_dev_metrics as metric_tools
from label_json_constraint import LabelJsonLogitsProcessor
import run_resource_parser_trial as exp022


PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"
DEV_PATH = DATA_ROOT / "dev.tsv"
LABELS_PATH = DATA_ROOT / "emotions.txt"
TEST_PATH = DATA_ROOT / "test.tsv"
MODEL_ROOT = PROJECT_ROOT / "models" / "qwen3-1.7b"
MODEL_DIR = MODEL_ROOT / "mlx-bf16"
MODEL_MANIFEST_PATH = MODEL_ROOT / "manifest.json"
RUNNER_PATH = Path(__file__).resolve()
METRICS_PATH = SCRIPT_DIR / "llm_full_dev_metrics.py"
VERIFIER_PATH = SCRIPT_DIR / "verify_full_dev.py"
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint.py"
PARSER_SOURCE_PATH = SCRIPT_DIR / "run_resource_parser_trial.py"
CONFIG_PATHS = {
    "EXP-025": SCRIPT_DIR / "configs" / "exp-025-full-dev-zero-few-shot.json",
    "EXP-026": SCRIPT_DIR / "configs" / "exp-026-unconstrained-decoder-ablation.json",
}
CONDITIONS = ("zero-shot", "few-shot-synthetic-3")
EXPECTED_LABELS = exp022.EXPECTED_LABELS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", choices=tuple(CONFIG_PATHS))
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not args.preflight and args.experiment is None:
        parser.error("--experiment is required for a formal run")
    if args.preflight and args.resume:
        parser.error("--resume is not valid with --preflight")
    return args


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


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
    return {
        "commit": commit,
        "dirty": bool(status),
        "dirty_path_count": len(status),
    }


def hardware_metadata() -> dict[str, Any]:
    memory_bytes = int(
        subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    chip = subprocess.run(
        ["sysctl", "-n", "machdep.cpu.brand_string"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "architecture": platform.machine(),
        "chip": chip,
        "memory_bytes": memory_bytes,
        "platform": platform.platform(),
    }


def package_versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in (
            "huggingface-hub",
            "mlx",
            "mlx-lm",
            "numpy",
            "transformers",
        )
    }


def config_path(experiment_id: str) -> Path:
    return CONFIG_PATHS[experiment_id]


def load_config(experiment_id: str) -> dict[str, Any]:
    path = config_path(experiment_id)
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["experiment_id"] != experiment_id:
        raise ValueError("Config experiment ID mismatch")
    if config["tier"] != "Major" or config["status"] != "Registered":
        raise ValueError("Formal config must be a registered Major")
    if tuple(item["name"] for item in config["conditions"]) != CONDITIONS:
        raise ValueError("Frozen condition order changed")
    return config


def resolve_project_path(value: str) -> Path:
    return PROJECT_ROOT / value


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Frozen hash mismatch for {path}: {actual} != {expected}")


def verify_static_inputs(
    experiment_id: str,
    config: dict[str, Any],
    include_dev: bool,
) -> dict[str, Any]:
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    verify_hash(LABELS_PATH, config["data"]["labels_sha256"])
    prompt_path = resolve_project_path(config["prompt"]["path"])
    verify_hash(prompt_path, config["prompt"]["sha256"])
    verify_hash(MODEL_MANIFEST_PATH, config["model"]["manifest_sha256"])
    if experiment_id == "EXP-025":
        verify_hash(CONSTRAINT_PATH, config["constraint"]["sha256"])
    else:
        verify_hash(
            resolve_project_path(config["decoder"]["parser_source_path"]),
            config["decoder"]["parser_source_sha256"],
        )
    for name in ("EXP-018", "EXP-020"):
        baseline = config["comparison_inputs"][name]
        if name == "EXP-018":
            verify_hash(
                resolve_project_path(baseline["predictions_path"]),
                baseline["predictions_sha256"],
            )
            verify_hash(
                resolve_project_path(baseline["run_path"]),
                baseline["run_sha256"],
            )
        else:
            verify_hash(
                resolve_project_path(baseline["aggregate_metrics_path"]),
                baseline["aggregate_metrics_sha256"],
            )
            for seed_record in baseline["seed_predictions"]:
                verify_hash(
                    resolve_project_path(seed_record["path"]),
                    seed_record["sha256"],
                )
    implementation = config.get("implementation")
    if not implementation:
        raise ValueError("Implementation hashes are not frozen in the config")
    for key, path in (
        ("runner_sha256", RUNNER_PATH),
        ("metrics_sha256", METRICS_PATH),
        ("verifier_sha256", VERIFIER_PATH),
    ):
        verify_hash(path, implementation[key])
    if include_dev:
        verify_hash(DEV_PATH, config["data"]["dev_sha256"])

    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError("GoEmotions label order changed")
    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        manifest["repo_id"] != config["model"]["repo_id"]
        or manifest["revision"] != config["model"]["revision"]
        or manifest["conversion"]["dtype"] != "bfloat16"
        or manifest["conversion"]["quantized"] is not False
    ):
        raise ValueError("Model manifest differs from the frozen condition")
    if not MODEL_DIR.is_dir() or not any(MODEL_DIR.glob("*.safetensors")):
        raise FileNotFoundError(f"Missing local MLX model: {MODEL_DIR}")

    paired = None
    if experiment_id == "EXP-026" and include_dev:
        paired_dir = resolve_project_path(
            config["comparison_inputs"]["EXP-025"]["run_dir"]
        )
        verification_path = paired_dir / "verification.json"
        if not verification_path.is_file():
            raise FileNotFoundError("EXP-025 verification is required before EXP-026")
        paired_verification = json.loads(verification_path.read_text(encoding="utf-8"))
        if paired_verification.get("status") != "Passed":
            raise ValueError("EXP-025 verification did not pass")
        paired = artifact(verification_path)
    return {
        "labels": labels,
        "paired_verification": paired,
        "prompt_path": prompt_path,
    }


def load_dev(
    expected_rows: int,
    labels: tuple[str, ...],
) -> tuple[list[str], np.ndarray, list[list[int]]]:
    texts: list[str] = []
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    gold_ids: list[list[int]] = []
    comment_ids: set[str] = set()
    with DEV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_index, row in enumerate(reader):
            row_number = row_index + 1
            if row_index >= expected_rows:
                raise ValueError("dev.tsv has too many rows")
            if len(row) != 3:
                raise ValueError(f"dev.tsv row {row_number} has {len(row)} columns")
            text, encoded_labels, comment_id = row
            if not text or not encoded_labels or not comment_id:
                raise ValueError(f"dev.tsv row {row_number} has an empty field")
            if comment_id in comment_ids:
                raise ValueError("dev.tsv repeats a comment ID")
            comment_ids.add(comment_id)
            try:
                values = [int(value) for value in encoded_labels.split(",")]
            except ValueError as error:
                raise ValueError(f"dev.tsv row {row_number} has invalid labels") from error
            if (
                not values
                or len(values) != len(set(values))
                or any(value < 0 or value >= len(labels) for value in values)
            ):
                raise ValueError(f"dev.tsv row {row_number} has invalid label IDs")
            texts.append(text)
            gold[row_index, values] = 1
            gold_ids.append(values)
    if len(texts) != expected_rows:
        raise ValueError(f"dev.tsv has {len(texts)} rows; expected {expected_rows}")
    return texts, gold, gold_ids


class TelemetryConstraint:
    """Record when the unrestricted argmax is removed by the frozen mask."""

    def __init__(self, processor: LabelJsonLogitsProcessor):
        self.processor = processor
        self.reset()

    def reset(self) -> None:
        self.processor.reset()
        self.calls = 0
        self.blocked_steps = 0
        self.first_blocked_step: int | None = None
        self.first_blocked_token_id: int | None = None

    @property
    def candidate_token_count(self) -> int:
        return self.processor.candidate_token_count

    def __call__(self, tokens: Any, logits: Any) -> Any:
        raw_argmax = int(mx.argmax(logits[0]).item())
        processed = self.processor(tokens, logits)
        blocked = not bool(mx.isfinite(processed[0, raw_argmax]).item())
        if blocked:
            self.blocked_steps += 1
            if self.first_blocked_step is None:
                self.first_blocked_step = self.calls
                self.first_blocked_token_id = raw_argmax
        self.calls += 1
        return processed

    def snapshot(self) -> dict[str, Any]:
        return {
            "constraint_intervened": self.blocked_steps > 0,
            "first_blocked_step": self.first_blocked_step,
            "first_blocked_token_id": self.first_blocked_token_id,
            "raw_argmax_blocked_steps": self.blocked_steps,
        }


def eos_token_ids(tokenizer: Any) -> set[int]:
    values = getattr(tokenizer, "eos_token_ids", None)
    if values is None:
        value = getattr(tokenizer, "eos_token_id", None)
        values = [] if value is None else [value]
    return {int(value) for value in values}


def generate_one(
    model: Any,
    tokenizer: Any,
    prompt: str,
    max_tokens: int,
    constraint: TelemetryConstraint | None,
) -> dict[str, Any]:
    if constraint is not None:
        constraint.reset()
    mx.reset_peak_memory()
    started = time.perf_counter()
    output_parts: list[str] = []
    token_logprobs: list[float] = []
    last_response = None
    eos_ids = eos_token_ids(tokenizer)
    processors = [] if constraint is None else [constraint]
    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=make_sampler(temp=0.0),
        logits_processors=processors,
    ):
        output_parts.append(response.text)
        token_id = int(response.token)
        if token_id not in eos_ids:
            selected_logprob = float(response.logprobs[token_id].item())
            if not math.isfinite(selected_logprob):
                raise ValueError("Generation returned a non-finite selected-token logprob")
            token_logprobs.append(selected_logprob)
        last_response = response
    elapsed = time.perf_counter() - started
    if last_response is None:
        raise RuntimeError("MLX-LM yielded no generation response")
    numeric_values = (
        last_response.prompt_tps,
        last_response.generation_tps,
        last_response.peak_memory,
        elapsed,
    )
    if not all(math.isfinite(float(value)) for value in numeric_values):
        raise ValueError("Generation returned a non-finite resource measurement")
    score_sum = float(sum(token_logprobs))
    score_mean = float(score_sum / len(token_logprobs)) if token_logprobs else 0.0
    telemetry = (
        {
            "constraint_intervened": None,
            "first_blocked_step": None,
            "first_blocked_token_id": None,
            "raw_argmax_blocked_steps": None,
        }
        if constraint is None
        else constraint.snapshot()
    )
    return {
        "finish_reason": last_response.finish_reason,
        "generated_tokens": int(last_response.generation_tokens),
        "generation_seconds": elapsed,
        "generation_tps": float(last_response.generation_tps),
        "output": "".join(output_parts),
        "peak_memory_gb": float(last_response.peak_memory),
        "prompt_tokens": int(last_response.prompt_tokens),
        "prompt_tps": float(last_response.prompt_tps),
        "sequence_logprob_mean": score_mean,
        "sequence_logprob_sum": score_sum,
        **telemetry,
    }


def condition_order(row_number: int) -> tuple[str, str]:
    return CONDITIONS if row_number % 2 else tuple(reversed(CONDITIONS))


def expected_pairs(row_count: int) -> Iterator[tuple[int, str]]:
    for row_number in range(1, row_count + 1):
        for condition in condition_order(row_number):
            yield row_number, condition


def make_record(
    row_number: int,
    condition: str,
    gold_label_ids: list[int],
    labels: tuple[str, ...],
    generated: dict[str, Any],
    constrained: bool,
) -> dict[str, Any]:
    output = generated.pop("output")
    parsed = exp022.strict_parse(output, labels)
    parser_error = parsed["error"]
    parser_valid = parser_error is None
    if generated["finish_reason"] != "stop":
        parser_valid = False
        parser_error = "length-terminated"
    predicted_labels = parsed["labels"] if parser_valid else []
    label_to_id = {label: index for index, label in enumerate(labels)}
    predicted_ids = [label_to_id[label] for label in predicted_labels]
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
        "predicted_label_ids": predicted_ids,
        "predicted_labels": predicted_labels,
        "prompt_tokens": generated["prompt_tokens"],
        "prompt_tps": generated["prompt_tps"],
        "raw_argmax_blocked_steps": generated["raw_argmax_blocked_steps"],
        "row_number": row_number,
        "sequence_logprob_mean": generated["sequence_logprob_mean"],
        "sequence_logprob_sum": generated["sequence_logprob_sum"],
        "sequence_score_space": "constrained" if constrained else "unconstrained",
    }


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_record_prefix(
    records: list[dict[str, Any]],
    gold_ids: list[list[int]],
    row_count: int,
) -> None:
    pairs = list(expected_pairs(row_count))
    if len(records) > len(pairs):
        raise ValueError("Checkpoint contains too many records")
    for index, record in enumerate(records):
        expected_row, expected_condition = pairs[index]
        if (
            record["row_number"] != expected_row
            or record["condition"] != expected_condition
            or record["gold_label_ids"] != gold_ids[expected_row - 1]
        ):
            raise ValueError(f"Checkpoint diverges at record {index + 1}")


def setup_logger(run_dir: Path, experiment_id: str, append: bool) -> logging.Logger:
    logger = logging.getLogger(experiment_id.lower())
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    file_handler = logging.FileHandler(
        run_dir / "stdout.log", encoding="utf-8", mode="a" if append else "w"
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def flush_logger(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()


def parse_generated_predictions(
    path: Path,
    labels: tuple[str, ...],
    expected_rows: int,
) -> tuple[np.ndarray, np.ndarray]:
    return metric_tools.read_baseline_predictions(path, labels, expected_rows)


def bootstrap_inputs(
    experiment_id: str,
    config: dict[str, Any],
    labels: tuple[str, ...],
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], list[tuple[str, str, str]]]:
    named: dict[str, np.ndarray] = {}
    prefix = "constrained" if experiment_id == "EXP-025" else "unconstrained"
    for condition in CONDITIONS:
        named[f"{prefix}-{condition}"] = predictions[condition]
    comparisons = [
        (
            f"{prefix}-zero-shot-minus-{prefix}-few-shot-synthetic-3",
            f"{prefix}-zero-shot",
            f"{prefix}-few-shot-synthetic-3",
        )
    ]

    if experiment_id == "EXP-026":
        exp025_dir = resolve_project_path(
            config["comparison_inputs"]["EXP-025"]["run_dir"]
        )
        for condition in CONDITIONS:
            paired_gold, paired_prediction = parse_generated_predictions(
                exp025_dir / condition / "predictions.csv",
                labels,
                gold.shape[0],
            )
            if not np.array_equal(paired_gold, gold):
                raise ValueError("EXP-025 gold rows differ from EXP-026 dev")
            named[f"constrained-{condition}"] = paired_prediction
            comparisons.append(
                (
                    f"unconstrained-minus-constrained-{condition}",
                    f"unconstrained-{condition}",
                    f"constrained-{condition}",
                )
            )

    for seed_record in config["comparison_inputs"]["EXP-020"]["seed_predictions"]:
        seed = int(seed_record["seed"])
        baseline_gold, baseline_prediction = metric_tools.read_baseline_predictions(
            resolve_project_path(seed_record["path"]), labels, gold.shape[0]
        )
        if not np.array_equal(baseline_gold, gold):
            raise ValueError(f"EXP-020 seed {seed} gold rows differ from dev")
        named[f"bert-seed-{seed}"] = baseline_prediction
        for condition in CONDITIONS:
            comparisons.append(
                (
                    f"{prefix}-{condition}-minus-bert-seed-{seed}",
                    f"{prefix}-{condition}",
                    f"bert-seed-{seed}",
                )
            )
    return named, comparisons


def compare_condition_to_baselines(
    config: dict[str, Any],
    task_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    exp018 = config["comparison_inputs"]["EXP-018"]["dev_macro_f1"]
    exp020 = config["comparison_inputs"]["EXP-020"]["dev_macro_f1_mean"]
    return {
        condition: {
            "macro_f1": task_metrics[condition]["macro"]["f1"],
            "minus_exp_018": task_metrics[condition]["macro"]["f1"] - exp018,
            "minus_exp_020_mean": task_metrics[condition]["macro"]["f1"] - exp020,
        }
        for condition in CONDITIONS
    }


def selection_record(
    experiment_id: str,
    config: dict[str, Any],
    task_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if experiment_id == "EXP-026":
        return {
            "candidate_override_allowed": False,
            "reason": config["evaluation"]["selection_rule"],
            "selected_condition": None,
        }
    zero = task_metrics["zero-shot"]["macro"]["f1"]
    few = task_metrics["few-shot-synthetic-3"]["macro"]["f1"]
    threshold = config["evaluation"]["practical_tie_absolute_macro_f1"]
    difference = zero - few
    if abs(difference) < threshold:
        selected = "zero-shot"
        reason = "practical tie; zero-shot selected for lower cost and complexity"
    elif difference > 0:
        selected = "zero-shot"
        reason = "zero-shot has higher dev Macro-F1 beyond the practical threshold"
    else:
        selected = "few-shot-synthetic-3"
        reason = "few-shot has higher dev Macro-F1 beyond the practical threshold"
    return {
        "absolute_difference": abs(difference),
        "difference_zero_minus_few": difference,
        "practical_tie": abs(difference) < threshold,
        "practical_tie_threshold": threshold,
        "reason": reason,
        "selected_condition": selected,
    }


def load_exp025_records(config: dict[str, Any]) -> tuple[Path, list[dict[str, Any]]]:
    run_dir = resolve_project_path(config["comparison_inputs"]["EXP-025"]["run_dir"])
    return run_dir, read_records(run_dir / "generation-records.jsonl")


def joint_decoder_analysis(
    config: dict[str, Any],
    unconstrained_records: list[dict[str, Any]],
    unconstrained_task: dict[str, dict[str, Any]],
    unconstrained_generation: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    exp025_dir, constrained_records = load_exp025_records(config)
    expected = config["data"]["dev_rows"] * len(CONDITIONS)
    if len(constrained_records) != expected:
        raise ValueError("EXP-025 generation record count changed")
    constrained_by_key = {
        (record["row_number"], record["condition"]): record
        for record in constrained_records
    }
    conditions: dict[str, Any] = {}
    for condition in CONDITIONS:
        unrestricted = [
            record for record in unconstrained_records if record["condition"] == condition
        ]
        constrained = [
            constrained_by_key[(record["row_number"], condition)]
            for record in unrestricted
        ]
        valid_pairs = [
            (left, right)
            for left, right in zip(unrestricted, constrained, strict=True)
            if left["parser_valid"] and right["parser_valid"]
        ]
        exact = sum(
            set(left["predicted_label_ids"]) == set(right["predicted_label_ids"])
            for left, right in valid_pairs
        )
        jaccards = []
        for left, right in valid_pairs:
            left_set = set(left["predicted_label_ids"])
            right_set = set(right["predicted_label_ids"])
            jaccards.append(len(left_set & right_set) / len(left_set | right_set))

        constrained_metrics = json.loads(
            (exp025_dir / condition / "metrics.json").read_text(encoding="utf-8")
        )
        constrained_task = constrained_metrics["task"]
        constrained_generation = constrained_metrics["generation"]
        per_label_delta = {
            label: {
                "unconstrained_minus_constrained_predicted_support": (
                    unconstrained_task[condition]["per_label"][label][
                        "predicted_support"
                    ]
                    - constrained_task["per_label"][label]["predicted_support"]
                )
            }
            for label in EXPECTED_LABELS
        }
        resource_deltas = {
            "generated_tokens_total": (
                unconstrained_generation[condition]["generated_tokens"]["total"]
                - constrained_generation["generated_tokens"]["total"]
            ),
            "generation_seconds": {
                key: (
                    unconstrained_generation[condition]["generation_seconds"][key]
                    - constrained_generation["generation_seconds"][key]
                )
                for key in ("total", "median", "p95")
            },
            "prompt_tokens_total": (
                unconstrained_generation[condition]["prompt_tokens"]["total"]
                - constrained_generation["prompt_tokens"]["total"]
            ),
        }
        conditions[condition] = {
            "constrained_macro_f1": constrained_task["macro"]["f1"],
            "constrained_parser_valid_rate": constrained_generation[
                "parser_valid_rate"
            ],
            "constraint_intervention": constrained_generation.get(
                "constraint_intervention"
            ),
            "exact_label_set_agreement": {
                "count": exact,
                "denominator_both_valid": len(valid_pairs),
                "rate": exact / len(valid_pairs) if valid_pairs else None,
            },
            "label_set_jaccard_mean_on_both_valid": float(np.mean(jaccards))
            if jaccards
            else None,
            "macro_f1_delta_unconstrained_minus_constrained": (
                unconstrained_task[condition]["macro"]["f1"]
                - constrained_task["macro"]["f1"]
            ),
            "per_label": per_label_delta,
            "predicted_cardinality_delta_unconstrained_minus_constrained": (
                unconstrained_task[condition]["label_cardinality"]["predicted_mean"]
                - constrained_task["label_cardinality"]["predicted_mean"]
            ),
            "resource_deltas_unconstrained_minus_constrained": resource_deltas,
            "unconstrained_macro_f1": unconstrained_task[condition]["macro"]["f1"],
            "unconstrained_parser_valid_count": unconstrained_generation[condition][
                "parser_valid_count"
            ],
            "unconstrained_parser_valid_rate": unconstrained_generation[condition][
                "parser_valid_rate"
            ],
            "validity_rate_delta_unconstrained_minus_constrained": (
                unconstrained_generation[condition]["parser_valid_rate"]
                - constrained_generation["parser_valid_rate"]
            ),
        }
    return {
        "analysis_scope": "paired full-dev decoder ablation",
        "conditions": conditions,
        "exp_025_artifacts": {
            "generation_records": artifact(exp025_dir / "generation-records.jsonl"),
            "verification": artifact(exp025_dir / "verification.json"),
        },
        "invalid_output_primary_policy": "invalid or length outputs are empty predictions",
        "valid_pair_metrics_are_diagnostic_only": True,
    }


def finalize_outputs(
    experiment_id: str,
    config: dict[str, Any],
    run_dir: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    gold: np.ndarray,
    logger: logging.Logger,
) -> dict[str, Any]:
    task_metrics: dict[str, dict[str, Any]] = {}
    generation_metrics: dict[str, dict[str, Any]] = {}
    predictions: dict[str, np.ndarray] = {}
    for condition in CONDITIONS:
        condition_records = [
            record for record in records if record["condition"] == condition
        ]
        if len(condition_records) != config["data"]["dev_rows"]:
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
        metric_tools.write_per_label(
            condition_dir / "per-label-metrics.csv", metrics, labels
        )
        metric_tools.write_confusion(
            condition_dir / "multilabel-confusion-matrix.csv", confusion, labels
        )
        metric_tools.write_json(
            condition_dir / "metrics.json",
            {"condition": condition, "generation": generation, "task": metrics},
        )
        logger.info(
            "%s final metrics: Macro-F1 %.6f Micro-F1 %.6f parser %.4f",
            condition,
            metrics["macro"]["f1"],
            metrics["micro"]["f1"],
            generation["parser_valid_rate"],
        )

    metric_tools.write_condition_summary(
        run_dir / "condition-summary.csv",
        CONDITIONS,
        task_metrics,
        generation_metrics,
    )
    named_predictions, comparisons = bootstrap_inputs(
        experiment_id, config, labels, gold, predictions
    )
    bootstrap_config = config["evaluation"]["bootstrap"]
    logger.info(
        "Starting %d-replicate paired bootstrap for %d comparisons",
        bootstrap_config["replicates"],
        len(comparisons),
    )
    bootstrap = metric_tools.paired_bootstrap_macro_f1(
        gold,
        named_predictions,
        comparisons,
        bootstrap_config["replicates"],
        bootstrap_config["seed"],
        config["evaluation"]["practical_tie_absolute_macro_f1"],
    )
    metric_tools.write_json(run_dir / "paired-bootstrap.json", bootstrap)
    aggregate = {
        "baseline_comparisons": compare_condition_to_baselines(config, task_metrics),
        "conditions": {
            condition: {
                "generation": generation_metrics[condition],
                "task": task_metrics[condition],
            }
            for condition in CONDITIONS
        },
        "experiment_id": experiment_id,
        "selection": selection_record(experiment_id, config, task_metrics),
    }
    metric_tools.write_json(run_dir / "aggregate-metrics.json", aggregate)
    joint = None
    if experiment_id == "EXP-026":
        joint = joint_decoder_analysis(
            config,
            records,
            task_metrics,
            generation_metrics,
        )
        metric_tools.write_json(run_dir / "joint-decoder-analysis.json", joint)
    logger.info("Metric and bootstrap artifacts complete")
    return {
        "aggregate": aggregate,
        "bootstrap": bootstrap,
        "generation_metrics": generation_metrics,
        "joint": joint,
        "task_metrics": task_metrics,
    }


def source_artifacts(
    experiment_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    values = {
        "config": artifact(config_path(experiment_id)),
        "labels": artifact(LABELS_PATH),
        "metrics_implementation": artifact(METRICS_PATH),
        "model_manifest": artifact(MODEL_MANIFEST_PATH),
        "prompt": artifact(resolve_project_path(config["prompt"]["path"])),
        "runner": artifact(RUNNER_PATH),
        "verifier": artifact(VERIFIER_PATH),
    }
    if experiment_id == "EXP-025":
        values["constraint"] = artifact(CONSTRAINT_PATH)
    else:
        values["parser_source"] = artifact(PARSER_SOURCE_PATH)
    return values


def generated_artifacts(
    config: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    values = {}
    for relative in config["artifacts"]["required"]:
        if relative in ("run.json", "verification.json"):
            continue
        path = run_dir / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required artifact missing: {path}")
        values[relative] = artifact(path)
    return values


def run_preflight() -> None:
    if TEST_PATH.exists():
        raise ValueError("test.tsv must remain absent")
    for experiment_id in CONFIG_PATHS:
        config = load_config(experiment_id)
        run_dir = resolve_project_path(config["artifacts"]["output_dir"])
        if run_dir.exists():
            raise FileExistsError(f"Preflight requires absent run directory: {run_dir}")
        verify_static_inputs(experiment_id, config, include_dev=False)

    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    parser_fixtures = {
        '{"labels":["joy"]}': True,
        ' {"labels":["joy","gratitude"]} ': True,
        '{"labels":["neutral","joy"]}': False,
        '```json\n{"labels":["joy"]}\n```': False,
    }
    for output, expected in parser_fixtures.items():
        actual = exp022.strict_parse(output, labels)["error"] is None
        if actual != expected:
            raise ValueError(f"Parser fixture failed for {output!r}")

    fixture_gold = np.array([[1, 0], [1, 1], [0, 1]], dtype=np.uint8)
    fixture_predicted = np.array([[1, 0], [0, 1], [0, 0]], dtype=np.uint8)
    fixture_metrics, _ = metric_tools.compute_metrics(
        fixture_gold, fixture_predicted, ("a", "b")
    )
    if not math.isclose(fixture_metrics["macro"]["f1"], 2 / 3, abs_tol=1e-12):
        raise ValueError("Metric fixture Macro-F1 failed")

    load_started = time.perf_counter()
    model, tokenizer = load(str(MODEL_DIR), lazy=False)
    processor = TelemetryConstraint(LabelJsonLogitsProcessor(tokenizer, labels, mx))
    prompt_spec = json.loads(
        resolve_project_path(load_config("EXP-025")["prompt"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    synthetic = "I am thrilled by the result and grateful for everyone's help."
    results = []
    for constrained in (False, True):
        for condition in CONDITIONS:
            prompt = exp022.build_prompt(
                tokenizer, prompt_spec, labels, synthetic, condition
            )
            generated = generate_one(
                model,
                tokenizer,
                prompt,
                64,
                processor if constrained else None,
            )
            parsed = exp022.strict_parse(generated["output"], labels)
            if generated["finish_reason"] != "stop":
                raise ValueError("Synthetic preflight did not stop normally")
            if constrained and parsed["error"] is not None:
                raise ValueError("Constrained synthetic preflight did not parse")
            results.append(
                {
                    "condition": condition,
                    "constrained": constrained,
                    "finish_reason": generated["finish_reason"],
                    "parser_valid": parsed["error"] is None,
                }
            )
    print(
        json.dumps(
            {
                "dev_accessed": False,
                "model_load_seconds": time.perf_counter() - load_started,
                "results": results,
                "run_directories_absent": True,
                "status": "Passed",
                "test_absent": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


def formal_run(experiment_id: str, resume: bool) -> None:
    config = load_config(experiment_id)
    run_dir = resolve_project_path(config["artifacts"]["output_dir"])
    if resume:
        if not run_dir.is_dir():
            raise FileNotFoundError("Resume requested but run directory is absent")
    else:
        if run_dir.exists():
            raise FileExistsError(f"Append-only output already exists: {run_dir}")
        run_dir.mkdir(parents=True)
    logger = setup_logger(run_dir, experiment_id, append=resume)
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    records_path = run_dir / "generation-records.jsonl"
    run_path = run_dir / "run.json"
    run: dict[str, Any] = {
        "accessed_splits": [],
        "completed_generation_pairs": 0,
        "errors": [],
        "experiment_id": experiment_id,
        "invocation": [sys.executable, *sys.argv],
        "parent_experiment": config["parent_experiment"],
        "resume": resume,
        "rq_id": config["rq_id"],
        "stage": config["stage"],
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Major",
        "validation_split_accessed": False,
        "warnings": [
            "EXP-025 measures the constrained end-to-end system; EXP-026 is the matched decoder ablation.",
            "Dev is a model-selection split, not an independent test or public benchmark result.",
            "Invalid or length-terminated outputs are scored as empty predictions without retry.",
            "Sequence log probabilities are not calibrated 28-label probabilities.",
        ],
    }
    metric_tools.write_json(run_path, run)
    try:
        logger.info("Starting %s formal full-dev run", experiment_id)
        static = verify_static_inputs(experiment_id, config, include_dev=True)
        run["accessed_splits"] = ["dev"]
        run["validation_split_accessed"] = True
        labels = static["labels"]
        texts, gold, gold_ids = load_dev(config["data"]["dev_rows"], labels)
        run["data"] = {
            "dataset_protocol": config["data"]["dataset_protocol"],
            "dev_rows": len(texts),
            "dev_sha256": config["data"]["dev_sha256"],
            "labels": list(labels),
            "labels_sha256": config["data"]["labels_sha256"],
            "raw_comment_ids_stored": False,
            "raw_input_text_stored": False,
            "split": "dev",
            "test_rows_accessed": 0,
            "train_rows_accessed": 0,
        }
        run["environment"] = {
            "hardware": hardware_metadata(),
            "packages": package_versions(),
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "python_prefix": sys.prefix,
        }
        run["git"] = git_metadata()
        run["source_artifacts"] = source_artifacts(experiment_id, config)
        metric_tools.write_json(run_path, run)
        logger.info("Frozen hashes and dev row count verified")

        mx.reset_peak_memory()
        load_started = time.perf_counter()
        model, tokenizer = load(str(MODEL_DIR), lazy=False)
        model_load_seconds = time.perf_counter() - load_started
        model_load_peak_gb = mx.get_peak_memory() / 1e9
        model_active_memory_gb = mx.get_active_memory() / 1e9
        prompt_spec = json.loads(static["prompt_path"].read_text(encoding="utf-8"))
        constrained = experiment_id == "EXP-025"
        constraint_init_seconds = None
        constraint = None
        if constrained:
            constraint_started = time.perf_counter()
            constraint = TelemetryConstraint(
                LabelJsonLogitsProcessor(tokenizer, labels, mx)
            )
            constraint_init_seconds = time.perf_counter() - constraint_started
        logger.info(
            "Model loaded in %.3fs; constrained=%s",
            model_load_seconds,
            constrained,
        )

        warmup_text = "I am pleased that the local evaluation pipeline is ready."
        for condition in CONDITIONS:
            prompt = exp022.build_prompt(
                tokenizer, prompt_spec, labels, warmup_text, condition
            )
            warmup = generate_one(
                model,
                tokenizer,
                prompt,
                config["decoding"]["max_new_tokens"],
                constraint,
            )
            if warmup["finish_reason"] != "stop":
                raise ValueError(f"{condition} warm-up did not stop normally")
            if constrained and exp022.strict_parse(warmup["output"], labels)["error"]:
                raise ValueError(f"{condition} constrained warm-up failed parsing")
        logger.info("Two synthetic warm-ups completed")

        records = read_records(records_path) if resume else []
        verify_record_prefix(records, gold_ids, len(texts))
        if records and not resume:
            raise ValueError("Existing checkpoint requires --resume")
        pairs = list(expected_pairs(len(texts)))
        file_mode = "a" if resume else "w"
        with records_path.open(file_mode, encoding="utf-8") as output:
            for pair_index, (row_number, condition) in enumerate(
                pairs[len(records) :], start=len(records) + 1
            ):
                elapsed = time.perf_counter() - started
                if elapsed > config["resource_budget"]["wall_time_minutes_max"] * 60:
                    raise TimeoutError("Formal run exceeded the frozen wall-time budget")
                prompt = exp022.build_prompt(
                    tokenizer,
                    prompt_spec,
                    labels,
                    texts[row_number - 1],
                    condition,
                )
                generated = generate_one(
                    model,
                    tokenizer,
                    prompt,
                    config["decoding"]["max_new_tokens"],
                    constraint,
                )
                record = make_record(
                    row_number,
                    condition,
                    gold_ids[row_number - 1],
                    labels,
                    generated,
                    constrained,
                )
                output.write(json.dumps(record, sort_keys=True) + "\n")
                output.flush()
                records.append(record)
                run["completed_generation_pairs"] = len(records)
                if pair_index % 50 == 0:
                    os.fsync(output.fileno())
                if pair_index % 100 == 0 or pair_index == len(pairs):
                    elapsed = time.perf_counter() - started
                    rate = pair_index / elapsed
                    remaining_seconds = (len(pairs) - pair_index) / rate
                    run["progress"] = {
                        "completed": pair_index,
                        "estimated_remaining_seconds": remaining_seconds,
                        "total": len(pairs),
                    }
                    metric_tools.write_json(run_path, run)
                    logger.info(
                        "Progress %d/%d (%.1f%%), elapsed %.1f min, ETA %.1f min",
                        pair_index,
                        len(pairs),
                        100 * pair_index / len(pairs),
                        elapsed / 60,
                        remaining_seconds / 60,
                    )

        verify_record_prefix(records, gold_ids, len(texts))
        if len(records) != config["resource_budget"]["measured_generations"]:
            raise ValueError("Measured generation count is incomplete")
        finalized = finalize_outputs(
            experiment_id, config, run_dir, records, labels, gold, logger
        )
        total_seconds = time.perf_counter() - started
        if total_seconds > config["resource_budget"]["wall_time_minutes_max"] * 60:
            raise TimeoutError("Formal run exceeded the frozen wall-time budget")
        peak_memory = max(
            value["peak_memory_gb_max"]
            for value in finalized["generation_metrics"].values()
        )
        if peak_memory > config["resource_budget"]["peak_mlx_memory_gb_max"]:
            raise MemoryError("Formal run exceeded the frozen MLX memory budget")
        run.update(
            {
                "api_cost_usd": 0,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "completed_generation_pairs": len(records),
                "decoder": {
                    "constrained": constrained,
                    "constraint_candidate_token_count": constraint.candidate_token_count
                    if constraint
                    else None,
                    "constraint_init_seconds": constraint_init_seconds,
                    "post_hoc_repair": False,
                    "retries": 0,
                    "strict_parser": True,
                    "synonym_mapping": False,
                },
                "generated_artifacts": {},
                "model": {
                    **config["model"],
                    "active_memory_after_load_gb": model_active_memory_gb,
                    "load_peak_memory_gb": model_load_peak_gb,
                    "load_seconds": model_load_seconds,
                },
                "resource_usage": {
                    "api_cost_usd": 0,
                    "overall_peak_memory_gb": peak_memory,
                    "total_seconds": total_seconds,
                    "warmup_generations": 2,
                },
                "status": "Completed",
                "verification_status": "Pending",
            }
        )
        logger.info(
            "%s generation and evaluation complete in %.1f minutes; verification pending",
            experiment_id,
            total_seconds / 60,
        )
        flush_logger(logger)
        run["generated_artifacts"] = generated_artifacts(config, run_dir)
        metric_tools.write_json(run_path, run)
    except Exception as error:
        run.update(
            {
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "errors": [
                    {
                        "message": str(error),
                        "traceback": traceback.format_exc(),
                        "type": type(error).__name__,
                    }
                ],
                "status": "Failed",
            }
        )
        metric_tools.write_json(run_path, run)
        logger.exception("%s failed", experiment_id)
        raise


def main() -> None:
    args = parse_args()
    if args.preflight:
        run_preflight()
    else:
        formal_run(args.experiment, args.resume)


if __name__ == "__main__":
    main()

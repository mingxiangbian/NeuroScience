#!/usr/bin/env python3
"""Run the train-only CPU recovery preflight for EXP-051."""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import time
import traceback
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import torch
from torch.optim.lr_scheduler import LambdaLR
from torch.utils.data import DataLoader, Subset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

import run_exp051_m1 as core


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-051-m1-roberta-seed-42-cpu-recovery.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    run_config, shared = core.load_config(config_path, 42)
    if run_config["execution"]["required_device"] != "cpu":
        raise ValueError("CPU recovery preflight requires a CPU contract")
    output_dir = (
        args.output_dir
        or core.resolve_project(run_config["recovery"]["cpu_preflight_output"])
    ).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True)
    logger = core.setup_logger(output_dir)
    started = time.perf_counter()
    run_path = output_dir / "run.json"
    record: dict[str, Any] = {
        "schema_version": "exp-051-cpu-recovery-preflight-v1",
        "experiment_id": "EXP-051",
        "tier": "Minor",
        "stage": "cpu-recovery-train-only-preflight",
        "status": "Running",
        "started_at_utc": core.utc_now(),
        "accessed_splits": [],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "performance_metrics_computed": False,
    }
    core.atomic_json(run_path, record)

    try:
        recovery = run_config["recovery"]
        failed_run = core.resolve_project(recovery["failed_run_path"])
        failed_log = core.resolve_project(recovery["failed_log_path"])
        core.require_hash(failed_run, recovery["failed_run_sha256"])
        core.require_hash(failed_log, recovery["failed_log_sha256"])
        failed = json.loads(failed_run.read_text(encoding="utf-8"))
        if failed["status"] != "Failed" or failed["test_split_accessed"] is not False:
            raise ValueError("MPS incident contract drift")
        if "out of memory" not in failed["failure"]["message"].lower():
            raise ValueError("Recovery reason is not the recorded MPS OOM")

        environment = core.environment_gate(output_dir, run_config["execution"])
        model_record = core.verify_model(shared)
        train_rows = core.load_split(shared, "train")
        record["accessed_splits"] = ["train"]
        core.atomic_json(run_path, record)
        spec = shared["models"]["m1"]
        model_path = core.resolve_project(spec["local_path"])
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        encodings, lengths = core.encode_rows(
            tokenizer, train_rows, spec["max_sequence_length"]
        )
        gold = np.asarray([row["labels"] for row in train_rows], dtype=np.uint8)
        dataset = core.EncodedDataset(encodings, gold)
        order = torch.randperm(
            len(dataset), generator=torch.Generator().manual_seed(42)
        ).tolist()
        steps = recovery["cpu_train_only_preflight_steps"]
        sample_count = steps * spec["batch_size"]
        selected = order[:sample_count]
        selection_digest = core.canonical_digest(
            [train_rows[index]["sample_id"] for index in selected]
        )
        loader = DataLoader(
            Subset(dataset, selected),
            batch_size=spec["batch_size"],
            shuffle=False,
            drop_last=False,
            num_workers=0,
            collate_fn=core.make_collator(tokenizer),
        )

        core.seed_everything(42, "cpu")
        model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            local_files_only=True,
            num_labels=len(core.LABELS),
            id2label={index: label for index, label in enumerate(core.LABELS)},
            label2id={label: index for index, label in enumerate(core.LABELS)},
            problem_type="multi_label_classification",
            ignore_mismatched_sizes=True,
        )
        model.to(torch.device("cpu"))
        optimizer = torch.optim.AdamW(
            core.optimizer_groups(
                model,
                spec["weight_decay"],
                run_config["execution"]["weight_decay_exclusions"],
            ),
            lr=spec["learning_rate"],
            betas=(
                run_config["execution"]["adam_beta1"],
                run_config["execution"]["adam_beta2"],
            ),
            eps=run_config["execution"]["adam_epsilon"],
        )
        total_steps = math.ceil(len(dataset) / spec["batch_size"]) * spec["epochs"]
        warmup_steps = int(total_steps * spec["warmup_ratio"])
        scheduler = LambdaLR(
            optimizer,
            lambda step: core.linear_schedule(step, warmup_steps, total_steps),
        )
        initial_classifier = core.tensor_digest(
            {
                name: value
                for name, value in model.named_parameters()
                if name.startswith("classifier.")
            }
        )
        model.train()
        losses = []
        training_started = time.perf_counter()
        for index, batch in enumerate(loader, start=1):
            moved = core.move_batch(batch, torch.device("cpu"))
            labels = moved.pop("labels")
            optimizer.zero_grad(set_to_none=True)
            logits = model(**moved).logits
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
            if not torch.isfinite(loss) or tuple(logits.shape) != (spec["batch_size"], 6):
                raise ValueError("CPU preflight finite-loss or shape gate failed")
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                model.parameters(), run_config["execution"]["max_grad_norm"]
            )
            if not torch.isfinite(gradient_norm):
                raise ValueError("CPU preflight gradient gate failed")
            optimizer.step()
            scheduler.step()
            losses.append(float(loss.detach()))
            logger.info(
                "CPU preflight step %d/%d loss %.6f lr %.8g",
                index,
                steps,
                losses[-1],
                optimizer.param_groups[0]["lr"],
            )
        training_seconds = time.perf_counter() - training_started
        final_classifier = core.tensor_digest(
            {
                name: value
                for name, value in model.named_parameters()
                if name.startswith("classifier.")
            }
        )
        if initial_classifier == final_classifier:
            raise ValueError("CPU preflight classifier did not update")
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_rss_gb = peak_rss / 1e9 if platform.system() == "Darwin" else peak_rss * 1024 / 1e9
        estimated_training_minutes = training_seconds / steps * total_steps / 60
        if estimated_training_minutes > run_config["execution"]["maximum_wall_minutes"] * 0.9:
            raise TimeoutError("CPU preflight projects training beyond the frozen budget")
        if peak_rss_gb > run_config["execution"]["maximum_peak_memory_gb"]:
            raise MemoryError("CPU preflight exceeds the frozen memory budget")

        logger.info(
            "CPU preflight passed: %.3fs/step, projected training %.1f min, peak RSS %.3f GB",
            training_seconds / steps,
            estimated_training_minutes,
            peak_rss_gb,
        )
        core.flush_logger(logger)
        record.update(
            {
                "status": "Passed",
                "completed_at_utc": core.utc_now(),
                "accessed_splits": ["train"],
                "validation_split_accessed": False,
                "test_split_accessed": False,
                "performance_metrics_computed": False,
                "authorization": run_config["authorization"],
                "incident": {
                    "failed_run": core.artifact(failed_run),
                    "failed_log": core.artifact(failed_log),
                    "validation_metric_before_failure": False,
                },
                "data": {
                    "protocol_id": shared["data"]["protocol_id"],
                    "train_rows": len(train_rows),
                    "train_sha256": shared["data"]["train_sha256"],
                    "selected_rows": sample_count,
                    "selection_digest_sha256": selection_digest,
                    "token_lengths": lengths,
                },
                "environment": environment,
                "model": model_record,
                "preflight": {
                    "steps": steps,
                    "batch_size": spec["batch_size"],
                    "logit_shapes": [[spec["batch_size"], 6]] * steps,
                    "finite_losses": losses,
                    "classifier_initial_sha256": initial_classifier,
                    "classifier_final_sha256": final_classifier,
                    "training_seconds": training_seconds,
                    "seconds_per_step": training_seconds / steps,
                    "projected_training_minutes": estimated_training_minutes,
                    "projected_total_minutes_note": "Training projection excludes five validation passes and artifact finalization.",
                    "total_formal_optimizer_steps": total_steps,
                    "warmup_steps": warmup_steps,
                    "peak_process_rss_gb": peak_rss_gb,
                },
                "resource_usage": {
                    "wall_seconds": time.perf_counter() - started,
                    "api_cost_usd": 0,
                },
                "frozen_sources": {
                    "config": core.artifact(config_path),
                    "preflight": core.artifact(Path(__file__).resolve()),
                    "runner": core.artifact(SCRIPT_DIR / "run_exp051_m1.py"),
                },
            }
        )
        core.atomic_json(run_path, record)
    except Exception as error:
        logger.exception("CPU recovery preflight failed")
        core.flush_logger(logger)
        record.update(
            {
                "status": "Failed",
                "failed_at_utc": core.utc_now(),
                "failure": {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                },
                "test_split_accessed": False,
                "performance_metrics_computed": False,
            }
        )
        core.atomic_json(run_path, record)
        raise
    finally:
        gc.collect()


if __name__ == "__main__":
    run()

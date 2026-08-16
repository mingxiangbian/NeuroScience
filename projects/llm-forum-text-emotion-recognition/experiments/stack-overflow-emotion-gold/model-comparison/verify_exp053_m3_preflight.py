#!/usr/bin/env python3
"""Independently verify the EXP-053 train-only Classification LoRA preflight."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
from typing import Any

import numpy as np
from safetensors.numpy import load_file as load_safetensors


EXPERIMENT_ID = "EXP-053"
STAGE = "train-only-resource-preflight"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = (
    SCRIPT_DIR / "configs" / "exp-053-m3-resource-preflight-seed-42-attempt-2.json"
)
DEFAULT_RUN_DIR = (
    SCRIPT_DIR
    / "runs"
    / "exp-053-m3-classification-lora-resource-preflight-seed-42-attempt-2"
)


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


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_matches(record: dict[str, Any]) -> bool:
    path = resolve_project(record["path"])
    return (
        path.is_file()
        and path.stat().st_size == int(record["bytes"])
        and sha256(path) == record["sha256"]
    )


def load_record(record: dict[str, Any]) -> dict[str, Any]:
    if not record_matches(record):
        raise ValueError(f"Artifact drift: {record['path']}")
    return json.loads(resolve_project(record["path"]).read_text(encoding="utf-8"))


def rank_key(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}|{value}".encode()).hexdigest()


def select_length_aware_rows(
    rows: list[dict[str, Any]],
    token_counts: dict[str, int],
    labels: list[str],
    namespace: str,
    sample_rows: int,
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(labels):
        candidates = [row for row in rows if row["labels"][index] == 1]
        candidates.sort(key=lambda row: rank_key(namespace, f"label|{label}|{row['sample_id']}"))
        selected.setdefault(candidates[0]["sample_id"], candidates[0])
    for criterion, candidates, required in (
        ("neutral", [row for row in rows if row["neutral"]], 4),
        ("multilabel", [row for row in rows if row["label_cardinality"] == 2], 4),
    ):
        candidates.sort(key=lambda row: rank_key(namespace, f"{criterion}|{row['sample_id']}"))
        added = 0
        for row in candidates:
            if row["sample_id"] in selected:
                continue
            selected[row["sample_id"]] = row
            added += 1
            if added == required:
                break
    ordered = sorted(
        rows,
        key=lambda row: (token_counts[row["sample_id"]], rank_key(namespace, row["sample_id"])),
    )
    lower_end = ordered[: max(1, len(ordered) // 10)]
    upper_start = min(len(ordered) - 1, len(ordered) * 9 // 10)
    upper_end = ordered[upper_start:]
    for boundary, boundary_candidates in (("lower", lower_end), ("upper", upper_end)):
        boundary_candidates.sort(
            key=lambda row: rank_key(namespace, f"length-{boundary}|{row['sample_id']}")
        )
        selected.setdefault(boundary_candidates[0]["sample_id"], boundary_candidates[0])

    grid_size = sample_rows * 8
    candidates: list[tuple[int, dict[str, Any]]] = []
    for slot in range(grid_size):
        index = min(len(ordered) - 1, ((2 * slot + 1) * len(ordered)) // (2 * grid_size))
        candidates.append((slot, ordered[index]))
    candidates.sort(key=lambda item: rank_key(namespace, f"quantile|{item[0]}"))
    for _, row in candidates:
        selected.setdefault(row["sample_id"], row)
        if len(selected) == sample_rows:
            break
    if len(selected) < sample_rows:
        for row in sorted(rows, key=lambda row: rank_key(namespace, f"fill|{row['sample_id']}")):
            selected.setdefault(row["sample_id"], row)
            if len(selected) == sample_rows:
                break
    return sorted(selected.values(), key=lambda row: rank_key(namespace, f"order|{row['sample_id']}"))


def load_train(shared: dict[str, Any]) -> list[dict[str, Any]]:
    path = resolve_project(shared["data"]["train_path"])
    if sha256(path) != shared["data"]["train_sha256"]:
        raise ValueError("Frozen train hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    expected = {
        "component_id", "label_cardinality", "labels", "neutral",
        "protocol_id", "sample_id", "schema_version", "text",
    }
    if len(rows) != shared["data"]["train_rows"]:
        raise ValueError("Train row count drift")
    for row in rows:
        if set(row) != expected or row["protocol_id"] != shared["data"]["protocol_id"]:
            raise ValueError("Train schema/protocol drift")
        if len(row["labels"]) != 6 or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError("Invalid label vector")
        if row["label_cardinality"] != sum(row["labels"]):
            raise ValueError("Label cardinality drift")
        if row["neutral"] != (sum(row["labels"]) == 0):
            raise ValueError("Neutral derivation drift")
    return rows


def load_prompt(shared: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project(shared["prompt"]["path"])
    if sha256(path) != shared["prompt"]["sha256"]:
        raise ValueError("Frozen prompt hash drift")
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_ids(tokenizer: Any, prompt: dict[str, Any], text: str, limit: int) -> list[int]:
    value = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user_prefix"] + text + prompt["user_suffix"]},
        ],
        tokenize=True,
        return_dict=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not isinstance(value, list) or any(type(token) is not int for token in value):
        raise TypeError("Tokenizer output contract drift")
    if len(value) > limit:
        raise ValueError("Frozen input exceeds max length")
    if not tokenizer.decode(value).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Frozen empty-think wrapper drift")
    return value


def mlx_items(module: Any) -> list[tuple[str, Any]]:
    from mlx.utils import tree_flatten
    return list(tree_flatten(module.trainable_parameters()))


def mlx_digest(items: list[tuple[str, Any]]) -> str:
    import mlx.core as mx
    digest = hashlib.sha256()
    for name, tensor in sorted(items):
        array = np.asarray(tensor.astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def build_head(seed: int, hidden_size: int) -> Any:
    import mlx.core as mx
    import mlx.nn as nn
    mx.random.seed(seed)
    return nn.Linear(hidden_size, 6, bias=True)


def make_wrapper(backbone: Any, head: Any) -> Any:
    import mlx.nn as nn

    class Wrapper(nn.Module):
        def __init__(self, base: Any, linear: Any):
            super().__init__()
            self.backbone = base
            self.head = linear

        def __call__(self, input_ids: Any) -> Any:
            hidden = self.backbone.model(input_ids)
            return self.head(hidden[:, -1, :].astype(self.head.weight.dtype))

    return Wrapper(backbone, head)


def insertion_set(model: Any) -> list[tuple[int, str]]:
    observed: list[tuple[int, str]] = []
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError(f"Unexpected LoRA module path: {name}")
        observed.append((int(match.group(1)), match.group(2)))
    return sorted(observed)


def parse_history(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            rows.append(
                {
                    "step": int(row["step"]),
                    "loss": float(row["loss"]),
                    "input_tokens": int(row["input_tokens"]),
                    "step_seconds": float(row["step_seconds"]),
                    "peak_mlx_memory_gb": float(row["peak_mlx_memory_gb"]),
                }
            )
    return rows


def projected_runtime(run: dict[str, Any], shared: dict[str, Any], config: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, float]:
    resources = run["resources"]
    warmup = config["execution"]["warmup_steps_excluded"]
    steady_mean = statistics.fmean(row["step_seconds"] for row in history[warmup:])
    forward_mean = resources["projection"]["forward_step_seconds"]["mean"]
    tokenization = resources["tokenization_seconds"] * (
        (shared["data"]["train_rows"] + shared["data"]["validation_rows"])
        / shared["data"]["train_rows"]
    )
    raw = (
        resources["model_load_seconds"]
        + tokenization
        + steady_mean * shared["models"]["qwen_shared"]["total_iterations_per_seed"]
        + forward_mean * shared["data"]["validation_rows"]
        + resources["checkpoint_write_seconds"]
    )
    safe = raw * config["execution"]["projection_safety_factor"]
    return {"raw_seconds": raw, "safe_seconds": safe, "per_seed_hours": safe / 3600, "three_seed_hours": safe * 3 / 3600}


def verify(config_path: Path, run_dir: Path) -> dict[str, Any]:
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError(f"Refusing to overwrite append-only output: {verification_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("identity", run.get("experiment_id") == EXPERIMENT_ID and run.get("stage") == STAGE)
    check("run_status", run.get("status") == "Passed")
    check("train_only", run.get("accessed_splits") == ["train"])
    check("validation_not_accessed", run.get("validation_split_accessed") is False)
    check("test_not_accessed", run.get("test_split_accessed") is False)
    check("no_performance_metrics", run.get("performance_metrics_computed") is False)
    check("formal_training_sealed", run.get("formal_training_authorized") is False)
    check("authorization_scope", config["authorization"]["splits"] == ["train"] and config["authorization"]["formal_training"] is False)

    for name, record in config["implementation"].items():
        check(f"source_{name}_hash", record_matches(record))
    check("source_shared_config_hash", record_matches(config["prerequisites"]["shared_config"]))
    for group in ("exp050", "m2_seed_42", "m2_aggregate"):
        for name, record in config["prerequisites"][group].items():
            check(f"source_{group}_{name}_hash", record_matches(record))
    for name, record in run["frozen_sources"].items():
        check(f"frozen_{name}_hash", record_matches(record))

    shared = load_record(config["prerequisites"]["shared_config"])
    exp050_verify = load_record(config["prerequisites"]["exp050"]["verification"])
    exp050_m3 = load_record(config["prerequisites"]["exp050"]["m3"])
    m2_run = load_record(config["prerequisites"]["m2_seed_42"]["run"])
    m2_verify = load_record(config["prerequisites"]["m2_seed_42"]["verification"])
    m2_aggregate_verify = load_record(config["prerequisites"]["m2_aggregate"]["verification"])
    check("shared_formal_execution_false", shared.get("formal_execution_authorized") is False)
    check("shared_test_sealed", shared["data"]["test_status"] == "sealed_not_authorized_for_model_access")
    check(
        "exp050_verified_77",
        exp050_verify.get("status") == "Passed"
        and exp050_verify.get("checks_passed") == 77
        and exp050_verify.get("checks_total") == 77
        and exp050_verify.get("failed_checks") == [],
    )
    check("exp050_m3_matched_gate", exp050_m3.get("zero_step_max_abs_logit_difference") == 0.0 and exp050_m3.get("insertion_count") == 112)
    check("m2_seed42_verified_70", m2_verify.get("status") == "Passed" and m2_verify.get("check_count") == 70)
    check("m2_head_reference", m2_run["model_runtime"]["head_initial_sha256"] == run["model"]["head_initial_sha256"])
    check("m2_aggregate_verified_85", m2_aggregate_verify.get("status") == "Passed" and m2_aggregate_verify.get("check_count") == 85)

    history_record = run["training"]["history"]
    check("history_hash", record_matches(history_record))
    history = parse_history(resolve_project(history_record["path"]))
    check("history_steps", [row["step"] for row in history] == list(range(1, 33)))
    check("history_finite_losses", len(history) == 32 and all(math.isfinite(row["loss"]) for row in history))
    check("history_positive_times", all(row["step_seconds"] > 0 for row in history))
    check("history_token_bounds", all(0 < row["input_tokens"] <= shared["prompt"]["max_sequence_length"] for row in history))
    check("separate_optimizers", run["training"]["separate_optimizers"] is True)
    check("head_optimizer", run["training"]["head_optimizer"] == {"name": "AdamW", "learning_rate": 0.0001, "weight_decay": 0.01})
    check("lora_optimizer", run["training"]["lora_optimizer"] == {"name": "AdamW", "learning_rate": 0.00001, "weight_decay": 0.01})
    check("gradient_checkpointing", run["training"]["gradient_checkpointing"] is True)

    model = run["model"]
    check("head_parameters", model["head_parameter_count"] == 15366)
    check("lora_parameters", model["lora_parameter_count"] == 7340032)
    check("total_trainable_parameters", model["total_trainable_parameter_count"] == 7355398)
    check("insertion_count", model["insertion_count"] == 112)
    check("zero_initial_delta", model["zero_step_max_abs_logit_difference"] == 0.0)
    check("all_lora_b_updated", model["nonzero_lora_b_tensors"] == 112)
    check("head_updated", model["head_initial_sha256"] != model["head_final_sha256"])
    check("lora_updated", model["lora_initial_sha256"] != model["lora_final_sha256"])
    check("base_sentinel_unchanged", model["base_parameter_sentinel_before"] == model["base_parameter_sentinel_after"])

    for name in ("adapter", "head", "reference_logits"):
        record = run["checkpoints"][name]
        check(f"checkpoint_{name}_hash", record_matches(record))
        path = resolve_project(record["path"])
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT
        ).returncode == 0
        check(f"checkpoint_{name}_gitignored", ignored)
    private_selection = run["data"]["private_selection"]
    check("private_selection_hash", record_matches(private_selection))
    check(
        "private_selection_gitignored",
        subprocess.run(["git", "check-ignore", "-q", str(resolve_project(private_selection["path"]))], cwd=REPO_ROOT).returncode == 0,
    )

    adapter_arrays = load_safetensors(str(resolve_project(run["checkpoints"]["adapter"]["path"])))
    head_arrays = load_safetensors(str(resolve_project(run["checkpoints"]["head"]["path"])))
    check("adapter_tensor_count", len(adapter_arrays) == 224)
    check("adapter_lora_a_count", sum(name.endswith("lora_a") for name in adapter_arrays) == 112)
    check("adapter_lora_b_count", sum(name.endswith("lora_b") for name in adapter_arrays) == 112)
    check("adapter_parameter_count", sum(array.size for array in adapter_arrays.values()) == 7340032)
    check("adapter_all_lora_b_nonzero", all(np.any(array != 0) for name, array in adapter_arrays.items() if name.endswith("lora_b")))
    check("head_tensor_names", set(head_arrays) == {"weight", "bias"})
    check("head_shapes", tuple(head_arrays["weight"].shape) == (6, 2560) and tuple(head_arrays["bias"].shape) == (6,))

    resources = run["resources"]
    recomputed = projected_runtime(run, shared, config, history)
    projection = resources["projection"]
    check("projection_raw_seconds", math.isclose(recomputed["raw_seconds"], projection["raw_per_seed_seconds"], rel_tol=0, abs_tol=1e-9))
    check("projection_safe_seconds", math.isclose(recomputed["safe_seconds"], projection["projected_per_seed_seconds_with_safety"], rel_tol=0, abs_tol=1e-9))
    check("projection_per_seed_hours", math.isclose(recomputed["per_seed_hours"], projection["projected_per_seed_hours_with_safety"], rel_tol=0, abs_tol=1e-12))
    check("projection_three_seed_hours", math.isclose(recomputed["three_seed_hours"], projection["projected_three_seed_hours_with_safety"], rel_tol=0, abs_tol=1e-12))
    phase_peaks = [
        resources["training_phase_peak_mlx_memory_gb"],
        resources["checkpoint_replay_phase_peak_mlx_memory_gb"],
    ]
    check(
        "phase_peak_accounting",
        resources["phase_peak_rule"]
        == "max_of_sequential_training_and_checkpoint_replay_process_phases"
        and math.isclose(resources["peak_mlx_memory_gb"], max(phase_peaks), rel_tol=0, abs_tol=1e-12),
    )
    check(
        "each_phase_memory_budget",
        all(value <= config["execution"]["maximum_peak_memory_gb"] for value in phase_peaks),
    )
    check("memory_budget", resources["peak_mlx_memory_gb"] <= config["execution"]["maximum_peak_memory_gb"])
    check("per_seed_budget", recomputed["per_seed_hours"] <= config["execution"]["maximum_projected_hours_per_seed"])
    check("three_seed_budget", recomputed["three_seed_hours"] <= config["execution"]["maximum_projected_hours_three_seeds"])
    check("resource_gate", resources["gate"]["passed"] is True and all(resources["gate"][key] for key in ("memory_passed", "per_seed_time_passed", "three_seed_time_passed")))
    check("api_cost_zero", resources["api_cost_usd"] == 0.0)
    check("network_false", resources["network_access"] is False)

    replay_error: str | None = None
    try:
        os.environ.update(
            {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
        )
        import mlx.core as mx
        from mlx_lm import load
        from mlx_lm.tuner import linear_to_lora_layers

        rows = load_train(shared)
        prompt = load_prompt(shared)
        model_path = resolve_project(shared["models"]["qwen_shared"]["local_path"])
        replay_model, tokenizer = load(str(model_path), lazy=False)
        token_ids = {
            row["sample_id"]: prompt_ids(
                tokenizer, prompt, row["text"], shared["prompt"]["max_sequence_length"]
            )
            for row in rows
        }
        token_counts = {sample_id: len(ids) for sample_id, ids in token_ids.items()}
        selected = select_length_aware_rows(
            rows,
            token_counts,
            shared["data"]["labels"],
            config["sampling"]["selection_namespace"],
            config["sampling"]["sample_rows"],
        )
        private_rows = load_record(private_selection)["rows"]
        expected_private = [
            {
                "order": index,
                "sample_id": row["sample_id"],
                "component_id": row["component_id"],
                "labels": row["labels"],
                "neutral": row["neutral"],
                "label_cardinality": row["label_cardinality"],
                "input_tokens": token_counts[row["sample_id"]],
            }
            for index, row in enumerate(selected)
        ]
        check("selection_recomputed", private_rows == expected_private)
        check("selection_digest", run["data"]["sample"]["selection_digest_sha256"] == canonical_digest([{"sample_id": row["sample_id"], "component_id": row["component_id"]} for row in selected]))
        check("selection_all_labels", all(value >= 1 for value in run["data"]["sample"]["positive_counts"].values()))
        check("selection_neutral_multilabel", run["data"]["sample"]["neutral_rows"] >= 4 and run["data"]["sample"]["cardinality_2_rows"] >= 4)

        replay_model.freeze()
        replay_model.eval()
        head = build_head(42, shared["models"]["qwen_shared"]["hidden_size"])
        check("recomputed_head_initial_hash", mlx_digest(mlx_items(head)) == config["execution"]["expected_head_initial_sha256"])
        wrapper = make_wrapper(replay_model, head)
        ids = mx.array([token_ids[selected[0]["sample_id"]]], dtype=mx.int32)
        base_logits = wrapper(ids)
        mx.eval(base_logits)
        lora = shared["models"]["lora_shared"]
        mx.random.seed(100042)
        linear_to_lora_layers(
            replay_model,
            lora["num_layers"],
            {"rank": lora["rank"], "scale": lora["scale"], "dropout": lora["dropout"], "keys": lora["target_modules"]},
        )
        converted_logits = wrapper(ids)
        mx.eval(converted_logits)
        check("recomputed_zero_delta", float(mx.max(mx.abs(base_logits - converted_logits)).item()) == 0.0)
        expected_insertions = sorted((block, module) for block in lora["adapted_block_indices"] for module in lora["target_modules"])
        check("recomputed_insertion_set", insertion_set(replay_model) == expected_insertions)
        replay_model.load_weights(str(resolve_project(run["checkpoints"]["adapter"]["path"])), strict=False)
        head.load_weights(str(resolve_project(run["checkpoints"]["head"]["path"])), strict=True)
        replay_logits = wrapper(ids)
        mx.eval(replay_logits)
        reference = load_safetensors(str(resolve_project(run["checkpoints"]["reference_logits"]["path"])))
        difference = float(np.max(np.abs(np.asarray(replay_logits.astype(mx.float32)) - reference["logits"].astype(np.float32))))
        check("independent_checkpoint_replay", difference <= config["execution"]["maximum_reload_logit_difference"], difference)
        check("runner_reload_record", run["checkpoints"]["reload_max_abs_logit_difference"] <= config["execution"]["maximum_reload_logit_difference"])
        check("reloaded_adapter_digest", mlx_digest(mlx_items(replay_model)) == run["model"]["lora_final_sha256"])
        check("reloaded_head_digest", mlx_digest(mlx_items(head)) == run["model"]["head_final_sha256"])
        del wrapper, head, replay_model, tokenizer
        gc.collect()
        mx.clear_cache()
    except Exception as exc:
        replay_error = f"{type(exc).__name__}: {exc}"
        check("independent_model_replay_completed", False, replay_error)
    else:
        check("independent_model_replay_completed", True)

    check("report_exists", (run_dir / "REPORT.md").is_file())
    check("stdout_log_exists", (run_dir / "stdout.log").is_file())
    check("environment_exists", (run_dir / "environment-freeze.txt").is_file())
    failed = [item["name"] for item in checks if not item["passed"]]
    verification = {
        "schema_version": "exp-053-m3-resource-preflight-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": STAGE,
        "status": "Passed" if not failed else "Failed",
        "verified_at_utc": utc_now(),
        "check_count": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "run_sha256": sha256(run_dir / "run.json"),
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "performance_metrics_computed": False,
        "formal_training_authorized": False,
        "replay_error": replay_error,
    }
    write_json(verification_path, verification)
    summary = f"""# EXP-053 M3 Resource Preflight Verification

- Status: `{verification['status']}`
- Checks: `{len(checks) - len(failed)}/{len(checks)}` passed
- Validation accessed: no
- Test accessed: no
- Performance metrics computed: no
- Formal EXP-053 training authorized by this gate: no
"""
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(summary, encoding="utf-8")
    return verification


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    result = verify(args.config.resolve(), args.run_dir.resolve())
    print(json.dumps({"status": result["status"], "check_count": result["check_count"], "failed": result["failed_checks"]}, sort_keys=True))
    if result["status"] != "Passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

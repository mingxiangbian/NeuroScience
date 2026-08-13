#!/usr/bin/env python3
"""Independently verify the no-model EXP-047 runner dry-run."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import stat
import statistics
import subprocess
import sys
from typing import Any, Iterable

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-047"
VERIFICATION_ID = "EXP-047-RUNNER-DRY-RUN-VERIFY-V1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the EXP-047 no-model dry-run")
    parser.add_argument("--check", action="store_true", help="Recompute and compare the frozen verification")
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def normalize_token_ids(value: Any) -> list[int]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in value
    ):
        raise TypeError("Chat template must return one flat integer token sequence")
    return value


def percentile(values: Iterable[int], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot summarize an empty sequence")
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def numeric_summary(values: list[int]) -> dict[str, Any]:
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
    }


def render_messages(
    config: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]
) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    assistant = prompt["assistant_target_template"].replace("{label}", row["label"])
    if json.loads(assistant) != {"label": row["label"]}:
        raise ValueError("Assistant target violates strict JSON schema")
    return [
        {
            "role": "system",
            "content": prompt["system_template"].format(
                label_definitions=definitions,
                output_schema=prompt["output_schema"],
            ),
        },
        {
            "role": "user",
            "content": prompt["target_only_template"].format(
                target=row["views"]["target_only"]["target"]
            ),
        },
        {"role": "assistant", "content": assistant},
    ]


def expected_runtime_config(config: dict[str, Any], seed: int) -> dict[str, Any]:
    training = config["training"]
    private_root = resolve_project_path(config["paths"]["private_root"])
    return {
        "adapter_path": str(private_root / "adapters" / f"seed-{seed}"),
        "batch_size": training["batch_size"],
        "clear_cache_threshold": 0,
        "data": str(private_root / "lora-data"),
        "fine_tune_type": "lora",
        "grad_accumulation_steps": training["grad_accumulation_steps"],
        "grad_checkpoint": training["grad_checkpoint"],
        "iters": training["total_iterations_per_seed"],
        "learning_rate": training["learning_rate"],
        "lora_parameters": {
            "dropout": training["dropout"],
            "keys": training["target_modules"],
            "rank": training["rank"],
            "scale": training["scale"],
        },
        "lr_schedule": training["lr_schedule"],
        "mask_prompt": training["mask_prompt"],
        "max_seq_length": training["max_sequence_length"],
        "model": str(resolve_project_path(config["model"]["local_path"])),
        "num_layers": training["num_layers"],
        "optimizer": training["optimizer"],
        "optimizer_config": training["optimizer_config"],
        "project_name": None,
        "report_to": None,
        "resume_adapter_file": None,
        "save_every": training["iterations_per_epoch"],
        "seed": seed,
        "steps_per_eval": training["total_iterations_per_seed"] + 1,
        "steps_per_report": 10,
        "test": False,
        "test_batches": 0,
        "train": True,
        "val_batches": 0,
    }


def inspect_runner_source(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imported_roots: set[str] = set()
    transformer_names: set[str] = set()
    forbidden_calls: list[str] = []
    command_choices: list[str] | None = None
    from_pretrained_calls: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
            if node.module == "transformers":
                transformer_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                forbidden_calls.append(node.func.id)
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    dotted = f"{node.func.value.id}.{node.func.attr}"
                    if dotted in {"os.system", "os.popen", "subprocess.run", "subprocess.Popen"}:
                        forbidden_calls.append(dotted)
                    if node.func.attr == "from_pretrained":
                        from_pretrained_calls.append(dotted)
                if node.func.attr == "add_argument" and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and first.value == "command":
                        for keyword in node.keywords:
                            if keyword.arg == "choices" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                                command_choices = [
                                    item.value
                                    for item in keyword.value.elts
                                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                                ]

    banned_imports = sorted(imported_roots & {"mlx", "mlx_lm", "torch", "subprocess"})
    passed = (
        not banned_imports
        and not forbidden_calls
        and transformer_names == {"AutoTokenizer"}
        and from_pretrained_calls == ["AutoTokenizer.from_pretrained"]
        and command_choices == ["dry-run"]
    )
    return {
        "banned_imports": banned_imports,
        "command_choices": command_choices,
        "forbidden_calls": forbidden_calls,
        "from_pretrained_calls": from_pretrained_calls,
        "passed": passed,
        "transformers_imports": sorted(transformer_names),
    }


def verify_environment(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config["runtime"]
    python_path = Path(runtime["python_executable"])
    if not python_path.is_file() or not Path(sys.executable).samefile(python_path):
        raise ValueError("Verifier is not running under the frozen Python executable")
    packages = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in runtime["packages"]
    }
    cli = Path(runtime["mlx_lora_cli"]["path"])
    if packages != runtime["packages"] or not cli.is_file():
        raise ValueError("Frozen runtime drift")
    if not os.access(cli, os.X_OK) or sha256_file(cli) != runtime["mlx_lora_cli"]["sha256"]:
        raise ValueError("Frozen MLX-LM CLI drift")
    return {
        "mlx_lora_cli": artifact(cli),
        "offline_environment": True,
        "packages": packages,
        "python_executable": str(python_path),
    }


def verify_model_files(config: dict[str, Any]) -> dict[str, Any]:
    model = config["model"]
    manifest_path = resolve_project_path(model["manifest_path"])
    if sha256_file(manifest_path) != model["manifest_sha256"]:
        raise ValueError("Model manifest drift")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("repo_id") != model["repo_id"] or manifest.get("revision") != model["revision"]:
        raise ValueError("Model identity drift")
    model_root = resolve_project_path(model["local_path"])
    stream = hashlib.sha256()
    total_bytes = 0
    files = manifest["mlx_bf16"]["files"]
    for expected in files:
        path = model_root / expected["path"]
        observed = {
            "bytes": path.stat().st_size if path.is_file() else -1,
            "path": expected["path"],
            "sha256": sha256_file(path) if path.is_file() else None,
        }
        if observed != expected:
            raise ValueError(f"Model file drift: {path}")
        stream.update(
            f"{expected['path']}\0{expected['bytes']}\0{expected['sha256']}\n".encode("utf-8")
        )
        total_bytes += expected["bytes"]
    if len(files) != manifest["mlx_bf16"]["file_count"] or total_bytes != manifest["mlx_bf16"]["total_bytes"]:
        raise ValueError("Model manifest totals drift")
    return {
        "file_count": len(files),
        "files_manifest_sha256": stream.hexdigest(),
        "manifest": artifact(manifest_path),
        "model_weights_loaded": False,
        "total_bytes": total_bytes,
        "weight_files_hashed": True,
    }


def reconstruct_train(
    config: dict[str, Any],
) -> tuple[bytes, dict[str, Any], list[str], list[str], list[str]]:
    train_path = resolve_project_path(config["data"]["train_path"])
    prompt_path = resolve_project_path(config["implementation"]["prompt_path"])
    if sha256_file(train_path) != config["data"]["train_sha256"]:
        raise ValueError("Frozen train drift")
    if sha256_file(prompt_path) != config["implementation"]["prompt_sha256"]:
        raise ValueError("Frozen prompt drift")
    prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    labels = config["data"]["labels"]
    if list(prompt["label_definitions"]) != labels:
        raise ValueError("Prompt label order drift")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        resolve_project_path(config["model"]["local_path"]),
        local_files_only=True,
    )
    expected_fields = {
        "ambiguous_target",
        "context_available",
        "group_id",
        "label",
        "protocol_id",
        "sample_id",
        "schema_version",
        "views",
    }
    prepared: list[bytes] = []
    raw_targets: list[str] = []
    sample_ids: list[str] = []
    group_ids: list[str] = []
    seen_samples: set[str] = set()
    seen_groups: set[str] = set()
    label_counts: Counter[str] = Counter()
    token_lengths: list[int] = []
    supervised_lengths: list[int] = []
    target_stream = hashlib.sha256()
    wrapper = "<think>\n\n</think>\n\n"

    with train_path.open("r", encoding="utf-8") as source:
        for row_number, line in enumerate(source, start=1):
            row = json.loads(line)
            if set(row) != expected_fields or row.get("protocol_id") != config["data"]["protocol_id"]:
                raise ValueError(f"Train schema drift at row {row_number}")
            if row["label"] not in labels or row["sample_id"] in seen_samples:
                raise ValueError(f"Train identity drift at row {row_number}")
            if set(row["views"]) != {"previous_context", "target_only"}:
                raise ValueError(f"View schema drift at row {row_number}")
            if set(row["views"]["target_only"]) != {"target"}:
                raise ValueError(f"Target-only schema drift at row {row_number}")
            target = row["views"]["target_only"]["target"]
            if not isinstance(target, str) or not target:
                raise ValueError(f"Invalid target at row {row_number}")
            messages = render_messages(config, prompt, row)
            token_ids = normalize_token_ids(tokenizer.apply_chat_template(messages, return_dict=False))
            prompt_ids = normalize_token_ids(
                tokenizer.apply_chat_template(
                    messages[:-1],
                    add_generation_prompt=True,
                    return_dict=False,
                )
            )
            if token_ids[: len(prompt_ids)] != prompt_ids:
                raise ValueError(f"Prompt prefix drift at row {row_number}")
            supervised = tokenizer.decode(token_ids[len(prompt_ids) :])
            expected_supervised = wrapper + messages[-1]["content"] + "<|im_end|>\n"
            if supervised != expected_supervised:
                raise ValueError(f"Supervision boundary drift at row {row_number}")
            if len(token_ids) > config["training"]["max_sequence_length"]:
                raise ValueError(f"Token budget exceeded at row {row_number}")

            prepared.append(
                (json.dumps({"messages": messages}, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
                    "utf-8"
                )
            )
            raw_targets.append(target)
            sample_ids.append(row["sample_id"])
            group_ids.append(row["group_id"])
            seen_samples.add(row["sample_id"])
            seen_groups.add(row["group_id"])
            label_counts[row["label"]] += 1
            token_lengths.append(len(token_ids))
            supervised_lengths.append(len(token_ids) - len(prompt_ids))
            target_stream.update(
                f"{row_number}\t{row['label']}\t{len(token_ids)}\t{len(token_ids) - len(prompt_ids)}\n".encode(
                    "utf-8"
                )
            )

    if len(prepared) != config["data"]["train_rows"] or set(label_counts) != set(labels):
        raise ValueError("Full-train row count or label coverage drift")
    prepared_bytes = b"".join(prepared)
    summary = {
        "group_count": len(seen_groups),
        "label_counts": {label: label_counts[label] for label in labels},
        "prepared_bytes": len(prepared_bytes),
        "prepared_sha256": sha256_bytes(prepared_bytes),
        "raw_ids_stored_publicly": False,
        "raw_text_stored_publicly": False,
        "rows": len(prepared),
        "supervised_token_lengths": numeric_summary(supervised_lengths),
        "target_stream_sha256": target_stream.hexdigest(),
        "template_contract": {
            "assistant_target": "strict JSON single label",
            "empty_think_wrapper_inserted_by_chat_template": True,
            "input_view": "target_only",
            "mask_prompt": True,
            "rationale_gold": False,
        },
        "token_lengths": numeric_summary(token_lengths),
        "truncated_rows": 0,
    }
    return prepared_bytes, summary, raw_targets, sample_ids, group_ids


def resource_contract_is_consistent(config: dict[str, Any]) -> bool:
    budget = config["resource_budget"]
    training = config["training"]
    evaluation = config["evaluation"]
    gate = config["runtime_gate"]
    return (
        training["iterations_per_epoch"] == config["data"]["train_rows"]
        and training["total_iterations_per_seed"]
        == training["iterations_per_epoch"] * training["epochs"]
        and budget["training_total_hours_max"]
        == budget["training_hours_per_seed_max"] * len(training["seeds"])
        and budget["full_dev_total_hours_max"]
        == budget["full_dev_pass_hours_max"] * evaluation["formal_dev_passes"]
        and budget["total_active_hours_max"]
        == budget["training_total_hours_max"]
        + budget["post_adapter_replay_total_hours_max"]
        + budget["full_dev_total_hours_max"]
        + budget["aggregation_verification_hours_max"]
        and evaluation["formal_dev_generations"]
        == config["data"]["validation_rows"] * evaluation["formal_dev_passes"]
        and gate["replay_total_generations"]
        == gate["replay_rows"] * gate["replay_passes_per_adapter"] * len(training["seeds"])
    )


def git_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def contains_private_material(
    content: bytes, raw_targets: list[str], sample_ids: list[str], group_ids: list[str]
) -> bool:
    text = content.decode("utf-8")
    if any(value in text for value in sample_ids) or any(value in text for value in group_ids):
        return True
    return any(len(target) >= 4 and target in text for target in raw_targets)


def build_verification(config: dict[str, Any], completed_at_utc: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"check": name, "detail": detail, "status": "Passed" if passed else "Failed"})

    check(
        "registration-and-split-gates",
        config.get("experiment_id") == EXPERIMENT_ID
        and config.get("tier") == "Major"
        and config.get("status") == "Registered"
        and config["execution"].get("authorized") is False
        and config["data"].get("test_access") is False
        and config["data"].get("validation_access")
        == "deferred_until_all_adapters_pass_train_only_gates",
        {
            "execution_authorized": config["execution"].get("authorized"),
            "status": config.get("status"),
            "test_access": config["data"].get("test_access"),
            "validation_access": config["data"].get("validation_access"),
        },
    )

    implementation = config["implementation"]
    frozen_paths = {
        "runner": (implementation["runner_path"], implementation["runner_sha256"]),
        "test": (implementation["test_path"], implementation["test_sha256"]),
        "verifier": (implementation["verifier_path"], implementation["verifier_sha256"]),
        "protocol": (config["paths"]["protocol"], config["paths"]["protocol_sha256"]),
        "prompt": (implementation["prompt_path"], implementation["prompt_sha256"]),
        "parser": (implementation["parser_path"], implementation["parser_sha256"]),
        "requirements": (implementation["requirements_path"], implementation["requirements_sha256"]),
    }
    frozen_observed = {
        name: sha256_file(resolve_project_path(path_value)) for name, (path_value, _) in frozen_paths.items()
    }
    check(
        "frozen-source-and-protocol-hashes",
        all(frozen_observed[name] == digest for name, (_, digest) in frozen_paths.items()),
        frozen_observed,
    )

    runner_path = resolve_project_path(implementation["runner_path"])
    source_safety = inspect_runner_source(runner_path)
    check("runner-has-only-no-model-dry-run-entrypoint", source_safety["passed"], source_safety)

    environment = verify_environment(config)
    check("frozen-offline-runtime", environment["packages"] == config["runtime"]["packages"], environment)
    model = verify_model_files(config)
    check(
        "model-identity-hashed-without-weight-loading",
        model["model_weights_loaded"] is False and model["weight_files_hashed"] is True,
        {key: model[key] for key in ("file_count", "files_manifest_sha256", "total_bytes")},
    )

    prepared_bytes, train_summary, raw_targets, sample_ids, group_ids = reconstruct_train(config)
    check(
        "full-train-render-and-token-contract",
        train_summary["rows"] == config["data"]["train_rows"]
        and train_summary["truncated_rows"] == 0
        and train_summary["token_lengths"]["max"] <= config["training"]["max_sequence_length"],
        {
            "label_counts": train_summary["label_counts"],
            "rows": train_summary["rows"],
            "supervised_token_lengths": train_summary["supervised_token_lengths"],
            "token_lengths": train_summary["token_lengths"],
            "truncated_rows": train_summary["truncated_rows"],
        },
    )

    private_root = resolve_project_path(config["paths"]["private_root"])
    private_train = private_root / "lora-data" / "train.jsonl"
    private_files = sorted(path.relative_to(private_root).as_posix() for path in private_root.rglob("*") if path.is_file())
    private_modes = {
        "private_root": oct(stat.S_IMODE(private_root.stat().st_mode)),
        "lora_data": oct(stat.S_IMODE(private_train.parent.stat().st_mode)),
        "train": oct(stat.S_IMODE(private_train.stat().st_mode)),
    }
    check(
        "private-prepared-train-is-exact-and-isolated",
        private_train.read_bytes() == prepared_bytes
        and private_files == ["lora-data/train.jsonl"]
        and private_modes == {"private_root": "0o700", "lora_data": "0o700", "train": "0o600"}
        and git_ignored(private_train),
        {
            "files": private_files,
            "gitignored": git_ignored(private_train),
            "modes": private_modes,
            "prepared_sha256": sha256_file(private_train),
        },
    )

    runtime_artifacts: dict[str, dict[str, Any]] = {}
    runtime_ok = True
    public_contents: list[bytes] = []
    for seed in config["training"]["seeds"]:
        path = resolve_project_path(config["paths"]["runtime_config_pattern"].format(seed=seed))
        expected = expected_runtime_config(config, seed)
        observed = json.loads(path.read_text(encoding="utf-8"))
        runtime_ok = runtime_ok and observed == expected
        runtime_ok = runtime_ok and observed["train"] is True and observed["test"] is False
        runtime_ok = runtime_ok and observed["val_batches"] == 0 and observed["test_batches"] == 0
        runtime_artifacts[str(seed)] = artifact(path)
        public_contents.append(path.read_bytes())
    check(
        "three-seed-train-only-runtime-configs",
        runtime_ok and set(runtime_artifacts) == {str(seed) for seed in config["training"]["seeds"]},
        {"seeds": config["training"]["seeds"], "train_only": runtime_ok},
    )

    report_path = resolve_project_path(config["paths"]["dry_run_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    public_contents.append(report_path.read_bytes())
    expected_implementation = {
        "runner": artifact(runner_path),
        "test": artifact(resolve_project_path(implementation["test_path"])),
        "verifier": artifact(resolve_project_path(implementation["verifier_path"])),
    }
    report_ok = (
        report.get("experiment_id") == EXPERIMENT_ID
        and report.get("status") == "Passed"
        and report.get("stage") == "no-model-runner-dry-run"
        and report.get("accessed_splits") == ["train"]
        and report.get("validation_split_accessed") is False
        and report.get("test_split_accessed") is False
        and report.get("model_weights_loaded") is False
        and report.get("model_forward_or_backward_executed") is False
        and report.get("mlx_lora_subprocess_executed") is False
        and report.get("tokenizer_loaded") is True
        and report.get("train") == train_summary
        and report.get("prepared_train") == artifact(private_train)
        and report.get("runtime_configs") == runtime_artifacts
        and report.get("implementation") == expected_implementation
        and report.get("config") == artifact(CONFIG_PATH)
        and report.get("protocol") == artifact(resolve_project_path(config["paths"]["protocol"]))
        and report.get("environment") == environment
        and report.get("model") == model
        and report.get("execution_gate", {}).get("formal_execution_entrypoints_present") is False
        and report.get("execution_gate", {}).get("model_commands_executed") == []
    )
    check(
        "public-dry-run-report-reconstructs",
        report_ok,
        {
            "accessed_splits": report.get("accessed_splits"),
            "prepared_sha256": report.get("prepared_train", {}).get("sha256"),
            "status": report.get("status"),
        },
    )

    no_private_material = all(
        not contains_private_material(content, raw_targets, sample_ids, group_ids)
        for content in public_contents
    )
    check(
        "public-artifacts-contain-no-row-text-or-identifiers",
        no_private_material,
        {"public_files_scanned": len(public_contents), "target_minimum_scan_length": 4},
    )
    check(
        "resource-and-count-arithmetic",
        resource_contract_is_consistent(config),
        {
            "formal_dev_generations": config["evaluation"]["formal_dev_generations"],
            "replay_generations": config["runtime_gate"]["replay_total_generations"],
            "total_active_hours_max": config["resource_budget"]["total_active_hours_max"],
            "training_iterations_per_seed": config["training"]["total_iterations_per_seed"],
        },
    )

    mismatches = [item["check"] for item in checks if item["status"] != "Passed"]
    return {
        "accessed_splits": ["train"],
        "checks": checks,
        "checks_passed": len(checks) - len(mismatches),
        "completed_at_utc": completed_at_utc,
        "experiment_id": EXPERIMENT_ID,
        "mismatches": mismatches,
        "model_execution": False,
        "prepared_train_sha256": sha256_bytes(prepared_bytes),
        "status": "Passed" if not mismatches else "Failed",
        "test_split_accessed": False,
        "training_executed": False,
        "validation_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }


def main() -> int:
    args = parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    output = resolve_project_path(config["paths"]["dry_run_verification"])
    if args.check:
        existing = json.loads(output.read_text(encoding="utf-8"))
        verification = build_verification(config, existing["completed_at_utc"])
        if json_bytes(existing) != json_bytes(verification):
            raise ValueError("Frozen verification does not reproduce exactly")
        print(json.dumps({"checks_passed": verification["checks_passed"], "status": "Passed"}, sort_keys=True))
        return 0

    if output.exists():
        raise FileExistsError("EXP-047 dry-run verification is append-only")
    verification = build_verification(config, datetime.now(timezone.utc).isoformat())
    if verification["mismatches"]:
        raise RuntimeError(f"Dry-run verification failed: {verification['mismatches']}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as target:
        target.write(json_bytes(verification))
    print(json.dumps({"checks_passed": verification["checks_passed"], "status": "Passed"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

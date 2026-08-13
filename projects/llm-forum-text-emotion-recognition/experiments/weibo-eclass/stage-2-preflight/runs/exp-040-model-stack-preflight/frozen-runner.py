#!/usr/bin/env python3
"""Run the train-only EXP-040 Stage 2 model-stack preflight."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any, Callable, Iterable


EXPERIMENT_ID = "EXP-040"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIG_PATH = SCRIPT_DIR / "config.json"
PROMPT_PATH = SCRIPT_DIR / "prompt-v1.json"
PARSER_PATH = SCRIPT_DIR / "label_parser.py"
VERIFIER_PATH = SCRIPT_DIR / "verify_preflight.py"
MLX_PYTHON = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python")
MLX_CONVERT = MLX_PYTHON.parent / "mlx_lm.convert"
MLX_LORA = MLX_PYTHON.parent / "mlx_lm.lora"
TRAIN_LOG_PATTERN = re.compile(
    r"Iter (?P<iteration>\d+): Train loss (?P<loss>[^,]+), "
    r"Learning Rate (?P<learning_rate>[^,]+), It/sec (?P<iterations_per_second>[^,]+), "
    r"Tokens/sec (?P<tokens_per_second>[^,]+), Trained Tokens (?P<trained_tokens>\d+), "
    r"Peak mem (?P<peak_memory_gb>[^ ]+) GB"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("static", "models", "tokenize", "classical", "encoder", "qwen", "lora"),
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    write_json(path, value)
    os.chmod(path, 0o600)


def write_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def secure_private_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in [root, *(item for item in root.rglob("*") if item.is_dir())]:
        os.chmod(path, 0o700)
    for path in (item for item in root.rglob("*") if item.is_file()):
        os.chmod(path, 0o600)


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"bytes": path.stat().st_size, "path": display_path(path), "sha256": sha256_file(path)}


def inventory(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        files.append(
            {
                "bytes": path.stat().st_size,
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
            }
        )
    return {
        "file_count": len(files),
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files),
    }


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("tier") != "Minor"
        or config.get("status") != "Registered"
    ):
        raise ValueError("EXP-040 must remain a registered Minor experiment")
    if config["data"]["validation_access"] or config["data"]["test_access"]:
        raise ValueError("EXP-040 must remain train-only")
    implementation = config["implementation"]
    if any(value == "PENDING" for key, value in implementation.items() if key.endswith("sha256")):
        raise ValueError("Implementation hashes must be frozen before execution")
    bindings = (
        (implementation["parser_path"], implementation["parser_sha256"]),
        (implementation["prompt_path"], implementation["prompt_sha256"]),
        (implementation["runner_path"], implementation["runner_sha256"]),
        (implementation["verifier_path"], implementation["verifier_sha256"]),
    )
    for relative, expected in bindings:
        path = resolve_project_path(relative)
        if sha256_file(path) != expected:
            raise ValueError(f"Frozen implementation hash mismatch: {relative}")
    return config


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def package_versions(names: Iterable[str]) -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version()}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def run_dir(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["run_dir"])


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["private_root"])


def initialize_run(config: dict[str, Any]) -> dict[str, Any]:
    root = run_dir(config)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Append-only run directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    private = private_root(config)
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(private, 0o700)
    run = {
        "accessed_splits": ["train"],
        "command_history": [],
        "config": artifact(CONFIG_PATH),
        "experiment_id": EXPERIMENT_ID,
        "git": git_metadata(),
        "rq_ids": config["rq_ids"],
        "stage": "environment-model-parser-lora-preflight",
        "stages": {},
        "started_at_utc": utc_now(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Minor",
        "validation_split_accessed": False,
    }
    write_json(root / "run.json", run)
    return run


def load_run(config: dict[str, Any]) -> dict[str, Any]:
    path = run_dir(config) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Run static before later EXP-040 stages")
    run = json.loads(path.read_text(encoding="utf-8"))
    if run.get("experiment_id") != EXPERIMENT_ID or run.get("accessed_splits") != ["train"]:
        raise ValueError("Run metadata drift")
    return run


def require_stages(run: dict[str, Any], *names: str) -> None:
    missing = [name for name in names if run.get("stages", {}).get(name, {}).get("status") != "Passed"]
    if missing:
        raise RuntimeError(f"Required preflight stages have not passed: {missing}")


def record_stage(
    config: dict[str, Any],
    name: str,
    report_path: Path,
    status: str,
    started_at: str,
    started: float,
) -> None:
    run = load_run(config)
    if name in run["stages"]:
        raise FileExistsError(f"Stage is append-only once recorded: {name}")
    run["command_history"].append(f"{sys.executable} {display_path(Path(__file__))} {name}")
    run["stages"][name] = {
        "artifact": artifact(report_path),
        "completed_at_utc": utc_now(),
        "duration_seconds": time.perf_counter() - started,
        "started_at_utc": started_at,
        "status": status,
    }
    statuses = [item["status"] for item in run["stages"].values()]
    if "blocked_gpu_required" in statuses:
        run["status"] = "Blocked"
    elif "Failed" in statuses:
        run["status"] = "Failed"
    elif len(run["stages"]) == 7 and set(statuses) == {"Passed"}:
        run["status"] = "Awaiting Independent Verification"
    else:
        run["status"] = "In Progress"
    write_json(run_dir(config) / "run.json", run)


def load_train(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = resolve_project_path(config["data"]["train_path"])
    if sha256_file(path) != config["data"]["train_sha256"]:
        raise ValueError("Frozen train hash mismatch")
    expected_keys = {
        "ambiguous_target",
        "context_available",
        "group_id",
        "label",
        "protocol_id",
        "sample_id",
        "schema_version",
        "views",
    }
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            if set(row) != expected_keys:
                raise ValueError(f"Unexpected train schema at line {line_number}")
            if row["protocol_id"] != config["data"]["protocol_id"]:
                raise ValueError(f"Protocol mismatch at line {line_number}")
            if row["label"] not in config["data"]["labels"]:
                raise ValueError(f"Unknown label at line {line_number}")
            target = row["views"]["target_only"]["target"]
            paired = row["views"]["previous_context"]
            if not isinstance(target, str) or not target or paired["target"] != target:
                raise ValueError(f"Paired target mismatch at line {line_number}")
            previous = paired["previous"]
            if bool(previous) != bool(row["context_available"]):
                raise ValueError(f"Context flag mismatch at line {line_number}")
            rows.append(row)
    if len(rows) != config["data"]["train_rows"]:
        raise ValueError("Train row count mismatch")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError("Train sample IDs are not unique")
    return rows


def select_rows(config: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    strata: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    seed = config["data"]["selection_seed"]
    for row in rows:
        selected = dict(row)
        selected["selector_sha256"] = sha256_text(f"{seed}:{row['sample_id']}")
        strata[(row["label"], bool(row["context_available"]))].append(selected)
    result: list[dict[str, Any]] = []
    per_stratum = config["data"]["selection_per_label_context_stratum"]
    for label in config["data"]["labels"]:
        for context_available in (False, True):
            values = sorted(
                strata[(label, context_available)],
                key=lambda row: (row["selector_sha256"], row["sample_id"]),
            )
            if len(values) < per_stratum:
                raise ValueError(f"Insufficient rows in stratum {(label, context_available)}")
            for rank, row in enumerate(values[:per_stratum]):
                row["selection_rank"] = rank
                result.append(row)
    if len(result) != config["data"]["selection_rows"]:
        raise ValueError("Deterministic selection count mismatch")
    return result


def load_selection(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = private_root(config) / "selection.jsonl"
    if not path.is_file():
        raise FileNotFoundError("Private selection is missing")
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def load_prompt(config: dict[str, Any]) -> dict[str, Any]:
    prompt = json.loads(resolve_project_path(config["implementation"]["prompt_path"]).read_text(encoding="utf-8"))
    if tuple(prompt["label_definitions"]) != tuple(config["data"]["labels"]):
        raise ValueError("Prompt label order differs from frozen ontology")
    return prompt


def prompt_messages(
    config: dict[str, Any],
    prompt: dict[str, Any],
    row: dict[str, Any],
    view: str,
    *,
    previous_override: str | None | object = Ellipsis,
    include_target: bool = False,
) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions,
        output_schema=prompt["output_schema"],
    )
    target = row["views"]["target_only"]["target"]
    if view == "target_only":
        user = prompt["target_only_template"].format(target=target)
    elif view == "previous_context":
        previous = row["views"]["previous_context"]["previous"]
        if previous_override is not Ellipsis:
            previous = previous_override
        if not previous:
            user = prompt["target_only_template"].format(target=target)
        else:
            user = prompt["previous_context_template"].format(previous=previous, target=target)
    else:
        raise ValueError(f"Unknown input view: {view}")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if include_target:
        messages.append(
            {
                "role": "assistant",
                "content": render_assistant_target(prompt, row["label"]),
            }
        )
    return messages


def render_assistant_target(prompt: dict[str, Any], label: str) -> str:
    template = prompt["assistant_target_template"]
    if template.count("{label}") != 1:
        raise ValueError("Assistant target template must contain one literal {label} slot")
    rendered = template.replace("{label}", label)
    if json.loads(rendered) != {"label": label}:
        raise ValueError("Rendered assistant target violates the frozen JSON schema")
    return rendered


def classifier_text(prompt: dict[str, Any], row: dict[str, Any], view: str, previous: str | None = None) -> str:
    target = row["views"]["target_only"]["target"]
    if view == "target_only":
        return prompt["target_only_template"].format(target=target)
    if view != "previous_context":
        raise ValueError(view)
    if previous is None:
        previous = row["views"]["previous_context"]["previous"]
    if not previous:
        return prompt["target_only_template"].format(target=target)
    return prompt["previous_context_template"].format(previous=previous, target=target)


def quantile(values: list[float | int], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot summarize an empty sequence")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: list[float | int]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "p50": quantile(values, 0.50),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
    }


def run_static(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    initialize_run(config)
    rows = load_train(config)
    selected = select_rows(config, rows)
    selection_path = private_root(config) / "selection.jsonl"
    if selection_path.exists():
        raise FileExistsError(selection_path)
    write_private_jsonl(selection_path, selected)
    prompt = load_prompt(config)
    checks = Counter()
    for row in selected:
        target_messages = prompt_messages(config, prompt, row, "target_only")
        context_messages = prompt_messages(config, prompt, row, "previous_context")
        if target_messages[0] != context_messages[0]:
            raise ValueError("System prompt changed across input views")
        target = row["views"]["target_only"]["target"]
        if target not in target_messages[1]["content"] or target not in context_messages[1]["content"]:
            raise ValueError("Target boundary disappeared during prompt construction")
        if row["context_available"]:
            previous = row["views"]["previous_context"]["previous"]
            if previous not in context_messages[1]["content"]:
                raise ValueError("Frozen preceding context disappeared")
            checks["context_prompt_rows"] += 1
        else:
            if target_messages != context_messages:
                raise ValueError("Missing-context row changed between paired prompts")
            checks["missing_context_fallback_rows"] += 1
        target_json = render_assistant_target(prompt, row["label"])
        if json.loads(target_json) != {"label": row["label"]}:
            raise ValueError("Assistant target schema drift")
        checks["prompt_rows_checked"] += 1
    population = Counter((row["label"], bool(row["context_available"])) for row in rows)
    selected_counts = Counter((row["label"], bool(row["context_available"])) for row in selected)
    material = "\n".join(row["sample_id"] for row in selected)
    report = {
        "accessed_splits": ["train"],
        "checks": dict(sorted(checks.items())),
        "completed_at_utc": utc_now(),
        "data_protocol": config["data"]["protocol_id"],
        "experiment_id": EXPERIMENT_ID,
        "private_selection": {
            "artifact_sha256": sha256_file(selection_path),
            "path_publicly_disclosed": False,
            "row_level_data_public": False,
        },
        "raw_ids_stored_publicly": False,
        "raw_text_stored_publicly": False,
        "selection_digest_sha256": sha256_text(material),
        "selection_rows": len(selected),
        "status": "Passed",
        "strata": [
            {
                "context_available": context,
                "label": label,
                "population": population[(label, context)],
                "selected": selected_counts[(label, context)],
            }
            for label in config["data"]["labels"]
            for context in (False, True)
        ],
        "test_split_accessed": False,
        "train_rows_scanned": len(rows),
        "validation_split_accessed": False,
    }
    path = run_dir(config) / "static.json"
    write_json(path, report)
    record_stage(config, "static", path, "Passed", started_at, started)
    print(json.dumps({"stage": "static", "selection_rows": len(selected), "status": "Passed"}))


def retry_snapshot_download(**kwargs: Any) -> Path:
    from huggingface_hub import snapshot_download

    errors: list[str] = []
    for attempt in range(1, 3):
        try:
            return Path(snapshot_download(**kwargs)).resolve()
        except Exception as error:  # network failures vary by hub version
            errors.append(f"attempt-{attempt}:{type(error).__name__}")
            if attempt == 2:
                raise RuntimeError(f"Model download failed twice: {errors}") from error
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def validate_remote_model(spec: dict[str, Any]) -> dict[str, Any]:
    from huggingface_hub import model_info

    remote = model_info(spec["repo_id"], revision=spec["revision"])
    if remote.sha != spec["revision"]:
        raise ValueError(f"Resolved revision mismatch for {spec['repo_id']}")
    card = remote.card_data or {}
    license_value = card.get("license") if hasattr(card, "get") else getattr(card, "license", None)
    if str(license_value).lower() != spec["license"].lower():
        raise ValueError(f"License mismatch for {spec['repo_id']}: {license_value}")
    return {"license": str(license_value), "repo_id": spec["repo_id"], "revision": remote.sha}


def run_models(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    require_stages(run, "static")
    output = run_dir(config) / "models.json"
    if output.exists():
        raise FileExistsError(output)
    qwen = config["qwen"]
    encoder = config["encoder"]
    qwen_root = resolve_project_path(qwen["local_path"]).parent
    qwen_upstream = qwen_root / "upstream"
    qwen_mlx = resolve_project_path(qwen["local_path"])
    qwen_temp = qwen_root / "mlx-bf16.tmp"
    encoder_root = resolve_project_path(encoder["local_path"]).parent
    encoder_snapshot = resolve_project_path(encoder["local_path"])
    remote_qwen = validate_remote_model(qwen)
    remote_encoder = validate_remote_model(encoder)
    qwen_upstream.mkdir(parents=True, exist_ok=True)
    resolved_qwen = retry_snapshot_download(
        repo_id=qwen["repo_id"],
        revision=qwen["revision"],
        local_dir=qwen_upstream,
        allow_patterns=[
            "*.json",
            "*.jinja",
            "*.safetensors",
            "*.txt",
            "README.md",
            "LICENSE*",
        ],
    )
    if resolved_qwen != qwen_upstream.resolve():
        raise ValueError("Unexpected Qwen snapshot path")
    weight_bytes = sum(path.stat().st_size for path in qwen_upstream.glob("*.safetensors"))
    if weight_bytes != qwen["source_safetensors_bytes"]:
        raise ValueError(f"Qwen source-weight size drift: {weight_bytes}")
    source_config = json.loads((qwen_upstream / "config.json").read_text(encoding="utf-8"))
    if source_config.get("num_hidden_layers") != qwen["num_hidden_layers"]:
        raise ValueError("Qwen layer count drift")
    if not qwen_mlx.exists():
        if qwen_temp.exists():
            raise FileExistsError(f"Partial Qwen conversion requires review: {qwen_temp}")
        command = [
            str(MLX_CONVERT),
            "--hf-path",
            str(qwen_upstream),
            "--mlx-path",
            str(qwen_temp),
            "--dtype",
            "bfloat16",
        ]
        subprocess.run(command, check=True)
        if not any(qwen_temp.glob("*.safetensors")):
            raise FileNotFoundError("MLX conversion produced no model weights")
        qwen_temp.rename(qwen_mlx)
    if not any(qwen_mlx.glob("*.safetensors")):
        raise FileNotFoundError("Qwen MLX model is incomplete")
    qwen_upstream_inventory = inventory(qwen_upstream)
    qwen_mlx_inventory = inventory(qwen_mlx)
    qwen_combined = qwen_upstream_inventory["total_bytes"] + qwen_mlx_inventory["total_bytes"]
    if qwen_combined > config["resource_budget"]["qwen_source_plus_conversion_bytes_max"]:
        raise RuntimeError("Qwen source plus conversion exceeded frozen disk budget")

    encoder_snapshot.mkdir(parents=True, exist_ok=True)
    resolved_encoder = retry_snapshot_download(
        repo_id=encoder["repo_id"],
        revision=encoder["revision"],
        local_dir=encoder_snapshot,
        allow_patterns=[
            "config.json",
            "pytorch_model.bin",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "README.md",
            "LICENSE*",
        ],
    )
    if resolved_encoder != encoder_snapshot.resolve():
        raise ValueError("Unexpected encoder snapshot path")
    encoder_weight = encoder_snapshot / "pytorch_model.bin"
    if encoder_weight.stat().st_size != encoder["source_weight_bytes"]:
        raise ValueError("Encoder source-weight size drift")

    qwen_manifest = {
        "conversion": {
            "dtype": qwen["precision"],
            "mlx_lm": importlib.metadata.version("mlx-lm"),
            "quantized": qwen["quantized"],
        },
        "downloaded_at_utc": utc_now(),
        "mlx_bf16": qwen_mlx_inventory,
        **remote_qwen,
        "upstream": qwen_upstream_inventory,
    }
    encoder_manifest = {
        "downloaded_at_utc": utc_now(),
        "snapshot": inventory(encoder_snapshot),
        **remote_encoder,
    }
    qwen_manifest_path = qwen_root / "manifest.json"
    encoder_manifest_path = encoder_root / "manifest.json"
    write_json(qwen_manifest_path, qwen_manifest)
    write_json(encoder_manifest_path, encoder_manifest)
    report = {
        "accessed_splits": [],
        "completed_at_utc": utc_now(),
        "encoder": {
            "manifest": artifact(encoder_manifest_path),
            "snapshot_bytes": encoder_manifest["snapshot"]["total_bytes"],
        },
        "environment": package_versions(("huggingface-hub", "mlx", "mlx-lm", "transformers")),
        "experiment_id": EXPERIMENT_ID,
        "qwen": {
            "combined_bytes": qwen_combined,
            "manifest": artifact(qwen_manifest_path),
            "mlx_bytes": qwen_manifest["mlx_bf16"]["total_bytes"],
            "upstream_bytes": qwen_manifest["upstream"]["total_bytes"],
        },
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    write_json(output, report)
    record_stage(config, "models", output, "Passed", started_at, started)
    print(json.dumps({"stage": "models", "status": "Passed", "qwen_combined_bytes": qwen_combined}))


def tail_truncate(
    tokenizer: Any,
    previous: str,
    fits: Callable[[str], bool],
) -> tuple[str, bool]:
    if fits(previous):
        return previous, False
    token_ids = tokenizer.encode(previous, add_special_tokens=False)
    low, high = 0, len(token_ids)
    best = ""
    while low <= high:
        midpoint = (low + high) // 2
        candidate = tokenizer.decode(
            token_ids[-midpoint:] if midpoint else [],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        if fits(candidate):
            best = candidate
            low = midpoint + 1
        else:
            high = midpoint - 1
    if not fits(best):
        raise ValueError("Target alone does not fit the sequence budget")
    return best, True


def run_tokenize(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    require_stages(run, "static", "models")
    output = run_dir(config) / "tokenization.json"
    if output.exists():
        raise FileExistsError(output)
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    from transformers import AutoTokenizer

    rows = load_train(config)
    selected = load_selection(config)
    prompt = load_prompt(config)
    encoder_tokenizer = AutoTokenizer.from_pretrained(
        resolve_project_path(config["encoder"]["local_path"]), local_files_only=True
    )
    qwen_tokenizer = AutoTokenizer.from_pretrained(
        resolve_project_path(config["qwen"]["local_path"]), local_files_only=True
    )
    encoder_limit = config["encoder"]["max_sequence_length"]
    qwen_limit = config["qwen"]["lora"]["max_sequence_length"]
    measurements: dict[str, list[int]] = defaultdict(list)
    truncations = Counter()
    for row in rows:
        target = row["views"]["target_only"]["target"]
        target_text = classifier_text(prompt, row, "target_only")
        encoder_target_length = len(encoder_tokenizer.encode(target_text, add_special_tokens=True))
        if encoder_target_length > encoder_limit:
            raise ValueError("An encoder target exceeds the frozen limit")
        measurements["encoder_target_only"].append(encoder_target_length)
        previous = row["views"]["previous_context"]["previous"]
        if previous:
            previous, truncated = tail_truncate(
                encoder_tokenizer,
                previous,
                lambda candidate: len(
                    encoder_tokenizer.encode(
                        classifier_text(prompt, row, "previous_context", candidate),
                        add_special_tokens=True,
                    )
                )
                <= encoder_limit,
            )
            truncations["encoder_context_rows"] += int(truncated)
        encoder_context_text = classifier_text(prompt, row, "previous_context", previous)
        measurements["encoder_previous_context"].append(
            len(encoder_tokenizer.encode(encoder_context_text, add_special_tokens=True))
        )

        for thinking in (False, True):
            target_messages = prompt_messages(config, prompt, row, "target_only")
            target_length = len(
                qwen_tokenizer.apply_chat_template(
                    target_messages,
                    add_generation_prompt=True,
                    enable_thinking=thinking,
                    return_dict=False,
                )
            )
            if target_length > qwen_limit:
                raise ValueError("A Qwen target-only prompt exceeds the frozen limit")
            measurements[f"qwen_target_only_thinking_{str(thinking).lower()}"].append(target_length)
        previous = row["views"]["previous_context"]["previous"]
        if previous:
            previous, truncated = tail_truncate(
                qwen_tokenizer,
                previous,
                lambda candidate: max(
                    len(
                        qwen_tokenizer.apply_chat_template(
                            prompt_messages(
                                config,
                                prompt,
                                row,
                                "previous_context",
                                previous_override=candidate,
                            ),
                            add_generation_prompt=True,
                            enable_thinking=thinking,
                            return_dict=False,
                        )
                    )
                    for thinking in (False, True)
                )
                <= qwen_limit,
            )
            truncations["qwen_context_rows"] += int(truncated)
        for thinking in (False, True):
            messages = prompt_messages(
                config, prompt, row, "previous_context", previous_override=previous
            )
            length = len(
                qwen_tokenizer.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    enable_thinking=thinking,
                    return_dict=False,
                )
            )
            measurements[f"qwen_previous_context_thinking_{str(thinking).lower()}"].append(length)
        if target not in prompt_messages(config, prompt, row, "previous_context", previous_override=previous)[1]["content"]:
            raise ValueError("Target-preserving truncation changed the target")

    lora_rows: list[dict[str, Any]] = []
    lora_lengths: list[int] = []
    lora_view_counts = Counter()
    for row in selected:
        view = "previous_context" if row["context_available"] and row["selection_rank"] < 2 else "target_only"
        messages = prompt_messages(config, prompt, row, view, include_target=True)
        length = len(qwen_tokenizer.apply_chat_template(messages, return_dict=False))
        if length > qwen_limit:
            previous = row["views"]["previous_context"]["previous"]
            if not previous:
                raise ValueError("A target-only LoRA example exceeds the frozen limit")
            truncated, _ = tail_truncate(
                qwen_tokenizer,
                previous,
                lambda candidate: len(
                    qwen_tokenizer.apply_chat_template(
                        prompt_messages(
                            config,
                            prompt,
                            row,
                            view,
                            previous_override=candidate,
                            include_target=True,
                        ),
                        return_dict=False,
                    )
                )
                <= qwen_limit,
            )
            messages = prompt_messages(
                config,
                prompt,
                row,
                view,
                previous_override=truncated,
                include_target=True,
            )
            length = len(qwen_tokenizer.apply_chat_template(messages, return_dict=False))
            truncations["lora_rows"] += 1
        lora_rows.append({"messages": messages})
        lora_lengths.append(length)
        lora_view_counts[view] += 1
    lora_dir = private_root(config) / "lora-data"
    if any((lora_dir / name).exists() for name in ("train.jsonl", "valid.jsonl", "test.jsonl")):
        raise FileExistsError("LoRA smoke data directory is not empty")
    write_private_jsonl(lora_dir / "train.jsonl", lora_rows)

    synthetic = dict(selected[0])
    synthetic["views"] = json.loads(json.dumps(selected[0]["views"]))
    synthetic["views"]["previous_context"]["previous"] = "很长的前文。" * 5000
    synthetic_target = synthetic["views"]["target_only"]["target"]
    synthetic_previous, synthetic_truncated = tail_truncate(
        qwen_tokenizer,
        synthetic["views"]["previous_context"]["previous"],
        lambda candidate: len(
            qwen_tokenizer.apply_chat_template(
                prompt_messages(
                    config,
                    prompt,
                    synthetic,
                    "previous_context",
                    previous_override=candidate,
                ),
                add_generation_prompt=True,
                enable_thinking=True,
                return_dict=False,
            )
        )
        <= qwen_limit,
    )
    synthetic_user = prompt_messages(
        config,
        prompt,
        synthetic,
        "previous_context",
        previous_override=synthetic_previous,
    )[1]["content"]
    if not synthetic_truncated or synthetic_target not in synthetic_user:
        raise ValueError("Synthetic target-preserving truncation test failed")
    report = {
        "accessed_splits": ["train"],
        "completed_at_utc": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "lengths": {key: numeric_summary(values) for key, values in sorted(measurements.items())},
        "limits": {"encoder": encoder_limit, "qwen": qwen_limit},
        "lora_smoke_data": {
            "lengths": numeric_summary(lora_lengths),
            "private_artifact_sha256": sha256_file(lora_dir / "train.jsonl"),
            "row_level_data_public": False,
            "rows": len(lora_rows),
            "views": dict(sorted(lora_view_counts.items())),
        },
        "raw_ids_stored_publicly": False,
        "raw_text_stored_publicly": False,
        "status": "Passed",
        "synthetic_target_preservation": "Passed",
        "test_split_accessed": False,
        "train_rows_scanned": len(rows),
        "truncations": dict(sorted(truncations.items())),
        "validation_split_accessed": False,
    }
    write_json(output, report)
    record_stage(config, "tokenize", output, "Passed", started_at, started)
    print(json.dumps({"stage": "tokenize", "status": "Passed", "truncations": report["truncations"]}))


def split_smoke_selection(selected: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train = [row for row in selected if row["selection_rank"] < 3]
    holdout = [row for row in selected if row["selection_rank"] == 3]
    if len(train) != 42 or len(holdout) != 14:
        raise ValueError("Smoke train/holdout split drift")
    return train, holdout


def run_classical(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    require_stages(run, "static")
    output = run_dir(config) / "classical.json"
    if output.exists():
        raise FileExistsError(output)
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    from sklearn.svm import LinearSVC

    selected = load_selection(config)
    smoke_train, holdout = split_smoke_selection(selected)
    prompt = load_prompt(config)
    results: dict[str, Any] = {}
    for view in ("target_only", "previous_context"):
        train_text = [classifier_text(prompt, row, view) for row in smoke_train]
        holdout_text = [classifier_text(prompt, row, view) for row in holdout]
        vectorizer = FeatureUnion(
            [
                (
                    "word",
                    TfidfVectorizer(
                        ngram_range=tuple(config["m1"]["word_ngram_range"]),
                        min_df=config["m1"]["min_df"],
                        sublinear_tf=config["m1"]["sublinear_tf"],
                    ),
                ),
                (
                    "char",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        ngram_range=tuple(config["m1"]["char_ngram_range"]),
                        min_df=config["m1"]["min_df"],
                        sublinear_tf=config["m1"]["sublinear_tf"],
                    ),
                ),
            ]
        )
        fit_started = time.perf_counter()
        train_matrix = vectorizer.fit_transform(train_text)
        holdout_matrix = vectorizer.transform(holdout_text)
        classifier = LinearSVC(
            C=config["m1"]["c"],
            class_weight=config["m1"]["class_weight"],
            random_state=config["m1"]["random_state"],
        )
        classifier.fit(train_matrix, [row["label"] for row in smoke_train])
        scores = classifier.decision_function(holdout_matrix)
        if scores.shape != (14, 7) or not np.isfinite(scores).all():
            raise ValueError(f"Classical decision tensor failed for {view}")
        if tuple(classifier.classes_) != tuple(sorted(config["data"]["labels"])):
            raise ValueError("Classical classifier class order drift")
        results[view] = {
            "decision_shape": list(scores.shape),
            "features": int(train_matrix.shape[1]),
            "fit_seconds": time.perf_counter() - fit_started,
            "finite_decisions": True,
            "holdout_rows": len(holdout),
            "train_rows": len(smoke_train),
        }
    report = {
        "accessed_splits": ["train"],
        "completed_at_utc": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "performance_metrics_computed": False,
        "predictions_stored_publicly": False,
        "results": results,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    write_json(output, report)
    record_stage(config, "classical", output, "Passed", started_at, started)
    print(json.dumps({"stage": "classical", "status": "Passed", "views": list(results)}))


def truncate_classifier_input(
    tokenizer: Any,
    prompt: dict[str, Any],
    row: dict[str, Any],
    view: str,
    limit: int,
) -> str:
    text = classifier_text(prompt, row, view)
    if len(tokenizer.encode(text, add_special_tokens=True)) <= limit:
        return text
    previous = row["views"]["previous_context"]["previous"]
    if not previous:
        raise ValueError("Target-only encoder input exceeds frozen limit")
    previous, _ = tail_truncate(
        tokenizer,
        previous,
        lambda candidate: len(
            tokenizer.encode(
                classifier_text(prompt, row, "previous_context", candidate),
                add_special_tokens=True,
            )
        )
        <= limit,
    )
    return classifier_text(prompt, row, "previous_context", previous)


def run_encoder(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    require_stages(run, "static", "models", "tokenize")
    output = run_dir(config) / "encoder.json"
    if output.exists():
        raise FileExistsError(output)
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True, warn_only=True)
    selected = [row for row in load_selection(config) if row["selection_rank"] == 0]
    if len(selected) != 14:
        raise ValueError("Encoder smoke batch must contain one row per stratum")
    prompt = load_prompt(config)
    model_path = resolve_project_path(config["encoder"]["local_path"])
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path,
        local_files_only=True,
        num_labels=len(config["data"]["labels"]),
        ignore_mismatched_sizes=True,
    )
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["encoder"]["learning_rate"])
    label_to_id = {label: index for index, label in enumerate(config["data"]["labels"])}
    classifier_before = {
        name: parameter.detach().clone()
        for name, parameter in model.named_parameters()
        if parameter.requires_grad and "classifier" in name
    }
    if not classifier_before:
        raise ValueError("Encoder classifier parameters were not found")
    losses: list[float] = []
    shapes: list[list[int]] = []
    for view in ("target_only", "previous_context"):
        texts = [
            truncate_classifier_input(
                tokenizer,
                prompt,
                row,
                view,
                config["encoder"]["max_sequence_length"],
            )
            for row in selected
        ]
        batch = tokenizer(
            texts,
            padding=True,
            truncation=False,
            return_tensors="pt",
        )
        labels = torch.tensor([label_to_id[row["label"]] for row in selected], dtype=torch.long)
        optimizer.zero_grad(set_to_none=True)
        result = model(**batch, labels=labels)
        loss = result.loss
        if not torch.isfinite(loss):
            raise ValueError("Encoder smoke loss is not finite")
        if tuple(result.logits.shape) != (14, 7):
            raise ValueError("Encoder smoke logits have the wrong shape")
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
        shapes.append(list(result.logits.shape))
    changed = any(
        not torch.equal(classifier_before[name], parameter.detach())
        for name, parameter in model.named_parameters()
        if name in classifier_before
    )
    if not changed:
        raise ValueError("Encoder classifier parameters did not change")
    report = {
        "accessed_splits": ["train"],
        "batch_size": len(selected),
        "completed_at_utc": utc_now(),
        "environment": package_versions(("torch", "transformers")),
        "experiment_id": EXPERIMENT_ID,
        "finite_losses": losses,
        "logit_shapes": shapes,
        "optimizer_steps": len(losses),
        "performance_metrics_computed": False,
        "predictions_stored_publicly": False,
        "status": "Passed",
        "test_split_accessed": False,
        "trainable_parameters_changed": True,
        "validation_split_accessed": False,
    }
    write_json(output, report)
    record_stage(config, "encoder", output, "Passed", started_at, started)
    print(json.dumps({"stage": "encoder", "status": "Passed", "losses": losses}))


def qwen_cases(config: dict[str, Any], selected: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str, bool, str]]:
    cases: list[tuple[dict[str, Any], str, bool, str]] = []
    for label in config["data"]["labels"]:
        available = next(
            row
            for row in selected
            if row["label"] == label and row["context_available"] and row["selection_rank"] == 0
        )
        missing = next(
            row
            for row in selected
            if row["label"] == label and not row["context_available"] and row["selection_rank"] == 0
        )
        for view in ("target_only", "previous_context"):
            for thinking in (False, True):
                cases.append((available, view, thinking, f"available__{view}__thinking_{str(thinking).lower()}"))
        for thinking in (False, True):
            cases.append((missing, "target_only", thinking, f"missing__target_only__thinking_{str(thinking).lower()}"))
    if len(cases) != 42:
        raise ValueError("Qwen smoke generation count drift")
    return cases


def run_qwen(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    require_stages(run, "static", "models", "tokenize")
    output = run_dir(config) / "qwen.json"
    if output.exists():
        raise FileExistsError(output)
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    from label_parser import parse_final_label

    model_path = resolve_project_path(config["qwen"]["local_path"])
    model, tokenizer = load(str(model_path))
    inference = config["qwen"]["inference"]
    sampler = make_sampler(
        temp=inference["temperature"],
        top_p=inference["top_p"],
        top_k=inference["top_k"],
        min_p=inference["min_p"],
    )
    selected = load_selection(config)
    prompt_spec = load_prompt(config)
    cases = qwen_cases(config, selected)
    private_output = private_root(config) / "qwen-outputs.jsonl"
    if private_output.exists():
        raise FileExistsError(private_output)
    temporary = private_output.with_name(private_output.name + ".tmp")
    condition_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with temporary.open("w", encoding="utf-8") as target:
        os.chmod(temporary, 0o600)
        for index, (row, view, thinking, condition) in enumerate(cases):
            messages = prompt_messages(config, prompt_spec, row, view)
            prompt = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                enable_thinking=thinking,
                tokenize=False,
            )
            seed = int(sha256_text(f"{EXPERIMENT_ID}:{condition}:{row['sample_id']}")[:8], 16)
            mx.random.seed(seed)
            generated_parts: list[str] = []
            final_response = None
            generation_started = time.perf_counter()
            for response in stream_generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=inference["max_new_tokens"],
                sampler=sampler,
            ):
                generated_parts.append(response.text)
                final_response = response
            elapsed = time.perf_counter() - generation_started
            if final_response is None:
                raise RuntimeError("Qwen generation yielded no response metadata")
            raw_output = "".join(generated_parts)
            parsed = parse_final_label(raw_output, thinking=thinking, labels=config["data"]["labels"])
            private_record = {
                "condition": condition,
                "finish_reason": final_response.finish_reason,
                "generated_tokens": final_response.generation_tokens,
                "generation_seconds": elapsed,
                "generation_tps": final_response.generation_tps,
                "gold_label": row["label"],
                "parse": parsed.to_dict(),
                "peak_memory_gb": final_response.peak_memory,
                "prompt_tokens": final_response.prompt_tokens,
                "prompt_tps": final_response.prompt_tps,
                "raw_output": raw_output,
                "sample_id": row["sample_id"],
                "seed": seed,
                "thinking": thinking,
                "view": view,
            }
            target.write(json.dumps(private_record, ensure_ascii=False, sort_keys=True) + "\n")
            condition_rows[condition].append(private_record)
            print(json.dumps({"stage": "qwen", "completed": index + 1, "total": len(cases), "condition": condition}))
    temporary.replace(private_output)
    os.chmod(private_output, 0o600)
    summaries: dict[str, Any] = {}
    all_rows = [row for values in condition_rows.values() for row in values]
    for condition, values in sorted(condition_rows.items()):
        valid = sum(row["parse"]["valid"] for row in values)
        summaries[condition] = {
            "finish_reasons": dict(sorted(Counter(row["finish_reason"] for row in values).items())),
            "generated_tokens": numeric_summary([row["generated_tokens"] for row in values]),
            "generation_seconds": numeric_summary([row["generation_seconds"] for row in values]),
            "parser_errors": dict(
                sorted(Counter(row["parse"]["error"] for row in values if row["parse"]["error"]).items())
            ),
            "parser_valid_count": valid,
            "parser_valid_rate": valid / len(values),
            "peak_memory_gb_max": max(row["peak_memory_gb"] for row in values),
            "prompt_tokens": numeric_summary([row["prompt_tokens"] for row in values]),
            "rows": len(values),
        }
    overall_valid = sum(row["parse"]["valid"] for row in all_rows)
    overall_rate = overall_valid / len(all_rows)
    passed = overall_rate >= inference["minimum_overall_parser_valid_rate"] and all(
        summary["parser_valid_count"] > 0 for summary in summaries.values()
    )
    report = {
        "accessed_splits": ["train"],
        "completed_at_utc": utc_now(),
        "conditions": summaries,
        "experiment_id": EXPERIMENT_ID,
        "generation_rows": len(all_rows),
        "gold_labels_used_for_performance": False,
        "overall_parser_valid_count": overall_valid,
        "overall_parser_valid_rate": overall_rate,
        "performance_metrics_computed": False,
        "predictions_stored_publicly": False,
        "private_output_sha256": sha256_file(private_output),
        "raw_output_stored_publicly": False,
        "sampler": {
            "max_new_tokens": inference["max_new_tokens"],
            "min_p": inference["min_p"],
            "temperature": inference["temperature"],
            "top_k": inference["top_k"],
            "top_p": inference["top_p"],
        },
        "status": "Passed" if passed else "Failed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    write_json(output, report)
    record_stage(config, "qwen", output, report["status"], started_at, started)
    if not passed:
        raise RuntimeError(f"Qwen parser gate failed: {overall_valid}/{len(all_rows)}")
    print(json.dumps({"stage": "qwen", "status": "Passed", "parser_valid_rate": overall_rate}))


def lora_runtime_config(config: dict[str, Any]) -> dict[str, Any]:
    lora = config["qwen"]["lora"]
    return {
        "adapter_path": str(private_root(config) / "lora-adapter"),
        "batch_size": lora["batch_size"],
        "clear_cache_threshold": 0,
        "data": str(private_root(config) / "lora-data"),
        "fine_tune_type": "lora",
        "grad_accumulation_steps": 1,
        "grad_checkpoint": lora["grad_checkpoint"],
        "iters": lora["iterations"],
        "learning_rate": lora["learning_rate"],
        "lora_parameters": {
            "dropout": lora["dropout"],
            "keys": lora["target_modules"],
            "rank": lora["rank"],
            "scale": lora["scale"],
        },
        "lr_schedule": None,
        "mask_prompt": lora["mask_prompt"],
        "max_seq_length": lora["max_sequence_length"],
        "model": str(resolve_project_path(config["qwen"]["local_path"])),
        "num_layers": lora["num_layers"],
        "optimizer": lora["optimizer"],
        "optimizer_config": {lora["optimizer"]: {}},
        "project_name": None,
        "report_to": None,
        "resume_adapter_file": None,
        "save_every": lora["iterations"] + 1,
        "seed": 42,
        "steps_per_eval": lora["iterations"] + 1,
        "steps_per_report": 1,
        "test": False,
        "test_batches": 0,
        "train": True,
        "val_batches": 0,
    }


def adapter_summary(path: Path) -> dict[str, Any]:
    import numpy as np
    from safetensors import safe_open

    tensor_count = 0
    parameter_count = 0
    b_count = 0
    b_nonzero = 0
    with safe_open(path, framework="numpy") as source:
        for name in source.keys():
            tensor = source.get_tensor(name)
            tensor_count += 1
            parameter_count += int(tensor.size)
            if name.endswith("lora_b"):
                b_count += 1
                b_nonzero += int(bool(np.any(tensor != 0)))
    return {
        "lora_b_nonzero_tensors": b_nonzero,
        "lora_b_tensor_count": b_count,
        "tensor_count": tensor_count,
        "trainable_parameter_count": parameter_count,
    }


def parse_lora_history(log_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = TRAIN_LOG_PATTERN.search(line)
        if not match:
            continue
        row = {
            "iteration": int(match.group("iteration")),
            "iterations_per_second": float(match.group("iterations_per_second")),
            "learning_rate": float(match.group("learning_rate")),
            "peak_memory_gb": float(match.group("peak_memory_gb")),
            "tokens_per_second": float(match.group("tokens_per_second")),
            "train_loss": float(match.group("loss")),
            "trained_tokens": int(match.group("trained_tokens")),
        }
        if not all(math.isfinite(value) for key, value in row.items() if isinstance(value, float)):
            raise ValueError("LoRA log contains a non-finite value")
        rows.append(row)
    return rows


def memory_blocked(return_code: int, text: str) -> bool:
    lowered = text.lower()
    signals = ("out of memory", "cannot allocate memory", "memory allocation", "resource exhausted")
    return return_code in (-9, 137) or any(signal in lowered for signal in signals)


def run_lora(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    require_stages(run, "static", "models", "tokenize", "qwen")
    output = run_dir(config) / "lora.json"
    if output.exists():
        raise FileExistsError(output)
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers

    model_path = resolve_project_path(config["qwen"]["local_path"])
    lora = config["qwen"]["lora"]
    model, _ = load(str(model_path))
    if len(model.layers) != config["qwen"]["num_hidden_layers"]:
        raise ValueError("Loaded Qwen layer count drift")
    model.freeze()
    linear_to_lora_layers(
        model,
        lora["num_layers"],
        {
            "dropout": lora["dropout"],
            "keys": lora["target_modules"],
            "rank": lora["rank"],
            "scale": lora["scale"],
        },
    )
    observed: list[tuple[int, str]] = []
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError(f"Unexpected LoRA module path: {name}")
        observed.append((int(match.group(1)), match.group(2)))
    expected = [
        (block, target)
        for block in lora["adapted_block_indices"]
        for target in lora["target_modules"]
    ]
    if sorted(observed) != sorted(expected):
        raise ValueError("LoRA insertion set differs from the frozen 112-module contract")
    del model
    gc.collect()
    mx.clear_cache()

    runtime = lora_runtime_config(config)
    runtime_path = private_root(config) / "lora-runtime.json"
    adapter_dir = Path(runtime["adapter_path"])
    log_path = private_root(config) / "lora-stdout.log"
    if any(path.exists() for path in (runtime_path, adapter_dir, log_path)):
        raise FileExistsError("LoRA smoke outputs already exist")
    write_private_json(runtime_path, runtime)
    command = [str(MLX_LORA), "-c", str(runtime_path)]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=config["resource_budget"]["local_wall_time_minutes_max"] * 60,
    )
    combined_log = (completed.stdout or "") + (completed.stderr or "")
    log_path.write_text(combined_log, encoding="utf-8")
    os.chmod(log_path, 0o600)
    secure_private_tree(private_root(config))
    if completed.returncode != 0:
        status = "blocked_gpu_required" if memory_blocked(completed.returncode, combined_log) else "Failed"
        report = {
            "accessed_splits": ["train"],
            "completed_at_utc": utc_now(),
            "error_type": "local_memory_gate" if status == "blocked_gpu_required" else "runtime_failure",
            "exact_insertion_count": len(observed),
            "experiment_id": EXPERIMENT_ID,
            "return_code": completed.returncode,
            "status": status,
            "test_split_accessed": False,
            "validation_split_accessed": False,
        }
        write_json(output, report)
        record_stage(config, "lora", output, status, started_at, started)
        if status == "Failed":
            raise RuntimeError("Exact 4B LoRA smoke failed for a non-memory reason")
        print(json.dumps({"stage": "lora", "status": status}))
        return
    adapter_file = adapter_dir / "adapters.safetensors"
    adapter_config = adapter_dir / "adapter_config.json"
    if not adapter_file.is_file() or not adapter_config.is_file():
        raise FileNotFoundError("MLX-LM did not save the final adapter")
    history = parse_lora_history(log_path)
    if len(history) != lora["iterations"] or history[-1]["iteration"] != lora["iterations"]:
        raise ValueError("LoRA smoke history does not contain both frozen iterations")
    adapter = adapter_summary(adapter_file)
    expected_b = len(lora["adapted_block_indices"]) * len(lora["target_modules"])
    if adapter["lora_b_tensor_count"] != expected_b or adapter["lora_b_nonzero_tensors"] != expected_b:
        raise ValueError("One or more LoRA B tensors remained zero or were missing")
    reloaded, tokenizer = load(str(model_path), adapter_path=str(adapter_dir))
    token_ids = tokenizer.encode("测试", add_special_tokens=False)[:1]
    logits = reloaded(mx.array([token_ids]))
    mx.eval(logits)
    reload_finite = bool(mx.all(mx.isfinite(logits)).item())
    if not reload_finite:
        raise ValueError("Reloaded adapter produced non-finite logits")
    report = {
        "accessed_splits": ["train"],
        "adapter": {**adapter, "weights_sha256": sha256_file(adapter_file)},
        "adapted_block_indices": lora["adapted_block_indices"],
        "completed_at_utc": utc_now(),
        "environment": package_versions(("mlx", "mlx-lm", "numpy", "safetensors")),
        "exact_insertion_count": len(observed),
        "experiment_id": EXPERIMENT_ID,
        "history": history,
        "peak_memory_gb": max(row["peak_memory_gb"] for row in history),
        "reload_finite_logits": True,
        "status": "Passed",
        "target_modules": lora["target_modules"],
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    write_json(output, report)
    record_stage(config, "lora", output, "Passed", started_at, started)
    print(json.dumps({"stage": "lora", "status": "Passed", "peak_memory_gb": report["peak_memory_gb"]}))


def main() -> None:
    args = parse_args()
    config = load_config()
    commands = {
        "static": run_static,
        "models": run_models,
        "tokenize": run_tokenize,
        "classical": run_classical,
        "encoder": run_encoder,
        "qwen": run_qwen,
        "lora": run_lora,
    }
    commands[args.command](config)


if __name__ == "__main__":
    main()

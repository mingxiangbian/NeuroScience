#!/usr/bin/env python3
"""Run the registered independent-verification amendment for EXP-041."""

from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
from typing import Any, Iterable


EXPERIMENT_ID = "EXP-041"
AUDIT_ID = "AUDIT-EXP-041-V1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIG_PATH = SCRIPT_DIR / "config.json"
PUBLIC_STAGE_FILES = {
    "static": "static.json",
    "models": "models.json",
    "tokenize": "tokenization.json",
    "classical": "classical.json",
    "encoder": "encoder.json",
    "qwen": "qwen.json",
    "lora": "lora.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-gpu-blocked",
        action="store_true",
        help="Verify a resource-blocked LoRA result without marking Stage 2 passed.",
    )
    return parser.parse_args()


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
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def artifact(path: Path) -> dict[str, Any]:
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def assert_close(observed: float, expected: float, name: str, tolerance: float = 1e-9) -> None:
    if not math.isclose(float(observed), float(expected), rel_tol=tolerance, abs_tol=tolerance):
        raise ValueError(f"Numeric mismatch for {name}: {observed} != {expected}")


def quantile(values: list[float | int], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
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


def compare_numeric_summary(observed: dict[str, Any], expected: dict[str, Any], name: str) -> None:
    for key in ("count", "max", "min"):
        if observed[key] != expected[key]:
            raise ValueError(f"{name} {key} mismatch")
    for key in ("mean", "p50", "p95", "p99"):
        assert_close(observed[key], expected[key], f"{name}.{key}")


def load_and_verify_config() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("tier") != "Minor":
        raise ValueError("Unexpected EXP-041 identity")
    implementation = config["implementation"]
    bindings = (
        (implementation["parser_path"], implementation["parser_sha256"]),
        (implementation["prompt_path"], implementation["prompt_sha256"]),
        (implementation["runner_path"], implementation["runner_sha256"]),
        (implementation["verifier_path"], implementation["verifier_sha256"]),
    )
    for relative, expected in bindings:
        path = resolve_project_path(relative)
        if sha256_file(path) != expected:
            raise ValueError(f"Implementation hash mismatch: {relative}")
    runner_source = resolve_project_path(implementation["runner_path"]).read_text(encoding="utf-8")
    verifier_source = Path(__file__).read_text(encoding="utf-8")
    forbidden_modules = {"run_preflight", "label_parser"}
    for node in ast.walk(ast.parse(verifier_source)):
        if isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
            raise ValueError("Verifier imports implementation under test")
        if isinstance(node, ast.Import) and any(
            imported.name in forbidden_modules for imported in node.names
        ):
            raise ValueError("Verifier imports implementation under test")
    if "validation.jsonl" in runner_source or "test.labels.sealed.jsonl" in runner_source:
        raise ValueError("Runner contains a forbidden split path")
    return config


def reconstruct_selection(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train_path = resolve_project_path(config["data"]["train_path"])
    if sha256_file(train_path) != config["data"]["train_sha256"]:
        raise ValueError("Train hash drift")
    rows = load_jsonl(train_path)
    if len(rows) != config["data"]["train_rows"]:
        raise ValueError("Train count drift")
    strata: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["label"] not in config["data"]["labels"]:
            raise ValueError("Train contains an unknown label")
        if row["views"]["target_only"]["target"] != row["views"]["previous_context"]["target"]:
            raise ValueError("Paired target drift")
        if bool(row["views"]["previous_context"]["previous"]) != bool(row["context_available"]):
            raise ValueError("Context flag drift")
        copy = dict(row)
        copy["selector_sha256"] = sha256_text(
            f"{config['data']['selection_seed']}:{row['sample_id']}"
        )
        strata[(row["label"], bool(row["context_available"]))].append(copy)
    selected: list[dict[str, Any]] = []
    limit = config["data"]["selection_per_label_context_stratum"]
    for label in config["data"]["labels"]:
        for context in (False, True):
            ranked = sorted(
                strata[(label, context)], key=lambda row: (row["selector_sha256"], row["sample_id"])
            )
            for rank, row in enumerate(ranked[:limit]):
                row["selection_rank"] = rank
                selected.append(row)
    return rows, selected


def independent_parse(output: str, thinking: bool, labels: tuple[str, ...]) -> dict[str, Any]:
    opening = "<think>" in output
    closes = output.count("</think>")

    def invalid(error: str, boundary: bool = False) -> dict[str, Any]:
        return {
            "canonical_output": None,
            "error": error,
            "label": None,
            "opening_marker_found": opening,
            "thinking_boundary_found": boundary,
            "valid": False,
        }

    if not isinstance(output, str) or not output.strip():
        return invalid("empty_output")
    if thinking:
        if closes != 1:
            return invalid("missing_thinking_boundary" if closes == 0 else "multiple_thinking_boundaries")
        prefix, candidate = output.split("</think>", 1)
        if prefix.count("<think>") > 1:
            return invalid("multiple_opening_markers", True)
        if opening and not prefix.lstrip().startswith("<think>"):
            return invalid("misplaced_opening_marker", True)
    else:
        if opening or closes:
            return invalid("thinking_marker_in_nonthinking_output", bool(closes))
        candidate = output
    try:
        decoded = json.loads(candidate.strip())
    except json.JSONDecodeError:
        return invalid("invalid_json", thinking)
    if not isinstance(decoded, dict):
        return invalid("json_not_object", thinking)
    if set(decoded) != {"label"}:
        return invalid("schema_keys_mismatch", thinking)
    label = decoded["label"]
    if not isinstance(label, str):
        return invalid("label_not_string", thinking)
    if label not in labels:
        return invalid("unknown_label", thinking)
    return {
        "canonical_output": json.dumps({"label": label}, separators=(",", ":")),
        "error": None,
        "label": label,
        "opening_marker_found": opening,
        "thinking_boundary_found": thinking,
        "valid": True,
    }


def verify_run_and_stage_artifacts(config: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, dict[str, Any]]]:
    root = resolve_project_path(config["run_dir"])
    run_path = root / "run.json"
    run = load_json(run_path)
    if (
        run.get("experiment_id") != EXPERIMENT_ID
        or run.get("accessed_splits") != ["train"]
        or run.get("validation_split_accessed")
        or run.get("test_split_accessed")
    ):
        raise ValueError("Run split boundary or identity drift")
    if set(run.get("stages", {})) != set(PUBLIC_STAGE_FILES):
        raise ValueError("Run does not contain all seven Stage 2 steps")
    reports: dict[str, dict[str, Any]] = {}
    for stage, filename in PUBLIC_STAGE_FILES.items():
        path = root / filename
        report = load_json(path)
        if report.get("experiment_id") != EXPERIMENT_ID:
            raise ValueError(f"{stage} report identity drift")
        if report.get("validation_split_accessed") or report.get("test_split_accessed"):
            raise ValueError(f"{stage} reports forbidden split access")
        if run["stages"][stage]["artifact"] != artifact(path):
            raise ValueError(f"{stage} artifact binding drift")
        reports[stage] = report
    return root, run, reports


def verify_static(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    reconstructed: list[dict[str, Any]],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    selection_path = resolve_project_path(config["private_root"]) / "selection.jsonl"
    stored = load_jsonl(selection_path)
    if stored != reconstructed:
        raise ValueError("Private deterministic selection mismatch")
    if report["selection_rows"] != len(stored) or report["train_rows_scanned"] != len(rows):
        raise ValueError("Static row counts mismatch")
    expected_digest = sha256_text("\n".join(row["sample_id"] for row in stored))
    if report["selection_digest_sha256"] != expected_digest:
        raise ValueError("Selection digest mismatch")
    expected_counts = Counter((row["label"], bool(row["context_available"])) for row in stored)
    if set(expected_counts.values()) != {config["data"]["selection_per_label_context_stratum"]}:
        raise ValueError("Selection stratum coverage mismatch")
    if report["status"] != "Passed" or report["raw_text_stored_publicly"]:
        raise ValueError("Static public boundary failed")
    return stored


def verify_models(config: dict[str, Any], report: dict[str, Any]) -> None:
    qwen_root = resolve_project_path(config["qwen"]["local_path"]).parent
    encoder_root = resolve_project_path(config["encoder"]["local_path"]).parent
    qwen_manifest_path = qwen_root / "manifest.json"
    encoder_manifest_path = encoder_root / "manifest.json"
    if report["qwen"]["manifest"] != artifact(qwen_manifest_path):
        raise ValueError("Qwen manifest binding mismatch")
    if report["encoder"]["manifest"] != artifact(encoder_manifest_path):
        raise ValueError("Encoder manifest binding mismatch")
    qwen = load_json(qwen_manifest_path)
    encoder = load_json(encoder_manifest_path)
    if qwen["repo_id"] != config["qwen"]["repo_id"] or qwen["revision"] != config["qwen"]["revision"]:
        raise ValueError("Qwen identity drift")
    if encoder["repo_id"] != config["encoder"]["repo_id"] or encoder["revision"] != config["encoder"]["revision"]:
        raise ValueError("Encoder identity drift")
    if qwen["upstream"] != inventory(qwen_root / "upstream"):
        raise ValueError("Qwen upstream inventory mismatch")
    if qwen["mlx_bf16"] != inventory(resolve_project_path(config["qwen"]["local_path"])):
        raise ValueError("Qwen MLX inventory mismatch")
    if encoder["snapshot"] != inventory(resolve_project_path(config["encoder"]["local_path"])):
        raise ValueError("Encoder inventory mismatch")
    qwen_weight_bytes = sum(
        path.stat().st_size for path in (qwen_root / "upstream").glob("*.safetensors")
    )
    if qwen_weight_bytes != config["qwen"]["source_safetensors_bytes"]:
        raise ValueError("Qwen source size mismatch")
    if (
        resolve_project_path(config["encoder"]["local_path"]) / "pytorch_model.bin"
    ).stat().st_size != config["encoder"]["source_weight_bytes"]:
        raise ValueError("Encoder source size mismatch")


def verify_tokenization(config: dict[str, Any], report: dict[str, Any]) -> None:
    if report["status"] != "Passed" or report["train_rows_scanned"] != config["data"]["train_rows"]:
        raise ValueError("Tokenization status or train count mismatch")
    for name, summary in report["lengths"].items():
        if summary["count"] != config["data"]["train_rows"]:
            raise ValueError(f"Tokenization count mismatch for {name}")
        limit = report["limits"]["encoder" if name.startswith("encoder") else "qwen"]
        if summary["max"] > limit:
            raise ValueError(f"Tokenization limit exceeded for {name}")
    lora_path = resolve_project_path(config["private_root"]) / "lora-data" / "train.jsonl"
    lora_rows = load_jsonl(lora_path)
    if len(lora_rows) != config["data"]["selection_rows"]:
        raise ValueError("LoRA smoke-data row count mismatch")
    if report["lora_smoke_data"]["private_artifact_sha256"] != sha256_file(lora_path):
        raise ValueError("LoRA smoke-data hash mismatch")
    for row in lora_rows:
        if set(row) != {"messages"} or row["messages"][-1]["role"] != "assistant":
            raise ValueError("LoRA chat schema mismatch")
        target = json.loads(row["messages"][-1]["content"])
        if set(target) != {"label"} or target["label"] not in config["data"]["labels"]:
            raise ValueError("LoRA assistant target mismatch")
    for forbidden in ("valid.jsonl", "validation.jsonl", "dev.jsonl", "test.jsonl"):
        if (lora_path.parent / forbidden).exists():
            raise ValueError("LoRA smoke directory contains a non-train split")
    if report["synthetic_target_preservation"] != "Passed":
        raise ValueError("Synthetic truncation gate failed")


def verify_classical(config: dict[str, Any], report: dict[str, Any]) -> None:
    if report["status"] != "Passed" or report["performance_metrics_computed"]:
        raise ValueError("Classical preflight boundary failed")
    if set(report["results"]) != {"target_only", "previous_context"}:
        raise ValueError("Classical input views mismatch")
    for result in report["results"].values():
        if result["decision_shape"] != [14, 7] or result["features"] <= 0:
            raise ValueError("Classical finite-shape gate failed")
        if not result["finite_decisions"] or result["train_rows"] != 42 or result["holdout_rows"] != 14:
            raise ValueError("Classical smoke split or finite gate failed")


def verify_encoder(report: dict[str, Any]) -> None:
    if report["status"] != "Passed" or report["performance_metrics_computed"]:
        raise ValueError("Encoder preflight boundary failed")
    if report["optimizer_steps"] != 2 or report["batch_size"] != 14:
        raise ValueError("Encoder smoke budget drift")
    if report["logit_shapes"] != [[14, 7], [14, 7]] or not report["trainable_parameters_changed"]:
        raise ValueError("Encoder shape/update gate failed")
    if len(report["finite_losses"]) != 2 or not all(math.isfinite(value) for value in report["finite_losses"]):
        raise ValueError("Encoder finite-loss gate failed")


def verify_qwen(
    config: dict[str, Any],
    selection: list[dict[str, Any]],
    report: dict[str, Any],
) -> None:
    output_path = resolve_project_path(config["private_root"]) / "qwen-outputs.jsonl"
    outputs = load_jsonl(output_path)
    if len(outputs) != 42 or report["generation_rows"] != 42:
        raise ValueError("Qwen generation budget mismatch")
    if report["private_output_sha256"] != sha256_file(output_path):
        raise ValueError("Qwen private-output hash mismatch")
    by_id = {row["sample_id"]: row for row in selection}
    conditions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    identities: set[tuple[str, str]] = set()
    for row in outputs:
        source = by_id.get(row["sample_id"])
        if source is None or row["gold_label"] != source["label"]:
            raise ValueError("Qwen private output identity mismatch")
        identity = (row["sample_id"], row["condition"])
        if identity in identities:
            raise ValueError("Duplicate Qwen smoke condition")
        identities.add(identity)
        expected_seed = int(
            sha256_text(
                f"{config['qwen']['inference']['generation_seed_namespace']}:"
                f"{row['condition']}:{row['sample_id']}"
            )[:8],
            16,
        )
        if row["seed"] != expected_seed:
            raise ValueError("Qwen generation seed mismatch")
        expected_parse = independent_parse(
            row["raw_output"], bool(row["thinking"]), tuple(config["data"]["labels"])
        )
        if row["parse"] != expected_parse:
            raise ValueError("Independent Qwen parser result mismatch")
        conditions[row["condition"]].append(row)
    if len(conditions) != 6 or set(len(values) for values in conditions.values()) != {7}:
        raise ValueError("Qwen condition coverage mismatch")
    valid_total = 0
    for condition, values in conditions.items():
        public = report["conditions"][condition]
        valid = sum(row["parse"]["valid"] for row in values)
        valid_total += valid
        if public["rows"] != len(values) or public["parser_valid_count"] != valid:
            raise ValueError(f"Qwen parser count mismatch for {condition}")
        assert_close(public["parser_valid_rate"], valid / len(values), f"{condition}.valid_rate")
        if public["finish_reasons"] != dict(sorted(Counter(row["finish_reason"] for row in values).items())):
            raise ValueError(f"Qwen finish reasons mismatch for {condition}")
        expected_errors = dict(
            sorted(Counter(row["parse"]["error"] for row in values if row["parse"]["error"]).items())
        )
        if public["parser_errors"] != expected_errors:
            raise ValueError(f"Qwen parser errors mismatch for {condition}")
        compare_numeric_summary(
            public["generated_tokens"],
            numeric_summary([row["generated_tokens"] for row in values]),
            f"{condition}.generated_tokens",
        )
        compare_numeric_summary(
            public["generation_seconds"],
            numeric_summary([row["generation_seconds"] for row in values]),
            f"{condition}.generation_seconds",
        )
        compare_numeric_summary(
            public["prompt_tokens"],
            numeric_summary([row["prompt_tokens"] for row in values]),
            f"{condition}.prompt_tokens",
        )
        assert_close(public["peak_memory_gb_max"], max(row["peak_memory_gb"] for row in values), f"{condition}.peak")
    if report["overall_parser_valid_count"] != valid_total:
        raise ValueError("Qwen overall parser count mismatch")
    assert_close(report["overall_parser_valid_rate"], valid_total / 42, "qwen.overall_valid_rate")
    if report["sampler"]["generation_seed_namespace"] != config["qwen"]["inference"]["generation_seed_namespace"]:
        raise ValueError("Qwen public seed namespace mismatch")
    if report["status"] != "Passed" or report["performance_metrics_computed"]:
        raise ValueError("Qwen parser or no-performance gate failed")


def verify_lora(config: dict[str, Any], report: dict[str, Any], allow_gpu_blocked: bool) -> str:
    lora = config["qwen"]["lora"]
    expected_modules = len(lora["adapted_block_indices"]) * len(lora["target_modules"])
    if report["exact_insertion_count"] != expected_modules:
        raise ValueError("LoRA insertion count mismatch")
    if report["status"] == "blocked_gpu_required":
        if not allow_gpu_blocked or report.get("error_type") != "local_memory_gate":
            raise ValueError("LoRA is GPU-blocked without an allowed resource record")
        return "Blocked"
    if report["status"] != "Passed":
        raise ValueError("LoRA smoke did not pass")
    adapter_root = resolve_project_path(config["private_root"]) / "lora-adapter"
    adapter_file = adapter_root / "adapters.safetensors"
    adapter_config = adapter_root / "adapter_config.json"
    runtime_path = resolve_project_path(config["private_root"]) / "lora-runtime.json"
    if not all(path.is_file() for path in (adapter_file, adapter_config, runtime_path)):
        raise FileNotFoundError("LoRA private artifacts are incomplete")
    runtime = load_json(runtime_path)
    if (
        runtime["test"]
        or runtime["val_batches"] != 0
        or not runtime["train"]
        or runtime["iters"] != lora["iterations"]
        or runtime["num_layers"] != lora["num_layers"]
        or runtime["lora_parameters"]["keys"] != lora["target_modules"]
    ):
        raise ValueError("LoRA runtime contract drift")
    import numpy as np
    from safetensors import safe_open

    tensor_count = parameter_count = b_count = b_nonzero = 0
    with safe_open(adapter_file, framework="numpy") as source:
        for name in source.keys():
            tensor = source.get_tensor(name)
            tensor_count += 1
            parameter_count += int(tensor.size)
            if name.endswith("lora_b"):
                b_count += 1
                b_nonzero += int(bool(np.any(tensor != 0)))
    expected = {
        "lora_b_nonzero_tensors": b_nonzero,
        "lora_b_tensor_count": b_count,
        "tensor_count": tensor_count,
        "trainable_parameter_count": parameter_count,
        "weights_sha256": sha256_file(adapter_file),
    }
    if report["adapter"] != expected or b_count != expected_modules or b_nonzero != expected_modules:
        raise ValueError("LoRA adapter tensor summary mismatch")
    if len(report["history"]) != lora["iterations"] or not report["reload_finite_logits"]:
        raise ValueError("LoRA history/reload gate failed")
    for row in report["history"]:
        if not math.isfinite(row["train_loss"]):
            raise ValueError("LoRA history contains non-finite loss")
    return "Passed"


def iter_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_keys(child)


def verify_privacy(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    public_root: Path,
) -> dict[str, Any]:
    public_paths = [public_root / "run.json", *(public_root / name for name in PUBLIC_STAGE_FILES.values())]
    public_paths.extend(
        [
            resolve_project_path(config["qwen"]["local_path"]).parent / "manifest.json",
            resolve_project_path(config["encoder"]["local_path"]).parent / "manifest.json",
        ]
    )
    forbidden_keys = {
        "sample_id",
        "group_id",
        "raw_output",
        "gold_label",
        "prediction",
        "predicted_label",
        "target",
        "previous",
        "canonical_output",
        "parsed_label",
    }
    combined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in public_paths)
    for path in public_paths:
        value = load_json(path)
        overlap = forbidden_keys.intersection(iter_keys(value))
        if overlap:
            raise ValueError(f"Public artifact exposes forbidden row-level keys: {path}: {overlap}")
    identifiers = {row["sample_id"] for row in rows} | {row["group_id"] for row in rows}
    if any(identifier and identifier in combined for identifier in identifiers):
        raise ValueError("Public artifact contains a private row/group ID")
    private_text = {
        text
        for row in rows
        for text in (
            row["views"]["target_only"]["target"],
            row["views"]["previous_context"]["previous"],
        )
        if isinstance(text, str) and len(text) >= 8
    }
    if any(text in combined for text in private_text):
        raise ValueError("Public artifact contains private source text")
    private = resolve_project_path(config["private_root"])
    if (private.stat().st_mode & 0o777) != 0o700:
        raise PermissionError("Private EXP-041 root is not mode 0700")
    private_directories = [path for path in private.rglob("*") if path.is_dir()]
    for path in private_directories:
        if (path.stat().st_mode & 0o777) != 0o700:
            raise PermissionError(f"Private directory is not mode 0700: {path}")
    private_files = [path for path in private.rglob("*") if path.is_file()]
    for path in private_files:
        if (path.stat().st_mode & 0o777) != 0o600:
            raise PermissionError(f"Private file is not mode 0600: {path}")
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False
        ).returncode
        if ignored != 0:
            raise ValueError(f"Private file is not Git ignored: {path}")
    return {
        "private_directories_checked": len(private_directories) + 1,
        "private_files_checked": len(private_files),
        "public_files_checked": len(public_paths),
        "raw_id_matches": 0,
        "raw_text_matches": 0,
        "status": "Passed",
    }


def main() -> None:
    args = parse_args()
    config = load_and_verify_config()
    output = resolve_project_path(config["run_dir"]) / "verification.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite independent verification: {output}")
    public_root, run, reports = verify_run_and_stage_artifacts(config)
    rows, reconstructed = reconstruct_selection(config)
    selection = verify_static(config, rows, reconstructed, reports["static"])
    verify_models(config, reports["models"])
    verify_tokenization(config, reports["tokenize"])
    verify_classical(config, reports["classical"])
    verify_encoder(reports["encoder"])
    verify_qwen(config, selection, reports["qwen"])
    lora_status = verify_lora(config, reports["lora"], args.allow_gpu_blocked)
    privacy = verify_privacy(config, rows, public_root)
    status = "Passed" if lora_status == "Passed" else "Blocked"
    if status == "Passed" and any(
        run["stages"][stage]["status"] != "Passed" for stage in PUBLIC_STAGE_FILES
    ):
        raise ValueError("A required run stage is not passed")
    checks = [
        "frozen-implementation-hashes",
        "train-only-run-boundary",
        "deterministic-selection-reconstruction",
        "prompt-and-parser-independence",
        "qwen-source-inventory",
        "qwen-mlx-inventory",
        "encoder-source-inventory",
        "sequence-length-and-target-preservation",
        "lora-train-only-data-schema",
        "classical-finite-shape",
        "encoder-finite-update",
        "qwen-condition-coverage",
        "qwen-independent-output-parse",
        "qwen-aggregate-recalculation",
        "lora-insertion-and-adapter",
        "public-private-boundary",
    ]
    result = {
        "accessed_splits": ["train"],
        "audit_id": AUDIT_ID,
        "check_count": len(checks),
        "checks": checks,
        "experiment_id": EXPERIMENT_ID,
        "implementation": {
            "imports_parser": False,
            "imports_runner": False,
            "verifier": artifact(Path(__file__)),
        },
        "lora_gate": lora_status,
        "mismatches": 0,
        "privacy": privacy,
        "recomputed_qwen_rows": 42,
        "reconstructed_selection_rows": len(selection),
        "status": status,
        "test_split_accessed": False,
        "train_rows_reparsed": len(rows),
        "validation_split_accessed": False,
    }
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"verification": status, "mismatches": 0, "checks": result["check_count"]}))


if __name__ == "__main__":
    main()

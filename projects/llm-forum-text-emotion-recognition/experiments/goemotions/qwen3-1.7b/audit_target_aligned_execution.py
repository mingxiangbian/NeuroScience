#!/usr/bin/env python3
"""Audit the complete model, runtime, and smoke contract without training."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import sys
from typing import Any


AUDIT_ID = "PRE-EXP-033-EXECUTION"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-contract.json"
VERIFIER_PATH = SCRIPT_DIR / "verify_target_aligned_execution.py"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_artifact(spec: dict[str, Any]) -> Path:
    path = resolve_path(spec["path"])
    if sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen artifact hash mismatch: {path}")
    return path


def package_versions() -> dict[str, str]:
    versions = {
        name: importlib.metadata.version(name)
        for name in ("mlx", "mlx-lm", "numpy", "transformers")
    }
    versions["python"] = platform.python_version()
    return versions


def load_source_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load source module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_model_files(model: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_path = resolve_path(model["manifest_path"])
    if sha256_file(manifest_path) != model["manifest_sha256"]:
        raise ValueError("Model manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest["repo_id"] != model["repo_id"]
        or manifest["revision"] != model["revision"]
        or manifest["condition"] != model["condition"]
        or manifest["conversion"]["dtype"] != model["precision"]
        or manifest["conversion"]["quantized"] != model["quantized"]
    ):
        raise ValueError("Model manifest identity differs from the contract")
    model_dir = resolve_path(model["local_path"])
    expected = {entry["path"]: entry for entry in manifest["mlx_bf16"]["files"]}
    actual = {path.name for path in model_dir.iterdir() if path.is_file()}
    if actual != set(expected):
        raise ValueError(f"Model directory file set differs: {sorted(actual ^ set(expected))}")
    verified = []
    for name in sorted(expected):
        path = model_dir / name
        entry = expected[name]
        if path.stat().st_size != int(entry["bytes"]):
            raise ValueError(f"Model artifact size mismatch: {path}")
        digest = sha256_file(path)
        if digest != entry["sha256"]:
            raise ValueError(f"Model artifact hash mismatch: {path}")
        verified.append({"bytes": path.stat().st_size, "path": name, "sha256": digest})
    if sum(item["bytes"] for item in verified) != int(manifest["mlx_bf16"]["total_bytes"]):
        raise ValueError("Model artifact total size mismatch")
    return verified


def deterministic_pick(
    rows: list[dict[str, Any]], selected: set[int], salt: str
) -> dict[str, Any]:
    candidates = [row for row in rows if row["row_number"] not in selected]
    if not candidates:
        raise ValueError(f"No row remains for {salt}")
    return min(
        candidates,
        key=lambda row: sha256_text(f"{salt}:{row['row_number']}"),
    )


def select_boundary_smoke(
    rows: list[dict[str, Any]],
    labels: tuple[str, ...],
    truncated_rows: set[int],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = set(truncated_rows)
    maximum_cardinality = max(row["cardinality"] for row in rows)
    for cardinality in (4, maximum_cardinality):
        if any(
            row["row_number"] in selected and row["cardinality"] == cardinality
            for row in rows
        ):
            continue
        chosen = deterministic_pick(
            [row for row in rows if row["cardinality"] == cardinality],
            selected,
            f"PRE-EXP-033-boundary-cardinality:{cardinality}",
        )
        selected.add(chosen["row_number"])
    maximum_target_tokens = max(row["target_tokens"] for row in rows)
    if not any(
        row["row_number"] in selected
        and row["target_tokens"] == maximum_target_tokens
        for row in rows
    ):
        chosen = deterministic_pick(
            [row for row in rows if row["target_tokens"] == maximum_target_tokens],
            selected,
            "PRE-EXP-033-boundary-target-tokens",
        )
        selected.add(chosen["row_number"])

    neutral_rows = [row for row in rows if row["neutral_cooccurrence"]]
    target_neutral = int(contract["exact_neutral_cooccurrence_rows"])
    while sum(
        row["neutral_cooccurrence"] and row["row_number"] in selected for row in rows
    ) < target_neutral:
        chosen = deterministic_pick(
            neutral_rows,
            selected,
            f"PRE-EXP-033-boundary-neutral:{len(selected)}",
        )
        selected.add(chosen["row_number"])
    if sum(
        row["neutral_cooccurrence"] and row["row_number"] in selected for row in rows
    ) > target_neutral:
        raise ValueError("Mandatory boundary rows exceed the neutral smoke quota")

    label_to_id = {label: index for index, label in enumerate(labels)}
    for label in labels:
        label_id = label_to_id[label]
        if any(
            row["row_number"] in selected and label_id in row["label_ids"]
            for row in rows
        ):
            continue
        chosen = deterministic_pick(
            [
                row
                for row in rows
                if not row["neutral_cooccurrence"] and label_id in row["label_ids"]
            ],
            selected,
            f"PRE-EXP-033-boundary-label:{label_id}",
        )
        selected.add(chosen["row_number"])
    non_neutral = [row for row in rows if not row["neutral_cooccurrence"]]
    while len(selected) < int(contract["rows"]):
        chosen = deterministic_pick(
            non_neutral,
            selected,
            f"PRE-EXP-033-boundary-fill:{len(selected)}",
        )
        selected.add(chosen["row_number"])
    if len(selected) != int(contract["rows"]):
        raise ValueError("Boundary smoke row count overflowed")
    return sorted(
        (row for row in rows if row["row_number"] in selected),
        key=lambda row: row["row_number"],
    )


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract["audit_id"] != AUDIT_ID:
        raise ValueError("Unexpected execution audit contract")
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    report_path = resolve_path(contract["outputs"]["audit_report"])
    verification_path = resolve_path(contract["outputs"]["verification_report"])
    smoke_path = resolve_path(contract["outputs"]["private_smoke_path"])
    if report_path.exists() or verification_path.exists() or smoke_path.exists():
        raise FileExistsError("Execution preflight outputs already exist; they are append-only")

    for spec in contract["data_contract"].values():
        verify_artifact(spec)
    for spec in contract["parent_evidence"].values():
        verify_artifact(spec)
    for spec in contract["aligned_inference"].values():
        if isinstance(spec, dict) and "path" in spec:
            verify_artifact(spec)
    for key, spec in contract["runtime"].items():
        if key != "packages":
            verify_artifact(spec)
    versions = package_versions()
    if versions != contract["runtime"]["packages"]:
        raise ValueError(f"Runtime package drift: {versions}")

    parent_config = json.loads(
        resolve_path(contract["parent_evidence"]["exp_029_config"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if contract["training"] != parent_config["training"]:
        raise ValueError("Complete training condition differs from EXP-029")
    if contract["model"] != parent_config["model"]:
        raise ValueError("Complete model condition differs from EXP-029")
    if contract["preflight"] != parent_config["preflight"]:
        raise ValueError("Complete smoke/LoRA preflight differs from EXP-029")
    exp_032 = json.loads(
        resolve_path(
            contract["parent_evidence"]["exp_032_verification"]["path"]
        ).read_text(encoding="utf-8")
    )
    if exp_032["training"]["selected_condition"] != "batch2-grad5":
        raise ValueError("EXP-032 training selection changed")
    if exp_032["cache"]["recommended"] is not False:
        raise ValueError("EXP-032 cache rejection changed")
    if contract["aligned_inference"]["prompt_execution"] != "full-prompt":
        raise ValueError("Rejected common-prefix cache was reintroduced")

    model_files = audit_model_files(contract["model"])
    data_report = json.loads(
        resolve_path(contract["data_contract"]["audit_report"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    data_verification = json.loads(
        resolve_path(
            contract["data_contract"]["verification_report"]["path"]
        ).read_text(encoding="utf-8")
    )
    if data_report["status"] != "Passed" or data_verification["status"] != "Passed":
        raise ValueError("Target-aligned data contract did not pass")
    prepared_path = resolve_path(contract["data_contract"]["prepared_train"]["path"])
    if sha256_file(prepared_path) != contract["data_contract"]["prepared_train"]["sha256"]:
        raise ValueError("Prepared train hash changed")

    tokenizer_module = load_source_module(
        "pre_exp_033_tokenizer_utils",
        Path(contract["runtime"]["tokenizer_utils_source"]["path"]),
    )
    datasets_module = load_source_module(
        "pre_exp_033_datasets",
        Path(contract["runtime"]["datasets_source"]["path"]),
    )
    tokenizer = tokenizer_module.load(resolve_path(contract["model"]["local_path"]))
    if tokenizer.has_thinking is not True:
        raise ValueError("MLX-LM TokenizerWrapper did not detect Qwen thinking tokens")
    labels = tuple(
        (PROJECT_ROOT / "data" / "goemotions" / "official" / "emotions.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    label_to_id = {label: index for index, label in enumerate(labels)}
    neutral = "neutral"
    rows: list[dict[str, Any]] = []
    with prepared_path.open("r", encoding="utf-8") as source:
        for row_number, line in enumerate(source, start=1):
            record = json.loads(line)
            target = json.loads(record["messages"][-1]["content"])["labels"]
            label_ids = tuple(label_to_id[label] for label in target)
            if label_ids != tuple(sorted(label_ids)):
                raise ValueError(f"Prepared target order changed at row {row_number}")
            rows.append(
                {
                    "cardinality": len(target),
                    "label_ids": label_ids,
                    "line": line,
                    "neutral_cooccurrence": neutral in target and len(target) > 1,
                    "record": record,
                    "row_number": row_number,
                    "target_tokens": len(
                        tokenizer.encode(record["messages"][-1]["content"], add_special_tokens=False)
                    ),
                }
            )
    if len(rows) != int(contract["data_contract"]["prepared_train"]["rows"]):
        raise ValueError("Prepared train row count changed")
    truncated_rows = {
        int(item["row_number"]) for item in data_report["truncation"]["records"]
    }
    smoke = select_boundary_smoke(
        rows,
        labels,
        truncated_rows,
        contract["smoke_contract"],
    )
    smoke_records = [row["record"] for row in smoke]
    chat_dataset = datasets_module.ChatDataset(
        smoke_records,
        tokenizer,
        mask_prompt=bool(contract["training"]["mask_prompt"]),
    )
    sequence_lengths: list[int] = []
    target_cardinalities: list[int] = []
    control_counts: set[int] = set()
    for row, record in zip(smoke, smoke_records, strict=True):
        tokens, offset = chat_dataset.process(record)
        tokens = list(tokens)
        inference_prefix = list(
            tokenizer.apply_chat_template(
                record["messages"][:-1],
                add_generation_prompt=True,
                enable_thinking=False,
                return_dict=False,
            )
        )
        target_and_eos = list(
            tokenizer.encode(
                record["messages"][-1]["content"] + "<|im_end|>\n",
                add_special_tokens=False,
            )
        )
        if tokens[: len(inference_prefix)] != inference_prefix:
            raise ValueError(f"Runtime inference context mismatch at row {row['row_number']}")
        if tokens[len(inference_prefix) :] != target_and_eos:
            raise ValueError(f"Runtime target suffix mismatch at row {row['row_number']}")
        control_counts.add(len(inference_prefix) - int(offset))
        sequence_lengths.append(len(tokens))
        target_cardinalities.append(row["cardinality"])
    smoke_spec = contract["smoke_contract"]
    smoke_rows = {row["row_number"] for row in smoke}
    coverage = {label_id for row in smoke for label_id in row["label_ids"]}
    neutral_count = sum(row["neutral_cooccurrence"] for row in smoke)
    if coverage != set(range(len(labels))) or control_counts != {4}:
        raise ValueError("Runtime smoke coverage or loss boundary failed")
    if neutral_count != int(smoke_spec["exact_neutral_cooccurrence_rows"]):
        raise ValueError("Runtime smoke neutral quota failed")
    if not truncated_rows.issubset(smoke_rows) or max(sequence_lengths) != int(
        smoke_spec["must_reach_max_sequence_length"]
    ):
        raise ValueError("Runtime smoke does not cover truncation boundaries")
    if max(target_cardinalities) < int(smoke_spec["max_target_cardinality_at_least"]):
        raise ValueError("Runtime smoke omits the maximum target cardinality")
    if 4 not in target_cardinalities:
        raise ValueError("Runtime smoke omits cardinality-four targets")

    smoke_path.parent.mkdir(parents=True, exist_ok=False)
    smoke_path.write_text("".join(row["line"] for row in smoke), encoding="utf-8")
    report = {
        "accessed_splits": ["train"],
        "audit_id": AUDIT_ID,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "complete_inheritance": {
            "model_equals_exp_029": True,
            "preflight_equals_exp_029": True,
            "training_equals_exp_029": True,
            "training_sha256": sha256_text(
                json.dumps(contract["training"], separators=(",", ":"), sort_keys=True)
            ),
        },
        "contract": artifact(CONTRACT_PATH),
        "execution_gate": {
            "formal_training_authorized": False,
            "model_forward_or_backward_executed": False,
            "next_required_step": contract["execution_gate"]["next_required_step"],
        },
        "implementation": {
            "auditor": artifact(Path(__file__)),
            "verifier": artifact(VERIFIER_PATH),
        },
        "model": {
            "files": model_files,
            "manifest": artifact(resolve_path(contract["model"]["manifest_path"])),
            "verified_file_count": len(model_files),
            "verified_total_bytes": sum(item["bytes"] for item in model_files),
        },
        "privacy": {
            "public_comment_ids": False,
            "public_raw_text": False,
        },
        "runtime": {
            "chat_dataset_process_executed_rows": len(smoke),
            "packages": versions,
            "tokenizer_wrapper_has_thinking": tokenizer.has_thinking,
        },
        "smoke": {
            **artifact(smoke_path),
            "control_token_counts": sorted(control_counts),
            "covers_all_labels": True,
            "includes_all_truncated_rows": truncated_rows.issubset(smoke_rows),
            "max_sequence_tokens": max(sequence_lengths),
            "max_target_cardinality": max(target_cardinalities),
            "neutral_cooccurrence_rows": neutral_count,
            "row_numbers": [row["row_number"] for row in smoke],
            "rows": len(smoke),
        },
        "status": "Passed",
        "test_split_absent": not TEST_PATH.exists(),
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

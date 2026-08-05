#!/usr/bin/env python3
"""Verify PRE-EXP-033 execution inputs; --check never rewrites evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-contract.json"
REPORT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-audit.json"
VERIFICATION_PATH = (
    SCRIPT_DIR / "preflight" / "pre-exp-033-execution-verification.json"
)
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


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


def verify_spec(spec: dict[str, Any]) -> Path:
    path = resolve_path(spec["path"])
    if sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen artifact changed: {path}")
    return path


def verify_model(contract: dict[str, Any], report: dict[str, Any]) -> None:
    model = contract["model"]
    manifest_path = resolve_path(model["manifest_path"])
    if sha256_file(manifest_path) != model["manifest_sha256"]:
        raise ValueError("Model manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest["repo_id"] != model["repo_id"]
        or manifest["revision"] != model["revision"]
        or manifest["condition"] != model["condition"]
        or manifest["conversion"]["dtype"] != model["precision"]
        or manifest["conversion"]["quantized"] != model["quantized"]
    ):
        raise ValueError("Model identity changed")
    expected = {entry["path"]: entry for entry in manifest["mlx_bf16"]["files"]}
    model_dir = resolve_path(model["local_path"])
    actual_names = {path.name for path in model_dir.iterdir() if path.is_file()}
    if actual_names != set(expected):
        raise ValueError("Model file set changed")
    reported = {entry["path"]: entry for entry in report["model"]["files"]}
    if set(reported) != set(expected):
        raise ValueError("Audit report model file set is incomplete")
    for name, entry in expected.items():
        path = model_dir / name
        digest = sha256_file(path)
        if path.stat().st_size != int(entry["bytes"]) or digest != entry["sha256"]:
            raise ValueError(f"Model file changed: {name}")
        if reported[name] != {
            "bytes": int(entry["bytes"]),
            "path": name,
            "sha256": entry["sha256"],
        }:
            raise ValueError(f"Reported model evidence differs: {name}")


def main() -> None:
    args = parse_args()
    if not args.check and VERIFICATION_PATH.exists():
        raise FileExistsError("Verification output already exists; use --check")
    if not REPORT_PATH.is_file():
        raise FileNotFoundError("Execution audit report is absent")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if report["status"] != "Passed" or report["audit_id"] != "PRE-EXP-033-EXECUTION":
        raise ValueError("Execution audit did not pass")
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    if report["contract"]["sha256"] != sha256_file(CONTRACT_PATH):
        raise ValueError("Execution contract hash mismatch")
    for spec in contract["data_contract"].values():
        verify_spec(spec)
    for spec in contract["parent_evidence"].values():
        verify_spec(spec)
    for value in contract["aligned_inference"].values():
        if isinstance(value, dict) and "path" in value:
            verify_spec(value)
    for key, spec in contract["runtime"].items():
        if key != "packages":
            verify_spec(spec)
    versions = package_versions()
    if versions != contract["runtime"]["packages"] or versions != report["runtime"]["packages"]:
        raise ValueError("Runtime package versions changed")

    parent_config = json.loads(
        resolve_path(contract["parent_evidence"]["exp_029_config"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if contract["training"] != parent_config["training"]:
        raise ValueError("Complete training condition changed")
    if contract["model"] != parent_config["model"]:
        raise ValueError("Complete model condition changed")
    if contract["preflight"] != parent_config["preflight"]:
        raise ValueError("Complete preflight condition changed")
    exp_032 = json.loads(
        resolve_path(
            contract["parent_evidence"]["exp_032_verification"]["path"]
        ).read_text(encoding="utf-8")
    )
    if exp_032["training"]["selected_condition"] != "batch2-grad5":
        raise ValueError("Selected training condition changed")
    if exp_032["cache"]["recommended"] is not False:
        raise ValueError("Rejected prompt cache was reintroduced")
    verify_model(contract, report)

    auditor_path = resolve_path(report["implementation"]["auditor"]["path"])
    if sha256_file(auditor_path) != report["implementation"]["auditor"]["sha256"]:
        raise ValueError("Execution auditor changed after evidence generation")
    if sha256_file(Path(__file__)) != report["implementation"]["verifier"]["sha256"]:
        raise ValueError("Execution verifier changed after evidence generation")
    smoke_path = resolve_path(contract["outputs"]["private_smoke_path"])
    if sha256_file(smoke_path) != report["smoke"]["sha256"]:
        raise ValueError("Boundary smoke artifact changed")
    prepared_path = resolve_path(contract["data_contract"]["prepared_train"]["path"])
    if sha256_file(prepared_path) != contract["data_contract"]["prepared_train"]["sha256"]:
        raise ValueError("Prepared train artifact changed")
    prepared_lines = prepared_path.read_text(encoding="utf-8").splitlines(keepends=True)
    smoke_lines = smoke_path.read_text(encoding="utf-8").splitlines(keepends=True)
    row_numbers = [int(value) for value in report["smoke"]["row_numbers"]]
    if smoke_lines != [prepared_lines[row - 1] for row in row_numbers]:
        raise ValueError("Boundary smoke rows differ from prepared train")

    tokenizer_module = load_source_module(
        "pre_exp_033_verify_tokenizer_utils",
        Path(contract["runtime"]["tokenizer_utils_source"]["path"]),
    )
    datasets_module = load_source_module(
        "pre_exp_033_verify_datasets",
        Path(contract["runtime"]["datasets_source"]["path"]),
    )
    tokenizer = tokenizer_module.load(resolve_path(contract["model"]["local_path"]))
    if tokenizer.has_thinking is not True or report["runtime"][
        "tokenizer_wrapper_has_thinking"
    ] is not True:
        raise ValueError("TokenizerWrapper thinking detection changed")
    records = [json.loads(line) for line in smoke_lines]
    dataset = datasets_module.ChatDataset(records, tokenizer, mask_prompt=True)
    labels = tuple(
        (PROJECT_ROOT / "data" / "goemotions" / "official" / "emotions.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    coverage: set[str] = set()
    neutral_count = 0
    cardinalities: list[int] = []
    lengths: list[int] = []
    control_counts: set[int] = set()
    for record in records:
        target = json.loads(record["messages"][-1]["content"])["labels"]
        if not target or len(target) != len(set(target)) or any(x not in labels for x in target):
            raise ValueError("Boundary smoke target is invalid")
        coverage.update(target)
        neutral_count += int("neutral" in target and len(target) > 1)
        cardinalities.append(len(target))
        tokens, offset = dataset.process(record)
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
            raise ValueError("Actual ChatDataset inference context mismatch")
        if tokens[len(inference_prefix) :] != target_and_eos:
            raise ValueError("Actual ChatDataset target suffix mismatch")
        control_counts.add(len(inference_prefix) - int(offset))
        lengths.append(len(tokens))
    smoke_contract = contract["smoke_contract"]
    truncated_rows = {
        int(item["row_number"])
        for item in json.loads(
            resolve_path(contract["data_contract"]["audit_report"]["path"]).read_text(
                encoding="utf-8"
            )
        )["truncation"]["records"]
    }
    if coverage != set(labels) or control_counts != {4}:
        raise ValueError("Boundary smoke runtime coverage failed")
    if neutral_count != int(smoke_contract["exact_neutral_cooccurrence_rows"]):
        raise ValueError("Boundary smoke neutral quota failed")
    if not truncated_rows.issubset(set(row_numbers)):
        raise ValueError("Boundary smoke omits truncated rows")
    if max(lengths) != int(smoke_contract["must_reach_max_sequence_length"]):
        raise ValueError("Boundary smoke omits max-length sequence")
    if max(cardinalities) < int(smoke_contract["max_target_cardinality_at_least"]):
        raise ValueError("Boundary smoke omits max-cardinality target")
    if 4 not in cardinalities:
        raise ValueError("Boundary smoke omits cardinality-four target")

    verification = {
        "accessed_splits": ["train"],
        "audit_id": "PRE-EXP-033-EXECUTION",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "formal_training_authorized": False,
        "independent_checks": {
            "actual_chat_dataset_rows": len(records),
            "all_model_manifest_files_rehashed": len(report["model"]["files"]),
            "boundary_smoke_max_sequence_tokens": max(lengths),
            "boundary_smoke_max_target_cardinality": max(cardinalities),
            "boundary_smoke_neutral_cooccurrence_rows": neutral_count,
            "complete_model_condition_inherited": True,
            "complete_preflight_condition_inherited": True,
            "complete_training_condition_inherited": True,
            "runtime_and_tokenizer_rechecked": True,
            "test_split_absent": True,
        },
        "mode": "check" if args.check else "initial-write",
        "model_forward_or_backward_executed": False,
        "next_required_step": contract["execution_gate"]["next_required_step"],
        "report_sha256": sha256_file(REPORT_PATH),
        "runtime_packages": versions,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    if not args.check:
        VERIFICATION_PATH.write_text(
            json.dumps(verification, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

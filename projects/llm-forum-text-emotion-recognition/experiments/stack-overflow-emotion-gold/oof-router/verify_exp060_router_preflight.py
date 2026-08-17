#!/usr/bin/env python3
"""Independently verify the no-result EXP-060 router preflight."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Iterable
import zipfile

import numpy as np


EXPERIMENT_ID = "EXP-060"
RQ_ID = "RQ-S3"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
FEATURE_NAMES = (
    "m1_probability_love",
    "m1_probability_joy",
    "m1_probability_surprise",
    "m1_probability_anger",
    "m1_probability_sadness",
    "m1_probability_fear",
    "m1_mean_binary_entropy",
    "m1_max_binary_entropy",
    "m1_minimum_threshold_margin",
    "m1_predicted_cardinality",
    "m1_highest_probability",
    "m1_lowest_probability",
    "character_length",
    "m1_token_length",
)
PROHIBITED_RUNTIME_PREFIXES = (
    "m3_",
    "gold",
    "oracle",
    "sample_id",
    "component_id",
    "fold_id",
    "raw_text",
    "validation",
    "test",
)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-060-router-preflight.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            yield value
        else:
            for child in value.values():
                yield from iter_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_records(child)


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def npz_header_schema(path: Path) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            if not member.endswith(".npy"):
                continue
            with archive.open(member) as source:
                version = np.lib.format.read_magic(source)
                if version == (1, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_1_0(source)
                elif version == (2, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_2_0(source)
                else:
                    shape, fortran, dtype = np.lib.format._read_array_header(source, version)
            schema[Path(member).stem] = {
                "shape": list(shape),
                "dtype": str(dtype),
                "fortran_order": bool(fortran),
            }
    return schema


def expected_paired_schema() -> dict[str, dict[str, Any]]:
    return {
        "sample_ids": {"shape": [3360], "dtype": "<U31", "fortran_order": False},
        "component_ids": {"shape": [3360], "dtype": "<U34", "fortran_order": False},
        "fold_ids": {"shape": [3360], "dtype": "int8", "fortran_order": False},
        "gold": {"shape": [3360, 6], "dtype": "uint8", "fortran_order": False},
        "m1_logits": {"shape": [3360, 6], "dtype": "float32", "fortran_order": False},
        "m3_logits": {"shape": [3360, 6], "dtype": "float32", "fortran_order": False},
        "character_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
        "m1_token_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
        "m3_token_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
        "m1_fold_run_sha256": {"shape": [3360], "dtype": "<U64", "fortran_order": False},
        "m3_fold_run_sha256": {"shape": [3360], "dtype": "<U64", "fortran_order": False},
    }


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


def verify(config_path: Path) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("rq_id") != RQ_ID:
        raise ValueError("EXP-060 config identity drift")
    run_dir = resolve_project(config["outputs"]["preflight_run_dir"])
    run_path = run_dir / "run.json"
    contract_path = run_dir / "preflight-contract.json"
    if not run_path.is_file() or not contract_path.is_file():
        raise FileNotFoundError("EXP-060 preflight outputs are incomplete")

    checks = Checks()
    run = json.loads(run_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    checks.add("run_identity", run.get("experiment_id") == EXPERIMENT_ID and run.get("rq_id") == RQ_ID)
    checks.add("run_stage", run.get("stage") == "no-result-preflight")
    checks.add("run_completed", run.get("status") == "Completed")
    checks.add("runner_checks_all_passed", run["checks"]["failed"] == 0)

    authorization = config["authorization"]
    for key in (
        "formal_router_training",
        "formal_result_computation",
        "validation_access",
        "test_access",
        "model_loading_or_forward",
        "raw_text_access",
    ):
        checks.add(f"authorization_{key}_false", authorization[key] is False)
        checks.add(f"run_authorization_{key}_false", run["authorization"][key] is False)

    flags = run["execution_flags"]
    for key, value in flags.items():
        checks.add(f"execution_flag_{key}_false", value is False)

    for section in ("implementation", "prerequisites", "input"):
        for index, record in enumerate(iter_records(config[section])):
            path = require_record(record)
            checks.add(f"frozen_{section}_{index}", path.stat().st_size == record["bytes"])

    frozen_sources = run["source_artifacts"]
    expected_frozen_names = {"config", *config["implementation"].keys()}
    checks.add("frozen_source_keys", set(frozen_sources) == expected_frozen_names, sorted(frozen_sources))
    for key, record in frozen_sources.items():
        path = require_record(record)
        checks.add(f"frozen_source_{key}_exists", path.is_file())
        if key == "config":
            checks.add("frozen_config_matches", path.read_bytes() == config_path.read_bytes())
        else:
            source = require_record(config["implementation"][key])
            checks.add(f"frozen_source_{key}_matches", path.read_bytes() == source.read_bytes())

    paired = require_record(config["input"]["paired_oof"])
    schema = npz_header_schema(paired)
    checks.add("paired_schema_exact", schema == expected_paired_schema())
    checks.add("paired_mode_0600", stat.S_IMODE(paired.stat().st_mode) == 0o600)
    checks.add("paired_parent_mode_0700", stat.S_IMODE(paired.parent.stat().st_mode) == 0o700)

    calibration_path = require_record(config["prerequisites"]["exp059_calibration_parameters"])
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    selected = {
        family: calibration["families"][family]["selected_calibrator"] for family in ("m1", "m3")
    }
    temperatures = {
        family: calibration["families"][family]["final_temperature"] for family in ("m1", "m3")
    }
    checks.add("identity_calibration_recomputed", selected == {"m1": "identity", "m3": "identity"})
    checks.add("identity_temperature_recomputed", temperatures == {"m1": 1.0, "m3": 1.0})

    features = tuple(config["feature_contract"]["ordered_features"])
    checks.add("config_feature_order_exact", features == FEATURE_NAMES)
    checks.add("contract_feature_order_exact", tuple(contract["ordered_model_features"]) == FEATURE_NAMES)
    checks.add("contract_feature_count", contract["feature_count"] == 14)
    violations = [
        name for name in features if any(name.startswith(prefix) for prefix in PROHIBITED_RUNTIME_PREFIXES)
    ]
    checks.add("no_prohibited_model_feature", not violations, violations)
    checks.add("contract_result_bearing_false", contract["result_bearing"] is False)
    checks.add("contract_nested_cross_fitting", contract["nested_cross_fitting_required"] is True)
    checks.add("contract_formal_training_false", contract["formal_router_training_authorized"] is False)
    checks.add("contract_formal_results_false", contract["formal_result_computation_authorized"] is False)
    checks.add("contract_validation_false", contract["validation_access"] is False)
    checks.add("contract_test_false", contract["test_access"] is False)
    expected_schema_rows = [
        {"array_name": name, **details} for name, details in sorted(expected_paired_schema().items())
    ]
    checks.add("contract_schema_is_header_only", contract["input_schema"] == expected_schema_rows)

    formal_run = resolve_project(config["outputs"]["formal_run_dir"])
    formal_private = resolve_project(config["outputs"]["formal_private_dir"])
    checks.add("formal_run_still_absent", not formal_run.exists(), display_path(formal_run))
    checks.add("formal_private_still_absent", not formal_private.exists(), display_path(formal_private))

    allowed_public_suffixes = {".json", ".md", ".py"}
    unexpected = [
        display_path(path) for path in run_dir.rglob("*")
        if path.is_file() and path.suffix not in allowed_public_suffixes
    ]
    checks.add("no_row_level_artifact_type", not unexpected, unexpected)

    verification = {
        "schema_version": "exp-060-preflight-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": RQ_ID,
        "verified_at": utc_now(),
        "status": "Failed" if checks.failed else "Passed",
        "independent": True,
        "runner_imported": False,
        "checks": {
            "passed": len(checks.rows) - len(checks.failed),
            "failed": len(checks.failed),
            "total": len(checks.rows),
            "records": checks.rows,
        },
        "verified_artifacts": {
            "run": artifact(run_path),
            "contract": artifact(contract_path),
            "paired_oof_header_only": artifact(paired),
            "calibration_parameters": artifact(calibration_path),
        },
        "execution_claims": {
            "router_fitted": False,
            "real_router_target_computed": False,
            "router_result_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "raw_text_accessed": False,
            "model_loaded_or_forward_run": False,
        },
        "claim_boundary": "Verified no-result preflight only; formal EXP-060 remains unauthorized.",
    }
    atomic_json(run_dir / "verification.json", verification)
    summary = (
        "# EXP-060 Preflight Verification Summary\n\n"
        f"- Status: `{verification['status']}`\n"
        f"- Checks: `{verification['checks']['passed']}/{verification['checks']['total']}` passed\n"
        "- Independent verifier imported the runner: `false`\n"
        "- Router/scaler fitted: `false`\n"
        "- Real target, route score or metric computed: `false`\n"
        "- Validation/test/raw-text/model access: `false`\n"
        "- Claim boundary: protocol and environment preflight only; formal routing evidence does not yet exist.\n"
    )
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(summary, encoding="utf-8")
    print(json.dumps({
        "status": verification["status"],
        "checks_passed": verification["checks"]["passed"],
        "checks_total": verification["checks"]["total"],
        "run_dir": display_path(run_dir),
    }, sort_keys=True))
    return 1 if checks.failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(verify(parse_args().config.resolve()))

#!/usr/bin/env python3
"""Verify EXP-049 TEST-READY state without opening either test file."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONTRACT = SCRIPT_DIR / "configs" / "exp-049-test-ready.json"
DEFAULT_OUTPUT = SCRIPT_DIR / "preflight" / "exp-049-test-ready-verification-v1.json"
CONDITIONS = (
    "m0-majority",
    "m1-target-only",
    "encoder-seed-42",
    "encoder-seed-43",
    "encoder-seed-44",
    "qwen-reference",
    "qwen-lora-seed-42",
    "qwen-lora-seed-43",
    "qwen-lora-seed-44",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.resolve().relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def verify_spec(spec: dict[str, Any]) -> Path:
    path = project_path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(spec["bytes"]) or sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen artifact drift: {spec['path']}")
    return path


def tree_artifact(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
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
        "path": str(root.resolve().relative_to(PROJECT_ROOT)),
        "total_bytes": sum(item["bytes"] for item in files),
    }


def stat_test_file_only(spec: dict[str, Any]) -> dict[str, Any]:
    # Do not call open(), read_text(), read_bytes(), or sha256_file() here.
    path = project_path(spec["path"])
    observed = path.stat()
    if not stat.S_ISREG(observed.st_mode) or observed.st_size != int(spec["bytes"]):
        raise ValueError(f"Test file metadata drift: {spec['path']}")
    return {"bytes": observed.st_size, "exists": True, "path": spec["path"]}


def runtime_probe(runtime: dict[str, Any], *, require_mps: bool) -> dict[str, Any]:
    executable = Path(runtime["python_executable"])
    if not executable.is_file():
        raise FileNotFoundError(executable)
    package_names = list(runtime["packages"])
    code = (
        "import importlib.metadata,json,platform;"
        f"names={package_names!r};"
        "result={n:(platform.python_version() if n=='python' else importlib.metadata.version(n)) for n in names};"
        + (
            "import torch;result['mps_available']=bool(torch.backends.mps.is_available());"
            if require_mps
            else ""
        )
        + "print(json.dumps(result,sort_keys=True))"
    )
    completed = subprocess.run(
        [str(executable), "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(completed.stdout)
    packages = {key: observed[key] for key in package_names}
    if packages != runtime["packages"]:
        raise ValueError(f"Runtime package drift: {packages}")
    if require_mps and observed.get("mps_available") is not True:
        raise RuntimeError("Frozen MPS runtime is unavailable")
    return observed


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    contract_path = args.contract.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise FileExistsError("TEST-READY verification is append-only")
    contract = load_json(contract_path)
    if (
        contract.get("contract_id") != "EXP-049-TEST-READY-V1"
        or contract.get("experiment_id") != "EXP-049"
        or contract.get("status") != "Frozen TEST-READY"
        or tuple(contract.get("condition_order", ())) != CONDITIONS
        or contract.get("resource_budget", {}).get("formal_test_units") != 9
        or contract.get("test_policy", {}).get("all_predictions_before_label_open") is not True
        or contract.get("test_policy", {}).get("evaluate_every_unit_once") is not True
        or contract.get("test_policy", {}).get("allow_post_result_tuning") is not False
    ):
        raise ValueError("Unexpected frozen EXP-049 contract")

    checks = []
    implementation = {}
    for name, spec in contract["implementation"].items():
        implementation[name] = artifact(verify_spec(spec))
    checks.append("implementation_and_protocol_hashes")

    authorization_path = verify_spec(contract["authorization"])
    authorization = load_json(authorization_path)
    if (
        authorization.get("authorization_id") != "EXP-049-FROZEN-TEST-AUTH-V1"
        or authorization.get("status") != "Authorized"
        or authorization.get("authorized_split") != "test"
        or tuple(authorization.get("authorized_conditions_in_order", ())) != CONDITIONS
        or authorization.get("authorized_formal_test_units") != 9
        or authorization.get("boundaries", {}).get("all_predictions_before_label_open") is not True
        or authorization.get("boundaries", {}).get("post_result_tuning") is not False
    ):
        raise ValueError("Explicit test authorization is invalid")
    checks.append("explicit_user_authorization")

    for item in contract["upstream_verifications"]:
        path = verify_spec(item["artifact"])
        value = load_json(path)
        if value.get("status") != item["expected_status"]:
            raise ValueError(f"Upstream status drift: {path}")
        for key, expected in item.get("required_fields", {}).items():
            if value.get(key) != expected:
                raise ValueError(f"Upstream test boundary drift: {path}:{key}")
    checks.append("verified_dev_evidence_and_sealed_test_boundary")

    for spec in contract["frozen_sources"].values():
        verify_spec(spec)
    train_spec = contract["data"]["train"]
    train_path = project_path(train_spec["path"])
    if train_path.stat().st_size != int(train_spec["bytes"]) or sha256_file(train_path) != train_spec["sha256"]:
        raise ValueError("Frozen train data drift")
    checks.append("frozen_source_and_train_hashes")

    checkpoint_files = 0
    checkpoint_bytes = 0
    for condition, condition_spec in contract["encoder"]["conditions"].items():
        observed = tree_artifact(project_path(condition_spec["checkpoint"]["path"]))
        if observed != condition_spec["checkpoint"]:
            raise ValueError(f"Encoder checkpoint drift: {condition}")
        checkpoint_files += observed["file_count"]
        checkpoint_bytes += observed["total_bytes"]
    checks.append("three_encoder_checkpoint_trees")

    qwen_manifest = load_json(verify_spec(contract["qwen"]["model_manifest"]))
    model = contract["qwen"]["model"]
    if qwen_manifest.get("repo_id") != model["repo_id"] or qwen_manifest.get("revision") != model["revision"]:
        raise ValueError("Qwen identity drift")
    qwen_root = project_path(model["local_path"])
    for expected in qwen_manifest["mlx_bf16"]["files"]:
        path = qwen_root / expected["path"]
        if path.stat().st_size != expected["bytes"] or sha256_file(path) != expected["sha256"]:
            raise ValueError(f"Qwen model file drift: {expected['path']}")
    for condition, condition_spec in contract["qwen"]["conditions"].items():
        for key in ("adapter", "adapter_config"):
            if condition_spec.get(key) is not None:
                verify_spec(condition_spec[key])
    checks.append("qwen_bf16_model_and_three_adapters")

    encoder_runtime = runtime_probe(contract["encoder"]["runtime"], require_mps=True)
    qwen_runtime = runtime_probe(contract["qwen"]["runtime"], require_mps=False)
    checks.append("frozen_python_environments")

    test_input_metadata = stat_test_file_only(contract["data"]["test_inputs"])
    test_label_metadata = stat_test_file_only(contract["data"]["test_labels"])
    checks.append("test_files_exist_by_metadata_only")

    public_output = project_path(contract["outputs"]["public_dir"])
    private_output = project_path(contract["outputs"]["private_dir"])
    if public_output.exists() or private_output.exists():
        raise FileExistsError("Formal EXP-049 outputs are not empty/absent")
    relative_private = private_output.relative_to(REPO_ROOT)
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(relative_private)],
        cwd=REPO_ROOT,
        check=False,
    ).returncode == 0
    if not ignored:
        raise ValueError("Private EXP-049 output is not gitignored")
    checks.append("empty_outputs_and_private_gitignore")

    unit_test = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(SCRIPT_DIR),
            "-p",
            "test_test_gate.py",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    checks.append("synthetic_unit_tests")

    report = {
        "authorization": artifact(authorization_path),
        "check_count": len(checks),
        "checks": checks,
        "completed_at_utc": utc_now(),
        "condition_order": list(CONDITIONS),
        "contract": artifact(contract_path),
        "encoder_checkpoints": {
            "file_count": checkpoint_files,
            "total_bytes": checkpoint_bytes,
        },
        "experiment_id": "EXP-049",
        "implementation": implementation,
        "outputs_absent": True,
        "private_output_gitignored": True,
        "runtime": {"encoder": encoder_runtime, "qwen": qwen_runtime},
        "status": "Passed",
        "test_input_metadata": test_input_metadata,
        "test_inputs_opened": False,
        "test_label_metadata": test_label_metadata,
        "test_labels_opened": False,
        "unit_test_stdout": unit_test.stdout,
        "verification_id": "EXP-049-TEST-READY-VERIFY-V1",
    }
    write_json(output_path, report)
    print(
        json.dumps(
            {
                "contract_sha256": report["contract"]["sha256"],
                "status": report["status"],
                "test_inputs_opened": False,
                "test_labels_opened": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

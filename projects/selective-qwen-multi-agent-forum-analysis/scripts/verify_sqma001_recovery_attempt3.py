#!/usr/bin/env python3
"""SQMA-001 verification attempt 3 with a narrow M1 cache-metadata allowance."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any


sys.dont_write_bytecode = True

import verify_sqma001_recovery_attempt2 as attempt2  # noqa: E402


base = attempt2.base
REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_CONFIG = PROJECT_ROOT / "configs" / "sqma-001-verification-recovery-attempt-3.json"
ALLOWED_M1_EXTRA_PREFIX = ".cache/huggingface/"
MAX_CACHE_FILE_BYTES = 1048576
MAX_CACHE_TOTAL_BYTES = 10485760
CACHE_EVIDENCE: dict[str, Any] = {}
MARKER_HASHES = {
    ".cache/huggingface/.gitignore": "684888c0ebb17f374298b65ee2807526c066094c701bcc7ebbe1c1095f494fc1",
    ".cache/huggingface/CACHEDIR.TAG": "f6572428f6d5e1575e73a1502895a8731f10757dfbb634909c6e154b849af91d",
}
EXPECTED_AUTHORIZATION = {
    "verification_recovery": True,
    "reuse_sealed_run": True,
    "allow_m1_cache_metadata_only": True,
    "runner_reexecution": False,
    "run_mutation": False,
    "model_loading": False,
    "private_access": False,
    "training": False,
    "agent_calls": False,
    "validation_access": False,
    "test_access": False,
    "network": False,
}


def cache_tolerant_model_probe(archive_root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    global CACHE_EVIDENCE
    expected_keys = {
        "repo_id",
        "revision",
        "manifest_path",
        "manifest_bytes",
        "manifest_sha256",
        "root_path",
        "manifest_inventory_key",
        "file_count",
        "total_bytes",
    }
    base.require(set(spec) == expected_keys, "model asset schema drift")
    manifest_path = base.checked_path(archive_root, spec["manifest_path"])
    base.regular_file(manifest_path, "model manifest")
    base.require(manifest_path.stat().st_size == spec["manifest_bytes"], "model manifest byte drift")
    base.require(base.sha256(manifest_path) == spec["manifest_sha256"], "model manifest hash drift")
    manifest = base.read_json(manifest_path)
    base.require(manifest["repo_id"] == spec["repo_id"] and manifest["revision"] == spec["revision"], "model identity drift")
    if spec["manifest_inventory_key"] == "files":
        files = manifest["files"]
    elif spec["manifest_inventory_key"] == "mlx_bf16.files":
        files = manifest["mlx_bf16"]["files"]
    else:
        raise base.VerificationError("unsupported model inventory key")
    base.require(len(files) == spec["file_count"], "model inventory count drift")
    base.require(sum(int(item["bytes"]) for item in files) == spec["total_bytes"], "model inventory byte drift")
    root = base.checked_path(archive_root, spec["root_path"])
    base.require(root.is_dir() and not root.is_symlink(), "model root invalid")
    expected_names = {item["path"] for item in files}
    actual_names = {str(item.relative_to(root)) for item in root.rglob("*") if item.is_file()}
    missing = expected_names - actual_names
    extras = actual_names - expected_names
    base.require(not missing, "model manifest file missing")
    if spec["repo_id"] == "FacebookAI/roberta-base":
        revision = spec["revision"]
        expected_extras = {
            ".cache/huggingface/.gitignore",
            ".cache/huggingface/CACHEDIR.TAG",
            f".cache/huggingface/trees/{revision}.json",
        }
        for core_name in expected_names:
            expected_extras.add(f".cache/huggingface/download/{core_name}.lock")
            expected_extras.add(f".cache/huggingface/download/{core_name}.metadata")
        base.require(extras == expected_extras, "M1 cache sidecar inventory drift")
        expected_dirs = {
            ".cache",
            ".cache/huggingface",
            ".cache/huggingface/download",
            ".cache/huggingface/trees",
        }
        actual_dirs = {str(item.relative_to(root)) for item in root.rglob("*") if item.is_dir()}
        base.require(actual_dirs == expected_dirs, "M1 cache directory inventory drift")
        total_extra = 0
        inventory = []
        for name in extras:
            path = base.checked_path(root, name)
            base.regular_file(path, "M1 cache metadata")
            base.require(path.stat().st_size <= MAX_CACHE_FILE_BYTES, "M1 cache metadata file too large")
            total_extra += path.stat().st_size
            digest = base.sha256(path)
            inventory.append((name, path.stat().st_size, digest))
            if name in MARKER_HASHES:
                base.require(digest == MARKER_HASHES[name], "M1 cache marker drift")
            elif name.endswith(".lock"):
                base.require(path.stat().st_size == 0, "M1 cache lock must be empty")
            elif name.endswith(".metadata"):
                lines = path.read_text(encoding="utf-8").splitlines()
                base.require(len(lines) == 3 and lines[0] == revision, "M1 metadata structure drift")
                base.require(re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", lines[1]) is not None, "M1 metadata identity drift")
                try:
                    timestamp = float(lines[2])
                except ValueError as exc:
                    raise base.VerificationError("M1 metadata timestamp drift") from exc
                base.require(math.isfinite(timestamp) and timestamp >= 0, "M1 metadata timestamp drift")
            elif name == f".cache/huggingface/trees/{revision}.json":
                base.require(path.stat().st_size <= 65536, "M1 cache tree too large")
                tree = base.read_json(path)
                base.require(tree.get("format_version") == 1 and isinstance(tree.get("files"), dict), "M1 cache tree schema drift")
            else:
                raise base.VerificationError("unclassified M1 cache sidecar")
        base.require(total_extra <= MAX_CACHE_TOTAL_BYTES, "M1 cache metadata total too large")
        encoded = json.dumps(sorted(inventory), separators=(",", ":")).encode("utf-8")
        CACHE_EVIDENCE = {
            "count": len(inventory),
            "total_bytes": total_extra,
            "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
            "load_bearing": False,
        }
    else:
        base.require(not extras, "unexpected model extra file")
    for item in files:
        path = base.checked_path(root, item["path"])
        base.regular_file(path, "model file")
        base.require(path.stat().st_size == item["bytes"] and base.sha256(path) == item["sha256"], "model file drift")
    return {
        "repo_id": spec["repo_id"],
        "revision": spec["revision"],
        "manifest_sha256": spec["manifest_sha256"],
        "file_count": len(files),
        "total_bytes": spec["total_bytes"],
        "all_file_hashes_verified": True,
        "framework_imported": False,
    }


def validate_config(path: Path) -> dict[str, Any]:
    value = base.read_json(path)
    base.require(
        set(value)
        == {
            "schema_version",
            "verification_attempt",
            "authorization",
            "base_config",
            "sealed_run",
            "prior_failures",
            "failed_verifier",
            "attempt2_recovery_config",
            "attempt2_recovery_verifier",
            "recovery_verifier",
            "cache_policy",
        },
        "attempt-3 config schema drift",
    )
    base.require(value["schema_version"] == "sqma-001-verification-recovery-v2", "recovery schema drift")
    base.require(value["verification_attempt"] == 3, "verification attempt drift")
    base.require(value["authorization"] == EXPECTED_AUTHORIZATION, "authorization drift")
    for key in (
        "base_config",
        "sealed_run",
        "failed_verifier",
        "attempt2_recovery_config",
        "attempt2_recovery_verifier",
        "recovery_verifier",
    ):
        base.verify_record(value[key])
    base.require(isinstance(value["prior_failures"], list) and len(value["prior_failures"]) == 2, "prior failure list drift")
    for record in value["prior_failures"]:
        base.verify_record(record)
    base.require(
        value["cache_policy"]
        == {
            "allowed_repo_id": "FacebookAI/roberta-base",
            "allowed_prefix": ALLOWED_M1_EXTRA_PREFIX,
            "inventory_rule": "exact_markers_plus_core_lock_metadata_plus_revision_tree",
            "maximum_file_bytes": MAX_CACHE_FILE_BYTES,
            "maximum_total_bytes": MAX_CACHE_TOTAL_BYTES,
            "regular_non_symlink_required": True,
            "empty_lock_required": True,
            "metadata_three_line_structure_required": True,
            "revision_tree_format_version": 1,
            "manifest_files_still_hash_required": True,
            "m3_extra_files_allowed": 0,
        },
        "cache policy drift",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    supplied = Path(args.config).resolve()
    base.require(supplied == RECOVERY_CONFIG.resolve(), "noncanonical recovery config")
    recovery = validate_config(supplied)
    base_config_path = base.checked_path(REPO_ROOT, recovery["base_config"]["path"])
    sealed_run_path = base.checked_path(REPO_ROOT, recovery["sealed_run"]["path"])
    base.require(base.artifact(base_config_path) == recovery["base_config"], "base config drift")
    base.require(base.artifact(sealed_run_path) == recovery["sealed_run"], "sealed run drift")

    base.load_contract = attempt2.fixed_load_contract
    base.model_probe = cache_tolerant_model_probe
    verification, complete = base.verify(base_config_path)
    verification["verification_attempt"] = 3
    verification["recovery_config"] = base.artifact(supplied)
    verification["prior_failures"] = recovery["prior_failures"]
    verification["runner_reexecuted"] = False
    verification["run_mutated"] = False
    verification["m1_extra_file_policy"] = recovery["cache_policy"]
    verification["m1_cache_sidecar_evidence"] = CACHE_EVIDENCE
    complete["verification_attempt"] = 3
    complete["recovery_config"] = base.artifact(supplied)
    complete["prior_failures"] = recovery["prior_failures"]
    complete["runner_reexecuted"] = False
    complete["run_mutated"] = False

    base_config = base.read_json(base_config_path)
    attempt = base.output_dir(base_config)
    base.atomic_json(attempt / "verification.json", verification)
    complete["verification"] = base.artifact(attempt / "verification.json")
    complete.pop("verification_pending_artifact")
    base.atomic_json(attempt / "complete.json", complete)
    base.require(
        sum(item.stat().st_size for item in attempt.iterdir())
        <= base_config["resources"]["maximum_public_output_bytes"],
        "total output budget exceeded",
    )
    print(
        json.dumps(
            {
                "status": "Passed",
                "experiment_id": "SQMA-001",
                "verification_attempt": 3,
                "sqma001_complete": True,
                "runner_reexecuted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, base.VerificationError) as exc:
        print(f"SQMA-001 verification recovery attempt 3 Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Independently verify the EXP-052 feature-cache reuse gate."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Sequence

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
ALLOWED_SPLITS = ("train", "validation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise ValueError(f"Path escapes project root: {recorded}")
    return resolved


def verify_artifact(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"Byte-size drift: {path}")
    if sha256_file(path) != record["sha256"]:
        raise ValueError(f"Hash drift: {path}")
    return path


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_split_rows(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ALLOWED_SPLITS:
        raise PermissionError(f"Reuse verifier cannot access split: {split}")
    path = resolve_project(shared["data"][f"{split}_path"])
    if sha256_file(path) != shared["data"][f"{split}_sha256"]:
        raise ValueError(f"{split} hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != int(shared["data"][f"{split}_rows"]):
        raise ValueError(f"{split} row-count drift")
    return rows


def gitignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False
    )
    return result.returncode == 0


def source_access_audit(path: Path) -> dict[str, bool]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    audited_source = "\n".join(
        ast.get_source_segment(source, node) or ""
        for node in tree.body
        if not (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "source_access_audit"
        )
    )
    loader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_split_rows"
    )
    loader_source = ast.get_source_segment(source, loader) or ""
    return {
        "explicit_train_validation_allowlist": 'ALLOWED_SPLITS = ("train", "validation")' in source,
        "no_test_path_lookup": "test_path" not in loader_source,
        "no_recursive_data_access": all(
            token not in loader_source for token in (".glob(", ".rglob(", "os.walk(")
        ),
        "no_training_entrypoint": all(
            token not in audited_source
            for token in ("optimizer.update(", "loss_and_grad", "model.train(")
        ),
        "read_only_memmap": 'mmap_mode="r"' in audited_source,
    }


def public_privacy_check(
    run_dir: Path, rows: Sequence[dict[str, Any]]
) -> tuple[bool, bool]:
    public_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in run_dir.rglob("*")
        if path.is_file() and path.suffix not in (".npy", ".npz", ".safetensors")
    )
    no_text = all(row["text"] not in public_text for row in rows if len(row["text"]) >= 24)
    no_ids = all(
        row["sample_id"] not in public_text and row["component_id"] not in public_text
        for row in rows
    )
    return no_text, no_ids


def render_summary(verification: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# EXP-052 Feature-cache Reuse Gate Verification",
            "",
            f"- Status: `{verification['status']}`",
            f"- Checks: `{verification['check_count']}/{verification['check_count']}`",
            "- Source cache: verified EXP-052 seed 42 train/validation",
            "- Consumer training authorized: no",
            "- Performance metrics computed: no",
            "- Test accessed: no",
            "- Allowed future consumers after separate authorization: EXP-052 seeds 43/44 only",
            "",
        ]
    )


def verify() -> dict[str, Any]:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != "EXP-052" or config.get("stage") != "feature-cache-reuse-integrity-gate":
        raise PermissionError("Unexpected feature-cache gate contract")
    run_dir = (args.run_dir or resolve_project(config["execution"]["public_run_dir"])).resolve()
    output = run_dir / "verification.json"
    summary_path = run_dir / "VERIFICATION-SUMMARY.md"
    if output.exists() or summary_path.exists():
        raise FileExistsError("Refusing to overwrite append-only gate verification")
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    check("run completed", run.get("status") == "Completed")
    check("experiment identity", run.get("experiment_id") == "EXP-052")
    check("stage identity", run.get("stage") == config["stage"])
    check("test sealed", run.get("test_split_accessed") is False and config["authorization"]["test_access"] is False)
    check("train validation only", run.get("accessed_splits") == ["train", "validation"])
    check("no training", run.get("training_performed") is False and config["authorization"]["training_authorized"] is False)
    check("no performance metrics", run.get("performance_metrics_computed") is False and config["authorization"]["performance_metrics_authorized"] is False)
    check("no Qwen forward", run.get("qwen_forward_executed") is False)
    check("consumer seeds not authorized", config["authorization"]["consumer_seeds_authorized"] is False)
    check("M3 and M4 sealed", config["authorization"]["exp_053_054_authorized"] is False)

    if run.get("status") != "Completed":
        failed = [item["name"] for item in checks if not item["passed"]]
        verification = {
            "schema_version": "exp-052-feature-cache-reuse-verification-v1",
            "experiment_id": "EXP-052",
            "stage": config["stage"],
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "Failed",
            "check_count": len(checks),
            "failed_checks": failed,
            "checks": checks,
            "test_split_accessed": run.get("test_split_accessed"),
        }
        atomic_json(output, verification)
        summary_path.write_text(render_summary(verification), encoding="utf-8")
        raise ValueError(f"Cache gate did not complete: {failed}")

    frozen = run["artifacts"]["frozen_sources"]
    for record in frozen.values():
        verify_artifact(record)
    check("config matches frozen config", sha256_file(config_path) == frozen["config"]["sha256"])
    for name, record in config["implementation"].items():
        source_path = resolve_project(record["path"])
        check(f"implementation hash: {name}", sha256_file(source_path) == record["sha256"])
        check(f"frozen implementation: {name}", frozen[name]["sha256"] == record["sha256"])
    for name, passed in source_access_audit(run_dir / "frozen-runner.py").items():
        check(f"runner source audit: {name}", passed)
    for name, passed in source_access_audit(run_dir / "frozen-verifier.py").items():
        check(f"verifier source audit: {name}", passed)

    shared_path = verify_artifact(config["shared_contract"])
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    check("shared split allowlist", shared["data"]["model_access_whitelist"] == ["train", "validation"])
    check("shared test status", shared["data"]["test_status"] == "sealed_not_authorized_for_model_access")

    source_run_path = verify_artifact(config["source_seed_42"]["run"])
    source_verification_path = verify_artifact(config["source_seed_42"]["verification"])
    source_manifest_path = verify_artifact(config["source_seed_42"]["private_manifest"])
    source_run = json.loads(source_run_path.read_text(encoding="utf-8"))
    source_verification = json.loads(source_verification_path.read_text(encoding="utf-8"))
    check("source seed-42 identity", source_run["experiment_id"] == "EXP-052" and source_run["seed"] == 42)
    check("source seed-42 completed", source_run["status"] == "Completed")
    check("source seed-42 test sealed", source_run["test_split_accessed"] is False)
    check("source verification passed", source_verification["status"] == "Passed" and not source_verification["failed_checks"])
    check("source verification count", source_verification["check_count"] == 70)
    check("source verifier test sealed", source_verification["test_split_accessed"] is False)
    check("source manifest provenance", run["source_seed_42"]["private_manifest"]["sha256"] == sha256_file(source_manifest_path))

    rows_for_privacy: list[dict[str, Any]] = []
    for split in ALLOWED_SPLITS:
        rows = load_split_rows(shared, split)
        rows_for_privacy.extend(rows)
        expected = config["feature_cache"][split]
        source_metadata = source_run["feature_cache"][split]
        source_artifact = source_run["artifacts"][f"{split}_features_private"]
        check(f"{split} source artifact identity", expected["artifact"] == source_artifact == source_metadata["feature"])
        cache_path = verify_artifact(expected["artifact"])
        array = np.load(cache_path, mmap_mode="r", allow_pickle=False)
        check(f"{split} shape", tuple(array.shape) == tuple(expected["shape"]), list(array.shape))
        check(f"{split} dtype", array.dtype == np.float32, str(array.dtype))
        check(f"{split} finite", np.isfinite(array).all())
        check(f"{split} read-only mmap", array.flags.writeable is False)
        check(f"{split} Git ignored", gitignored(cache_path))
        order_digest = canonical_digest([row["sample_id"] for row in rows])
        check(f"{split} sample order", order_digest == expected["sample_order_sha256"] == source_metadata["sample_order_sha256"])
        check(f"{split} token stream", expected["token_id_stream_sha256"] == source_metadata["token_id_stream_sha256"])
        recorded = run["feature_cache"][split]
        check(f"{split} gate artifact", recorded["sha256"] == expected["artifact"]["sha256"])
        check(f"{split} gate shape and dtype", recorded["shape"] == expected["shape"] and recorded["dtype"] == "float32")
        check(f"{split} gate no labels", recorded["gold_labels_used_for_features"] is False)
        del array

    frozen_contract = run["frozen_contract"]
    check("model revision frozen", frozen_contract["model_revision"] == shared["models"]["qwen_shared"]["revision"])
    check("model manifest frozen", frozen_contract["model_manifest_sha256"] == shared["models"]["qwen_shared"]["manifest_sha256"])
    check("prompt frozen", frozen_contract["prompt_sha256"] == shared["prompt"]["sha256"])
    check("thinking disabled", frozen_contract["enable_thinking"] is False)
    check("pooling frozen", frozen_contract["pooling"] == shared["prompt"]["pooling"])
    check("consumer list", run["consumer_contract"]["candidate_seeds"] == [43, 44])
    check("consumer training still sealed", run["consumer_contract"]["training_authorized_by_this_gate"] is False)
    check("M3 M4 reuse forbidden", all(name in run["consumer_contract"]["forbidden_consumers"] for name in ("EXP-053", "EXP-054", "test")))
    check("report artifact", verify_artifact(run["artifacts"]["report"]).is_file())

    no_text, no_ids = public_privacy_check(run_dir, rows_for_privacy)
    check("public artifacts contain no substantive raw text", no_text)
    check("public artifacts contain no row identifiers", no_ids)
    check("finite wall time", math.isfinite(run["resource_usage"]["wall_seconds"]))
    check("zero API cost", run["resource_usage"]["api_cost_usd"] == 0)
    check("test remains sealed after verification", run["test_split_accessed"] is False)

    failed = [item["name"] for item in checks if not item["passed"]]
    verification = {
        "schema_version": "exp-052-feature-cache-reuse-verification-v1",
        "experiment_id": "EXP-052",
        "stage": config["stage"],
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "Passed" if not failed else "Failed",
        "check_count": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "test_split_accessed": False,
    }
    atomic_json(output, verification)
    summary_path.write_text(render_summary(verification), encoding="utf-8")
    if failed:
        raise ValueError(f"EXP-052 cache reuse verification failed: {failed}")
    return verification


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))

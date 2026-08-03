#!/usr/bin/env python3
"""Independently verify EXP-027 synthetic frozen-probe smoke artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(condition: bool, message: str, checks: list[dict[str, Any]]) -> None:
    checks.append({"message": message, "passed": bool(condition)})


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError(f"Refusing to overwrite: {verification_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    check(config["experiment_id"] == "EXP-027", "config identity is EXP-027", checks)
    check(run["experiment_id"] == "EXP-027", "run identity is EXP-027", checks)
    check(config["tier"] == "Minor" and run["tier"] == "Minor", "tier is Minor", checks)
    check(run["config_sha256"] == sha256(config_path), "config hash matches", checks)
    check(run["status"] == "completed", "runner completed", checks)
    check(run["accessed_splits"] == [], "no project split was accessed", checks)
    check(run["project_rows_accessed"] == 0, "zero project rows were accessed", checks)
    check(not run["validation_split_accessed"], "validation was not accessed", checks)
    check(not run["test_split_accessed"], "test was not accessed", checks)
    check(run["test_absent_before_run"] and run["test_absent_after_run"], "test was absent throughout", checks)
    check(
        not (PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv").exists(),
        "test remains absent during verification",
        checks,
    )
    check(run["synthetic_text_count"] == 6, "six synthetic texts were used", checks)
    check(not run["synthetic_text_stored_in_run"], "run does not retain synthetic text", checks)

    condition_reports = {item["condition"]: item for item in run["conditions"]}
    check(set(condition_reports) == {"base", "post-trained"}, "both matched conditions exist", checks)
    expected_tokenizer_hash = config["tokenizer"]["asset_sha256"]
    for spec in config["models"]:
        condition = spec["condition"]
        report = condition_reports.get(condition, {})
        manifest_path = PROJECT_ROOT / spec["manifest_path"]
        tokenizer_path = PROJECT_ROOT / spec["local_path"] / config["tokenizer"]["asset"]
        check(sha256(manifest_path) == spec["manifest_sha256"], f"{condition} manifest hash matches", checks)
        check(sha256(tokenizer_path) == expected_tokenizer_hash, f"{condition} tokenizer hash matches", checks)
        check(report.get("finite") is True, f"{condition} features are finite", checks)
        check(report.get("feature_shape") == [6, 2048], f"{condition} feature shape is 6 x 2048", checks)
        check(report.get("feature_dtype") == "float32", f"{condition} feature dtype is float32", checks)
        check(report.get("hidden_size") == 2048, f"{condition} hidden size matches", checks)
        check(report.get("num_hidden_layers") == 28, f"{condition} layer count matches", checks)
        check(report.get("peak_mlx_memory_gb", float("inf")) <= config["resource_budget"]["peak_mlx_memory_gb_max"], f"{condition} peak memory is within budget", checks)
        check(report.get("norm_min", 0.0) > 0.0, f"{condition} pooled vectors are nonzero", checks)

    base = condition_reports.get("base", {})
    post_trained = condition_reports.get("post-trained", {})
    check(
        base.get("token_id_digest_sha256") == post_trained.get("token_id_digest_sha256"),
        "Base and post-trained token IDs are identical",
        checks,
    )
    check(
        base.get("feature_digest_sha256") != post_trained.get("feature_digest_sha256"),
        "Base and post-trained feature digests differ",
        checks,
    )
    diagnostics = run["paired_diagnostics"]
    check(
        all(math.isfinite(float(value)) for value in diagnostics.values()),
        "paired diagnostics are finite",
        checks,
    )
    check(diagnostics["l2_difference_min"] > 0.0, "every paired vector differs", checks)
    check(
        run["total_seconds"] <= config["resource_budget"]["wall_time_minutes_max"] * 60,
        "runtime is within budget",
        checks,
    )

    failures = [item["message"] for item in checks if not item["passed"]]
    verification = {
        "checks": checks,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-027",
        "failed_checks": failures,
        "run_json_sha256": sha256(run_dir / "run.json"),
        "status": "Passed" if not failures else "Failed",
        "verifier_sha256": sha256(Path(__file__).resolve()),
    }
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"failed_checks": failures, "status": verification["status"]}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

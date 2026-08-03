#!/usr/bin/env python3
"""Validate the EXP-028 freeze before any formal train/dev access."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(checks: list[dict[str, Any]], condition: bool, message: str) -> None:
    checks.append({"message": message, "passed": bool(condition)})


def environment_versions(python: Path, packages: list[str]) -> dict[str, str]:
    code = (
        "import importlib.metadata as m, json; "
        f"print(json.dumps({{name: m.version(name) for name in {packages!r}}}, sort_keys=True))"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout.strip())


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    protocol_path = args.protocol.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite preflight artifact: {output_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    check(checks, config.get("experiment_id") == "EXP-028", "config identity is EXP-028")
    check(checks, config.get("tier") == "Major", "config tier is Major")
    check(checks, protocol_path.is_file(), "Major protocol exists")
    check(checks, not config["test_gate"]["authorized"], "test access is not authorized")

    test_path = PROJECT_ROOT / config["data"]["test_path"]
    run_dir = PROJECT_ROOT / config["paths"]["formal_run_dir"]
    cache_root = PROJECT_ROOT / config["paths"]["private_cache_root"]
    check(checks, not test_path.exists(), "GoEmotions test is absent")
    check(checks, not run_dir.exists(), "formal output directory is absent")
    check(checks, not cache_root.exists(), "private feature cache is absent")
    gitignore_path = SCRIPT_DIR / ".gitignore"
    check(
        checks,
        "private-cache/" in gitignore_path.read_text(encoding="utf-8").splitlines(),
        "private feature cache is gitignored",
    )

    for split, spec in config["data"]["splits"].items():
        path = PROJECT_ROOT / spec["path"]
        check(checks, path.is_file(), f"{split} split exists")
        check(checks, sha256(path) == spec["sha256"], f"{split} split hash matches")
    labels_path = PROJECT_ROOT / config["data"]["labels_path"]
    check(checks, sha256(labels_path) == config["data"]["labels_sha256"], "label ontology hash matches")
    check(
        checks,
        len(labels_path.read_text(encoding="utf-8").splitlines()) == config["data"]["label_count"],
        "label ontology contains 28 labels",
    )

    for spec in config["models"]:
        condition = spec["condition"]
        manifest_path = PROJECT_ROOT / spec["manifest_path"]
        tokenizer_path = PROJECT_ROOT / spec["local_path"] / config["tokenizer"]["asset"]
        check(checks, sha256(manifest_path) == spec["manifest_sha256"], f"{condition} manifest hash matches")
        check(checks, sha256(tokenizer_path) == config["tokenizer"]["asset_sha256"], f"{condition} tokenizer hash matches")

    for name in ("extractor", "fitter", "verifier"):
        path = PROJECT_ROOT / config["implementation"][f"{name}_path"]
        expected = config["implementation"][f"{name}_sha256"]
        check(checks, sha256(path) == expected, f"{name} implementation hash matches")

    parent_path = PROJECT_ROOT / config["preflight_parent"]["verification_path"]
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    check(checks, sha256(parent_path) == config["preflight_parent"]["verification_sha256"], "EXP-027 verification hash matches")
    check(checks, parent.get("status") == "Passed", "EXP-027 synthetic representation smoke passed")
    check(checks, parent.get("experiment_id") == "EXP-027", "EXP-027 parent identity matches")

    extractor_python = Path(config["environment"]["extractor_python"])
    probe_python = Path(config["environment"]["probe_python"])
    check(checks, extractor_python.is_file(), "MLX extractor Python exists")
    check(checks, probe_python.is_file(), "probe Python exists")
    actual_extractor_versions = environment_versions(
        extractor_python,
        ["mlx", "mlx-lm", "numpy", "transformers"],
    )
    actual_probe_versions = environment_versions(
        probe_python,
        ["numpy", "scikit-learn", "scipy"],
    )
    check(
        checks,
        actual_extractor_versions == config["environment"]["extractor_versions"],
        "MLX extractor package versions match",
    )
    check(
        checks,
        actual_probe_versions == config["environment"]["probe_versions"],
        "probe package versions match",
    )

    failures = [item["message"] for item in checks if not item["passed"]]
    report = {
        "accessed_splits": [],
        "checks": checks,
        "config_path": str(config_path.relative_to(PROJECT_ROOT)),
        "config_sha256": sha256(config_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "extractor": actual_extractor_versions,
            "probe": actual_probe_versions,
        },
        "experiment_id": "EXP-028",
        "failed_checks": failures,
        "preflight_sha256": sha256(Path(__file__).resolve()),
        "protocol_path": str(protocol_path.relative_to(PROJECT_ROOT)),
        "protocol_sha256": sha256(protocol_path),
        "status": "Passed" if not failures else "Failed",
        "test_absent": not test_path.exists(),
        "test_split_accessed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"failed_checks": failures, "status": report["status"]}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

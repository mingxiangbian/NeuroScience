#!/usr/bin/env python3
"""Verify completed EXP-056 outputs without reopening the sealed label source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from test_gate_common import (
    LABELS,
    aggregate_values,
    artifact,
    atomic_json,
    load_json,
    metric_bundle,
    require_artifact,
    resolve_project,
    sha256_file,
    utc_now,
    verify_authorization,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_DIR / "configs" / "exp-056-test-ready.json"


def verify(contract_path: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    public = resolve_project(contract["execution"]["public_output_dir"])
    authorization_path = resolve_project(contract["execution"]["authorization"]["path"])
    verify_authorization(contract, authorization_path)
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    seal_path = public / "prediction-seal.json"
    results_path = public / "results.json"
    state_path = public / "state.json"
    seal = load_json(seal_path)
    results = load_json(results_path)
    state = load_json(state_path)
    check("contract_hash", results.get("contract_sha256") == sha256_file(contract_path))
    check("prediction_seal_status", seal.get("status") == "Predictions sealed before labels opened")
    check("prediction_seal_scope", seal.get("unit_ids") == contract["unit_order"])
    check("results_status", results.get("status") == "Completed")
    check("state_status", state.get("labels_opened") is True and state.get("prediction_seal_created") is True)
    check("label_open_order", results.get("labels_opened_after_prediction_seal") is True)
    check("frozen_score_input", require_artifact(results["private_score_input"]).is_file())
    check("unit_scope", list(results.get("unit_results", {})) == contract["unit_order"])
    check("family_scope", list(results.get("family_results", {})) == ["m1", "m2", "m3", "m4"])

    evidence_path = require_artifact(results["private_score_evidence"])
    with np.load(evidence_path, allow_pickle=False) as source:
        evidence = {name: source[name] for name in source.files}
    gold = evidence["gold"]
    check("gold_shape", gold.shape == (contract["data"]["test_rows"], len(LABELS)))
    for unit_id in contract["unit_order"]:
        predicted = evidence[f"pred__{unit_id.replace('-', '_')}"]
        recomputed = metric_bundle(gold, predicted)
        check(
            f"metrics:{unit_id}",
            recomputed == results["unit_results"][unit_id]["metrics"],
        )

    for family in ("m1", "m2", "m3", "m4"):
        ids = [f"{family}-seed-{seed}" for seed in (42, 43, 44)]
        expected = aggregate_values([
            results["unit_results"][unit_id]["metrics"]["macro_f1"] for unit_id in ids
        ])
        check(
            f"aggregate:{family}:macro_f1",
            expected == results["family_results"][family]["metrics"]["macro_f1"],
        )

    check("bootstrap_evidence", require_artifact(results["private_bootstrap_replicates"]).is_file())
    check("no_post_test_selection", results.get("selection_or_tuning_after_test") is False)
    public_text = "\n".join(
        path.read_text(encoding="utf-8") for path in public.rglob("*.json") if path.is_file()
    )
    check("no_public_raw_text_field", '"raw_output"' not in public_text and '"text"' not in public_text)
    failed = [row["name"] for row in checks if not row["passed"]]
    report = {
        "schema_version": "exp-056-frozen-test-verification-v1",
        "experiment_id": "EXP-056", "verified_at_utc": utc_now(),
        "status": "Passed" if not failed else "Failed",
        "results": artifact(results_path), "prediction_seal": artifact(seal_path),
        "checks": checks, "failed_checks": failed,
        "sealed_test_label_source_reopened_by_verifier": False,
    }
    atomic_json(public / "verification.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    report = verify(args.contract.resolve())
    print(json.dumps({"status": report["status"], "failed_checks": report["failed_checks"]}, indent=2))
    raise SystemExit(0 if report["status"] == "Passed" else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the immutable-until-authorized EXP-056 TEST-READY contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from test_gate_common import (
    LABELS,
    PROJECT_ROOT,
    artifact,
    atomic_json,
    load_json,
    require_artifact,
    require_tree,
    resolve_project,
    utc_now,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "configs" / "exp-056-test-ready.json"
AUTHORIZATION = (
    "experiments/stack-overflow-emotion-gold/test-gate/protocols/"
    "exp-056-test-authorization-v1.json"
)
PUBLIC_OUTPUT = (
    "experiments/stack-overflow-emotion-gold/test-gate/runs/"
    "exp-056-frozen-test"
)
PRIVATE_OUTPUT = (
    "data/stack-overflow-emotion-gold/derived-private/task-v1/experiments/"
    "exp-056-frozen-test"
)


def source_run(path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    record = artifact(resolve_project(path))
    run = load_json(require_artifact(record))
    if run.get("status") != "Completed" or run.get("test_split_accessed") is not False:
        raise ValueError(f"Source run is not validation-complete and test-sealed: {path}")
    return record, run


def m1_units() -> list[dict[str, Any]]:
    roots = {
        42: "exp-051-m1-roberta-cpu-recovery",
        43: "exp-051-m1-roberta-cpu",
        44: "exp-051-m1-roberta-cpu",
    }
    units = []
    for seed in (42, 43, 44):
        run_path = (
            "experiments/stack-overflow-emotion-gold/model-comparison/runs/"
            f"{roots[seed]}/seed-{seed}/run.json"
        )
        run_record, run = source_run(run_path)
        checkpoint = run["artifacts"]["selected_checkpoint_private"]
        require_tree(checkpoint)
        units.append({
            "unit_id": f"m1-seed-{seed}",
            "family": "m1",
            "seed": seed,
            "source_experiment_id": "EXP-051",
            "source_run": run_record,
            "selected_epoch": int(run["selection"]["selected_epoch"]),
            "shared_threshold": float(run["threshold_selection"]["selected_threshold"]),
            "selected_checkpoint": checkpoint,
            "prediction_mode": "roberta_six_independent_logits",
        })
    return units


def m2_units() -> list[dict[str, Any]]:
    units = []
    for seed in (42, 43, 44):
        run_path = (
            "experiments/stack-overflow-emotion-gold/model-comparison/runs/"
            f"exp-052-m2-frozen-qwen/seed-{seed}/run.json"
        )
        run_record, run = source_run(run_path)
        head = run["artifacts"]["selected_head_private"]
        require_artifact(head)
        units.append({
            "unit_id": f"m2-seed-{seed}",
            "family": "m2",
            "seed": seed,
            "source_experiment_id": "EXP-052",
            "source_run": run_record,
            "selected_epoch": int(run["selection"]["selected_epoch"]),
            "shared_threshold": float(run["threshold_selection"]["selected_threshold"]),
            "selected_head": head,
            "prediction_mode": "frozen_qwen_final_input_state_linear_head",
        })
    return units


def m3_units() -> list[dict[str, Any]]:
    units = []
    for seed in (42, 43, 44):
        run_path = (
            "experiments/stack-overflow-emotion-gold/model-comparison/runs/"
            f"exp-053-m3-classification-lora/seed-{seed}/run.json"
        )
        run_record, run = source_run(run_path)
        selected = run["artifacts"]["selected_checkpoint_private"]
        require_artifact(selected["adapter"])
        require_artifact(selected["head"])
        units.append({
            "unit_id": f"m3-seed-{seed}",
            "family": "m3",
            "seed": seed,
            "source_experiment_id": "EXP-053",
            "source_run": run_record,
            "selected_epoch": int(run["selection"]["selected_epoch"]),
            "shared_threshold": float(run["threshold_selection"]["selected_threshold"]),
            "selected_adapter": selected["adapter"],
            "selected_head": selected["head"],
            "expected_lora_initial_sha256": run["model"]["lora_initial_sha256"],
            "prediction_mode": "qwen_classification_lora_and_linear_head",
        })
    return units


def m4_units() -> list[dict[str, Any]]:
    units = []
    for seed in (42, 43, 44):
        run_path = (
            "experiments/stack-overflow-emotion-gold/model-comparison/runs/"
            f"exp-054-m4-generative-lora/seed-{seed}/run.json"
        )
        run_record, run = source_run(run_path)
        adapter = run["artifacts"]["selected_adapter_private"]
        require_artifact(adapter)
        units.append({
            "unit_id": f"m4-seed-{seed}",
            "family": "m4",
            "seed": seed,
            "source_experiment_id": "EXP-054",
            "source_run": run_record,
            "selected_epoch": int(run["selection"]["selected_epoch"]),
            "shared_threshold": None,
            "selected_adapter": adapter,
            "expected_lora_initial_sha256": run["model"]["lora_initial_sha256"],
            "prediction_mode": "qwen_generative_lora_strict_json_parser",
        })
    return units


def upstream() -> dict[str, Any]:
    roots = {
        "m1": "exp-051-m1-roberta-three-seed-validation",
        "m2": "exp-052-m2-frozen-qwen-three-seed-validation",
        "m3": "exp-053-m3-classification-lora-three-seed-validation",
        "m4": "exp-054-m4-generative-lora-three-seed-validation",
    }
    records: dict[str, Any] = {}
    for family, root in roots.items():
        base = (
            "experiments/stack-overflow-emotion-gold/model-comparison/runs/"
            f"{root}"
        )
        aggregate = artifact(resolve_project(f"{base}/aggregate.json"))
        verification = artifact(resolve_project(f"{base}/verification.json"))
        if load_json(require_artifact(verification)).get("status") != "Passed":
            raise ValueError(f"Upstream aggregate verification did not pass: {family}")
        records[family] = {"aggregate": aggregate, "verification": verification}
    exp055 = artifact(resolve_project(
        "experiments/stack-overflow-emotion-gold/error-analysis/runs/"
        "exp-055-m1-m3-validation-error-analysis/verification-attempt-2.json"
    ))
    if load_json(require_artifact(exp055)).get("status") != "Passed":
        raise ValueError("EXP-055 verification did not pass")
    records["exp055_validation_error_analysis"] = {
        "verification": exp055,
        "test_scope": "excluded_non_deployable_oracle_and_no_oof_router_gate",
    }
    return records


def implementation() -> dict[str, Any]:
    paths = {
        "builder": SCRIPT_DIR / "build_test_ready_contract.py",
        "common": SCRIPT_DIR / "test_gate_common.py",
        "runner": SCRIPT_DIR / "run_frozen_test.py",
        "readiness_verifier": SCRIPT_DIR / "verify_test_ready.py",
        "final_verifier": SCRIPT_DIR / "verify_frozen_test.py",
        "tests": SCRIPT_DIR / "tests" / "test_test_gate.py",
        "protocol": SCRIPT_DIR / "protocols" / "exp-056-unified-frozen-test-gate.md",
        "shared_config": resolve_project(
            "experiments/stack-overflow-emotion-gold/model-comparison/config.json"
        ),
        "prompt": resolve_project(
            "experiments/stack-overflow-emotion-gold/model-comparison/prompt-v1.json"
        ),
        "parser": resolve_project(
            "experiments/stack-overflow-emotion-gold/model-comparison/strict_multilabel_parser.py"
        ),
        "qwen_primitives": resolve_project(
            "experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py"
        ),
        "m2_reference": resolve_project(
            "experiments/stack-overflow-emotion-gold/model-comparison/run_exp052_m2.py"
        ),
        "m3_reference": resolve_project(
            "experiments/stack-overflow-emotion-gold/model-comparison/run_exp053_m3.py"
        ),
        "m4_reference": resolve_project(
            "experiments/stack-overflow-emotion-gold/model-comparison/run_exp054_m4.py"
        ),
    }
    return {name: artifact(path) for name, path in paths.items()}


def build(output: Path) -> dict[str, Any]:
    authorization_path = resolve_project(AUTHORIZATION)
    if authorization_path.exists():
        raise FileExistsError("Refusing to rebuild EXP-056 after authorization")
    for path in (resolve_project(PUBLIC_OUTPUT), resolve_project(PRIVATE_OUTPUT)):
        if path.exists():
            raise FileExistsError(f"Formal output already exists: {path}")

    manifest_path = resolve_project("data/stack-overflow-emotion-gold/task-v1.manifest.json")
    manifest_record = artifact(manifest_path)
    manifest = load_json(manifest_path)
    if manifest.get("status") != "verified":
        raise ValueError("DATA-SO-TASK-V1 is not verified")
    test_inputs = manifest["private_artifacts"]["test_inputs"]
    test_labels = manifest["private_artifacts"]["test_labels"]
    # Deliberately use metadata from the public manifest. Do not hash or parse test files here.
    for record in (test_inputs, test_labels):
        path = resolve_project(record["path"])
        if not path.is_file() or path.stat().st_size != int(record["bytes"]):
            raise ValueError(f"Sealed test file metadata drift: {record['path']}")

    units = m1_units() + m2_units() + m3_units() + m4_units()
    unit_order = [unit["unit_id"] for unit in units]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    contract = {
        "schema_version": "exp-056-test-ready-contract-v1",
        "experiment_id": "EXP-056",
        "rq_id": "RQ-S1",
        "tier": "Major",
        "status": "Frozen TEST-READY; test access not authorized",
        "created_at_utc": utc_now(),
        "git_commit_at_freeze": commit,
        "contract_path": str(output.resolve().relative_to(PROJECT_ROOT.resolve())),
        "data": {
            "protocol_id": "DATA-SO-TASK-V1",
            "manifest": manifest_record,
            "test_rows": int(manifest["counts"]["split_rows"]["test"]),
            "test_inputs": test_inputs,
            "test_labels": test_labels,
            "test_status": manifest["test_gate"]["status"],
            "split_contract": "duplicate-component-disjoint multilabel group stratification",
            "test_inputs_opened_during_freeze": False,
            "test_labels_opened_during_freeze": False,
            "freeze_check": "existence_and_byte_count_only_from_public_manifest",
        },
        "labels": list(LABELS),
        "models": {
            "roberta_manifest": artifact(resolve_project("models/roberta-base/manifest.json")),
            "qwen_manifest": artifact(resolve_project("models/qwen3-4b/manifest.json")),
            "roberta_local_path": "models/roberta-base/snapshot",
            "qwen_local_path": "models/qwen3-4b/mlx-bf16",
        },
        "implementation": implementation(),
        "upstream": upstream(),
        "unit_order": unit_order,
        "units": units,
        "evaluation": {
            "primary": "six_label_macro_f1",
            "auxiliary": [
                "five_label_macro_f1_without_surprise", "micro_f1", "weighted_f1",
                "macro_precision", "macro_recall", "strict_subset_accuracy",
                "hamming_loss", "per_label_metrics", "empty_prediction_rate",
                "predicted_label_cardinality_mean", "m4_parser_validity_and_latency",
            ],
            "family_aggregation": "three seeds; mean and sample standard deviation ddof=1",
            "paired_contrasts": ["m2-m1", "m3-m1", "m3-m2", "m4-m1", "m4-m3"],
            "bootstrap": {
                "unit": "duplicate_component_id",
                "replicates": 2000,
                "confidence_interval": "percentile_95",
                "statistics": ["macro_f1", "five_label_macro_f1_without_surprise"],
                "namespace": "EXP-056-component-bootstrap-v1",
            },
            "surprise_test_support": 7,
            "selection_after_test_forbidden": True,
        },
        "execution": {
            "authorization": {
                "path": AUTHORIZATION,
                "present": False,
                "required_schema": "exp-056-test-authorization-v1",
                "scope": "one_time_stack_overflow_test_execution_for_all_12_frozen_units",
            },
            "public_output_dir": PUBLIC_OUTPUT,
            "private_output_dir": PRIVATE_OUTPUT,
            "stages": ["initialize", "predict-family", "seal-predictions", "score"],
            "python": {
                "m1": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
                "m2_m3_m4": "/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python",
            },
            "offline_only": True,
            "api_cost_usd": 0,
            "maximum_total_wall_hours": 12,
            "maximum_mlx_peak_memory_gb": 13,
            "maximum_m4_generation_hours_per_seed": 2,
            "formal_output_dirs_absent_at_freeze": True,
        },
        "claim_boundary": {
            "supports": [
                "held_out_performance_for_exact_frozen_systems",
                "three_seed_stability", "format_reliability", "resource_cost",
            ],
            "does_not_support": [
                "causal_benefit_of_generation", "human_like_emotion_mechanism",
                "deployable_router", "generalization_beyond_this_gold_set",
            ],
        },
    }
    atomic_json(output, contract)
    return contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    contract = build(args.output.resolve())
    print(json.dumps({
        "status": contract["status"],
        "units": len(contract["units"]),
        "output": contract["contract_path"],
        "test_inputs_opened": False,
        "test_labels_opened": False,
    }, indent=2))


if __name__ == "__main__":
    main()

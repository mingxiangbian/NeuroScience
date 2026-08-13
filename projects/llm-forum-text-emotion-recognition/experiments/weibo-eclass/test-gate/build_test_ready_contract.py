#!/usr/bin/env python3
"""Build EXP-049's frozen contract without opening either test file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_gate_common import (
    PROJECT_ROOT,
    artifact,
    atomic_json,
    load_json,
    resolve_project_path,
    sha256_file,
    tree_artifact,
    utc_now,
)


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT = SCRIPT_DIR / "configs" / "exp-049-test-ready.json"
PUBLIC_OUTPUT = SCRIPT_DIR / "runs" / "exp-049-frozen-test"
PRIVATE_OUTPUT = resolve_project_path(
    "data/weibo-emotion-corpus/derived-private/eclass-v1/experiments/exp-049-frozen-test"
)
CONDITION_ORDER = [
    "m0-majority",
    "m1-target-only",
    "encoder-seed-42",
    "encoder-seed-43",
    "encoder-seed-44",
    "qwen-reference",
    "qwen-lora-seed-42",
    "qwen-lora-seed-43",
    "qwen-lora-seed-44",
]
EXPECTED_HASHES = {
    "dataset_manifest": "54e929d7a9263c83d2895fd109fbdfb46b876043dec668d0fe25f30c149fd210",
    "encoder_manifest": "c1629b5349d66f3a873c3d6bc4bc490089b86745941eebfaf70749e1e916cba5",
    "exp042_config": "60e5b2b4b8269d7ab95e6a344e64419a4e4280ebed65affbe08a64ba40bdf8a9",
    "exp042_verification": "a518135c9bbebf4fb9f6fb080f61c3996772d7d45a6077776ce6a4e99f0f9fb7",
    "exp047_contract": "72b9ef256be16e009f8f42231976383394ce75c3a00531e07ba5e2feed51b3b2",
    "exp047_verification": "42da926faa9fd4a18ed8d209d7d30bfd54403e8951e0b6b4bb3bb0aae0df90e9",
    "exp048_verification": "995d9448508b73ffcb1ed4f1c8ee8d48e25d7127891045f5862ffc41eae3f2e3",
    "parser": "429c8708da864086c11859449ebf427b8a681c20eec58900d97574d508067a21",
    "prompt": "d9a92aab3a531b769c3b4794572cf0842536c7c38dcdd6a1cd4ac25885e6631b",
    "qwen_manifest": "da447350d9e43213dacc1202da03b50d7e7114b0a4fe2904ff353240b404a641",
    "stage5_config": "992e42535c7acf6fd503aa870f52825a30a90fd767280bf5ba06f43f69739b15",
    "train": "b1fd309acf45dfa4ad0c907ee3f373ea95fce751d51b637d402e289aa79d19e0",
}


def checked_artifact(relative: str, expected_hash: str | None = None) -> dict[str, Any]:
    value = artifact(resolve_project_path(relative))
    if expected_hash is not None and value["sha256"] != expected_hash:
        raise ValueError(f"Pre-frozen artifact hash drift: {relative}")
    return value


def checked_json(relative: str, expected_hash: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = checked_artifact(relative, expected_hash)
    return load_json(resolve_project_path(relative)), spec


def assert_test_file_metadata_only(spec: dict[str, Any]) -> None:
    # Deliberately use stat only. Opening or hashing either test file is forbidden here.
    path = resolve_project_path(spec["path"])
    observed = path.stat()
    if not path.is_file() or observed.st_size != int(spec["bytes"]):
        raise ValueError(f"Test file metadata drift: {spec['path']}")


def encoder_condition(seed: int) -> dict[str, Any]:
    root_relative = (
        "data/weibo-emotion-corpus/derived-private/eclass-v1/experiments/"
        f"exp-042-stage-3-baselines/m2/target_only/seed-{seed}/final-model"
    )
    run_relative = (
        "experiments/weibo-eclass/stage-3-baselines/runs/exp-042-stage-3-baselines/"
        f"m2/target_only/seed-{seed}/run.json"
    )
    source_run, run_spec = checked_json(run_relative)
    observed_tree = tree_artifact(resolve_project_path(root_relative))
    if observed_tree != source_run["checkpoint"]:
        raise ValueError(f"Encoder checkpoint differs from verified EXP-042 run: seed {seed}")
    return {
        "checkpoint": observed_tree,
        "seed": seed,
        "source_run": run_spec,
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("Frozen EXP-049 contract already exists")
    if PUBLIC_OUTPUT.exists() or PRIVATE_OUTPUT.exists():
        raise FileExistsError("EXP-049 output directories must be absent before contract freeze")

    manifest, manifest_spec = checked_json(
        "data/weibo-emotion-corpus/eclass-v1.manifest.json", EXPECTED_HASHES["dataset_manifest"]
    )
    if (
        manifest.get("protocol_id") != "DATA-WEIBO-TASK-V1"
        or manifest.get("counts", {}).get("split_rows")
        != {"test": 1273, "train": 5995, "validation": 1272}
        or manifest.get("test_gate", {}).get("status") != "sealed_not_authorized_for_model_access"
        or manifest.get("test_gate", {}).get("inputs_contain_gold_labels") is not False
        or manifest.get("test_gate", {}).get("labels_gitignored") is not True
    ):
        raise ValueError("Unexpected public Weibo EClass manifest")
    train_manifest = manifest["private_artifacts"]["train"]
    if train_manifest["sha256"] != EXPECTED_HASHES["train"]:
        raise ValueError("Frozen train hash drift in public manifest")
    test_inputs = {**manifest["private_artifacts"]["test_inputs"], "rows": 1273}
    test_labels = {**manifest["private_artifacts"]["test_labels"], "rows": 1273}
    if (
        test_inputs["sha256"] != "5229637a285179a3626858edc369664d159fe9c99cd7bb03aae8fbc868f4406e"
        or test_labels["sha256"] != "649ce91f58aa7550e76450c25a571f5dbbe3b03c70ba0e9e07fb53c84cdfd002"
    ):
        raise ValueError("Sealed test hashes differ from the registered protocol")
    assert_test_file_metadata_only(test_inputs)
    assert_test_file_metadata_only(test_labels)

    stage3, stage3_spec = checked_json(
        "experiments/weibo-eclass/stage-3-baselines/config.json", EXPECTED_HASHES["exp042_config"]
    )
    matched, matched_spec = checked_json(
        "experiments/weibo-eclass/stage-5-generative-lora/preflight/"
        "exp-047-matched-validation-contract-v1.json",
        EXPECTED_HASHES["exp047_contract"],
    )
    if stage3["m2"]["seeds"] != [42, 43, 44] or matched["condition_order"] != [
        "reference",
        "seed-42",
        "seed-43",
        "seed-44",
    ]:
        raise ValueError("Upstream seed registry drift")

    upstream = [
        {
            "artifact": checked_artifact(
                "experiments/weibo-eclass/stage-3-baselines/runs/"
                "exp-042-stage-3-baselines/verification.json",
                EXPECTED_HASHES["exp042_verification"],
            ),
            "expected_status": "Verified",
            "required_fields": {"test_split_accessed": False},
        },
        {
            "artifact": checked_artifact(
                "experiments/weibo-eclass/stage-5-generative-lora/runs/"
                "exp-047-stage-5-generative-lora/matched-validation-v1/verification.json",
                EXPECTED_HASHES["exp047_verification"],
            ),
            "expected_status": "Passed",
            "required_fields": {"test_split_accessed": False},
        },
        {
            "artifact": checked_artifact(
                "experiments/weibo-eclass/error-analysis/runs/"
                "exp-048-frozen-dev-error-analysis/verification.json",
                EXPECTED_HASHES["exp048_verification"],
            ),
            "expected_status": "Verified",
            "required_fields": {"test_accessed": False},
        },
    ]
    for item in upstream:
        value = load_json(resolve_project_path(item["artifact"]["path"]))
        if value.get("status") != item["expected_status"]:
            raise ValueError("Upstream verification status drift")
        for key, expected in item["required_fields"].items():
            if value.get(key) != expected:
                raise ValueError(f"Upstream test boundary drift: {key}")

    encoder_conditions = {
        f"encoder-seed-{seed}": encoder_condition(seed) for seed in (42, 43, 44)
    }
    qwen_mapping = {
        "qwen-reference": "reference",
        "qwen-lora-seed-42": "seed-42",
        "qwen-lora-seed-43": "seed-43",
        "qwen-lora-seed-44": "seed-44",
    }
    qwen_conditions = {}
    for target, source in qwen_mapping.items():
        source_value = matched["conditions"][source]
        for field in ("adapter", "adapter_config"):
            if source_value.get(field) is not None:
                observed = checked_artifact(source_value[field]["path"])
                if observed != source_value[field]:
                    raise ValueError(f"Frozen adapter drift: {target} {field}")
        qwen_conditions[target] = {
            "adapter": source_value.get("adapter"),
            "adapter_config": source_value.get("adapter_config"),
            "seed": source_value.get("seed"),
        }

    source_paths = {
        "dataset_manifest": "data/weibo-emotion-corpus/eclass-v1.manifest.json",
        "encoder_manifest": "models/chinese-roberta-wwm-ext/manifest.json",
        "encoder_requirements": "experiments/weibo-eclass/stage-3-baselines/requirements-lock.txt",
        "exp042_config": "experiments/weibo-eclass/stage-3-baselines/config.json",
        "exp047_contract": "experiments/weibo-eclass/stage-5-generative-lora/preflight/exp-047-matched-validation-contract-v1.json",
        "exp048_verification": "experiments/weibo-eclass/error-analysis/runs/exp-048-frozen-dev-error-analysis/verification.json",
        "parser": "experiments/weibo-eclass/stage-4-qwen-2x2/label_parser.py",
        "prompt": "experiments/weibo-eclass/stage-2-preflight/prompt-v1.json",
        "qwen_manifest": "models/qwen3-4b/manifest.json",
        "qwen_requirements": "experiments/weibo-eclass/stage-4-qwen-2x2/requirements-lock.txt",
        "stage5_config": "experiments/weibo-eclass/stage-5-generative-lora/config.json",
    }
    frozen_sources = {}
    for name, relative in source_paths.items():
        expected = EXPECTED_HASHES.get(name)
        frozen_sources[name] = checked_artifact(relative, expected)
    if frozen_sources["exp042_config"] != stage3_spec or frozen_sources["exp047_contract"] != matched_spec:
        raise AssertionError("Source artifact reconstruction drift")

    implementation_paths = {
        "builder": "experiments/weibo-eclass/test-gate/build_test_ready_contract.py",
        "common": "experiments/weibo-eclass/test-gate/test_gate_common.py",
        "final_verifier": "experiments/weibo-eclass/test-gate/verify_frozen_test.py",
        "preflight_verifier": "experiments/weibo-eclass/test-gate/verify_test_ready.py",
        "protocol": "experiments/weibo-eclass/test-gate/protocols/exp-049-frozen-test-gate.md",
        "runner": "experiments/weibo-eclass/test-gate/run_frozen_test.py",
        "test": "experiments/weibo-eclass/test-gate/test_test_gate.py",
    }
    implementation = {
        name: checked_artifact(relative) for name, relative in implementation_paths.items()
    }

    unit_registry = {
        "m0-majority": {"dev_macro_f1": 0.11691327715480061, "seed": None},
        "m1-target-only": {"dev_macro_f1": 0.3382670361475599, "seed": 42},
        "encoder-seed-42": {"dev_macro_f1": 0.6098336406463812, "seed": 42},
        "encoder-seed-43": {"dev_macro_f1": 0.5870270105506048, "seed": 43},
        "encoder-seed-44": {"dev_macro_f1": 0.5879147130672928, "seed": 44},
        "qwen-reference": {"dev_macro_f1": 0.33359776854597856, "seed": None},
        "qwen-lora-seed-42": {"dev_macro_f1": 0.55202826219447, "seed": 42},
        "qwen-lora-seed-43": {"dev_macro_f1": 0.5482887936777165, "seed": 43},
        "qwen-lora-seed-44": {"dev_macro_f1": 0.5870963580895064, "seed": 44},
    }
    contract = {
        "authorization": checked_artifact(
            "experiments/weibo-eclass/test-gate/preflight/exp-049-authorization-v1.json"
        ),
        "condition_order": CONDITION_ORDER,
        "contract_id": "EXP-049-TEST-READY-V1",
        "data": {
            "manifest": manifest_spec,
            "protocol_id": "DATA-WEIBO-TASK-V1",
            "test_inputs": test_inputs,
            "test_labels": test_labels,
            "train": {**train_manifest, "rows": 5995},
        },
        "encoder": {
            "conditions": encoder_conditions,
            "evaluation_batch_size": 64,
            "max_sequence_length": 256,
            "model": {
                "repo_id": stage3["m2"]["repo_id"],
                "revision": stage3["m2"]["revision"],
            },
            "runtime": {
                "backend": "local_apple_metal_mps",
                "packages": {
                    "numpy": "2.2.6",
                    "python": "3.10.20",
                    "safetensors": "0.8.0",
                    "scikit-learn": "1.7.2",
                    "torch": "2.9.1",
                    "transformers": "5.8.0",
                },
                "python_executable": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
            },
        },
        "evaluation": {
            "bootstrap_repeats": 2000,
            "bootstrap_seed_namespace": "EXP-049-frozen-test-group-bootstrap-v1",
            "contrasts": {
                "encoder_mean_minus_m1": {
                    "candidate_units": ["encoder-seed-42", "encoder-seed-43", "encoder-seed-44"],
                    "reference_units": ["m1-target-only"],
                },
                "lora_mean_minus_encoder_mean": {
                    "candidate_units": ["qwen-lora-seed-42", "qwen-lora-seed-43", "qwen-lora-seed-44"],
                    "reference_units": ["encoder-seed-42", "encoder-seed-43", "encoder-seed-44"],
                },
                "lora_mean_minus_qwen_reference": {
                    "candidate_units": ["qwen-lora-seed-42", "qwen-lora-seed-43", "qwen-lora-seed-44"],
                    "reference_units": ["qwen-reference"],
                },
            },
            "long_tail_labels": ["anger", "joy", "neutral", "sadness"],
            "practical_tie_macro_f1": 0.005,
            "primary_metric": "macro_f1",
            "slices": [
                "all",
                "context_available",
                "first_clause",
                "ambiguous_target",
                "unambiguous_target",
                "no_emotion",
                "emotion_label",
                "long_tail_label",
            ],
        },
        "experiment_id": "EXP-049",
        "families": {
            "encoder": {
                "name": "Chinese RoBERTa-WWM-ext supervised encoder",
                "unit_ids": ["encoder-seed-42", "encoder-seed-43", "encoder-seed-44"],
            },
            "m0": {"name": "Train-majority baseline", "unit_ids": ["m0-majority"]},
            "m1": {"name": "Target-only TF-IDF + LinearSVC", "unit_ids": ["m1-target-only"]},
            "qwen_lora": {
                "name": "Qwen3-4B generative LoRA",
                "unit_ids": ["qwen-lora-seed-42", "qwen-lora-seed-43", "qwen-lora-seed-44"],
            },
            "qwen_reference": {
                "name": "Qwen3-4B matched no-adapter reference",
                "unit_ids": ["qwen-reference"],
            },
        },
        "frozen_sources": frozen_sources,
        "implementation": implementation,
        "labels": ["anger", "joy", "negative", "neutral", "no_emotion", "positive", "sadness"],
        "outputs": {
            "private_dir": "data/weibo-emotion-corpus/derived-private/eclass-v1/experiments/exp-049-frozen-test",
            "public_dir": "experiments/weibo-eclass/test-gate/runs/exp-049-frozen-test",
        },
        "qwen": {
            "conditions": qwen_conditions,
            "generation": matched["generation"],
            "model": matched["model"],
            "model_manifest": frozen_sources["qwen_manifest"],
            "runtime": matched["runtime"],
        },
        "registered_at_utc": utc_now(),
        "resource_budget": {
            "baseline_encoder_hours_max_total": 2,
            "bootstrap_repeats": 2000,
            "formal_test_units": 9,
            "peak_mlx_memory_gb_max": 13,
            "qwen_lora_hours_max_per_unit": 3,
            "qwen_reference_hours_max": 30,
            "qwen_total_hours_max": 39,
        },
        "rq_ids": ["RQ-F1"],
        "stage": "formal-frozen-test-gate",
        "status": "Frozen TEST-READY",
        "test_policy": {
            "all_predictions_before_label_open": True,
            "allow_checkpoint_selection": False,
            "allow_ensemble": False,
            "allow_post_result_tuning": False,
            "evaluate_every_unit_once": True,
            "technical_resume_exact_prefix_only": True,
        },
        "test_ready_verification_path": (
            "experiments/weibo-eclass/test-gate/preflight/"
            "exp-049-test-ready-verification-v1.json"
        ),
        "tier": "Major",
        "traditional": {
            "m0": stage3["m0"],
            "m1": stage3["m1"],
        },
        "unit_registry": unit_registry,
        "upstream_verifications": upstream,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(OUTPUT, contract)
    print(
        json.dumps(
            {
                "contract": str(OUTPUT.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(OUTPUT),
                "status": "Frozen TEST-READY contract built without opening test files",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

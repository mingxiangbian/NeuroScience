#!/usr/bin/env python3
"""Run the frozen, label-sealed EXP-049 Weibo EClass test gate."""

from __future__ import annotations

import argparse
from collections import Counter
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Sequence

from test_gate_common import (
    INVALID_LABEL,
    PROJECT_ROOT,
    append_private_jsonl,
    artifact,
    atomic_json,
    atomic_text,
    bootstrap_family_contrast,
    display_path,
    git_state,
    load_json,
    load_test_inputs,
    load_test_labels,
    load_train_rows,
    metrics_by_slice,
    numeric_summary,
    primary_decision,
    read_jsonl,
    render_target_only,
    resolve_project_path,
    sha256_file,
    sha256_text,
    train_label_counts,
    tree_artifact,
    utc_now,
    verify_spec,
    verify_tree_spec,
    write_csv,
    write_private_jsonl,
)


EXPERIMENT_ID = "EXP-049"
CONTRACT_ID = "EXP-049-TEST-READY-V1"
CONDITION_ORDER = (
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
BASELINE_CONDITIONS = CONDITION_ORDER[:5]
QWEN_CONDITIONS = CONDITION_ORDER[5:]
SCRIPT_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = SCRIPT_DIR / "configs" / "exp-049-test-ready.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize")
    baseline = subparsers.add_parser("infer-baseline")
    baseline.add_argument("--condition", required=True, choices=BASELINE_CONDITIONS)
    qwen = subparsers.add_parser("infer-qwen")
    qwen.add_argument("--condition", required=True, choices=QWEN_CONDITIONS)
    subparsers.add_parser("finalize")
    return parser.parse_args()


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    expected_generation = {
        "batch_size": 1,
        "completion_batch_size": 1,
        "do_sample": False,
        "enable_thinking": True,
        "max_input_tokens": 512,
        "max_new_tokens": 1024,
        "prefill_batch_size": 1,
        "prefill_step_size": 2048,
        "temperature": 0.0,
        "view": "target_only",
    }
    if (
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("tier") != "Major"
        or contract.get("stage") != "formal-frozen-test-gate"
        or contract.get("status") != "Frozen TEST-READY"
        or tuple(contract.get("condition_order", ())) != CONDITION_ORDER
        or contract.get("labels")
        != ["anger", "joy", "negative", "neutral", "no_emotion", "positive", "sadness"]
        or contract.get("data", {}).get("protocol_id") != "DATA-WEIBO-TASK-V1"
        or contract.get("data", {}).get("train", {}).get("rows") != 5995
        or contract.get("data", {}).get("test_inputs", {}).get("rows") != 1273
        or contract.get("data", {}).get("test_labels", {}).get("rows") != 1273
        or contract.get("qwen", {}).get("generation") != expected_generation
        or contract.get("test_policy", {}).get("all_predictions_before_label_open") is not True
        or contract.get("test_policy", {}).get("evaluate_every_unit_once") is not True
    ):
        raise ValueError("Unexpected EXP-049 frozen contract")
    if tuple(contract["evaluation"]["slices"]) != (
        "all",
        "context_available",
        "first_clause",
        "ambiguous_target",
        "unambiguous_target",
        "no_emotion",
        "emotion_label",
        "long_tail_label",
    ):
        raise ValueError("Frozen slice registry drift")
    if contract["evaluation"]["primary_metric"] != "macro_f1":
        raise ValueError("Primary metric drift")
    for spec in contract["implementation"].values():
        verify_spec(spec)
    if resolve_project_path(contract["implementation"]["runner"]["path"]) != Path(__file__).resolve():
        raise ValueError("Runner path drift")
    return contract


def verify_authorization(contract: dict[str, Any]) -> dict[str, Any]:
    path = verify_spec(contract["authorization"])
    value = load_json(path)
    if (
        value.get("authorization_id") != "EXP-049-FROZEN-TEST-AUTH-V1"
        or value.get("status") != "Authorized"
        or value.get("authorized_split") != "test"
        or tuple(value.get("authorized_conditions_in_order", ())) != CONDITION_ORDER
        or value.get("authorized_formal_test_units") != 9
        or value.get("boundaries", {}).get("all_predictions_before_label_open") is not True
        or value.get("boundaries", {}).get("one_final_label_opening_step") is not True
        or value.get("boundaries", {}).get("post_result_tuning") is not False
    ):
        raise ValueError("EXP-049 authorization is invalid")
    return value


def verify_test_ready(contract: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(contract["test_ready_verification_path"])
    value = load_json(path)
    if (
        value.get("verification_id") != "EXP-049-TEST-READY-VERIFY-V1"
        or value.get("status") != "Passed"
        or value.get("test_inputs_opened") is not False
        or value.get("test_labels_opened") is not False
        or value.get("contract", {}).get("sha256") != sha256_file(CONTRACT_PATH)
    ):
        raise ValueError("EXP-049 TEST-READY verification is invalid")
    return value


def verify_upstream(contract: dict[str, Any]) -> None:
    for item in contract["upstream_verifications"]:
        path = verify_spec(item["artifact"])
        value = load_json(path)
        if value.get("status") != item["expected_status"]:
            raise ValueError(f"Upstream verification status drift: {item['artifact']['path']}")
        for key, expected in item.get("required_fields", {}).items():
            if value.get(key) != expected:
                raise ValueError(f"Upstream verification boundary drift: {key}")
    for spec in contract["frozen_sources"].values():
        verify_spec(spec)


def verify_runtime(runtime: dict[str, Any]) -> None:
    expected = Path(runtime["python_executable"])
    if not expected.is_file() or not Path(sys.executable).samefile(expected):
        raise ValueError(f"Wrong Python runtime: expected {expected}")
    observed = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in runtime["packages"]
    }
    if observed != runtime["packages"]:
        raise ValueError(f"Runtime package drift: {observed}")


def verify_qwen_model(contract: dict[str, Any]) -> dict[str, Any]:
    manifest_path = verify_spec(contract["qwen"]["model_manifest"])
    manifest = load_json(manifest_path)
    model = contract["qwen"]["model"]
    if (
        manifest.get("repo_id") != model["repo_id"]
        or manifest.get("revision") != model["revision"]
        or manifest.get("conversion", {}).get("dtype") != "bfloat16"
        or manifest.get("conversion", {}).get("quantized") is not False
    ):
        raise ValueError("Frozen Qwen model identity drift")
    root = resolve_project_path(model["local_path"])
    checked = []
    for expected in manifest["mlx_bf16"]["files"]:
        path = root / expected["path"]
        observed = artifact(path)
        if observed["bytes"] != expected["bytes"] or observed["sha256"] != expected["sha256"]:
            raise ValueError(f"Qwen model file drift: {expected['path']}")
        checked.append(observed)
    return {"file_count": len(checked), "total_bytes": sum(row["bytes"] for row in checked)}


def verify_encoder_checkpoint(contract: dict[str, Any], condition: str) -> Path:
    return verify_tree_spec(contract["encoder"]["conditions"][condition]["checkpoint"])


def verify_qwen_condition(contract: dict[str, Any], condition: str) -> None:
    spec = contract["qwen"]["conditions"][condition]
    for key in ("adapter", "adapter_config"):
        if spec.get(key) is not None:
            verify_spec(spec[key])


def public_dir(contract: dict[str, Any]) -> Path:
    return resolve_project_path(contract["outputs"]["public_dir"])


def private_dir(contract: dict[str, Any]) -> Path:
    return resolve_project_path(contract["outputs"]["private_dir"])


def private_prediction_path(contract: dict[str, Any], condition: str) -> Path:
    return private_dir(contract) / f"condition-{condition}-predictions.jsonl"


def load_run(contract: dict[str, Any]) -> dict[str, Any]:
    path = public_dir(contract) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("EXP-049 has not been initialized")
    return load_json(path)


def save_run(contract: dict[str, Any], run: dict[str, Any]) -> None:
    atomic_json(public_dir(contract) / "run.json", run)


def add_command(run: dict[str, Any], command: str) -> None:
    run.setdefault("commands", []).append({"command": command, "recorded_at_utc": utc_now()})


def stage_key(condition: str) -> str:
    return f"infer__{condition}"


def require_condition_order(run: dict[str, Any], condition: str, *, resume: bool) -> None:
    index = CONDITION_ORDER.index(condition)
    for prior in CONDITION_ORDER[:index]:
        if run["stages"].get(stage_key(prior), {}).get("status") != "Completed":
            raise RuntimeError(f"Prior frozen unit is incomplete: {prior}")
    for later in CONDITION_ORDER[index + 1 :]:
        if stage_key(later) in run["stages"]:
            raise RuntimeError(f"Condition-order drift: later unit already exists: {later}")
    current = run["stages"].get(stage_key(condition))
    if current is not None and not (resume and current.get("status") == "Running"):
        raise FileExistsError(f"Frozen unit already started or completed: {condition}")


def mark_condition_running(contract: dict[str, Any], condition: str, command: str) -> dict[str, Any]:
    run = load_run(contract)
    require_condition_order(run, condition, resume=condition in QWEN_CONDITIONS)
    key = stage_key(condition)
    if key not in run["stages"]:
        run["stages"][key] = {
            "started_at_utc": utc_now(),
            "status": "Running",
            "test_inputs_accessed": True,
            "test_labels_accessed": False,
        }
    add_command(run, command)
    run["status"] = "Formal test inference in progress; labels sealed"
    run["test_inputs_accessed"] = True
    save_run(contract, run)
    return run


def complete_condition(
    contract: dict[str, Any], condition: str, summary_path: Path, private_path: Path
) -> None:
    run = load_run(contract)
    key = stage_key(condition)
    if run["stages"].get(key, {}).get("status") != "Running":
        raise RuntimeError(f"Condition was not marked Running: {condition}")
    run["stages"][key].update(
        {
            "completed_at_utc": utc_now(),
            "private_predictions": artifact(private_path),
            "public_summary": artifact(summary_path),
            "status": "Completed",
        }
    )
    run["status"] = "Formal test predictions in progress; labels sealed"
    save_run(contract, run)


def initialize(contract: dict[str, Any]) -> None:
    verify_authorization(contract)
    verify_test_ready(contract)
    verify_upstream(contract)
    for condition in BASELINE_CONDITIONS[2:]:
        verify_encoder_checkpoint(contract, condition)
    verify_qwen_model(contract)
    for condition in QWEN_CONDITIONS:
        verify_qwen_condition(contract, condition)
    public = public_dir(contract)
    private = private_dir(contract)
    if public.exists() or private.exists():
        raise FileExistsError("EXP-049 output directories must be absent before initialization")
    public.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    private.chmod(0o700)
    initialized_at = utc_now()
    report = {
        "authorization": artifact(resolve_project_path(contract["authorization"]["path"])),
        "completed_at_utc": initialized_at,
        "condition_order": list(CONDITION_ORDER),
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "model_artifacts_verified": True,
        "performance_metrics_computed": False,
        "status": "Passed",
        "test_inputs_accessed": False,
        "test_labels_accessed": False,
        "test_ready_verification": artifact(
            resolve_project_path(contract["test_ready_verification_path"])
        ),
    }
    initialize_path = public / "initialize.json"
    atomic_json(initialize_path, report)
    run = {
        "accessed_splits": [],
        "commands": [],
        "condition_order": list(CONDITION_ORDER),
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "git": git_state(),
        "label_opening": {"status": "sealed"},
        "raw_outputs_stored_publicly": False,
        "stages": {
            "initialize": {
                "artifact": artifact(initialize_path),
                "completed_at_utc": initialized_at,
                "status": "Passed",
            }
        },
        "started_at_utc": initialized_at,
        "status": "Initialized; test labels sealed",
        "test_inputs_accessed": False,
        "test_labels_accessed": False,
        "tier": "Major",
    }
    add_command(run, f"{sys.executable} {display_path(Path(__file__))} initialize")
    save_run(contract, run)
    print(json.dumps({"status": "Initialized", "test_labels_accessed": False}, sort_keys=True))


def load_prompt(contract: dict[str, Any]) -> dict[str, Any]:
    path = verify_spec(contract["frozen_sources"]["prompt"])
    prompt = load_json(path)
    if tuple(prompt["label_definitions"]) != tuple(contract["labels"]):
        raise ValueError("Prompt label order drift")
    return prompt


def condition_summary_path(contract: dict[str, Any], condition: str) -> Path:
    return public_dir(contract) / f"condition-{condition}.json"


def ensure_new_condition_outputs(contract: dict[str, Any], condition: str, *, resume: bool) -> Path:
    summary = condition_summary_path(contract, condition)
    private = private_prediction_path(contract, condition)
    if summary.exists():
        raise FileExistsError(f"Public condition summary already exists: {condition}")
    if private.exists() and not resume:
        raise FileExistsError(f"Private prediction file already exists: {condition}")
    return private


def prediction_records(
    condition: str,
    rows: Sequence[dict[str, Any]],
    predictions: Sequence[str],
    scores: Sequence[Sequence[float]] | None,
    score_type: str,
    labels: Sequence[str],
) -> list[dict[str, Any]]:
    records = []
    for index, (source, prediction) in enumerate(zip(rows, predictions)):
        record = {
            "ambiguous_target": bool(source["ambiguous_target"]),
            "condition": condition,
            "context_available": bool(source["context_available"]),
            "group_id": source["group_id"],
            "prediction": prediction,
            "row_index": index,
            "sample_id": source["sample_id"],
            "score_type": score_type,
            "view": "target_only",
        }
        if scores is not None:
            record["scores"] = {label: float(scores[index][offset]) for offset, label in enumerate(labels)}
        records.append(record)
    return records


def infer_m0(contract: dict[str, Any], condition: str, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    train = load_train_rows(contract)
    counts = train_label_counts(train, contract["labels"])
    majority = max(contract["labels"], key=lambda label: counts[label])
    if majority != contract["traditional"]["m0"]["expected_majority_label"]:
        raise ValueError("Frozen M0 majority label drift")
    predictions = [majority] * len(rows)
    private = private_prediction_path(contract, condition)
    write_private_jsonl(
        private,
        prediction_records(condition, rows, predictions, None, "constant", contract["labels"]),
    )
    return {
        "label_counts": counts,
        "majority_label": majority,
        "private_predictions": artifact(private),
    }


def infer_m1(contract: dict[str, Any], condition: str, rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    from sklearn.svm import LinearSVC

    train = load_train_rows(contract)
    prompt = load_prompt(contract)
    train_texts = [render_target_only(prompt, row) for row in train]
    test_texts = [render_target_only(prompt, row) for row in rows]
    config = contract["traditional"]["m1"]
    vectorizer = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    ngram_range=tuple(config["word_ngram_range"]),
                    min_df=config["min_df"],
                    sublinear_tf=config["sublinear_tf"],
                    lowercase=config["lowercase"],
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer=config["char_analyzer"],
                    ngram_range=tuple(config["char_ngram_range"]),
                    min_df=config["min_df"],
                    sublinear_tf=config["sublinear_tf"],
                    lowercase=config["lowercase"],
                ),
            ),
        ]
    )
    fit_started = time.perf_counter()
    train_matrix = vectorizer.fit_transform(train_texts)
    test_matrix = vectorizer.transform(test_texts)
    classifier = LinearSVC(
        C=config["c"], class_weight=config["class_weight"], random_state=config["random_state"]
    )
    classifier.fit(train_matrix, [row["label"] for row in train])
    fit_seconds = time.perf_counter() - fit_started
    infer_started = time.perf_counter()
    predictions = classifier.predict(test_matrix).tolist()
    raw_scores = classifier.decision_function(test_matrix)
    infer_seconds = time.perf_counter() - infer_started
    if raw_scores.shape != (len(rows), len(contract["labels"])) or not np.isfinite(raw_scores).all():
        raise ValueError("M1 decision scores are invalid")
    class_index = {label: index for index, label in enumerate(classifier.classes_.tolist())}
    if set(class_index) != set(contract["labels"]):
        raise ValueError("M1 class set drift")
    ordered_scores = raw_scores[:, [class_index[label] for label in contract["labels"]]]
    private = private_prediction_path(contract, condition)
    write_private_jsonl(
        private,
        prediction_records(
            condition,
            rows,
            predictions,
            ordered_scores.tolist(),
            "decision",
            contract["labels"],
        ),
    )
    return {
        "feature_count": int(train_matrix.shape[1]),
        "fit_seconds": fit_seconds,
        "inference_seconds": infer_seconds,
        "private_predictions": artifact(private),
        "train_rows": len(train),
    }


class InferenceDataset:
    def __init__(self, encodings: dict[str, list[list[int]]]) -> None:
        self.encodings = encodings

    def __len__(self) -> int:
        return len(next(iter(self.encodings.values())))

    def __getitem__(self, index: int) -> dict[str, Any]:
        return {key: values[index] for key, values in self.encodings.items()}


def infer_encoder(
    contract: dict[str, Any], condition: str, rows: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    import numpy as np
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding

    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable")
    checkpoint = verify_encoder_checkpoint(contract, condition)
    prompt = load_prompt(contract)
    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    texts = [render_target_only(prompt, row) for row in rows]
    lengths = [len(tokenizer.encode(text, add_special_tokens=True)) for text in texts]
    max_length = int(contract["encoder"]["max_sequence_length"])
    if max(lengths) > max_length:
        raise ValueError("Frozen encoder test input exceeds the preregistered token budget")
    encodings = tokenizer(texts, add_special_tokens=True, padding=False, truncation=False)
    loader = DataLoader(
        InferenceDataset(encodings),
        batch_size=int(contract["encoder"]["evaluation_batch_size"]),
        shuffle=False,
        drop_last=False,
        num_workers=0,
        collate_fn=DataCollatorWithPadding(tokenizer=tokenizer, padding=True, return_tensors="pt"),
    )
    model = AutoModelForSequenceClassification.from_pretrained(checkpoint, local_files_only=True)
    id_to_label = {int(index): label for index, label in model.config.id2label.items()}
    if set(id_to_label.values()) != set(contract["labels"]):
        raise ValueError("Encoder checkpoint label mapping drift")
    device = torch.device("mps")
    model.to(device)
    model.eval()
    started = time.perf_counter()
    checkpoint_probabilities = []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            probabilities = torch.softmax(logits, dim=-1)
            checkpoint_probabilities.extend(probabilities.detach().cpu().tolist())
    inference_seconds = time.perf_counter() - started
    array = np.asarray(checkpoint_probabilities, dtype=np.float64)
    if array.shape != (len(rows), len(contract["labels"])) or not np.isfinite(array).all():
        raise ValueError("Encoder probability array is invalid")
    if not np.allclose(array.sum(axis=1), 1.0, atol=1e-5):
        raise ValueError("Encoder probabilities do not sum to one")
    predictions = [id_to_label[int(index)] for index in array.argmax(axis=1).tolist()]
    checkpoint_index = {label: index for index, label in id_to_label.items()}
    ordered_scores = array[:, [checkpoint_index[label] for label in contract["labels"]]]
    private = private_prediction_path(contract, condition)
    write_private_jsonl(
        private,
        prediction_records(
            condition,
            rows,
            predictions,
            ordered_scores.tolist(),
            "probability",
            contract["labels"],
        ),
    )
    result = {
        "checkpoint": tree_artifact(checkpoint),
        "inference_seconds": inference_seconds,
        "input_tokens": numeric_summary(lengths),
        "private_predictions": artifact(private),
    }
    del model, tokenizer, loader
    gc.collect()
    torch.mps.empty_cache()
    return result


def infer_baseline(contract: dict[str, Any], condition: str) -> None:
    verify_runtime(contract["encoder"]["runtime"])
    verify_authorization(contract)
    verify_test_ready(contract)
    verify_upstream(contract)
    ensure_new_condition_outputs(contract, condition, resume=False)
    command = f"{sys.executable} {display_path(Path(__file__))} infer-baseline --condition {condition}"
    mark_condition_running(contract, condition, command)
    rows = load_test_inputs(contract)
    started = time.perf_counter()
    if condition == "m0-majority":
        details = infer_m0(contract, condition, rows)
    elif condition == "m1-target-only":
        details = infer_m1(contract, condition, rows)
    else:
        details = infer_encoder(contract, condition, rows)
    elapsed = time.perf_counter() - started
    summary = {
        "completed_at_utc": utc_now(),
        "condition": condition,
        "details": details,
        "experiment_id": EXPERIMENT_ID,
        "performance_metrics_computed": False,
        "rows": len(rows),
        "status": "Completed; labels sealed",
        "test_inputs_accessed": True,
        "test_labels_accessed": False,
        "total_seconds": elapsed,
        "view": "target_only",
    }
    summary_path = condition_summary_path(contract, condition)
    atomic_json(summary_path, summary)
    complete_condition(contract, condition, summary_path, private_prediction_path(contract, condition))
    print(json.dumps({"condition": condition, "rows": len(rows), "status": summary["status"]}, sort_keys=True))


def load_parser(contract: dict[str, Any]):
    path = verify_spec(contract["frozen_sources"]["parser"])
    spec = importlib.util.spec_from_file_location("exp049_frozen_parser", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_final_label


def prompt_messages(
    contract: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]
) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in contract["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions, output_schema=prompt["output_schema"]
    )
    user = render_target_only(prompt, row)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def require_token_ids(value: Any) -> list[int]:
    tokens = list(value)
    if not tokens or not all(isinstance(token, int) and not isinstance(token, bool) for token in tokens):
        raise TypeError("Chat template must return non-empty integer token IDs")
    return tokens


def output_token_counts(tokenizer: Any, output: str, generated_tokens: int) -> dict[str, int]:
    if "</think>" not in output:
        return {"final_tokens": 0, "thinking_tokens": generated_tokens}
    thinking, final = output.split("</think>", maxsplit=1)
    return {
        "final_tokens": len(tokenizer.encode(final, add_special_tokens=False)),
        "thinking_tokens": len(tokenizer.encode(thinking, add_special_tokens=False)),
    }


def validate_qwen_prefix(
    records: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]], condition: str
) -> None:
    if len(records) > len(rows):
        raise ValueError("Qwen prediction prefix exceeds test length")
    for index, record in enumerate(records):
        if (
            record.get("condition") != condition
            or record.get("row_index") != index
            or record.get("sample_id") != rows[index]["sample_id"]
            or record.get("group_id") != rows[index]["group_id"]
            or "gold_label" in record
        ):
            raise ValueError("Existing Qwen predictions are not an exact resumable prefix")


def qwen_summary(
    contract: dict[str, Any], condition: str, records: Sequence[dict[str, Any]], elapsed: float, peak: float
) -> dict[str, Any]:
    valid = sum(bool(record["parse"]["valid"]) for record in records)
    active_generation_seconds = sum(float(record["generation_seconds"]) for record in records)
    return {
        "completed_at_utc": utc_now(),
        "condition": condition,
        "experiment_id": EXPERIMENT_ID,
        "generation": {
            "api_cost_usd": 0,
            "active_generation_seconds": active_generation_seconds,
            "batch_size": 1,
            "command_elapsed_seconds": elapsed,
            "final_tokens": numeric_summary([record["final_tokens"] for record in records]),
            "generated_tokens": numeric_summary([record["generated_tokens"] for record in records]),
            "generation_seconds": numeric_summary([record["generation_seconds"] for record in records]),
            "peak_memory_gb": peak,
            "prompt_tokens": numeric_summary([record["prompt_tokens"] for record in records]),
            "thinking_tokens": numeric_summary([record["thinking_tokens"] for record in records]),
        },
        "parser": {
            "error_counts": dict(
                sorted(Counter(record["parse"]["error"] for record in records if record["parse"]["error"]).items())
            ),
            "likely_truncated_count": sum(bool(record["likely_truncated"]) for record in records),
            "valid_count": valid,
            "valid_rate": valid / len(records),
        },
        "performance_metrics_computed": False,
        "private_predictions": artifact(private_prediction_path(contract, condition)),
        "raw_outputs_stored_publicly": False,
        "reasoning": True,
        "rows": len(records),
        "status": "Completed; labels sealed",
        "test_inputs_accessed": True,
        "test_labels_accessed": False,
        "view": "target_only",
    }


def infer_qwen(contract: dict[str, Any], condition: str) -> None:
    verify_runtime(contract["qwen"]["runtime"])
    verify_authorization(contract)
    verify_test_ready(contract)
    verify_upstream(contract)
    verify_qwen_model(contract)
    verify_qwen_condition(contract, condition)
    private = ensure_new_condition_outputs(contract, condition, resume=True)
    command = f"{sys.executable} {display_path(Path(__file__))} infer-qwen --condition {condition}"
    mark_condition_running(contract, condition, command)
    rows = load_test_inputs(contract)
    existing = read_jsonl(private) if private.exists() else []
    validate_qwen_prefix(existing, rows, condition)
    prompt = load_prompt(contract)
    parse_final_label = load_parser(contract)
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    import mlx.core as mx
    from mlx_lm import batch_generate, load
    from mlx_lm.sample_utils import make_sampler

    model_path = resolve_project_path(contract["qwen"]["model"]["local_path"])
    condition_spec = contract["qwen"]["conditions"][condition]
    adapter = condition_spec.get("adapter")
    mx.reset_peak_memory()
    if adapter is None:
        model, tokenizer = load(str(model_path), lazy=False)
    else:
        adapter_path = resolve_project_path(adapter["path"])
        model, tokenizer = load(str(model_path), adapter_path=str(adapter_path.parent), lazy=False)
    generation = contract["qwen"]["generation"]
    sampler = make_sampler(temp=float(generation["temperature"]))
    started = time.perf_counter()
    for row_index in range(len(existing), len(rows)):
        source = rows[row_index]
        messages = prompt_messages(contract, prompt, source)
        prompt_ids = require_token_ids(
            tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                enable_thinking=True,
                tokenize=True,
                return_dict=False,
            )
        )
        if len(prompt_ids) > int(generation["max_input_tokens"]):
            raise RuntimeError(f"Rendered test prompt exceeds token budget at row {row_index}")
        generation_started = time.perf_counter()
        generated = batch_generate(
            model,
            tokenizer,
            [prompt_ids],
            max_tokens=int(generation["max_new_tokens"]),
            sampler=sampler,
            completion_batch_size=1,
            prefill_batch_size=1,
            prefill_step_size=int(generation["prefill_step_size"]),
            verbose=False,
        )
        generation_seconds = time.perf_counter() - generation_started
        if not math.isfinite(generation_seconds) or generation_seconds <= 0:
            raise RuntimeError("Invalid Qwen singleton generation timing")
        output = generated.texts[0]
        parsed = parse_final_label(output, thinking=True, labels=contract["labels"])
        generated_tokens = len(tokenizer.encode(output, add_special_tokens=False))
        partition = output_token_counts(tokenizer, output, generated_tokens)
        record = {
            "ambiguous_target": bool(source["ambiguous_target"]),
            "condition": condition,
            "context_available": bool(source["context_available"]),
            "final_tokens": partition["final_tokens"],
            "generated_tokens": generated_tokens,
            "generation_seconds": generation_seconds,
            "group_id": source["group_id"],
            "likely_truncated": generated_tokens >= int(generation["max_new_tokens"]) - 2,
            "message_sha256": sha256_text(
                json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            ),
            "parse": parsed.to_dict(),
            "prediction": parsed.label if parsed.valid else INVALID_LABEL,
            "prompt_sha256": sha256_text(json.dumps(prompt_ids, separators=(",", ":"))),
            "prompt_tokens": len(prompt_ids),
            "raw_output": output,
            "raw_output_sha256": sha256_text(output),
            "reasoning": True,
            "row_index": row_index,
            "sample_id": source["sample_id"],
            "thinking_tokens": partition["thinking_tokens"],
            "view": "target_only",
        }
        append_private_jsonl(private, [record])
        completed = row_index + 1
        if completed % 10 == 0 or completed == len(rows):
            print(json.dumps({"completed": completed, "condition": condition, "total": len(rows)}, sort_keys=True), flush=True)
    records = read_jsonl(private)
    validate_qwen_prefix(records, rows, condition)
    if len(records) != len(rows):
        raise RuntimeError("Qwen condition is incomplete")
    elapsed = time.perf_counter() - started
    peak = float(mx.get_peak_memory()) / 1e9
    maximum_hours = float(
        contract["resource_budget"][
            "qwen_reference_hours_max" if condition == "qwen-reference" else "qwen_lora_hours_max_per_unit"
        ]
    )
    if peak > float(contract["resource_budget"]["peak_mlx_memory_gb_max"]):
        raise RuntimeError("Qwen condition exceeded the frozen memory budget")
    active_generation_seconds = sum(float(record["generation_seconds"]) for record in records)
    if active_generation_seconds > maximum_hours * 3600:
        raise RuntimeError("Qwen condition exceeded the frozen wall-time budget")
    summary = qwen_summary(contract, condition, records, elapsed, peak)
    summary_path = condition_summary_path(contract, condition)
    atomic_json(summary_path, summary)
    complete_condition(contract, condition, summary_path, private)
    del model, tokenizer
    gc.collect()
    mx.clear_cache()
    print(json.dumps({"condition": condition, "parser_valid_rate": summary["parser"]["valid_rate"], "status": summary["status"]}, sort_keys=True))


def load_predictions(
    contract: dict[str, Any], condition: str, rows: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    records = read_jsonl(private_prediction_path(contract, condition))
    if len(records) != len(rows):
        raise ValueError(f"Prediction row-count drift: {condition}")
    for index, (record, source) in enumerate(zip(records, rows)):
        if (
            record.get("condition") != condition
            or record.get("row_index") != index
            or record.get("sample_id") != source["sample_id"]
            or record.get("group_id") != source["group_id"]
            or record.get("prediction") not in set(contract["labels"]) | {INVALID_LABEL}
            or "gold_label" in record
        ):
            raise ValueError(f"Prediction alignment drift: {condition}:{index}")
    return records


def write_metric_artifacts(
    contract: dict[str, Any], condition: str, metrics: dict[str, Any]
) -> dict[str, Any]:
    root = public_dir(contract) / "conditions" / condition
    if root.exists():
        raise FileExistsError(f"Metric output already exists: {condition}")
    root.mkdir(parents=True, exist_ok=False)
    metrics_path = root / "metrics.json"
    atomic_json(metrics_path, metrics)
    per_class_rows = []
    confusion_rows = []
    for slice_name, values in metrics["slices"].items():
        for label in contract["labels"]:
            per_class_rows.append({"slice": slice_name, "label": label, **values["per_class"][label]})
        if slice_name == "all":
            for gold_label, row in zip(contract["labels"], values["confusion_matrix"]):
                item = {"gold_label": gold_label}
                item.update(dict(zip(values["confusion_columns"], row)))
                confusion_rows.append(item)
    per_class_path = root / "per-class-metrics.csv"
    write_csv(
        per_class_path,
        ("slice", "label", "precision", "recall", "f1", "support", "predicted_support"),
        per_class_rows,
    )
    confusion_path = root / "confusion-matrix.csv"
    write_csv(confusion_path, ("gold_label", *contract["labels"], INVALID_LABEL), confusion_rows)
    return {
        "confusion_matrix": artifact(confusion_path),
        "metrics": artifact(metrics_path),
        "per_class_metrics": artifact(per_class_path),
    }


def family_summary(
    contract: dict[str, Any], unit_metrics: dict[str, dict[str, Any]], family: dict[str, Any]
) -> dict[str, Any]:
    units = family["unit_ids"]
    result = {"family": family["name"], "unit_ids": units, "unit_count": len(units)}
    for metric in ("macro_f1", "accuracy", "macro_precision", "macro_recall", "weighted_f1"):
        values = [unit_metrics[unit]["slices"]["all"][metric] for unit in units]
        result[metric] = {
            "mean": statistics.fmean(values),
            "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "values": values,
        }
    return result


def render_report(aggregate: dict[str, Any]) -> str:
    rows = [
        "# EXP-049 Weibo EClass Frozen Test Report",
        "",
        "Status: Completed; pending independent verification.",
        "",
        "| Unit | Macro-F1 | Accuracy | Macro-P | Macro-R | Weighted-F1 | Parser valid | Seconds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for unit in CONDITION_ORDER:
        result = aggregate["units"][unit]
        metric = result["metrics"]["slices"]["all"]
        parser = result.get("parser", {}).get("valid_rate")
        parser_text = f"{parser:.6f}" if parser is not None else "N/A"
        rows.append(
            f"| {unit} | {metric['macro_f1']:.6f} | {metric['accuracy']:.6f} | "
            f"{metric['macro_precision']:.6f} | {metric['macro_recall']:.6f} | "
            f"{metric['weighted_f1']:.6f} | "
            f"{parser_text} | {result['resource']['seconds']:.3f} |"
        )
    rows.extend(["", "## Family Summary", ""])
    for family_id, summary in aggregate["families"].items():
        rows.append(
            f"- `{family_id}` Macro-F1: `{summary['macro_f1']['mean']:.6f} +/- "
            f"{summary['macro_f1']['sample_std']:.6f}`"
        )
    rows.extend(["", "## Frozen Contrasts", ""])
    for contrast_id, contrast in aggregate["contrasts"].items():
        rows.append(
            f"- `{contrast_id}`: delta `{contrast['observed_delta']:+.6f}`, "
            f"95% group bootstrap CI `[{contrast['ci95'][0]:+.6f}, {contrast['ci95'][1]:+.6f}]`, "
            f"decision `{contrast['decision']}`."
        )
    rows.extend(
        [
            "",
            "All nine configurations were frozen before test access and are reported without best-seed selection.",
            "Row-level predictions, source identifiers, text, gold labels, and Qwen reasoning remain private.",
            "No result may be used to tune or rerun this held-out split.",
            "",
        ]
    )
    return "\n".join(rows)


def finalize(contract: dict[str, Any]) -> None:
    verify_authorization(contract)
    verify_test_ready(contract)
    verify_upstream(contract)
    run = load_run(contract)
    for condition in CONDITION_ORDER:
        if run["stages"].get(stage_key(condition), {}).get("status") != "Completed":
            raise RuntimeError(f"All nine predictions must complete before labels open: {condition}")
    if run.get("test_labels_accessed") or run.get("label_opening", {}).get("status") != "sealed":
        raise RuntimeError("Test labels were already opened")
    aggregate_path = public_dir(contract) / "aggregate-metrics.json"
    report_path = public_dir(contract) / "REPORT.md"
    label_open_path = public_dir(contract) / "label-opening.json"
    if aggregate_path.exists() or report_path.exists() or label_open_path.exists():
        raise FileExistsError("EXP-049 final outputs are append-only")
    rows = load_test_inputs(contract)
    records = {condition: load_predictions(contract, condition, rows) for condition in CONDITION_ORDER}

    inference_summaries = {
        condition: load_json(condition_summary_path(contract, condition))
        for condition in CONDITION_ORDER
    }
    baseline_encoder_seconds = sum(
        float(inference_summaries[condition]["total_seconds"])
        for condition in BASELINE_CONDITIONS
    )
    qwen_active_seconds = sum(
        float(inference_summaries[condition]["generation"]["active_generation_seconds"])
        for condition in QWEN_CONDITIONS
    )
    if baseline_encoder_seconds > float(
        contract["resource_budget"]["baseline_encoder_hours_max_total"]
    ) * 3600:
        raise RuntimeError("Baseline/encoder units exceeded the frozen total wall-time budget")
    if qwen_active_seconds > float(contract["resource_budget"]["qwen_total_hours_max"]) * 3600:
        raise RuntimeError("Qwen units exceeded the frozen total active-generation budget")

    # Persist the irreversible transition before opening labels. A crash after this
    # point consumes the gate rather than silently permitting a second opening.
    labels_opened_at = utc_now()
    opening_record = {
        "all_nine_prediction_files_complete_before_open": True,
        "experiment_id": EXPERIMENT_ID,
        "labels_opened_at_utc": labels_opened_at,
        "model_calls_after_open": 0,
        "rows": len(rows),
        "status": "Opening",
        "test_label_artifact": {
            "bytes": contract["data"]["test_labels"]["bytes"],
            "path": contract["data"]["test_labels"]["path"],
            "sha256": contract["data"]["test_labels"]["sha256"],
        },
    }
    atomic_json(label_open_path, opening_record)
    run = load_run(contract)
    run["label_opening"] = {
        "artifact": artifact(label_open_path),
        "opened_at_utc": labels_opened_at,
        "status": "opening",
    }
    run["status"] = "Test labels opening; gate consumed"
    run["test_labels_accessed"] = True
    save_run(contract, run)

    # This is the single formal label read; no model code is called after it.
    label_rows = load_test_labels(contract)
    if [row["sample_id"] for row in label_rows] != [row["sample_id"] for row in rows]:
        raise ValueError("Test input/label sample order drift")
    gold = [row["label"] for row in label_rows]
    predictions = {
        condition: [record["prediction"] for record in condition_rows]
        for condition, condition_rows in records.items()
    }
    scored_path = private_dir(contract) / "scored-predictions.jsonl"
    write_private_jsonl(
        scored_path,
        (
            {
                "gold_label": gold[index],
                "group_id": row["group_id"],
                "predictions": {condition: predictions[condition][index] for condition in CONDITION_ORDER},
                "row_index": index,
                "sample_id": row["sample_id"],
            }
            for index, row in enumerate(rows)
        ),
    )
    unit_metrics = {}
    units = {}
    result_rows = []
    for condition in CONDITION_ORDER:
        metrics = {
            "condition": condition,
            "experiment_id": EXPERIMENT_ID,
            "slices": metrics_by_slice(rows, gold, predictions[condition], contract),
        }
        unit_metrics[condition] = metrics
        metric_artifacts = write_metric_artifacts(contract, condition, metrics)
        inference = inference_summaries[condition]
        parser = inference.get("parser")
        seconds = (
            float(inference["generation"]["active_generation_seconds"])
            if condition in QWEN_CONDITIONS
            else float(inference["total_seconds"])
        )
        units[condition] = {
            "artifacts": metric_artifacts,
            "dev_macro_f1": contract["unit_registry"][condition]["dev_macro_f1"],
            "dev_to_test_macro_f1_delta": metrics["slices"]["all"]["macro_f1"]
            - contract["unit_registry"][condition]["dev_macro_f1"],
            "metrics": metrics,
            "parser": parser,
            "private_predictions": artifact(private_prediction_path(contract, condition)),
            "resource": {"seconds": seconds},
        }
        all_metrics = metrics["slices"]["all"]
        result_rows.append(
            {
                "accuracy": all_metrics["accuracy"],
                "condition": condition,
                "dev_macro_f1": contract["unit_registry"][condition]["dev_macro_f1"],
                "macro_f1": all_metrics["macro_f1"],
                "macro_precision": all_metrics["macro_precision"],
                "macro_recall": all_metrics["macro_recall"],
                "parser_valid_rate": parser["valid_rate"] if parser else "",
                "seconds": seconds,
                "weighted_f1": all_metrics["weighted_f1"],
            }
        )
    result_path = public_dir(contract) / "unit-results.csv"
    write_csv(
        result_path,
        (
            "condition",
            "dev_macro_f1",
            "macro_f1",
            "accuracy",
            "macro_precision",
            "macro_recall",
            "weighted_f1",
            "parser_valid_rate",
            "seconds",
        ),
        result_rows,
    )
    families = {
        family_id: family_summary(contract, unit_metrics, family)
        for family_id, family in contract["families"].items()
    }
    contrasts = {}
    for contrast_id, contrast in contract["evaluation"]["contrasts"].items():
        result = bootstrap_family_contrast(
            rows,
            gold,
            predictions,
            contrast["candidate_units"],
            contrast["reference_units"],
            contract["labels"],
            int(contract["evaluation"]["bootstrap_repeats"]),
            f"{contract['evaluation']['bootstrap_seed_namespace']}:{contrast_id}",
        )
        result["decision"] = primary_decision(
            result["observed_delta"], float(contract["evaluation"]["practical_tie_macro_f1"])
        )
        contrasts[contrast_id] = result
    aggregate = {
        "accessed_splits": ["test"],
        "completed_at_utc": utc_now(),
        "contrasts": contrasts,
        "experiment_id": EXPERIMENT_ID,
        "families": families,
        "label_opened_at_utc": labels_opened_at,
        "raw_outputs_stored_publicly": False,
        "resource": {
            "baseline_encoder_seconds": baseline_encoder_seconds,
            "qwen_active_generation_seconds": qwen_active_seconds,
        },
        "rows": len(rows),
        "scored_predictions": artifact(scored_path),
        "status": "Completed; pending independent verification",
        "test_inputs_accessed": True,
        "test_labels_accessed": True,
        "unit_results": artifact(result_path),
        "units": units,
    }
    atomic_json(aggregate_path, aggregate)
    atomic_text(report_path, render_report(aggregate))
    atomic_json(
        label_open_path,
        {**opening_record, "completed_at_utc": utc_now(), "status": "Consumed"},
    )
    run = load_run(contract)
    run["accessed_splits"] = ["test"]
    add_command(run, f"{sys.executable} {display_path(Path(__file__))} finalize")
    run["label_opening"] = {
        "artifact": artifact(label_open_path),
        "opened_at_utc": labels_opened_at,
        "status": "consumed",
    }
    run["stages"]["finalize"] = {
        "aggregate": artifact(aggregate_path),
        "completed_at_utc": utc_now(),
        "report": artifact(report_path),
        "status": "Completed",
    }
    run["status"] = "Completed; pending independent verification"
    run["test_inputs_accessed"] = True
    run["test_labels_accessed"] = True
    save_run(contract, run)
    print(
        json.dumps(
            {
                "contrasts": {key: value["observed_delta"] for key, value in contrasts.items()},
                "status": aggregate["status"],
            },
            sort_keys=True,
        )
    )


def main() -> None:
    args = parse_args()
    contract = load_contract()
    if args.command == "initialize":
        initialize(contract)
    elif args.command == "infer-baseline":
        infer_baseline(contract, args.condition)
    elif args.command == "infer-qwen":
        infer_qwen(contract, args.condition)
    elif args.command == "finalize":
        finalize(contract)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Execute the explicitly authorized, staged EXP-056 held-out test."""

from __future__ import annotations

import argparse
from collections import Counter
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import time
from typing import Any, Sequence

import numpy as np

from test_gate_common import (
    LABELS,
    aggregate_values,
    artifact,
    atomic_json,
    atomic_jsonl,
    canonical_digest,
    dynamic_module,
    load_json,
    load_prediction_npz,
    load_test_inputs,
    load_test_labels_after_prediction_seal,
    metric_bundle,
    require_artifact,
    require_tree,
    resolve_project,
    save_prediction_npz,
    sha256_file,
    sigmoid,
    utc_now,
    verify_authorization,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_DIR / "configs" / "exp-056-test-ready.json"
FAMILIES = ("m1", "m2", "m3", "m4")


def load_contract(path: Path) -> dict[str, Any]:
    contract = load_json(path)
    if contract.get("schema_version") != "exp-056-test-ready-contract-v1":
        raise ValueError("EXP-056 contract schema drift")
    if contract.get("status") != "Frozen TEST-READY; test access not authorized":
        raise ValueError("EXP-056 contract status drift")
    if contract.get("contract_path") != str(path.resolve().relative_to(resolve_project(".").resolve())):
        raise ValueError("EXP-056 contract path drift")
    for record in contract["implementation"].values():
        require_artifact(record)
    return contract


def paths(contract: dict[str, Any]) -> tuple[Path, Path, Path]:
    public = resolve_project(contract["execution"]["public_output_dir"])
    private = resolve_project(contract["execution"]["private_output_dir"])
    authorization = resolve_project(contract["execution"]["authorization"]["path"])
    return public, private, authorization


def state_path(contract: dict[str, Any]) -> Path:
    return paths(contract)[0] / "state.json"


def load_state(contract: dict[str, Any], contract_path: Path) -> dict[str, Any]:
    path = state_path(contract)
    if not path.is_file():
        raise RuntimeError("Run initialize before any prediction stage")
    state = load_json(path)
    if state.get("contract_sha256") != sha256_file(contract_path):
        raise ValueError("Initialized state is bound to a different contract")
    if state.get("experiment_id") != "EXP-056":
        raise ValueError("Initialized state experiment drift")
    return state


def update_state(contract: dict[str, Any], state: dict[str, Any], **changes: Any) -> None:
    state.update(changes)
    state["updated_at_utc"] = utc_now()
    atomic_json(state_path(contract), state)


def initialize(contract_path: Path) -> dict[str, Any]:
    contract = load_contract(contract_path)
    public, private, authorization_path = paths(contract)
    authorization = verify_authorization(contract, authorization_path)
    for output in (public, private):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite formal EXP-056 output: {output}")
    public.mkdir(parents=True)
    private.mkdir(parents=True, mode=0o700)
    os.chmod(private, 0o700)
    state = {
        "schema_version": "exp-056-run-state-v1",
        "experiment_id": "EXP-056",
        "status": "Initialized; labels sealed",
        "initialized_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "contract_sha256": sha256_file(contract_path),
        "authorization": artifact(authorization_path),
        "authorization_scope": authorization["scope"],
        "completed_families": [],
        "prediction_seal_created": False,
        "labels_opened": False,
        "test_inputs_opened": False,
    }
    atomic_json(public / "state.json", state)
    return state


def units_for(contract: dict[str, Any], family: str) -> list[dict[str, Any]]:
    units = [unit for unit in contract["units"] if unit["family"] == family]
    if [unit["seed"] for unit in units] != [42, 43, 44]:
        raise ValueError(f"Frozen unit order drift for {family}")
    return units


def prediction_path(private: Path, unit_id: str) -> Path:
    return private / "predictions" / f"{unit_id}.npz"


def unit_record_path(public: Path, unit_id: str) -> Path:
    return public / "units" / f"{unit_id}.json"


def expected_order(rows: Sequence[dict[str, Any]]) -> tuple[list[str], list[str]]:
    return (
        [str(row["sample_id"]) for row in rows],
        [str(row["component_id"]) for row in rows],
    )


def completed_prefix(
    units: Sequence[dict[str, Any]], public: Path, private: Path,
    sample_ids: Sequence[str], component_ids: Sequence[str], expected_rows: int,
) -> int:
    completed = []
    for unit in units:
        pred_path = prediction_path(private, unit["unit_id"])
        record_path = unit_record_path(public, unit["unit_id"])
        if pred_path.exists() != record_path.exists():
            raise ValueError(f"Incomplete append-only unit pair: {unit['unit_id']}")
        completed.append(pred_path.exists())
        if pred_path.exists():
            payload = load_prediction_npz(pred_path, expected_rows)
            if payload["sample_ids"].tolist() != list(sample_ids):
                raise ValueError(f"Sample order drift in {unit['unit_id']}")
            if payload["component_ids"].tolist() != list(component_ids):
                raise ValueError(f"Component order drift in {unit['unit_id']}")
            record = load_json(record_path)
            if record.get("prediction") != artifact(pred_path):
                raise ValueError(f"Prediction record drift in {unit['unit_id']}")
    if any(completed[index] and not all(completed[:index]) for index in range(len(completed))):
        raise ValueError("Completed predictions are not a contiguous family prefix")
    return sum(completed)


def save_unit(
    contract: dict[str, Any], public: Path, private: Path, unit: dict[str, Any],
    sample_ids: Sequence[str], component_ids: Sequence[str], probabilities: np.ndarray,
    predicted: np.ndarray, resource: dict[str, Any], *, parser_valid: np.ndarray | None = None,
    raw_generations: list[dict[str, Any]] | None = None,
) -> None:
    pred_path = prediction_path(private, unit["unit_id"])
    record_path = unit_record_path(public, unit["unit_id"])
    if pred_path.exists() or record_path.exists():
        raise FileExistsError(f"Refusing to overwrite completed unit: {unit['unit_id']}")
    save_prediction_npz(
        pred_path, sample_ids, component_ids, probabilities, predicted,
        parser_valid=parser_valid,
    )
    raw_record = None
    if raw_generations is not None:
        raw_path = private / "generations" / f"{unit['unit_id']}.jsonl"
        if raw_path.exists():
            raise FileExistsError(raw_path)
        atomic_jsonl(raw_path, raw_generations, private=True)
        raw_record = artifact(raw_path)
    record = {
        "schema_version": "exp-056-unit-prediction-record-v1",
        "experiment_id": "EXP-056",
        "unit_id": unit["unit_id"],
        "family": unit["family"],
        "seed": unit["seed"],
        "rows": contract["data"]["test_rows"],
        "prediction": artifact(pred_path),
        "raw_generations": raw_record,
        "resource": resource,
        "labels_opened": False,
        "completed_at_utc": utc_now(),
    }
    atomic_json(record_path, record)


def infer_m1(
    contract: dict[str, Any], units: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]],
    public: Path, private: Path, start_index: int,
) -> None:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_grad_enabled(False)
    sample_ids, component_ids = expected_order(rows)
    for unit in units[start_index:]:
        checkpoint = require_tree(unit["selected_checkpoint"])
        started = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint, local_files_only=True,
        ).to("cpu").eval()
        batches = []
        for offset in range(0, len(rows), 32):
            encoded = tokenizer(
                [row["text"] for row in rows[offset:offset + 32]],
                padding=True, truncation=True, max_length=256, return_tensors="pt",
            )
            batches.append(torch.sigmoid(model(**encoded).logits).cpu().numpy())
        probabilities = np.concatenate(batches).astype(np.float32)
        predicted = (probabilities >= float(unit["shared_threshold"])).astype(np.uint8)
        save_unit(
            contract, public, private, unit, sample_ids, component_ids,
            probabilities, predicted,
            {"backend": "PyTorch_CPU", "wall_seconds": time.perf_counter() - started,
             "batch_size": 32},
        )
        del model, tokenizer, probabilities, predicted, batches
        gc.collect()


def load_shared(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    shared = load_json(require_artifact(contract["implementation"]["shared_config"]))
    prompt = load_json(require_artifact(contract["implementation"]["prompt"]))
    return shared, prompt


def infer_m2(
    contract: dict[str, Any], units: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]],
    public: Path, private: Path, start_index: int,
) -> None:
    import mlx.core as mx
    from mlx_lm import load

    shared, prompt = load_shared(contract)
    reference = dynamic_module(
        "exp056_m2_reference", require_artifact(contract["implementation"]["m2_reference"])
    )
    sample_ids, component_ids = expected_order(rows)
    mx.reset_peak_memory()
    started = time.perf_counter()
    model, tokenizer = load(str(resolve_project(contract["models"]["qwen_local_path"])), lazy=False)
    model.freeze()
    model.eval()
    features = np.empty((len(rows), int(shared["models"]["qwen_shared"]["hidden_size"])), dtype=np.float32)
    token_lengths = []
    truncated = 0
    limit = int(shared["prompt"]["max_sequence_length"])
    for index, row in enumerate(rows):
        ids, _, was_truncated = reference.qwen_prompt_ids(tokenizer, prompt, row["text"], limit)
        hidden = model.model(mx.array([ids], dtype=mx.int32))
        pooled = hidden[:, -1, :].astype(mx.float32)
        mx.eval(pooled)
        features[index] = np.asarray(pooled)[0]
        token_lengths.append(len(ids))
        truncated += int(was_truncated)
        if (index + 1) % 100 == 0:
            mx.clear_cache()
    feature_seconds = time.perf_counter() - started
    for unit in units[start_index:]:
        unit_started = time.perf_counter()
        head_path = require_artifact(unit["selected_head"])
        head = reference.build_head(int(unit["seed"]), features.shape[1])
        head.load_weights(str(head_path), strict=True)
        logits = head(mx.array(features)).astype(mx.float32)
        mx.eval(logits)
        probabilities = sigmoid(np.asarray(logits))
        predicted = (probabilities >= float(unit["shared_threshold"])).astype(np.uint8)
        save_unit(
            contract, public, private, unit, sample_ids, component_ids,
            probabilities, predicted,
            {"backend": "MLX_Apple_Metal", "shared_feature_seconds": feature_seconds,
             "head_seconds": time.perf_counter() - unit_started,
             "peak_memory_gb": float(mx.get_peak_memory()) / 1e9,
             "token_length_maximum": max(token_lengths), "truncated_rows": truncated},
        )
        del head, logits, probabilities, predicted
    del model, tokenizer, features
    gc.collect()
    mx.clear_cache()


def initialize_lora_model(
    contract: dict[str, Any], unit: dict[str, Any], shared: dict[str, Any],
    *, with_head: bool,
) -> dict[str, Any]:
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers

    primitives = dynamic_module(
        f"exp056_primitives_{unit['unit_id']}",
        require_artifact(contract["implementation"]["qwen_primitives"]),
    )
    model, tokenizer = load(str(resolve_project(contract["models"]["qwen_local_path"])), lazy=False)
    model.freeze()
    model.eval()
    head = None
    if with_head:
        head = primitives.build_qwen_head(
            int(unit["seed"]), int(shared["models"]["qwen_shared"]["hidden_size"])
        )
    lora = shared["models"]["lora_shared"]
    mx.random.seed(int(unit["seed"]) + 100000)
    linear_to_lora_layers(model, int(lora["num_layers"]), {
        "rank": lora["rank"], "scale": lora["scale"], "dropout": lora["dropout"],
        "keys": lora["target_modules"],
    })
    observed = primitives.insertion_contract(model, shared)
    initial_digest = primitives.mlx_tensor_digest(primitives.mlx_trainable(model))
    if len(observed) != 112 or initial_digest != unit["expected_lora_initial_sha256"]:
        raise ValueError(f"LoRA insertion/initialization drift: {unit['unit_id']}")
    model.load_weights(str(require_artifact(unit["selected_adapter"])), strict=False)
    model.eval()
    if head is not None:
        head.load_weights(str(require_artifact(unit["selected_head"])), strict=True)
        head.eval()
    return {"model": model, "tokenizer": tokenizer, "head": head, "primitives": primitives}


def infer_m3(
    contract: dict[str, Any], units: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]],
    public: Path, private: Path, start_index: int,
) -> None:
    import mlx.core as mx

    shared, prompt = load_shared(contract)
    reference = dynamic_module(
        "exp056_m3_reference", require_artifact(contract["implementation"]["m3_reference"])
    )
    sample_ids, component_ids = expected_order(rows)
    for unit in units[start_index:]:
        mx.reset_peak_memory()
        started = time.perf_counter()
        initialized = initialize_lora_model(contract, unit, shared, with_head=True)
        token_ids, token_summary = reference.tokenize_rows(
            initialized["tokenizer"], prompt, rows,
            int(shared["prompt"]["max_sequence_length"]),
        )
        wrapper = initialized["primitives"].make_classification_wrapper(
            initialized["model"], initialized["head"]
        )
        logits = np.empty((len(rows), len(LABELS)), dtype=np.float32)
        for index, ids in enumerate(token_ids):
            value = wrapper(mx.array([ids], dtype=mx.int32)).astype(mx.float32)
            mx.eval(value)
            logits[index] = np.asarray(value)[0]
            if (index + 1) % 100 == 0:
                mx.clear_cache()
        probabilities = sigmoid(logits)
        predicted = (probabilities >= float(unit["shared_threshold"])).astype(np.uint8)
        peak = float(mx.get_peak_memory()) / 1e9
        if peak > float(contract["execution"]["maximum_mlx_peak_memory_gb"]):
            raise MemoryError(f"M3 memory budget exceeded: {unit['unit_id']}")
        save_unit(
            contract, public, private, unit, sample_ids, component_ids,
            probabilities, predicted,
            {"backend": "MLX_Apple_Metal", "wall_seconds": time.perf_counter() - started,
             "peak_memory_gb": peak, "tokenization": token_summary},
        )
        del initialized, wrapper, logits, probabilities, predicted, token_ids
        gc.collect()
        mx.clear_cache()


def infer_m4(
    contract: dict[str, Any], units: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]],
    public: Path, private: Path, start_index: int,
) -> None:
    import mlx.core as mx
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    shared, prompt = load_shared(contract)
    reference = dynamic_module(
        "exp056_m4_reference", require_artifact(contract["implementation"]["m4_reference"])
    )
    parser = dynamic_module(
        "exp056_strict_parser", require_artifact(contract["implementation"]["parser"])
    )
    sample_ids, component_ids = expected_order(rows)
    sampler = make_sampler(temp=0.0)
    max_tokens = int(shared["models"]["m4"]["generation"]["max_new_tokens"])
    for unit in units[start_index:]:
        mx.reset_peak_memory()
        started = time.perf_counter()
        initialized = initialize_lora_model(contract, unit, shared, with_head=False)
        token_ids, token_summary = reference.preprocess_generation_rows(
            initialized["tokenizer"], prompt, rows,
            int(shared["prompt"]["max_sequence_length"]),
        )
        predicted = np.zeros((len(rows), len(LABELS)), dtype=np.uint8)
        valid = np.zeros(len(rows), dtype=np.uint8)
        raw_rows = []
        latencies = []
        token_counts = []
        outcomes: Counter[str] = Counter()
        for index, (row, ids) in enumerate(zip(rows, token_ids)):
            row_started = time.perf_counter()
            raw = generate(
                initialized["model"], initialized["tokenizer"], prompt=ids,
                max_tokens=max_tokens, sampler=sampler, verbose=False,
            )
            latency = time.perf_counter() - row_started
            parsed = parser.parse_output(raw, LABELS)
            predicted[index] = np.asarray(parsed["vector"], dtype=np.uint8)
            valid[index] = int(parsed["valid"])
            generated_tokens = len(initialized["tokenizer"].encode(raw, add_special_tokens=False))
            latencies.append(latency)
            token_counts.append(generated_tokens)
            outcomes[parsed["error"] or "valid"] += 1
            raw_rows.append({
                "row_index": index, "sample_id": row["sample_id"],
                "component_id": row["component_id"], "raw_output": raw,
                "parsed": parsed, "generated_tokens_before_eos": generated_tokens,
                "generation_latency_seconds": latency,
            })
        elapsed = time.perf_counter() - started
        if elapsed > float(contract["execution"]["maximum_m4_generation_hours_per_seed"]) * 3600:
            raise TimeoutError(f"M4 generation budget exceeded: {unit['unit_id']}")
        peak = float(mx.get_peak_memory()) / 1e9
        if peak > float(contract["execution"]["maximum_mlx_peak_memory_gb"]):
            raise MemoryError(f"M4 memory budget exceeded: {unit['unit_id']}")
        save_unit(
            contract, public, private, unit, sample_ids, component_ids,
            predicted.astype(np.float32), predicted,
            {"backend": "MLX_Apple_Metal", "wall_seconds": elapsed,
             "peak_memory_gb": peak, "tokenization": token_summary,
             "parser_valid_count": int(valid.sum()),
             "parser_valid_rate": float(valid.mean()),
             "parser_outcomes": dict(sorted(outcomes.items())),
             "latency_seconds_mean": float(np.mean(latencies)),
             "generated_tokens_mean": float(np.mean(token_counts)),
             "throughput_rows_per_second": len(rows) / elapsed if elapsed else 0.0,
             "probability_semantics": "hard_label_indicator_not_confidence"},
            parser_valid=valid, raw_generations=raw_rows,
        )
        del initialized, token_ids, predicted, valid, raw_rows
        gc.collect()
        mx.clear_cache()


def predict_family(contract_path: Path, family: str) -> dict[str, Any]:
    if family not in FAMILIES:
        raise ValueError(f"Unknown family: {family}")
    os.environ.update({
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
    })
    contract = load_contract(contract_path)
    public, private, authorization_path = paths(contract)
    verify_authorization(contract, authorization_path)
    state = load_state(contract, contract_path)
    if state.get("prediction_seal_created") or state.get("labels_opened"):
        raise RuntimeError("Predictions are already sealed or labels have been opened")
    rows = load_test_inputs(contract, authorization_path)
    sample_ids, component_ids = expected_order(rows)
    units = units_for(contract, family)
    prefix = completed_prefix(
        units, public, private, sample_ids, component_ids, contract["data"]["test_rows"]
    )
    if prefix < 3:
        {"m1": infer_m1, "m2": infer_m2, "m3": infer_m3, "m4": infer_m4}[family](
            contract, units, rows, public, private, prefix
        )
    manifest_path = public / "families" / f"{family}.json"
    if not manifest_path.exists():
        atomic_json(manifest_path, {
            "schema_version": "exp-056-family-prediction-manifest-v1",
            "experiment_id": "EXP-056", "family": family,
            "unit_ids": [unit["unit_id"] for unit in units],
            "unit_records": [artifact(unit_record_path(public, unit["unit_id"])) for unit in units],
            "labels_opened": False, "completed_at_utc": utc_now(),
        })
    completed = list(state.get("completed_families", []))
    if family not in completed:
        completed.append(family)
    completed.sort(key=FAMILIES.index)
    update_state(
        contract, state, status="Predictions in progress; labels sealed",
        completed_families=completed, test_inputs_opened=True,
    )
    return {"family": family, "completed_units": 3, "labels_opened": False}


def seal_predictions(contract_path: Path) -> dict[str, Any]:
    contract = load_contract(contract_path)
    public, private, authorization_path = paths(contract)
    verify_authorization(contract, authorization_path)
    state = load_state(contract, contract_path)
    seal_path = public / "prediction-seal.json"
    if seal_path.exists():
        raise FileExistsError("Prediction seal already exists")
    if state.get("labels_opened"):
        raise RuntimeError("Cannot seal predictions after labels were opened")
    records = []
    expected_sample_ids = None
    expected_component_ids = None
    for unit_id in contract["unit_order"]:
        path = prediction_path(private, unit_id)
        payload = load_prediction_npz(path, contract["data"]["test_rows"])
        sample_ids = payload["sample_ids"].tolist()
        component_ids = payload["component_ids"].tolist()
        if expected_sample_ids is None:
            expected_sample_ids, expected_component_ids = sample_ids, component_ids
        if sample_ids != expected_sample_ids or component_ids != expected_component_ids:
            raise ValueError(f"Prediction row order drift: {unit_id}")
        records.append({"unit_id": unit_id, "prediction": artifact(path)})
    seal = {
        "schema_version": "exp-056-prediction-seal-v1",
        "experiment_id": "EXP-056",
        "status": "Predictions sealed before labels opened",
        "contract_sha256": sha256_file(contract_path),
        "unit_ids": contract["unit_order"],
        "predictions": records,
        "sample_order_sha256": canonical_digest(expected_sample_ids),
        "component_order_sha256": canonical_digest(expected_component_ids),
        "labels_opened": False,
        "sealed_at_utc": utc_now(),
    }
    atomic_json(seal_path, seal)
    update_state(
        contract, state, status="All 12 predictions sealed; labels unopened",
        prediction_seal_created=True,
    )
    return seal


def bootstrap_contrast(
    gold: np.ndarray, component_ids: Sequence[str], predictions_a: Sequence[np.ndarray],
    predictions_b: Sequence[np.ndarray], comparison: str, replicates: int,
) -> tuple[dict[str, Any], np.ndarray]:
    components = sorted(set(component_ids))
    groups = {component: np.flatnonzero(np.asarray(component_ids) == component) for component in components}
    seed_material = f"EXP-056-component-bootstrap-v1|{comparison}"
    seed = int.from_bytes(hashlib.sha256(seed_material.encode()).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    values = np.empty((replicates, 2), dtype=np.float64)
    for replicate in range(replicates):
        selected = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in selected])
        for metric_index, metric_name in enumerate(("macro_f1", "five_label_macro_f1_without_surprise")):
            a = np.mean([metric_bundle(gold[indices], pred[indices])[metric_name] for pred in predictions_a])
            b = np.mean([metric_bundle(gold[indices], pred[indices])[metric_name] for pred in predictions_b])
            values[replicate, metric_index] = b - a
    point = {}
    for metric_name in ("macro_f1", "five_label_macro_f1_without_surprise"):
        a = np.mean([metric_bundle(gold, pred)[metric_name] for pred in predictions_a])
        b = np.mean([metric_bundle(gold, pred)[metric_name] for pred in predictions_b])
        point[metric_name] = float(b - a)
    return {
        "comparison": comparison, "orientation": "second_family_minus_first_family",
        "unit": "duplicate_component_id", "components": len(components),
        "rows": len(component_ids), "replicates": replicates,
        "seed": seed, "seed_material": seed_material,
        "macro_f1": {
            "point": point["macro_f1"],
            "lower": float(np.quantile(values[:, 0], 0.025, method="linear")),
            "upper": float(np.quantile(values[:, 0], 0.975, method="linear")),
        },
        "five_label_macro_f1_without_surprise": {
            "point": point["five_label_macro_f1_without_surprise"],
            "lower": float(np.quantile(values[:, 1], 0.025, method="linear")),
            "upper": float(np.quantile(values[:, 1], 0.975, method="linear")),
        },
    }, values


def score(contract_path: Path) -> dict[str, Any]:
    contract = load_contract(contract_path)
    public, private, authorization_path = paths(contract)
    verify_authorization(contract, authorization_path)
    state = load_state(contract, contract_path)
    results_path = public / "results.json"
    if results_path.exists():
        raise RuntimeError("EXP-056 has already been scored")
    seal_path = public / "prediction-seal.json"
    seal = load_json(seal_path)
    reference = load_prediction_npz(
        prediction_path(private, contract["unit_order"][0]), contract["data"]["test_rows"]
    )
    sample_ids = reference["sample_ids"].tolist()
    component_ids = reference["component_ids"].tolist()
    score_input_path = private / "score-input.npz"
    if state.get("labels_opened"):
        score_input_record = state.get("score_input")
        if not isinstance(score_input_record, dict):
            raise RuntimeError("Labels were opened but no frozen scoring input was retained")
        require_artifact(score_input_record)
        with np.load(score_input_path, allow_pickle=False) as source:
            gold = source["gold"]
            frozen_sample_ids = source["sample_ids"].tolist()
            frozen_component_ids = source["component_ids"].tolist()
        if frozen_sample_ids != sample_ids or frozen_component_ids != component_ids:
            raise ValueError("Frozen scoring input order drift")
    else:
        labels = load_test_labels_after_prediction_seal(contract, authorization_path, seal)
        label_ids = [row["sample_id"] for row in labels]
        if label_ids != sample_ids:
            raise ValueError("Sealed label and prediction sample order drift")
        gold = np.asarray([row["labels"] for row in labels], dtype=np.uint8)
        np.savez_compressed(
            score_input_path, gold=gold, sample_ids=reference["sample_ids"],
            component_ids=reference["component_ids"],
        )
        os.chmod(score_input_path, 0o600)
        update_state(
            contract, state,
            status="Scoring in progress from sealed predictions and frozen scoring input",
            labels_opened=True, labels_opened_at_utc=utc_now(),
            score_input=artifact(score_input_path),
        )
        state = load_state(contract, contract_path)
    if gold.shape != (contract["data"]["test_rows"], len(LABELS)):
        raise ValueError("Frozen scoring input shape drift")
    predictions: dict[str, np.ndarray] = {}
    unit_results: dict[str, Any] = {}
    for unit_id in contract["unit_order"]:
        payload = load_prediction_npz(
            prediction_path(private, unit_id), contract["data"]["test_rows"]
        )
        if payload["sample_ids"].tolist() != sample_ids or payload["component_ids"].tolist() != component_ids:
            raise ValueError(f"Scoring order drift: {unit_id}")
        predictions[unit_id] = payload["predicted"]
        metrics = metric_bundle(gold, payload["predicted"])
        record = load_json(unit_record_path(public, unit_id))
        unit_results[unit_id] = {
            "family": record["family"], "seed": record["seed"],
            "metrics": metrics, "resource": record["resource"],
        }
        if record["family"] == "m4":
            unit_results[unit_id]["parser_valid_rate"] = float(payload["parser_valid"].mean())

    family_results: dict[str, Any] = {}
    aggregate_metrics = (
        "macro_f1", "five_label_macro_f1_without_surprise", "micro_f1", "weighted_f1",
        "macro_precision", "macro_recall", "subset_accuracy", "hamming_loss",
        "empty_prediction_rate", "predicted_label_cardinality_mean",
    )
    for family in FAMILIES:
        ids = [f"{family}-seed-{seed}" for seed in (42, 43, 44)]
        family_results[family] = {
            "unit_ids": ids,
            "metrics": {
                name: aggregate_values([unit_results[unit_id]["metrics"][name] for unit_id in ids])
                for name in aggregate_metrics
            },
            "per_label_f1": {
                label: aggregate_values([
                    unit_results[unit_id]["metrics"]["per_label"][label]["f1"] for unit_id in ids
                ]) for label in LABELS
            },
        }

    contrasts: dict[str, Any] = {}
    bootstrap_payload: dict[str, np.ndarray] = {}
    for comparison in contract["evaluation"]["paired_contrasts"]:
        second, first = comparison.split("-")
        first_ids = [f"{first}-seed-{seed}" for seed in (42, 43, 44)]
        second_ids = [f"{second}-seed-{seed}" for seed in (42, 43, 44)]
        paired = {}
        for metric_name in ("macro_f1", "five_label_macro_f1_without_surprise"):
            deltas = [
                unit_results[b]["metrics"][metric_name] - unit_results[a]["metrics"][metric_name]
                for a, b in zip(first_ids, second_ids)
            ]
            paired[metric_name] = aggregate_values(deltas)
        bootstrap, replicate_values = bootstrap_contrast(
            gold, component_ids, [predictions[key] for key in first_ids],
            [predictions[key] for key in second_ids], comparison,
            int(contract["evaluation"]["bootstrap"]["replicates"]),
        )
        contrasts[comparison] = {"paired_seed_delta": paired, "component_bootstrap": bootstrap}
        bootstrap_payload[comparison.replace("-", "_")] = replicate_values

    evidence_path = private / "score-evidence.npz"
    evidence_payload: dict[str, np.ndarray] = {
        "gold": gold, "sample_ids": reference["sample_ids"],
        "component_ids": reference["component_ids"],
    }
    for unit_id, predicted in predictions.items():
        evidence_payload[f"pred__{unit_id.replace('-', '_')}"] = predicted
    np.savez_compressed(evidence_path, **evidence_payload)
    os.chmod(evidence_path, 0o600)
    bootstrap_path = private / "bootstrap-replicates.npz"
    np.savez_compressed(bootstrap_path, **bootstrap_payload)
    os.chmod(bootstrap_path, 0o600)
    results = {
        "schema_version": "exp-056-frozen-test-results-v1",
        "experiment_id": "EXP-056", "status": "Completed",
        "completed_at_utc": utc_now(), "contract_sha256": sha256_file(contract_path),
        "prediction_seal": artifact(seal_path),
        "test_rows": contract["data"]["test_rows"],
        "labels_opened_after_prediction_seal": True,
        "private_score_input": artifact(score_input_path),
        "test_label_record": contract["data"]["test_labels"],
        "unit_results": unit_results, "family_results": family_results,
        "paired_contrasts": contrasts,
        "private_score_evidence": artifact(evidence_path),
        "private_bootstrap_replicates": artifact(bootstrap_path),
        "surprise_claim_boundary": (
            "surprise has seven test positives and cannot alone support a broad family claim"
        ),
        "selection_or_tuning_after_test": False,
    }
    atomic_json(results_path, results)
    update_state(
        contract, state, status="Completed; test labels opened only after prediction seal",
        labels_opened=True, scored_at_utc=utc_now(),
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    subparsers = parser.add_subparsers(dest="stage", required=True)
    subparsers.add_parser("initialize")
    predict = subparsers.add_parser("predict-family")
    predict.add_argument("--family", choices=FAMILIES, required=True)
    subparsers.add_parser("seal-predictions")
    subparsers.add_parser("score")
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    started = time.perf_counter()
    if args.stage == "initialize":
        result = initialize(contract_path)
    elif args.stage == "predict-family":
        result = predict_family(contract_path, args.family)
    elif args.stage == "seal-predictions":
        result = seal_predictions(contract_path)
    else:
        result = score(contract_path)
    print(json.dumps({
        "stage": args.stage, "wall_seconds": time.perf_counter() - started,
        "result": result,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Score sealed classifier-free SQMA-005 Agent-Tune system outputs.

Importing this module performs no I/O.  The scorer consumes only a sealed
systems NPZ and the SQMA-004 consumer-gold NPZ; raw calls are verifier-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import stat
from typing import Any, Mapping, Sequence
import zipfile


LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
SYSTEMS = ("s1", "s2a", "s2b", "s3")
GOLD_ARRAYS = {"sample_ids", "component_ids", "fold_ids", "source_ordinals", "gold"}
SYSTEM_ARRAYS = {
    "sample_ids", "component_ids", "fold_ids", "source_ordinals",
    "s1", "s2a", "s2b", "s3",
    "single_valid", "role_valid", "single_abstained", "judge_abstained", "s2b_k",
    "s3_ceiling_tokens", "s2b_ceiling_tokens", "s2b_ceiling_utilization",
    "s3_actual_tokens", "s2b_actual_tokens",
}
EXPECTED_ROWS = 672
EXPECTED_CALLS = 4032
EXPECTED_GENERATED_CEILING = 1_161_216
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260903
BOOTSTRAP_ALGORITHM = "python_random_mt19937_component_resampling_v1"
BOOTSTRAP_NAMESPACE = "SQMA-D0-component-bootstrap-v1"
TUNE_GATE = {
    "s3_minus_s2b_six_point_minimum": 0.010,
    "s3_minus_s2b_six_q05_strictly_greater_than": 0.0,
    "s3_minus_s2b_five_point_minimum": -0.005,
    "s3_minus_s2b_hamming_q95_maximum": 0.0025,
    "s3_minus_s2a_six_q05_minimum": -0.005,
    "s3_minus_s2a_hamming_q95_maximum": 0.0025,
}
PUBLIC_SENSITIVE_KEYS = {
    "sample_id", "sample_ids", "component_id", "component_ids", "source_ordinals",
    "gold", "text", "raw_output", "parsed_output",
}


class ScoringError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScoringError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_list(value: Any) -> Any:
    return value.tolist() if hasattr(value, "tolist") else value


def bit_matrix(value: Any, rows: int, name: str) -> list[list[int]]:
    matrix = as_list(value)
    require(isinstance(matrix, list) and len(matrix) == rows, f"{name} row drift")
    result: list[list[int]] = []
    for row in matrix:
        require(isinstance(row, list) and len(row) == len(LABEL_ORDER), f"{name} width drift")
        require(all(type(item) in (bool, int) and int(item) in (0, 1) for item in row), f"{name} bit drift")
        result.append([int(item) for item in row])
    return result


def vector(value: Any, rows: int, name: str, *, kind: type) -> list[Any]:
    values = as_list(value)
    require(isinstance(values, list) and len(values) == rows, f"{name} shape drift")
    require(all(type(item) is kind for item in values), f"{name} type drift")
    return values


def validate_payloads(
    gold: Mapping[str, Any], systems: Mapping[str, Any], *, expected_rows: int = 672
) -> tuple[dict[str, Any], dict[str, Any]]:
    require(set(gold) == GOLD_ARRAYS, "consumer-gold inventory drift")
    require(set(systems) == SYSTEM_ARRAYS, "systems inventory drift")
    normalized_gold = {
        "sample_ids": vector(gold["sample_ids"], expected_rows, "gold.sample_ids", kind=str),
        "component_ids": vector(gold["component_ids"], expected_rows, "gold.component_ids", kind=str),
        "fold_ids": vector(gold["fold_ids"], expected_rows, "gold.fold_ids", kind=int),
        "source_ordinals": vector(gold["source_ordinals"], expected_rows, "gold.source_ordinals", kind=int),
        "gold": bit_matrix(gold["gold"], expected_rows, "gold.gold"),
    }
    normalized_systems: dict[str, Any] = {
        "sample_ids": vector(systems["sample_ids"], expected_rows, "systems.sample_ids", kind=str),
        "component_ids": vector(systems["component_ids"], expected_rows, "systems.component_ids", kind=str),
        "fold_ids": vector(systems["fold_ids"], expected_rows, "systems.fold_ids", kind=int),
        "source_ordinals": vector(systems["source_ordinals"], expected_rows, "systems.source_ordinals", kind=int),
    }
    for system in SYSTEMS:
        normalized_systems[system] = bit_matrix(systems[system], expected_rows, system)
    for name, width in (("single_valid", 3), ("role_valid", 3), ("single_abstained", 3)):
        value = as_list(systems[name])
        require(isinstance(value, list) and len(value) == expected_rows, f"{name} row drift")
        require(all(isinstance(row, list) and len(row) == width and all(type(item) in (bool, int) and int(item) in (0, 1) for item in row) for row in value), f"{name} drift")
        normalized_systems[name] = [[int(item) for item in row] for row in value]
    normalized_systems["judge_abstained"] = [int(item) for item in vector(systems["judge_abstained"], expected_rows, "judge_abstained", kind=int)]
    require(all(value in (0, 1) for value in normalized_systems["judge_abstained"]), "judge_abstained bit drift")
    normalized_systems["s2b_k"] = vector(systems["s2b_k"], expected_rows, "s2b_k", kind=int)
    require(all(value in (2, 3) for value in normalized_systems["s2b_k"]), "s2b_k drift")
    utilization = as_list(systems["s2b_ceiling_utilization"])
    require(isinstance(utilization, list) and len(utilization) == expected_rows, "S2b utilization shape drift")
    require(
        all(type(value) is float and math.isfinite(value) for value in utilization),
        "S2b utilization type drift",
    )
    normalized_systems["s2b_ceiling_utilization"] = utilization
    for name in ("s3_ceiling_tokens", "s2b_ceiling_tokens", "s3_actual_tokens", "s2b_actual_tokens"):
        normalized_systems[name] = vector(systems[name], expected_rows, name, kind=int)
        require(all(value >= 0 for value in normalized_systems[name]), f"{name} negative")
    require(
        normalized_gold["sample_ids"] == normalized_systems["sample_ids"]
        and normalized_gold["component_ids"] == normalized_systems["component_ids"]
        and normalized_gold["fold_ids"] == normalized_systems["fold_ids"]
        and normalized_gold["source_ordinals"] == normalized_systems["source_ordinals"],
        "gold/systems row identity drift",
    )
    require(all(value == 3 for value in normalized_gold["fold_ids"]), "Tune fold drift")
    require(len(set(normalized_gold["sample_ids"])) == expected_rows, "Tune sample identity drift")
    require(
        normalized_gold["source_ordinals"] == sorted(normalized_gold["source_ordinals"])
        and len(set(normalized_gold["source_ordinals"])) == expected_rows,
        "Tune order drift",
    )
    for index in range(expected_rows):
        require(normalized_systems["s2b_ceiling_tokens"][index] <= normalized_systems["s3_ceiling_tokens"][index], "S2b ceiling exceeds S3")
        expected_utilization = (
            normalized_systems["s2b_ceiling_tokens"][index]
            / normalized_systems["s3_ceiling_tokens"][index]
        )
        require(
            math.isclose(
                normalized_systems["s2b_ceiling_utilization"][index],
                expected_utilization,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and 0.9 <= expected_utilization <= 1.0,
            "S2b utilization drift",
        )
        require(normalized_systems["s3_actual_tokens"][index] <= normalized_systems["s3_ceiling_tokens"][index], "S3 actual exceeds ceiling")
        require(normalized_systems["s2b_actual_tokens"][index] <= normalized_systems["s2b_ceiling_tokens"][index], "S2b actual exceeds ceiling")
    return normalized_gold, normalized_systems


def safe_f1(tp: int, fp: int, fn: int) -> float:
    denominator = 2 * tp + fp + fn
    return 0.0 if denominator == 0 else 2 * tp / denominator


def metric_bundle(truth: Sequence[Sequence[int]], predicted: Sequence[Sequence[int]]) -> dict[str, Any]:
    require(len(truth) == len(predicted) and len(truth) > 0, "metric row drift")
    per_label: dict[str, Any] = {}
    label_f1: list[float] = []
    total_tp = total_fp = total_fn = mismatches = exact_rows = 0
    for label_index, label in enumerate(LABEL_ORDER):
        tp = fp = fn = support = predicted_positive = 0
        for target, output in zip(truth, predicted, strict=True):
            actual = int(target[label_index]); guess = int(output[label_index])
            support += actual; predicted_positive += guess
            tp += actual & guess; fp += (1 - actual) & guess; fn += actual & (1 - guess)
        precision = 0.0 if tp + fp == 0 else tp / (tp + fp)
        recall = 0.0 if tp + fn == 0 else tp / (tp + fn)
        f1 = safe_f1(tp, fp, fn)
        label_f1.append(f1); total_tp += tp; total_fp += fp; total_fn += fn
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support, "predicted_positive": predicted_positive}
    for target, output in zip(truth, predicted, strict=True):
        mismatches += sum(int(a) != int(b) for a, b in zip(target, output, strict=True))
        exact_rows += int(list(target) == list(output))
    return {
        "six_label_macro_f1": sum(label_f1) / 6,
        "five_label_macro_f1_without_surprise": sum(value for index, value in enumerate(label_f1) if index != 2) / 5,
        "hamming_loss": mismatches / (len(truth) * 6),
        "micro_f1": safe_f1(total_tp, total_fp, total_fn),
        "subset_accuracy": exact_rows / len(truth),
        "per_label": per_label,
    }


def nearest_rank(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(probability * len(ordered)) - 1))]


def distribution_summary(values: Sequence[float]) -> dict[str, float]:
    require(bool(values), "empty bootstrap distribution")
    return {"q025": nearest_rank(values, 0.025), "q05": nearest_rank(values, 0.05), "median": nearest_rank(values, 0.5), "q95": nearest_rank(values, 0.95), "q975": nearest_rank(values, 0.975)}


def component_bootstrap(
    truth: Sequence[Sequence[int]], predictions: Mapping[str, Sequence[Sequence[int]]],
    component_ids: Sequence[str], *, replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    require(replicates > 0 and len(truth) == len(component_ids), "bootstrap contract drift")
    component_order = list(dict.fromkeys(component_ids))
    rows_by_component = {component: [index for index, value in enumerate(component_ids) if value == component] for component in component_order}
    rng = random.Random(seed)
    metric_names = ("six_label_macro_f1", "five_label_macro_f1_without_surprise", "hamming_loss", "micro_f1", "subset_accuracy")
    system_values = {system: {metric: [] for metric in metric_names} for system in SYSTEMS}
    contrast_values = {contrast: {metric: [] for metric in metric_names} for contrast in ("s3_minus_s2a", "s3_minus_s2b")}
    for _ in range(replicates):
        sampled = [component_order[rng.randrange(len(component_order))] for _ in component_order]
        indices = [index for component in sampled for index in rows_by_component[component]]
        sampled_truth = [truth[index] for index in indices]
        replicate_metrics = {}
        for system in SYSTEMS:
            replicate_metrics[system] = metric_bundle(sampled_truth, [predictions[system][index] for index in indices])
            for metric in metric_names:
                system_values[system][metric].append(replicate_metrics[system][metric])
        for baseline in ("s2a", "s2b"):
            contrast = f"s3_minus_{baseline}"
            for metric in metric_names:
                contrast_values[contrast][metric].append(replicate_metrics["s3"][metric] - replicate_metrics[baseline][metric])
    return (
        {system: {metric: distribution_summary(values) for metric, values in metrics.items()} for system, metrics in system_values.items()},
        {contrast: {metric: distribution_summary(values) for metric, values in metrics.items()} for contrast, metrics in contrast_values.items()},
    )


def evaluate_tune_gate(contrasts: Mapping[str, Any], integrity: Mapping[str, bool]) -> dict[str, Any]:
    s2b = contrasts["s3_minus_s2b"]; s2a = contrasts["s3_minus_s2a"]
    checks = {
        "all_schema_budget_resource_checks": bool(integrity) and all(value is True for value in integrity.values()),
        "s3_minus_s2b_six_point": s2b["point"]["six_label_macro_f1"] >= TUNE_GATE["s3_minus_s2b_six_point_minimum"],
        "s3_minus_s2b_six_q05": s2b["bootstrap"]["six_label_macro_f1"]["q05"] > TUNE_GATE["s3_minus_s2b_six_q05_strictly_greater_than"],
        "s3_minus_s2b_five_point": s2b["point"]["five_label_macro_f1_without_surprise"] >= TUNE_GATE["s3_minus_s2b_five_point_minimum"],
        "s3_minus_s2b_hamming_q95": s2b["bootstrap"]["hamming_loss"]["q95"] <= TUNE_GATE["s3_minus_s2b_hamming_q95_maximum"],
        "s3_minus_s2a_six_q05": s2a["bootstrap"]["six_label_macro_f1"]["q05"] >= TUNE_GATE["s3_minus_s2a_six_q05_minimum"],
        "s3_minus_s2a_hamming_q95": s2a["bootstrap"]["hamming_loss"]["q95"] <= TUNE_GATE["s3_minus_s2a_hamming_q95_maximum"],
    }
    return {"passed": all(checks.values()), "checks": checks, "thresholds": dict(TUNE_GATE), "failure_action": "stop_without_confirm_or_selective"}


def score_payloads(
    gold: Mapping[str, Any], systems: Mapping[str, Any], *, expected_rows: int = 672,
    replicates: int = BOOTSTRAP_REPLICATES, seed: int = BOOTSTRAP_SEED,
    integrity: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    gold_values, system_values = validate_payloads(gold, systems, expected_rows=expected_rows)
    point = {system: metric_bundle(gold_values["gold"], system_values[system]) for system in SYSTEMS}
    system_bootstrap, contrast_bootstrap = component_bootstrap(gold_values["gold"], {system: system_values[system] for system in SYSTEMS}, gold_values["component_ids"], replicates=replicates, seed=seed)
    metric_names = ("six_label_macro_f1", "five_label_macro_f1_without_surprise", "hamming_loss", "micro_f1", "subset_accuracy")
    contrasts = {}
    for baseline in ("s2a", "s2b"):
        name = f"s3_minus_{baseline}"
        contrasts[name] = {"point": {metric: point["s3"][metric] - point[baseline][metric] for metric in metric_names}, "bootstrap": contrast_bootstrap[name]}
    integrity = dict(integrity or {"schema": True, "budget": True, "resource": True})
    result = {
        "schema_version": "sqma-005-score-v1", "experiment_id": "SQMA-005",
        "rows": expected_rows, "components": len(set(gold_values["component_ids"])),
        "label_order": list(LABEL_ORDER),
        "systems": {system: {"point": point[system], "bootstrap": system_bootstrap[system]} for system in SYSTEMS},
        "contrasts": contrasts,
        "bootstrap": {"unit": "duplicate_component_id", "replicates": replicates, "seed": seed, "namespace": BOOTSTRAP_NAMESPACE, "algorithm": BOOTSTRAP_ALGORITHM, "paired_multiplicities": True, "zero_division": 0},
        "integrity": integrity,
    }
    result["tune_gate"] = evaluate_tune_gate(contrasts, integrity)
    require(not public_sensitive_paths(result), "score contains row-level material")
    return result


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (value.startswith("sample-") or value.startswith("component-")):
        violations.append(prefix)
    return violations


def load_npz(path: Path, expected: set[str]) -> dict[str, Any]:
    import numpy as np
    require(path.is_file() and not path.is_symlink(), "NPZ missing or linked")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "NPZ duplicate member")
        require(set(names) == {f"{name}.npy" for name in expected}, "NPZ member drift")
    with np.load(path, allow_pickle=False) as source:
        require(set(source.files) == expected, "NPZ inventory drift")
        arrays = {name: np.asarray(source[name]) for name in source.files}
    rows = EXPECTED_ROWS
    if expected == GOLD_ARRAYS:
        expected_layout = {
            "sample_ids": ((rows,), "U"), "component_ids": ((rows,), "U"),
            "fold_ids": ((rows,), "int8"), "source_ordinals": ((rows,), "int32"),
            "gold": ((rows, 6), "uint8"),
        }
    else:
        expected_layout = {
            "sample_ids": ((rows,), "U"), "component_ids": ((rows,), "U"),
            "fold_ids": ((rows,), "int8"), "source_ordinals": ((rows,), "int32"),
            **{name: ((rows, 6), "uint8") for name in SYSTEMS},
            "single_valid": ((rows, 3), "uint8"), "role_valid": ((rows, 3), "uint8"),
            "single_abstained": ((rows, 3), "uint8"),
            "judge_abstained": ((rows,), "uint8"), "s2b_k": ((rows,), "uint8"),
            "s3_ceiling_tokens": ((rows,), "int32"),
            "s2b_ceiling_tokens": ((rows,), "int32"),
            "s2b_ceiling_utilization": ((rows,), "float64"),
            "s3_actual_tokens": ((rows,), "int32"),
            "s2b_actual_tokens": ((rows,), "int32"),
        }
    for name, (shape, dtype) in expected_layout.items():
        observed = arrays[name]
        require(observed.shape == shape, f"{name} NPZ shape drift")
        if dtype == "U":
            require(observed.dtype.kind == "U", f"{name} NPZ dtype drift")
        else:
            require(str(observed.dtype) == dtype, f"{name} NPZ dtype drift")
    return arrays


def regular_private_file(path: Path, label: str) -> None:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(
        stat.S_ISREG(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and observed.st_nlink == 1
        and observed.st_uid == os.getuid()
        and f"{stat.S_IMODE(observed.st_mode):04o}" == "0600",
        f"{label} privacy drift",
    )


def validate_artifact_record(record: Any, path: Path, label: str) -> None:
    require(
        isinstance(record, dict)
        and set(record) >= {"path", "bytes", "sha256"}
        and record["path"] == path.name,
        f"{label} record drift",
    )
    require(
        record["bytes"] == path.stat().st_size and record["sha256"] == sha256(path),
        f"{label} identity drift",
    )


def validate_producer_seal(
    manifest: Any, producer_run: Any, systems_path: Path
) -> dict[str, bool]:
    """Confirm the producer was sealed before any consumer-gold is opened."""

    require(isinstance(manifest, dict) and isinstance(producer_run, dict), "producer seal root drift")
    require(
        manifest.get("schema_version") == "sqma-005-private-manifest-v1"
        and manifest.get("experiment_id") == "SQMA-005"
        and manifest.get("status") == "SealedAwaitingScore",
        "producer is not sealed",
    )
    require(
        manifest.get("score_authorized") is False
        and manifest.get("next_gate") == "independent_gold_consumer_scoring",
        "producer/consumer boundary drift",
    )
    call_plan = manifest.get("call_plan", {})
    require(
        call_plan.get("rows") == EXPECTED_ROWS
        and call_plan.get("calls_per_row") == 6
        and call_plan.get("physical_calls") == EXPECTED_CALLS
        and call_plan.get("single_pool_shared") is True,
        "sealed call plan drift",
    )
    validate_artifact_record(manifest.get("systems_artifact"), systems_path, "sealed systems")
    access = manifest.get("access", {})
    for key in (
        "gold_accessed", "classifier_accessed", "adapter_loaded", "training_executed",
        "optimizer_executed", "network_accessed", "validation_accessed", "test_accessed",
        "fold4_accessed",
    ):
        require(access.get(key) is False, f"producer access drift: {key}")

    require(
        producer_run.get("schema_version") == "sqma-005-producer-run-v1"
        and producer_run.get("experiment_id") == "SQMA-005"
        and producer_run.get("status") == "CompletedAwaitingScore",
        "producer run identity drift",
    )
    require(
        producer_run.get("calls", {}).get("physical") == EXPECTED_CALLS
        and producer_run.get("calls", {}).get("per_row") == 6,
        "producer run call-count drift",
    )
    run_systems = producer_run.get("outputs", {}).get("systems")
    require(
        isinstance(run_systems, dict)
        and run_systems.get("bytes") == systems_path.stat().st_size
        and run_systems.get("sha256") == sha256(systems_path)
        and run_systems.get("mode") == "0600"
        and run_systems.get("gold_present") is False,
        "producer run systems identity drift",
    )
    resources = producer_run.get("resources", {})
    generated = resources.get("generated_tokens")
    require(type(generated) is int and 0 <= generated <= EXPECTED_GENERATED_CEILING, "generated-token budget drift")
    for key in ("critical_memory_events", "oom_or_kill_events", "orphan_processes_after_exit"):
        require(resources.get(key) == 0, f"producer resource drift: {key}")
    aggregate = manifest.get("aggregate_cost", {})
    require(aggregate.get("generated_tokens") == generated, "manifest/run cost drift")
    return {"schema": True, "budget": True, "resource": True}


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as output:
        output.write(payload); output.flush(); os.fsync(output.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consumer-gold", required=True)
    parser.add_argument("--systems", required=True)
    parser.add_argument("--producer-manifest", required=True)
    parser.add_argument("--producer-run", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--replicates", type=int, default=BOOTSTRAP_REPLICATES)
    arguments = parser.parse_args()
    gold_path = Path(arguments.consumer_gold).resolve(); systems_path = Path(arguments.systems).resolve()
    manifest_path = Path(arguments.producer_manifest).resolve()
    producer_run_path = Path(arguments.producer_run).resolve()
    for path, label in (
        (gold_path, "consumer gold"), (systems_path, "systems"),
        (manifest_path, "producer manifest"),
    ):
        regular_private_file(path, label)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    producer_run = json.loads(producer_run_path.read_text(encoding="utf-8"))
    integrity = validate_producer_seal(manifest, producer_run, systems_path)
    result = score_payloads(load_npz(gold_path, GOLD_ARRAYS), load_npz(systems_path, SYSTEM_ARRAYS), replicates=arguments.replicates, integrity=integrity)
    result["inputs"] = {
        "consumer_gold": {"bytes": gold_path.stat().st_size, "sha256": sha256(gold_path)},
        "systems": {"bytes": systems_path.stat().st_size, "sha256": sha256(systems_path)},
        "producer_manifest": {"bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path)},
        "producer_run": {"bytes": producer_run_path.stat().st_size, "sha256": sha256(producer_run_path)},
    }
    require(not public_sensitive_paths(result), "score contains row-level material")
    write_json_exclusive(Path(arguments.output).resolve(), result)
    print(json.dumps({"experiment_id": "SQMA-005", "status": "Scored", "tune_gate_passed": result["tune_gate"]["passed"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, zipfile.BadZipFile, ScoringError) as exc:
        print(f"SQMA-005 scoring Failed: {type(exc).__name__}: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1)

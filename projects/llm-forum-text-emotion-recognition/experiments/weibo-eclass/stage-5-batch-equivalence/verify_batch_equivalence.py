#!/usr/bin/env python3
"""Independently verify EXP-045 without importing its runner."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
from typing import Any, Sequence


EXPERIMENT_ID = "EXP-045"
INVALID_LABEL = "__invalid__"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "config.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project path escapes root: {value}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def quantile(values: list[float | int], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: list[float | int]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "p50": quantile(values, 0.50),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
    }


def allocate_quotas(counts: dict[str, int], total: int, labels: list[str]) -> dict[str, int]:
    population = sum(counts.values())
    raw = {label: total * counts[label] / population for label in labels}
    quotas = {label: max(1, math.floor(raw[label])) for label in labels}
    while sum(quotas.values()) > total:
        choices = [label for label in labels if quotas[label] > 1]
        label = min(choices, key=lambda item: (raw[item] - quotas[item], labels.index(item)))
        quotas[label] -= 1
    while sum(quotas.values()) < total:
        label = max(labels, key=lambda item: (raw[item] - quotas[item], -labels.index(item)))
        quotas[label] += 1
    return quotas


def render_messages(config: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    return [
        {
            "role": "system",
            "content": prompt["system_template"].format(
                label_definitions=definitions,
                output_schema=prompt["output_schema"],
            ),
        },
        {
            "role": "user",
            "content": prompt["target_only_template"].format(
                target=row["views"]["target_only"]["target"]
            ),
        },
    ]


def message_sha256(messages: list[dict[str, str]]) -> str:
    payload = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def expected_selection(
    config: dict[str, Any], rows: list[dict[str, Any]], tokenizer: Any, prompt: dict[str, Any]
) -> list[dict[str, Any]]:
    measured = []
    for row in rows:
        messages = render_messages(config, prompt, row)
        prompt_ids = list(
            tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                enable_thinking=True,
                tokenize=True,
            )
        )
        measured.append(
            {
                "label": row["label"],
                "messages": messages,
                "prompt_sha256": sha256_text(json.dumps(prompt_ids, separators=(",", ":"))),
                "prompt_tokens": len(prompt_ids),
                "row": row,
                "sample_id": row["sample_id"],
            }
        )
    counts = Counter(row["label"] for row in measured)
    quotas = allocate_quotas(dict(counts), config["sampling"]["rows"], config["data"]["labels"])
    selected = []
    namespace = config["sampling"]["seed_namespace"]
    for label in config["data"]["labels"]:
        values = [row for row in measured if row["label"] == label]
        values.sort(
            key=lambda row: (
                row["prompt_tokens"],
                sha256_text(f"{namespace}:length-tie:{row['sample_id']}"),
            )
        )
        quota = quotas[label]
        indices = [
            min(len(values) - 1, ((2 * rank + 1) * len(values)) // (2 * quota))
            for rank in range(quota)
        ]
        selected.extend(values[index] for index in indices)
    selected.sort(key=lambda row: sha256_text(f"{namespace}:native-order:{row['sample_id']}"))
    for index, row in enumerate(selected):
        row["selection_index"] = index
        row["selector_sha256"] = sha256_text(f"{namespace}:sample:{row['sample_id']}")
    return selected


def independent_parse(output: str, labels: list[str]) -> dict[str, Any]:
    def invalid(error: str, boundary: bool = False, opening: bool = False) -> dict[str, Any]:
        return {
            "canonical_output": None,
            "error": error,
            "label": None,
            "opening_marker_found": opening,
            "thinking_boundary_found": boundary,
            "valid": False,
        }

    if not isinstance(output, str) or not output.strip():
        return invalid("empty_output")
    opening = "<think>" in output
    close_count = output.count("</think>")
    if close_count != 1:
        return invalid(
            "missing_thinking_boundary" if close_count == 0 else "multiple_thinking_boundaries",
            opening=opening,
        )
    prefix, candidate = output.split("</think>", maxsplit=1)
    if prefix.count("<think>") > 1:
        return invalid("multiple_opening_markers", boundary=True, opening=True)
    if opening and not prefix.lstrip().startswith("<think>"):
        return invalid("misplaced_opening_marker", boundary=True, opening=True)
    try:
        decoded = json.loads(candidate.strip())
    except json.JSONDecodeError:
        return invalid("invalid_json", boundary=True, opening=opening)
    if not isinstance(decoded, dict):
        return invalid("json_not_object", boundary=True, opening=opening)
    if set(decoded) != {"label"}:
        return invalid("schema_keys_mismatch", boundary=True, opening=opening)
    label = decoded["label"]
    if not isinstance(label, str):
        return invalid("label_not_string", boundary=True, opening=opening)
    if label not in labels:
        return invalid("unknown_label", boundary=True, opening=opening)
    return {
        "canonical_output": json.dumps({"label": label}, ensure_ascii=True, separators=(",", ":")),
        "error": None,
        "label": label,
        "opening_marker_found": opening,
        "thinking_boundary_found": True,
        "valid": True,
    }


def compare(left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]]) -> dict[str, Any]:
    left_map = {row["selection_index"]: row for row in left}
    right_map = {row["selection_index"]: row for row in right}
    if set(left_map) != set(right_map) or not left_map:
        raise ValueError("Comparison row identities differ")
    indices = sorted(left_map)
    raw = sum(left_map[index]["raw_output_sha256"] == right_map[index]["raw_output_sha256"] for index in indices)
    parser = sum(left_map[index]["parse"] == right_map[index]["parse"] for index in indices)
    label = sum(left_map[index]["prediction"] == right_map[index]["prediction"] for index in indices)
    return {
        "final_label_equal_count": label,
        "final_label_equal_rate": label / len(indices),
        "parser_state_equal_count": parser,
        "parser_state_equal_rate": parser / len(indices),
        "raw_output_equal_count": raw,
        "raw_output_equal_rate": raw / len(indices),
        "rows": len(indices),
    }


def independent_decision(config: dict[str, Any], comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rules = config["decision"]
    if (
        comparisons["batch8_replay"]["final_label_equal_rate"]
        >= rules["batch_replay_label_agreement_min"]
        and comparisons["batch8_composition"]["final_label_equal_rate"]
        >= rules["batch_composition_label_agreement_min"]
    ):
        return {
            "gate_status": "Passed",
            "recommended_execution_protocol": "batch8_fixed_order",
            "requirements": [
                "freeze validation row order",
                "batch_size=completion_batch_size=prefill_batch_size=8",
                "repeat the train-only replay after each adapter is trained and before dev access",
            ],
            "rules_applied": rules,
        }
    if (
        comparisons["singleton_replay"]["final_label_equal_rate"]
        >= rules["singleton_replay_label_agreement_min"]
    ):
        return {
            "gate_status": "Passed",
            "recommended_execution_protocol": "singleton",
            "requirements": [
                "batch_size=completion_batch_size=prefill_batch_size=1",
                "repeat the train-only replay after each adapter is trained and before dev access",
            ],
            "rules_applied": rules,
        }
    return {
        "gate_status": "Blocked",
        "recommended_execution_protocol": rules["fallback_if_no_stable_reasoning_on_mode"],
        "requirements": ["register and run a reasoning-off replay gate before Stage 5 dev evaluation"],
        "rules_applied": rules,
    }


def mode_order(config: dict[str, Any], mode: str, selection: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, str]:
    if mode.startswith("singleton"):
        return list(selection), 1, "selection_hash"
    if mode == "batch8-length-stress":
        return (
            sorted(selection, key=lambda row: (row["prompt_tokens"], row["selector_sha256"])),
            config["generation"]["batch_size"],
            "prompt_length_ascending",
        )
    return list(selection), config["generation"]["batch_size"], "selection_hash"


def main() -> None:
    config = load_json(CONFIG_PATH)
    run_dir = resolve(config["run_dir"])
    private_root = resolve(config["private_root"])
    output = run_dir / "verification.json"
    if output.exists():
        raise FileExistsError("EXP-045 verification is append-only")
    run = load_json(run_dir / "run.json")
    sample_summary = load_json(run_dir / "sample_summary.json")
    aggregate = load_json(run_dir / "aggregate.json")
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"check": name, "detail": detail, "status": "Passed" if passed else "Failed"})

    check(
        "run-boundary",
        run.get("experiment_id") == EXPERIMENT_ID
        and run.get("tier") == "Minor"
        and run.get("status") == "Awaiting Independent Verification"
        and run.get("accessed_splits") == ["train"]
        and run.get("validation_split_accessed") is False
        and run.get("test_split_accessed") is False,
        {"accessed_splits": run.get("accessed_splits"), "status": run.get("status")},
    )
    train_path = resolve(config["data"]["train_path"])
    prompt_path = resolve(config["implementation"]["prompt_path"])
    parser_path = resolve(config["implementation"]["parser_path"])
    requirements_path = resolve(config["implementation"]["requirements_path"])
    manifest_path = resolve(config["model"]["manifest_path"])
    check(
        "frozen-input-hashes",
        sha256_file(train_path) == config["data"]["train_sha256"]
        and sha256_file(prompt_path) == config["implementation"]["prompt_sha256"]
        and sha256_file(parser_path) == config["implementation"]["parser_sha256"]
        and sha256_file(requirements_path) == config["implementation"]["requirements_sha256"]
        and sha256_file(manifest_path) == config["model"]["manifest_sha256"],
        {"train_rows_expected": config["data"]["train_rows"]},
    )
    implementation_paths = {
        "config_sha256": CONFIG_PATH,
        "runner_sha256": SCRIPT_DIR / "run_batch_equivalence.py",
        "test_sha256": SCRIPT_DIR / "test_batch_equivalence.py",
        "verifier_sha256": Path(__file__),
    }
    check(
        "frozen-implementation-hashes",
        all(run["implementation"].get(key) == sha256_file(path) for key, path in implementation_paths.items()),
        {key: sha256_file(path) for key, path in implementation_paths.items()},
    )

    rows = load_jsonl(train_path)
    labels = set(config["data"]["labels"])
    check(
        "train-schema-and-count",
        len(rows) == config["data"]["train_rows"]
        and len({row["sample_id"] for row in rows}) == len(rows)
        and all(
            row["protocol_id"] == config["data"]["protocol_id"]
            and row["label"] in labels
            and isinstance(row["views"]["target_only"]["target"], str)
            and bool(row["views"]["target_only"]["target"])
            for row in rows
        ),
        {"rows": len(rows)},
    )
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(resolve(config["model"]["local_path"]), local_files_only=True)
    prompt = load_json(prompt_path)
    selected = expected_selection(config, rows, tokenizer, prompt)
    private_selection = load_jsonl(private_root / "selection.jsonl")
    check(
        "deterministic-representative-sample",
        private_selection == selected and len(selected) == config["sampling"]["rows"],
        {"label_counts": dict(Counter(row["label"] for row in selected)), "rows": len(selected)},
    )
    native_groups = {
        frozenset(row["selection_index"] for row in selected[start : start + config["generation"]["batch_size"]])
        for start in range(0, len(selected), config["generation"]["batch_size"])
    }
    stressed = sorted(selected, key=lambda row: (row["prompt_tokens"], row["selector_sha256"]))
    stress_groups = {
        frozenset(row["selection_index"] for row in stressed[start : start + config["generation"]["batch_size"]])
        for start in range(0, len(stressed), config["generation"]["batch_size"])
    }
    check(
        "batch-composition-stress",
        native_groups != stress_groups and sample_summary["native_and_stress_batch_partitions_differ"] is True,
        {"native_group_count": len(native_groups), "stress_group_count": len(stress_groups)},
    )
    selection_material = "\n".join(row["selector_sha256"] for row in selected)
    expected_sample_counts = dict(Counter(row["label"] for row in selected))
    expected_population_counts = dict(Counter(row["label"] for row in rows))
    check(
        "public-sample-summary",
        sample_summary["sample_rows"] == len(selected)
        and sample_summary["selection_digest_sha256"] == sha256_text(selection_material)
        and sample_summary["sample_label_counts"] == expected_sample_counts
        and sample_summary["population_label_counts"] == expected_population_counts
        and sample_summary["sample_prompt_tokens"] == numeric_summary([row["prompt_tokens"] for row in selected])
        and sample_summary["raw_ids_stored_publicly"] is False
        and sample_summary["raw_text_stored_publicly"] is False,
        {"selection_digest_sha256": sample_summary["selection_digest_sha256"]},
    )

    mode_records: dict[str, list[dict[str, Any]]] = {}
    mode_failures: dict[str, list[str]] = {}
    total_elapsed = float(run["stages"]["initialize"]["duration_seconds"])
    for mode in config["generation"]["modes"]:
        public = load_json(run_dir / f"mode-{mode}.json")
        private_path = private_root / f"mode-{mode}.jsonl"
        records = load_jsonl(private_path)
        mode_records[mode] = records
        ordered, batch_size, order_strategy = mode_order(config, mode, selected)
        expected_position = {row["selection_index"]: index for index, row in enumerate(ordered)}
        expected_by_index = {row["selection_index"]: row for row in selected}
        failures = []
        if len(records) != len(selected) or len({row["selection_index"] for row in records}) != len(selected):
            failures.append("row_identity")
        for record in records:
            source = expected_by_index.get(record.get("selection_index"))
            if source is None:
                failures.append("unknown_selection_index")
                continue
            expected_parse = independent_parse(record["raw_output"], config["data"]["labels"])
            expected_prediction = expected_parse["label"] if expected_parse["valid"] else INVALID_LABEL
            if record.get("sample_id") != source["sample_id"]:
                failures.append("sample_id")
            if record.get("mode") != mode or record.get("execution_position") != expected_position[source["selection_index"]]:
                failures.append("execution_order")
            if record.get("message_sha256") != message_sha256(source["messages"]):
                failures.append("message_hash")
            if record.get("prompt_sha256") != source["prompt_sha256"] or record.get("prompt_tokens") != source["prompt_tokens"]:
                failures.append("prompt_contract")
            if record.get("raw_output_sha256") != sha256_text(record["raw_output"]):
                failures.append("raw_output_hash")
            if record.get("parse") != expected_parse or record.get("prediction") != expected_prediction:
                failures.append("independent_parser")
            if record.get("generated_tokens") != len(tokenizer.encode(record["raw_output"], add_special_tokens=False)):
                failures.append("generated_tokens")
            expected_batch_index = expected_position[source["selection_index"]] // batch_size
            expected_batch_rows = min(batch_size, len(selected) - expected_batch_index * batch_size)
            if (
                record.get("batch_stats", {}).get("execution_batch_index") != expected_batch_index
                or record.get("batch_stats", {}).get("batch_rows") != expected_batch_rows
            ):
                failures.append("batch_membership")
        distinct_batches = {
            record["batch_stats"]["execution_batch_index"]: record["batch_stats"] for record in records
        }
        valid = sum(record["parse"]["valid"] for record in records)
        expected_public = {
            "batch_size": batch_size,
            "batches": len(distinct_batches),
            "generated_tokens": numeric_summary([record["generated_tokens"] for record in records]),
            "order_strategy": order_strategy,
            "parser_error_counts": dict(Counter(record["parse"]["error"] for record in records if record["parse"]["error"])),
            "parser_valid_count": valid,
            "parser_valid_rate": valid / len(records),
            "peak_memory_gb": max(float(value["peak_memory"]) for value in distinct_batches.values()),
            "private_output_sha256": sha256_file(private_path),
            "prompt_tokens": numeric_summary([record["prompt_tokens"] for record in records]),
            "rows": len(records),
        }
        if any(public.get(key) != value for key, value in expected_public.items()):
            failures.append("public_summary")
        if not (
            public.get("experiment_id") == EXPERIMENT_ID
            and public.get("mode") == mode
            and public.get("api_cost_usd") == 0
            and public.get("accessed_splits") == ["train"]
            and public.get("performance_metrics_computed") is False
            and public.get("raw_output_stored_publicly") is False
            and public.get("validation_split_accessed") is False
            and public.get("test_split_accessed") is False
            and public.get("peak_memory_gb") <= config["resource_budget"]["peak_memory_gb_max"]
        ):
            failures.append("mode_boundary")
        stage = run["stages"].get(f"infer_{mode}", {})
        if not (
            stage.get("status") == "Passed"
            and stage.get("artifact", {}).get("sha256") == sha256_file(run_dir / f"mode-{mode}.json")
            and stage.get("duration_seconds") == public.get("command_elapsed_seconds")
        ):
            failures.append("run_stage")
        total_elapsed += float(public.get("command_elapsed_seconds", 0.0))
        mode_failures[mode] = sorted(set(failures))
    check(
        "mode-artifacts-and-independent-parser",
        all(not failures for failures in mode_failures.values()),
        mode_failures,
    )
    check(
        "resource-gates",
        total_elapsed <= config["resource_budget"]["local_wall_time_minutes_max"] * 60
        and sum(len(records) for records in mode_records.values()) == config["resource_budget"]["formal_generations"],
        {"formal_generations": sum(len(records) for records in mode_records.values()), "wall_time_seconds": total_elapsed},
    )

    prompt_contract_ok = all(
        [row["message_sha256"] for row in mode_records[mode]]
        == [row["message_sha256"] for row in mode_records["singleton-r1"]]
        and [row["prompt_sha256"] for row in mode_records[mode]]
        == [row["prompt_sha256"] for row in mode_records["singleton-r1"]]
        for mode in config["generation"]["modes"]
    )
    comparisons = {
        "singleton_replay": compare(mode_records["singleton-r1"], mode_records["singleton-r2"]),
        "batch8_replay": compare(mode_records["batch8-r1"], mode_records["batch8-r2"]),
        "batch8_composition": compare(mode_records["batch8-r1"], mode_records["batch8-length-stress"]),
        "singleton_vs_batch8": compare(mode_records["singleton-r1"], mode_records["batch8-r1"]),
    }
    decision = independent_decision(config, comparisons)
    check(
        "aggregate-recomputation",
        aggregate["comparisons"] == comparisons
        and aggregate["decision"] == decision
        and aggregate["prompt_contract_identical_across_modes"] is prompt_contract_ok is True
        and aggregate["formal_generations"] == config["resource_budget"]["formal_generations"]
        and aggregate["gold_labels_used_for_performance"] is False
        and aggregate["performance_metrics_computed"] is False
        and aggregate["validation_split_accessed"] is False
        and aggregate["test_split_accessed"] is False,
        {"decision": decision, "prompt_contract_identical": prompt_contract_ok},
    )

    public_paths = [path for path in run_dir.iterdir() if path.is_file() and path.name != output.name]
    public_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in public_paths)
    leaked_ids = sum(row["sample_id"] in public_text for row in rows)
    long_targets = {
        row["views"]["target_only"]["target"]
        for row in rows
        if len(row["views"]["target_only"]["target"]) >= 16
    }
    leaked_targets = sum(target in public_text for target in long_targets)
    check(
        "public-privacy-boundary",
        leaked_ids == 0 and leaked_targets == 0,
        {"long_raw_text_matches": leaked_targets, "raw_id_matches": leaked_ids},
    )
    check(
        "no-performance-claim",
        all(key not in public_text.lower() for key in ('"accuracy"', '"macro_f1"', '"weighted_f1"')),
        {"classification_metrics_present": False},
    )

    failed = [item["check"] for item in checks if item["status"] != "Passed"]
    report = {
        "accessed_splits": ["train"],
        "check_count": len(checks),
        "checks": checks,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "failed_checks": failed,
        "status": "Passed" if not failed else "Failed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "verifier_imported_runner": False,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not failed:
        run["status"] = "Verified"
        run["verified_at_utc"] = report["completed_at_utc"]
        run["verification"] = {
            "path": str(output.relative_to(PROJECT_ROOT)),
            "sha256": sha256_file(output),
        }
        (run_dir / "run.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"check_count": len(checks), "failed_checks": failed, "status": report["status"]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

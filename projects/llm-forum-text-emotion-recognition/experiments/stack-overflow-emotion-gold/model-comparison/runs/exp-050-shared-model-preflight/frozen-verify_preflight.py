#!/usr/bin/env python3
"""Independently verify the public artifacts produced by EXP-050."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "EXP-050"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-050-shared-model-preflight"
DEFAULT_OUTPUT = DEFAULT_RUN_DIR / "verification.json"
PRIVATE_GENERATIONS = SCRIPT_DIR / "private" / "exp-050-shared-model-preflight" / "m4-generations.jsonl"
FROZEN_NAMES = (
    "config.json",
    "prompt-v1.json",
    "run_preflight.py",
    "strict_multilabel_parser.py",
    "verify_preflight.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_project(path: str) -> Path:
    return PROJECT_ROOT / path


def ranked(rows: list[dict[str, Any]], namespace: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: hashlib.sha256(f"{namespace}|{row['sample_id']}".encode()).hexdigest(),
    )


def independently_select(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    namespace = config["preflight"]["selection_namespace"]
    selected: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(LABELS):
        before = len(selected)
        candidates = [row for row in rows if row["labels"][index] == 1]
        for row in ranked(candidates, f"{namespace}|positive|{label}"):
            selected.setdefault(row["sample_id"], row)
            if len(selected) == before + 2:
                break
    groups = (
        ("neutral", [row for row in rows if row["neutral"]], 4),
        ("cardinality2", [row for row in rows if row["label_cardinality"] == 2], 4),
    )
    for name, candidates, required in groups:
        added = 0
        for row in ranked(candidates, f"{namespace}|{name}"):
            if row["sample_id"] in selected:
                continue
            selected[row["sample_id"]] = row
            added += 1
            if added == required:
                break
    for row in ranked(rows, f"{namespace}|fill"):
        selected.setdefault(row["sample_id"], row)
        if len(selected) == config["preflight"]["sample_rows"]:
            break
    return ranked(list(selected.values()), f"{namespace}|final-order")


def numeric_summary(values: list[int]) -> dict[str, int]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[int(len(ordered) * 0.95)],
        "p99": ordered[int(len(ordered) * 0.99)],
        "max": ordered[-1],
    }


def strict_parse(raw: Any) -> dict[str, Any]:
    result = {"valid": False, "labels": [], "vector": [0] * len(LABELS), "error": None}
    if not isinstance(raw, str):
        result["error"] = "not_string"
        return result
    if not raw or raw != raw.strip():
        result["error"] = "outer_whitespace_or_empty"
        return result
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        result["error"] = "invalid_json"
        return result
    if not isinstance(value, dict) or list(value) != ["emotions"]:
        result["error"] = "schema_keys"
        return result
    selected = value["emotions"]
    if not isinstance(selected, list) or any(type(label) is not str for label in selected):
        result["error"] = "emotions_not_string_list"
        return result
    if len(selected) != len(set(selected)):
        result["error"] = "duplicate_label"
        return result
    if any(label not in LABELS for label in selected):
        result["error"] = "unknown_label"
        return result
    canonical = [label for label in LABELS if label in selected]
    if selected != canonical:
        result["error"] = "noncanonical_order"
        return result
    if raw != json.dumps({"emotions": selected}, ensure_ascii=True, separators=(",", ":")):
        result["error"] = "noncanonical_json"
        return result
    result.update(valid=True, labels=selected, vector=[int(label in selected) for label in LABELS])
    return result


def forbidden_public_keys(value: Any) -> set[str]:
    forbidden = {"sample_id", "component_id", "text", "raw_output", "gold", "prediction"}
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(key for key in value if key in forbidden)
        for child in value.values():
            found.update(forbidden_public_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(forbidden_public_keys(child))
    return found


def source_access_audit(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    load_train = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load_train"
    )
    constants = [node.value for node in ast.walk(load_train) if isinstance(node, ast.Constant)]
    prohibited_apis = (".glob(", ".rglob(", "os.walk(", ".walk(")
    return {
        "load_train_names_train_path": constants.count("train_path") == 1,
        "load_train_names_no_validation_or_test_path": not {"validation_path", "test_path"}.intersection(constants),
        "no_recursive_or_glob_file_access": not any(token in source for token in prohibited_apis),
    }


def qwen_lora_parameter_count(model_config: dict[str, Any], rank: int, layers: int) -> int:
    hidden = model_config["hidden_size"]
    attention_out = model_config["num_attention_heads"] * model_config["head_dim"]
    key_value_out = model_config["num_key_value_heads"] * model_config["head_dim"]
    intermediate = model_config["intermediate_size"]
    per_layer = rank * (
        (hidden + attention_out)
        + 2 * (hidden + key_value_out)
        + (attention_out + hidden)
        + 2 * (hidden + intermediate)
        + (intermediate + hidden)
    )
    return layers * per_layer


def verify(run_dir: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    config = json.loads((run_dir / "frozen-config.json").read_text(encoding="utf-8"))
    prompt = json.loads((run_dir / "frozen-prompt-v1.json").read_text(encoding="utf-8"))
    reports = {
        stage: json.loads((run_dir / f"{stage}.json").read_text(encoding="utf-8"))
        for stage in ("static", "m1", "m2", "m3", "m4")
    }
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    check("experiment identity", run["experiment_id"] == config["preflight"]["experiment_id"] == EXPERIMENT_ID)
    check("run reached Passed", run["status"] == "Passed")
    check("all required stages passed", all(run["stages"][stage]["status"] == "Passed" for stage in run["required_stages"]))
    check("formal execution remains unauthorized", config["formal_execution_authorized"] is False)
    check("run denies validation access", run["validation_split_accessed"] is False)
    check("run denies test access", run["test_split_accessed"] is False)
    check("model whitelist excludes test", config["data"]["model_access_whitelist"] == ["train", "validation"])
    check("test remains sealed", config["data"]["test_status"] == "sealed_not_authorized_for_model_access")

    frozen_hashes = {}
    for name in FROZEN_NAMES:
        current = SCRIPT_DIR / name
        frozen = run_dir / f"frozen-{name}"
        frozen_hashes[name] = sha256(frozen)
        check(f"frozen {name} matches source", sha256(current) == sha256(frozen))
    check("frozen prompt hash matches contract", frozen_hashes["prompt-v1.json"] == config["prompt"]["sha256"])
    check("train hash matches contract", sha256(resolve_project(config["data"]["train_path"])) == config["data"]["train_sha256"])
    check("task manifest hash matches contract", sha256(resolve_project(config["data"]["task_manifest_path"])) == config["data"]["task_manifest_sha256"])
    check("RoBERTa manifest hash matches contract", sha256(resolve_project(config["models"]["m1"]["manifest_path"])) == config["models"]["m1"]["manifest_sha256"])
    check("Qwen manifest hash matches contract", sha256(resolve_project(config["models"]["qwen_shared"]["manifest_path"])) == config["models"]["qwen_shared"]["manifest_sha256"])
    check("chat template hash matches contract", sha256(resolve_project(config["prompt"]["chat_template_path"])) == config["prompt"]["chat_template_sha256"])
    check("tokenizer asset hash matches contract", sha256(resolve_project(config["prompt"]["tokenizer_asset_path"])) == config["prompt"]["tokenizer_asset_sha256"])

    train_path = resolve_project(config["data"]["train_path"])
    rows = [json.loads(line) for line in train_path.read_text(encoding="utf-8").splitlines()]
    check("train row count", len(rows) == config["data"]["train_rows"], len(rows))
    check("label order", tuple(config["data"]["labels"]) == LABELS)
    check("train vectors are binary six-vectors", all(len(row["labels"]) == 6 and set(row["labels"]) <= {0, 1} for row in rows))
    check("neutral is derived from labels", all(row["neutral"] == (sum(row["labels"]) == 0) for row in rows))
    check("cardinality is derived from labels", all(row["label_cardinality"] == sum(row["labels"]) for row in rows))

    selected = independently_select(rows, config)
    identities = [{"sample_id": row["sample_id"], "component_id": row["component_id"]} for row in selected]
    selection = reports["static"]["selection"]
    positive_counts = {label: sum(row["labels"][i] for row in selected) for i, label in enumerate(LABELS)}
    check("selection size", len(selected) == config["preflight"]["sample_rows"], len(selected))
    check("selection identity digest", canonical_digest(identities) == selection["selection_digest_sha256"])
    check("selection order digest", canonical_digest([row["sample_id"] for row in selected]) == selection["order_digest_sha256"])
    check("selection label counts", positive_counts == selection["positive_counts"])
    check("selection covers both outcomes per label", all(2 <= count < len(selected) for count in positive_counts.values()))
    check("selection neutral coverage", sum(row["neutral"] for row in selected) == selection["neutral_rows"] >= 4)
    check("selection multilabel coverage", sum(row["label_cardinality"] == 2 for row in selected) == selection["cardinality_2_rows"] >= 4)

    from transformers import AutoTokenizer

    roberta = AutoTokenizer.from_pretrained(resolve_project(config["models"]["m1"]["local_path"]), local_files_only=True)
    qwen = AutoTokenizer.from_pretrained(resolve_project(config["models"]["qwen_shared"]["local_path"]), local_files_only=True)
    roberta_lengths = [len(roberta.encode(row["text"], add_special_tokens=True)) for row in rows]
    qwen_ids = [
        qwen.apply_chat_template(
            [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user_prefix"] + row["text"] + prompt["user_suffix"]},
            ],
            tokenize=True,
            return_dict=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        for row in rows
    ]
    qwen_lengths = [len(ids) for ids in qwen_ids]
    check("RoBERTa length summary independently matches", numeric_summary(roberta_lengths) == reports["static"]["roberta_token_lengths"])
    check("Qwen length summary independently matches", numeric_summary(qwen_lengths) == reports["static"]["qwen_prompt_token_lengths"])
    check("RoBERTa train has no truncation", max(roberta_lengths) <= config["models"]["m1"]["max_sequence_length"])
    check("Qwen train has no truncation", max(qwen_lengths) <= config["prompt"]["max_sequence_length"])
    suffixes = {tuple(ids[-5:]) for ids in qwen_ids}
    check("Qwen empty-think suffix is invariant", len(suffixes) == 1)
    check("Qwen suffix digest", canonical_digest(list(next(iter(suffixes)))) == reports["static"]["qwen_prompt_suffix_token_sha256"])

    audit = source_access_audit(run_dir / "frozen-run_preflight.py")
    for name, passed in audit.items():
        check(f"source access audit: {name}", passed)
    check("all reports are train-only", all(report["accessed_splits"] == ["train"] for report in reports.values()))
    check("all reports deny validation", all(report["validation_split_accessed"] is False for report in reports.values()))
    check("all reports deny test", all(report["test_split_accessed"] is False for report in reports.values()))
    check("no performance metric was computed", all(report["performance_metrics_computed"] is False for report in reports.values()))
    check("public report schemas contain no row-level fields", not set().union(*(forbidden_public_keys(report) for report in reports.values())))
    public_serialized = "\n".join(json.dumps(report, sort_keys=True) for report in reports.values())
    check("public reports contain no sample identifiers", all(row["sample_id"] not in public_serialized for row in rows))
    check("public reports contain no component identifiers", all(row["component_id"] not in public_serialized for row in rows))

    m1 = reports["m1"]
    check("M1 two-step finite BCE", m1["optimizer_steps"] == 2 and len(m1["finite_losses"]) == 2 and all(math.isfinite(value) for value in m1["finite_losses"]))
    check("M1 six-logit shapes", m1["logit_shapes"] == [[12, 6], [12, 6]])
    check("M1 classifier changed", m1["classifier_initial_sha256"] != m1["classifier_final_sha256"] and m1["trainable_parameters_changed"] is True)

    qwen_spec = config["models"]["qwen_shared"]
    expected_head = qwen_spec["hidden_size"] * len(LABELS) + len(LABELS)
    m2 = reports["m2"]
    check("M2 exact head size", expected_head == qwen_spec["head_parameters"] == m2["trainable_parameter_count"])
    check("M2 pooling and logit shapes", m2["pooled_shape"] == [1, 2560] and m2["logit_shape"] == [1, 6])
    check("M2 two-step finite BCE", m2["optimizer_steps"] == 2 and len(m2["finite_losses"]) == 2 and all(math.isfinite(value) for value in m2["finite_losses"]))
    check("M2 only head changed", m2["qwen_parameters_frozen"] is True and m2["head_initial_sha256"] != m2["head_final_sha256"])

    local_qwen_config = json.loads((resolve_project(qwen_spec["local_path"]) / "config.json").read_text(encoding="utf-8"))
    lora = config["models"]["lora_shared"]
    expected_lora = qwen_lora_parameter_count(local_qwen_config, lora["rank"], lora["num_layers"])
    expected_insertions = lora["num_layers"] * len(lora["target_modules"])
    m3 = reports["m3"]
    check("M3 independent LoRA parameter count", expected_lora == lora["trainable_parameters"] == m3["lora_parameter_count"])
    check("M3 insertion contract", expected_insertions == lora["insertion_points"] == m3["insertion_count"])
    check("M3 exact blocks", m3["adapted_blocks"] == lora["adapted_block_indices"])
    check("M3 exact target modules", m3["target_modules"] == lora["target_modules"])
    check("M2/M3 matched head initialization", m2["head_initial_sha256"] == m3["head_initial_sha256"])
    check("M2/M3 matched zero-step logits", m2["initial_logits_sha256"] == m3["initial_logits_sha256"])
    check("M3 exact zero initial LoRA delta", m3["zero_step_max_abs_logit_difference"] == 0.0)
    check("M3 head and LoRA changed", m3["head_initial_sha256"] != m3["head_final_sha256"] and m3["lora_initial_sha256"] != m3["lora_final_sha256"] and m3["nonzero_lora_b_tensors_after_training"] > 0)
    check("M3 two-step finite BCE", m3["optimizer_steps"] == 2 and len(m3["finite_losses"]) == 2 and all(math.isfinite(value) for value in m3["finite_losses"]))
    check("M3 optimizer separation", m3["separate_head_and_lora_optimizers"] is True)

    m4 = reports["m4"]
    check("M3/M4 matched LoRA initialization", m3["lora_initial_sha256"] == m4["lora_initial_sha256"])
    check("M4 insertion and parameter contract", m4["insertion_count"] == expected_insertions and m4["trainable_parameter_count"] == expected_lora)
    check("M4 two-step finite assistant loss", m4["optimizer_steps"] == 2 and len(m4["finite_losses"]) == 2 and all(math.isfinite(value) for value in m4["finite_losses"]))
    check("M4 prompt is masked", m4["prompt_loss_masked"] is True and all(count > 1 for count in m4["supervised_token_counts"]))
    check("M4 LoRA changed", m4["lora_initial_sha256"] != m4["lora_final_sha256"] and m4["nonzero_lora_b_tensors_after_training"] > 0)
    check("M4 generation has no retries", m4["generation_rows"] == config["preflight"]["generation_rows"] and m4["generation_retries"] == 0)
    check("M4 private generation hash", sha256(PRIVATE_GENERATIONS) == m4["private_generation_sha256"])
    private_rows = [json.loads(line) for line in PRIVATE_GENERATIONS.read_text(encoding="utf-8").splitlines()]
    parsed = [strict_parse(row["raw_output"]) for row in private_rows]
    check("M4 private row count", len(private_rows) == config["preflight"]["generation_rows"])
    check("M4 parser independently matches", all(row["parsed"] == result for row, result in zip(private_rows, parsed)))
    check("M4 valid count independently matches", sum(result["valid"] for result in parsed) == m4["parser_valid_count"])

    elapsed = sum(run["stages"][stage]["wall_seconds"] for stage in run["required_stages"])
    check("preflight wall-time budget", elapsed <= 45 * 60, elapsed)
    check("M2-M4 peak memory budget", all(reports[stage]["peak_memory_gb"] <= config["preflight"]["max_peak_memory_gb"] for stage in ("m2", "m3", "m4")))

    failed = [item["name"] for item in checks if not item["passed"]]
    result = {
        "experiment_id": EXPERIMENT_ID,
        "status": "Passed" if not failed else "Failed",
        "checks_passed": len(checks) - len(failed),
        "checks_total": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "accessed_splits": ["train"],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "performance_metrics_computed": False,
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = verify(args.run_dir.resolve(), args.output.resolve())
    print(json.dumps({key: result[key] for key in ("experiment_id", "status", "checks_passed", "checks_total", "failed_checks")}, indent=2))
    if result["status"] != "Passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

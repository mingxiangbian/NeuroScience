#!/usr/bin/env python3
"""Independently verify the EXP-047 seed-43 singleton replay gate."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import statistics
import sys
from typing import Any


os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-047"
CONTRACT_ID = "EXP-047-SEED-43-REPLAY-V1"
VERIFICATION_ID = "EXP-047-SEED-43-REPLAY-VERIFY-V1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-047-seed-43-replay-contract-v1.json"
INVALID_LABEL = "__invalid__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"bytes": path.stat().st_size, "path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(observed: Any, expected: Any, message: str) -> None:
    if observed != expected:
        raise ValueError(f"{message}: observed={observed!r}, expected={expected!r}")


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(spec["path"])
    observed = artifact(path)
    require_equal(observed["sha256"], spec["sha256"], "Frozen artifact hash drift")
    require_equal(observed["bytes"], int(spec["bytes"]), "Frozen artifact size drift")
    return observed


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    if (
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("seed") != 43
        or contract.get("accessed_splits") != ["train"]
    ):
        raise ValueError("Unexpected EXP-047 seed-43 replay contract")
    verifier = resolve_project_path(contract["implementation"]["verifier"]["path"])
    require_equal(verifier, Path(__file__).resolve(), "Replay verifier path drift")
    for spec in contract["implementation"].values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    return contract


def load_parser(contract: dict[str, Any]):
    path = resolve_project_path(contract["frozen_artifacts"]["parser"]["path"])
    spec = importlib.util.spec_from_file_location("exp047_seed43_independent_parser", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_final_label


def selection_digest(rows: list[dict[str, Any]]) -> str:
    return sha256_text("\n".join(row["selector_sha256"] for row in rows))


def compare_records(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    left_map = {row["selection_index"]: row for row in left}
    right_map = {row["selection_index"]: row for row in right}
    indices = sorted(left_map)
    require_equal(indices, sorted(right_map), "Replay pass row-set drift")
    return {
        "final_label_equal_count": sum(left_map[i]["prediction"] == right_map[i]["prediction"] for i in indices),
        "parser_state_equal_count": sum(left_map[i]["parse"] == right_map[i]["parse"] for i in indices),
        "raw_output_equal_count": sum(left_map[i]["raw_output_sha256"] == right_map[i]["raw_output_sha256"] for i in indices),
        "rows": len(indices),
    }


def numeric_summary(values: list[float | int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("Cannot summarize an empty list")
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
    }


def generated_token_count(tokenizer: Any, output: str) -> int:
    token_ids = list(tokenizer.encode(output, add_special_tokens=False))
    if not all(isinstance(token, int) and not isinstance(token, bool) for token in token_ids):
        raise TypeError("Independent output tokenization did not return integer token IDs")
    return len(token_ids)


def verify_training(contract: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(contract["frozen_artifacts"]["training_verification"]["path"])
    verification = load_json(path)
    if (
        verification.get("verification_id") != "EXP-047-FORMAL-SEED-43-ATTEMPT-2-TRAIN-VERIFY-V1"
        or verification.get("status") != "Passed"
        or verification.get("formal_training_verified") is not True
        or verification.get("validation_split_accessed") is not False
        or verification.get("test_split_accessed") is not False
    ):
        raise ValueError("Seed-43 training verification is invalid")
    return artifact(path)


def verify_selection_and_prompts(
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], Any]:
    from transformers import AutoTokenizer

    selection_path = resolve_project_path(contract["frozen_artifacts"]["selection"]["path"])
    selection = read_jsonl(selection_path)
    rows = int(contract["replay"]["rows"])
    require_equal(len(selection), rows, "Replay selection row-count drift")
    require_equal([row["selection_index"] for row in selection], list(range(rows)), "Selection index drift")
    require_equal(selection_digest(selection), contract["replay"]["selection_digest_sha256"], "Selection digest drift")
    tokenizer = AutoTokenizer.from_pretrained(
        str(resolve_project_path(contract["model"]["local_path"])),
        local_files_only=True,
    )
    by_index: dict[int, dict[str, Any]] = {}
    for row in selection:
        token_ids = list(
            tokenizer.apply_chat_template(
                row["messages"],
                add_generation_prompt=True,
                enable_thinking=True,
                tokenize=True,
                return_dict=False,
            )
        )
        if not token_ids or not all(isinstance(token, int) and not isinstance(token, bool) for token in token_ids):
            raise TypeError("Independent replay template did not return integer token IDs")
        prompt_hash = sha256_text(json.dumps(token_ids, separators=(",", ":")))
        require_equal(prompt_hash, row["prompt_sha256"], "Independent prompt hash drift")
        require_equal(len(token_ids), int(row["prompt_tokens"]), "Independent prompt length drift")
        by_index[int(row["selection_index"])] = row
    return selection, by_index, tokenizer


def verify_pass(
    contract: dict[str, Any],
    pass_id: str,
    selection: dict[int, dict[str, Any]],
    parse_final_label: Any,
    tokenizer: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    public = resolve_project_path(contract["outputs"]["public_dir"]) / f"pass-{pass_id}.json"
    private = resolve_project_path(contract["outputs"]["private_dir"]) / f"pass-{pass_id}.jsonl"
    summary = load_json(public)
    records = read_jsonl(private)
    require_equal(len(records), int(contract["replay"]["rows"]), "Replay private row-count drift")
    require_equal([row["selection_index"] for row in records], list(range(len(records))), "Replay output order drift")
    if stat.S_IMODE(private.stat().st_mode) != 0o600:
        raise PermissionError("Replay private output mode drift")
    generated_tokens: list[int] = []
    for row in records:
        source = selection[int(row["selection_index"])]
        require_equal(row["pass_id"], pass_id, "Replay pass ID drift")
        require_equal(row["prompt_sha256"], source["prompt_sha256"], "Replay prompt hash drift")
        require_equal(row["prompt_tokens"], source["prompt_tokens"], "Replay prompt length drift")
        messages_hash = sha256_text(
            json.dumps(source["messages"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        require_equal(row["message_sha256"], messages_hash, "Replay message hash drift")
        require_equal(row["raw_output_sha256"], sha256_text(row["raw_output"]), "Raw output hash drift")
        parsed = parse_final_label(row["raw_output"], thinking=True, labels=contract["labels"])
        require_equal(row["parse"], parsed.to_dict(), "Independent parser result drift")
        require_equal(row["prediction"], parsed.label if parsed.valid else INVALID_LABEL, "Prediction drift")
        token_count = generated_token_count(tokenizer, row["raw_output"])
        require_equal(row["generated_tokens"], token_count, "Generated-token count drift")
        generated_tokens.append(token_count)
    valid = sum(bool(row["parse"]["valid"]) for row in records)
    expected_summary = {
        "accessed_splits": ["train"],
        "duration_seconds": summary["duration_seconds"],
        "experiment_id": EXPERIMENT_ID,
        "generated_tokens": numeric_summary(generated_tokens),
        "label_counts": dict(Counter(row["prediction"] for row in records)),
        "parser_valid_count": valid,
        "pass_id": pass_id,
        "peak_memory_gb": summary["peak_memory_gb"],
        "private_output_sha256": sha256_file(private),
        "raw_outputs_stored_publicly": False,
        "rows": len(records),
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    require_equal(summary, expected_summary, "Replay public summary drift")
    duration = float(summary["duration_seconds"])
    peak = float(summary["peak_memory_gb"])
    if duration <= 0 or duration > float(contract["resource_budget"]["per_pass_hours_max"]) * 3600:
        raise ValueError("Replay duration is outside the contract")
    if peak <= 0 or peak > float(contract["resource_budget"]["peak_memory_gb_max"]):
        raise ValueError("Replay peak memory is outside the contract")
    return records, artifact(public)


def verify_public_privacy(contract: dict[str, Any], records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    public = resolve_project_path(contract["outputs"]["public_dir"])
    source_names = ("aggregate.json", "pass-r1.json", "pass-r2.json", "run.json")
    source_paths = [public / name for name in source_names]
    contents = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    forbidden = {
        str(value)
        for pass_rows in records.values()
        for row in pass_rows
        for value in (row.get("raw_output"),)
        if isinstance(value, str) and len(value) >= 4
    }
    leaked = [sha256_text(value) for value in forbidden if value in contents]
    if leaked:
        raise ValueError("Public replay artifacts contain raw model output")
    return {"public_json_files_scanned": len(source_paths), "raw_output_leaks": 0}


def build_verification(contract: dict[str, Any], completed_at_utc: str) -> dict[str, Any]:
    public = resolve_project_path(contract["outputs"]["public_dir"])
    private = resolve_project_path(contract["outputs"]["private_dir"])
    if stat.S_IMODE(private.stat().st_mode) != 0o700:
        raise PermissionError("Replay private directory mode drift")
    run_path = public / "run.json"
    aggregate_path = public / "aggregate.json"
    run = load_json(run_path)
    aggregate = load_json(aggregate_path)
    if (
        run.get("status") != "Completed; pending independent replay verification"
        or run.get("accessed_splits") != ["train"]
        or run.get("validation_split_accessed") is not False
        or run.get("test_split_accessed") is not False
    ):
        raise ValueError("Replay run boundary fields are invalid")
    require_equal(run["contract"], artifact(CONTRACT_PATH), "Replay contract artifact drift")
    training = verify_training(contract)
    _, selection, tokenizer = verify_selection_and_prompts(contract)
    parse_final_label = load_parser(contract)
    records: dict[str, list[dict[str, Any]]] = {}
    pass_artifacts: dict[str, Any] = {}
    for pass_id in ("r1", "r2"):
        records[pass_id], pass_artifacts[pass_id] = verify_pass(
            contract, pass_id, selection, parse_final_label, tokenizer
        )
    comparison = compare_records(records["r1"], records["r2"])
    valid_counts = {
        pass_id: sum(bool(row["parse"]["valid"]) for row in rows)
        for pass_id, rows in records.items()
    }
    gate = contract["replay"]["gate"]
    require_equal(comparison["rows"], int(contract["replay"]["rows"]), "Replay row gate failed")
    require_equal(comparison["final_label_equal_count"], int(gate["final_label_equal_count"]), "Label equality gate failed")
    require_equal(comparison["parser_state_equal_count"], int(gate["parser_state_equal_count"]), "Parser equality gate failed")
    require_equal(comparison["raw_output_equal_count"], int(gate["raw_output_equal_count"]), "Raw equality gate failed")
    if min(valid_counts.values()) < int(gate["parser_valid_count_min_per_pass"]):
        raise ValueError("Parser-valid replay gate failed")
    require_equal(aggregate["comparison"], comparison, "Aggregate comparison drift")
    require_equal(aggregate["parser_valid_counts"], valid_counts, "Aggregate valid-count drift")
    require_equal(aggregate["status"], "Passed", "Aggregate status drift")
    privacy = verify_public_privacy(contract, records)
    expected_public = {"aggregate.json", "pass-r1.json", "pass-r2.json", "run.json"}
    if (public / "verification.json").exists():
        expected_public.add("verification.json")
    require_equal({path.name for path in public.iterdir()}, expected_public, "Replay public inventory drift")
    require_equal({path.name for path in private.iterdir()}, {"pass-r1.jsonl", "pass-r2.jsonl"}, "Replay private inventory drift")
    return {
        "accessed_splits": ["train"],
        "completed_at_utc": completed_at_utc,
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "formal_dev_authorized": False,
        "implementation": {"imports_runner": False, "verifier": artifact(Path(__file__).resolve())},
        "next_required_step": "Decide whether to authorize seed 44; validation/test remain closed until all registered adapter gates pass.",
        "recalculated": {
            "aggregate": artifact(aggregate_path),
            "comparison": comparison,
            "passes": pass_artifacts,
            "privacy": privacy,
            "run": artifact(run_path),
            "training_verification": training,
        },
        "remaining_training_seeds_authorized": False,
        "seed": 43,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }


def main() -> None:
    args = parse_args()
    contract = load_contract()
    verification_path = resolve_project_path(contract["outputs"]["public_dir"]) / "verification.json"
    if args.check:
        existing = load_json(verification_path)
        expected = build_verification(contract, str(existing.get("completed_at_utc")))
        require_equal(existing, expected, "Stored replay verification differs from recomputation")
        print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, sort_keys=True))
        return
    if verification_path.exists():
        raise FileExistsError(verification_path)
    verification = build_verification(contract, datetime.now(timezone.utc).isoformat())
    write_json(verification_path, verification)
    print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, sort_keys=True))


if __name__ == "__main__":
    main()

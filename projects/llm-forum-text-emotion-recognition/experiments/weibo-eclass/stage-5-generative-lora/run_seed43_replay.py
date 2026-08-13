#!/usr/bin/env python3
"""Run the frozen two-pass singleton replay for the EXP-047 seed-43 adapter."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable


EXPERIMENT_ID = "EXP-047"
CONTRACT_ID = "EXP-047-SEED-43-REPLAY-V1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-047-seed-43-replay-contract-v1.json"
INVALID_LABEL = "__invalid__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize")
    infer = subparsers.add_parser("infer")
    infer.add_argument("--pass-id", choices=("r1", "r2"), required=True)
    subparsers.add_parser("aggregate")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        temporary.chmod(0o600)
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(spec["path"])
    observed = artifact(path)
    if observed["sha256"] != spec["sha256"] or observed["bytes"] != int(spec["bytes"]):
        raise ValueError(f"Frozen artifact drift: {path}")
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
    runner = resolve_project_path(contract["implementation"]["runner"]["path"])
    if runner != Path(__file__).resolve():
        raise ValueError("Replay runner path drift")
    for spec in contract["implementation"].values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    python = Path(contract["runtime"]["python_executable"])
    if not python.is_file() or not Path(sys.executable).samefile(python):
        raise ValueError("Replay must use the frozen Python environment")
    observed_packages = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in contract["runtime"]["packages"]
    }
    if observed_packages != contract["runtime"]["packages"]:
        raise ValueError("Replay package-version drift")
    return contract


def load_parser(contract: dict[str, Any]):
    path = resolve_project_path(contract["frozen_artifacts"]["parser"]["path"])
    spec = importlib.util.spec_from_file_location("exp047_seed43_replay_parser", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_final_label


def require_token_ids(value: Any) -> list[int]:
    tokens = list(value)
    if not tokens or not all(isinstance(token, int) and not isinstance(token, bool) for token in tokens):
        raise TypeError("Chat template must return non-empty integer token IDs")
    return tokens


def numeric_summary(values: list[float | int]) -> dict[str, float | int]:
    if not values:
        raise ValueError("Cannot summarize an empty list")
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
    }


def selection_digest(rows: list[dict[str, Any]]) -> str:
    return sha256_text("\n".join(row["selector_sha256"] for row in rows))


def verify_bound_inputs(contract: dict[str, Any]) -> list[dict[str, Any]]:
    training = load_json(resolve_project_path(contract["frozen_artifacts"]["training_verification"]["path"]))
    if (
        training.get("verification_id") != "EXP-047-FORMAL-SEED-43-ATTEMPT-2-TRAIN-VERIFY-V1"
        or training.get("status") != "Passed"
        or training.get("formal_training_verified") is not True
        or training.get("validation_split_accessed") is not False
        or training.get("test_split_accessed") is not False
    ):
        raise ValueError("Seed-43 training verification is invalid")
    selection_path = resolve_project_path(contract["frozen_artifacts"]["selection"]["path"])
    rows = read_jsonl(selection_path)
    if (
        len(rows) != int(contract["replay"]["rows"])
        or [row.get("selection_index") for row in rows] != list(range(int(contract["replay"]["rows"])))
        or selection_digest(rows) != contract["replay"]["selection_digest_sha256"]
    ):
        raise ValueError("Replay selection drift")
    if any(not isinstance(row.get("messages"), list) or not row["messages"] for row in rows):
        raise ValueError("Replay selection contains invalid messages")
    return rows


def public_dir(contract: dict[str, Any]) -> Path:
    return resolve_project_path(contract["outputs"]["public_dir"])


def private_dir(contract: dict[str, Any]) -> Path:
    return resolve_project_path(contract["outputs"]["private_dir"])


def load_run(contract: dict[str, Any]) -> dict[str, Any]:
    return load_json(public_dir(contract) / "run.json")


def save_run(contract: dict[str, Any], run: dict[str, Any]) -> None:
    atomic_json(public_dir(contract) / "run.json", run)


def git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def initialize(contract: dict[str, Any]) -> None:
    rows = verify_bound_inputs(contract)
    public = public_dir(contract)
    private = private_dir(contract)
    if public.exists() or private.exists():
        raise FileExistsError("Append-only replay output already exists")
    public.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    private.chmod(0o700)
    run = {
        "accessed_splits": ["train"],
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "git": git_state(),
        "raw_outputs_stored_publicly": False,
        "rows": len(rows),
        "seed": 43,
        "stages": {"initialize": {"completed_at_utc": utc_now(), "status": "Passed"}},
        "status": "Initialized",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    save_run(contract, run)
    print(json.dumps({"rows": len(rows), "status": "Initialized"}, sort_keys=True))


def infer(contract: dict[str, Any], pass_id: str) -> None:
    run = load_run(contract)
    if run["stages"].get("initialize", {}).get("status") != "Passed":
        raise RuntimeError("Replay initialize must pass before inference")
    stage = f"infer_{pass_id}"
    if stage in run["stages"]:
        raise FileExistsError(f"Replay pass already recorded: {pass_id}")
    public_path = public_dir(contract) / f"pass-{pass_id}.json"
    private_path = private_dir(contract) / f"pass-{pass_id}.jsonl"
    if public_path.exists() or private_path.exists():
        raise FileExistsError(f"Replay pass output exists: {pass_id}")
    rows = verify_bound_inputs(contract)
    started = time.perf_counter()
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    import mlx.core as mx
    from mlx_lm import batch_generate, load
    from mlx_lm.sample_utils import make_sampler

    parse_final_label = load_parser(contract)
    model_path = resolve_project_path(contract["model"]["local_path"])
    adapter_path = resolve_project_path(contract["frozen_artifacts"]["adapter"]["path"])
    mx.reset_peak_memory()
    model, tokenizer = load(str(model_path), adapter_path=str(adapter_path.parent), lazy=False)
    sampler = make_sampler(temp=float(contract["generation"]["temperature"]))
    records: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        prompt_ids = require_token_ids(
            tokenizer.apply_chat_template(
                source["messages"],
                add_generation_prompt=True,
                enable_thinking=True,
                tokenize=True,
                return_dict=False,
            )
        )
        prompt_hash = sha256_text(json.dumps(prompt_ids, separators=(",", ":")))
        if prompt_hash != source["prompt_sha256"] or len(prompt_ids) != int(source["prompt_tokens"]):
            raise ValueError("Replay prompt-token contract drift")
        generated = batch_generate(
            model,
            tokenizer,
            [prompt_ids],
            max_tokens=int(contract["generation"]["max_new_tokens"]),
            sampler=sampler,
            completion_batch_size=1,
            prefill_batch_size=1,
            prefill_step_size=int(contract["generation"]["prefill_step_size"]),
            verbose=False,
        )
        output = generated.texts[0]
        parsed = parse_final_label(output, thinking=True, labels=contract["labels"])
        records.append(
            {
                "generated_tokens": len(tokenizer.encode(output, add_special_tokens=False)),
                "message_sha256": sha256_text(
                    json.dumps(source["messages"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                ),
                "parse": parsed.to_dict(),
                "pass_id": pass_id,
                "prediction": parsed.label if parsed.valid else INVALID_LABEL,
                "prompt_sha256": prompt_hash,
                "prompt_tokens": len(prompt_ids),
                "raw_output": output,
                "raw_output_sha256": sha256_text(output),
                "selection_index": source["selection_index"],
            }
        )
        print(json.dumps({"completed": index + 1, "pass_id": pass_id, "total": len(rows)}), flush=True)
    elapsed = time.perf_counter() - started
    peak_memory = float(mx.get_peak_memory()) / 1e9
    if peak_memory > float(contract["resource_budget"]["peak_memory_gb_max"]):
        raise RuntimeError("Replay exceeded the frozen memory budget")
    if elapsed > float(contract["resource_budget"]["per_pass_hours_max"]) * 3600:
        raise RuntimeError("Replay exceeded the frozen wall-time budget")
    atomic_jsonl(private_path, records)
    valid = sum(bool(row["parse"]["valid"]) for row in records)
    summary = {
        "accessed_splits": ["train"],
        "duration_seconds": elapsed,
        "experiment_id": EXPERIMENT_ID,
        "generated_tokens": numeric_summary([row["generated_tokens"] for row in records]),
        "label_counts": dict(Counter(row["prediction"] for row in records)),
        "parser_valid_count": valid,
        "pass_id": pass_id,
        "peak_memory_gb": peak_memory,
        "private_output_sha256": sha256_file(private_path),
        "raw_outputs_stored_publicly": False,
        "rows": len(records),
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    atomic_json(public_path, summary)
    run = load_run(contract)
    run["stages"][stage] = {"artifact": artifact(public_path), "completed_at_utc": utc_now(), "status": "Passed"}
    run["status"] = "Replay in progress"
    save_run(contract, run)
    del model, tokenizer
    gc.collect()
    mx.clear_cache()
    print(json.dumps({"pass_id": pass_id, "status": "Passed"}, sort_keys=True))


def compare_records(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    left_map = {row["selection_index"]: row for row in left}
    right_map = {row["selection_index"]: row for row in right}
    indices = sorted(left_map)
    if indices != sorted(right_map):
        raise ValueError("Replay pass row-set drift")
    return {
        "final_label_equal_count": sum(left_map[i]["prediction"] == right_map[i]["prediction"] for i in indices),
        "parser_state_equal_count": sum(left_map[i]["parse"] == right_map[i]["parse"] for i in indices),
        "raw_output_equal_count": sum(left_map[i]["raw_output_sha256"] == right_map[i]["raw_output_sha256"] for i in indices),
        "rows": len(indices),
    }


def aggregate(contract: dict[str, Any]) -> None:
    run = load_run(contract)
    if any(run["stages"].get(f"infer_{name}", {}).get("status") != "Passed" for name in ("r1", "r2")):
        raise RuntimeError("Both replay inference passes must pass before aggregation")
    output = public_dir(contract) / "aggregate.json"
    if output.exists():
        raise FileExistsError(output)
    records = {name: read_jsonl(private_dir(contract) / f"pass-{name}.jsonl") for name in ("r1", "r2")}
    comparison = compare_records(records["r1"], records["r2"])
    valid_counts = {name: sum(bool(row["parse"]["valid"]) for row in rows) for name, rows in records.items()}
    gate = contract["replay"]["gate"]
    passed = (
        comparison["rows"] == int(contract["replay"]["rows"])
        and comparison["final_label_equal_count"] == int(gate["final_label_equal_count"])
        and comparison["parser_state_equal_count"] == int(gate["parser_state_equal_count"])
        and comparison["raw_output_equal_count"] == int(gate["raw_output_equal_count"])
        and min(valid_counts.values()) >= int(gate["parser_valid_count_min_per_pass"])
    )
    result = {
        "accessed_splits": ["train"],
        "comparison": comparison,
        "completed_at_utc": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "parser_valid_counts": valid_counts,
        "raw_outputs_stored_publicly": False,
        "seed": 43,
        "status": "Passed" if passed else "Failed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    atomic_json(output, result)
    run["stages"]["aggregate"] = {"artifact": artifact(output), "completed_at_utc": utc_now(), "status": result["status"]}
    run["status"] = "Completed; pending independent replay verification" if passed else "Failed"
    save_run(contract, run)
    print(json.dumps({"comparison": comparison, "status": result["status"]}, sort_keys=True))
    if not passed:
        raise RuntimeError("Seed-43 replay gate failed")


def main() -> None:
    args = parse_args()
    contract = load_contract()
    if args.command == "initialize":
        initialize(contract)
    elif args.command == "infer":
        infer(contract, args.pass_id)
    elif args.command == "aggregate":
        aggregate(contract)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()

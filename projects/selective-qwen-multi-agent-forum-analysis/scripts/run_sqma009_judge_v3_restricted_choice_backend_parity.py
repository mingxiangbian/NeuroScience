#!/usr/bin/env python3
"""SQMA-009 Judge V3 restricted-choice producer and pure contracts.

Importing this module performs no I/O. Execution remains blocked until the
SQMA-009 config binds the verified C1 sources, v5 identities, and resources.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import resource
import stat
import sys
import time
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-009-judge-v3-restricted-choice-backend-parity.json"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
GENERATION_NAMESPACE = "SQMA-009-judge-v3-restricted-choice-v1"
EXPECTED_ROWS = 16
EXPECTED_CALLS = 96
PRIVATE_ALLOWED = ["token-seal.json", "calls.jsonl", "assemblies.jsonl", "private-manifest.json"]
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text", "candidate_mapping", "component_id", "component_ids",
    "evidence", "critic", "ordinary_v2_labels", "option_mapping", "raw_output",
    "response_token", "sample_id", "sample_ids", "selected_evidence_id",
    "selected_symbol", "target_label", "text",
}
CALL_FIELDS = {
    "schema_version", "call_ordinal", "row_ordinal", "selection_rank",
    "sample_id", "component_id", "source_ordinal", "target_label", "seed",
    "analysis_text_sha256", "context_sha256", "messages_sha256",
    "prompt_ids_sha256", "candidate_mapping", "allowed_token_ids",
    "processor_instance_id", "processor_invocations", "response_count",
    "response_token", "generated_tokens", "finish_reason", "generated_text_sha256",
    "selected_symbol", "selected_evidence_id", "terminal_valid",
    "selected_token_allowed", "selected_eos_token", "post_mask_valid",
    "prefill_tokens", "latency_seconds", "mlx_peak_bytes",
}
ASSEMBLY_FIELDS = {
    "schema_version", "row_ordinal", "selection_rank", "sample_id", "component_id",
    "source_ordinal", "allowed_evidence_ids", "v3_slots", "v3_labels",
    "ordinary_v2_labels", "exact_label_set_parity", "per_label_parity",
    "assembly_diagnostics",
}
FALLBACK_EVIDENCE = {
    "schema_version": "evidence-v3", "candidate_emotions": [],
    "evidence_spans": [], "insufficient_evidence": True,
}
FALLBACK_CRITIC = {
    "schema_version": "critic-v3", "recommended_emotions": [],
    "challenged_emotions": [], "warning_flags": [],
}


class SQMA009Error(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SQMA009Error(message)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def seed_for(sample_id: str, target_label: str) -> int:
    material = f"{GENERATION_NAMESPACE}|{sample_id}|{target_label}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big", signed=False)


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(contains_placeholder(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_placeholder(child) for child in value)
    return isinstance(value, str) and value.startswith("PLACEHOLDER_")


class CountingProcessor:
    """Fresh per-call wrapper; the wrapped mask remains stateless."""

    def __init__(self, processor: Any, observer: Any = None) -> None:
        self.processor = processor
        self.observer = observer
        self.invocations = 0
        self.post_mask_valid = True

    def __call__(self, tokens: Any, logits: Any) -> Any:
        self.invocations += 1
        masked = self.processor(tokens, logits)
        if self.observer is not None:
            self.post_mask_valid = self.post_mask_valid and bool(self.observer(masked))
        return masked


def build_counting_processor(base_processor: Any, observer: Any = None) -> CountingProcessor:
    require(callable(base_processor), "base logits processor must be callable")
    require(observer is None or callable(observer), "mask observer must be callable")
    return CountingProcessor(base_processor, observer)


def validate_static_config(config: Mapping[str, Any]) -> None:
    require(config.get("schema_version") == "sqma-009-judge-v3-restricted-choice-backend-parity-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-009", "experiment identity drift")
    require(config.get("design_status") in {"StaticDesignAwaitingImplementation", "FrozenReady"}, "design status drift")
    if config.get("design_status") == "FrozenReady":
        require(config.get("authorization", {}).get("execution_authorized") is True, "execution authorization drift")
        require(not contains_placeholder(config), "FrozenReady placeholders remain")
    else:
        require(all(value is False for value in config.get("authorization", {}).values()), "static authorization drift")
    require(config.get("generation", {}).get("rows") == 16 and config["generation"].get("physical_calls") == 96, "call plan drift")
    require(config.get("outputs", {}).get("private_allowed_files") == PRIVATE_ALLOWED, "private output inventory drift")


def assert_execution_ready(config: Mapping[str, Any]) -> None:
    require(config.get("design_status") == "FrozenReady" and config.get("authorization", {}).get("execution_authorized") is True, "SQMA-009 not FrozenReady")
    require(not contains_placeholder(config), "SQMA-009 unresolved identity")


def c1_call_groups(calls: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    require(len(calls) == 48, "C1 call count drift")
    groups = [list(calls[index : index + 3]) for index in range(0, 48, 3)]
    for rank, group in enumerate(groups):
        require([call.get("role") for call in group] == ["evidence", "critic", "judge"], "C1 role order drift")
        require(all(call.get("selection_rank") == rank for call in group), "C1 rank drift")
    return groups


def replay_c1_rows(
    selection: Mapping[str, Any], calls: Sequence[Mapping[str, Any]], validator_v4: Any,
) -> list[dict[str, Any]]:
    rows = selection.get("rows")
    require(isinstance(rows, list) and len(rows) == 16, "C1 selection drift")
    output = []
    for row_ordinal, (selected, group) in enumerate(zip(rows, c1_call_groups(calls), strict=True)):
        evidence_call, critic_call, judge_call = group
        require(all(call.get("sample_id") == selected["sample_id"] and call.get("component_id") == selected["component_id"] for call in group), "C1 call identity drift")
        analysis_text = evidence_call.get("analysis_text")
        require(isinstance(analysis_text, str) and all(call.get("analysis_text") == analysis_text for call in group), "C1 analysis text drift")
        evidence_context = {"analysis_text": analysis_text, "ontology": validator_v4.ONTOLOGY}
        evidence = None
        try:
            evidence = validator_v4.validate_evidence(evidence_call["raw_output"], evidence_context)
        except validator_v4.AgentOutputError:
            evidence = FALLBACK_EVIDENCE
        critic_context = {**evidence_context, "evidence": evidence}
        critic = None
        try:
            critic = validator_v4.validate_critic(critic_call["raw_output"], critic_context)
        except validator_v4.AgentOutputError:
            critic = FALLBACK_CRITIC
        allowed = list(range(len(evidence["evidence_spans"])))
        judge_context = {**critic_context, "critic": critic, "allowed_evidence_ids": allowed}
        judge = validator_v4.judge_contract_result(judge_call["raw_output"], judge_context)
        require(judge["rendered_contract_valid"] is True, "C1 ordinary Judge replay drift")
        output.append(
            {
                "row_ordinal": row_ordinal, "selection_rank": selected["selection_rank"],
                "sample_id": selected["sample_id"], "component_id": selected["component_id"],
                "source_ordinal": selected["source_ordinal"], "analysis_text": analysis_text,
                "evidence": evidence, "critic": critic, "allowed_evidence_ids": allowed,
                "ordinary_v2_labels": list(judge["derived_labels"]),
            }
        )
    return output


def planned_calls(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    require(len(rows) == 16, "row count drift")
    return [
        {
            "call_ordinal": row_ordinal * 6 + label_index,
            "row_ordinal": row_ordinal, "selection_rank": row["selection_rank"],
            "sample_id": row["sample_id"], "component_id": row["component_id"],
            "source_ordinal": row["source_ordinal"], "target_label": label,
            "seed": seed_for(row["sample_id"], label),
        }
        for row_ordinal, row in enumerate(rows)
        for label_index, label in enumerate(LABEL_ORDER)
    ]


def judge_context(row: Mapping[str, Any], label: str, mapping: Sequence[Mapping[str, Any]], ontology: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "analysis_text": row["analysis_text"], "ontology": dict(ontology),
        "evidence": row["evidence"], "critic": row["critic"],
        "target_label": label, "allowed_evidence_ids": row["allowed_evidence_ids"],
        "option_mapping": list(mapping),
    }


def validate_calls(
    calls: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]],
    token_seal: Mapping[str, Any], validator_v5: Any,
) -> None:
    plan = planned_calls(rows)
    require(len(calls) == len(plan) == 96, "restricted call count drift")
    seen_processors = set()
    for call, expected in zip(calls, plan, strict=True):
        require(isinstance(call, Mapping) and set(call) == CALL_FIELDS, "restricted call schema drift")
        require(all(call[key] == value for key, value in expected.items()), "restricted call plan drift")
        row = rows[call["row_ordinal"]]
        mapping = validator_v5.build_candidate_mapping(row["allowed_evidence_ids"], token_seal)
        context = judge_context(row, call["target_label"], mapping, validator_v5.ONTOLOGY)
        require(call["analysis_text_sha256"] == text_sha256(row["analysis_text"]), "analysis identity drift")
        require(call["context_sha256"] == canonical_digest(context), "context identity drift")
        require(call["candidate_mapping"] == mapping, "candidate mapping drift")
        require(call["allowed_token_ids"] == [item["token_id"] for item in mapping], "allowed token drift")
        terminal = {
            "response_count": call["response_count"], "token": call["response_token"],
            "generation_tokens": call["generated_tokens"], "finish_reason": call["finish_reason"],
        }
        validator_v5.validate_generation_terminal(terminal, mapping)
        choice = validator_v5.choice_from_terminal(terminal, mapping)
        require(
            call["selected_symbol"] == choice["symbol"]
            and call["selected_evidence_id"] == choice["evidence_id"]
            and call["terminal_valid"] is True,
            "authoritative response-token mapping drift",
        )
        require(
            call["selected_token_allowed"] is True
            and call["selected_eos_token"] is False
            and call["post_mask_valid"] is True,
            "mask/token diagnostic drift",
        )
        require(type(call["processor_invocations"]) is int and call["processor_invocations"] >= 1, "processor invocation drift")
        require(call["processor_instance_id"] not in seen_processors, "processor instance reused")
        seen_processors.add(call["processor_instance_id"])


def assemble_rows(
    calls: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]],
    token_seal: Mapping[str, Any], validator_v5: Any,
) -> list[dict[str, Any]]:
    validate_calls(calls, rows, token_seal, validator_v5)
    assemblies = []
    for row_ordinal, row in enumerate(rows):
        group = calls[row_ordinal * 6 : row_ordinal * 6 + 6]
        terminals = {
            call["target_label"]: {
                "response_count": call["response_count"], "token": call["response_token"],
                "generation_tokens": call["generated_tokens"], "finish_reason": call["finish_reason"],
            }
            for call in group
        }
        assembled = validator_v5.assemble_judge_slots(
            terminals, allowed_evidence_ids=row["allowed_evidence_ids"], token_seal=token_seal
        )
        v3_labels = list(assembled["derived_labels"])
        ordinary = list(row["ordinary_v2_labels"])
        assemblies.append(
            {
                "schema_version": "sqma-009-assembly-v1", "row_ordinal": row_ordinal,
                "selection_rank": row["selection_rank"], "sample_id": row["sample_id"],
                "component_id": row["component_id"], "source_ordinal": row["source_ordinal"],
                "allowed_evidence_ids": list(row["allowed_evidence_ids"]),
                "v3_slots": assembled["per_label_refs"], "v3_labels": v3_labels,
                "ordinary_v2_labels": ordinary,
                "exact_label_set_parity": v3_labels == ordinary,
                "per_label_parity": {label: (label in v3_labels) == (label in ordinary) for label in LABEL_ORDER},
                "assembly_diagnostics": assembled["diagnostics"],
            }
        )
    return assemblies


def technical_metrics(calls: Sequence[Mapping[str, Any]], assemblies: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    require(len(calls) == 96 and len(assemblies) == 16, "technical metric count drift")
    latency = [float(call["latency_seconds"]) for call in calls]
    prefill = [int(call["prefill_tokens"]) for call in calls]
    exact = sum(assembly["exact_label_set_parity"] is True for assembly in assemblies)
    return {
        "calls": 96, "assemblies": 16,
        "terminal_valid_calls": sum(call["terminal_valid"] is True for call in calls),
        "response_count_one": sum(call["response_count"] == 1 for call in calls),
        "generation_tokens_one": sum(call["generated_tokens"] == 1 for call in calls),
        "finish_reason_length": sum(call["finish_reason"] == "length" for call in calls),
        "processor_invocations_total": sum(call["processor_invocations"] for call in calls),
        "processor_invocations_minimum": min(call["processor_invocations"] for call in calls),
        "unique_processor_instances": len({call["processor_instance_id"] for call in calls}),
        "assembly_valid": sum(assembly["assembly_diagnostics"]["illegal_reference_ids_constructed"] == 0 for assembly in assemblies),
        "selected_token_escape": sum(call["selected_token_allowed"] is not True for call in calls),
        "selected_eos_tokens": sum(call["selected_eos_token"] is True for call in calls),
        "post_mask_dead_end_or_nonfinite": sum(call["post_mask_valid"] is not True for call in calls),
        "semantic_repair_events": sum(assembly["assembly_diagnostics"]["semantic_repair_events"] for assembly in assemblies),
        "unhandled_failures": 0,
        "latency_seconds": {"mean": sum(latency) / len(latency), "max": max(latency)},
        "prefill_tokens": {"mean": sum(prefill) / len(prefill), "max": max(prefill)},
        "mlx_peak_bytes": max(call["mlx_peak_bytes"] for call in calls),
        "v2_v3_exact_label_set_parity_report_only": exact / 16,
        "v2_v3_per_label_parity_report_only": {
            label: sum(assembly["per_label_parity"][label] for assembly in assemblies) / 16
            for label in LABEL_ORDER
        },
    }


def technical_gate(metrics: Mapping[str, Any]) -> bool:
    return (
        metrics["calls"] == 96 and metrics["assemblies"] == 16
        and metrics["terminal_valid_calls"] == 96
        and metrics["response_count_one"] == 96
        and metrics["generation_tokens_one"] == 96
        and metrics["finish_reason_length"] == 96
        and metrics["processor_invocations_minimum"] >= 1
        and metrics["unique_processor_instances"] == 96
        and metrics["assembly_valid"] == 16
        and metrics["selected_token_escape"] == 0
        and metrics["selected_eos_tokens"] == 0
        and metrics["post_mask_dead_end_or_nonfinite"] == 0
        and metrics["semantic_repair_events"] == 0
        and metrics["unhandled_failures"] == 0
    )


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (value.startswith("sample-") or value.startswith("component-")):
        violations.append(prefix)
    return violations


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute() and ".." not in Path(relative).parts, f"unsafe {label} path")
    root = root.resolve(); path = (root / relative).resolve(); require(path == root or root in path.parents, f"{label} escapes root"); return path


def regular_file(path: Path, label: str, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}"); observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode) and observed.st_uid == os.getuid() and observed.st_nlink == 1, f"{label} identity drift")
    if mode is not None: require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_file(path, label); value = json.loads(path.read_text()); require(isinstance(value, dict), f"{label} root drift"); return value


def read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    regular_file(path, label); values = [json.loads(line) for line in path.read_text().splitlines()]; require(all(isinstance(value, dict) for value in values), f"{label} rows drift"); return values


def verify_record(record: Mapping[str, Any], label: str) -> Path:
    require({"path", "bytes", "sha256"} <= set(record) and type(record["bytes"]) is int, f"{label} record drift"); path = checked_path(REPO_ROOT, record["path"], label); observed = regular_file(path, label); require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} hash drift"); return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name); spec = importlib.util.spec_from_file_location(name, path); require(spec is not None and spec.loader is not None, f"{name} import unavailable"); module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module


def artifact(path: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    return {"path": path.resolve().relative_to(root.resolve()).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json(path: Path, value: Mapping[str, Any], mode: int) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(); descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as target: target.write(payload); target.flush(); os.fsync(target.fileno())
    path.chmod(mode)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]], mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        for row in rows: target.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        target.flush(); os.fsync(target.fileno())
    path.chmod(mode)


def verify_model(config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    model = config["model"]; archive = Path(os.environ.get(model["archive_root_env"], model["audited_archive_root"])).resolve(); manifest_path = checked_path(archive, model["manifest_path"], "model manifest"); observed = regular_file(manifest_path, "model manifest"); require(observed.st_size == model["manifest_bytes"] and sha256(manifest_path) == model["manifest_sha256"], "model manifest drift"); manifest = read_json(manifest_path, "model manifest"); inventory = manifest["mlx_bf16"]["files"]; model_root = checked_path(archive, model["relative_path"], "model root"); total = 0
    for record in inventory:
        path = checked_path(model_root, record["path"], "model file"); file_stat = regular_file(path, "model file"); require(file_stat.st_size == record["bytes"] and sha256(path) == record["sha256"], "model file drift"); total += record["bytes"]
    require(total == model["total_bytes"], "model total drift"); return model_root, {"repo_id": model["repo_id"], "revision": model["revision"], "manifest_sha256": model["manifest_sha256"], "file_count": len(inventory), "total_bytes": total, "adapter": None}


def prompt_messages(bundle: Mapping[str, Any], context: Mapping[str, Any]) -> list[dict[str, str]]:
    system = bundle["judge_restricted_choice"]["system"]
    return [{"role": "system", "content": system}, {"role": "user", "content": "Input JSON:\n" + json.dumps(context, ensure_ascii=True, sort_keys=True, separators=(",", ":"))}]


def resource_snapshot(started: float, mx: Any) -> dict[str, Any]:
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform.startswith("linux"): rss *= 1024
    return {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": rss, "mlx_peak_bytes": int(mx.get_peak_memory())}


def run(config_argument: str) -> dict[str, Any]:
    started = time.monotonic(); started_at = utc_now()
    supplied = Path(config_argument).expanduser().resolve()
    require(supplied == CONFIG_PATH.resolve(), "noncanonical SQMA-009 config")
    config = read_json(supplied, "config"); validate_static_config(config); assert_execution_ready(config)
    for section in ("implementation", "prerequisites"):
        for name, record in config[section].items(): verify_record(record, f"{section}.{name}")
    c1_complete = read_json(verify_record(config["prerequisites"]["sqma007_complete"], "C1 complete"), "C1 complete")
    require(c1_complete.get("sqma007_complete") is True and c1_complete.get("ordinary_decoding_c1_gate") == "Passed", "C1 prerequisite drift")
    public_dir = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public output"); private_dir = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private output")
    require(not os.path.lexists(public_dir) and not os.path.lexists(private_dir), "output namespace exists")
    free_disk = __import__("shutil").disk_usage(REPO_ROOT).free; require(free_disk >= config["resources"]["minimum_free_disk_bytes"], "disk gate failed")
    public_dir.mkdir(parents=True, mode=0o755, exist_ok=False)
    claim = {"schema_version": "sqma-009-run-claim-v1", "experiment_id": "SQMA-009", "status": "ClaimedBeforeC1PrivateReuseOrModelLoad", "claimed_at_utc": utc_now(), "config": artifact(supplied), "c1_rows": 16, "judge_calls": 96, "evidence_critic_generation_calls": 0, "gold_access": False, "classifier_access": False, "next_gate": "c1_replay_and_runtime_token_seal"}
    require(not public_sensitive_paths(claim), "claim leak"); write_json(public_dir / "run-claim.json", claim, 0o644)
    c1 = config["sealed_c1_private_input"]; c1_root = checked_path(REPO_ROOT, c1["base_dir"], "C1 private root")
    c1_paths = {}
    for name, record in c1["artifacts"].items():
        path = checked_path(c1_root, record["path"], f"C1 {name}"); observed = regular_file(path, f"C1 {name}", record["mode"]); require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"C1 {name} drift"); c1_paths[name] = path
    c1_selection = read_json(c1_paths["selection"], "C1 selection"); c1_calls = read_jsonl(c1_paths["calls"], "C1 calls")
    validator_v4 = load_module("sqma009_validator_v4", config["implementation"]["validator_v4_lineage"])
    validator_v5 = load_module("sqma009_validator_v5", config["implementation"]["validator_v5"])
    rows = replay_c1_rows(c1_selection, c1_calls, validator_v4)
    bundle = read_json(verify_record(config["implementation"]["prompt_v5"], "v5 prompt"), "v5 prompt")
    model_root, model_identity = verify_model(config)
    runtime = config["runtime"]; require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve() and platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime drift")
    for source in runtime["backend_sources"].values():
        path = Path(source["path"]); observed = regular_file(path, "backend source"); require(observed.st_size == source["bytes"] and sha256(path) == source["sha256"], "backend source drift")
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    for package, version in runtime["packages"].items(): require(importlib.metadata.version(package) == version, f"package drift: {package}")
    mx.reset_peak_memory(); load_started = time.monotonic(); model, tokenizer = load(str(model_root), adapter_path=None, lazy=False); model_load_seconds = time.monotonic() - load_started
    seal_contract = config["token_seal"]; tokenizer_file = model_root / seal_contract["model_root_relative_files"]["tokenizer_json"]["path"]; chat_file = model_root / seal_contract["model_root_relative_files"]["chat_template"]["path"]
    for path, record in ((tokenizer_file, seal_contract["model_root_relative_files"]["tokenizer_json"]), (chat_file, seal_contract["model_root_relative_files"]["chat_template"])):
        observed = regular_file(path, "token seal source"); require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "token seal source drift")
    chat_template = tokenizer.chat_template if isinstance(tokenizer.chat_template, str) else ""; require(text_sha256(chat_template) == seal_contract["model_root_relative_files"]["chat_template"]["sha256"], "runtime chat template drift")
    eos_value = tokenizer.eos_token_id; eos_ids = list(eos_value) if isinstance(eos_value, (list, tuple)) else [int(eos_value)]
    token_seal = validator_v5.build_token_seal(tokenizer, tokenizer_sha256=sha256(tokenizer_file), chat_template_sha256=sha256(chat_file), eos_token_ids=eos_ids)
    private_dir.mkdir(parents=True, mode=0o700, exist_ok=False); private_dir.chmod(0o700); write_json(private_dir / "token-seal.json", token_seal, 0o600)
    calls = []; sampler = make_sampler(temp=0.0)
    for expected in planned_calls(rows):
        row = rows[expected["row_ordinal"]]; mapping = validator_v5.build_candidate_mapping(row["allowed_evidence_ids"], token_seal); context = judge_context(row, expected["target_label"], mapping, validator_v5.ONTOLOGY); messages = prompt_messages(bundle, context); prompt_ids = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False)
        if isinstance(prompt_ids, Mapping): prompt_ids = prompt_ids["input_ids"]
        prompt_ids = [int(value) for value in prompt_ids]; mx.random.seed(expected["seed"]); allowed_tokens = [item["token_id"] for item in mapping]; base_processor = validator_v5.make_stateless_mlx_logits_processor(mx, allowed_tokens)
        def observe_mask(masked_logits: Any) -> bool:
            allowed_values = masked_logits[..., allowed_tokens]
            mx.eval(allowed_values)
            return bool(mx.any(mx.isfinite(allowed_values)).item())
        processor = build_counting_processor(base_processor, observe_mask)
        responses = []; call_started = time.monotonic(); stream = stream_generate(model, tokenizer, prompt_ids, max_tokens=1, sampler=sampler, logits_processors=[processor], prompt_cache=None)
        try:
            for response in stream: responses.append(response)
        finally: stream.close()
        latency = time.monotonic() - call_started; require(len(responses) == 1, "response count drift"); response = responses[0]; terminal = {"response_count": 1, "token": int(response.token), "generation_tokens": int(response.generation_tokens), "finish_reason": response.finish_reason}; validator_v5.validate_generation_terminal(terminal, mapping); choice = validator_v5.choice_from_terminal(terminal, mapping)
        selected_eos = terminal["token"] in set(eos_ids); selected_allowed = terminal["token"] in set(allowed_tokens); record = {"schema_version": "sqma-009-call-v1", **expected, "analysis_text_sha256": text_sha256(row["analysis_text"]), "context_sha256": canonical_digest(context), "messages_sha256": canonical_digest(messages), "prompt_ids_sha256": canonical_digest(prompt_ids), "candidate_mapping": mapping, "allowed_token_ids": allowed_tokens, "processor_instance_id": f"processor-{expected['call_ordinal']}", "processor_invocations": processor.invocations, "response_count": 1, "response_token": terminal["token"], "generated_tokens": terminal["generation_tokens"], "finish_reason": terminal["finish_reason"], "generated_text_sha256": text_sha256(response.text), "selected_symbol": choice["symbol"], "selected_evidence_id": choice["evidence_id"], "terminal_valid": True, "selected_token_allowed": selected_allowed, "selected_eos_token": selected_eos, "post_mask_valid": processor.post_mask_valid, "prefill_tokens": int(response.prompt_tokens), "latency_seconds": latency, "mlx_peak_bytes": int(mx.get_peak_memory())}; require(set(record) == CALL_FIELDS, "call schema drift"); calls.append(record); del responses; gc.collect(); mx.clear_cache()
    require(sum(call["generated_tokens"] for call in calls) == config["resources"]["maximum_generated_tokens"] == 96, "generated-token gate drift")
    assemblies = assemble_rows(calls, rows, token_seal, validator_v5); write_jsonl(private_dir / "calls.jsonl", calls, 0o600); write_jsonl(private_dir / "assemblies.jsonl", assemblies, 0o600)
    metrics = technical_metrics(calls, assemblies); resources = {**resource_snapshot(started, mx), "generated_tokens": 96, "physical_calls": 96, "model_load_seconds": model_load_seconds, "private_output_bytes": 0, "free_disk_bytes_before": free_disk, "critical_memory_events": 0, "oom_or_kill_events": 0, "orphan_processes_after_exit": 0}; limits = config["resources"]; resource_passed = resources["wall_seconds"] <= limits["maximum_wall_seconds"] and resources["peak_rss_bytes"] <= limits["maximum_process_rss_bytes"] and resources["mlx_peak_bytes"] <= limits["maximum_mlx_peak_bytes"]
    access = {"c1_private_reused": True, "visible_c1_content_accessed": True, "locked_content_accessed": False, "gold_accessed": False, "classifier_accessed": False, "model_loaded": True, "training_executed": False, "network_accessed": False, "fold3_accessed": False, "fold4_accessed": False, "validation_accessed": False, "test_accessed": False}
    manifest = {"schema_version": "sqma-009-private-manifest-v1", "experiment_id": "SQMA-009", "status": "SealedAwaitingVerification" if technical_gate(metrics) and resource_passed else "Failed", "c1_source_identity": {name: artifact(path, c1_root) for name, path in c1_paths.items()}, "token_seal": artifact(private_dir / "token-seal.json", private_dir), "calls": artifact(private_dir / "calls.jsonl", private_dir), "assemblies": artifact(private_dir / "assemblies.jsonl", private_dir), "model_identity": model_identity, "access": access, "technical_gate_passed": technical_gate(metrics) and resource_passed, "next_gate": "independent_verification" if technical_gate(metrics) and resource_passed else "stop_failed_incident_required"}
    write_json(private_dir / "private-manifest.json", manifest, 0o600); resources["private_output_bytes"] = sum(path.stat().st_size for path in private_dir.iterdir()); require(resources["private_output_bytes"] <= limits["maximum_private_output_bytes"], "private output cap drift")
    passed = technical_gate(metrics) and resource_passed
    run_payload = {"schema_version": "sqma-009-run-v1", "experiment_id": "SQMA-009", "status": "CompletedAwaitingVerification" if passed else "Failed", "config": artifact(supplied), "run_claim": artifact(public_dir / "run-claim.json"), "token_seal": {"sha256": sha256(private_dir / "token-seal.json"), "valid": True}, "calls": {"physical": 96, "evidence": 0, "critic": 0, "judge_restricted_choice": 96}, "technical_gate": metrics, "technical_gate_passed": passed, "resources": resources, "model": model_identity, "access": access, "outputs": {"private_manifest_sha256": sha256(private_dir / "private-manifest.json"), "calls_sha256": sha256(private_dir / "calls.jsonl"), "assemblies_sha256": sha256(private_dir / "assemblies.jsonl")}, "claim_boundary": "Technical restricted-choice backend parity only; V2-V3 label parity is report-only and no model logits are independently recomputed.", "next_gate": "independent_verification" if passed else "stop_failed_incident_required"}; require(not public_sensitive_paths(run_payload), "public leak"); write_json(public_dir / "run.json", run_payload, 0o644); return run_payload


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True)
    result = run(parser.parse_args().config); print(json.dumps({"experiment_id": "SQMA-009", "status": result["status"], "technical_gate_passed": result["technical_gate_passed"], "next_gate": result["next_gate"]}, sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, SQMA009Error) as exc:
        print(f"SQMA-009 blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

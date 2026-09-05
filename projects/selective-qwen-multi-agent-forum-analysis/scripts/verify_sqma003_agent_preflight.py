#!/usr/bin/env python3
"""Independent, model-free verifier for SQMA-003 Agent-Dev preflight."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import stat
import sys
import time
from typing import Any, Iterable, Mapping, Sequence

sys.dont_write_bytecode = True
REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-003-classifier-free-agent-preflight.json"
FORBIDDEN_FRAMEWORK_ROOTS = {"mlx", "mlx_lm", "torch", "transformers"}
SHA256_CHARS = frozenset("0123456789abcdef")
INPUT_FIELD_ORDER = (
    "schema_version", "protocol_id", "sample_id", "component_id", "fold_id",
    "source_ordinal", "text",
)
INPUT_FIELDS = set(INPUT_FIELD_ORDER)
SELECTION_FIELDS = {"schema_version", "namespace", "rows"}
SELECTION_ROW_FIELDS = {"selection_rank", "selection_stratum", "sample_id", "component_id", "fold_id", "source_ordinal"}
CALL_FIELDS = {
    "selection_rank", "selection_stratum", "sample_id", "component_id", "source_ordinal",
    "system_id", "role", "call_index", "seed", "prompt_sha256", "prefill_tokens",
    "generated_tokens", "finish_reason", "latency_seconds", "peak_memory_gb", "raw_output",
    "parsed_output", "validation_error", "final_labels", "text_meta",
}
TEXT_META_FIELDS = {"original_tokens", "analysis_tokens", "was_truncated"}
PRIVATE_MANIFEST_FIELDS = {
    "schema_version", "calls", "selection", "calls_artifact", "input_snapshot_sha256",
    "gold_accessed", "classifier_fields_present",
}
PUBLIC_RUN_FIELDS = {
    "schema_version", "experiment_id", "tier", "stage", "status", "started_at_utc",
    "completed_at_utc", "config", "classifier_free", "selection", "calls", "gate",
    "gate_passed", "latency_seconds", "tokens", "resources", "access", "next_gate",
}
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text", "component_id", "component_ids", "final_labels", "gold", "labels",
    "parsed_output", "raw_output", "sample_id", "sample_ids", "text",
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= SHA256_CHARS


def checked_path(root: Path, relative: str, field: str = "path") -> Path:
    candidate = Path(relative)
    require(isinstance(relative, str) and relative and not candidate.is_absolute(), f"invalid {field}")
    require(all(part not in ("", ".", "..") for part in candidate.parts), f"invalid {field}")
    root = root.resolve()
    path = (root / candidate).resolve()
    require(path == root or root in path.parents, f"{field} escapes root")
    return path


def regular_file(path: Path, field: str, *, links: int | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {field}")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), f"invalid {field}")
    if links is not None:
        require(observed.st_nlink == links, f"{field} link-count drift")
    return observed


def read_json(path: Path, field: str) -> dict[str, Any]:
    regular_file(path, field)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid {field} JSON") from exc
    require(isinstance(value, dict), f"{field} root drift")
    return value


def read_jsonl(path: Path, field: str) -> list[dict[str, Any]]:
    regular_file(path, field)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for index, line in enumerate(source):
            require(line.strip(), f"empty {field} line {index + 1}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"invalid {field} line {index + 1}") from exc
            require(isinstance(value, dict), f"{field} row drift")
            rows.append(value)
    return rows


def artifact(path: Path) -> dict[str, Any]:
    observed = regular_file(path, "artifact")
    return {"path": path.resolve().relative_to(REPO_ROOT.resolve()).as_posix(), "bytes": observed.st_size, "sha256": sha256(path)}


def verify_record(record: Any) -> Path:
    require(isinstance(record, dict) and {"path", "bytes", "sha256"} <= set(record), "artifact schema drift")
    path = checked_path(REPO_ROOT, record["path"], "artifact")
    observed = regular_file(path, "artifact")
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], "artifact drift")
    return path


def verify_private_record(record: Any, private_root: Path, name: str) -> Path:
    path = verify_record(record)
    require(path == (private_root / name).resolve(), "private artifact path drift")
    observed = os.lstat(path)
    require(observed.st_uid == os.getuid() and observed.st_nlink == 1 and f"{stat.S_IMODE(observed.st_mode):04o}" == "0600", "private artifact privacy drift")
    return path


def atomic_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        if os.path.lexists(path):
            path.unlink()
        raise


def peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def load_validator(record: dict[str, Any]) -> Any:
    path = verify_record(record)
    name = "sqma003_validator_v2_for_independent_verifier"
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "validator import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_config(config: dict[str, Any]) -> None:
    require(config.get("schema_version") == "sqma-003-classifier-free-agent-preflight-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-003", "config identity drift")
    auth = config["authorization"]
    false_keys = (
        "adapter_loading", "model_training", "gold_access", "accuracy_scoring",
        "train_capable_access", "consumer_gold_access", "fold3_access", "fold4_access",
        "validation_access", "test_access", "network", "external_tools", "automatic_next_stage",
    )
    require(all(auth.get(key) is False for key in false_keys), "authorization drift")
    require(config["inputs"]["allowed_fields"] == list(INPUT_FIELD_ORDER), "input field drift")
    require([item["fold_id"] for item in config["inputs"]["gold_free_snapshots"]] == [0, 1, 2], "input fold drift")
    require(config["selection"]["components"] == 32 and config["call_plan"]["physical_call_cap"] == 144, "plan drift")
    require(config["generation"]["qwen_repair_calls"] == 0 and config["model"]["adapter"] is None, "generation/model drift")
    for name, record in config["implementation"].items():
        require(isinstance(record, dict) and set(record) == {"path", "bytes", "sha256"}, f"implementation schema drift: {name}")
        require(type(record["bytes"]) is int and record["bytes"] > 0 and is_sha256(record["sha256"]), f"implementation unresolved: {name}")


def verify_implementations(config: dict[str, Any]) -> Any:
    for name, record in config["implementation"].items():
        path = verify_record(record)
        if name == "verifier":
            require(path == Path(__file__).resolve(), "verifier path drift")
    return load_validator(config["implementation"]["validator"])


def verify_model_inventory(config: dict[str, Any]) -> dict[str, Any]:
    model = config["model"]
    archive_root = Path(
        os.environ.get(model["archive_root_env"], model["audited_archive_root"])
    ).expanduser().resolve()
    require(archive_root.is_dir(), "archive root missing")
    manifest_path = checked_path(archive_root, model["manifest_path"], "model manifest")
    observed = regular_file(manifest_path, "model manifest")
    require(
        observed.st_size == model["manifest_bytes"]
        and sha256(manifest_path) == model["manifest_sha256"],
        "model manifest drift",
    )
    manifest = read_json(manifest_path, "model manifest")
    require(
        manifest.get("repo_id") == model["repo_id"]
        and manifest.get("revision") == model["revision"],
        "model identity drift",
    )
    files = manifest.get("mlx_bf16", {}).get("files")
    require(isinstance(files, list) and len(files) == model["file_count"], "model inventory drift")
    require(
        sum(int(item["bytes"]) for item in files) == model["total_bytes"],
        "model inventory bytes drift",
    )
    model_root = checked_path(archive_root, model["relative_path"], "model root")
    require(model_root.is_dir() and not model_root.is_symlink(), "model root invalid")
    for item in files:
        path = checked_path(model_root, item["path"], "model file")
        file_stat = regular_file(path, "model file")
        require(
            file_stat.st_size == item["bytes"] and sha256(path) == item["sha256"],
            "model file drift",
        )
    return {
        "repo_id": model["repo_id"],
        "revision": model["revision"],
        "manifest_sha256": model["manifest_sha256"],
        "file_count": len(files),
        "total_bytes": model["total_bytes"],
        "model_loaded": False,
    }


def load_inputs(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    root = checked_path(REPO_ROOT, config["inputs"]["private_root"], "input root")
    rows: list[dict[str, Any]] = []
    hashes: list[str] = []
    for spec in config["inputs"]["gold_free_snapshots"]:
        path = checked_path(root, spec["path"], "input")
        observed = regular_file(path, "input", links=1)
        require(observed.st_uid == os.getuid() and f"{stat.S_IMODE(observed.st_mode):04o}" == "0600", "input privacy drift")
        require(observed.st_size == spec["bytes"] and sha256(path) == spec["sha256"], "input identity drift")
        values = read_jsonl(path, "input")
        require(len(values) == spec["rows"], "input row drift")
        components = set()
        for row in values:
            require(set(row) == INPUT_FIELDS and row["fold_id"] == spec["fold_id"], "input schema/fold drift")
            components.add(row["component_id"])
        require(len(components) == spec["components"], "input component drift")
        rows.extend(values)
        hashes.append(spec["sha256"])
    require(len(rows) == 2016, "combined input drift")
    return rows, hashes


def select_rows(config: dict[str, Any], rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    representatives: dict[str, dict[str, Any]] = {}
    for row in rows:
        prior = representatives.get(row["component_id"])
        if prior is None or row["source_ordinal"] < prior["source_ordinal"]:
            representatives[row["component_id"]] = row
    require(len(representatives) == 1963, "component count drift")
    namespace = config["selection"]["namespace"]
    return sorted(representatives.values(), key=lambda row: hashlib.sha256(f"{namespace}|{row['component_id']}".encode()).hexdigest())[:32]


def validate_selection(config: dict[str, Any], selection: dict[str, Any], inputs: Sequence[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    require(set(selection) == SELECTION_FIELDS, "selection schema drift")
    require(selection["schema_version"] == "sqma-003-selection-v1" and selection["namespace"] == config["selection"]["namespace"], "selection identity drift")
    require(isinstance(selection["rows"], list) and len(selection["rows"]) == 32, "selection count drift")
    expected = select_rows(config, inputs)
    by_rank: dict[int, dict[str, Any]] = {}
    for rank, (observed, source) in enumerate(zip(selection["rows"], expected, strict=True)):
        require(isinstance(observed, dict) and set(observed) == SELECTION_ROW_FIELDS, "selection row schema drift")
        stratum = "shakedown" if rank < 8 else "locked"
        require(observed["selection_rank"] == rank and observed["selection_stratum"] == stratum, "selection rank/stratum drift")
        for key in ("sample_id", "component_id", "fold_id", "source_ordinal"):
            require(observed[key] == source[key], f"selection source drift: {key}")
        by_rank[rank] = {**source, "selection_rank": rank, "selection_stratum": stratum}
    return by_rank


def fallback_evidence() -> dict[str, Any]:
    return {
        "schema_version": "evidence-appraisal-v2", "candidate_emotions": [], "evidence_spans": [],
        "expression_type": "unclear", "insufficient_evidence": True,
        "appraisal": {"goal_obstruction": "unclear", "responsibility": "unclear", "control": "unclear", "certainty": "unclear", "expectation_violation": "unclear", "loss_or_threat": "unclear"},
    }


def fallback_critic() -> dict[str, Any]:
    return {"schema_version": "pragmatics-critic-v2", "reading": "unclear", "negation": "unclear", "sarcasm": "unclear", "emotion_evidence": "unclear", "recommended_emotions": [], "challenged_emotions": [], "warning_flags": []}


def seed_for(config: dict[str, Any], system: str, sample: str, role: str, call: int) -> int:
    material = f"{config['generation']['seed_namespace']}|{system}|{sample}|{role}|{call}"
    return int.from_bytes(hashlib.sha256(material.encode()).digest()[:4], "big")


def expected_slots(by_rank: Mapping[int, dict[str, Any]]) -> list[dict[str, Any]]:
    slots = []
    for rank in range(32):
        for index, role in enumerate(("evidence_appraisal", "pragmatics_critic", "judge")):
            slots.append({"selection_rank": rank, "selection_stratum": by_rank[rank]["selection_stratum"], "system_id": "S3", "role": role, "call_index": index})
    for system in ("single_pool", "provisional_s2b"):
        for rank in range(8, 16):
            for index in range(3):
                slots.append({"selection_rank": rank, "selection_stratum": "locked", "system_id": system, "role": "single_agent", "call_index": index})
    return slots


def output_diagnostics(raw: str, text: str, allowed: set[str]) -> tuple[int, int, int]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return 0, 0, 0
    claimed = exact = out = 0
    stack = [value]
    label_keys = {"candidate_emotions", "recommended_emotions", "challenged_emotions", "emotions"}
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "evidence_spans" and isinstance(child, list):
                    claimed += len(child)
                    exact += sum(isinstance(span, str) and span in text for span in child)
                if key in label_keys and isinstance(child, list):
                    out += sum(isinstance(label, str) and label not in allowed for label in child)
                stack.append(child)
        elif isinstance(item, list):
            stack.extend(item)
    return claimed, exact, out


def numeric_summary(values: list[float]) -> dict[str, float]:
    require(values, "empty numeric summary")
    ordered = sorted(values)
    def q(p: float) -> float:
        return ordered[min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)]
    return {"min": ordered[0], "median": q(0.5), "p95": q(0.95), "max": ordered[-1], "mean": sum(ordered) / len(ordered)}


def validate_calls(config: dict[str, Any], validator: Any, calls: Sequence[dict[str, Any]], by_rank: Mapping[int, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], float]:
    slots = expected_slots(by_rank)
    require(len(calls) == len(slots) == 144, "call inventory drift")
    parsed_s3: dict[int, dict[str, Any]] = defaultdict(dict)
    totals: Counter[str] = Counter(); valid: Counter[str] = Counter()
    fallback_rows: set[int] = set(); single_votes: dict[int, list[tuple[str, ...]]] = defaultdict(list)
    claimed = exact = out = cap_hits = generated_total = 0
    latencies: dict[str, list[float]] = defaultdict(list); prefill: dict[str, list[float]] = defaultdict(list); generated: dict[str, list[float]] = defaultdict(list)
    allowed = set(validator.LABEL_ORDER)
    for record, slot in zip(calls, slots, strict=True):
        require(isinstance(record, dict) and set(record) == CALL_FIELDS, "call schema drift")
        require(all(record[key] == value for key, value in slot.items()), "call plan drift")
        selected = by_rank[record["selection_rank"]]
        require(all(record[key] == selected[key] for key in ("sample_id", "component_id", "source_ordinal")), "call selection drift")
        require(record["seed"] == seed_for(config, record["system_id"], record["sample_id"], record["role"], record["call_index"]), "seed drift")
        require(is_sha256(record["prompt_sha256"]), "prompt hash drift")
        require(type(record["prefill_tokens"]) is int and 0 < record["prefill_tokens"] <= 4096, "prefill token drift")
        require(type(record["generated_tokens"]) is int and 0 <= record["generated_tokens"] <= config["generation"]["max_new_tokens"][record["role"]], "generated token drift")
        require(isinstance(record["finish_reason"], str) and isinstance(record["raw_output"], str), "call terminal drift")
        require(all(type(record[key]) in (int, float) and math.isfinite(record[key]) and record[key] >= 0 for key in ("latency_seconds", "peak_memory_gb")), "call numeric drift")
        require(isinstance(record["text_meta"], dict) and set(record["text_meta"]) == TEXT_META_FIELDS, "text metadata drift")
        meta = record["text_meta"]
        require(type(meta["original_tokens"]) is int and type(meta["analysis_tokens"]) is int and type(meta["was_truncated"]) is bool, "text metadata type drift")
        require(0 < meta["analysis_tokens"] <= 1024 and meta["original_tokens"] >= meta["analysis_tokens"], "text token drift")
        require(meta["was_truncated"] is False and meta["original_tokens"] == meta["analysis_tokens"], "truncated context not independently replayable")
        context: dict[str, Any] = {"analysis_text": selected["text"], "ontology": validator.ONTOLOGY}
        role = record["role"]
        if record["system_id"] == "S3" and role in {"pragmatics_critic", "judge"}:
            context["evidence_appraisal"] = parsed_s3[record["selection_rank"]].get("evidence_appraisal", fallback_evidence())
        if record["system_id"] == "S3" and role == "judge":
            context["pragmatics_critic"] = parsed_s3[record["selection_rank"]].get("pragmatics_critic", fallback_critic())
        parsed = None; error = None
        try:
            parsed = validator.validate_output(role, record["raw_output"], context)
        except validator.AgentOutputError as exc:
            error = exc.code
        require(record["parsed_output"] == parsed and record["validation_error"] == error, "semantic replay drift")
        labels = validator.final_labels_from_validated(role, parsed) if parsed is not None and role in {"judge", "single_agent"} else []
        require(record["final_labels"] == labels, "final-label drift")
        if record["system_id"] == "S3" and parsed is not None:
            parsed_s3[record["selection_rank"]][role] = parsed
        if record["selection_stratum"] == "locked":
            totals[role] += 1; valid[role] += int(error is None)
            if record["system_id"] == "S3" and error is not None:
                fallback_rows.add(record["selection_rank"])
        if record["system_id"] == "single_pool":
            single_votes[record["selection_rank"]].append(tuple(labels))
        a, b, c = output_diagnostics(record["raw_output"], selected["text"], allowed)
        claimed += a; exact += b; out += c
        cap_hits += int(record["finish_reason"] == "length")
        generated_total += record["generated_tokens"]
        latencies[role].append(float(record["latency_seconds"])); prefill[role].append(float(record["prefill_tokens"])); generated[role].append(float(record["generated_tokens"]))
    per_role = {role: valid[role] / totals[role] for role in sorted(totals)}
    agreements = [max(Counter(single_votes[rank]).values()) / 3 for rank in range(8, 16)]
    metrics = {
        "planned_calls_complete": True, "planned_call_terminal_rate": 1.0,
        "raw_schema_valid_rate": sum(valid.values()) / sum(totals.values()),
        "per_role_valid_rate": per_role, "technical_fallback_rows": len(fallback_rows),
        "token_cap_hits": cap_hits, "mean_modal_exact_label_set_agreement": sum(agreements) / len(agreements),
        "evidence_exact_substring_rate": exact / claimed if claimed else 1.0,
        "out_of_ontology_labels": out, "generated_tokens_total": generated_total,
    }
    latency_summary = {role: numeric_summary(values) for role, values in latencies.items()}
    token_summary = {role: {"prefill": numeric_summary(prefill[role]), "generated": numeric_summary(generated[role])} for role in sorted(prefill)}
    projected = 1.25 * 672 * (latency_summary["evidence_appraisal"]["p95"] + latency_summary["pragmatics_critic"]["p95"] + latency_summary["judge"]["p95"] + 3 * latency_summary["single_agent"]["p95"])
    return metrics, latency_summary, token_summary, projected


def gate_passes(config: dict[str, Any], metrics: dict[str, Any], projected: float) -> bool:
    gate = config["pass_gate"]
    return (
        metrics["planned_call_terminal_rate"] >= gate["planned_call_terminal_rate"]
        and metrics["raw_schema_valid_rate"] >= gate["raw_schema_valid_rate_overall_minimum"]
        and all(value >= gate["raw_schema_valid_rate_per_role_minimum"] for value in metrics["per_role_valid_rate"].values())
        and metrics["technical_fallback_rows"] <= gate["maximum_locked_S3_technical_fallback_rows"]
        and metrics["evidence_exact_substring_rate"] >= gate["evidence_exact_substring_rate"]
        and metrics["out_of_ontology_labels"] <= gate["out_of_ontology_labels"]
        and metrics["token_cap_hits"] <= gate["maximum_token_cap_hits"]
        and metrics["mean_modal_exact_label_set_agreement"] >= gate["mean_modal_exact_label_set_agreement_minimum"]
        and metrics["generated_tokens_total"] <= config["resources"]["maximum_generated_tokens"]
        and projected <= config["resources"]["maximum_full_tune_projected_wall_seconds"]
    )


def validate_private_tree(root: Path, config: dict[str, Any]) -> int:
    root_stat = os.lstat(root)
    require(
        stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode)
        and root_stat.st_uid == os.getuid()
        and f"{stat.S_IMODE(root_stat.st_mode):04o}" == "0700",
        "private root privacy drift",
    )
    actual = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    require(actual == sorted(config["outputs"]["private_allowed_files"]), "private inventory drift")
    total = 0
    for path in root.rglob("*"):
        observed = os.lstat(path)
        require(not stat.S_ISLNK(observed.st_mode) and observed.st_uid == os.getuid(), "private owner/symlink drift")
        if path.is_dir():
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0700", "private directory mode drift")
        else:
            require(stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1 and f"{stat.S_IMODE(observed.st_mode):04o}" == "0600", "private file mode drift")
            total += observed.st_size
    require(total <= config["resources"]["maximum_private_output_bytes"], "private byte cap exceeded")
    return total


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


def require_public_safe(value: Any, private_root: Path) -> None:
    require(not public_sensitive_paths(value), "public row-level leak")
    require(str(private_root.resolve()) not in json.dumps(value, ensure_ascii=False), "public private-path leak")


def verify(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    config = read_json(config_path, "config")
    validate_config(config)
    validator = verify_implementations(config)
    require("run_sqma003_agent_preflight" not in sys.modules, "runner imported")
    require(not (FORBIDDEN_FRAMEWORK_ROOTS & set(sys.modules)), "model framework imported")
    for record in config["prerequisites"].values():
        verify_record(record)
    model_identity = verify_model_inventory(config)
    public_root = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"], "public root")
    private_root = checked_path(REPO_ROOT, config["outputs"]["private_attempt_dir"], "private root")
    require(public_root.is_dir() and private_root.is_dir(), "attempt roots missing")
    require(not os.path.lexists(public_root / "verification.json") and not os.path.lexists(public_root / "complete.json"), "verification already exists")
    private_bytes = validate_private_tree(private_root, config)
    selection_path = private_root / "selection.json"; calls_path = private_root / "calls.jsonl"; manifest_path = private_root / "private-manifest.json"
    selection = read_json(selection_path, "selection"); calls = read_jsonl(calls_path, "calls"); manifest = read_json(manifest_path, "private manifest")
    require(set(manifest) == PRIVATE_MANIFEST_FIELDS and manifest["schema_version"] == "sqma-003-private-manifest-v1" and manifest["calls"] == 144, "private manifest drift")
    verify_private_record(manifest["selection"], private_root, "selection.json"); verify_private_record(manifest["calls_artifact"], private_root, "calls.jsonl")
    require(manifest["gold_accessed"] is False and manifest["classifier_fields_present"] is False, "private boundary drift")
    inputs, hashes = load_inputs(config)
    require(manifest["input_snapshot_sha256"] == hashes, "input lineage drift")
    by_rank = validate_selection(config, selection, inputs)
    metrics, latency_summary, token_summary, projected_without_load = validate_calls(config, validator, calls, by_rank)
    claim = read_json(public_root / "run-claim.json", "run claim"); run = read_json(public_root / "run.json", "run")
    require(set(run) == PUBLIC_RUN_FIELDS and run["schema_version"] == "sqma-003-run-v1" and run["experiment_id"] == "SQMA-003" and run["status"] == "CompletedAwaitingVerification", "public run drift")
    require(run["config"] == artifact(config_path), "config binding drift")
    expected_claim = {"schema_version": "sqma-003-run-claim-v1", "experiment_id": "SQMA-003", "status": "ClaimedBeforeModelLoad", "config": artifact(config_path), "classifier_free": True, "gold_access": False, "model_training": False, "planned_calls": 144}
    require(claim == expected_claim, "run claim drift")
    require(run["classifier_free"] is True, "classifier-free drift")
    require(run["selection"] == {"components": 32, "shakedown": 8, "locked": 24, "selection_sha256": sha256(selection_path)}, "selection summary drift")
    require(run["calls"] == {"physical": 144, "by_role": {"evidence_appraisal": 32, "pragmatics_critic": 32, "judge": 32, "single_agent": 48}}, "call summary drift")
    require(run["latency_seconds"] == latency_summary and run["tokens"] == token_summary, "token/latency summary drift")
    projection = projected_without_load + run["resources"]["model_load_seconds"]
    runner_gate = {"planned_calls_complete": metrics["planned_calls_complete"], "raw_schema_valid_rate": metrics["raw_schema_valid_rate"], "per_role_valid_rate": metrics["per_role_valid_rate"], "technical_fallback_rows": metrics["technical_fallback_rows"], "token_cap_hits": metrics["token_cap_hits"], "mean_modal_exact_label_set_agreement": metrics["mean_modal_exact_label_set_agreement"], "full_tune_projected_wall_seconds": projection}
    require(run["gate"] == runner_gate, "runner gate replay drift")
    passed = gate_passes(config, metrics, projection)
    require(run["gate_passed"] is passed and passed, "independent gate failed")
    require(run["next_gate"] == "independent_preflight_verification", "runner next gate drift")
    require_public_safe(claim, private_root); require_public_safe(run, private_root)
    resources = run["resources"]
    require(resources["wall_seconds"] <= 14400 and resources["peak_rss_bytes"] <= config["resources"]["maximum_process_rss_bytes"] and resources["mlx_peak_bytes"] <= config["resources"]["maximum_mlx_peak_bytes"] and resources["private_output_bytes"] == private_bytes, "runner resource drift")
    require(run["access"] == {"gold_accessed": False, "classifier_outputs_accessed": False, "adapter_loaded": False, "model_training": False, "network_accessed": False, "fold3_accessed": False, "fold4_accessed": False, "validation_accessed": False, "test_accessed": False}, "access drift")
    elapsed = time.monotonic() - started; peak = peak_rss_bytes(); require(elapsed <= 300 and peak <= 1073741824, "verifier resource cap")
    next_gate = "freeze_agent_tune_budget_before_fold3_materialization"
    verification = {
        "schema_version": "sqma-003-verification-v1", "experiment_id": "SQMA-003", "status": "Passed", "verified_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": artifact(config_path), "run": artifact(public_root / "run.json"), "run_claim": artifact(public_root / "run-claim.json"),
        "model_identity": model_identity,
        "private_manifest": {"logical_name": "private-manifest.json", "bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path), "mode": "0600"},
        "checks": ["identity_and_authorization", "gold_free_input_replay", "deterministic_selection", "exact_call_plan_and_seeds", "independent_v2_semantic_validation", "evidence_and_ontology", "token_latency_stability_replay", "locked_pass_gate", "resource_access_boundary", "public_privacy"],
        "aggregates": metrics, "full_tune_projected_wall_seconds": projection,
        "resources": {"wall_seconds": elapsed, "peak_rss_bytes": peak, "private_output_bytes": private_bytes},
        "access": {"gold_accessed": False, "accuracy_scored": False, "runner_imported": False, "model_framework_imported": False, "model_loaded": False, "fold3_accessed": False, "fold4_accessed": False, "validation_accessed": False, "test_accessed": False, "files_written_private": False},
        "preflight_gate": "Passed", "next_gate": next_gate,
        "claim_boundary": "Independent model-free replay of SQMA-003 gold-free selection, classifier-free calls, v2 semantic validity, evidence, tokens, stability, and locked gates; no gold, accuracy, training, model, fold 3/4, validation, or test access.",
    }
    require_public_safe(verification, private_root); atomic_json_exclusive(public_root / "verification.json", verification)
    complete = {"schema_version": "sqma-003-complete-v1", "experiment_id": "SQMA-003", "status": "Complete", "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verification": artifact(public_root / "verification.json"), "sqma003_complete": True, "agent_preflight_verified": True, "accuracy_scored": False, "gold_accessed": False, "model_training_executed": False, "preflight_gate": "Passed", "next_gate": next_gate}
    require_public_safe(complete, private_root); atomic_json_exclusive(public_root / "complete.json", complete)
    require(sorted(path.name for path in public_root.iterdir() if path.is_file()) == sorted(config["outputs"]["public_allowed_files"]), "public inventory drift")
    require(sum(path.stat().st_size for path in public_root.iterdir() if path.is_file()) <= config["resources"]["maximum_public_output_bytes"], "public byte cap")
    return verification, complete


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True); args = parser.parse_args()
    supplied = Path(args.config).expanduser().resolve(); require(supplied == CONFIG_PATH.resolve(), "noncanonical config")
    verification, complete = verify(supplied)
    print(json.dumps({"experiment_id": "SQMA-003", "status": verification["status"], "sqma003_complete": complete["sqma003_complete"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, VerificationError) as exc:
        print(f"SQMA-003 verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

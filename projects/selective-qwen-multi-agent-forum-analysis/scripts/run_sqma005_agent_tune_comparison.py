#!/usr/bin/env python3
"""Run the gold-free SQMA-005 classifier-free Agent-Tune producer.

The future SQMA-005 config must bind every source, implementation, model,
runtime, and budget identity before this runner can execute.  The producer reads
only the verified fold-3 gold-free snapshot.  It never receives gold or a
classifier output, never loads an adapter, and never trains a model.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gc
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import stat
import sys
import time
from typing import Any, Iterable, Mapping, Sequence, TextIO
import zipfile


sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma005_agent_tune_comparison.py"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
ROLE_ORDER = ("evidence_appraisal", "pragmatics_critic", "judge")
CALL_ORDER = (
    ("S3", "evidence_appraisal", 0),
    ("S3", "pragmatics_critic", 1),
    ("S3", "judge", 2),
    ("single_pool", "single_agent", 0),
    ("single_pool", "single_agent", 1),
    ("single_pool", "single_agent", 2),
)
EXPECTED_ROWS = 672
EXPECTED_COMPONENTS = 657
EXPECTED_PHYSICAL_CALLS = 4032
EXPECTED_GENERATED_CEILING = 1_161_216
PROMPT_V2_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/prompts/"
    "agent-bundle-v2-classifier-free.json"
)
SCHEMA_V2_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/schemas/"
    "agent-output-v2.schema.json"
)
VALIDATOR_V2_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
    "validate_agent_output_v2.py"
)
RUNNER_RELATIVE = RUNNER_PATH.relative_to(REPO_ROOT).as_posix()
TEST_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/tests/"
    "test_sqma005_agent_tune_comparison.py"
)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
SENSITIVE_PUBLIC_KEYS = {
    "analysis_text",
    "component_id",
    "component_ids",
    "evidence_spans",
    "final_labels",
    "gold",
    "labels",
    "logits",
    "parsed_output",
    "probabilities",
    "raw_output",
    "sample_id",
    "sample_ids",
    "source_ordinal",
    "source_ordinals",
    "text",
}

EMPTY_EVIDENCE = {
    "schema_version": "evidence-appraisal-v2",
    "candidate_emotions": [],
    "evidence_spans": [],
    "expression_type": "unclear",
    "insufficient_evidence": True,
    "appraisal": {
        "goal_obstruction": "unclear",
        "responsibility": "unclear",
        "control": "unclear",
        "certainty": "unclear",
        "expectation_violation": "unclear",
        "loss_or_threat": "unclear",
    },
}
EMPTY_CRITIC = {
    "schema_version": "pragmatics-critic-v2",
    "reading": "unclear",
    "negation": "unclear",
    "sarcasm": "unclear",
    "emotion_evidence": "unclear",
    "recommended_emotions": [],
    "challenged_emotions": [],
    "warning_flags": [],
}


class ProducerError(RuntimeError):
    """Raised when an SQMA-005 producer gate fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProducerError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_for(namespace: str, system_id: str, sample_id: str, role: str, call_index: int) -> int:
    material = f"{namespace}|{system_id}|{sample_id}|{role}|{call_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big", signed=False)


def strict_majority(votes: Sequence[Iterable[str] | None]) -> list[str]:
    require(bool(votes), "votes must not be empty")
    normalized: list[set[str]] = []
    for vote in votes:
        values = [] if vote is None else list(vote)
        require(len(values) == len(set(values)), "duplicate vote label")
        require(all(label in LABEL_ORDER for label in values), "unknown vote label")
        require(values == sorted(values, key=LABEL_ORDER.index), "vote label order drift")
        normalized.append(set(values))
    threshold = len(normalized) / 2
    return [label for label in LABEL_ORDER if sum(label in vote for vote in normalized) > threshold]


def choose_s2b_k(
    s3_ceiling_tokens: int,
    single_call_ceiling_tokens: int,
    tolerance_fraction: float,
) -> tuple[int, int, float]:
    require(s3_ceiling_tokens > 0 and single_call_ceiling_tokens > 0, "invalid token ceiling")
    require(0 <= tolerance_fraction < 1, "invalid S2b tolerance")
    for k in (3, 2):
        used = k * single_call_ceiling_tokens
        utilization = used / s3_ceiling_tokens
        if used <= s3_ceiling_tokens and utilization >= 1 - tolerance_fraction:
            return k, used, utilization
    raise ProducerError("no whole-call S2b allocation satisfies the frozen token ceiling")


def effective_s3_labels(
    role_valid: Sequence[bool], judge_labels: Sequence[str], judge_abstained: bool
) -> list[str]:
    require(len(role_valid) == 3, "S3 must have three role-valid flags")
    if not all(role_valid) or judge_abstained:
        return []
    values = list(judge_labels)
    require(values == sorted(set(values), key=LABEL_ORDER.index), "Judge labels drift")
    return values


def planned_call_slots(rows: int = EXPECTED_ROWS) -> list[tuple[int, str, str, int]]:
    require(rows > 0, "row count must be positive")
    return [
        (row_ordinal, system_id, role, call_index)
        for row_ordinal in range(rows)
        for system_id, role, call_index in CALL_ORDER
    ]


def numeric_summary(values: Sequence[float]) -> dict[str, float]:
    require(bool(values), "numeric summary requires values")
    ordered = sorted(float(value) for value in values)

    def quantile(fraction: float) -> float:
        index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
        return ordered[index]

    return {
        "min": ordered[0],
        "median": quantile(0.5),
        "p95": quantile(0.95),
        "max": ordered[-1],
        "mean": sum(ordered) / len(ordered),
    }


def _has_wildcard(value: str) -> bool:
    return any(character in value for character in "*?[]{}")


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"invalid {label} path")
    candidate = Path(relative)
    require(not candidate.is_absolute() and ".." not in candidate.parts, f"unsafe {label} path")
    require(not _has_wildcard(relative), f"wildcard {label} path")
    lexical = root / candidate
    resolved_root = root.resolve()
    resolved = lexical.resolve()
    require(resolved == resolved_root or resolved_root in resolved.parents, f"{label} path escapes root")
    current = root
    for part in candidate.parts:
        current = current / part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains symlink")
    return lexical


def regular_file(
    path: Path,
    label: str,
    *,
    mode: str | None = None,
    require_owner: bool = True,
) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), f"invalid {label}")
    if require_owner:
        require(observed.st_uid == os.getuid(), f"{label} owner drift")
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        require(key not in value, "duplicate JSON key")
        value[key] = child
    return value


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_file(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProducerError(f"invalid {label}") from exc
    require(isinstance(value, dict), f"{label} root must be object")
    return value


def artifact_record(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    base = REPO_ROOT if root is None else root
    return {
        "path": path.resolve().relative_to(base.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def verify_record(record: Any, label: str) -> Path:
    require(isinstance(record, dict) and set(record) >= {"path", "bytes", "sha256"}, f"invalid {label} record")
    require(type(record["bytes"]) is int and record["bytes"] > 0, f"invalid {label} bytes")
    require(isinstance(record["sha256"], str) and SHA_RE.fullmatch(record["sha256"]), f"invalid {label} hash")
    path = checked_path(REPO_ROOT, record["path"], label)
    observed = regular_file(path, label)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} identity drift")
    return path


def load_module(name: str, record: Mapping[str, Any]) -> Any:
    path = verify_record(record, name)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"{name} import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path.resolve(), f"{name} import drift")
    return module


def validate_no_producer_gold_reference(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = key.lower().replace("-", "_")
            if lowered in {"gold", "consumer_gold", "train_capable", "classifier_result"}:
                raise ProducerError(f"forbidden producer field at {path}.{key}")
            validate_no_producer_gold_reference(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_no_producer_gold_reference(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        require("consumer-gold" not in lowered and "train-capable" not in lowered, f"forbidden producer source at {path}")


def validate_config(config: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "experiment_id",
        "tier",
        "stage",
        "registered_at",
        "authorization",
        "implementation",
        "prerequisites",
        "input",
        "model",
        "runtime",
        "generation",
        "call_plan",
        "budget",
        "outputs",
        "commands",
    }
    require(set(config) == required, "config top-level schema drift")
    require(config["schema_version"] == "sqma-005-agent-tune-matched-comparison-v1", "config schema drift")
    require(config["experiment_id"] == "SQMA-005", "experiment identity drift")
    authorization = config["authorization"]
    require(isinstance(authorization, dict), "authorization missing")
    required_false = {
        "gold_access",
        "classifier_access",
        "adapter_loading",
        "training",
        "optimizer",
        "validation_access",
        "test_access",
        "fold4_access",
        "network",
        "external_tools",
        "automatic_next_stage",
    }
    require(all(authorization.get(key) is False for key in required_false), "producer authorization drift")
    require(authorization.get("producer") is True and authorization.get("model_loading") is True and authorization.get("generation") is True, "producer execution not authorized")
    validate_no_producer_gold_reference({"input": config["input"]})

    implementation = config["implementation"]
    require(isinstance(implementation, dict), "implementation missing")
    for key, record in implementation.items():
        verify_record(record, f"implementation.{key}")
    expected_paths = {
        "prompt_bundle": PROMPT_V2_RELATIVE,
        "output_schema": SCHEMA_V2_RELATIVE,
        "validator": VALIDATOR_V2_RELATIVE,
        "runner": RUNNER_RELATIVE,
        "unit_tests": TEST_RELATIVE,
    }
    for key, path in expected_paths.items():
        require(key in implementation and implementation[key]["path"] == path, f"implementation.{key} path drift")
    prerequisites = config["prerequisites"]
    require(isinstance(prerequisites, dict) and {"sqma004_complete", "sqma004_verification"} <= set(prerequisites), "SQMA-004 prerequisites missing")
    for key, record in prerequisites.items():
        verify_record(record, f"prerequisite.{key}")

    input_contract = config["input"]
    require(
        isinstance(input_contract, dict)
        and set(input_contract) == {"private_root", "gold_free_snapshot"},
        "input contract drift",
    )
    snapshot = input_contract["gold_free_snapshot"]
    require(
        isinstance(snapshot, dict)
        and set(snapshot) >= {"path", "bytes", "sha256", "mode", "fold_id", "rows", "components"},
        "snapshot record drift",
    )
    require(snapshot["mode"] == "0600" and snapshot["fold_id"] == 3, "snapshot scope drift")
    require(snapshot["rows"] == EXPECTED_ROWS and snapshot["components"] == EXPECTED_COMPONENTS, "snapshot count drift")

    model = config["model"]
    require(model.get("repo_id") == "Qwen/Qwen3-4B" and model.get("adapter") is None, "model identity/adapter drift")
    generation = config["generation"]
    require(generation.get("enable_thinking") is False, "thinking mode drift")
    require(
        (generation.get("temperature"), generation.get("top_p"), generation.get("top_k"))
        == (0.6, 0.95, 20),
        "sampler drift",
    )
    require(generation.get("context_token_cap") == 4096 and generation.get("analysis_text_token_cap") == 1024, "token cap drift")
    require(generation.get("qwen_repair_calls") == 0, "repair drift")
    require(
        generation.get("max_new_tokens")
        == {"evidence_appraisal": 256, "pragmatics_critic": 192, "judge": 128, "single_agent": 384},
        "generation cap drift",
    )
    call_plan = config["call_plan"]
    require(
        call_plan.get("rows") == EXPECTED_ROWS
        and call_plan.get("calls_per_row") == 6
        and call_plan.get("physical_calls") == EXPECTED_PHYSICAL_CALLS
        and call_plan.get("single_pool_calls_per_row") == 3
        and call_plan.get("S3_calls_per_row") == 3
        and call_plan.get("S1_reuses_single_call_0") is True
        and call_plan.get("S2a_reuses_single_calls") == [0, 1, 2]
        and call_plan.get("S2b_reuses_single_prefix") is True,
        "call plan drift",
    )
    budget = config["budget"]
    require(budget.get("maximum_generated_tokens") == EXPECTED_GENERATED_CEILING, "generated ceiling drift")
    require(budget.get("S2b_k_candidates") == [2, 3], "S2b K drift")
    tolerance = budget.get("S2b_ceiling_tolerance_fraction")
    require(isinstance(tolerance, (int, float)) and 0 <= tolerance < 1, "S2b tolerance drift")
    require(budget.get("maximum_wall_seconds", 172801) <= 172800, "wall cap exceeds 48 hours")

    outputs = config["outputs"]
    require(
        isinstance(outputs, dict)
        and outputs.get("private_allowed_files")
        == ["input-seal.json", "calls.jsonl", "systems.npz", "private-manifest.json"]
        and outputs.get("public_allowed_files")
        == ["run-claim.json", "run.json", "score.json", "verification.json", "complete.json"],
        "output allowlist drift",
    )


def verify_prerequisites(config: Mapping[str, Any]) -> None:
    complete = read_json(verify_record(config["prerequisites"]["sqma004_complete"], "SQMA-004 complete"), "SQMA-004 complete")
    require(complete.get("sqma004_complete") is True and complete.get("agent_tune_inputs_verified") is True, "SQMA-004 completion drift")
    require(complete.get("training_executed") is False and complete.get("model_loaded") is False, "SQMA-004 authority drift")


def load_input(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], Path]:
    input_contract = config["input"]
    root = checked_path(REPO_ROOT, input_contract["private_root"], "input root")
    snapshot = input_contract["gold_free_snapshot"]
    path = checked_path(root, snapshot["path"], "gold-free fold-3 snapshot")
    observed = regular_file(path, "gold-free fold-3 snapshot", mode="0600")
    require(observed.st_size == snapshot["bytes"] and sha256(path) == snapshot["sha256"], "input snapshot identity drift")
    rows: list[dict[str, Any]] = []
    expected_fields = {"schema_version", "protocol_id", "sample_id", "component_id", "fold_id", "source_ordinal", "text"}
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            try:
                row = json.loads(line, object_pairs_hook=strict_pairs)
            except json.JSONDecodeError as exc:
                raise ProducerError("input JSONL decode failed") from exc
            require(isinstance(row, dict) and set(row) == expected_fields, "input row schema drift")
            require(row["schema_version"] == "sqma-gold-free-inference-snapshot-v1", "input row identity drift")
            require(row["fold_id"] == 3 and isinstance(row["text"], str) and row["text"], "input fold/text drift")
            require(type(row["source_ordinal"]) is int, "input source ordinal drift")
            rows.append(row)
    require(len(rows) == EXPECTED_ROWS, "input row count drift")
    require(len({row["sample_id"] for row in rows}) == EXPECTED_ROWS, "input sample identity drift")
    require(len({row["component_id"] for row in rows}) == EXPECTED_COMPONENTS, "input component count drift")
    ordinals = [row["source_ordinal"] for row in rows]
    require(ordinals == sorted(ordinals) and len(ordinals) == len(set(ordinals)), "input source order drift")
    return rows, path


def build_output_contracts(bundle: Mapping[str, Any]) -> dict[str, str]:
    examples = bundle.get("concrete_output_examples")
    require(isinstance(examples, dict), "concrete output examples missing")
    contracts: dict[str, str] = {}
    for role in (*ROLE_ORDER, "single_agent"):
        require(role in examples and isinstance(examples[role], dict), f"missing {role} example")
        encoded = json.dumps(examples[role], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        require("|" not in encoded, "pipe placeholder in output contract")
        contracts[role] = (
            "Use this example only for JSON shape and value types; its semantic values are not a "
            "default answer. Return exactly one JSON object with the same keys and types. "
            "evidence_spans contains exact-substring strings only; evidence_refs contains zero-based "
            "integers only. Concrete valid JSON example: "
            + encoded
        )
    return contracts


def truncate_analysis_text(tokenizer: Any, text: str, cap: int) -> tuple[str, dict[str, Any]]:
    token_ids = list(tokenizer.encode(text, add_special_tokens=False))
    if len(token_ids) <= cap:
        return text, {
            "original_tokens": len(token_ids),
            "analysis_tokens": len(token_ids),
            "was_truncated": False,
        }
    analysis_text = tokenizer.decode(token_ids[:cap], skip_special_tokens=True)
    require(isinstance(analysis_text, str) and analysis_text, "analysis-text truncation failed")
    analysis_ids = list(tokenizer.encode(analysis_text, add_special_tokens=False))
    require(len(analysis_ids) <= cap, "analysis-text roundtrip exceeds cap")
    return analysis_text, {
        "original_tokens": len(token_ids),
        "analysis_tokens": len(analysis_ids),
        "was_truncated": True,
    }


def call_text_metadata(
    source_text: str, analysis_text: str, token_metadata: Mapping[str, Any]
) -> dict[str, Any]:
    require(isinstance(source_text, str) and isinstance(analysis_text, str), "text metadata input drift")
    require(
        set(token_metadata) == {"original_tokens", "analysis_tokens", "was_truncated"},
        "token metadata schema drift",
    )
    require(
        type(token_metadata["original_tokens"]) is int
        and type(token_metadata["analysis_tokens"]) is int
        and type(token_metadata["was_truncated"]) is bool,
        "token metadata type drift",
    )
    if not token_metadata["was_truncated"]:
        require(analysis_text == source_text, "untruncated analysis text differs from source")
    return {
        "original_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "analysis_sha256": hashlib.sha256(analysis_text.encode("utf-8")).hexdigest(),
        "original_token_count": token_metadata["original_tokens"],
        "analysis_token_count": token_metadata["analysis_tokens"],
        "was_truncated": token_metadata["was_truncated"],
        "model_free_truncation_replay": not token_metadata["was_truncated"],
    }


def render_prompt(
    tokenizer: Any,
    bundle: Mapping[str, Any],
    output_contracts: Mapping[str, str],
    role: str,
    context: Mapping[str, Any],
    context_cap: int,
    max_new_tokens: int,
) -> tuple[list[int], list[dict[str, str]]]:
    role_spec = bundle["roles"][role]
    require(set(context) == set(role_spec["visible_fields"]), "role context allowlist drift")
    system = "\n".join([*bundle["shared_rules"], role_spec["system"], output_contracts[role]])
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Input JSON:\n" + canonical_json(context)},
    ]
    prompt_ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        return_dict=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if isinstance(prompt_ids, dict):
        prompt_ids = prompt_ids["input_ids"]
    ids = [int(token) for token in prompt_ids]
    require(ids and len(ids) + max_new_tokens <= context_cap, "constructed prompt exceeds context budget")
    return ids, messages


def abstained(role: str, parsed: Mapping[str, Any] | None) -> bool:
    if parsed is None:
        return False
    decision = parsed if role == "judge" else parsed.get("decision") if role == "single_agent" else None
    return isinstance(decision, Mapping) and decision.get("action") == "abstain"


class ResourceGuard:
    def __init__(self, config: Mapping[str, Any], mx: Any, started: float | None = None) -> None:
        self.config = config
        self.mx = mx
        self.started = time.monotonic() if started is None else started
        self.generated_tokens = 0

    def snapshot(self) -> dict[str, Any]:
        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform.startswith("linux"):
            rss *= 1024
        return {
            "wall_seconds": time.monotonic() - self.started,
            "peak_rss_bytes": rss,
            "mlx_peak_bytes": int(self.mx.get_peak_memory()),
            "generated_tokens": self.generated_tokens,
        }

    def check(self) -> dict[str, Any]:
        observed = self.snapshot()
        budget = self.config["budget"]
        require(observed["wall_seconds"] <= budget["maximum_wall_seconds"], "wall budget exceeded")
        require(observed["peak_rss_bytes"] <= budget["maximum_process_rss_bytes"], "RSS budget exceeded")
        require(observed["mlx_peak_bytes"] <= budget["maximum_mlx_peak_bytes"], "MLX budget exceeded")
        require(observed["generated_tokens"] <= budget["maximum_generated_tokens"], "generated-token budget exceeded")
        return observed


def write_json_exclusive(path: Path, value: Mapping[str, Any], mode: int) -> int:
    encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(encoded)
        target.flush()
        os.fsync(target.fileno())
    path.chmod(mode)
    return len(encoded)


def write_call(target: TextIO, record: Mapping[str, Any]) -> None:
    target.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def verify_model_files(config: Mapping[str, Any]) -> tuple[Path, dict[str, Any]]:
    model = config["model"]
    archive_value = os.environ.get(model["archive_root_env"], model["audited_archive_root"])
    require(isinstance(archive_value, str) and archive_value, "model archive root missing")
    archive_root = Path(archive_value).expanduser().resolve()
    require(archive_root.is_dir(), "model archive root unavailable")
    manifest_path = checked_path(archive_root, model["manifest_path"], "model manifest")
    observed = regular_file(manifest_path, "model manifest")
    require(observed.st_size == model["manifest_bytes"] and sha256(manifest_path) == model["manifest_sha256"], "model manifest drift")
    manifest = read_json(manifest_path, "model manifest")
    require(manifest.get("repo_id") == model["repo_id"] and manifest.get("revision") == model["revision"], "model revision drift")
    inventory = manifest.get("mlx_bf16", {}).get("files")
    require(isinstance(inventory, list) and len(inventory) == model["file_count"], "model inventory drift")
    model_root = checked_path(archive_root, model["relative_path"], "model root")
    total = 0
    for item in inventory:
        require(isinstance(item, dict) and set(item) >= {"path", "bytes", "sha256"}, "model file record drift")
        path = checked_path(model_root, item["path"], "model file")
        file_stat = regular_file(path, "model file")
        require(file_stat.st_size == item["bytes"] and sha256(path) == item["sha256"], "model file drift")
        total += item["bytes"]
    require(total == model["total_bytes"], "model byte total drift")
    return model_root, {
        "repo_id": model["repo_id"],
        "revision": model["revision"],
        "manifest_sha256": model["manifest_sha256"],
        "file_count": len(inventory),
        "total_bytes": total,
        "adapter": None,
    }


def public_safe(value: Any, prefix: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            require(key not in SENSITIVE_PUBLIC_KEYS, f"public sensitive key at {prefix}.{key}")
            public_safe(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            public_safe(child, f"{prefix}[{index}]")
    elif isinstance(value, str):
        require(not value.startswith("sample-") and not value.startswith("component-"), f"public identity leak at {prefix}")


def array_metadata(array: Any) -> dict[str, Any]:
    return {"dtype": str(array.dtype), "shape": list(array.shape)}


def run(config_argument: str) -> dict[str, Any]:
    run_started = time.monotonic()
    started_at = utc_now()
    supplied = Path(config_argument).expanduser().resolve()
    require(REPO_ROOT.resolve() in supplied.parents, "config outside repository")
    config = read_json(supplied, "SQMA-005 config")
    validate_config(config)
    verify_prerequisites(config)

    outputs = config["outputs"]
    public_dir = checked_path(REPO_ROOT, outputs["public_attempt_dir"], "public output")
    private_dir = checked_path(REPO_ROOT, outputs["private_attempt_dir"], "private output")
    staging = private_dir.with_name(private_dir.name + ".staging")
    for path in (public_dir, private_dir, staging):
        require(not os.path.lexists(path), "output namespace already exists")
    free_bytes = __import__("shutil").disk_usage(REPO_ROOT).free
    require(free_bytes >= config["budget"]["minimum_free_disk_bytes"], "free disk below budget")
    public_dir.mkdir(parents=True, mode=0o755, exist_ok=False)
    claim = {
        "schema_version": "sqma-005-run-claim-v1",
        "experiment_id": "SQMA-005",
        "status": "ClaimedBeforePrivateInputOrModelLoad",
        "claimed_at_utc": utc_now(),
        "config": artifact_record(supplied),
        "planned_physical_calls": EXPECTED_PHYSICAL_CALLS,
        "classifier_free": True,
        "gold_access": False,
        "adapter_loading": False,
        "training": False,
        "next_gate": "gold_free_producer",
    }
    public_safe(claim)
    write_json_exclusive(public_dir / "run-claim.json", claim, 0o644)

    rows, input_path = load_input(config)
    prompt_path = verify_record(config["implementation"]["prompt_bundle"], "prompt bundle")
    bundle = read_json(prompt_path, "prompt bundle")
    require(bundle["schema_version"] == "sqma-agent-prompt-bundle-v2-classifier-free", "prompt bundle drift")
    validator = load_module("sqma005_validator_v2", config["implementation"]["validator"])
    output_contracts = build_output_contracts(bundle)
    model_path, model_identity = verify_model_files(config)
    runtime = config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve(), "runtime executable drift")
    require(platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime identity drift")
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    import mlx.core as mx
    import numpy as np
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    require(isinstance(runtime.get("packages"), dict) and runtime["packages"], "runtime package contract missing")
    for package_name, expected_version in runtime["packages"].items():
        observed_version = np.__version__ if package_name == "numpy" else importlib.metadata.version(package_name)
        require(observed_version == expected_version, f"runtime package drift: {package_name}")
    mx.reset_peak_memory()
    model_load_started = time.monotonic()
    model, tokenizer = load(str(model_path), adapter_path=None, lazy=False)
    model_load_seconds = time.monotonic() - model_load_started
    sampler = make_sampler(
        temp=config["generation"]["temperature"],
        top_p=config["generation"]["top_p"],
        top_k=config["generation"]["top_k"],
    )
    ontology = {"label_order": list(LABEL_ORDER), "instruction": bundle["ontology"]["instruction"]}
    guard = ResourceGuard(config, mx, run_started)

    staging.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    staging.parent.chmod(0o700)
    staging.mkdir(mode=0o700, exist_ok=False)
    staging.chmod(0o700)
    input_seal = {
        "schema_version": "sqma-005-input-seal-v1",
        "experiment_id": "SQMA-005",
        "snapshot": {
            "bytes": input_path.stat().st_size,
            "sha256": sha256(input_path),
            "rows": EXPECTED_ROWS,
            "components": EXPECTED_COMPONENTS,
            "fold_id": 3,
        },
        "sample_order_sha256": canonical_digest([row["sample_id"] for row in rows]),
        "row_membership_sha256": canonical_digest(
            [(row["sample_id"], row["component_id"], row["source_ordinal"]) for row in rows]
        ),
        "gold_present": False,
    }
    write_json_exclusive(staging / "input-seal.json", input_seal, 0o600)
    calls_path = staging / "calls.jsonl"
    descriptor = os.open(calls_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    call_file = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")

    systems: dict[str, list[Any]] = defaultdict(list)
    aggregate_counts: Counter[str] = Counter()
    token_values: dict[str, list[float]] = defaultdict(list)
    latency_values: dict[str, list[float]] = defaultdict(list)
    call_ordinal = 0

    def one_call(
        row_ordinal: int,
        row: Mapping[str, Any],
        analysis_text: str,
        text_meta: Mapping[str, Any],
        system_id: str,
        role: str,
        call_index: int,
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        nonlocal call_ordinal
        local_context = {**context, "analysis_text": analysis_text, "ontology": ontology}
        max_new = config["generation"]["max_new_tokens"][role]
        prompt_ids, messages = render_prompt(
            tokenizer,
            bundle,
            output_contracts,
            role,
            local_context,
            config["generation"]["context_token_cap"],
            max_new,
        )
        seed = seed_for(config["generation"]["seed_namespace"], system_id, row["sample_id"], role, call_index)
        mx.random.seed(seed)
        raw_parts: list[str] = []
        final_meta: dict[str, Any] | None = None
        generated = stream_generate(model, tokenizer, prompt_ids, max_tokens=max_new, sampler=sampler)
        call_started = time.monotonic()
        try:
            for response in generated:
                raw_parts.append(response.text)
                final_meta = {
                    "finish_reason": response.finish_reason,
                    "prompt_tokens": int(response.prompt_tokens),
                    "generated_tokens": int(response.generation_tokens),
                    "prompt_tps": float(response.prompt_tps),
                    "generation_tps": float(response.generation_tps),
                }
                guard.check()
                del response
        finally:
            generated.close()
        latency = time.monotonic() - call_started
        require(final_meta is not None, "generation returned no terminal metadata")
        require(final_meta["prompt_tokens"] == len(prompt_ids), "prompt token accounting drift")
        guard.generated_tokens += final_meta["generated_tokens"]
        snapshot = guard.check()
        raw = "".join(raw_parts)
        token_cap_hit = final_meta["finish_reason"] == "length"
        parsed = None
        error_code = None
        try:
            parsed = validator.validate_output(role, raw, dict(local_context))
        except validator.AgentOutputError as exc:
            error_code = exc.code
        if token_cap_hit:
            parsed = None
            error_code = "token_cap_hit"
        is_valid = parsed is not None
        is_abstained = abstained(role, parsed)
        labels = (
            validator.final_labels_from_validated(role, parsed)
            if is_valid and role in {"judge", "single_agent"}
            else []
        )
        record = {
            "schema_version": "sqma-005-call-v1",
            "call_ordinal": call_ordinal,
            "row_ordinal": row_ordinal,
            "sample_id": row["sample_id"],
            "component_id": row["component_id"],
            "source_ordinal": row["source_ordinal"],
            "system_id": system_id,
            "role": role,
            "call_index": call_index,
            "seed": seed,
            "analysis_text": analysis_text,
            "analysis_text_sha256": hashlib.sha256(analysis_text.encode("utf-8")).hexdigest(),
            "text_meta": call_text_metadata(row["text"], analysis_text, text_meta),
            "context_sha256": canonical_digest(local_context),
            "messages_sha256": canonical_digest(messages),
            "prompt_ids_sha256": canonical_digest(prompt_ids),
            "prefill_tokens": len(prompt_ids),
            "max_new_tokens": max_new,
            "finish_reason": final_meta["finish_reason"],
            "generated_tokens": final_meta["generated_tokens"],
            "latency_seconds": latency,
            "prompt_tps": final_meta["prompt_tps"],
            "generation_tps": final_meta["generation_tps"],
            "mlx_peak_bytes": snapshot["mlx_peak_bytes"],
            "raw_output_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "raw_output": raw,
            "valid": is_valid,
            "error_code": error_code,
            "parsed_output": parsed,
            "final_labels": labels,
            "abstained": is_abstained,
            "token_cap_hit": token_cap_hit,
        }
        write_call(call_file, record)
        call_ordinal += 1
        aggregate_counts[f"role:{role}"] += 1
        aggregate_counts[f"valid:{role}:{is_valid}"] += 1
        aggregate_counts[f"abstained:{role}:{is_abstained}"] += 1
        aggregate_counts[f"token_cap:{token_cap_hit}"] += 1
        token_values[f"prefill:{role}"].append(float(len(prompt_ids)))
        token_values[f"generated:{role}"].append(float(final_meta["generated_tokens"]))
        latency_values[role].append(latency)
        return record

    try:
        for row_ordinal, row in enumerate(rows):
            analysis_text, text_meta = truncate_analysis_text(
                tokenizer, row["text"], config["generation"]["analysis_text_token_cap"]
            )
            systems["original_tokens"].append(text_meta["original_tokens"])
            systems["analysis_tokens"].append(text_meta["analysis_tokens"])
            systems["was_truncated"].append(int(text_meta["was_truncated"]))

            evidence_call = one_call(
                row_ordinal, row, analysis_text, text_meta, "S3", "evidence_appraisal", 0, {}
            )
            evidence_value = evidence_call["parsed_output"] or EMPTY_EVIDENCE
            critic_call = one_call(
                row_ordinal,
                row,
                analysis_text,
                text_meta,
                "S3",
                "pragmatics_critic",
                1,
                {"evidence_appraisal": evidence_value},
            )
            critic_value = critic_call["parsed_output"] or EMPTY_CRITIC
            judge_call = one_call(
                row_ordinal,
                row,
                analysis_text,
                text_meta,
                "S3",
                "judge",
                2,
                {"evidence_appraisal": evidence_value, "pragmatics_critic": critic_value},
            )
            role_calls = [evidence_call, critic_call, judge_call]

            single_calls = [
                one_call(
                    row_ordinal,
                    row,
                    analysis_text,
                    text_meta,
                    "single_pool",
                    "single_agent",
                    index,
                    {},
                )
                for index in range(3)
            ]
            single_votes = [call["final_labels"] if call["valid"] and not call["abstained"] else [] for call in single_calls]
            s1 = list(single_votes[0])
            s2a = strict_majority(single_votes)
            judge_labels = judge_call["final_labels"] if judge_call["valid"] else []
            s3 = effective_s3_labels(
                [call["valid"] for call in role_calls], judge_labels, judge_call["abstained"]
            )
            s3_ceiling = sum(call["prefill_tokens"] + call["max_new_tokens"] for call in role_calls)
            single_prefills = {call["prefill_tokens"] for call in single_calls}
            require(len(single_prefills) == 1, "single-pool prompt length drift")
            single_ceiling = next(iter(single_prefills)) + config["generation"]["max_new_tokens"]["single_agent"]
            k, s2b_ceiling, utilization = choose_s2b_k(
                s3_ceiling,
                single_ceiling,
                config["budget"]["S2b_ceiling_tolerance_fraction"],
            )
            s2b = strict_majority(single_votes[:k])
            s3_actual = sum(call["prefill_tokens"] + call["generated_tokens"] for call in role_calls)
            s2b_actual = sum(
                call["prefill_tokens"] + call["generated_tokens"] for call in single_calls[:k]
            )

            for key, value in {
                "sample_ids": row["sample_id"],
                "component_ids": row["component_id"],
                "fold_ids": 3,
                "source_ordinals": row["source_ordinal"],
                "s1": s1,
                "s2a": s2a,
                "s2b": s2b,
                "s3": s3,
                "single_valid": [int(call["valid"]) for call in single_calls],
                "role_valid": [int(call["valid"]) for call in role_calls],
                "single_abstained": [int(call["abstained"]) for call in single_calls],
                "judge_abstained": int(judge_call["abstained"]),
                "s2b_k": k,
                "s3_ceiling_tokens": s3_ceiling,
                "s2b_ceiling_tokens": s2b_ceiling,
                "s2b_ceiling_utilization": utilization,
                "s3_actual_tokens": s3_actual,
                "s2b_actual_tokens": s2b_actual,
            }.items():
                systems[key].append(value)
            gc.collect()
            mx.clear_cache()
            guard.check()
    finally:
        call_file.flush()
        os.fsync(call_file.fileno())
        call_file.close()
        calls_path.chmod(0o600)

    require(call_ordinal == EXPECTED_PHYSICAL_CALLS, "physical call count drift")
    vector = lambda labels: [int(label in labels) for label in LABEL_ORDER]
    arrays = {
        "sample_ids": np.asarray(systems["sample_ids"], dtype=f"<U{max(map(len, systems['sample_ids']))}"),
        "component_ids": np.asarray(systems["component_ids"], dtype=f"<U{max(map(len, systems['component_ids']))}"),
        "fold_ids": np.asarray(systems["fold_ids"], dtype=np.int8),
        "source_ordinals": np.asarray(systems["source_ordinals"], dtype=np.int32),
        "s1": np.asarray([vector(value) for value in systems["s1"]], dtype=np.uint8),
        "s2a": np.asarray([vector(value) for value in systems["s2a"]], dtype=np.uint8),
        "s2b": np.asarray([vector(value) for value in systems["s2b"]], dtype=np.uint8),
        "s3": np.asarray([vector(value) for value in systems["s3"]], dtype=np.uint8),
        "single_valid": np.asarray(systems["single_valid"], dtype=np.uint8),
        "role_valid": np.asarray(systems["role_valid"], dtype=np.uint8),
        "single_abstained": np.asarray(systems["single_abstained"], dtype=np.uint8),
        "judge_abstained": np.asarray(systems["judge_abstained"], dtype=np.uint8),
        "s2b_k": np.asarray(systems["s2b_k"], dtype=np.uint8),
        "s3_ceiling_tokens": np.asarray(systems["s3_ceiling_tokens"], dtype=np.int32),
        "s2b_ceiling_tokens": np.asarray(systems["s2b_ceiling_tokens"], dtype=np.int32),
        "s2b_ceiling_utilization": np.asarray(systems["s2b_ceiling_utilization"], dtype=np.float64),
        "s3_actual_tokens": np.asarray(systems["s3_actual_tokens"], dtype=np.int32),
        "s2b_actual_tokens": np.asarray(systems["s2b_actual_tokens"], dtype=np.int32),
    }
    systems_path = staging / "systems.npz"
    descriptor = os.open(systems_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        np.savez(target, **arrays)
        target.flush()
        os.fsync(target.fileno())
    systems_path.chmod(0o600)
    with zipfile.ZipFile(systems_path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "systems NPZ duplicate member")
        require(set(names) == {f"{name}.npy" for name in arrays}, "systems NPZ inventory drift")

    calls_record = artifact_record(calls_path, root=staging)
    systems_record = artifact_record(systems_path, root=staging)
    input_record = artifact_record(staging / "input-seal.json", root=staging)
    final_resources = guard.check()
    private_manifest = {
        "schema_version": "sqma-005-private-manifest-v1",
        "experiment_id": "SQMA-005",
        "status": "SealedAwaitingScore",
        "input_seal": input_record,
        "model_identity": model_identity,
        "prompt_identities": {
            "bundle_sha256": config["implementation"]["prompt_bundle"]["sha256"],
            "schema_sha256": config["implementation"]["output_schema"]["sha256"],
            "validator_sha256": config["implementation"]["validator"]["sha256"],
        },
        "calls_artifact": calls_record,
        "systems_artifact": systems_record,
        "call_plan": {
            "rows": EXPECTED_ROWS,
            "calls_per_row": 6,
            "physical_calls": call_ordinal,
            "order": [list(value) for value in CALL_ORDER],
            "single_pool_shared": True,
        },
        "aggregate_cost": {
            "generated_tokens": guard.generated_tokens,
            "s2b_k_counts": dict(sorted(Counter(systems["s2b_k"]).items())),
        },
        "access": {
            "gold_accessed": False,
            "classifier_accessed": False,
            "adapter_loaded": False,
            "model_loaded": True,
            "training_executed": False,
            "optimizer_executed": False,
            "network_accessed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "fold4_accessed": False,
        },
        "score_authorized": False,
        "next_gate": "independent_gold_consumer_scoring",
    }
    write_json_exclusive(staging / "private-manifest.json", private_manifest, 0o600)
    private_bytes = sum(path.stat().st_size for path in staging.iterdir() if path.is_file())
    require(private_bytes <= config["budget"]["maximum_private_output_bytes"], "private output budget exceeded")
    require(sorted(path.name for path in staging.iterdir()) == sorted(outputs["private_allowed_files"]), "private inventory drift")
    os.replace(staging, private_dir)
    private_dir.chmod(0o700)

    per_role = {
        role: {
            "calls": aggregate_counts[f"role:{role}"],
            "valid": aggregate_counts[f"valid:{role}:True"],
            "invalid": aggregate_counts[f"valid:{role}:False"],
            "abstained": aggregate_counts[f"abstained:{role}:True"],
            "prefill_tokens": numeric_summary(token_values[f"prefill:{role}"]),
            "generated_tokens": numeric_summary(token_values[f"generated:{role}"]),
            "latency_seconds": numeric_summary(latency_values[role]),
        }
        for role in (*ROLE_ORDER, "single_agent")
    }
    run_payload = {
        "schema_version": "sqma-005-producer-run-v1",
        "experiment_id": "SQMA-005",
        "tier": config["tier"],
        "stage": config["stage"],
        "status": "CompletedAwaitingScore",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "config": artifact_record(supplied),
        "run_claim": artifact_record(public_dir / "run-claim.json"),
        "claim_boundary": "A classifier-free Qwen producer generated sealed S1/S2a/S2b/S3 outputs for all 672 gold-free fold-3 rows. No gold, classifier output, adapter, training, validation, test, fold 4, network, or external tool was accessed.",
        "model": model_identity,
        "inputs": {
            "rows": EXPECTED_ROWS,
            "components": EXPECTED_COMPONENTS,
            "fold_id": 3,
            "snapshot_sha256": sha256(input_path),
            "gold_present": False,
        },
        "calls": {
            "physical": call_ordinal,
            "per_row": 6,
            "single_pool_shared": True,
            "system_accounted": {
                "S1": EXPECTED_ROWS,
                "S2a": EXPECTED_ROWS * 3,
                "S2b": int(sum(systems["s2b_k"])),
                "S3": EXPECTED_ROWS * 3,
            },
        },
        "aggregates": {
            "per_role": per_role,
            "token_cap_hits": aggregate_counts["token_cap:True"],
            "s2b_k_counts": {str(key): value for key, value in sorted(Counter(systems["s2b_k"]).items())},
            "s2b_ceiling_utilization": numeric_summary(systems["s2b_ceiling_utilization"]),
        },
        "resources": {
            **final_resources,
            "model_load_seconds": model_load_seconds,
            "private_output_bytes": private_bytes,
            "free_disk_bytes_before": free_bytes,
            "critical_memory_events": 0,
            "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "access": private_manifest["access"],
        "outputs": {
            "private_manifest": {
                "logical_name": "private-manifest.json",
                "bytes": (private_dir / "private-manifest.json").stat().st_size,
                "sha256": sha256(private_dir / "private-manifest.json"),
                "mode": "0600",
            },
            "calls": {**calls_record, "mode": "0600"},
            "systems": {**systems_record, "mode": "0600", "gold_present": False},
        },
        "score_authorized": False,
        "next_gate": "independent_gold_consumer_scoring",
    }
    public_safe(run_payload)
    encoded_size = len((json.dumps(run_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    existing_public = (public_dir / "run-claim.json").stat().st_size
    require(existing_public + encoded_size <= config["budget"]["maximum_public_output_bytes"], "public output budget exceeded")
    write_json_exclusive(public_dir / "run.json", run_payload, 0o644)
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    arguments = parser.parse_args()
    result = run(arguments.config)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "status": result["status"],
                "physical_calls": result["calls"]["physical"],
                "next_gate": result["next_gate"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, zipfile.BadZipFile, ProducerError) as exc:
        print(f"SQMA-005 producer Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

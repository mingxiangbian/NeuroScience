#!/usr/bin/env python3
"""Contracts for Judge V3 restricted single-token evidence selection."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
V3_VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v3.py"
V3_VALIDATOR_SHA256 = "0901c046936ca217cb210aec1f48d815d1e64b9f4db88f52c0f93ae8dc1ad07d"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
OPTION_SYMBOLS = ("A", "B", "C", "D")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_pinned_v3() -> Any:
    if not V3_VALIDATOR_PATH.is_file() or _sha256(V3_VALIDATOR_PATH) != V3_VALIDATOR_SHA256:
        raise RuntimeError("frozen v3 validator identity drift")
    module_name = "sqma_v5_pinned_validator_v3"
    spec = importlib.util.spec_from_file_location(module_name, V3_VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("frozen v3 validator import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


V3 = _load_pinned_v3()
AgentOutputError = V3.AgentOutputError
ONTOLOGY = V3.ONTOLOGY
ONTOLOGY_INSTRUCTION = V3.ONTOLOGY_INSTRUCTION


def fail(code: str, path: str) -> None:
    raise AgentOutputError(code, path)


def validate_evidence(raw: str, context: dict[str, Any]) -> dict[str, Any]:
    return V3.validate_output("evidence", raw, context)


def validate_critic(raw: str, context: dict[str, Any]) -> dict[str, Any]:
    return V3.validate_output("critic", raw, context)


def validate_token_seal(seal: Any) -> dict[str, Any]:
    value = V3.exact_object(
        seal,
        {
            "schema_version",
            "tokenizer_sha256",
            "chat_template_sha256",
            "encode_add_special_tokens",
            "symbols",
        },
        "token_seal",
    )
    if value["schema_version"] != "sqma-judge-v3-option-token-seal-v1":
        fail("token_seal_version", "token_seal.schema_version")
    for field in ("tokenizer_sha256", "chat_template_sha256"):
        if not isinstance(value[field], str) or SHA256_RE.fullmatch(value[field]) is None:
            fail("token_seal_hash", f"token_seal.{field}")
    if value["encode_add_special_tokens"] is not False:
        fail("token_seal_encoding", "token_seal.encode_add_special_tokens")
    symbols = value["symbols"]
    if not isinstance(symbols, list) or len(symbols) != 4:
        fail("token_seal_symbols", "token_seal.symbols")
    observed_symbols: list[str] = []
    token_ids: list[int] = []
    for index, item in enumerate(symbols):
        entry = V3.exact_object(item, {"symbol", "token_id"}, f"token_seal.symbols[{index}]")
        if entry["symbol"] != OPTION_SYMBOLS[index]:
            fail("token_symbol_order", f"token_seal.symbols[{index}].symbol")
        if type(entry["token_id"]) is not int or entry["token_id"] < 0:
            fail("option_token_id", f"token_seal.symbols[{index}].token_id")
        observed_symbols.append(entry["symbol"])
        token_ids.append(entry["token_id"])
    if tuple(observed_symbols) != OPTION_SYMBOLS or len(set(token_ids)) != 4:
        fail("option_token_identity", "token_seal.symbols")
    return value


def build_token_seal(
    tokenizer: Any,
    *,
    tokenizer_sha256: str,
    chat_template_sha256: str,
    eos_token_ids: Sequence[int],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    eos = set(eos_token_ids)
    for symbol in OPTION_SYMBOLS:
        encoded = list(tokenizer.encode(symbol, add_special_tokens=False))
        if len(encoded) != 1 or type(encoded[0]) is not int:
            fail("option_not_single_token", f"symbol.{symbol}")
        token_id = encoded[0]
        if token_id in eos:
            fail("option_is_eos", f"symbol.{symbol}")
        decoded = tokenizer.decode([token_id], skip_special_tokens=False)
        if decoded != symbol:
            fail("option_decode_drift", f"symbol.{symbol}")
        entries.append({"symbol": symbol, "token_id": token_id})
    seal = {
        "schema_version": "sqma-judge-v3-option-token-seal-v1",
        "tokenizer_sha256": tokenizer_sha256,
        "chat_template_sha256": chat_template_sha256,
        "encode_add_special_tokens": False,
        "symbols": entries,
    }
    return validate_token_seal(seal)


def symbol_token_ids(seal: Mapping[str, Any]) -> dict[str, int]:
    checked = validate_token_seal(seal)
    return {item["symbol"]: item["token_id"] for item in checked["symbols"]}


def validate_allowed_evidence_ids(value: Any) -> list[int]:
    if not isinstance(value, list) or len(value) > 3:
        fail("allowed_evidence_ids", "allowed_evidence_ids")
    if any(type(item) is not int for item in value):
        fail("allowed_evidence_id_type", "allowed_evidence_ids")
    if value != list(range(len(value))):
        fail("allowed_evidence_id_range", "allowed_evidence_ids")
    return value


def build_candidate_mapping(
    allowed_evidence_ids: Any, token_seal: Mapping[str, Any]
) -> list[dict[str, Any]]:
    allowed = validate_allowed_evidence_ids(allowed_evidence_ids)
    token_ids = symbol_token_ids(token_seal)
    mapping = [{"symbol": "A", "token_id": token_ids["A"], "evidence_id": None}]
    for index, evidence_id in enumerate(allowed, start=1):
        symbol = OPTION_SYMBOLS[index]
        mapping.append(
            {"symbol": symbol, "token_id": token_ids[symbol], "evidence_id": evidence_id}
        )
    return mapping


def validate_candidate_mapping(
    mapping: Any, allowed_evidence_ids: Any, token_seal: Mapping[str, Any]
) -> list[dict[str, Any]]:
    expected = build_candidate_mapping(allowed_evidence_ids, token_seal)
    if mapping != expected:
        fail("candidate_mapping", "option_mapping")
    return expected


def validate_judge_context(
    context: Any, token_seal: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    value = V3.exact_object(
        context,
        {
            "analysis_text",
            "ontology",
            "evidence",
            "critic",
            "target_label",
            "allowed_evidence_ids",
            "option_mapping",
        },
        "context",
    )
    _, analysis_text = V3.validate_context(
        {"analysis_text": value["analysis_text"], "ontology": value["ontology"]},
        {"analysis_text", "ontology"},
    )
    evidence = V3.validate_evidence(value["evidence"], analysis_text, "context.evidence")
    V3.validate_critic(value["critic"], "context.critic")
    if value["target_label"] not in LABEL_ORDER:
        fail("target_label", "context.target_label")
    allowed = validate_allowed_evidence_ids(value["allowed_evidence_ids"])
    if allowed != list(range(len(evidence["evidence_spans"]))):
        fail("allowed_evidence_context_drift", "context.allowed_evidence_ids")
    mapping = validate_candidate_mapping(value["option_mapping"], allowed, token_seal)
    return value, mapping


def validate_generation_terminal(
    terminal: Any, candidate_mapping: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    value = V3.exact_object(
        terminal,
        {"response_count", "token", "generation_tokens", "finish_reason"},
        "terminal",
    )
    if value["response_count"] != 1:
        fail("response_count", "terminal.response_count")
    if type(value["token"]) is not int:
        fail("response_token_type", "terminal.token")
    if value["generation_tokens"] != 1:
        fail("generation_token_count", "terminal.generation_tokens")
    if value["finish_reason"] != "length":
        fail("finish_reason", "terminal.finish_reason")
    allowed = {item["token_id"] for item in candidate_mapping}
    if value["token"] not in allowed:
        fail("masked_token_escape", "terminal.token")
    return value


def choice_from_terminal(
    terminal: Any, candidate_mapping: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    checked = validate_generation_terminal(terminal, candidate_mapping)
    matches = [item for item in candidate_mapping if item["token_id"] == checked["token"]]
    if len(matches) != 1:
        fail("candidate_token_identity", "terminal.token")
    return dict(matches[0])


def assemble_judge_slots(
    terminals_by_label: Any,
    *,
    allowed_evidence_ids: Any,
    token_seal: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(terminals_by_label, Mapping) or set(terminals_by_label) != set(LABEL_ORDER):
        fail("label_call_inventory", "terminals_by_label")
    mapping = build_candidate_mapping(allowed_evidence_ids, token_seal)
    slots: dict[str, list[int]] = {}
    choices: dict[str, dict[str, Any]] = {}
    for label in LABEL_ORDER:
        choice = choice_from_terminal(terminals_by_label[label], mapping)
        evidence_id = choice["evidence_id"]
        slots[label] = [] if evidence_id is None else [evidence_id]
        choices[label] = choice
    derived = [label for label in LABEL_ORDER if slots[label]]
    return {
        "raw_contract_valid": True,
        "rendered_contract_valid": True,
        "derived_labels": derived,
        "per_label_refs": slots,
        "per_label_choices": choices,
        "diagnostics": {
            "selection_calls": 6,
            "generated_tokens": 6,
            "illegal_reference_ids_constructed": 0,
            "semantic_repair_events": 0,
        },
    }


def python_mask_logits(
    logits: Sequence[float], allowed_token_ids: Sequence[int]
) -> list[float]:
    """Pure reference implementation for the stateless logits mask."""

    allowed = tuple(allowed_token_ids)
    if not allowed or len(set(allowed)) != len(allowed):
        fail("mask_token_ids", "allowed_token_ids")
    if any(type(item) is not int or item < 0 or item >= len(logits) for item in allowed):
        fail("mask_token_range", "allowed_token_ids")
    allowed_set = set(allowed)
    return [float(value) if index in allowed_set else -float("inf") for index, value in enumerate(logits)]


def make_stateless_mlx_logits_processor(mx: Any, allowed_token_ids: Sequence[int]):
    """Return a fresh processor compatible with mlx-lm 0.31.3 generate_step."""

    allowed = tuple(allowed_token_ids)
    if not allowed or len(set(allowed)) != len(allowed) or any(type(item) is not int or item < 0 for item in allowed):
        fail("mask_token_ids", "allowed_token_ids")

    def processor(_tokens: Any, logits: Any):
        vocabulary_size = logits.shape[-1]
        if any(token_id >= vocabulary_size for token_id in allowed):
            raise ValueError("allowed option token exceeds vocabulary")
        indices = mx.arange(vocabulary_size)
        mask = indices == allowed[0]
        for token_id in allowed[1:]:
            mask = mx.logical_or(mask, indices == token_id)
        negative = mx.full(logits.shape, -float("inf"), dtype=logits.dtype)
        return mx.where(mask, logits, negative)

    return processor

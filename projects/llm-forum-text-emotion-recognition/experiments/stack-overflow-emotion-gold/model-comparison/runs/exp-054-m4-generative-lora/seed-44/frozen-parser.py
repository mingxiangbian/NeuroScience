#!/usr/bin/env python3
"""Strict parser for the frozen Stack Overflow generative label schema."""

from __future__ import annotations

import json
from typing import Any


DEFAULT_LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")


def canonical_target(label_vector: list[int], labels: tuple[str, ...] = DEFAULT_LABELS) -> str:
    if len(label_vector) != len(labels) or any(value not in (0, 1) for value in label_vector):
        raise ValueError("label_vector must be a binary vector aligned with labels")
    selected = [label for label, value in zip(labels, label_vector) if value]
    return json.dumps({"emotions": selected}, ensure_ascii=True, separators=(",", ":"))


def parse_output(raw: str, labels: tuple[str, ...] = DEFAULT_LABELS) -> dict[str, Any]:
    result = {"valid": False, "labels": [], "vector": [0] * len(labels), "error": None}
    if not isinstance(raw, str):
        result["error"] = "not_string"
        return result
    if raw != raw.strip() or not raw:
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
    if any(label not in labels for label in selected):
        result["error"] = "unknown_label"
        return result
    canonical = [label for label in labels if label in selected]
    if selected != canonical:
        result["error"] = "noncanonical_order"
        return result
    if raw != json.dumps({"emotions": selected}, ensure_ascii=True, separators=(",", ":")):
        result["error"] = "noncanonical_json"
        return result
    result.update(
        valid=True,
        labels=selected,
        vector=[int(label in selected) for label in labels],
        error=None,
    )
    return result

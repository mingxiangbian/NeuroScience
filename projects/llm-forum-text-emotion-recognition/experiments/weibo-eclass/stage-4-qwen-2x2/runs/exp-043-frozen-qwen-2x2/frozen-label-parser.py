#!/usr/bin/env python3
"""Strict final-label parser for EXP-043."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Iterable


DEFAULT_LABELS = (
    "anger",
    "joy",
    "negative",
    "neutral",
    "no_emotion",
    "positive",
    "sadness",
)


@dataclass(frozen=True)
class ParseResult:
    valid: bool
    label: str | None
    canonical_output: str | None
    error: str | None
    thinking_boundary_found: bool
    opening_marker_found: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _invalid(
    error: str,
    *,
    thinking_boundary_found: bool = False,
    opening_marker_found: bool = False,
) -> ParseResult:
    return ParseResult(
        valid=False,
        label=None,
        canonical_output=None,
        error=error,
        thinking_boundary_found=thinking_boundary_found,
        opening_marker_found=opening_marker_found,
    )


def parse_final_label(
    output: str,
    *,
    thinking: bool,
    labels: Iterable[str] = DEFAULT_LABELS,
) -> ParseResult:
    """Parse one response without repairing, retrying or guessing its label."""

    allowed = tuple(labels)
    if not allowed or len(allowed) != len(set(allowed)):
        raise ValueError("labels must be a non-empty unique iterable")
    if not isinstance(output, str) or not output.strip():
        return _invalid("empty_output")

    opening_found = "<think>" in output
    close_count = output.count("</think>")
    if thinking:
        if close_count != 1:
            return _invalid(
                "missing_thinking_boundary" if close_count == 0 else "multiple_thinking_boundaries",
                opening_marker_found=opening_found,
            )
        prefix, candidate = output.split("</think>", maxsplit=1)
        if prefix.count("<think>") > 1:
            return _invalid(
                "multiple_opening_markers",
                thinking_boundary_found=True,
                opening_marker_found=True,
            )
        if opening_found and not prefix.lstrip().startswith("<think>"):
            return _invalid(
                "misplaced_opening_marker",
                thinking_boundary_found=True,
                opening_marker_found=True,
            )
    else:
        if opening_found or close_count:
            return _invalid(
                "thinking_marker_in_nonthinking_output",
                thinking_boundary_found=bool(close_count),
                opening_marker_found=opening_found,
            )
        candidate = output

    candidate = candidate.strip()
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        return _invalid(
            "invalid_json",
            thinking_boundary_found=thinking,
            opening_marker_found=opening_found,
        )
    if not isinstance(decoded, dict):
        return _invalid(
            "json_not_object",
            thinking_boundary_found=thinking,
            opening_marker_found=opening_found,
        )
    if set(decoded) != {"label"}:
        return _invalid(
            "schema_keys_mismatch",
            thinking_boundary_found=thinking,
            opening_marker_found=opening_found,
        )
    label = decoded["label"]
    if not isinstance(label, str):
        return _invalid(
            "label_not_string",
            thinking_boundary_found=thinking,
            opening_marker_found=opening_found,
        )
    if label not in allowed:
        return _invalid(
            "unknown_label",
            thinking_boundary_found=thinking,
            opening_marker_found=opening_found,
        )
    canonical = json.dumps({"label": label}, ensure_ascii=True, separators=(",", ":"))
    return ParseResult(
        valid=True,
        label=label,
        canonical_output=canonical,
        error=None,
        thinking_boundary_found=thinking,
        opening_marker_found=opening_found,
    )

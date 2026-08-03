#!/usr/bin/env python3
"""Finite-state label JSON constraint that permits neutral co-occurrence."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from label_json_constraint import LabelJsonGrammar, LabelJsonLogitsProcessor, PrefixStatus


class NeutralCooccurrenceGrammar(LabelJsonGrammar):
    """Keep canonical JSON and unique labels while treating neutral as non-exclusive."""

    @lru_cache(maxsize=None)
    def _after_label(
        self,
        remaining: str,
        selected: tuple[str, ...],
    ) -> PrefixStatus:
        if len(remaining) <= len(self.suffix) and self.suffix.startswith(remaining):
            return PrefixStatus(True, remaining == self.suffix)
        if remaining.startswith(self.suffix):
            return PrefixStatus(False, False)
        if remaining.startswith(","):
            return self._label_slot(remaining[1:], selected)
        return PrefixStatus(False, False)

    @lru_cache(maxsize=None)
    def _remaining_labels(self, selected: tuple[str, ...]) -> tuple[str, ...]:
        selected_set = set(selected)
        return tuple(label for label in self.labels if label not in selected_set)


class NeutralCooccurrenceLogitsProcessor(LabelJsonLogitsProcessor):
    """Use the frozen token-mask implementation with the open-neutral grammar."""

    def __init__(self, tokenizer: Any, labels: tuple[str, ...], mx: Any):
        self.tokenizer = tokenizer
        self.grammar = NeutralCooccurrenceGrammar(labels)
        self.mx = mx
        self.eos_token_ids = tuple(
            sorted(int(value) for value in tokenizer.eos_token_ids)
        )
        if not self.eos_token_ids:
            raise ValueError("Tokenizer has no EOS token IDs")
        self._prompt_tail_tokens: int | None = None
        self._allowed_cache: dict[str, tuple[int, ...]] = {}
        self._candidates_by_first = self._build_candidates()
        self._validate_tokenizer_coverage()
        for output in (
            '{"labels":["neutral","joy"]}',
            '{"labels":["anger","neutral","annoyance"]}',
        ):
            token_ids = tokenizer.encode(output, add_special_tokens=False)
            if self._decode(token_ids) != output or not self.grammar.status(output).complete:
                raise ValueError(f"Tokenizer cannot represent neutral co-occurrence: {output}")

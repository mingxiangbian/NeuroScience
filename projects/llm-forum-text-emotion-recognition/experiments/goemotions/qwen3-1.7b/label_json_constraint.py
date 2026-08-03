#!/usr/bin/env python3
"""Finite-state JSON constraint for GoEmotions label-name generation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any


@dataclass(frozen=True)
class PrefixStatus:
    valid: bool
    complete: bool


class LabelJsonGrammar:
    """Recognize prefixes of {"labels":[...]} over a fixed label ontology."""

    prefix = '{"labels":['
    suffix = "]}"

    def __init__(self, labels: tuple[str, ...], neutral_label: str = "neutral"):
        if not labels or len(labels) != len(set(labels)):
            raise ValueError("Labels must be a non-empty unique tuple")
        if neutral_label not in labels:
            raise ValueError("Neutral label is missing from the ontology")
        if any(not label.isascii() or not label.isalpha() or not label.islower() for label in labels):
            raise ValueError("Labels must contain lowercase ASCII letters only")
        self.labels = labels
        self.neutral_label = neutral_label
        self.alphabet = tuple(
            sorted(set(self.prefix + self.suffix + ',"' + "".join(labels)))
        )

    def status(self, text: str) -> PrefixStatus:
        if len(text) < len(self.prefix):
            return PrefixStatus(self.prefix.startswith(text), False)
        if not text.startswith(self.prefix):
            return PrefixStatus(False, False)
        return self._label_slot(text[len(self.prefix) :], ())

    @lru_cache(maxsize=None)
    def _label_slot(
        self,
        remaining: str,
        selected: tuple[str, ...],
    ) -> PrefixStatus:
        candidates = self._remaining_labels(selected)
        for label in candidates:
            quoted = f'"{label}"'
            if len(remaining) < len(quoted) and quoted.startswith(remaining):
                return PrefixStatus(True, False)
            if remaining.startswith(quoted):
                status = self._after_label(
                    remaining[len(quoted) :],
                    (*selected, label),
                )
                if status.valid:
                    return status
        return PrefixStatus(False, False)

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
        if self.neutral_label in selected:
            return PrefixStatus(False, False)
        if remaining.startswith(","):
            return self._label_slot(remaining[1:], selected)
        return PrefixStatus(False, False)

    @lru_cache(maxsize=None)
    def _remaining_labels(self, selected: tuple[str, ...]) -> tuple[str, ...]:
        if self.neutral_label in selected:
            return ()
        selected_set = set(selected)
        return tuple(
            label
            for label in self.labels
            if label not in selected_set
            and (not selected or label != self.neutral_label)
        )


class LabelJsonLogitsProcessor:
    """Mask tokens that cannot extend the frozen label-name JSON grammar."""

    def __init__(self, tokenizer: Any, labels: tuple[str, ...], mx: Any):
        self.tokenizer = tokenizer
        self.grammar = LabelJsonGrammar(labels)
        self.mx = mx
        self.eos_token_ids = tuple(sorted(int(value) for value in tokenizer.eos_token_ids))
        if not self.eos_token_ids:
            raise ValueError("Tokenizer has no EOS token IDs")
        self._prompt_tail_tokens: int | None = None
        self._allowed_cache: dict[str, tuple[int, ...]] = {}
        self._candidates_by_first = self._build_candidates()
        self._validate_tokenizer_coverage()

    @property
    def candidate_token_count(self) -> int:
        return sum(len(values) for values in self._candidates_by_first.values())

    def reset(self) -> None:
        """Reset per-generation state while retaining token and prefix caches."""
        self._prompt_tail_tokens = None

    def _decode(self, token_ids: list[int]) -> str:
        return self.tokenizer.decode(
            token_ids,
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )

    def _build_candidates(self) -> dict[str, tuple[tuple[int, str], ...]]:
        by_first: dict[str, list[tuple[int, str]]] = {
            character: [] for character in self.grammar.alphabet
        }
        eos = set(self.eos_token_ids)
        for token_id in sorted(set(self.tokenizer.get_vocab().values())):
            if token_id in eos:
                continue
            piece = self._decode([token_id])
            if (
                piece
                and piece[0] in by_first
                and all(character in self.grammar.alphabet for character in piece)
            ):
                by_first[piece[0]].append((token_id, piece))
        return {key: tuple(values) for key, values in by_first.items()}

    def _validate_tokenizer_coverage(self) -> None:
        examples = [
            '{"labels":["neutral"]}',
            *(
                f'{{"labels":["{label}"]}}'
                for label in self.grammar.labels
                if label != self.grammar.neutral_label
            ),
            '{"labels":["joy","excitement"]}',
            '{"labels":["anger","disgust","disapproval"]}',
        ]
        for output in examples:
            token_ids = self.tokenizer.encode(output, add_special_tokens=False)
            decoded = self._decode(token_ids)
            if decoded != output or not self.grammar.status(decoded).complete:
                raise ValueError(f"Tokenizer cannot represent canonical output: {output}")
            prefix = ""
            for token_id in token_ids:
                prefix += self._decode([int(token_id)])
                if not self.grammar.status(prefix).valid:
                    raise ValueError(
                        f"Tokenizer token boundary violates grammar for: {output}"
                    )

    def allowed_token_ids(self, current_text: str) -> tuple[int, ...]:
        cached = self._allowed_cache.get(current_text)
        if cached is not None:
            return cached
        status = self.grammar.status(current_text)
        if not status.valid:
            raise ValueError(f"Generated text left the JSON grammar: {current_text!r}")
        if status.complete:
            allowed = self.eos_token_ids
        else:
            next_characters = (
                character
                for character in self.grammar.alphabet
                if self.grammar.status(current_text + character).valid
            )
            allowed = tuple(
                token_id
                for character in next_characters
                for token_id, piece in self._candidates_by_first[character]
                if self.grammar.status(current_text + piece).valid
            )
        if not allowed:
            raise RuntimeError(f"No token can extend grammar prefix: {current_text!r}")
        self._allowed_cache[current_text] = allowed
        return allowed

    def __call__(self, tokens: Any, logits: Any) -> Any:
        token_ids = [int(value) for value in tokens.tolist()]
        if self._prompt_tail_tokens is None:
            self._prompt_tail_tokens = len(token_ids)
        generated_ids = token_ids[self._prompt_tail_tokens :]
        eos_positions = [
            index
            for index, token_id in enumerate(generated_ids)
            if token_id in self.eos_token_ids
        ]
        if eos_positions:
            if eos_positions != [len(generated_ids) - 1]:
                raise ValueError("EOS appeared before the end of generated tokens")
            terminal_text = self._decode(generated_ids[:-1])
            if not self.grammar.status(terminal_text).complete:
                raise ValueError("EOS followed an incomplete JSON output")
            # MLX-LM computes one look-ahead token before yielding the EOS token.
            return logits
        current_text = self._decode(generated_ids)
        allowed = self.allowed_token_ids(current_text)
        mask = self.mx.ones(logits.shape, dtype=self.mx.bool_)
        mask[:, list(allowed)] = False
        return self.mx.where(mask, -self.mx.inf, logits)

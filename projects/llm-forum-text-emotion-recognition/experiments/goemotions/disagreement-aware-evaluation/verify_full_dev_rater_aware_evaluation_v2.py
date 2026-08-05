#!/usr/bin/env python3
"""Run the EXP-037 verifier with normalized JSON object-key comparison."""

from __future__ import annotations

from typing import Any

import verify_full_dev_rater_aware_evaluation as verifier


ORIGINAL_COMPARE_NESTED = verifier.compare_nested


def compare_nested(observed: Any, expected: Any, path: str = "$") -> float:
    if isinstance(expected, dict):
        if not isinstance(observed, dict):
            raise RuntimeError(f"JSON object differs at {path}")
        observed_by_key = {str(key): value for key, value in observed.items()}
        expected_by_key = {str(key): value for key, value in expected.items()}
        if set(observed_by_key) != set(expected_by_key):
            raise RuntimeError(f"JSON object differs at {path}")
        return max(
            (
                compare_nested(
                    observed_by_key[key], expected_by_key[key], f"{path}.{key}"
                )
                for key in expected_by_key
            ),
            default=0.0,
        )
    return ORIGINAL_COMPARE_NESTED(observed, expected, path)


if __name__ == "__main__":
    verifier.compare_nested = compare_nested
    verifier.__file__ = __file__
    verifier.main()

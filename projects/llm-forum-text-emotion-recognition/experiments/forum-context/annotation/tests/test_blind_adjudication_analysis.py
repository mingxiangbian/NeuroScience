from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANNOTATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANNOTATION_DIR))

import finalize_blind_adjudication_v1 as finalizer  # noqa: E402


def labeled(emotion: str) -> dict:
    return {
        "status": "labeled",
        "primary_emotion": emotion,
        "other_emotion_text": None,
    }


def row(
    case_id: str,
    aliases: dict[str, str],
    assessments: dict[str, str],
    *,
    independent: str,
    final: str | None,
    stratum: str,
    reason: str,
) -> dict:
    candidates = [
        {"alias": alias, "decision": labeled(emotion)}
        for alias, emotion in zip(
            ("candidate_a", "candidate_b", "candidate_c"),
            ("anger", "frustration", "neutral"),
            strict=True,
        )
    ]
    resolution = "final_decision" if final is not None else "no_stable_gold"
    return {
        "case": {"candidates": candidates},
        "mapping": {
            "blind_case_id": case_id,
            "alias_to_source": aliases,
            "stratum": stratum,
        },
        "record": {
            "phase_1": {
                "emotion_presence": "clear_emotion",
                "stance": "oppose",
                "unit_validity": "valid_single_unit",
                "independent_decision": labeled(independent),
            },
            "phase_2": {
                "candidate_assessments": assessments,
                "resolution": resolution,
                "final_decision": labeled(final) if final is not None else None,
                "primary_reason": reason,
            },
        },
    }


class BlindAdjudicationAnalysisTests(unittest.TestCase):
    def test_source_metrics_follow_hidden_mapping_not_alias_position(self) -> None:
        rows = [
            row(
                "001",
                {
                    "candidate_a": "human",
                    "candidate_b": "model_01",
                    "candidate_c": "model_02",
                },
                {
                    "candidate_a": "supported",
                    "candidate_b": "unsupported",
                    "candidate_c": "acceptable_but_not_primary",
                },
                independent="anger",
                final="anger",
                stratum="stance_candidate",
                reason="stance_vs_emotion",
            ),
            row(
                "002",
                {
                    "candidate_a": "model_02",
                    "candidate_b": "human",
                    "candidate_c": "model_01",
                },
                {
                    "candidate_a": "unsupported",
                    "candidate_b": "supported",
                    "candidate_c": "supported",
                },
                independent="anger",
                final=None,
                stratum="all_three_different",
                reason="ontology_gap",
            ),
        ]

        result = finalizer.analyze_rows(
            rows,
            {
                "session_count": 1,
                "completed_cases": 2,
                "completed_per_session": [2],
                "maximum_completed_in_one_session": 2,
                "session_limit": 20,
                "session_limit_passed": True,
            },
        )

        human = result["candidate_assessment_by_source"]["human"]
        model_01 = result["candidate_assessment_by_source"]["model_01"]
        model_02 = result["candidate_assessment_by_source"]["model_02"]
        self.assertEqual(human["assessment_counts"], {"supported": 2})
        self.assertEqual(
            model_01["assessment_counts"],
            {"supported": 1, "unsupported": 1},
        )
        self.assertEqual(
            model_02["assessment_counts"],
            {"acceptable_but_not_primary": 1, "unsupported": 1},
        )
        self.assertEqual(result["resolution"]["counts"]["no_stable_gold"], 1)
        self.assertEqual(
            result["resolution"]["final_outcome_status_counts"],
            {"labeled": 1, "no_stable_gold": 1},
        )
        self.assertEqual(result["independent_to_final"]["unchanged"], 1)

    def test_public_privacy_gate_rejects_per_case_fields(self) -> None:
        safe = {"source": {"human": {"supported": 2}}}
        unsafe = {"analysis": {"sample_uid": "private"}}

        self.assertEqual(finalizer.public_violations(safe), [])
        self.assertTrue(finalizer.public_violations(unsafe))


if __name__ == "__main__":
    unittest.main()

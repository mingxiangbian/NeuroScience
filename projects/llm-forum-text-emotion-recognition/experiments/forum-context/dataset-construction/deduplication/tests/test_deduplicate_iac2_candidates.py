#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dedup = load_module(
    "deduplicate_iac2_candidates_v2",
    ROOT / "deduplicate_iac2_candidates_v2.py",
)


def candidate(
    index: int,
    pair_hash: str,
    parent_row: int,
    target_row: int,
    *,
    severe: int = 0,
    flags: int = 0,
    words: int = 20,
) -> object:
    return dedup.Candidate(
        index=index,
        sample_uid=f"smp_{index:064x}",
        parent_row=parent_row,
        target_row=target_row,
        pair_sha256=pair_hash,
        severe_flag_count=severe,
        total_flag_count=flags,
        combined_word_count_capped=words,
    )


class TextMetricTests(unittest.TestCase):
    def test_punctuation_only_difference_can_be_format_only(self) -> None:
        edge = dedup.classify_edge(
            0,
            1,
            "This is the same longer parent statement, and every lexical token remains unchanged.",
            "I completely agree with this longer conclusion because every lexical token is identical!",
            "This is the same longer parent statement; and every lexical token remains unchanged.",
            "I completely agree with this longer conclusion because every lexical token is identical.",
            0.99,
            0.99,
            False,
            False,
        )
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertTrue(edge.format_auto)
        self.assertEqual(edge.edge_type, "format_only")

    def test_negation_change_is_not_lexical_duplicate(self) -> None:
        edge = dedup.classify_edge(
            0,
            1,
            "This is the same parent statement.",
            "I am pleased with the result.",
            "This is the same parent statement.",
            "I am not pleased with the result.",
            0.99,
            0.97,
            False,
            False,
        )
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertFalse(edge.format_auto)
        self.assertFalse(edge.lexical_review)
        self.assertTrue(edge.semantic_review)
        self.assertIn("target_negation_mismatch", edge.guard_flags)

    def test_semantic_similarity_never_becomes_auto_drop(self) -> None:
        edge = dedup.classify_edge(
            2,
            3,
            "The release was discussed by the community.",
            "I am disappointed by this update.",
            "Community members discussed the new release.",
            "This update leaves me frustrated.",
            0.96,
            0.95,
            False,
            False,
        )
        self.assertIsNotNone(edge)
        assert edge is not None
        self.assertTrue(edge.semantic_review)
        self.assertFalse(edge.format_auto)


class RepresentativeTests(unittest.TestCase):
    def test_exact_representative_uses_frozen_quality_rank(self) -> None:
        candidates = [
            candidate(0, "same", 0, 1, severe=1, words=100),
            candidate(1, "same", 2, 3, severe=0, flags=2, words=50),
            candidate(2, "other", 4, 5),
        ]
        representatives, groups = dedup.choose_exact_representatives(candidates)
        self.assertEqual(groups["same"], [0, 1])
        self.assertEqual(representatives[0], 1)
        self.assertEqual(representatives[1], 1)

    def test_format_chain_does_not_collapse_without_direct_edge(self) -> None:
        candidates = [
            candidate(0, "a", 0, 1, words=100),
            candidate(1, "b", 2, 3, words=90),
            candidate(2, "c", 4, 5, words=80),
        ]
        exact_representative, exact_groups = dedup.choose_exact_representatives(
            candidates
        )
        final, decisions = dedup.assign_direct_representatives(
            candidates,
            exact_representative,
            exact_groups,
            {(0, 1), (1, 2)},
        )
        self.assertEqual(final, {0: 0, 1: 0, 2: 2})
        self.assertEqual(decisions[1], "drop_format_only")
        self.assertEqual(decisions[2], "keep")

    def test_every_auto_drop_gets_a_direct_evidence_edge(self) -> None:
        candidates = [
            candidate(0, "same", 0, 1),
            candidate(1, "same", 2, 3),
            candidate(2, "format", 4, 5),
        ]
        texts = [
            "The parent statement is unchanged.",
            "I agree with this conclusion!",
            "The parent statement is unchanged.",
            "I agree with this conclusion!",
            "The parent statement is unchanged",
            "I agree with this conclusion.",
        ]
        embeddings = np.zeros((6, dedup.EMBEDDING_DIM), dtype=np.float32)
        embeddings[:, 0] = 1.0
        rows = dedup.direct_decision_edges(
            candidates,
            {0: 0, 1: 0, 2: 0},
            {0: "keep", 1: "drop_exact", 2: "drop_format_only"},
            embeddings,
            texts,
            np.full(6, 20, dtype=np.uint16),
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual({row[2] for row in rows}, {"exact", "format_only"})
        self.assertEqual({(row[0], row[1]) for row in rows}, {(0, 1), (0, 2)})

    def test_exact_group_uses_final_format_representative(self) -> None:
        candidates = [
            candidate(0, "same", 0, 1, words=100),
            candidate(1, "same", 2, 3, words=90),
            candidate(2, "format", 4, 5, words=120),
        ]
        exact_representative, exact_groups = dedup.choose_exact_representatives(
            candidates
        )
        final, decisions = dedup.assign_direct_representatives(
            candidates,
            exact_representative,
            exact_groups,
            {(0, 2)},
        )
        self.assertEqual(final, {0: 2, 1: 2, 2: 2})
        self.assertEqual(decisions[0], "drop_format_only")
        self.assertEqual(decisions[1], "drop_format_only")
        self.assertEqual(decisions[2], "keep")


class VectorTests(unittest.TestCase):
    def test_pair_vector_inner_product_is_average_role_cosine(self) -> None:
        candidates = [candidate(0, "a", 0, 1), candidate(1, "b", 2, 3)]
        embeddings = np.zeros((4, dedup.EMBEDDING_DIM), dtype=np.float32)
        embeddings[0, 0] = 1.0
        embeddings[1, 1] = 1.0
        embeddings[2, 0] = 0.8
        embeddings[2, 2] = 0.6
        embeddings[3, 1] = 0.6
        embeddings[3, 3] = 0.8
        vectors = dedup.pair_vectors(candidates, embeddings, [0, 1])
        self.assertAlmostEqual(float(vectors[0] @ vectors[1]), 0.7, places=6)

    def test_hnsw_retrieval_matches_flat_on_synthetic_vectors(self) -> None:
        faiss = dedup.load_faiss()
        random = np.random.default_rng(7)
        vectors = random.standard_normal((256, dedup.PAIR_DIM)).astype(np.float32)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        exact = faiss.IndexFlatIP(dedup.PAIR_DIM)
        exact.add(vectors)
        approximate = faiss.IndexHNSWFlat(
            dedup.PAIR_DIM,
            dedup.HNSW_M,
            faiss.METRIC_INNER_PRODUCT,
        )
        approximate.hnsw.efConstruction = dedup.HNSW_EF_CONSTRUCTION
        approximate.hnsw.efSearch = dedup.HNSW_EF_SEARCH
        approximate.add(vectors)
        _, exact_neighbors = exact.search(vectors[:32], 10)
        _, approximate_neighbors = approximate.search(vectors[:32], 10)
        recalls = [
            len(set(left) & set(right)) / 10
            for left, right in zip(exact_neighbors, approximate_neighbors)
        ]
        self.assertGreaterEqual(float(np.mean(recalls)), 0.99)


class ProtocolTests(unittest.TestCase):
    def test_v2_retrieval_effort_is_frozen(self) -> None:
        self.assertEqual(dedup.PIPELINE_ID, "DATA-FCTX-DEDUP-V2")
        self.assertEqual(dedup.HNSW_EF_SEARCH, 768)
        self.assertEqual(dedup.INITIAL_K, 64)
        self.assertEqual(dedup.MAX_K, 512)

    def test_token_counts_exclude_batch_padding(self) -> None:
        worker = ROOT / "embed_iac2_posts_v2.py"
        code = """
import runpy
import sys

namespace = runpy.run_path(sys.argv[1])
torch = namespace["torch"]
mask = torch.tensor([[1, 1, 1, 0, 0], [1, 1, 1, 1, 1]])
lengths = namespace["capped_token_lengths"](mask).tolist()
if lengths != [3, 5]:
    raise SystemExit(f"unexpected lengths: {lengths}")
"""
        subprocess.run([sys.executable, "-c", code, str(worker)], check=True)


if __name__ == "__main__":
    unittest.main()

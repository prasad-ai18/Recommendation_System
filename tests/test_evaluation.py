"""Unit tests for offline recommendation ranking metrics."""

import pytest
import numpy as np
from src.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    hit_rate_at_k,
    ndcg_at_k,
    catalog_coverage,
)


def test_hit_rate_at_k():
    ground_truth = {101, 102, 103}
    # Hit in top 3
    assert hit_rate_at_k([105, 101, 200], ground_truth, k=2) == 1.0
    # Miss in top 2, hit in top 3
    assert hit_rate_at_k([105, 200, 101], ground_truth, k=2) == 0.0
    assert hit_rate_at_k([105, 200, 101], ground_truth, k=3) == 1.0
    # Completely disjoint
    assert hit_rate_at_k([999, 998], ground_truth, k=5) == 0.0
    # Empty ground truth
    assert hit_rate_at_k([101, 102], set(), k=5) == 0.0


def test_precision_at_k():
    ground_truth = {1, 2, 3}
    # 2 hits out of 4 recommendations -> 2/4 = 0.5
    assert precision_at_k([1, 4, 2, 5], ground_truth, k=4) == 0.5
    # 1 hit out of 2 recommendations -> 1/2 = 0.5
    assert precision_at_k([1, 4, 2, 5], ground_truth, k=2) == 0.5
    # 0 hits
    assert precision_at_k([9, 8, 7], ground_truth, k=3) == 0.0


def test_recall_at_k():
    ground_truth = {1, 2, 3, 4}  # total 4 relevant items
    # 2 hits in top 5 -> 2/4 = 0.5
    assert recall_at_k([1, 99, 2, 98, 97], ground_truth, k=5) == 0.5
    # All 4 hits -> 4/4 = 1.0
    assert recall_at_k([1, 2, 3, 4], ground_truth, k=4) == 1.0
    # 0 hits
    assert recall_at_k([10, 11], ground_truth, k=2) == 0.0


def test_ndcg_at_k():
    ground_truth = {1, 2}
    # Perfect ranking: both items at rank 1 and 2
    # DCG = 1/log2(2) + 1/log2(3) = 1 + 0.6309 = 1.6309
    # IDCG = 1.6309 -> NDCG = 1.0
    perf_ndcg = ndcg_at_k([1, 2, 99, 98], ground_truth, k=4)
    assert abs(perf_ndcg - 1.0) < 1e-4

    # Item at rank 1 only
    # DCG = 1.0, IDCG = 1.6309 -> NDCG = 1.0 / 1.6309 ~= 0.6131
    ndcg_rank1 = ndcg_at_k([1, 99, 98], ground_truth, k=3)
    assert 0.60 < ndcg_rank1 < 0.63

    # Item at rank 2 only
    # DCG = 1/log2(3) = 0.6309 -> NDCG = 0.6309 / 1.6309 ~= 0.3868
    ndcg_rank2 = ndcg_at_k([99, 1, 98], ground_truth, k=3)
    assert 0.37 < ndcg_rank2 < 0.40

    # Higher rank gives higher NDCG
    assert ndcg_rank1 > ndcg_rank2

    # Zero hits gives 0.0
    assert ndcg_at_k([99, 98, 97], ground_truth, k=3) == 0.0


def test_catalog_coverage():
    all_recs = [
        [1, 2, 3],
        [3, 4, 5],
        [1, 5, 6],
    ]
    # Unique recommended: {1, 2, 3, 4, 5, 6} = 6 items
    # Total catalog items: 10
    # Coverage: 6 / 10 = 0.6
    assert catalog_coverage(all_recs, total_catalog_items=10) == 0.6
    assert catalog_coverage([], total_catalog_items=10) == 0.0

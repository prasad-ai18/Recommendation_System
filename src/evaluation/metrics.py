"""Pure evaluation metric functions for Top-K recommendation ranking."""

from typing import List, Set, Union
import numpy as np


def hit_rate_at_k(recommended_ids: List[int], ground_truth_ids: Set[int], k: int) -> float:
    """
    Computes Hit Rate@K: 1.0 if at least one ground-truth item appears in Top-K, else 0.0.
    """
    if not ground_truth_ids or k <= 0:
        return 0.0
    top_k = recommended_ids[:k]
    return 1.0 if any(item in ground_truth_ids for item in top_k) else 0.0


def precision_at_k(recommended_ids: List[int], ground_truth_ids: Set[int], k: int) -> float:
    """
    Computes Precision@K: Fraction of top-K recommendations that are in ground truth.
    P@K = |TopK ∩ Rel| / K
    """
    if not ground_truth_ids or k <= 0:
        return 0.0
    top_k = recommended_ids[:k]
    hits = sum(1 for item in top_k if item in ground_truth_ids)
    return float(hits / k)


def recall_at_k(recommended_ids: List[int], ground_truth_ids: Set[int], k: int) -> float:
    """
    Computes Recall@K: Fraction of ground truth items that were retrieved in Top-K.
    R@K = |TopK ∩ Rel| / |Rel|
    """
    if not ground_truth_ids or k <= 0:
        return 0.0
    top_k = recommended_ids[:k]
    hits = sum(1 for item in top_k if item in ground_truth_ids)
    return float(hits / len(ground_truth_ids))


def ndcg_at_k(recommended_ids: List[int], ground_truth_ids: Set[int], k: int) -> float:
    """
    Computes Normalized Discounted Cumulative Gain (NDCG) at K.
    DCG@K = sum_{i=1}^K (rel_i / log2(i + 1))
    IDCG@K = sum_{i=1}^{min(K, |Rel|)} (1 / log2(i + 1))
    NDCG@K = DCG@K / IDCG@K
    """
    if not ground_truth_ids or k <= 0:
        return 0.0

    top_k = recommended_ids[:k]
    dcg = 0.0
    for i, item in enumerate(top_k):
        if item in ground_truth_ids:
            dcg += 1.0 / np.log2(i + 2)  # i is 0-indexed, so rank is i+1, log2(rank + 1) = log2(i + 2)

    # Ideal DCG: top min(k, |ground_truth|) are all relevant
    ideal_hits = min(k, len(ground_truth_ids))
    if ideal_hits == 0:
        return 0.0

    idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_hits))
    return float(dcg / idcg) if idcg > 0 else 0.0


def catalog_coverage(all_recommended_ids: List[List[int]], total_catalog_items: int) -> float:
    """
    Computes Catalog Coverage: Fraction of all unique catalog items recommended across users.
    Coverage = |Union of recommended items across all users| / |Total Catalog Items|
    """
    if total_catalog_items <= 0:
        return 0.0
    unique_recommended = set()
    for rec_list in all_recommended_ids:
        unique_recommended.update(rec_list)
    return float(len(unique_recommended) / total_catalog_items)

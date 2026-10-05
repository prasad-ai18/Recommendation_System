"""Evaluation package for ranking metrics and benchmark evaluation."""

from src.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    hit_rate_at_k,
    ndcg_at_k,
    catalog_coverage,
)
from src.evaluation.evaluator import OfflineEvaluator

__all__ = [
    "precision_at_k",
    "recall_at_k",
    "hit_rate_at_k",
    "ndcg_at_k",
    "catalog_coverage",
    "OfflineEvaluator",
]

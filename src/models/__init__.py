"""Recommendation models package."""

from src.models.base import BaseRecommender, RecommendationItem, RecommendationResult
from src.models.popularity import PopularityRecommender
from src.models.collaborative import ItemCollaborativeRecommender
from src.models.matrix_factorization import MatrixFactorizationRecommender
from src.models.hybrid import HybridRecommender
from src.models.representations import UserItemRepresentations
from src.models.registry import ModelRegistry

__all__ = [
    "BaseRecommender",
    "RecommendationItem",
    "RecommendationResult",
    "PopularityRecommender",
    "ItemCollaborativeRecommender",
    "MatrixFactorizationRecommender",
    "HybridRecommender",
    "UserItemRepresentations",
    "ModelRegistry",
]

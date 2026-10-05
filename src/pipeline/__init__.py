"""Pipeline package for candidate generation, ranking, and orchestration."""

from src.pipeline.candidate_gen import (
    CandidateGenerator,
    CandidatePoolItem,
    BaseCandidateChannel,
    CollaborativeNeighborhoodChannel,
    LatentFactorChannel,
    GenreAffinityChannel,
    PopularityPriorChannel,
)
from src.pipeline.ranker import CandidateRanker

__all__ = [
    "CandidateGenerator",
    "CandidatePoolItem",
    "BaseCandidateChannel",
    "CollaborativeNeighborhoodChannel",
    "LatentFactorChannel",
    "GenreAffinityChannel",
    "PopularityPriorChannel",
    "CandidateRanker",
]

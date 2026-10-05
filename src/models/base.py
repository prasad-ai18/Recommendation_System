"""Base recommender abstract class and response structures."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
import pandas as pd


class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    genres: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    predicted_score: float
    rating_mean: float = 0.0
    rating_count: int = 0
    recommendation_signal: str = "Recommended for you"
    candidate_source: str = "retrieval"
    confidence: float = 1.0


class RecommendationResult(BaseModel):
    user_id: int
    model_name: str
    recommendations: List[RecommendationItem]
    total_returned: int
    latency_ms: float
    is_cold_start: bool = False
    context: Dict[str, Any] = Field(default_factory=dict)


class BaseRecommender(ABC):
    """Abstract interface that all recommendation algorithms must implement."""

    def __init__(self, name: str):
        self.name = name
        self.is_fitted = False
        self.movies_df: Optional[pd.DataFrame] = None
        self.movie_meta: Dict[int, Dict[str, Any]] = {}

    @abstractmethod
    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame) -> "BaseRecommender":
        """Fits the recommendation model using training interactions and movie metadata."""
        pass

    @abstractmethod
    def recommend(
        self,
        user_id: int,
        k: int = 10,
        seen_movie_ids: Optional[Set[int]] = None,
        candidate_ids: Optional[List[int]] = None,
        genre_filter: Optional[str] = None,
    ) -> List[RecommendationItem]:
        """Generates Top-K recommendation items for a given user."""
        pass

    @abstractmethod
    def predict_scores(self, user_id: int, movie_ids: List[int]) -> Dict[int, float]:
        """Predicts recommendation scores for specific user-movie pairs."""
        pass

    def get_name(self) -> str:
        return self.name

    def _cache_movie_metadata(self, movies_df: pd.DataFrame):
        """Indexes movie metadata into a fast in-memory dictionary."""
        self.movies_df = movies_df.copy()
        meta = {}
        for _, row in movies_df.iterrows():
            m_id = int(row["movieId"])
            genre_list = row.get("genre_list", [])
            if not isinstance(genre_list, list):
                genre_list = [g.strip() for g in str(row.get("genres", "")).split("|") if g.strip()]
            meta[m_id] = {
                "movieId": m_id,
                "title": str(row.get("title", f"Movie {m_id}")),
                "clean_title": str(row.get("clean_title", row.get("title", ""))),
                "year": int(row["year"]) if pd.notna(row.get("year")) else None,
                "genres": genre_list,
                "rating_mean": float(row.get("rating_mean", 0.0)),
                "rating_count": int(row.get("rating_count", 0)),
                "bayesian_score": float(row.get("bayesian_score", 0.0)),
            }
        self.movie_meta = meta

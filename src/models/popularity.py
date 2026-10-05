"""Popularity-based baseline recommender using Bayesian dampening."""

from typing import List, Dict, Any, Optional, Set
import pandas as pd
import numpy as np

from src.models.base import BaseRecommender, RecommendationItem
from src.logger import logger


class PopularityRecommender(BaseRecommender):
    """
    Baseline recommender that ranks items using a Bayesian weighted rating:
    WR = (v / (v + m)) * R + (m / (v + m)) * C
    where:
    - v is the count of ratings for the movie
    - m is the minimum vote threshold (e.g. 10)
    - R is the average rating for the movie
    - C is the global mean rating across all movies
    """

    def __init__(self, m: float = 10.0):
        super().__init__(name="popularity")
        self.m = m
        self.global_mean: float = 3.5
        self.item_scores: Dict[int, float] = {}
        self.sorted_items: List[int] = []

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame) -> "PopularityRecommender":
        logger.info("Fitting PopularityRecommender...")
        self._cache_movie_metadata(movies_df)

        self.global_mean = float(train_df["rating"].mean())

        # Group by movieId in training set only to avoid leakage
        agg = train_df.groupby("movieId")["rating"].agg(
            rating_count="count",
            rating_mean="mean"
        ).reset_index()

        scores = {}
        for _, row in agg.iterrows():
            m_id = int(row["movieId"])
            v = float(row["rating_count"])
            R = float(row["rating_mean"])
            wr = (v / (v + self.m)) * R + (self.m / (v + self.m)) * self.global_mean
            scores[m_id] = wr

        # For any movies in catalog without training ratings, assign default
        for m_id in self.movie_meta:
            if m_id not in scores:
                scores[m_id] = self.global_mean * 0.5

        self.item_scores = scores
        # Sort items descending by score
        self.sorted_items = sorted(self.item_scores.keys(), key=lambda x: self.item_scores[x], reverse=True)
        self.is_fitted = True
        logger.info(f"PopularityRecommender fitted on {len(self.sorted_items)} items.")
        return self

    def predict_scores(self, user_id: int, movie_ids: List[int]) -> Dict[int, float]:
        return {m_id: self.item_scores.get(m_id, self.global_mean) for m_id in movie_ids}

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        seen_movie_ids: Optional[Set[int]] = None,
        candidate_ids: Optional[List[int]] = None,
        genre_filter: Optional[str] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted. Call fit() before recommend().")

        seen = seen_movie_ids or set()
        candidate_pool = candidate_ids if candidate_ids is not None else self.sorted_items

        results: List[RecommendationItem] = []
        for m_id in candidate_pool:
            if m_id in seen:
                continue

            meta = self.movie_meta.get(m_id)
            if not meta:
                continue

            if genre_filter and genre_filter.lower() not in [g.lower() for g in meta["genres"]]:
                continue

            score = self.item_scores.get(m_id, self.global_mean)
            votes = meta.get("rating_count", 0)

            signal = f"Trending & highly rated ({votes} ratings, {meta['rating_mean']}★ avg)"
            results.append(
                RecommendationItem(
                    movie_id=m_id,
                    title=meta["title"],
                    genres=meta["genres"],
                    year=meta.get("year"),
                    predicted_score=round(score, 3),
                    rating_mean=meta["rating_mean"],
                    rating_count=votes,
                    recommendation_signal=signal,
                    candidate_source="popularity_baseline",
                    confidence=min(1.0, round(score / 5.0, 3)),
                )
            )

            if len(results) >= k:
                break

        return results

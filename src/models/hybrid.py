"""Hybrid recommendation model implementing multi-stage candidate generation and ranking."""

from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
import numpy as np
import pandas as pd

from src.models.base import BaseRecommender, RecommendationItem
from src.models.popularity import PopularityRecommender
from src.models.collaborative import ItemCollaborativeRecommender
from src.models.matrix_factorization import MatrixFactorizationRecommender
from src.pipeline.candidate_gen import CandidateGenerator
from src.pipeline.ranker import CandidateRanker
from src.logger import logger


class HybridRecommender(BaseRecommender):
    """
    Two-stage production-style Hybrid Recommender:
    Stage 1: Multi-channel candidate retrieval (CF + SVD + Genre + Popularity)
    Stage 2: Feature-weighted ranking + diversity penalty + explainability signals
    """

    def __init__(
        self,
        candidate_pool_size: int = 100,
        weight_cf: float = 0.35,
        weight_svd: float = 0.35,
        weight_genre: float = 0.15,
        weight_pop: float = 0.15,
    ):
        super().__init__(name="hybrid")
        self.candidate_gen = CandidateGenerator(pool_size=candidate_pool_size)
        self.ranker = CandidateRanker(
            weight_cf=weight_cf,
            weight_svd=weight_svd,
            weight_genre=weight_genre,
            weight_popularity=weight_pop,
        )

        self.popularity_model = PopularityRecommender()
        self.cf_model = ItemCollaborativeRecommender()
        self.svd_model = MatrixFactorizationRecommender()

        self.user_ratings: Dict[int, Dict[int, float]] = defaultdict(dict)
        self.user_genre_affinities: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.genre_to_movies: Dict[str, List[int]] = defaultdict(list)
        self.global_mean: float = 3.5

    def fit_with_prefitted_submodels(self, train_df: pd.DataFrame, movies_df: pd.DataFrame) -> "HybridRecommender":
        """Wires already fitted submodels and prepares user profile vectors."""
        self._cache_movie_metadata(movies_df)
        self.global_mean = float(train_df["rating"].mean())

        # In-memory ratings and genre affinities
        for _, row in train_df.iterrows():
            u = int(row["userId"])
            m = int(row["movieId"])
            r = float(row["rating"])
            self.user_ratings[u][m] = r

        for _, row in movies_df.iterrows():
            m_id = int(row["movieId"])
            genres = row.get("genre_list", [])
            if not isinstance(genres, list):
                genres = [g.strip() for g in str(row.get("genres", "")).split("|") if g.strip()]
            for g in genres:
                self.genre_to_movies[g].append(m_id)

        for g in self.genre_to_movies:
            self.genre_to_movies[g].sort(
                key=lambda m: self.movie_meta.get(m, {}).get("bayesian_score", 0.0), reverse=True
            )

        for u, m_dict in self.user_ratings.items():
            genre_rating_sums: Dict[str, float] = defaultdict(float)
            genre_rating_counts: Dict[str, int] = defaultdict(int)

            for m_id, r in m_dict.items():
                meta = self.movie_meta.get(m_id)
                if meta:
                    for g in meta.get("genres", []):
                        genre_rating_sums[g] += r
                        genre_rating_counts[g] += 1

            for g, count in genre_rating_counts.items():
                self.user_genre_affinities[u][g] = genre_rating_sums[g] / count

        self.is_fitted = True
        return self

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame) -> "HybridRecommender":
        logger.info("Fitting HybridRecommender sub-models...")
        self.popularity_model.fit(train_df, movies_df)
        self.cf_model.fit(train_df, movies_df)
        self.svd_model.fit(train_df, movies_df)
        return self.fit_with_prefitted_submodels(train_df, movies_df)

    def add_user_interaction(
        self, user_id: int, movie_id: int, rating: Optional[float] = None, interaction_type: str = "rating"
    ):
        """Dynamically updates user state when new feedback arrives."""
        val = rating if rating is not None else 4.0
        if interaction_type == "dislike":
            val = 1.0
        elif interaction_type in ["like", "bookmark"]:
            val = 4.5

        self.user_ratings[user_id][movie_id] = val
        meta = self.movie_meta.get(movie_id)
        if meta:
            for g in meta.get("genres", []):
                curr = self.user_genre_affinities[user_id].get(g, self.global_mean)
                self.user_genre_affinities[user_id][g] = (curr + val) / 2.0

    def predict_scores(self, user_id: int, movie_ids: List[int]) -> Dict[int, float]:
        cf_preds = self.cf_model.predict_scores(user_id, movie_ids)
        svd_preds = self.svd_model.predict_scores(user_id, movie_ids)
        scores = {}
        for m_id in movie_ids:
            scores[m_id] = (cf_preds.get(m_id, 3.5) * 0.5) + (svd_preds.get(m_id, 3.5) * 0.5)
        return scores

    def recommend(
        self,
        user_id: int,
        k: int = 10,
        seen_movie_ids: Optional[Set[int]] = None,
        candidate_ids: Optional[List[int]] = None,
        genre_filter: Optional[str] = None,
    ) -> List[RecommendationItem]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        user_history = self.user_ratings.get(user_id, {})
        seen = set(seen_movie_ids) if seen_movie_ids else set(user_history.keys())
        affinities = dict(self.user_genre_affinities.get(user_id, {}))

        if not user_history:
            return self.popularity_model.recommend(
                user_id=user_id, k=k, seen_movie_ids=seen, genre_filter=genre_filter
            )

        # Stage 1: Candidate Generation
        candidates = self.candidate_gen.generate_candidates(
            user_id=user_id,
            seen_movie_ids=seen,
            user_ratings=user_history,
            user_genre_affinities=affinities,
            item_cf_model=self.cf_model,
            svd_model=self.svd_model,
            popularity_model=self.popularity_model,
            movie_meta=self.movie_meta,
            genre_to_movies=self.genre_to_movies,
            genre_filter=genre_filter,
        )

        if candidate_ids is not None:
            cand_set = set(candidate_ids)
            candidates = [c for c in candidates if c.movie_id in cand_set]

        # Stage 2: Ranking & Diversity
        recommendations = self.ranker.rank(
            user_id=user_id,
            candidates=candidates,
            k=k,
            user_ratings=user_history,
            user_genre_affinities=affinities,
            item_cf_model=self.cf_model,
            svd_model=self.svd_model,
            movie_meta=self.movie_meta,
            global_mean=self.global_mean,
        )

        if len(recommendations) < k:
            existing_ids = {r.movie_id for r in recommendations} | seen
            fill_items = self.popularity_model.recommend(
                user_id=user_id,
                k=k - len(recommendations),
                seen_movie_ids=existing_ids,
                genre_filter=genre_filter,
            )
            recommendations.extend(fill_items)

        return recommendations[:k]

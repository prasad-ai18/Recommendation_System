"""Candidate generation pipeline retrieving candidates across multiple sources."""

from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd

from src.logger import logger


class CandidatePoolItem(BaseModel):
    movie_id: int
    source: str
    source_score: float
    seed_movie_id: Optional[int] = None
    seed_title: Optional[str] = None


class CandidateGenerator:
    """
    Multi-channel candidate generator retrieving items from:
    1. Item-Item collaborative neighborhood
    2. Latent factor SVD embeddings
    3. User genre-affinity preferences
    4. Popularity baseline priors
    """

    def __init__(
        self,
        pool_size: int = 100,
        cf_candidates_count: int = 40,
        svd_candidates_count: int = 40,
        genre_candidates_count: int = 30,
        pop_candidates_count: int = 20,
    ):
        self.pool_size = pool_size
        self.cf_candidates_count = cf_candidates_count
        self.svd_candidates_count = svd_candidates_count
        self.genre_candidates_count = genre_candidates_count
        self.pop_candidates_count = pop_candidates_count

    def generate_candidates(
        self,
        user_id: int,
        seen_movie_ids: Set[int],
        user_ratings: Dict[int, float],
        user_genre_affinities: Dict[str, float],
        item_cf_model: Any,
        svd_model: Any,
        popularity_model: Any,
        movie_meta: Dict[int, Dict[str, Any]],
        genre_to_movies: Dict[str, List[int]],
        genre_filter: Optional[str] = None,
    ) -> List[CandidatePoolItem]:
        """Collects and deduplicates candidate items from all available retrieval channels."""
        candidates: Dict[int, CandidatePoolItem] = {}

        # 1. Collaborative Filtering Channel
        if item_cf_model and item_cf_model.is_fitted and user_ratings:
            # Pick top liked items
            top_liked = sorted(
                [(m, r) for m, r in user_ratings.items() if r >= 3.0],
                key=lambda x: x[1],
                reverse=True,
            )[:5]

            for seed_id, seed_r in top_liked:
                seed_meta = movie_meta.get(seed_id, {})
                neighbors = item_cf_model.item_similarities.get(seed_id, [])
                for neighbor_id, sim in neighbors[:15]:
                    if neighbor_id in seen_movie_ids:
                        continue
                    if neighbor_id not in candidates or sim > candidates[neighbor_id].source_score:
                        candidates[neighbor_id] = CandidatePoolItem(
                            movie_id=neighbor_id,
                            source="item_collaborative",
                            source_score=float(sim),
                            seed_movie_id=seed_id,
                            seed_title=seed_meta.get("clean_title", "Liked Movie"),
                        )

        # 2. Latent Factor SVD Channel
        if svd_model and svd_model.is_fitted and user_id in svd_model.user_to_idx:
            u_idx = svd_model.user_to_idx[user_id]
            u_bias = svd_model.user_biases[u_idx]
            u_vector = svd_model.user_factors[u_idx]

            dot_products = np.dot(svd_model.item_factors, u_vector)
            preds = svd_model.global_mean + u_bias + svd_model.item_biases + dot_products

            # Top 40 indices
            top_indices = np.argsort(preds)[::-1][: self.svd_candidates_count * 2]
            added_svd = 0
            for idx in top_indices:
                m_id = svd_model.idx_to_item[idx]
                if m_id in seen_movie_ids:
                    continue
                if m_id not in candidates:
                    candidates[m_id] = CandidatePoolItem(
                        movie_id=m_id,
                        source="matrix_factorization_svd",
                        source_score=float(preds[idx]),
                    )
                    added_svd += 1
                    if added_svd >= self.svd_candidates_count:
                        break

        # 3. User Genre-Affinity Channel
        if user_genre_affinities and genre_to_movies:
            # Identify user's top 2 favorite genres
            top_genres = sorted(user_genre_affinities.items(), key=lambda x: x[1], reverse=True)[:3]
            for genre_name, aff_score in top_genres:
                genre_movies = genre_to_movies.get(genre_name, [])
                added_g = 0
                for m_id in genre_movies:
                    if m_id in seen_movie_ids:
                        continue
                    if m_id not in candidates:
                        meta = movie_meta.get(m_id, {})
                        candidates[m_id] = CandidatePoolItem(
                            movie_id=m_id,
                            source=f"genre_affinity_{genre_name.lower()}",
                            source_score=float(meta.get("bayesian_score", 3.5)),
                        )
                        added_g += 1
                        if added_g >= 10:
                            break

        # 4. Popularity Baseline Channel (Catalog coverage & cold-start guarantee)
        if popularity_model and popularity_model.is_fitted:
            added_pop = 0
            for m_id in popularity_model.sorted_items:
                if m_id in seen_movie_ids:
                    continue
                if m_id not in candidates:
                    candidates[m_id] = CandidatePoolItem(
                        movie_id=m_id,
                        source="popularity_prior",
                        source_score=float(popularity_model.item_scores.get(m_id, 3.5)),
                    )
                    added_pop += 1
                    if added_pop >= self.pop_candidates_count:
                        break

        # Filter by genre if genre_filter is applied
        candidate_list = list(candidates.values())
        if genre_filter:
            gf_lower = genre_filter.lower()
            candidate_list = [
                c
                for c in candidate_list
                if gf_lower in [g.lower() for g in movie_meta.get(c.movie_id, {}).get("genres", [])]
            ]

        return candidate_list[: self.pool_size]

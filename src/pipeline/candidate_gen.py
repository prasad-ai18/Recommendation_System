"""Modular candidate generation pipeline with extensible retrieval channels."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
from pydantic import BaseModel, Field
import numpy as np

from src.logger import logger


class CandidatePoolItem(BaseModel):
    movie_id: int
    source: str
    source_score: float
    seed_movie_id: Optional[int] = None
    seed_title: Optional[str] = None


class BaseCandidateChannel(ABC):
    """Abstract interface for candidate retrieval channels."""

    def __init__(self, name: str, candidate_limit: int):
        self.name = name
        self.candidate_limit = candidate_limit

    @abstractmethod
    def retrieve(
        self,
        user_id: int,
        seen_movie_ids: Set[int],
        context: Dict[str, Any],
    ) -> List[CandidatePoolItem]:
        pass


class CollaborativeNeighborhoodChannel(BaseCandidateChannel):
    """Retrieves candidates from the item-item collaborative similarity neighborhood."""

    def __init__(self, candidate_limit: int = 40):
        super().__init__(name="collaborative_neighborhood", candidate_limit=candidate_limit)

    def retrieve(
        self,
        user_id: int,
        seen_movie_ids: Set[int],
        context: Dict[str, Any],
    ) -> List[CandidatePoolItem]:
        item_cf_model = context.get("item_cf_model")
        user_ratings = context.get("user_ratings", {})
        movie_meta = context.get("movie_meta", {})

        if not item_cf_model or not item_cf_model.is_fitted or not user_ratings:
            return []

        # Find top 5 user liked movies (rating >= 3.0)
        top_liked = sorted(
            [(m, r) for m, r in user_ratings.items() if r >= 3.0],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        candidates = []
        seen_in_channel = set()

        for seed_id, seed_r in top_liked:
            seed_meta = movie_meta.get(seed_id, {})
            neighbors = item_cf_model.item_similarities.get(seed_id, [])
            for neighbor_id, sim in neighbors[:15]:
                if neighbor_id in seen_movie_ids or neighbor_id in seen_in_channel:
                    continue
                candidates.append(
                    CandidatePoolItem(
                        movie_id=neighbor_id,
                        source="item_collaborative",
                        source_score=float(sim),
                        seed_movie_id=seed_id,
                        seed_title=seed_meta.get("clean_title", "Liked Movie"),
                    )
                )
                seen_in_channel.add(neighbor_id)
                if len(candidates) >= self.candidate_limit:
                    return candidates

        return candidates


class LatentFactorChannel(BaseCandidateChannel):
    """Retrieves candidates with highest dot-product in latent SVD embedding space."""

    def __init__(self, candidate_limit: int = 40):
        super().__init__(name="latent_factor_svd", candidate_limit=candidate_limit)

    def retrieve(
        self,
        user_id: int,
        seen_movie_ids: Set[int],
        context: Dict[str, Any],
    ) -> List[CandidatePoolItem]:
        svd_model = context.get("svd_model")
        if not svd_model or not svd_model.is_fitted or user_id not in svd_model.user_to_idx:
            return []

        u_idx = svd_model.user_to_idx[user_id]
        u_bias = svd_model.user_biases[u_idx]
        u_vector = svd_model.user_factors[u_idx]

        dot_products = np.dot(svd_model.item_factors, u_vector)
        preds = svd_model.global_mean + u_bias + svd_model.item_biases + dot_products

        top_indices = np.argsort(preds)[::-1][: self.candidate_limit * 2]
        candidates = []
        for idx in top_indices:
            m_id = svd_model.idx_to_item[idx]
            if m_id in seen_movie_ids:
                continue
            candidates.append(
                CandidatePoolItem(
                    movie_id=m_id,
                    source="matrix_factorization_svd",
                    source_score=float(preds[idx]),
                )
            )
            if len(candidates) >= self.candidate_limit:
                break
        return candidates


class GenreAffinityChannel(BaseCandidateChannel):
    """Retrieves candidates aligned with user's top preferred genre distributions."""

    def __init__(self, candidate_limit: int = 30):
        super().__init__(name="genre_affinity", candidate_limit=candidate_limit)

    def retrieve(
        self,
        user_id: int,
        seen_movie_ids: Set[int],
        context: Dict[str, Any],
    ) -> List[CandidatePoolItem]:
        affinities = context.get("user_genre_affinities", {})
        genre_to_movies = context.get("genre_to_movies", {})
        movie_meta = context.get("movie_meta", {})

        if not affinities or not genre_to_movies:
            return []

        top_genres = sorted(affinities.items(), key=lambda x: x[1], reverse=True)[:3]
        candidates = []
        seen_in_channel = set()

        for genre_name, _ in top_genres:
            genre_movies = genre_to_movies.get(genre_name, [])
            added_for_genre = 0
            for m_id in genre_movies:
                if m_id in seen_movie_ids or m_id in seen_in_channel:
                    continue
                meta = movie_meta.get(m_id, {})
                candidates.append(
                    CandidatePoolItem(
                        movie_id=m_id,
                        source=f"genre_affinity_{genre_name.lower()}",
                        source_score=float(meta.get("bayesian_score", 3.5)),
                    )
                )
                seen_in_channel.add(m_id)
                added_for_genre += 1
                if added_for_genre >= 10:
                    break
                if len(candidates) >= self.candidate_limit:
                    return candidates

        return candidates


class PopularityPriorChannel(BaseCandidateChannel):
    """Retrieves catalog discovery items based on Bayesian dampening weighted ratings."""

    def __init__(self, candidate_limit: int = 20):
        super().__init__(name="popularity_prior", candidate_limit=candidate_limit)

    def retrieve(
        self,
        user_id: int,
        seen_movie_ids: Set[int],
        context: Dict[str, Any],
    ) -> List[CandidatePoolItem]:
        popularity_model = context.get("popularity_model")
        if not popularity_model or not popularity_model.is_fitted:
            return []

        candidates = []
        for m_id in popularity_model.sorted_items:
            if m_id in seen_movie_ids:
                continue
            candidates.append(
                CandidatePoolItem(
                    movie_id=m_id,
                    source="popularity_prior",
                    source_score=float(popularity_model.item_scores.get(m_id, 3.5)),
                )
            )
            if len(candidates) >= self.candidate_limit:
                break
        return candidates


class CandidateGenerator:
    """
    Multi-channel candidate generator coordinating modular retrieval channels.
    Allows easy addition of new candidate generation strategies.
    """

    def __init__(self, pool_size: int = 100):
        self.pool_size = pool_size
        self.channels: List[BaseCandidateChannel] = [
            CollaborativeNeighborhoodChannel(candidate_limit=40),
            LatentFactorChannel(candidate_limit=40),
            GenreAffinityChannel(candidate_limit=30),
            PopularityPriorChannel(candidate_limit=20),
        ]

    def register_channel(self, channel: BaseCandidateChannel):
        """Adds a custom candidate retrieval channel modularly."""
        self.channels.append(channel)
        logger.info(f"Registered new candidate retrieval channel: '{channel.name}'")

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
        """Collects, deduplicates, and filters candidates across all active channels."""
        context = {
            "user_ratings": user_ratings,
            "user_genre_affinities": user_genre_affinities,
            "item_cf_model": item_cf_model,
            "svd_model": svd_model,
            "popularity_model": popularity_model,
            "movie_meta": movie_meta,
            "genre_to_movies": genre_to_movies,
        }

        candidates_by_id: Dict[int, CandidatePoolItem] = {}

        for channel in self.channels:
            channel_items = channel.retrieve(user_id=user_id, seen_movie_ids=seen_movie_ids, context=context)
            for item in channel_items:
                if item.movie_id not in candidates_by_id:
                    candidates_by_id[item.movie_id] = item
                elif item.source_score > candidates_by_id[item.movie_id].source_score:
                    candidates_by_id[item.movie_id] = item

        candidate_list = list(candidates_by_id.values())

        # Filter by genre if applied
        if genre_filter:
            gf_lower = genre_filter.lower()
            candidate_list = [
                c
                for c in candidate_list
                if gf_lower in [g.lower() for g in movie_meta.get(c.movie_id, {}).get("genres", [])]
            ]

        return candidate_list[: self.pool_size]

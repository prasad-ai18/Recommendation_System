"""Ranking engine combining multi-source scoring, diversity penalties, and explainability."""

from typing import List, Dict, Any, Optional, Set, Tuple
from collections import Counter
import numpy as np

from src.models.base import RecommendationItem
from src.pipeline.candidate_gen import CandidatePoolItem
from src.logger import logger


class CandidateRanker:
    """
    Ranks candidate items using a weighted hybrid scoring function,
    generates transparent explainability signals, and applies diversity control.
    """

    def __init__(
        self,
        weight_cf: float = 0.35,
        weight_svd: float = 0.35,
        weight_genre: float = 0.15,
        weight_popularity: float = 0.15,
        diversity_lambda: float = 0.10,
    ):
        self.weight_cf = weight_cf
        self.weight_svd = weight_svd
        self.weight_genre = weight_genre
        self.weight_popularity = weight_popularity
        self.diversity_lambda = diversity_lambda

    def rank(
        self,
        user_id: int,
        candidates: List[CandidatePoolItem],
        k: int,
        user_ratings: Dict[int, float],
        user_genre_affinities: Dict[str, float],
        item_cf_model: Any,
        svd_model: Any,
        movie_meta: Dict[int, Dict[str, Any]],
        global_mean: float = 3.5,
    ) -> List[RecommendationItem]:
        """Scores, re-ranks, and attaches explainability signals to candidates."""
        if not candidates:
            return []

        movie_ids = [c.movie_id for c in candidates]

        # Get batch predictions from CF and SVD
        cf_preds = item_cf_model.predict_scores(user_id, movie_ids) if item_cf_model else {}
        svd_preds = svd_model.predict_scores(user_id, movie_ids) if svd_model else {}

        # Max genre affinity for normalization
        max_genre_aff = max(user_genre_affinities.values()) if user_genre_affinities else 1.0
        if max_genre_aff <= 0:
            max_genre_aff = 1.0

        scored_items: List[Dict[str, Any]] = []

        for cand in candidates:
            m_id = cand.movie_id
            meta = movie_meta.get(m_id, {})
            movie_genres = meta.get("genres", [])

            # Compute genre score
            genre_scores = [user_genre_affinities.get(g, 0.0) for g in movie_genres]
            genre_score = (sum(genre_scores) / len(genre_scores)) if genre_scores else 0.0
            norm_genre = min(1.0, genre_score / max_genre_aff)

            # Component predictions (1.0 to 5.0)
            cf_val = cf_preds.get(m_id, global_mean)
            svd_val = svd_preds.get(m_id, global_mean)
            pop_val = meta.get("bayesian_score", global_mean)

            # Normalized components to [0, 1]
            cf_norm = np.clip((cf_val - 1.0) / 4.0, 0.0, 1.0)
            svd_norm = np.clip((svd_val - 1.0) / 4.0, 0.0, 1.0)
            pop_norm = np.clip((pop_val - 1.0) / 4.0, 0.0, 1.0)

            composite_score = (
                self.weight_cf * cf_norm
                + self.weight_svd * svd_norm
                + self.weight_genre * norm_genre
                + self.weight_popularity * pop_norm
            )

            # Rescale back to 1.0 - 5.0 scale for intuitive user-facing rating prediction
            predicted_rating = 1.0 + composite_score * 4.0

            # Generate Explainability Signal
            signal = self._build_explainability_signal(
                cand=cand,
                meta=meta,
                user_ratings=user_ratings,
                user_genre_affinities=user_genre_affinities,
                cf_val=cf_val,
                svd_val=svd_val,
            )

            scored_items.append({
                "candidate": cand,
                "meta": meta,
                "raw_score": composite_score,
                "predicted_rating": predicted_rating,
                "signal": signal,
                "genres": movie_genres,
                "confidence": min(1.0, round(composite_score, 3)),
            })

        # Apply Diversity Re-ranking (Greedy MMR-inspired approach)
        selected_items = self._apply_diversity_selection(scored_items, k=k)

        # Convert to RecommendationItem list
        results: List[RecommendationItem] = []
        for item in selected_items:
            meta = item["meta"]
            results.append(
                RecommendationItem(
                    movie_id=item["candidate"].movie_id,
                    title=meta.get("title", f"Movie {item['candidate'].movie_id}"),
                    genres=meta.get("genres", []),
                    year=meta.get("year"),
                    predicted_score=round(float(item["predicted_rating"]), 3),
                    rating_mean=meta.get("rating_mean", 0.0),
                    rating_count=meta.get("rating_count", 0),
                    recommendation_signal=item["signal"],
                    candidate_source=item["candidate"].source,
                    confidence=item["confidence"],
                )
            )

        return results

    def _apply_diversity_selection(
        self, scored_items: List[Dict[str, Any]], k: int
    ) -> List[Dict[str, Any]]:
        """Applies a gentle diversity penalty for duplicate genres in top results."""
        remaining = list(scored_items)
        selected: List[Dict[str, Any]] = []
        genre_counts: Counter = Counter()

        while remaining and len(selected) < k:
            best_idx = -1
            best_penalized_score = -float("inf")

            for idx, item in enumerate(remaining):
                # Count overlap with already selected genres
                item_genres = item["genres"]
                overlap = sum(genre_counts[g] for g in item_genres)
                penalty = self.diversity_lambda * overlap
                adj_score = item["raw_score"] - penalty

                if adj_score > best_penalized_score:
                    best_penalized_score = adj_score
                    best_idx = idx

            chosen = remaining.pop(best_idx)
            selected.append(chosen)
            for g in chosen["genres"]:
                genre_counts[g] += 1

        return selected

    def _build_explainability_signal(
        self,
        cand: CandidatePoolItem,
        meta: Dict[str, Any],
        user_ratings: Dict[int, float],
        user_genre_affinities: Dict[str, float],
        cf_val: float,
        svd_val: float,
    ) -> str:
        """Determines the strongest justification for the recommendation."""
        # Check if item has a direct collaborative seed
        if cand.seed_title and cand.seed_movie_id:
            user_seed_rating = user_ratings.get(cand.seed_movie_id, 4.0)
            return f"Because you loved '{cand.seed_title}' ({user_seed_rating:.1f}★)"

        # Check if matched user's favorite genre
        movie_genres = meta.get("genres", [])
        if movie_genres and user_genre_affinities:
            top_genre = max(movie_genres, key=lambda g: user_genre_affinities.get(g, 0.0))
            if user_genre_affinities.get(top_genre, 0.0) >= 3.8:
                return f"Top match for your high affinity with {top_genre}"

        # High SVD latent affinity
        if svd_val >= 4.0:
            return "Strong alignment with your underlying viewing tastes"

        # Popularity / High ratings
        v = meta.get("rating_count", 0)
        mean_r = meta.get("rating_mean", 0.0)
        if v >= 50:
            return f"Acclaimed by community ({v} ratings, {mean_r}★ avg)"

        return "Personalized recommendation based on your profile"

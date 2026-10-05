"""Item-based Collaborative Filtering Recommender with fast vectorized neighbor caching."""

from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, diags

from src.models.base import BaseRecommender, RecommendationItem
from src.logger import logger


class ItemCollaborativeRecommender(BaseRecommender):
    """
    Item-Item Collaborative Filtering using cosine similarity on user-item interaction vectors.
    Aggregates user's historical ratings weighted by item-item similarity.
    """

    def __init__(self, top_neighbors: int = 40, min_sim: float = 0.01):
        super().__init__(name="item_collaborative")
        self.top_neighbors = top_neighbors
        self.min_sim = min_sim

        self.user_to_idx: Dict[int, int] = {}
        self.idx_to_user: Dict[int, int] = {}
        self.item_to_idx: Dict[int, int] = {}
        self.idx_to_item: Dict[int, int] = {}

        self.user_ratings: Dict[int, Dict[int, float]] = defaultdict(dict)
        self.user_means: Dict[int, float] = {}
        self.item_similarities: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
        self.global_mean: float = 3.5

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame) -> "ItemCollaborativeRecommender":
        logger.info("Fitting ItemCollaborativeRecommender...")
        self._cache_movie_metadata(movies_df)

        self.global_mean = float(train_df["rating"].mean())

        unique_users = sorted(train_df["userId"].unique().tolist())
        unique_items = sorted(train_df["movieId"].unique().tolist())

        self.user_to_idx = {u: i for i, u in enumerate(unique_users)}
        self.idx_to_user = {i: u for u, i in self.user_to_idx.items()}
        self.item_to_idx = {m: i for i, m in enumerate(unique_items)}
        self.idx_to_item = {i: m for m, i in self.item_to_idx.items()}

        for _, row in train_df.iterrows():
            u = int(row["userId"])
            m = int(row["movieId"])
            r = float(row["rating"])
            self.user_ratings[u][m] = r

        for u, ratings in self.user_ratings.items():
            self.user_means[u] = float(np.mean(list(ratings.values())))

        # Build sparse user-item matrix
        rows, cols, data = [], [], []
        for _, row in train_df.iterrows():
            u = int(row["userId"])
            m = int(row["movieId"])
            r = float(row["rating"])
            rows.append(self.user_to_idx[u])
            cols.append(self.item_to_idx[m])
            data.append(r)

        n_users = len(unique_users)
        n_items = len(unique_items)
        user_item_matrix = csr_matrix((data, (rows, cols)), shape=(n_users, n_items), dtype=np.float32)

        # Transpose to item-user matrix: shape (n_items, n_users)
        item_matrix = user_item_matrix.T.tocsr()

        # Compute cosine similarity between items via normalized sparse dot products
        logger.info(f"Computing item-item cosine similarities for {n_items} items...")
        row_sq_sums = np.array(item_matrix.multiply(item_matrix).sum(axis=1)).flatten()
        row_norms = np.sqrt(row_sq_sums)
        row_norms[row_norms == 0] = 1.0  # avoid division by zero
        inv_norms = diags(1.0 / row_norms)
        normalized_items = inv_norms.dot(item_matrix).tocsr()

        sim_matrix = normalized_items.dot(normalized_items.T).tocsr()

        # Fast vectorized top-K neighbor extraction using CSR raw arrays
        indptr = sim_matrix.indptr
        indices = sim_matrix.indices
        sim_data = sim_matrix.data

        for idx in range(n_items):
            m_id = self.idx_to_item[idx]
            r_start = indptr[idx]
            r_end = indptr[idx + 1]

            cols_slice = indices[r_start:r_end]
            sims_slice = sim_data[r_start:r_end]

            # Filter out self
            mask = (cols_slice != idx) & (sims_slice >= self.min_sim)
            valid_cols = cols_slice[mask]
            valid_sims = sims_slice[mask]

            if len(valid_cols) == 0:
                continue

            if len(valid_cols) > self.top_neighbors:
                part = np.argpartition(valid_sims, -self.top_neighbors)[-self.top_neighbors:]
                sorted_part = part[np.argsort(valid_sims[part])[::-1]]
                chosen_cols = valid_cols[sorted_part]
                chosen_sims = valid_sims[sorted_part]
            else:
                sort_idx = np.argsort(valid_sims)[::-1]
                chosen_cols = valid_cols[sort_idx]
                chosen_sims = valid_sims[sort_idx]

            self.item_similarities[m_id] = [
                (self.idx_to_item[int(c)], float(s)) for c, s in zip(chosen_cols, chosen_sims)
            ]

        self.is_fitted = True
        logger.info(
            f"ItemCollaborativeRecommender successfully fitted ({len(self.item_similarities)} items with neighbors)."
        )
        return self

    def predict_scores(self, user_id: int, movie_ids: List[int]) -> Dict[int, float]:
        user_history = self.user_ratings.get(user_id, {})
        u_mean = self.user_means.get(user_id, self.global_mean)

        scores = {}
        for m_id in movie_ids:
            neighbors = self.item_similarities.get(m_id, [])
            sim_sum = 0.0
            weighted_sum = 0.0

            for neighbor_id, sim in neighbors:
                if neighbor_id in user_history:
                    sim_sum += sim
                    weighted_sum += sim * user_history[neighbor_id]

            if sim_sum > 0:
                pred = float(np.clip(weighted_sum / sim_sum, 0.5, 5.0))
            else:
                pred = u_mean

            scores[m_id] = pred

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
            raise RuntimeError("Model is not fitted. Call fit() before recommend().")

        seen = set(seen_movie_ids) if seen_movie_ids else set(self.user_ratings.get(user_id, {}).keys())
        user_history = self.user_ratings.get(user_id, {})

        if not user_history:
            return self._cold_start_fallback(user_id, k, seen, genre_filter)

        u_mean = self.user_means.get(user_id, self.global_mean)

        candidate_scores: Dict[int, float] = defaultdict(float)
        candidate_weights: Dict[int, float] = defaultdict(float)
        best_contributor: Dict[int, Tuple[int, float, float]] = {}

        positive_seeds = {m: r for m, r in user_history.items() if r >= 3.0}
        if not positive_seeds:
            positive_seeds = user_history

        for seed_id, seed_rating in positive_seeds.items():
            neighbors = self.item_similarities.get(seed_id, [])
            for neighbor_id, sim in neighbors:
                if neighbor_id in seen:
                    continue
                if candidate_ids is not None and neighbor_id not in candidate_ids:
                    continue

                meta = self.movie_meta.get(neighbor_id)
                if not meta:
                    continue
                if genre_filter and genre_filter.lower() not in [g.lower() for g in meta["genres"]]:
                    continue

                weight = sim * (seed_rating / 5.0)
                candidate_scores[neighbor_id] += weight
                candidate_weights[neighbor_id] += sim

                if neighbor_id not in best_contributor or sim > best_contributor[neighbor_id][1]:
                    best_contributor[neighbor_id] = (seed_id, sim, seed_rating)

        if not candidate_scores:
            return self._cold_start_fallback(user_id, k, seen, genre_filter)

        final_scores: List[Tuple[int, float]] = []
        for m_id, raw_score in candidate_scores.items():
            w = candidate_weights[m_id]
            norm_score = raw_score / w if w > 0 else 0
            pred_rating = np.clip(u_mean * 0.3 + norm_score * 3.5, 1.0, 5.0)
            final_scores.append((m_id, float(pred_rating)))

        final_scores.sort(key=lambda x: x[1], reverse=True)

        results: List[RecommendationItem] = []
        for m_id, pred_score in final_scores[:k]:
            meta = self.movie_meta.get(m_id, {})
            seed_info = best_contributor.get(m_id)
            if seed_info:
                seed_meta = self.movie_meta.get(seed_info[0], {})
                signal = f"Because you liked '{seed_meta.get('clean_title', 'a movie')}' ({seed_info[2]:.1f}★)"
            else:
                signal = "Based on similar movies you enjoyed"

            results.append(
                RecommendationItem(
                    movie_id=m_id,
                    title=meta.get("title", f"Movie {m_id}"),
                    genres=meta.get("genres", []),
                    year=meta.get("year"),
                    predicted_score=round(pred_score, 3),
                    rating_mean=meta.get("rating_mean", 0.0),
                    rating_count=meta.get("rating_count", 0),
                    recommendation_signal=signal,
                    candidate_source="item_collaborative_cf",
                    confidence=min(1.0, round(pred_score / 5.0, 3)),
                )
            )

        return results

    def _cold_start_fallback(
        self, user_id: int, k: int, seen: Set[int], genre_filter: Optional[str]
    ) -> List[RecommendationItem]:
        sorted_meta = sorted(
            self.movie_meta.values(), key=lambda x: x.get("bayesian_score", 0.0), reverse=True
        )
        results = []
        for meta in sorted_meta:
            m_id = meta["movieId"]
            if m_id in seen:
                continue
            if genre_filter and genre_filter.lower() not in [g.lower() for g in meta["genres"]]:
                continue

            results.append(
                RecommendationItem(
                    movie_id=m_id,
                    title=meta["title"],
                    genres=meta["genres"],
                    year=meta.get("year"),
                    predicted_score=round(meta.get("bayesian_score", self.global_mean), 3),
                    rating_mean=meta["rating_mean"],
                    rating_count=meta["rating_count"],
                    recommendation_signal="Popular recommendation for new profile",
                    candidate_source="cold_start_prior",
                    confidence=0.7,
                )
            )
            if len(results) >= k:
                break
        return results

"""Latent factor matrix factorization recommender using scipy.sparse.linalg.svds."""

from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds

from src.models.base import BaseRecommender, RecommendationItem
from src.logger import logger


class MatrixFactorizationRecommender(BaseRecommender):
    """
    Latent factor model using Singular Value Decomposition (SVD) on centered user-item ratings.
    Computes dense latent representations (embeddings) for both users and items.
    """

    def __init__(self, n_components: int = 35, random_state: int = 42):
        super().__init__(name="matrix_factorization_svd")
        self.n_components = n_components
        self.random_state = random_state

        self.user_to_idx: Dict[int, int] = {}
        self.idx_to_user: Dict[int, int] = {}
        self.item_to_idx: Dict[int, int] = {}
        self.idx_to_item: Dict[int, int] = {}

        self.user_ratings: Dict[int, Dict[int, float]] = defaultdict(dict)
        self.user_biases: np.ndarray = np.array([])
        self.item_biases: np.ndarray = np.array([])
        self.global_mean: float = 3.5

        self.user_factors: np.ndarray = np.array([])
        self.item_factors: np.ndarray = np.array([])

    def fit(self, train_df: pd.DataFrame, movies_df: pd.DataFrame) -> "MatrixFactorizationRecommender":
        logger.info(f"Fitting MatrixFactorizationRecommender (n_components={self.n_components})...")
        self._cache_movie_metadata(movies_df)

        self.global_mean = float(train_df["rating"].mean())

        unique_users = sorted(train_df["userId"].unique().tolist())
        unique_items = sorted(train_df["movieId"].unique().tolist())

        self.user_to_idx = {u: i for i, u in enumerate(unique_users)}
        self.idx_to_user = {i: u for u, i in self.user_to_idx.items()}
        self.item_to_idx = {m: i for i, m in enumerate(unique_items)}
        self.idx_to_item = {i: m for m, i in self.item_to_idx.items()}

        n_users = len(unique_users)
        n_items = len(unique_items)

        for _, row in train_df.iterrows():
            u = int(row["userId"])
            m = int(row["movieId"])
            r = float(row["rating"])
            self.user_ratings[u][m] = r

        # Compute item and user biases
        item_sums = np.zeros(n_items)
        item_counts = np.zeros(n_items)
        user_sums = np.zeros(n_users)
        user_counts = np.zeros(n_users)

        for u, movies in self.user_ratings.items():
            u_idx = self.user_to_idx[u]
            for m, r in movies.items():
                m_idx = self.item_to_idx[m]
                diff = r - self.global_mean
                user_sums[u_idx] += diff
                user_counts[u_idx] += 1
                item_sums[m_idx] += diff
                item_counts[m_idx] += 1

        reg = 5.0
        self.user_biases = user_sums / (user_counts + reg)
        self.item_biases = item_sums / (item_counts + reg)

        # Residual sparse matrix: R_ui - mu - b_u - b_i
        rows, cols, data = [], [], []
        for u, movies in self.user_ratings.items():
            u_idx = self.user_to_idx[u]
            for m, r in movies.items():
                m_idx = self.item_to_idx[m]
                residual = r - self.global_mean - self.user_biases[u_idx] - self.item_biases[m_idx]
                rows.append(u_idx)
                cols.append(m_idx)
                data.append(residual)

        sparse_residuals = csr_matrix((data, (rows, cols)), shape=(n_users, n_items), dtype=np.float32)

        # Fit SVD using scipy.sparse.linalg.svds
        actual_k = min(self.n_components, n_users - 2, n_items - 2)
        u_mat, s_vec, vt_mat = svds(sparse_residuals, k=actual_k, random_state=self.random_state)

        # Sort singular values in descending order
        sort_indices = np.argsort(s_vec)[::-1]
        s_sorted = s_vec[sort_indices]
        u_sorted = u_mat[:, sort_indices]
        vt_sorted = vt_mat[sort_indices, :]

        # Weight factors by square root of singular values
        sqrt_s = np.sqrt(np.maximum(s_sorted, 1e-6))
        self.user_factors = u_sorted * sqrt_s  # shape: (n_users, k)
        self.item_factors = vt_sorted.T * sqrt_s  # shape: (n_items, k)

        self.is_fitted = True
        logger.info(f"MatrixFactorizationRecommender fitted successfully with {actual_k} latent factors.")
        return self

    def predict_scores(self, user_id: int, movie_ids: List[int]) -> Dict[int, float]:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted.")

        scores = {}
        if user_id in self.user_to_idx:
            u_idx = self.user_to_idx[user_id]
            u_bias = self.user_biases[u_idx]
            u_vector = self.user_factors[u_idx]

            for m_id in movie_ids:
                if m_id in self.item_to_idx:
                    m_idx = self.item_to_idx[m_id]
                    m_bias = self.item_biases[m_idx]
                    dot = float(np.dot(u_vector, self.item_factors[m_idx]))
                    pred = self.global_mean + u_bias + m_bias + dot
                    scores[m_id] = float(np.clip(pred, 0.5, 5.0))
                else:
                    scores[m_id] = self.global_mean
        else:
            for m_id in movie_ids:
                if m_id in self.item_to_idx:
                    m_idx = self.item_to_idx[m_id]
                    scores[m_id] = float(self.global_mean + self.item_biases[m_idx])
                else:
                    scores[m_id] = self.global_mean

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

        seen = set(seen_movie_ids) if seen_movie_ids else set(self.user_ratings.get(user_id, {}).keys())

        if user_id in self.user_to_idx:
            u_idx = self.user_to_idx[user_id]
            u_bias = self.user_biases[u_idx]
            u_vector = self.user_factors[u_idx]

            dot_products = np.dot(self.item_factors, u_vector)
            all_preds = self.global_mean + u_bias + self.item_biases + dot_products

            scored_candidates: List[Tuple[int, float]] = []
            pool_indices = (
                [self.item_to_idx[m] for m in candidate_ids if m in self.item_to_idx]
                if candidate_ids is not None
                else range(len(self.idx_to_item))
            )

            for m_idx in pool_indices:
                m_id = self.idx_to_item[m_idx]
                if m_id in seen:
                    continue

                meta = self.movie_meta.get(m_id)
                if not meta:
                    continue
                if genre_filter and genre_filter.lower() not in [g.lower() for g in meta["genres"]]:
                    continue

                pred = float(np.clip(all_preds[m_idx], 0.5, 5.0))
                scored_candidates.append((m_id, pred))

            scored_candidates.sort(key=lambda x: x[1], reverse=True)

            results: List[RecommendationItem] = []
            for m_id, pred in scored_candidates[:k]:
                meta = self.movie_meta[m_id]
                results.append(
                    RecommendationItem(
                        movie_id=m_id,
                        title=meta["title"],
                        genres=meta["genres"],
                        year=meta.get("year"),
                        predicted_score=round(pred, 3),
                        rating_mean=meta["rating_mean"],
                        rating_count=meta["rating_count"],
                        recommendation_signal="High affinity match in latent preference space",
                        candidate_source="matrix_factorization_svd",
                        confidence=min(1.0, round(pred / 5.0, 3)),
                    )
                )
            return results

        return self._cold_start_fallback(user_id, k, seen, genre_filter)

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
                    recommendation_signal="Global high-affinity baseline",
                    candidate_source="cold_start_prior",
                    confidence=0.7,
                )
            )
            if len(results) >= k:
                break
        return results

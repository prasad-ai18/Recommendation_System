"""User and item representation engine providing latent embeddings and content vectors."""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
from src.logger import logger


class UserItemRepresentations:
    """
    Manages structured user and item representations:
    1. Latent factor embeddings derived from Singular Value Decomposition (SVD).
    2. Explicit genre feature vectors (TF-IDF / normalized one-hot).
    3. User taste preference distributions across catalog dimensions.
    """

    def __init__(self):
        self.user_latent_embeddings: Dict[int, np.ndarray] = {}
        self.item_latent_embeddings: Dict[int, np.ndarray] = {}
        self.user_genre_profiles: Dict[int, np.ndarray] = {}
        self.item_genre_vectors: Dict[int, np.ndarray] = {}
        self.genre_to_idx: Dict[str, int] = {}
        self.idx_to_genre: Dict[int, str] = {}
        self.is_built = False

    def build_representations(
        self,
        movies_df: pd.DataFrame,
        train_df: pd.DataFrame,
        user_factors: np.ndarray,
        item_factors: np.ndarray,
        user_to_idx: Dict[int, int],
        item_to_idx: Dict[int, int],
    ):
        """Constructs explicit and latent representations for all catalog users and items."""
        logger.info("Building multidimensional user and item representations...")

        # 1. Index distinct genres
        all_genres = set()
        for _, row in movies_df.iterrows():
            g_list = row.get("genre_list", [])
            all_genres.update(g_list)
        sorted_genres = sorted(list(all_genres))
        self.genre_to_idx = {g: i for i, g in enumerate(sorted_genres)}
        self.idx_to_genre = {i: g for i, g in enumerate(sorted_genres)}
        n_genres = len(self.genre_to_idx)

        # 2. Build item genre feature vectors
        for _, row in movies_df.iterrows():
            m_id = int(row["movieId"])
            vec = np.zeros(n_genres, dtype=np.float32)
            for g in row.get("genre_list", []):
                if g in self.genre_to_idx:
                    vec[self.genre_to_idx[g]] = 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            self.item_genre_vectors[m_id] = vec

        # 3. Store latent factor embeddings from SVD
        for u_id, u_idx in user_to_idx.items():
            if u_idx < len(user_factors):
                self.user_latent_embeddings[u_id] = user_factors[u_idx].astype(np.float32)

        for m_id, m_idx in item_to_idx.items():
            if m_idx < len(item_factors):
                self.item_latent_embeddings[m_id] = item_factors[m_idx].astype(np.float32)

        # 4. Build user explicit genre taste profiles (rating-weighted genre centroid)
        user_ratings = train_df.groupby("userId")
        for u_id, group in user_ratings:
            profile = np.zeros(n_genres, dtype=np.float32)
            total_weight = 0.0
            for _, row in group.iterrows():
                m_id = int(row["movieId"])
                r = float(row["rating"])
                if m_id in self.item_genre_vectors:
                    weight = max(0.1, r - 2.5)  # give higher weight to positive ratings
                    profile += self.item_genre_vectors[m_id] * weight
                    total_weight += weight
            if total_weight > 0:
                profile = profile / total_weight
            self.user_genre_profiles[int(u_id)] = profile

        self.is_built = True
        logger.info(
            f"Representations successfully constructed: {len(self.user_latent_embeddings)} user latent vectors, "
            f"{len(self.item_latent_embeddings)} item latent vectors, {len(self.item_genre_vectors)} item genre vectors."
        )

    def get_user_latent_vector(self, user_id: int) -> Optional[np.ndarray]:
        return self.user_latent_embeddings.get(user_id)

    def get_item_latent_vector(self, movie_id: int) -> Optional[np.ndarray]:
        return self.item_latent_embeddings.get(movie_id)

    def get_user_genre_profile(self, user_id: int) -> Optional[np.ndarray]:
        return self.user_genre_profiles.get(user_id)

    def get_item_genre_vector(self, movie_id: int) -> Optional[np.ndarray]:
        return self.item_genre_vectors.get(movie_id)

    def compute_content_similarity(self, movie_id1: int, movie_id2: int) -> float:
        """Calculates cosine similarity between two items' genre feature vectors."""
        v1 = self.item_genre_vectors.get(movie_id1)
        v2 = self.item_genre_vectors.get(movie_id2)
        if v1 is None or v2 is None:
            return 0.0
        dot = float(np.dot(v1, v2))
        return max(0.0, dot)

    def compute_latent_similarity(self, movie_id1: int, movie_id2: int) -> float:
        """Calculates cosine similarity in the latent factor embedding space."""
        v1 = self.item_latent_embeddings.get(movie_id1)
        v2 = self.item_latent_embeddings.get(movie_id2)
        if v1 is None or v2 is None:
            return 0.0
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (n1 * n2))

    def find_nearest_items_by_latent(
        self, movie_id: int, top_k: int = 10, exclude_ids: Optional[set] = None
    ) -> List[Tuple[int, float]]:
        """Finds nearest neighbor items in the latent SVD embedding space."""
        target_vec = self.item_latent_embeddings.get(movie_id)
        if target_vec is None:
            return []

        target_norm = np.linalg.norm(target_vec)
        if target_norm == 0:
            return []

        exclude = exclude_ids or set()
        exclude.add(movie_id)

        sims = []
        for other_id, other_vec in self.item_latent_embeddings.items():
            if other_id in exclude:
                continue
            other_norm = np.linalg.norm(other_vec)
            if other_norm > 0:
                cos_sim = float(np.dot(target_vec, other_vec) / (target_norm * other_norm))
                sims.append((other_id, cos_sim))

        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[:top_k]

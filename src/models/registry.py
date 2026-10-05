"""Model registry for managing, training, registering, and retrieving recommendation models."""

from typing import Dict, List, Any, Optional, Type
import pandas as pd

from src.models.base import BaseRecommender
from src.models.popularity import PopularityRecommender
from src.models.collaborative import ItemCollaborativeRecommender
from src.models.matrix_factorization import MatrixFactorizationRecommender
from src.models.hybrid import HybridRecommender
from src.models.representations import UserItemRepresentations
from src.logger import logger


class ModelRegistry:
    """
    Central registry and lifecycle manager for all recommendation models.
    Supports dynamic registration of custom recommendation strategies for future model extensions.
    """

    _strategy_classes: Dict[str, Type[BaseRecommender]] = {}

    def __init__(self):
        self._models: Dict[str, BaseRecommender] = {}
        self.representations = UserItemRepresentations()
        self.is_initialized = False

    @classmethod
    def register_strategy(cls, name: str):
        """Class decorator for registering new recommendation algorithms modularly."""
        def decorator(subclass: Type[BaseRecommender]):
            cls._strategy_classes[name.lower()] = subclass
            return subclass
        return decorator

    def register(self, name: str, model: BaseRecommender):
        """Registers a model instance dynamically."""
        self._models[name.lower()] = model
        logger.info(f"Registered recommendation strategy: '{name}' ({type(model).__name__})")

    def register_default_models(self):
        """Initializes instances of all production models."""
        self.register("popularity", PopularityRecommender())
        self.register("item_collaborative", ItemCollaborativeRecommender())
        self.register("matrix_factorization_svd", MatrixFactorizationRecommender())
        self.register("hybrid", HybridRecommender())

    def fit_all(self, train_df: pd.DataFrame, movies_df: pd.DataFrame):
        """Fits all registered models on training interactions efficiently."""
        logger.info(f"Fitting all registered models ({list(self._models.keys())})...")

        # Fit Popularity
        logger.info("Training model: 'popularity'...")
        pop_model = self._models["popularity"]
        pop_model.fit(train_df, movies_df)

        # Fit Collaborative Filtering
        logger.info("Training model: 'item_collaborative'...")
        cf_model = self._models["item_collaborative"]
        cf_model.fit(train_df, movies_df)

        # Fit Latent Factor SVD
        logger.info("Training model: 'matrix_factorization_svd'...")
        svd_model: MatrixFactorizationRecommender = self._models["matrix_factorization_svd"]
        svd_model.fit(train_df, movies_df)

        # Build Multidimensional User & Item Representations
        self.representations.build_representations(
            movies_df=movies_df,
            train_df=train_df,
            user_factors=svd_model.user_factors,
            item_factors=svd_model.item_factors,
            user_to_idx=svd_model.user_to_idx,
            item_to_idx=svd_model.item_to_idx,
        )

        # Wire pre-fitted submodels directly into Hybrid to avoid redundant refitting
        logger.info("Training model: 'hybrid'...")
        hybrid_model: HybridRecommender = self._models["hybrid"]
        hybrid_model.popularity_model = pop_model
        hybrid_model.cf_model = cf_model
        hybrid_model.svd_model = svd_model
        hybrid_model.representations = self.representations
        hybrid_model.fit_with_prefitted_submodels(train_df, movies_df)

        self.is_initialized = True
        logger.info("All recommendation models fitted and ready for serving.")

    def get_model(self, name: str) -> BaseRecommender:
        """Retrieves a fitted model by name."""
        key = name.lower()
        if key in ["cf", "item_cf", "collaborative"]:
            key = "item_collaborative"
        elif key in ["svd", "mf", "matrix_factorization"]:
            key = "matrix_factorization_svd"

        if key not in self._models:
            raise KeyError(f"Model '{name}' not found. Available models: {list(self._models.keys())}")
        return self._models[key]

    def list_models(self) -> List[Dict[str, Any]]:
        """Returns metadata for all available models."""
        descriptions = {
            "popularity": {
                "name": "Popularity Baseline",
                "type": "Heuristic / Bayesian",
                "description": "Calculates Bayesian dampening weighted ratings. Optimal for cold-start and trending discovery.",
                "strengths": ["Zero cold-start penalty", "Fast O(1) retrieval", "Robust baseline"],
            },
            "item_collaborative": {
                "name": "Item-Item Collaborative Filtering",
                "type": "Memory-based Collaborative Filtering",
                "description": "Computes cosine similarities between item vectors with shrinkage. Transparent 'Because you liked X' explanations.",
                "strengths": ["High explainability", "Captures specific niche affinities", "Strong precision on active users"],
            },
            "matrix_factorization_svd": {
                "name": "Latent Factor Matrix Factorization",
                "type": "Model-based Latent Factor",
                "description": "Decomposes interaction matrix via Truncated SVD into dense user & item latent factors.",
                "strengths": ["Dense representation", "Discovers latent non-linear patterns", "Smooth generalization"],
            },
            "hybrid": {
                "name": "Two-Stage Hybrid Intelligence",
                "type": "Multi-Stage Retrieval & Ranking",
                "description": "Combines candidate generation across CF, SVD, and Genre Affinity with feature-weighted ranking and diversity control.",
                "strengths": ["State-of-the-art NDCG & Recall", "Full explainability", "Diversity re-ranking", "Cold-start resilient"],
            },
        }

        result = []
        for key, model in self._models.items():
            meta = descriptions.get(key, {"name": key, "type": "Custom", "description": "", "strengths": []})
            result.append({
                "id": key,
                "name": meta["name"],
                "type": meta["type"],
                "is_fitted": model.is_fitted,
                "description": meta["description"],
                "strengths": meta["strengths"],
            })
        return result

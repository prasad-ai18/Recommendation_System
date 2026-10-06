"""Configuration management using Pydantic Settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Application Configuration
    APP_NAME: str = "Personalized Recommendation Intelligence Platform"
    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Dataset Paths & URLs
    DATASET_NAME: str = "ml-latest-small"
    DATASET_URL: str = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
    DATA_DIR: str = str(BASE_DIR / "data")
    RAW_DATA_DIR: str = str(BASE_DIR / "data" / "raw")
    PROCESSED_DATA_DIR: str = str(BASE_DIR / "data" / "processed")
    CACHE_DIR: str = str(BASE_DIR / "data" / "cache")

    # Recommendation System Defaults
    DEFAULT_MODEL: str = "hybrid"
    DEFAULT_K: int = 10
    CANDIDATE_POOL_SIZE: int = 80
    MIN_USER_RATINGS: int = 5
    POSITIVE_RATING_THRESHOLD: float = 3.5
    RANDOM_STATE: int = 42

    # Model Hyperparameters
    SVD_N_COMPONENTS: int = 40
    ITEM_SIMILARITY_MIN_SUPPORT: int = 3
    POPULARITY_PRIOR_WEIGHT: float = 0.2

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure directories exist
for path_str in [settings.DATA_DIR, settings.RAW_DATA_DIR, settings.PROCESSED_DATA_DIR, settings.CACHE_DIR]:
    Path(path_str).mkdir(parents=True, exist_ok=True)

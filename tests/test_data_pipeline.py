"""Tests for data preprocessing, cleaning, and temporal split validation."""

import pytest
import pandas as pd
import numpy as np
from src.data.preprocessor import DataPreprocessor


@pytest.fixture
def sample_data():
    movies = pd.DataFrame([
        {"movieId": 1, "title": "Toy Story (1995)", "genres": "Adventure|Animation|Children"},
        {"movieId": 2, "title": "Jumanji (1995)", "genres": "Adventure|Children|Fantasy"},
        {"movieId": 3, "title": "Heat (1995)", "genres": "Action|Crime|Thriller"},
        {"movieId": 4, "title": "Documentary Movie", "genres": "(no genres listed)"},
    ])

    ratings = pd.DataFrame([
        {"userId": 1, "movieId": 1, "rating": 4.0, "timestamp": 1000},
        {"userId": 1, "movieId": 2, "rating": 5.0, "timestamp": 2000},
        {"userId": 1, "movieId": 3, "rating": 3.0, "timestamp": 3000},
        {"userId": 1, "movieId": 1, "rating": 4.5, "timestamp": 4000},  # duplicate, should keep latest
        {"userId": 2, "movieId": 1, "rating": 2.0, "timestamp": 1500},
        {"userId": 2, "movieId": 3, "rating": 5.0, "timestamp": 2500},
        {"userId": 3, "movieId": 999, "rating": 4.0, "timestamp": 1000},  # orphan movie, should be dropped
        {"userId": 3, "movieId": 2, "rating": 6.5, "timestamp": 2000},  # invalid rating > 5.0
    ])
    return movies, ratings


def test_clean_movies(sample_data):
    movies_raw, _ = sample_data
    preprocessor = DataPreprocessor()
    cleaned = preprocessor.clean_movies(movies_raw)

    assert len(cleaned) == 4
    # Year extraction
    assert cleaned.loc[cleaned["movieId"] == 1, "year"].values[0] == 1995
    assert cleaned.loc[cleaned["movieId"] == 1, "clean_title"].values[0] == "Toy Story"
    assert pd.isna(cleaned.loc[cleaned["movieId"] == 4, "year"].values[0])
    # Genre parsing
    g_list = cleaned.loc[cleaned["movieId"] == 1, "genre_list"].values[0]
    assert "Adventure" in g_list and "Animation" in g_list
    assert cleaned.loc[cleaned["movieId"] == 4, "genre_list"].values[0] == []


def test_clean_ratings_and_deduplication(sample_data):
    movies_raw, ratings_raw = sample_data
    preprocessor = DataPreprocessor()
    valid_movie_ids = {1, 2, 3, 4}

    cleaned = preprocessor.clean_ratings(ratings_raw, valid_movie_ids)

    # Orphan 999 and rating 6.5 should be removed
    assert 999 not in cleaned["movieId"].values
    assert (cleaned["rating"] > 5.0).sum() == 0
    # Duplicate (userId=1, movieId=1) should be 1 row with latest rating 4.5
    u1_m1 = cleaned[(cleaned["userId"] == 1) & (cleaned["movieId"] == 1)]
    assert len(u1_m1) == 1
    assert u1_m1["rating"].values[0] == 4.5
    assert u1_m1["timestamp"].values[0] == 4000


def test_bayesian_item_statistics(sample_data):
    movies_raw, ratings_raw = sample_data
    preprocessor = DataPreprocessor()
    cleaned_movies = preprocessor.clean_movies(movies_raw)
    cleaned_ratings = preprocessor.clean_ratings(ratings_raw, set(cleaned_movies["movieId"]))

    stats_df = preprocessor.compute_item_statistics(cleaned_ratings, cleaned_movies)
    assert "rating_count" in stats_df.columns
    assert "rating_mean" in stats_df.columns
    assert "bayesian_score" in stats_df.columns
    assert (stats_df["bayesian_score"] >= 0.5).all()


def test_temporal_split_no_leakage():
    preprocessor = DataPreprocessor()
    # Create user with 10 interactions chronologically ordered
    user_rows = []
    for t in range(10):
        user_rows.append({"userId": 1, "movieId": t + 1, "rating": 4.0, "timestamp": 1000 + t * 100})

    df = pd.DataFrame(user_rows)
    train, val, test = preprocessor.create_temporal_splits(df, min_ratings=5)

    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0

    max_train_ts = train["timestamp"].max()
    min_val_ts = val["timestamp"].min()
    max_val_ts = val["timestamp"].max()
    min_test_ts = test["timestamp"].min()

    # Strict temporal ordering: train <= val <= test
    assert max_train_ts <= min_val_ts
    assert max_val_ts <= min_test_ts

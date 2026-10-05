"""Unit and integration tests for recommender models (Popularity, CF, SVD, Hybrid)."""

import pytest
import pandas as pd
import numpy as np

from src.models.popularity import PopularityRecommender
from src.models.collaborative import ItemCollaborativeRecommender
from src.models.matrix_factorization import MatrixFactorizationRecommender
from src.models.hybrid import HybridRecommender


@pytest.fixture
def mock_dataset():
    movies = pd.DataFrame([
        {"movieId": 1, "title": "Star Wars (1977)", "genres": "Action|Sci-Fi", "genre_list": ["Action", "Sci-Fi"], "rating_mean": 4.5, "rating_count": 100, "bayesian_score": 4.3},
        {"movieId": 2, "title": "The Empire Strikes Back (1980)", "genres": "Action|Sci-Fi", "genre_list": ["Action", "Sci-Fi"], "rating_mean": 4.6, "rating_count": 95, "bayesian_score": 4.4},
        {"movieId": 3, "title": "Titanic (1997)", "genres": "Drama|Romance", "genre_list": ["Drama", "Romance"], "rating_mean": 3.8, "rating_count": 80, "bayesian_score": 3.7},
        {"movieId": 4, "title": "Notebook (2004)", "genres": "Drama|Romance", "genre_list": ["Drama", "Romance"], "rating_mean": 3.7, "rating_count": 60, "bayesian_score": 3.6},
        {"movieId": 5, "title": "Alien (1979)", "genres": "Horror|Sci-Fi", "genre_list": ["Horror", "Sci-Fi"], "rating_mean": 4.2, "rating_count": 70, "bayesian_score": 4.0},
    ])

    ratings = pd.DataFrame([
        # User 1: Sci-Fi lover
        {"userId": 1, "movieId": 1, "rating": 5.0, "timestamp": 100},
        {"userId": 1, "movieId": 2, "rating": 4.5, "timestamp": 200},
        # User 2: Sci-Fi & Alien
        {"userId": 2, "movieId": 1, "rating": 4.5, "timestamp": 110},
        {"userId": 2, "movieId": 5, "rating": 5.0, "timestamp": 210},
        # User 3: Romance lover
        {"userId": 3, "movieId": 3, "rating": 5.0, "timestamp": 120},
        {"userId": 3, "movieId": 4, "rating": 4.5, "timestamp": 220},
        # User 4: Mixed
        {"userId": 4, "movieId": 1, "rating": 4.0, "timestamp": 130},
        {"userId": 4, "movieId": 3, "rating": 3.5, "timestamp": 230},
        {"userId": 4, "movieId": 5, "rating": 4.0, "timestamp": 330},
    ])
    return movies, ratings


def test_popularity_recommender(mock_dataset):
    movies, ratings = mock_dataset
    model = PopularityRecommender(m=5.0)
    model.fit(ratings, movies)

    assert model.is_fitted
    recs = model.recommend(user_id=1, k=3, seen_movie_ids={1})
    assert len(recs) <= 3
    # Excludes seen movie 1
    assert all(r.movie_id != 1 for r in recs)
    # Ranks highest scored remaining items
    assert recs[0].predicted_score >= recs[1].predicted_score


def test_popularity_genre_filter(mock_dataset):
    movies, ratings = mock_dataset
    model = PopularityRecommender()
    model.fit(ratings, movies)

    recs = model.recommend(user_id=1, k=5, genre_filter="Romance")
    for r in recs:
        assert "Romance" in r.genres


def test_item_collaborative_recommender(mock_dataset):
    movies, ratings = mock_dataset
    model = ItemCollaborativeRecommender(top_neighbors=5, min_sim=0.01)
    model.fit(ratings, movies)

    assert model.is_fitted
    # User 1 rated Star Wars 1 and 2 high -> should recommend Alien (movieId 5) which co-occurs with 1
    recs = model.recommend(user_id=1, k=2, seen_movie_ids={1, 2})
    assert len(recs) > 0
    assert all(r.movie_id not in {1, 2} for r in recs)
    assert any("Because you liked" in r.recommendation_signal or "similar" in r.recommendation_signal.lower() for r in recs)


def test_matrix_factorization_svd(mock_dataset):
    movies, ratings = mock_dataset
    model = MatrixFactorizationRecommender(n_components=2)
    model.fit(ratings, movies)

    assert model.is_fitted
    assert model.user_factors.shape[0] == ratings["userId"].nunique()
    assert model.item_factors.shape[0] == ratings["movieId"].nunique()

    recs = model.recommend(user_id=1, k=2)
    assert len(recs) == 2
    assert all(r.predicted_score >= 0.5 for r in recs)


def test_hybrid_recommender_and_online_feedback(mock_dataset):
    movies, ratings = mock_dataset
    model = HybridRecommender(candidate_pool_size=10)
    model.fit(ratings, movies)

    assert model.is_fitted
    # Initial recommendations for User 1
    recs_initial = model.recommend(user_id=1, k=2)
    assert len(recs_initial) == 2

    # Provide online interaction feedback: User 1 rates Titanic (movieId 3) 5.0 stars
    model.add_user_interaction(user_id=1, movie_id=3, rating=5.0, interaction_type="rating")
    assert 3 in model.user_ratings[1]

    # Re-recommend for User 1 with seen movie 3 filtered
    recs_updated = model.recommend(user_id=1, k=3, seen_movie_ids={1, 2, 3})
    assert all(r.movie_id not in {1, 2, 3} for r in recs_updated)


def test_cold_start_fallback(mock_dataset):
    movies, ratings = mock_dataset
    model = HybridRecommender()
    model.fit(ratings, movies)

    # Unknown user 99999
    recs = model.recommend(user_id=99999, k=3)
    assert len(recs) == 3
    assert recs[0].predicted_score >= recs[1].predicted_score

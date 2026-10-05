"""Integration tests for all FastAPI recommendation endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture(scope="module")
def client():
    # Lifespan startup triggers
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "models" in data
    assert len(data["models"]) >= 4
    assert data["active_users_in_memory"] > 0


def test_recommend_endpoint_valid_user(client):
    response = client.get("/recommend/1?k=5&model_type=hybrid")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 1
    assert data["total_returned"] == 5
    assert len(data["recommendations"]) == 5
    assert data["is_cold_start"] is False

    rec = data["recommendations"][0]
    assert "movie_id" in rec
    assert "title" in rec
    assert "predicted_score" in rec
    assert "recommendation_signal" in rec
    assert rec["predicted_score"] >= 0.5


def test_recommend_endpoint_cold_start(client):
    # User 9999 is a new user
    response = client.get("/recommend/9999?k=5&model_type=popularity")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 9999
    assert data["total_returned"] == 5
    assert data["is_cold_start"] is True


def test_recommend_invalid_model(client):
    response = client.get("/recommend/1?model_type=non_existent_model")
    assert response.status_code == 400
    assert "Invalid model" in response.json()["detail"]


def test_movies_endpoint_pagination_and_search(client):
    # First page
    response = client.get("/movies?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert len(data["movies"]) == 10
    assert data["total_count"] > 1000

    # Search title
    search_res = client.get("/movies?query=matrix")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert any("matrix" in m["title"].lower() for m in search_data["movies"])

    # Filter genre
    genre_res = client.get("/movies?genre=Comedy&page_size=5")
    assert genre_res.status_code == 200
    genre_data = genre_res.json()
    for m in genre_data["movies"]:
        assert any(g.lower() == "comedy" for g in m["genres"])


def test_feedback_endpoint(client):
    payload = {
        "user_id": 1,
        "movie_id": 260,  # Star Wars: Episode IV
        "interaction_type": "rating",
        "rating": 5.0,
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["user_id"] == 1
    assert data["movie_id"] == 260


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "popularity" in data["models"]
    assert "hybrid" in data["models"]
    assert "precision@10" in data["models"]["hybrid"]["metrics"]
    assert "catalog_coverage" in data["models"]["hybrid"]["metrics"]


def test_users_and_genres_endpoints(client):
    u_res = client.get("/users")
    assert u_res.status_code == 200
    assert len(u_res.json()["sample_users"]) > 0

    g_res = client.get("/genres")
    assert g_res.status_code == 200
    assert len(g_res.json()["genres"]) >= 15

    m_res = client.get("/models")
    assert m_res.status_code == 200
    assert len(m_res.json()["models"]) >= 4

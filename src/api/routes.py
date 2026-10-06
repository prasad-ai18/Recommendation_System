"""API route definitions implementing all required recommendation endpoints."""

import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Path as FastPath, Depends, Header

from src.config import settings
from src.logger import logger
from src.data import db
from src.api.schemas import (
    RecommendationResponse,
    RecommendationItemResponse,
    MovieListResponse,
    MovieDetailResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    UserProfileResponse,
    ExplainabilityResponse,
    UserRegisterRequest,
    UserLoginRequest,
    AuthUserResponse,
    AuthSessionResponse,
)

router = APIRouter()

# Global state reference injected on startup
_app_state: Dict[str, Any] = {}


def set_app_state(state: Dict[str, Any]):
    global _app_state
    _app_state = state


def get_app_state() -> Dict[str, Any]:
    return _app_state


# ==========================================
# Production Authentication Endpoints
# ==========================================

@router.post("/auth/signup", response_model=AuthSessionResponse, summary="Register New Legitimate User")
def register_user(req: UserRegisterRequest):
    """
    Registers a new legitimate user with validation and PBKDF2 password hashing.
    Starts with a clean profile. No demo accounts or mock data copied.
    """
    try:
        user = db.create_user(
            email=req.email,
            password=req.password,
            name=req.name,
            primary_genre=req.primary_genre or "All",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = db.create_session(user["id"])
    return AuthSessionResponse(
        status="success",
        token=token,
        user=AuthUserResponse(**user),
    )


@router.post("/auth/login", response_model=AuthSessionResponse, summary="Authenticate User")
def login_user(req: UserLoginRequest):
    """
    Authenticates user against hashed credentials. Returns session token.
    Rejects invalid credentials. Zero hardcoded accounts.
    """
    user = db.authenticate_user(email=req.email, password=req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = db.create_session(user["id"])
    return AuthSessionResponse(
        status="success",
        token=token,
        user=AuthUserResponse(**user),
    )


@router.get("/auth/me", response_model=AuthUserResponse, summary="Get Current Authenticated User")
def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Returns the currently authenticated user from Bearer session token.
    Returns 401 if unauthenticated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")

    token = authorization.split("Bearer ", 1)[1].strip()
    user = db.get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.")

    return AuthUserResponse(**user)


@router.post("/auth/logout", summary="Logout and Invalidate Session")
def logout_user(authorization: Optional[str] = Header(None)):
    """
    Destroys active session token on logout.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        db.delete_session(token)
    return {"status": "success", "message": "Logged out successfully."}


@router.get("/recommend/{user_id}", response_model=RecommendationResponse, summary="Get Top-K Recommendations")
def get_recommendations(
    user_id: int = FastPath(..., ge=1, description="Target User ID"),
    k: int = Query(default=10, ge=1, le=50, description="Number of items to recommend"),
    model_type: str = Query(default="hybrid", description="Recommendation algorithm: 'hybrid', 'item_collaborative', 'matrix_factorization_svd', 'popularity'"),
    genre: Optional[str] = Query(default=None, description="Optional genre filter"),
    state: Dict[str, Any] = Depends(get_app_state),
):
    """
    Returns personalized Top-K recommendations for the specified user ID using the selected model.
    Includes transparent explainability signals, score predictions, and metadata.
    """
    start_time = time.perf_counter()
    registry = state.get("registry")
    movies_df = state.get("movies_df")

    if not registry or not registry.is_initialized:
        raise HTTPException(status_code=503, detail="Recommendation engine is still initializing.")

    try:
        model = registry.get_model(model_type)
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{model_type}'. Choose from: 'hybrid', 'item_collaborative', 'matrix_factorization_svd', 'popularity'",
        )

    # Check if user is known
    hybrid_model = registry.get_model("hybrid")
    user_ratings = getattr(hybrid_model, "user_ratings", {}).get(user_id, {})
    is_cold_start = len(user_ratings) == 0

    try:
        recs = model.recommend(user_id=user_id, k=k, genre_filter=genre)
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id} with model {model_type}: {e}")
        raise HTTPException(status_code=500, detail="Recommendation calculation failed.")

    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    rec_items = [
        RecommendationItemResponse(
            movie_id=item.movie_id,
            title=item.title,
            genres=item.genres,
            year=item.year,
            predicted_score=item.predicted_score,
            rating_mean=item.rating_mean,
            rating_count=item.rating_count,
            recommendation_signal=item.recommendation_signal,
            candidate_source=item.candidate_source,
            confidence=item.confidence,
        )
        for item in recs
    ]

    return RecommendationResponse(
        user_id=user_id,
        model_name=model.get_name(),
        total_returned=len(rec_items),
        latency_ms=latency_ms,
        is_cold_start=is_cold_start,
        recommendations=rec_items,
        context={
            "requested_k": k,
            "genre_filter": genre,
            "user_historical_ratings_count": len(user_ratings),
        },
    )


@router.get("/movies", response_model=MovieListResponse, summary="Browse & Search Movie Catalog")
def get_movies(
    query: Optional[str] = Query(default=None, description="Search term for movie title"),
    genre: Optional[str] = Query(default=None, description="Filter by genre"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        default="bayesian_score",
        description="Sort by: 'bayesian_score', 'rating_count', 'rating_mean', 'title', 'year'",
    ),
    state: Dict[str, Any] = Depends(get_app_state),
):
    """
    Search and browse available catalog items with pagination, genre filtering, and sorting.
    """
    movies_df = state.get("movies_df")
    if movies_df is None:
        raise HTTPException(status_code=503, detail="Movie catalog not loaded yet.")

    df = movies_df

    # Filter by text search
    if query:
        q_clean = query.strip().lower()
        df = df[df["title"].str.lower().str.contains(q_clean, na=False)]

    # Filter by genre
    if genre:
        g_clean = genre.strip().lower()
        df = df[df["genre_list"].apply(lambda glist: any(g.lower() == g_clean for g in glist))]

    total_count = len(df)

    # Sort
    valid_sorts = {
        "bayesian_score": ("bayesian_score", False),
        "rating_count": ("rating_count", False),
        "rating_mean": ("rating_mean", False),
        "year": ("year", False),
        "title": ("title", True),
    }
    col, ascending = valid_sorts.get(sort_by, ("bayesian_score", False))
    df = df.sort_values(by=col, ascending=ascending)

    total_pages = max(1, (total_count + page_size - 1) // page_size)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    sliced = df.iloc[start_idx:end_idx]

    items = []
    for _, row in sliced.iterrows():
        items.append(
            MovieDetailResponse(
                movie_id=int(row["movieId"]),
                title=str(row["title"]),
                clean_title=str(row.get("clean_title", row["title"])),
                genres=row.get("genre_list", []),
                year=int(row["year"]) if pd.notna(row.get("year")) else None,
                rating_mean=float(row.get("rating_mean", 0.0)),
                rating_count=int(row.get("rating_count", 0)),
                bayesian_score=float(row.get("bayesian_score", 0.0)),
            )
        )

    return MovieListResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        movies=items,
    )


@router.post("/feedback", response_model=FeedbackResponse, summary="Record User Feedback Event")
def record_feedback(
    payload: FeedbackRequest,
    state: Dict[str, Any] = Depends(get_app_state),
):
    """
    Accepts real-time user feedback events (explicit rating, like, dislike, bookmark)
    and dynamically updates the in-memory user interaction state to immediately influence future recommendations.
    """
    registry = state.get("registry")
    if not registry:
        raise HTTPException(status_code=503, detail="System not ready.")

    # Update hybrid model state
    hybrid_model = registry.get_model("hybrid")
    hybrid_model.add_user_interaction(
        user_id=payload.user_id,
        movie_id=payload.movie_id,
        rating=payload.rating,
        interaction_type=payload.interaction_type,
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    # Persist in SQLite database
    try:
        from src.data.db import record_feedback as db_record_feedback
        db_record_feedback(payload.user_id, payload.movie_id, payload.interaction_type, payload.rating)
    except Exception as e:
        logger.warning(f"Could not persist feedback event to database: {e}")

    # Log interaction
    feedback_log = state.setdefault("feedback_log", [])
    feedback_log.append({
        "user_id": payload.user_id,
        "movie_id": payload.movie_id,
        "type": payload.interaction_type,
        "rating": payload.rating,
        "timestamp": now_iso,
    })

    return FeedbackResponse(
        status="success",
        message=f"Interaction '{payload.interaction_type}' recorded successfully for User {payload.user_id}.",
        user_id=payload.user_id,
        movie_id=payload.movie_id,
        interaction_type=payload.interaction_type,
        updated_at=now_iso,
    )


@router.get("/metrics", summary="Get Current Offline Evaluation Metrics")
def get_metrics(state: Dict[str, Any] = Depends(get_app_state)):
    """
    Returns verified offline evaluation metrics calculated from the held-out test split.
    Reports Precision@K, Recall@K, NDCG@K, HitRate@K, and Catalog Coverage across all models.
    """
    metrics = state.get("evaluation_metrics")
    if not metrics:
        evaluator = state.get("evaluator")
        if evaluator:
            metrics = evaluator.load_cached_metrics()

    if not metrics:
        raise HTTPException(status_code=503, detail="Evaluation metrics not computed yet.")

    return metrics


@router.get("/health", response_model=HealthResponse, summary="Service Health & Diagnostic Status")
def get_health(state: Dict[str, Any] = Depends(get_app_state)):
    """
    Returns service health, loaded models, dataset statistics, and memory uptime.
    """
    registry = state.get("registry")
    stats = state.get("stats", {})
    start_time = state.get("start_time", time.time())
    models_list = [m["id"] for m in registry.list_models()] if registry else []

    hybrid_model = registry.get_model("hybrid") if registry else None
    active_users = len(getattr(hybrid_model, "user_ratings", {})) if hybrid_model else 0

    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        environment=settings.APP_ENV,
        version="1.0.0",
        dataset=stats,
        models=models_list,
        active_users_in_memory=active_users,
        uptime_seconds=round(time.time() - start_time, 1),
    )


@router.get("/users", summary="List Sample Users For Testing")
def get_sample_users(state: Dict[str, Any] = Depends(get_app_state)):
    """
    Returns a curated set of sample users with diverse taste profiles to enable easy testing in the UI.
    """
    sample_users = state.get("sample_users", [])
    return {"sample_users": sample_users}


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse, summary="Get User Taste Profile")
def get_user_profile(
    user_id: int = FastPath(..., ge=1),
    state: Dict[str, Any] = Depends(get_app_state),
):
    """
    Retrieves the active user's rating history, top genres, and rated movies.
    """
    registry = state.get("registry")
    movie_meta = getattr(registry.get_model("popularity"), "movie_meta", {}) if registry else {}
    hybrid_model = registry.get_model("hybrid") if registry else None

    user_ratings = dict(getattr(hybrid_model, "user_ratings", {}).get(user_id, {}))
    affinities = dict(getattr(hybrid_model, "user_genre_affinities", {}).get(user_id, {}))

    # Merge persisted database ratings
    try:
        from src.data.db import get_user_ratings as db_get_user_ratings
        db_ratings = db_get_user_ratings(user_id)
        if db_ratings:
            user_ratings.update(db_ratings)
    except Exception as e:
        logger.warning(f"Could not load database ratings for user {user_id}: {e}")

    ratings_count = len(user_ratings)
    avg_rating = round(float(sum(user_ratings.values()) / ratings_count), 2) if ratings_count > 0 else 0.0

    # Top genres
    sorted_genres = sorted(affinities.items(), key=lambda x: x[1], reverse=True)[:5]
    top_genres = [{"genre": g, "affinity_score": round(score, 2)} for g, score in sorted_genres]

    # Recent / Top ratings
    top_user_movies = sorted(user_ratings.items(), key=lambda x: x[1], reverse=True)[:10]
    recent_ratings = []
    for m_id, r in top_user_movies:
        meta = movie_meta.get(m_id, {})
        recent_ratings.append({
            "movie_id": m_id,
            "title": meta.get("title", f"Movie {m_id}"),
            "rating": r,
            "genres": meta.get("genres", []),
            "year": meta.get("year"),
        })

    return UserProfileResponse(
        user_id=user_id,
        ratings_count=ratings_count,
        average_rating=avg_rating,
        top_genres=top_genres,
        recent_ratings=recent_ratings,
    )


@router.get("/genres", summary="List All Catalog Genres")
def get_genres(state: Dict[str, Any] = Depends(get_app_state)):
    stats = state.get("stats", {})
    return {"genres": stats.get("genres", [])}


@router.get("/models", summary="List Available Recommendation Models")
def get_models(state: Dict[str, Any] = Depends(get_app_state)):
    registry = state.get("registry")
    if not registry:
        raise HTTPException(status_code=503, detail="Models not loaded.")
    return {"models": registry.list_models()}


@router.get("/pipeline/stats", summary="Get Pipeline Statistics")
def get_pipeline_stats(state: Dict[str, Any] = Depends(get_app_state)):
    feedback_log = state.get("feedback_log", [])
    stats = state.get("stats", {})
    return {
        "dataset_stats": stats,
        "live_feedback_events_count": len(feedback_log),
        "recent_feedback_events": feedback_log[-10:],
    }

"""FastAPI application factory, lifespan management, middleware, and exception handling."""

import os
import time
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Any, List
from collections import defaultdict
import pandas as pd

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings, BASE_DIR
from src.logger import logger
from src.data.preprocessor import DataPreprocessor
from src.data.loader import DataLoader
from src.models.registry import ModelRegistry
from src.evaluation.evaluator import OfflineEvaluator
from src.api.routes import router as api_router, set_app_state


def create_sample_users(train_df: pd.DataFrame, movies_df: pd.DataFrame, count: int = 8) -> List[Dict[str, Any]]:
    """Identifies representative users with rich rating histories and distinct genre tastes."""
    # Map movies to genres
    movie_to_genres = {}
    for _, row in movies_df.iterrows():
        movie_to_genres[int(row["movieId"])] = row.get("genre_list", [])

    user_genre_counts = defaultdict(lambda: defaultdict(int))
    user_rating_counts = defaultdict(int)

    for _, row in train_df.iterrows():
        u = int(row["userId"])
        m = int(row["movieId"])
        r = float(row["rating"])
        if r >= 3.5:
            user_rating_counts[u] += 1
            for g in movie_to_genres.get(m, []):
                user_genre_counts[u][g] += 1

    sample_list = []
    # Pick users with rich profiles
    active_users = sorted(user_rating_counts.keys(), key=lambda u: user_rating_counts[u], reverse=True)

    target_genres = ["Action", "Sci-Fi", "Drama", "Comedy", "Thriller", "Animation", "Romance", "Crime"]
    used_users = set()

    for genre in target_genres:
        best_u = None
        best_count = 0
        for u in active_users:
            if u in used_users:
                continue
            cnt = user_genre_counts[u].get(genre, 0)
            if cnt > best_count and user_rating_counts[u] >= 25:
                best_count = cnt
                best_u = u

        if best_u:
            used_users.add(best_u)
            top_genre_list = sorted(user_genre_counts[best_u].items(), key=lambda x: x[1], reverse=True)[:3]
            sample_list.append({
                "user_id": best_u,
                "label": f"User {best_u} ({genre} Enthusiast)",
                "ratings_count": user_rating_counts[best_u],
                "primary_genre": genre,
                "top_genres": [g[0] for g in top_genre_list],
            })

    # Add a cold-start user
    sample_list.append({
        "user_id": 9999,
        "label": "User 9999 (New User - Cold Start)",
        "ratings_count": 0,
        "primary_genre": "General",
        "top_genres": [],
    })

    return sample_list


from src.data.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes models, database, and datasets on server startup."""
    logger.info("Initializing Recommendation Intelligence Platform...")
    start_time = time.time()

    # 0. Initialize SQLite production database
    init_db()

    # 1. Ensure data is loaded and preprocessed
    loader = DataLoader()
    preprocessor = DataPreprocessor()
    try:
        data = preprocessor.load_processed()
    except Exception as e:
        logger.info(f"Processed dataset not ready ({e}), acquiring raw data and preprocessing...")
        ratings_df, movies_df = loader.load_raw_data()
        preprocessor = DataPreprocessor()
        preprocessor.process_and_save(ratings_df, movies_df)
        data = preprocessor.load_processed()

    # 2. Initialize and fit recommendation models
    registry = ModelRegistry()
    registry.register_default_models()
    registry.fit_all(data["train_df"], data["movies_df"])

    # 3. Load or compute offline evaluation metrics
    evaluator = OfflineEvaluator()
    cached_metrics = evaluator.load_cached_metrics()
    if not cached_metrics:
        logger.info("No cached evaluation metrics found. Computing offline evaluation...")
        cached_metrics = evaluator.evaluate_all_models(
            registry=registry,
            test_df=data["test_df"],
            total_catalog_items=len(data["movies_df"]),
            max_eval_users=80,
        )

    # 4. Generate sample user profiles for UI testing
    sample_users = create_sample_users(data["train_df"], data["movies_df"])

    app_state: Dict[str, Any] = {
        "registry": registry,
        "evaluator": evaluator,
        "evaluation_metrics": cached_metrics,
        "movies_df": data["movies_df"],
        "train_df": data["train_df"],
        "test_df": data["test_df"],
        "stats": data["stats"],
        "sample_users": sample_users,
        "start_time": start_time,
        "feedback_log": [],
    }

    set_app_state(app_state)
    logger.info("Recommendation Platform ready for live traffic.")

    yield

    logger.info("Shutting down Recommendation Platform.")


def create_app() -> FastAPI:
    """Creates configured FastAPI instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Production-grade Personalized Recommendation Intelligence Platform with multi-stage retrieval, ranking, and explainability.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Secure Exception Handlers (never expose internal stack traces per SOP)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An internal error occurred while processing the recommendation request.",
                "path": request.url.path,
            },
        )

    # Include REST API router
    app.include_router(api_router, prefix="/api")
    # Also include endpoints directly on root per SOP requirements (e.g. GET /recommend/{user_id}, GET /movies, GET /metrics, GET /health)
    app.include_router(api_router)

    # Static frontend assets
    frontend_dir = BASE_DIR / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_index():
            index_path = frontend_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return JSONResponse(content={"status": "Recommendation API active", "docs": "/docs"})

    return app


app = create_app()

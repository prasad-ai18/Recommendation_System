"""Pydantic schemas for the FastAPI REST API."""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class RecommendationItemResponse(BaseModel):
    movie_id: int = Field(..., description="Unique movie identifier")
    title: str = Field(..., description="Movie title")
    genres: List[str] = Field(default_factory=list, description="Movie genres")
    year: Optional[int] = Field(None, description="Release year")
    predicted_score: float = Field(..., description="Predicted score on 1-5 rating scale")
    rating_mean: float = Field(0.0, description="Catalog average rating")
    rating_count: int = Field(0, description="Total ratings count")
    recommendation_signal: str = Field(..., description="Transparent explainability signal")
    candidate_source: str = Field(..., description="Source retrieval channel")
    confidence: float = Field(..., description="Confidence score [0, 1]")


class RecommendationResponse(BaseModel):
    user_id: int
    model_name: str
    total_returned: int
    latency_ms: float
    is_cold_start: bool
    recommendations: List[RecommendationItemResponse]
    context: Dict[str, Any] = Field(default_factory=dict)


class MovieDetailResponse(BaseModel):
    movie_id: int
    title: str
    clean_title: str
    genres: List[str]
    year: Optional[int] = None
    rating_mean: float
    rating_count: int
    bayesian_score: float


class MovieListResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    total_pages: int
    movies: List[MovieDetailResponse]


class FeedbackRequest(BaseModel):
    user_id: int = Field(..., ge=1, description="Target user ID")
    movie_id: int = Field(..., ge=1, description="Target movie ID")
    interaction_type: Literal["rating", "click", "bookmark", "like", "dislike"] = Field(
        default="rating", description="Event type"
    )
    rating: Optional[float] = Field(None, ge=0.5, le=5.0, description="Rating if explicit")


class FeedbackResponse(BaseModel):
    status: str = "success"
    message: str
    user_id: int
    movie_id: int
    interaction_type: str
    updated_at: str


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str
    environment: str
    version: str
    dataset: Dict[str, Any]
    models: List[str]
    active_users_in_memory: int
    uptime_seconds: float


class UserProfileResponse(BaseModel):
    user_id: int
    ratings_count: int
    average_rating: float
    top_genres: List[Dict[str, Any]]
    recent_ratings: List[Dict[str, Any]]


class ExplainabilityResponse(BaseModel):
    user_id: int
    movie_id: int
    title: str
    genres: List[str]
    predicted_score: float
    score_breakdown: Dict[str, float]
    primary_signal: str
    similar_rated_seeds: List[Dict[str, Any]]


class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=60, description="User full name or display handle")
    email: str = Field(..., min_length=5, max_length=120, description="Valid email address")
    password: str = Field(..., min_length=6, max_length=100, description="Account password (min 6 chars)")
    primary_genre: Optional[str] = Field("All", description="Preferred starter movie genre")


class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120, description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class AuthUserResponse(BaseModel):
    id: int
    email: str
    name: str
    primary_genre: str
    role: str
    created_at: str
    ratings_count: int = 0


class AuthSessionResponse(BaseModel):
    status: str = "success"
    token: str
    user: AuthUserResponse


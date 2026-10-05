"""Data schemas and Pydantic validation models."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class RatingSchema(BaseModel):
    user_id: int = Field(..., alias="userId", ge=1, description="Unique user identifier")
    movie_id: int = Field(..., alias="movieId", ge=1, description="Unique movie identifier")
    rating: float = Field(..., ge=0.5, le=5.0, description="Explicit rating from 0.5 to 5.0")
    timestamp: int = Field(..., ge=0, description="Unix timestamp of interaction")

    model_config = ConfigDict(populate_by_name=True)


class MovieSchema(BaseModel):
    movie_id: int = Field(..., alias="movieId", ge=1)
    title: str = Field(..., min_length=1)
    genres: str = Field(default="(no genres listed)")
    year: Optional[int] = None
    clean_title: Optional[str] = None
    genre_list: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class FeedbackEvent(BaseModel):
    user_id: int = Field(..., ge=1, description="User performing the action")
    movie_id: int = Field(..., ge=1, description="Target movie ID")
    rating: Optional[float] = Field(None, ge=0.5, le=5.0, description="Rating if explicit")
    interaction_type: Literal["rating", "click", "bookmark", "like", "dislike"] = Field(
        default="rating", description="Interaction event type"
    )
    timestamp: Optional[int] = Field(default=None, description="Event timestamp")

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v, info):
        # If interaction_type is rating, rating should typically be provided
        return v

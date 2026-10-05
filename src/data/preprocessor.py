"""DataPreprocessor handles cleaning, metadata enrichment, item stats, and leak-free temporal splitting."""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd

from src.config import settings
from src.logger import logger


class DataPreprocessor:
    """Cleans movie and interaction data, computes metrics, and produces temporal splits."""

    def __init__(self, processed_dir: str = settings.PROCESSED_DATA_DIR):
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.year_pattern = re.compile(r"\((\d{4})\)\s*$")

    def clean_movies(self, movies_df: pd.DataFrame) -> pd.DataFrame:
        """Parses titles, extracts release years, and creates clean genre lists."""
        logger.info("Cleaning movies metadata...")
        df = movies_df.copy()

        # Deduplicate on movieId
        df = df.drop_duplicates(subset=["movieId"]).reset_index(drop=True)

        def extract_year_and_title(title_raw: str) -> Tuple[str, Optional[int]]:
            title_str = str(title_raw).strip()
            match = self.year_pattern.search(title_str)
            if match:
                year = int(match.group(1))
                clean_title = title_str[:match.start()].strip()
            else:
                year = None
                clean_title = title_str
            return clean_title, year

        parsed = [extract_year_and_title(t) for t in df["title"]]
        df["clean_title"] = [p[0] for p in parsed]
        df["year"] = [p[1] for p in parsed]

        # Process genres
        df["genres"] = df["genres"].fillna("(no genres listed)")
        df["genre_list"] = df["genres"].apply(
            lambda g: [] if g == "(no genres listed)" else [x.strip() for x in g.split("|") if x.strip()]
        )

        return df

    def clean_ratings(self, ratings_df: pd.DataFrame, valid_movie_ids: set) -> pd.DataFrame:
        """Validates rating bounds, removes orphaned items, and deduplicates ratings."""
        logger.info("Validating and cleaning ratings data...")
        df = ratings_df.copy()

        # Basic type conversion and filtering
        df["userId"] = df["userId"].astype(int)
        df["movieId"] = df["movieId"].astype(int)
        df["rating"] = df["rating"].astype(float)
        df["timestamp"] = df["timestamp"].astype(int)

        # Drop invalid bounds
        initial_len = len(df)
        df = df[(df["rating"] >= 0.5) & (df["rating"] <= 5.0)]
        df = df[df["movieId"].isin(valid_movie_ids)]

        # Drop duplicates: if user rated movie multiple times, keep latest timestamp
        df = df.sort_values(by=["userId", "movieId", "timestamp"]).drop_duplicates(
            subset=["userId", "movieId"], keep="last"
        )

        logger.info(f"Cleaned ratings: {len(df):,} valid interactions (filtered out {initial_len - len(df):,}).")
        return df.reset_index(drop=True)

    def compute_item_statistics(self, ratings_df: pd.DataFrame, movies_df: pd.DataFrame) -> pd.DataFrame:
        """Computes vote count, mean rating, and Bayesian dampening weighted score."""
        logger.info("Computing item statistics and Bayesian popularity scores...")
        agg = ratings_df.groupby("movieId")["rating"].agg(
            rating_count="count",
            rating_mean="mean",
        ).reset_index()

        df_merged = pd.merge(movies_df, agg, on="movieId", how="left")
        df_merged["rating_count"] = df_merged["rating_count"].fillna(0).astype(int)
        df_merged["rating_mean"] = df_merged["rating_mean"].fillna(0.0).round(2)

        # Global average rating across all ratings
        C = float(ratings_df["rating"].mean())
        # Minimum ratings threshold (m-estimate)
        m = 10.0

        # Bayesian Weighted Rating formula:
        # WR = (v / (v + m)) * R + (m / (v + m)) * C
        v = df_merged["rating_count"]
        R = df_merged["rating_mean"]
        df_merged["bayesian_score"] = np.where(
            v > 0,
            (v / (v + m)) * R + (m / (v + m)) * C,
            C * 0.5  # fallback for unrated items
        ).round(3)

        return df_merged

    def create_temporal_splits(
        self, ratings_df: pd.DataFrame, min_ratings: int = settings.MIN_USER_RATINGS
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Creates reproducible temporal train, validation, and test splits.
        For each user with at least min_ratings, their ratings are chronologically sorted
        by timestamp:
        - First 80% interactions -> Train
        - Next 10% interactions -> Validation
        - Last 10% interactions -> Held-out Test
        This strictly prevents future temporal leakage during offline evaluation.
        """
        logger.info("Generating leak-free chronological train/val/test splits...")
        train_rows = []
        val_rows = []
        test_rows = []

        # Sort chronologically
        sorted_df = ratings_df.sort_values(by=["userId", "timestamp"]).reset_index(drop=True)

        for user_id, user_group in sorted_df.groupby("userId"):
            n_ratings = len(user_group)
            if n_ratings < min_ratings:
                # Cold/low-activity users remain entirely in train
                train_rows.append(user_group)
            else:
                train_end = int(n_ratings * 0.8)
                val_end = int(n_ratings * 0.9)
                # Ensure at least 1 item in test if n_ratings >= min_ratings
                if val_end >= n_ratings:
                    val_end = n_ratings - 1
                if train_end >= val_end:
                    train_end = max(1, val_end - 1)

                train_rows.append(user_group.iloc[:train_end])
                val_rows.append(user_group.iloc[train_end:val_end])
                test_rows.append(user_group.iloc[val_end:])

        train_df = pd.concat(train_rows, ignore_index=True)
        val_df = pd.concat(val_rows, ignore_index=True) if val_rows else pd.DataFrame(columns=ratings_df.columns)
        test_df = pd.concat(test_rows, ignore_index=True) if test_rows else pd.DataFrame(columns=ratings_df.columns)

        logger.info(
            f"Split completed: Train={len(train_df):,} ({len(train_df)/len(ratings_df):.1%}), "
            f"Val={len(val_df):,} ({len(val_df)/len(ratings_df):.1%}), "
            f"Test={len(test_df):,} ({len(test_df)/len(ratings_df):.1%})"
        )
        return train_df, val_df, test_df

    def process_and_save(
        self, ratings_df: pd.DataFrame, movies_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Executes full preprocessing pipeline and saves artifacts."""
        cleaned_movies = self.clean_movies(movies_df)
        valid_movie_ids = set(cleaned_movies["movieId"].unique())
        cleaned_ratings = self.clean_ratings(ratings_df, valid_movie_ids)
        enriched_movies = self.compute_item_statistics(cleaned_ratings, cleaned_movies)

        train_df, val_df, test_df = self.create_temporal_splits(cleaned_ratings)

        # Collect distinct genres
        all_genres = sorted(list({g for genres in enriched_movies["genre_list"] for g in genres}))

        # Save processed files
        train_path = self.processed_dir / "train.csv"
        val_path = self.processed_dir / "val.csv"
        test_path = self.processed_dir / "test.csv"
        movies_path = self.processed_dir / "movies.csv"
        stats_path = self.processed_dir / "dataset_stats.json"

        train_df.to_csv(train_path, index=False)
        val_df.to_csv(val_path, index=False)
        test_df.to_csv(test_path, index=False)
        # Store genre_list as pipe-separated in CSV for easy parsing
        enriched_movies.to_csv(movies_path, index=False)

        stats = {
            "total_users": int(cleaned_ratings["userId"].nunique()),
            "total_movies": int(len(enriched_movies)),
            "total_ratings": int(len(cleaned_ratings)),
            "train_ratings": int(len(train_df)),
            "val_ratings": int(len(val_df)),
            "test_ratings": int(len(test_df)),
            "global_rating_mean": round(float(cleaned_ratings["rating"].mean()), 3),
            "genres_count": len(all_genres),
            "genres": all_genres,
        }

        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        logger.info(f"Processed artifacts saved successfully to {self.processed_dir}")
        return {
            "train_df": train_df,
            "val_df": val_df,
            "test_df": test_df,
            "movies_df": enriched_movies,
            "stats": stats,
        }

    def load_processed(self) -> Dict[str, Any]:
        """Loads already-processed data files if available."""
        train_path = self.processed_dir / "train.csv"
        val_path = self.processed_dir / "val.csv"
        test_path = self.processed_dir / "test.csv"
        movies_path = self.processed_dir / "movies.csv"
        stats_path = self.processed_dir / "dataset_stats.json"

        if not all(p.exists() for p in [train_path, val_path, test_path, movies_path, stats_path]):
            raise FileNotFoundError("Processed files not found. Run process_and_save() first.")

        train_df = pd.read_csv(train_path)
        val_df = pd.read_csv(val_path)
        test_df = pd.read_csv(test_path)
        movies_df = pd.read_csv(movies_path)

        # Parse genre_list
        def parse_genres(g_str: Any) -> List[str]:
            if pd.isna(g_str) or g_str == "(no genres listed)":
                return []
            if isinstance(g_str, str):
                # If stored as string representation of list or pipe
                if g_str.startswith("[") and g_str.endswith("]"):
                    try:
                        import ast
                        return ast.literal_eval(g_str)
                    except Exception:
                        pass
                return [x.strip() for x in g_str.split("|") if x.strip()]
            return []

        movies_df["genre_list"] = movies_df["genres"].apply(parse_genres)

        with open(stats_path, "r", encoding="utf-8") as f:
            stats = json.load(f)

        return {
            "train_df": train_df,
            "val_df": val_df,
            "test_df": test_df,
            "movies_df": movies_df,
            "stats": stats,
        }

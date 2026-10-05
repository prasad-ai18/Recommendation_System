"""DataLoader handles automated downloading, extraction, and verification of MovieLens data."""

import os
import zipfile
from pathlib import Path
from typing import Tuple
import pandas as pd
import requests
import certifi

from src.config import settings
from src.logger import logger


class DataLoader:
    """Manages raw dataset acquisition, caching, and validation."""

    def __init__(self, raw_dir: str = settings.RAW_DATA_DIR, dataset_url: str = settings.DATASET_URL):
        self.raw_dir = Path(raw_dir)
        self.dataset_url = dataset_url
        self.dataset_name = settings.DATASET_NAME
        self.extracted_path = self.raw_dir / self.dataset_name

    def ensure_dataset(self) -> Path:
        """Downloads and extracts the dataset if not already present."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        ratings_file = self.extracted_path / "ratings.csv"
        movies_file = self.extracted_path / "movies.csv"

        if ratings_file.exists() and movies_file.exists():
            logger.info(f"Dataset already present at: {self.extracted_path}")
            return self.extracted_path

        zip_dest = self.raw_dir / f"{self.dataset_name}.zip"
        logger.info(f"Downloading MovieLens dataset from {self.dataset_url}...")

        try:
            # First attempt with certifi verification
            response = requests.get(self.dataset_url, verify=certifi.where(), timeout=60, stream=True)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"Certifi download failed ({e}), attempting fallback download...")
            response = requests.get(self.dataset_url, verify=False, timeout=60, stream=True)
            response.raise_for_status()

        with open(zip_dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded {zip_dest.stat().st_size:,} bytes. Extracting archive...")
        with zipfile.ZipFile(zip_dest, "r") as zip_ref:
            zip_ref.extractall(self.raw_dir)

        if zip_dest.exists():
            zip_dest.unlink()

        logger.info(f"Dataset extracted successfully to: {self.extracted_path}")
        return self.extracted_path

    def load_raw_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Loads and returns raw ratings and movies DataFrames."""
        dataset_path = self.ensure_dataset()
        ratings_file = dataset_path / "ratings.csv"
        movies_file = dataset_path / "movies.csv"

        if not ratings_file.exists() or not movies_file.exists():
            raise FileNotFoundError(f"Missing required CSVs in {dataset_path}")

        logger.info(f"Reading {ratings_file} and {movies_file}...")
        ratings_df = pd.read_csv(ratings_file)
        movies_df = pd.read_csv(movies_file)

        logger.info(
            f"Loaded {len(ratings_df):,} ratings ({ratings_df['userId'].nunique():,} unique users, "
            f"{ratings_df['movieId'].nunique():,} unique movies) and {len(movies_df):,} movies metadata."
        )
        return ratings_df, movies_df

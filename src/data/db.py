"""Database persistence layer using SQLite.
Stores legitimate users, secure credentials (PBKDF2-HMAC-SHA256), active sessions, and user ratings/feedback.
Zero demo or mock users seeded.
"""

import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.config import settings
from src.logger import logger

DB_PATH = Path(settings.DATA_DIR) / "app.db"


def get_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite application database with WAL mode."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initializes the production database schema. No demo or mock records seeded."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                name TEXT NOT NULL,
                primary_genre TEXT DEFAULT 'All',
                role TEXT DEFAULT 'Member',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                movie_id INTEGER NOT NULL,
                interaction_type TEXT NOT NULL,
                rating REAL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON user_feedback(user_id);
        """)
        # Ensure registered production users start at ID 10001+ to cleanly isolate from MovieLens dataset IDs (1..610)
        cursor = conn.cursor()
        cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = 'users'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('users', 10000)")
        elif row["seq"] < 10000:
            cursor.execute("UPDATE sqlite_sequence SET seq = 10000 WHERE name = 'users'")
        conn.commit()
    logger.info(f"Initialized application database at {DB_PATH}")


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a unique cryptographic salt."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return dk.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Secure constant-time verification of password against stored hash."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return secrets.compare_digest(dk.hex(), password_hash)


def create_user(email: str, password: str, name: str, primary_genre: str = "All") -> Dict[str, Any]:
    """Creates a new legitimate user record with securely hashed credentials."""
    clean_email = email.strip().lower()
    clean_name = name.strip()
    pwd_hash, salt = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash, salt, name, primary_genre, role, created_at)
                VALUES (?, ?, ?, ?, ?, 'Member', ?)
                """,
                (clean_email, pwd_hash, salt, clean_name, primary_genre, now),
            )
            user_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("An account with this email address already exists.")

    return {
        "id": user_id,
        "email": clean_email,
        "name": clean_name,
        "primary_genre": primary_genre,
        "role": "Member",
        "created_at": now,
        "ratings_count": 0,
    }


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates user credentials against the database."""
    clean_email = email.strip().lower()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
        if not row:
            return None

        if not verify_password(password, row["password_hash"], row["salt"]):
            return None

        # Count ratings
        ratings_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM user_feedback WHERE user_id = ? AND rating IS NOT NULL",
            (row["id"],),
        ).fetchone()["cnt"]

    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "primary_genre": row["primary_genre"],
        "role": row["role"],
        "created_at": row["created_at"],
        "ratings_count": ratings_count,
    }


def create_session(user_id: int, duration_days: int = 7) -> str:
    """Creates a new authenticated session token."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=duration_days)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_id, now.isoformat(), expires.isoformat()),
        )
        conn.commit()

    return token


def get_user_by_session(token: str) -> Optional[Dict[str, Any]]:
    """Validates session token and returns current authenticated user if not expired."""
    if not token:
        return None

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        query = """
            SELECT u.id, u.email, u.name, u.primary_genre, u.role, u.created_at, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """
        row = conn.execute(query, (token, now)).fetchone()
        if not row:
            return None

        ratings_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM user_feedback WHERE user_id = ? AND rating IS NOT NULL",
            (row["id"],),
        ).fetchone()["cnt"]

    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "primary_genre": row["primary_genre"],
        "role": row["role"],
        "created_at": row["created_at"],
        "ratings_count": ratings_count,
    }


def delete_session(token: str):
    """Deletes an active session on logout."""
    if not token:
        return
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a user profile by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, email, name, primary_genre, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None

        ratings_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM user_feedback WHERE user_id = ? AND rating IS NOT NULL",
            (user_id,),
        ).fetchone()["cnt"]

    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "primary_genre": row["primary_genre"],
        "role": row["role"],
        "created_at": row["created_at"],
        "ratings_count": ratings_count,
    }


def record_feedback(user_id: int, movie_id: int, interaction_type: str, rating: Optional[float] = None):
    """Persists real interaction feedback for the user in the database."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_feedback (user_id, movie_id, interaction_type, rating, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, movie_id, interaction_type, rating, now),
        )
        conn.commit()


def get_user_ratings(user_id: int) -> Dict[int, float]:
    """Retrieves all explicit ratings recorded by this user."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT movie_id, rating
            FROM user_feedback
            WHERE user_id = ? AND rating IS NOT NULL
            ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()

    return {int(row["movie_id"]): float(row["rating"]) for row in rows}


def get_user_feedback_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves chronological feedback history for a user."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT movie_id, interaction_type, rating, created_at
            FROM user_feedback
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    return [
        {
            "movie_id": row["movie_id"],
            "type": row["interaction_type"],
            "rating": row["rating"],
            "time": row["created_at"],
        }
        for row in rows
    ]

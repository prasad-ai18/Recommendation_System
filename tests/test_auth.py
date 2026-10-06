import pytest
from fastapi.testclient import TestClient
from src.api.app import app
import time
from src.data.db import init_db, get_connection


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_auth_full_lifecycle(client):
    # 1. Unauthenticated /api/auth/me fails
    res = client.get("/api/auth/me")
    assert res.status_code == 401

    test_email = f"prod_{int(time.time()*1000)}@cinema.ai"

    # 2. Register a new user
    signup_payload = {
        "name": "Production User",
        "email": test_email,
        "password": "SecurePassword123!",
    }
    signup_res = client.post("/api/auth/signup", json=signup_payload)
    assert signup_res.status_code == 200, signup_res.text
    signup_data = signup_res.json()
    assert "token" in signup_data
    assert signup_data["user"]["name"] == "Production User"
    assert signup_data["user"]["email"] == test_email
    user_id = signup_data["user"]["id"]
    token = signup_data["token"]

    # 3. Verify password is securely hashed in SQLite, never plaintext
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, salt FROM users WHERE email = ?", (test_email,))
        row = cursor.fetchone()
        assert row is not None
        assert row["password_hash"] != "SecurePassword123!"
        assert len(row["salt"]) == 32
        assert len(row["password_hash"]) == 64

    # 4. Duplicate registration fails
    dup_res = client.post("/api/auth/signup", json=signup_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()

    # 5. Invalid login fails
    bad_login = client.post("/api/auth/login", json={"email": test_email, "password": "WrongPassword"})
    assert bad_login.status_code == 401

    # 6. Correct login succeeds
    good_login = client.post("/api/auth/login", json={"email": test_email, "password": "SecurePassword123!"})
    assert good_login.status_code == 200
    login_data = good_login.json()
    assert "token" in login_data
    new_token = login_data["token"]

    # 7. Authenticated /me succeeds
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == test_email

    # 8. User starts with clean profile (0 demo progress, 0 demo ratings)
    profile_res = client.get(f"/api/users/{user_id}/profile")
    assert profile_res.status_code == 200
    profile_data = profile_res.json()
    assert profile_data["ratings_count"] == 0
    assert profile_data["average_rating"] == 0.0

    # 9. Logout terminates session
    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {new_token}"})
    assert logout_res.status_code == 200

    # 10. Post-logout /me fails
    post_logout_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert post_logout_me.status_code == 401

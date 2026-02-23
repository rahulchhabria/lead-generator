"""Integration tests for background jobs API routes: list and detail."""

import uuid

import pytest

from src.database import Database
from src.web.auth import create_access_token
from src.web.background import job_manager


def _setup_two_users(db_path):
    """Create two users on separate teams. Returns (user_a, user_b) dicts."""
    db = Database(db_path)

    team_a_id = str(uuid.uuid4())
    user_a_id = str(uuid.uuid4())
    db.create_team(team_a_id, "TeamA", "teama.com")
    user_a = db.create_user(user_a_id, team_a_id, "alice@teama.com", "Alice", role="admin")

    team_b_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())
    db.create_team(team_b_id, "TeamB", "teamb.com")
    user_b = db.create_user(user_b_id, team_b_id, "bob@teamb.com", "Bob", role="admin")

    db.close()
    return user_a, user_b


def _headers(user):
    """Create auth headers for a user dict."""
    token = create_access_token(user["id"], user["email"], user["team_id"], user["role"])
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Job auth and scoping
# ---------------------------------------------------------------------------
class TestJobAuth:
    def test_list_own_jobs_only(self, app_client):
        """User A should only see their own jobs, not user B's."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        # Create jobs for each user
        job_a1 = job_manager.create_job("Job A1", user_id=user_a["id"])
        job_a2 = job_manager.create_job("Job A2", user_id=user_a["id"])
        job_b1 = job_manager.create_job("Job B1", user_id=user_b["id"])

        resp = client.get("/api/jobs/", headers=_headers(user_a))
        assert resp.status_code == 200
        jobs = resp.json()
        job_ids = {j["job_id"] for j in jobs}
        assert job_a1.job_id in job_ids
        assert job_a2.job_id in job_ids
        assert job_b1.job_id not in job_ids

    def test_get_job_owner(self, app_client):
        """Owner can access their job by ID."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        job = job_manager.create_job("My Job", user_id=user_a["id"])

        resp = client.get(f"/api/jobs/{job.job_id}", headers=_headers(user_a))
        assert resp.status_code == 200
        assert resp.json()["job_id"] == job.job_id

    def test_get_job_non_owner_404(self, app_client):
        """Bug #1 fix: non-owner gets 404 when trying to access another user's job."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        job = job_manager.create_job("Secret Job", user_id=user_a["id"])

        resp = client.get(f"/api/jobs/{job.job_id}", headers=_headers(user_b))
        assert resp.status_code == 404

    def test_nonexistent_job_404(self, app_client):
        """Requesting a job ID that doesn't exist returns 404."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        resp = client.get("/api/jobs/nonexistent-id", headers=_headers(user_a))
        assert resp.status_code == 404

    def test_unauthenticated_401(self, app_client):
        """Requests without a token are rejected with 401."""
        client, db_path = app_client

        resp = client.get("/api/jobs/")
        assert resp.status_code == 401

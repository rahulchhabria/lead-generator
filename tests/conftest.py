"""Shared test fixtures for auth, database, and API integration tests."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.database import Database
from src.web.auth import create_access_token


# ---------------------------------------------------------------------------
# Environment setup -- must happen before any app imports
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch, tmp_path):
    """Set required env vars for every test."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-jwt-signing-1234567890abcdef")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def db(tmp_path):
    """Fresh SQLite database per test."""
    db_path = str(tmp_path / f"test_{uuid.uuid4().hex[:8]}.db")
    database = Database(db_path)
    yield database
    database.close()


@pytest.fixture
def team_factory(db):
    """Factory to create teams with sensible defaults."""
    def _create(name="Acme Corp", domain="acme.com", team_id=None):
        tid = team_id or str(uuid.uuid4())
        return db.create_team(tid, name, domain)
    return _create


@pytest.fixture
def user_factory(db):
    """Factory to create users with sensible defaults."""
    def _create(team_id, email="alice@acme.com", name="Alice Smith",
                role="member", user_id=None, avatar_url=None):
        uid = user_id or str(uuid.uuid4())
        return db.create_user(uid, team_id, email, name, avatar_url, role)
    return _create


@pytest.fixture
def invitation_factory(db):
    """Factory to create invitations with sensible defaults."""
    def _create(team_id, email, invited_by, days_until_expiry=7,
                invitation_id=None):
        iid = invitation_id or str(uuid.uuid4())
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=days_until_expiry)
        ).isoformat()
        return db.create_invitation(iid, team_id, email, invited_by, expires_at)
    return _create


# ---------------------------------------------------------------------------
# Pre-built team + user combos
# ---------------------------------------------------------------------------
@pytest.fixture
def team_alpha(db):
    """Team Alpha with domain alpha.com."""
    return db.create_team(str(uuid.uuid4()), "Team Alpha", "alpha.com")


@pytest.fixture
def admin_alpha(db, team_alpha):
    """Admin user on Team Alpha."""
    return db.create_user(
        str(uuid.uuid4()), team_alpha["id"], "admin@alpha.com",
        "Alpha Admin", role="admin"
    )


@pytest.fixture
def member_alpha(db, team_alpha):
    """Regular member on Team Alpha."""
    return db.create_user(
        str(uuid.uuid4()), team_alpha["id"], "member@alpha.com",
        "Alpha Member", role="member"
    )


@pytest.fixture
def team_beta(db):
    """Team Beta with domain beta.io."""
    return db.create_team(str(uuid.uuid4()), "Team Beta", "beta.io")


@pytest.fixture
def admin_beta(db, team_beta):
    """Admin user on Team Beta."""
    return db.create_user(
        str(uuid.uuid4()), team_beta["id"], "admin@beta.io",
        "Beta Admin", role="admin"
    )


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def token_for():
    """Returns a function to create JWT tokens for a given user dict."""
    def _create(user):
        return create_access_token(
            user["id"], user["email"], user["team_id"], user["role"]
        )
    return _create


@pytest.fixture
def auth_header_for(token_for):
    """Returns a function to create Authorization headers for a user."""
    def _create(user):
        return {"Authorization": f"Bearer {token_for(user)}"}
    return _create


# ---------------------------------------------------------------------------
# Campaign helper
# ---------------------------------------------------------------------------
@pytest.fixture
def make_campaign(db):
    """Creates a campaign owned by a user and returns it."""
    def _create(user_id, icp_json=None, domains_json=None, config_json="{}"):
        from src.models import Campaign, PipelineStage
        campaign_id = str(uuid.uuid4())
        campaign = Campaign(
            id=campaign_id,
            icp_json=icp_json,
            domains_json=domains_json,
            config_json=config_json,
            current_stage=PipelineStage.DISCOVERY,
        )
        db.create_campaign(campaign, user_id=user_id)
        return campaign
    return _create


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------
@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """
    TestClient that uses a test database.
    Returns (client, db_path) so tests can create their own Database instances.
    """
    db_path = str(tmp_path / "api_test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    from src.web.main import app
    with TestClient(app) as c:
        yield c, db_path

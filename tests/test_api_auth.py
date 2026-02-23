"""Integration tests for auth API routes: signup, login, and /me."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt

from src.database import Database
from src.web.auth import ALGORITHM


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------
class TestSignup:
    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_signup_creates_team_and_admin(self, mock_verify, app_client):
        mock_verify.return_value = {
            "email": "founder@newco.com",
            "name": "Founder",
            "picture": None,
        }
        client, db_path = app_client

        resp = client.post(
            "/api/auth/signup",
            json={"google_token": "fake-token", "team_name": "NewCo"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        assert data["user"]["email"] == "founder@newco.com"
        assert data["team"]["allowed_domain"] == "newco.com"
        assert data["team"]["name"] == "NewCo"

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_signup_returns_valid_jwt(self, mock_verify, app_client):
        mock_verify.return_value = {
            "email": "founder@startup.io",
            "name": "Founder",
            "picture": "https://photo.url/pic.jpg",
        }
        client, db_path = app_client

        resp = client.post(
            "/api/auth/signup",
            json={"google_token": "fake-token", "team_name": "Startup"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]

        # Decode and verify claims
        secret = "test-secret-key-for-jwt-signing-1234567890abcdef"
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        assert payload["email"] == "founder@startup.io"
        assert payload["role"] == "admin"
        assert payload["sub"] == resp.json()["user"]["id"]
        assert payload["team_id"] == resp.json()["team"]["id"]

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_signup_duplicate_domain_409(self, mock_verify, app_client):
        mock_verify.return_value = {
            "email": "alice@duped.com",
            "name": "Alice",
            "picture": None,
        }
        client, db_path = app_client

        # First signup succeeds
        resp1 = client.post(
            "/api/auth/signup",
            json={"google_token": "tok1", "team_name": "First"},
        )
        assert resp1.status_code == 200

        # Second signup with same domain should fail
        mock_verify.return_value = {
            "email": "bob@duped.com",
            "name": "Bob",
            "picture": None,
        }
        resp2 = client.post(
            "/api/auth/signup",
            json={"google_token": "tok2", "team_name": "Second"},
        )
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class TestLogin:
    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_login_existing_user(self, mock_verify, app_client):
        client, db_path = app_client

        # Pre-create a team and user
        db = Database(db_path)
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        db.create_team(team_id, "LoginTeam", "loginteam.com")
        db.create_user(user_id, team_id, "alice@loginteam.com", "Alice", role="member")
        db.close()

        mock_verify.return_value = {
            "email": "alice@loginteam.com",
            "name": "Alice",
            "picture": None,
        }

        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "alice@loginteam.com"
        assert data["team"]["id"] == team_id
        assert "token" in data

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_login_disabled_user_403(self, mock_verify, app_client):
        client, db_path = app_client

        db = Database(db_path)
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        db.create_team(team_id, "DisabledTeam", "disabled.com")
        db.create_user(user_id, team_id, "dead@disabled.com", "Dead User", role="member")
        db.update_user_status(user_id, "disabled")
        db.close()

        mock_verify.return_value = {
            "email": "dead@disabled.com",
            "name": "Dead User",
            "picture": None,
        }

        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 403

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_login_with_invitation_creates_user(self, mock_verify, app_client):
        client, db_path = app_client

        db = Database(db_path)
        team_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        inv_id = str(uuid.uuid4())
        db.create_team(team_id, "InviteTeam", "inviteteam.com")
        db.create_user(admin_id, team_id, "admin@inviteteam.com", "Admin", role="admin")
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        db.create_invitation(inv_id, team_id, "newbie@inviteteam.com", admin_id, expires_at)
        db.close()

        mock_verify.return_value = {
            "email": "newbie@inviteteam.com",
            "name": "Newbie",
            "picture": None,
        }

        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "newbie@inviteteam.com"
        assert data["user"]["role"] == "member"
        assert data["team"]["id"] == team_id

        # Verify invitation was marked as accepted
        db = Database(db_path)
        inv = db.get_invitation(inv_id)
        assert inv["status"] == "accepted"
        db.close()

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_login_expired_invitation_403(self, mock_verify, app_client):
        """Bug #4: expired invitations should be rejected."""
        client, db_path = app_client

        db = Database(db_path)
        team_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        inv_id = str(uuid.uuid4())
        db.create_team(team_id, "ExpiredTeam", "expired.com")
        db.create_user(admin_id, team_id, "admin@expired.com", "Admin", role="admin")
        # Create an invitation that already expired
        expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        db.create_invitation(inv_id, team_id, "late@expired.com", admin_id, expires_at)
        db.close()

        mock_verify.return_value = {
            "email": "late@expired.com",
            "name": "Late User",
            "picture": None,
        }

        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 403
        assert "expired" in resp.json()["detail"].lower()

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_login_no_user_no_invitation_403(self, mock_verify, app_client):
        client, db_path = app_client

        mock_verify.return_value = {
            "email": "unknown@nowhere.com",
            "name": "Unknown",
            "picture": None,
        }

        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 403

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_login_domain_mismatch_403(self, mock_verify, app_client):
        """Invitation exists but Google returns email from a different domain."""
        client, db_path = app_client

        db = Database(db_path)
        team_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        inv_id = str(uuid.uuid4())
        db.create_team(team_id, "DomainTeam", "domainteam.com")
        db.create_user(admin_id, team_id, "admin@domainteam.com", "Admin", role="admin")
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        # Invitation is for user@domainteam.com
        db.create_invitation(inv_id, team_id, "user@domainteam.com", admin_id, expires_at)
        db.close()

        # But Google returns email from a different domain
        mock_verify.return_value = {
            "email": "user@domainteam.com",
            "name": "User",
            "picture": None,
        }
        # Actually, domain mismatch means the invitation email domain doesn't match the team domain.
        # Let's set up a scenario where invitation email domain differs from team allowed_domain.
        # The login flow checks the Google-returned email's domain vs team's allowed_domain.
        # So we need the invitation email to be on a different domain than the team's allowed_domain.
        # But create_invitation stores the email as-is. The check is on the Google email domain.
        # Let's create a realistic scenario: invitation for user@other.com on team domainmatch.com
        db = Database(db_path)
        team_id2 = str(uuid.uuid4())
        admin_id2 = str(uuid.uuid4())
        inv_id2 = str(uuid.uuid4())
        db.create_team(team_id2, "MatchTeam", "matchteam.com")
        db.create_user(admin_id2, team_id2, "admin@matchteam.com", "Admin2", role="admin")
        expires_at2 = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        db.create_invitation(inv_id2, team_id2, "intruder@other.com", admin_id2, expires_at2)
        db.close()

        mock_verify.return_value = {
            "email": "intruder@other.com",
            "name": "Intruder",
            "picture": None,
        }

        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 403
        assert "domain" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------
class TestMe:
    def test_me_returns_user_and_team(self, app_client):
        client, db_path = app_client

        db = Database(db_path)
        team_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        db.create_team(team_id, "MeTeam", "meteam.com")
        db.create_user(user_id, team_id, "me@meteam.com", "Me User", role="admin")
        db.close()

        from src.web.auth import create_access_token
        token = create_access_token(user_id, "me@meteam.com", team_id, "admin")

        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "me@meteam.com"
        assert data["user"]["id"] == user_id
        assert data["team"]["id"] == team_id
        assert data["team"]["name"] == "MeTeam"

    def test_me_without_auth_401(self, app_client):
        client, db_path = app_client

        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

"""Integration tests for team management API routes."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.database import Database
from src.web.auth import create_access_token


def _setup_team_and_users(db_path):
    """Helper: create a team with an admin and a member. Returns (team, admin, member) dicts."""
    db = Database(db_path)
    team_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())

    team = db.create_team(team_id, "AlphaTeam", "alpha.com")
    admin = db.create_user(admin_id, team_id, "admin@alpha.com", "Admin", role="admin")
    member = db.create_user(member_id, team_id, "member@alpha.com", "Member", role="member")
    db.close()
    return team, admin, member


def _headers(user):
    """Create auth headers for a user dict."""
    token = create_access_token(user["id"], user["email"], user["team_id"], user["role"])
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /api/team
# ---------------------------------------------------------------------------
class TestGetTeam:
    def test_get_team(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.get("/api/team/", headers=_headers(admin))
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == team["id"]
        assert data["name"] == "AlphaTeam"
        assert data["allowed_domain"] == "alpha.com"

    def test_get_team_without_auth_401(self, app_client):
        client, db_path = app_client

        resp = client.get("/api/team/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/team/members
# ---------------------------------------------------------------------------
class TestListMembers:
    def test_list_members(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.get("/api/team/members", headers=_headers(admin))
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 2
        emails = {m["email"] for m in members}
        assert "admin@alpha.com" in emails
        assert "member@alpha.com" in emails


# ---------------------------------------------------------------------------
# POST /api/team/invitations & GET /api/team/invitations
# ---------------------------------------------------------------------------
class TestInvitations:
    def test_admin_create_invitation(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.post(
            "/api/team/invitations",
            json={"email": "newperson@alpha.com"},
            headers=_headers(admin),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newperson@alpha.com"
        assert data["team_id"] == team["id"]
        assert data["status"] == "pending"

    def test_member_cannot_invite_403(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.post(
            "/api/team/invitations",
            json={"email": "another@alpha.com"},
            headers=_headers(member),
        )
        assert resp.status_code == 403

    def test_invite_wrong_domain_400(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.post(
            "/api/team/invitations",
            json={"email": "user@other.com"},
            headers=_headers(admin),
        )
        assert resp.status_code == 400
        assert "domain" in resp.json()["detail"].lower()

    def test_invite_existing_user_409(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        # member@alpha.com already exists
        resp = client.post(
            "/api/team/invitations",
            json={"email": "member@alpha.com"},
            headers=_headers(admin),
        )
        assert resp.status_code == 409

    def test_list_invitations(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        # Create two invitations
        client.post(
            "/api/team/invitations",
            json={"email": "inv1@alpha.com"},
            headers=_headers(admin),
        )
        client.post(
            "/api/team/invitations",
            json={"email": "inv2@alpha.com"},
            headers=_headers(admin),
        )

        resp = client.get("/api/team/invitations", headers=_headers(admin))
        assert resp.status_code == 200
        invitations = resp.json()
        assert len(invitations) == 2


# ---------------------------------------------------------------------------
# DELETE /api/team/invitations/{id}
# ---------------------------------------------------------------------------
class TestCancelInvitation:
    def test_admin_cancel_invitation(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        # Create an invitation
        resp = client.post(
            "/api/team/invitations",
            json={"email": "cancel-me@alpha.com"},
            headers=_headers(admin),
        )
        inv_id = resp.json()["id"]

        # Cancel it
        resp = client.delete(f"/api/team/invitations/{inv_id}", headers=_headers(admin))
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify it's gone
        db = Database(db_path)
        assert db.get_invitation(inv_id) is None
        db.close()

    def test_cannot_cancel_other_team_invitation(self, app_client):
        client, db_path = app_client
        team_a, admin_a, _ = _setup_team_and_users(db_path)

        # Create team B with its own admin
        db = Database(db_path)
        team_b_id = str(uuid.uuid4())
        admin_b_id = str(uuid.uuid4())
        db.create_team(team_b_id, "BetaTeam", "beta.io")
        admin_b = db.create_user(admin_b_id, team_b_id, "admin@beta.io", "BetaAdmin", role="admin")

        # Create invitation on team B
        inv_id = str(uuid.uuid4())
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        db.create_invitation(inv_id, team_b_id, "new@beta.io", admin_b_id, expires)
        db.close()

        # Admin of team A tries to cancel team B's invitation
        resp = client.delete(
            f"/api/team/invitations/{inv_id}", headers=_headers(admin_a)
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/team/members/{id}
# ---------------------------------------------------------------------------
class TestRemoveMember:
    def test_admin_remove_member(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.delete(
            f"/api/team/members/{member['id']}", headers=_headers(admin)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

        # Verify user is disabled
        db = Database(db_path)
        user = db.get_user(member["id"])
        assert user["status"] == "disabled"
        db.close()

    def test_admin_cannot_remove_self(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.delete(
            f"/api/team/members/{admin['id']}", headers=_headers(admin)
        )
        assert resp.status_code == 400

    def test_member_cannot_remove_403(self, app_client):
        client, db_path = app_client
        team, admin, member = _setup_team_and_users(db_path)

        resp = client.delete(
            f"/api/team/members/{admin['id']}", headers=_headers(member)
        )
        assert resp.status_code == 403

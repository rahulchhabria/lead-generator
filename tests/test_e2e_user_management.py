"""End-to-end tests for user management flows."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.database import Database
from src.web.auth import create_access_token


def _make_google_mock(email, name="Test User", picture=None):
    """Create a mock return value for verify_google_token."""
    return {"email": email.lower(), "name": name, "picture": picture}


class TestSignupInviteLoginFlow:
    """Full signup -> invite -> login flow."""

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_full_flow(self, mock_verify, app_client):
        client, db_path = app_client

        # Step 1: Admin signs up
        mock_verify.return_value = _make_google_mock("admin@newco.com", "Admin")
        resp = client.post("/api/auth/signup", json={
            "google_token": "fake-admin",
            "team_name": "NewCo",
        })
        assert resp.status_code == 200
        admin_data = resp.json()
        admin_token = admin_data["token"]
        assert admin_data["user"]["role"] == "admin"
        assert admin_data["team"]["allowed_domain"] == "newco.com"

        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Step 2: Admin invites a member
        resp = client.post("/api/team/invitations", json={"email": "dev@newco.com"},
                           headers=admin_headers)
        assert resp.status_code == 200
        invitation = resp.json()
        assert invitation["email"] == "dev@newco.com"
        assert invitation["status"] == "pending"

        # Step 3: Dev logs in with Google
        mock_verify.return_value = _make_google_mock("dev@newco.com", "Dev")
        resp = client.post("/api/auth/login", json={"google_token": "fake-dev"})
        assert resp.status_code == 200
        dev_data = resp.json()
        dev_token = dev_data["token"]
        assert dev_data["user"]["role"] == "member"
        assert dev_data["team"]["allowed_domain"] == "newco.com"

        dev_headers = {"Authorization": f"Bearer {dev_token}"}

        # Step 4: Dev can access /me
        resp = client.get("/api/auth/me", headers=dev_headers)
        assert resp.status_code == 200
        me = resp.json()
        assert me["user"]["email"] == "dev@newco.com"
        assert me["team"]["name"] == "NewCo"

        # Step 5: Admin sees 2 members
        resp = client.get("/api/team/members", headers=admin_headers)
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 2

        # Step 6: Invitation is marked accepted
        db = Database(db_path)
        try:
            inv = db.get_invitation(invitation["id"])
            assert inv["status"] == "accepted"
        finally:
            db.close()

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_expired_invitation_blocks_login(self, mock_verify, app_client):
        client, db_path = app_client

        # Admin signs up
        mock_verify.return_value = _make_google_mock("admin@newco.com", "Admin")
        resp = client.post("/api/auth/signup", json={
            "google_token": "fake", "team_name": "NewCo"
        })
        assert resp.status_code == 200
        admin = resp.json()

        # Create expired invitation directly in DB
        db = Database(db_path)
        try:
            expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            db.create_invitation(
                str(uuid.uuid4()), admin["team"]["id"],
                "invitee@newco.com", admin["user"]["id"], expires_at
            )
        finally:
            db.close()

        # Dev tries to login with expired invitation
        mock_verify.return_value = _make_google_mock("invitee@newco.com", "Invitee")
        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 403
        assert "expired" in resp.json()["detail"].lower()


class TestTwoTeamsIsolation:
    """Full data isolation between two teams."""

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_complete_isolation(self, mock_verify, app_client):
        client, db_path = app_client

        # Signup Team A
        mock_verify.return_value = _make_google_mock("admin@alpha.com", "Alpha Admin")
        resp = client.post("/api/auth/signup", json={
            "google_token": "fake-a", "team_name": "Alpha Inc"
        })
        assert resp.status_code == 200
        team_a = resp.json()
        headers_a = {"Authorization": f"Bearer {team_a['token']}"}

        # Signup Team B
        mock_verify.return_value = _make_google_mock("admin@beta.io", "Beta Admin")
        resp = client.post("/api/auth/signup", json={
            "google_token": "fake-b", "team_name": "Beta Corp"
        })
        assert resp.status_code == 200
        team_b = resp.json()
        headers_b = {"Authorization": f"Bearer {team_b['token']}"}

        # Team A creates a campaign directly in DB
        db = Database(db_path)
        try:
            from src.models import Campaign, PipelineStage
            campaign_id = str(uuid.uuid4())
            campaign = Campaign(id=campaign_id, config_json="{}")
            db.create_campaign(campaign, user_id=team_a["user"]["id"])
        finally:
            db.close()

        # Team B lists campaigns -> should be empty
        resp = client.get("/api/campaigns/", headers=headers_b)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # Team A lists campaigns -> should see 1
        resp = client.get("/api/campaigns/", headers=headers_a)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Team B tries to GET Team A's campaign -> 403
        resp = client.get(f"/api/campaigns/{campaign_id}", headers=headers_b)
        assert resp.status_code == 403

        # Team A adds enrichment data
        db = Database(db_path)
        try:
            from src.enrichment.models import EnrichmentData
            data = EnrichmentData(domain="test-iso.com", company_name="Test")
            db.upsert_enrichment(data, team_id=team_a["team"]["id"])
        finally:
            db.close()

        # Team B lists enrichments -> should be empty
        resp = client.get("/api/enrichment/", headers=headers_b)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # Team A lists enrichments -> should see 1
        resp = client.get("/api/enrichment/", headers=headers_a)
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestDisabledUserBlocked:
    """Disabled user cannot access any resources."""

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_disabled_user_blocked(self, mock_verify, app_client):
        client, _db_path = app_client

        # Admin signs up
        mock_verify.return_value = _make_google_mock("admin@newco.com", "Admin")
        resp = client.post("/api/auth/signup", json={
            "google_token": "fake", "team_name": "NewCo"
        })
        assert resp.status_code == 200
        admin = resp.json()
        admin_headers = {"Authorization": f"Bearer {admin['token']}"}

        # Invite and login as member
        client.post("/api/team/invitations", json={"email": "member@newco.com"},
                     headers=admin_headers)
        mock_verify.return_value = _make_google_mock("member@newco.com", "Member")
        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        assert resp.status_code == 200
        member = resp.json()
        member_headers = {"Authorization": f"Bearer {member['token']}"}

        # Verify member can access /me
        resp = client.get("/api/auth/me", headers=member_headers)
        assert resp.status_code == 200

        # Admin removes member
        resp = client.delete(f"/api/team/members/{member['user']['id']}",
                             headers=admin_headers)
        assert resp.status_code == 200

        # Member now gets 401 on all endpoints
        resp = client.get("/api/auth/me", headers=member_headers)
        assert resp.status_code == 401

        resp = client.get("/api/campaigns/", headers=member_headers)
        assert resp.status_code == 401


class TestCampaignReviewOwnershipE2E:
    """Campaign review endpoints enforce ownership."""

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_review_ownership(self, mock_verify, app_client):
        client, db_path = app_client

        # Create two users on the same team
        mock_verify.return_value = _make_google_mock("admin@newco.com", "Admin")
        resp = client.post("/api/auth/signup", json={
            "google_token": "fake", "team_name": "NewCo"
        })
        admin = resp.json()
        admin_headers = {"Authorization": f"Bearer {admin['token']}"}

        # Invite and create second user
        client.post("/api/team/invitations", json={"email": "user2@newco.com"},
                     headers=admin_headers)
        mock_verify.return_value = _make_google_mock("user2@newco.com", "User2")
        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        user2 = resp.json()
        user2_headers = {"Authorization": f"Bearer {user2['token']}"}

        # Admin creates a campaign and adds an account
        db = Database(db_path)
        try:
            from src.models import Campaign, Account, PipelineStage
            campaign_id = str(uuid.uuid4())
            campaign = Campaign(id=campaign_id, config_json="{}")
            db.create_campaign(campaign, user_id=admin["user"]["id"])
            account = Account(campaign_id=campaign_id, company_name="Test", domain="test.com")
            account_id = db.insert_account(account)
        finally:
            db.close()

        # Admin can review accounts
        resp = client.post(f"/api/campaigns/{campaign_id}/accounts/review",
                           json={"approved_ids": [account_id]},
                           headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["approved"] == 1

        # User2 cannot review accounts on admin's campaign
        resp = client.post(f"/api/campaigns/{campaign_id}/accounts/review",
                           json={"approved_ids": [account_id]},
                           headers=user2_headers)
        assert resp.status_code == 403


class TestJobIsolationE2E:
    """Jobs are isolated per user."""

    @patch("src.web.routes.auth.verify_google_token", new_callable=AsyncMock)
    def test_job_isolation(self, mock_verify, app_client):
        client, _db_path = app_client
        from src.web.background import job_manager

        # Create two users
        mock_verify.return_value = _make_google_mock("admin@newco.com", "Admin")
        resp = client.post("/api/auth/signup", json={
            "google_token": "fake", "team_name": "NewCo"
        })
        admin = resp.json()
        admin_headers = {"Authorization": f"Bearer {admin['token']}"}

        client.post("/api/team/invitations", json={"email": "user2@newco.com"},
                     headers=admin_headers)
        mock_verify.return_value = _make_google_mock("user2@newco.com", "User2")
        resp = client.post("/api/auth/login", json={"google_token": "fake"})
        user2 = resp.json()
        user2_headers = {"Authorization": f"Bearer {user2['token']}"}

        # Create a job for admin
        job = job_manager.create_job("Admin job", user_id=admin["user"]["id"])

        # Admin can see the job
        resp = client.get(f"/api/jobs/{job.job_id}", headers=admin_headers)
        assert resp.status_code == 200

        # User2 cannot see admin's job
        resp = client.get(f"/api/jobs/{job.job_id}", headers=user2_headers)
        assert resp.status_code == 404

        # User2's job list doesn't include admin's job
        resp = client.get("/api/jobs/", headers=user2_headers)
        assert resp.status_code == 200
        job_ids = [j["job_id"] for j in resp.json()]
        assert job.job_id not in job_ids

"""Tests for database CRUD methods in src/database.py -- teams, users, invitations,
campaigns, enrichment, and data-isolation guarantees."""

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from src.database import Database
from src.enrichment.models import EnrichmentData
from src.models import Campaign, PipelineStage


# ---------------------------------------------------------------------------
# TestTeamCRUD
# ---------------------------------------------------------------------------
class TestTeamCRUD:
    def test_create_team(self, team_factory):
        team = team_factory(name="Widgets Inc", domain="widgets.io")
        assert team["name"] == "Widgets Inc"
        assert team["allowed_domain"] == "widgets.io"
        assert "id" in team

    def test_get_team(self, db, team_alpha):
        fetched = db.get_team(team_alpha["id"])
        assert fetched is not None
        assert fetched["id"] == team_alpha["id"]
        assert fetched["name"] == "Team Alpha"
        assert fetched["allowed_domain"] == "alpha.com"

    def test_get_team_nonexistent(self, db):
        assert db.get_team("nonexistent-id-12345") is None

    def test_get_team_by_domain(self, db, team_alpha):
        fetched = db.get_team_by_domain("alpha.com")
        assert fetched is not None
        assert fetched["id"] == team_alpha["id"]

    def test_duplicate_domain_raises(self, db, team_factory):
        team_factory(name="First", domain="unique.io")
        with pytest.raises(sqlite3.IntegrityError):
            team_factory(name="Second", domain="unique.io")


# ---------------------------------------------------------------------------
# TestUserCRUD
# ---------------------------------------------------------------------------
class TestUserCRUD:
    def test_create_user(self, db, team_alpha, user_factory):
        user = user_factory(team_id=team_alpha["id"], email="new@alpha.com", name="New User")
        assert user["email"] == "new@alpha.com"
        assert user["name"] == "New User"
        assert user["role"] == "member"
        assert user["status"] == "active"

    def test_create_user_normalizes_email(self, db, team_alpha):
        """Bug #5 fix -- emails are stored lower-cased."""
        uid = str(uuid.uuid4())
        user = db.create_user(uid, team_alpha["id"], "Alice.UPPER@Alpha.COM", "Alice")
        assert user["email"] == "alice.upper@alpha.com"
        # Also confirm the DB stored it in lowercase
        fetched = db.get_user_by_email("ALICE.UPPER@ALPHA.COM")
        assert fetched is not None
        assert fetched["email"] == "alice.upper@alpha.com"

    def test_get_user_by_email_case_insensitive(self, db, team_alpha, user_factory):
        user_factory(team_id=team_alpha["id"], email="CamelCase@Alpha.com", name="Camel")
        # Lookup with different casing
        fetched = db.get_user_by_email("camelcase@alpha.com")
        assert fetched is not None
        assert fetched["name"] == "Camel"

    def test_list_team_members(self, db, team_alpha, admin_alpha, member_alpha):
        members = db.list_team_members(team_alpha["id"])
        assert len(members) == 2
        ids = {m["id"] for m in members}
        assert admin_alpha["id"] in ids
        assert member_alpha["id"] in ids

    def test_update_user_status(self, db, team_alpha, admin_alpha):
        db.update_user_status(admin_alpha["id"], "disabled")
        fetched = db.get_user(admin_alpha["id"])
        assert fetched["status"] == "disabled"

    def test_delete_user(self, db, team_alpha, admin_alpha):
        db.delete_user(admin_alpha["id"])
        assert db.get_user(admin_alpha["id"]) is None

    def test_duplicate_email_raises(self, db, team_alpha):
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        db.create_user(uid1, team_alpha["id"], "dupe@alpha.com", "First")
        with pytest.raises(sqlite3.IntegrityError):
            db.create_user(uid2, team_alpha["id"], "dupe@alpha.com", "Second")


# ---------------------------------------------------------------------------
# TestInvitationCRUD
# ---------------------------------------------------------------------------
class TestInvitationCRUD:
    def test_create_invitation(self, db, team_alpha, admin_alpha, invitation_factory):
        inv = invitation_factory(
            team_id=team_alpha["id"],
            email="invite@alpha.com",
            invited_by=admin_alpha["id"],
        )
        assert inv["email"] == "invite@alpha.com"
        assert inv["status"] == "pending"
        assert inv["team_id"] == team_alpha["id"]
        assert inv["invited_by"] == admin_alpha["id"]

    def test_get_pending_invitation_by_email(self, db, team_alpha, admin_alpha, invitation_factory):
        invitation_factory(
            team_id=team_alpha["id"],
            email="pending@alpha.com",
            invited_by=admin_alpha["id"],
        )
        found = db.get_pending_invitation_by_email("pending@alpha.com")
        assert found is not None
        assert found["email"] == "pending@alpha.com"
        assert found["status"] == "pending"

    def test_pending_ignores_accepted(self, db, team_alpha, admin_alpha, invitation_factory):
        inv = invitation_factory(
            team_id=team_alpha["id"],
            email="accepted@alpha.com",
            invited_by=admin_alpha["id"],
        )
        db.update_invitation_status(inv["id"], "accepted")
        found = db.get_pending_invitation_by_email("accepted@alpha.com")
        assert found is None

    def test_list_team_invitations(self, db, team_alpha, admin_alpha, invitation_factory):
        invitation_factory(
            team_id=team_alpha["id"],
            email="one@alpha.com",
            invited_by=admin_alpha["id"],
        )
        invitation_factory(
            team_id=team_alpha["id"],
            email="two@alpha.com",
            invited_by=admin_alpha["id"],
        )
        invitations = db.list_team_invitations(team_alpha["id"])
        assert len(invitations) == 2
        emails = {i["email"] for i in invitations}
        assert "one@alpha.com" in emails
        assert "two@alpha.com" in emails


# ---------------------------------------------------------------------------
# TestCampaignScoping
# ---------------------------------------------------------------------------
class TestCampaignScoping:
    def test_create_campaign_with_user_id(self, db, team_alpha, admin_alpha, make_campaign):
        campaign = make_campaign(user_id=admin_alpha["id"])
        owner = db.get_campaign_owner(campaign.id)
        assert owner == admin_alpha["id"]

    def test_list_campaigns_filtered_by_user(self, db, team_alpha, admin_alpha, member_alpha, make_campaign):
        make_campaign(user_id=admin_alpha["id"])
        make_campaign(user_id=admin_alpha["id"])
        make_campaign(user_id=member_alpha["id"])

        admin_campaigns = db.list_campaigns(user_id=admin_alpha["id"])
        member_campaigns = db.list_campaigns(user_id=member_alpha["id"])

        assert len(admin_campaigns) == 2
        assert len(member_campaigns) == 1

    def test_campaign_owner_returns_user_id(self, db, team_alpha, admin_alpha, make_campaign):
        campaign = make_campaign(user_id=admin_alpha["id"])
        # Re-fetch from DB and confirm timestamps are real (bug #8)
        fetched = db.get_campaign(campaign.id)
        assert fetched is not None
        assert fetched.created_at is not None
        assert fetched.updated_at is not None
        # Verify the owner
        owner = db.get_campaign_owner(campaign.id)
        assert owner == admin_alpha["id"]


# ---------------------------------------------------------------------------
# TestEnrichmentScoping
# ---------------------------------------------------------------------------
class TestEnrichmentScoping:
    def test_get_enrichment_with_team_filter(self, db, team_alpha, team_beta):
        """Bug #2 fix -- enrichment data is scoped to teams."""
        data_alpha = EnrichmentData(domain="example.com", company_name="Example Alpha")
        db.upsert_enrichment(data_alpha, team_id=team_alpha["id"])

        # Same domain but different team should not find alpha's data
        result = db.get_enrichment("example.com", team_id=team_beta["id"])
        assert result is None

        # The owning team should find it
        result = db.get_enrichment("example.com", team_id=team_alpha["id"])
        assert result is not None
        assert result["company_name"] == "Example Alpha"

    def test_list_enrichments_filtered_by_team(self, db, team_alpha, team_beta):
        data_a1 = EnrichmentData(domain="a1.com", company_name="Alpha One")
        data_a2 = EnrichmentData(domain="a2.com", company_name="Alpha Two")
        data_b1 = EnrichmentData(domain="b1.com", company_name="Beta One")

        db.upsert_enrichment(data_a1, team_id=team_alpha["id"])
        db.upsert_enrichment(data_a2, team_id=team_alpha["id"])
        db.upsert_enrichment(data_b1, team_id=team_beta["id"])

        alpha_list = db.list_enrichments(team_id=team_alpha["id"])
        beta_list = db.list_enrichments(team_id=team_beta["id"])

        assert len(alpha_list) == 2
        assert len(beta_list) == 1
        assert beta_list[0]["company_name"] == "Beta One"


# ---------------------------------------------------------------------------
# TestDataIsolation
# ---------------------------------------------------------------------------
class TestDataIsolation:
    def test_cross_team_user_isolation(self, db, team_alpha, admin_alpha, team_beta, admin_beta):
        """Users from one team must not appear in another team's member list."""
        alpha_members = db.list_team_members(team_alpha["id"])
        beta_members = db.list_team_members(team_beta["id"])

        alpha_ids = {m["id"] for m in alpha_members}
        beta_ids = {m["id"] for m in beta_members}

        assert admin_alpha["id"] in alpha_ids
        assert admin_alpha["id"] not in beta_ids
        assert admin_beta["id"] in beta_ids
        assert admin_beta["id"] not in alpha_ids

    def test_cross_user_campaign_isolation(self, db, team_alpha, admin_alpha, member_alpha, make_campaign):
        """Campaigns created by one user must not appear in another user's list."""
        make_campaign(user_id=admin_alpha["id"])
        make_campaign(user_id=member_alpha["id"])

        admin_campaigns = db.list_campaigns(user_id=admin_alpha["id"])
        member_campaigns = db.list_campaigns(user_id=member_alpha["id"])

        assert len(admin_campaigns) == 1
        assert len(member_campaigns) == 1

        # IDs must not overlap
        admin_ids = {c.id for c in admin_campaigns}
        member_ids = {c.id for c in member_campaigns}
        assert admin_ids.isdisjoint(member_ids)

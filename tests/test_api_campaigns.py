"""Integration tests for campaign API routes: listing, detail, and review endpoints."""

import uuid

import pytest

from src.database import Database
from src.models import Account, Campaign, Contact, DraftEmail, LeadStatus, PersonalizationDossier, PipelineStage
from src.web.auth import create_access_token


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


def _create_campaign(db_path, user_id, config_json="{}"):
    """Create a campaign owned by user_id. Returns the campaign id."""
    db = Database(db_path)
    campaign_id = str(uuid.uuid4())
    campaign = Campaign(
        id=campaign_id,
        config_json=config_json,
        current_stage=PipelineStage.DISCOVERY,
    )
    db.create_campaign(campaign, user_id=user_id)
    db.close()
    return campaign_id


def _create_account(db_path, campaign_id, company_name="TestCo", domain="test.com"):
    """Insert an account for a campaign. Returns the account id."""
    db = Database(db_path)
    account = Account(campaign_id=campaign_id, company_name=company_name, domain=domain)
    account_id = db.insert_account(account)
    db.close()
    return account_id


def _create_contact(db_path, campaign_id, account_id, first_name="John", last_name="Doe",
                    email="john@test.com"):
    """Insert a contact for a campaign. Returns the contact id."""
    db = Database(db_path)
    contact = Contact(
        account_id=account_id,
        campaign_id=campaign_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    contact_id = db.insert_contact(contact)
    db.close()
    return contact_id


def _create_draft_email(db_path, campaign_id, contact_id, dossier_id):
    """Insert a draft email for a campaign. Returns the email id."""
    db = Database(db_path)
    draft = DraftEmail(
        contact_id=contact_id,
        dossier_id=dossier_id,
        campaign_id=campaign_id,
        subject_line="Hello",
        body="Body text",
    )
    email_id = db.insert_draft_email(draft)
    db.close()
    return email_id


def _create_dossier(db_path, campaign_id, contact_id):
    """Insert a dossier for a contact. Returns the dossier id."""
    db = Database(db_path)
    dossier = PersonalizationDossier(
        contact_id=contact_id,
        campaign_id=campaign_id,
    )
    dossier_id = db.insert_dossier(dossier)
    db.close()
    return dossier_id


# ---------------------------------------------------------------------------
# Campaign ownership and listing
# ---------------------------------------------------------------------------
class TestCampaignOwnership:
    def test_list_returns_own_campaigns_only(self, app_client):
        """User A's list should contain only their campaigns, not user B's."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        # User A gets 2 campaigns, user B gets 1
        _create_campaign(db_path, user_a["id"])
        _create_campaign(db_path, user_a["id"])
        _create_campaign(db_path, user_b["id"])

        resp = client.get("/api/campaigns/", headers=_headers(user_a))
        assert resp.status_code == 200
        campaigns = resp.json()
        assert len(campaigns) == 2

        resp_b = client.get("/api/campaigns/", headers=_headers(user_b))
        assert resp_b.status_code == 200
        assert len(resp_b.json()) == 1

    def test_get_campaign_owner_access(self, app_client):
        """Owner can retrieve their own campaign by ID."""
        client, db_path = app_client
        user_a, _user_b = _setup_two_users(db_path)

        cid = _create_campaign(db_path, user_a["id"])
        resp = client.get(f"/api/campaigns/{cid}", headers=_headers(user_a))
        assert resp.status_code == 200
        assert resp.json()["id"] == cid

    def test_get_campaign_non_owner_403(self, app_client):
        """Non-owner is denied access to another user's campaign."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        cid = _create_campaign(db_path, user_a["id"])
        resp = client.get(f"/api/campaigns/{cid}", headers=_headers(user_b))
        assert resp.status_code == 403

    def test_unauthenticated_401(self, app_client):
        """Requests without a token are rejected with 401."""
        client, _db_path = app_client

        resp = client.get("/api/campaigns/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Review endpoints: accounts, contacts, emails
# ---------------------------------------------------------------------------
class TestReviewAuth:
    def test_review_accounts_owner_succeeds(self, app_client):
        """Bug #3 fix: campaign owner can review accounts."""
        client, db_path = app_client
        user_a, _user_b = _setup_two_users(db_path)

        cid = _create_campaign(db_path, user_a["id"])
        acct_id = _create_account(db_path, cid)

        resp = client.post(
            f"/api/campaigns/{cid}/accounts/review",
            json={"approved_ids": [acct_id], "rejected_ids": []},
            headers=_headers(user_a),
        )
        assert resp.status_code == 200
        assert resp.json()["approved"] == 1

        # Verify status changed
        db = Database(db_path)
        accounts = db.get_accounts(cid, LeadStatus.APPROVED)
        assert len(accounts) == 1
        db.close()

    def test_review_accounts_non_owner_403(self, app_client):
        """Bug #3 fix: non-owner cannot review another user's campaign accounts."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        cid = _create_campaign(db_path, user_a["id"])
        acct_id = _create_account(db_path, cid)

        resp = client.post(
            f"/api/campaigns/{cid}/accounts/review",
            json={"approved_ids": [acct_id], "rejected_ids": []},
            headers=_headers(user_b),
        )
        assert resp.status_code == 403

    def test_review_contacts_non_owner_403(self, app_client):
        """Non-owner cannot review contacts on another user's campaign."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        cid = _create_campaign(db_path, user_a["id"])
        acct_id = _create_account(db_path, cid)
        contact_id = _create_contact(db_path, cid, acct_id)

        resp = client.post(
            f"/api/campaigns/{cid}/contacts/review",
            json={"approved_ids": [contact_id], "rejected_ids": []},
            headers=_headers(user_b),
        )
        assert resp.status_code == 403

    def test_review_emails_non_owner_403(self, app_client):
        """Non-owner cannot review emails on another user's campaign."""
        client, db_path = app_client
        user_a, user_b = _setup_two_users(db_path)

        cid = _create_campaign(db_path, user_a["id"])
        acct_id = _create_account(db_path, cid)
        contact_id = _create_contact(db_path, cid, acct_id)
        dossier_id = _create_dossier(db_path, cid, contact_id)
        email_id = _create_draft_email(db_path, cid, contact_id, dossier_id)

        resp = client.post(
            f"/api/campaigns/{cid}/emails/review",
            json={"approved_ids": [email_id], "rejected_ids": []},
            headers=_headers(user_b),
        )
        assert resp.status_code == 403

    def test_review_null_owner_campaign_403(self, app_client):
        """Bug #7 fix: campaign with NULL user_id denies access to any user."""
        client, db_path = app_client
        user_a, _user_b = _setup_two_users(db_path)

        # Insert campaign with NULL user_id directly via SQL
        campaign_id = str(uuid.uuid4())
        db = Database(db_path)
        db.conn.execute(
            "INSERT INTO campaigns (id, config_json, current_stage) VALUES (?, '{}', 'discovery')",
            (campaign_id,),
        )
        db.conn.commit()

        # Insert an account so the review payload is valid
        account = Account(campaign_id=campaign_id, company_name="NullOwner Co", domain="nullowner.com")
        acct_id = db.insert_account(account)
        db.close()

        resp = client.post(
            f"/api/campaigns/{campaign_id}/accounts/review",
            json={"approved_ids": [acct_id], "rejected_ids": []},
            headers=_headers(user_a),
        )
        assert resp.status_code == 403

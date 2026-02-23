"""Integration tests for enrichment API routes: list, detail, and single-enrich."""

import uuid
from unittest.mock import patch

import pytest

from src.database import Database
from src.enrichment.models import EnrichmentData
from src.web.auth import create_access_token


def _setup_two_team_users(db_path):
    """Create two users on separate teams. Returns (user_alpha, user_beta) dicts
    along with their team IDs embedded in the user dicts."""
    db = Database(db_path)

    team_alpha_id = str(uuid.uuid4())
    user_alpha_id = str(uuid.uuid4())
    db.create_team(team_alpha_id, "Alpha", "alpha.com")
    user_alpha = db.create_user(
        user_alpha_id, team_alpha_id, "user@alpha.com", "Alpha User", role="admin"
    )

    team_beta_id = str(uuid.uuid4())
    user_beta_id = str(uuid.uuid4())
    db.create_team(team_beta_id, "Beta", "beta.io")
    user_beta = db.create_user(
        user_beta_id, team_beta_id, "user@beta.io", "Beta User", role="admin"
    )

    db.close()
    return user_alpha, user_beta


def _headers(user):
    """Create auth headers for a user dict."""
    token = create_access_token(user["id"], user["email"], user["team_id"], user["role"])
    return {"Authorization": f"Bearer {token}"}


def _insert_enrichment(db_path, domain, company_name, team_id):
    """Insert enrichment data for a domain scoped to a team."""
    db = Database(db_path)
    data = EnrichmentData(domain=domain, company_name=company_name)
    db.upsert_enrichment(data, team_id=team_id)
    db.close()


# ---------------------------------------------------------------------------
# Enrichment scoping by team
# ---------------------------------------------------------------------------
class TestEnrichmentScoping:
    def test_list_returns_team_enrichments_only(self, app_client):
        """Listing enrichments returns only the current user's team data."""
        client, db_path = app_client
        user_alpha, user_beta = _setup_two_team_users(db_path)

        _insert_enrichment(db_path, "alpha-one.com", "Alpha One", user_alpha["team_id"])
        _insert_enrichment(db_path, "alpha-two.com", "Alpha Two", user_alpha["team_id"])
        _insert_enrichment(db_path, "beta-one.com", "Beta One", user_beta["team_id"])

        resp = client.get("/api/enrichment/", headers=_headers(user_alpha))
        assert resp.status_code == 200
        results = resp.json()
        domains = {r["domain"] for r in results}
        assert "alpha-one.com" in domains
        assert "alpha-two.com" in domains
        assert "beta-one.com" not in domains

    @patch("src.enrichment.engine.enrich_domain")
    def test_get_enrichment_own_team(self, mock_enrich, app_client):
        """User can fetch enrichment data that belongs to their team (cache hit)."""
        client, db_path = app_client
        user_alpha, user_beta = _setup_two_team_users(db_path)

        _insert_enrichment(db_path, "mycompany.com", "My Company", user_alpha["team_id"])

        resp = client.get("/api/enrichment/mycompany.com", headers=_headers(user_alpha))
        assert resp.status_code == 200
        assert resp.json()["domain"] == "mycompany.com"
        assert resp.json()["company_name"] == "My Company"

        # enrich_domain should NOT have been called (cache hit)
        mock_enrich.assert_not_called()

    @patch("src.enrichment.engine.enrich_domain")
    def test_get_enrichment_other_team_not_found(self, mock_enrich, app_client):
        """Bug #2 fix: user cannot see enrichment data belonging to another team.
        When the team_id filter misses, the route falls through and calls enrich_domain.
        We mock it to return new data so the request does not error out, and verify
        that the original team's cached data was NOT returned."""
        client, db_path = app_client
        user_alpha, user_beta = _setup_two_team_users(db_path)

        # Insert enrichment for team alpha only
        _insert_enrichment(db_path, "secret.com", "Secret Corp", user_alpha["team_id"])

        # When beta requests it, the team_id filter returns None, so enrich_domain is called
        mock_data = EnrichmentData(domain="secret.com", company_name="Freshly Enriched")
        mock_enrich.return_value = mock_data

        resp = client.get("/api/enrichment/secret.com", headers=_headers(user_beta))
        assert resp.status_code == 200

        # enrich_domain WAS called because the cache missed for beta's team
        mock_enrich.assert_called_once_with("secret.com")

        # The response should contain the freshly enriched data, not alpha's cached data
        assert resp.json()["company_name"] == "Freshly Enriched"

    @patch("src.enrichment.engine.enrich_domain")
    def test_enrich_single_uses_cached_with_team_id(self, mock_enrich, app_client):
        """POST /enrichment/single returns cached data when it exists for this team,
        without calling the real enrichment engine."""
        client, db_path = app_client
        user_alpha, user_beta = _setup_two_team_users(db_path)

        _insert_enrichment(db_path, "cached.com", "Cached Inc", user_alpha["team_id"])

        resp = client.post(
            "/api/enrichment/single",
            json={"domain": "cached.com", "force_refresh": False},
            headers=_headers(user_alpha),
        )
        assert resp.status_code == 200
        assert resp.json()["domain"] == "cached.com"
        assert resp.json()["company_name"] == "Cached Inc"

        # Should not call the real enrichment engine
        mock_enrich.assert_not_called()

    @patch("src.enrichment.engine.enrich_domain")
    def test_enrich_single_calls_engine_on_cache_miss(self, mock_enrich, app_client):
        """POST /enrichment/single calls the enrichment engine when no cached data
        exists for this team."""
        client, db_path = app_client
        user_alpha, user_beta = _setup_two_team_users(db_path)

        mock_data = EnrichmentData(domain="new.com", company_name="New Corp")
        mock_enrich.return_value = mock_data

        resp = client.post(
            "/api/enrichment/single",
            json={"domain": "new.com"},
            headers=_headers(user_alpha),
        )
        assert resp.status_code == 200
        mock_enrich.assert_called_once_with("new.com", None)

    def test_unauthenticated_401(self, app_client):
        """Requests without a token are rejected with 401."""
        client, db_path = app_client

        resp = client.get("/api/enrichment/")
        assert resp.status_code == 401

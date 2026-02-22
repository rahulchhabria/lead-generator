"""Tests for tool modules."""

import json
from unittest.mock import patch


from tests.fixtures.mock_responses import (
    GITHUB_USER_INFO_RESPONSE,
    GITHUB_USER_REPOS_RESPONSE,
    HUNTER_DOMAIN_SEARCH_RESPONSE,
    HUNTER_EMAIL_FINDER_RESPONSE,
    HUNTER_EMAIL_VERIFIER_RESPONSE,
)


class TestEmailPatterns:
    def test_generate_patterns(self):
        from src.tools.email_patterns import execute

        result = json.loads(execute("Jane", "Doe", "acme.io"))
        assert result["count"] > 0
        assert "jane.doe@acme.io" in result["patterns"]
        assert "jane@acme.io" in result["patterns"]
        assert "jdoe@acme.io" in result["patterns"]

    def test_empty_inputs(self):
        from src.tools.email_patterns import execute

        result = json.loads(execute("", "Doe", "acme.io"))
        assert "error" in result

    def test_deduplication(self):
        from src.tools.email_patterns import execute

        result = json.loads(execute("Jane", "Doe", "acme.io"))
        assert len(result["patterns"]) == len(set(result["patterns"]))


class TestEmailVerifier:
    def test_invalid_syntax(self):
        from src.tools.email_verifier import execute

        result = json.loads(execute("not-an-email"))
        assert result["valid_syntax"] is False
        assert result["confidence"] == 0

    def test_valid_syntax(self):
        from src.tools.email_verifier import execute

        result = json.loads(execute("test@example.com"))
        assert result["valid_syntax"] is True

    def test_disposable_domain(self):
        from src.tools.email_verifier import execute

        result = json.loads(execute("test@mailinator.com"))
        assert result["is_disposable"] is True
        assert result["confidence"] == 0


class TestWebSearch:
    @patch("src.tools.web_search._serper_search")
    def test_serper_search(self, mock_serper):
        from src.tools.web_search import execute

        mock_serper.return_value = [
            {"title": "Acme Corp", "url": "https://acme.io", "snippet": "Dev tools"}
        ]

        result = json.loads(execute("acme corp", 10, "fake-api-key"))
        assert result["count"] == 1
        assert result["results"][0]["title"] == "Acme Corp"
        mock_serper.assert_called_once()

    def test_fallback_without_key(self):
        from src.tools.web_search import execute

        # Without serper key, should fall back to DuckDuckGo (which may fail in tests)
        result = json.loads(execute("test query", 5, ""))
        assert "results" in result or "message" in result


class TestHunter:
    @patch("src.tools.hunter._hunter_request")
    def test_domain_search(self, mock_request):
        from src.tools.hunter import domain_search

        mock_request.return_value = HUNTER_DOMAIN_SEARCH_RESPONSE

        result = json.loads(domain_search("acme.io", "fake-key"))
        assert result["domain"] == "acme.io"
        assert result["total"] >= 1
        assert result["emails"][0]["email"] == "jane.doe@acme.io"

    @patch("src.tools.hunter._hunter_request")
    def test_email_finder(self, mock_request):
        from src.tools.hunter import email_finder

        mock_request.return_value = HUNTER_EMAIL_FINDER_RESPONSE

        result = json.loads(email_finder("acme.io", "John", "Smith", "fake-key"))
        assert result["email"] == "john.smith@acme.io"
        assert result["confidence"] == 85

    @patch("src.tools.hunter._hunter_request")
    def test_email_verifier(self, mock_request):
        from src.tools.hunter import email_verifier

        mock_request.return_value = HUNTER_EMAIL_VERIFIER_RESPONSE

        result = json.loads(email_verifier("jane.doe@acme.io", "fake-key"))
        assert result["status"] == "valid"
        assert result["score"] == 95

    @patch("src.tools.hunter._hunter_request")
    def test_quota_exceeded(self, mock_request):
        from src.tools.hunter import domain_search

        mock_request.return_value = {"error": "Hunter.io quota exceeded. Consider upgrading your plan."}

        result = json.loads(domain_search("acme.io", "fake-key"))
        assert "error" in result


class TestGitHubAPI:
    @patch("src.tools.github_api._github_get")
    def test_user_info(self, mock_get):
        from src.tools.github_api import user_info

        mock_get.return_value = GITHUB_USER_INFO_RESPONSE

        result = json.loads(user_info("janedoe", "fake-token"))
        assert result["username"] == "janedoe"
        assert result["name"] == "Jane Doe"
        assert result["public_repos"] == 42

    @patch("src.tools.github_api._github_get")
    def test_user_repos(self, mock_get):
        from src.tools.github_api import user_repos

        mock_get.return_value = GITHUB_USER_REPOS_RESPONSE

        result = json.loads(user_repos("janedoe", "fake-token"))
        assert result["total"] == 2
        assert result["repos"][0]["name"] == "awesome-cli"

    @patch("src.tools.github_api._github_get")
    def test_user_not_found(self, mock_get):
        from src.tools.github_api import user_info

        mock_get.return_value = {"error": "GitHub user not found"}

        result = json.loads(user_info("nonexistent-user", ""))
        assert "error" in result


class TestWebScraper:
    @patch("src.tools.web_scraper._fetch_url")
    def test_scrape_basic_page(self, mock_fetch):
        from src.tools.web_scraper import execute

        mock_fetch.return_value = """
        <html>
        <body>
            <nav>Navigation</nav>
            <main><h1>About Acme</h1><p>We build developer tools.</p></main>
            <footer>Footer</footer>
        </body>
        </html>
        """

        result = json.loads(execute("https://acme.io/about"))
        assert "About Acme" in result["content"]
        assert "We build developer tools" in result["content"]
        # Nav and footer should be removed
        assert "Navigation" not in result["content"]

    @patch("src.tools.web_scraper._fetch_url")
    def test_truncation(self, mock_fetch):
        from src.tools.web_scraper import execute

        mock_fetch.return_value = "<html><body><p>" + "x" * 10000 + "</p></body></html>"

        result = json.loads(execute("https://example.com", max_chars=100))
        assert len(result["content"]) <= 120  # 100 + truncation message

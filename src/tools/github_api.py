"""GitHub API tools for personalization research."""

from __future__ import annotations

import json
import logging

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

USER_INFO_TOOL = {
    "name": "github_user_info",
    "description": (
        "Get a GitHub user's public profile: name, bio, company, location, blog, "
        "public repos count, and followers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "username": {"type": "string", "description": "GitHub username."},
        },
        "required": ["username"],
    },
}

USER_REPOS_TOOL = {
    "name": "github_user_repos",
    "description": (
        "List a GitHub user's public repositories with name, description, language, "
        "stars, and last update date."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "username": {"type": "string", "description": "GitHub username."},
            "sort": {
                "type": "string",
                "description": "Sort by: 'updated', 'created', or 'pushed' (default: updated).",
                "default": "updated",
            },
            "limit": {
                "type": "integer",
                "description": "Max repos to return (default: 10).",
                "default": 10,
            },
        },
        "required": ["username"],
    },
}


def _get_headers(token: str = "") -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
)
def _github_get(url: str, token: str = "") -> dict | list:
    response = requests.get(url, headers=_get_headers(token), timeout=15)
    if response.status_code == 404:
        return {"error": "GitHub user not found"}
    if response.status_code == 403:
        return {"error": "GitHub rate limit exceeded. Add GITHUB_TOKEN to .env for higher limits."}
    response.raise_for_status()
    return response.json()


def user_info(username: str, token: str = "") -> str:
    """Get GitHub user profile info."""
    try:
        data = _github_get(f"https://api.github.com/users/{username}", token)
    except Exception as e:
        return json.dumps({"error": f"GitHub API failed: {e}"})

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    return json.dumps(
        {
            "username": data.get("login", username),
            "name": data.get("name", ""),
            "bio": data.get("bio", ""),
            "company": data.get("company", ""),
            "location": data.get("location", ""),
            "blog": data.get("blog", ""),
            "twitter": data.get("twitter_username", ""),
            "public_repos": data.get("public_repos", 0),
            "followers": data.get("followers", 0),
            "following": data.get("following", 0),
            "created_at": data.get("created_at", ""),
        }
    )


def user_repos(username: str, token: str = "", sort: str = "updated", limit: int = 10) -> str:
    """List a user's public repos."""
    try:
        data = _github_get(
            f"https://api.github.com/users/{username}/repos?sort={sort}&per_page={limit}",
            token,
        )
    except Exception as e:
        return json.dumps({"error": f"GitHub API failed: {e}"})

    if isinstance(data, dict) and "error" in data:
        return json.dumps(data)

    repos = []
    for repo in data[:limit]:
        repos.append(
            {
                "name": repo.get("name", ""),
                "description": repo.get("description", ""),
                "language": repo.get("language", ""),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "updated_at": repo.get("updated_at", ""),
                "url": repo.get("html_url", ""),
                "topics": repo.get("topics", []),
            }
        )

    return json.dumps({"username": username, "repos": repos, "total": len(repos)})

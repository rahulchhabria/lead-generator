"""Fetch GitHub organization data for enrichment."""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from .models import GitHubData

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "enrichment-bot/1.0"}
    if token:
        h["Authorization"] = f"token {token}"
    return h


def _get(path: str, timeout: int = 8):
    try:
        resp = requests.get(f"{GITHUB_API}{path}", headers=_headers(), timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"GitHub API {path}: {e}")
    return None


def _find_org(company_name: str, domain: str) -> Optional[str]:
    candidates = [
        company_name.lower().replace(" ", ""),
        company_name.lower().replace(" ", "-"),
        domain.split(".")[0],
        company_name.lower().split(" ")[0],
    ]
    for slug in dict.fromkeys(candidates):  # deduplicate while preserving order
        if not slug or len(slug) < 2:
            continue
        for endpoint in [f"/orgs/{slug}", f"/users/{slug}"]:
            data = _get(endpoint)
            if data and isinstance(data, dict) and data.get("login"):
                return data["login"]
    return None


def fetch_github(company_name: str, domain: str) -> Optional[GitHubData]:
    """Fetch GitHub org/user data."""
    org = _find_org(company_name, domain)
    if not org:
        return None

    org_data = _get(f"/orgs/{org}") or _get(f"/users/{org}")
    if not org_data or not isinstance(org_data, dict):
        return None

    repos = _get(f"/orgs/{org}/repos?sort=stars&per_page=20&type=public")
    if not repos:
        repos = _get(f"/users/{org}/repos?sort=stars&per_page=20")
    repos = repos or []

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    top_repos = [
        {
            "name": r["name"],
            "url": r["html_url"],
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language"),
            "description": r.get("description", ""),
        }
        for r in sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:5]
    ]

    lang_counts: dict[str, int] = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
    total = sum(lang_counts.values()) or 1
    lang_breakdown = {k: round(v / total * 100, 1) for k, v in lang_counts.items()}
    languages = sorted(lang_counts.keys(), key=lambda x: lang_counts[x], reverse=True)

    return GitHubData(
        org_name=org,
        org_url=f"https://github.com/{org}",
        public_repos=org_data.get("public_repos", len(repos)),
        total_stars=total_stars,
        total_forks=total_forks,
        top_repos=top_repos,
        programming_languages=languages,
        language_breakdown=lang_breakdown,
    )

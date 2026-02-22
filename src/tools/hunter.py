"""Hunter.io API tools - optional, gracefully degrades when not configured."""

from __future__ import annotations

import json
import logging

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hunter.io/v2"

DOMAIN_SEARCH_TOOL = {
    "name": "hunter_domain_search",
    "description": (
        "Search for all email addresses associated with a company domain using Hunter.io. "
        "Returns names, emails, positions, and confidence scores. "
        "Costs 1 Hunter credit per call."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Company domain to search (e.g. 'stripe.com').",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default: 10, max: 100).",
                "default": 10,
            },
            "department": {
                "type": "string",
                "description": "Filter by department: executive, it, engineering, finance, etc.",
            },
        },
        "required": ["domain"],
    },
}

EMAIL_FINDER_TOOL = {
    "name": "hunter_email_finder",
    "description": (
        "Find a specific person's email address at a company using Hunter.io. "
        "Costs 1 Hunter credit per call."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Company domain (e.g. 'stripe.com')."},
            "first_name": {"type": "string", "description": "Person's first name."},
            "last_name": {"type": "string", "description": "Person's last name."},
        },
        "required": ["domain", "first_name", "last_name"],
    },
}

EMAIL_VERIFIER_TOOL = {
    "name": "hunter_email_verifier",
    "description": (
        "Verify if an email address is valid and deliverable using Hunter.io. "
        "Returns status (valid/invalid/accept_all), confidence score, and details. "
        "Costs 1 Hunter verification credit per call."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "Email address to verify."},
        },
        "required": ["email"],
    },
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
)
def _hunter_request(endpoint: str, params: dict, api_key: str) -> dict:
    """Make a request to Hunter.io API."""
    params["api_key"] = api_key
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=15)

    if response.status_code == 429:
        raise requests.exceptions.ConnectionError("Hunter.io rate limited")
    if response.status_code == 402:
        return {"error": "Hunter.io quota exceeded. Consider upgrading your plan."}

    response.raise_for_status()
    return response.json()


def domain_search(domain: str, api_key: str, limit: int = 10, department: str = "") -> str:
    """Search for emails at a domain."""
    params = {"domain": domain, "limit": limit}
    if department:
        params["department"] = department

    try:
        data = _hunter_request("domain-search", params, api_key)
    except Exception as e:
        return json.dumps({"error": f"Hunter domain search failed: {e}"})

    if "error" in data:
        return json.dumps(data)

    emails = data.get("data", {}).get("emails", [])
    results = []
    for e in emails:
        results.append(
            {
                "email": e.get("value", ""),
                "type": e.get("type", ""),
                "confidence": e.get("confidence", 0),
                "first_name": e.get("first_name", ""),
                "last_name": e.get("last_name", ""),
                "position": e.get("position", ""),
                "department": e.get("department", ""),
                "linkedin": e.get("linkedin", ""),
            }
        )

    pattern = data.get("data", {}).get("pattern", "")
    return json.dumps(
        {
            "domain": domain,
            "email_pattern": pattern,
            "emails": results,
            "total": len(results),
        }
    )


def email_finder(domain: str, first_name: str, last_name: str, api_key: str) -> str:
    """Find a specific person's email."""
    try:
        data = _hunter_request(
            "email-finder",
            {"domain": domain, "first_name": first_name, "last_name": last_name},
            api_key,
        )
    except Exception as e:
        return json.dumps({"error": f"Hunter email finder failed: {e}"})

    if "error" in data:
        return json.dumps(data)

    result = data.get("data", {})
    return json.dumps(
        {
            "email": result.get("email", ""),
            "confidence": result.get("score", 0),
            "first_name": result.get("first_name", first_name),
            "last_name": result.get("last_name", last_name),
            "position": result.get("position", ""),
            "linkedin": result.get("linkedin", ""),
            "sources": len(result.get("sources", [])),
        }
    )


def email_verifier(email: str, api_key: str) -> str:
    """Verify an email address."""
    try:
        data = _hunter_request("email-verifier", {"email": email}, api_key)
    except Exception as e:
        return json.dumps({"error": f"Hunter email verifier failed: {e}"})

    if "error" in data:
        return json.dumps(data)

    result = data.get("data", {})
    return json.dumps(
        {
            "email": result.get("email", email),
            "status": result.get("status", "unknown"),
            "result": result.get("result", "unknown"),
            "score": result.get("score", 0),
            "regexp": result.get("regexp", False),
            "mx_records": result.get("mx_records", False),
            "smtp_server": result.get("smtp_server", False),
            "smtp_check": result.get("smtp_check", False),
            "accept_all": result.get("accept_all", False),
        }
    )

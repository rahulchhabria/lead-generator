"""Web search tool - uses Serper.dev when available, falls back to DuckDuckGo."""

from __future__ import annotations

import json
import logging

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

TOOL_DEFINITION = {
    "name": "web_search",
    "description": (
        "Search Google for information about companies, people, industries, or any topic. "
        "Returns titles, URLs, and snippets for each result."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific and targeted.",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 10, max: 20).",
                "default": 10,
            },
        },
        "required": ["query"],
    },
}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
)
def _serper_search(query: str, api_key: str, num_results: int = 10) -> list[dict]:
    """Search using Serper.dev Google Search API."""
    response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": min(num_results, 20)},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("organic", [])[:num_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return results


def _duckduckgo_search(query: str, num_results: int = 10) -> list[dict]:
    """Fallback: search using DuckDuckGo (no API key needed)."""
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )
        return results
    except ImportError:
        logger.warning("duckduckgo-search not installed. Install with: pip install duckduckgo-search")
        return [{"title": "Search unavailable", "url": "", "snippet": "No search API configured and duckduckgo-search is not installed."}]
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []


def execute(query: str, num_results: int = 10, serper_api_key: str = "") -> str:
    """Execute a web search and return formatted results."""
    if serper_api_key:
        try:
            results = _serper_search(query, serper_api_key, num_results)
        except Exception as e:
            logger.warning(f"Serper search failed, falling back to DuckDuckGo: {e}")
            results = _duckduckgo_search(query, num_results)
    else:
        results = _duckduckgo_search(query, num_results)

    if not results:
        return json.dumps({"results": [], "message": "No results found"})

    return json.dumps({"results": results, "count": len(results)})

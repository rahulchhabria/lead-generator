"""Web scraping tool - fetch and extract text content from URLs."""

from __future__ import annotations

import json
import logging
import re

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

TOOL_DEFINITION = {
    "name": "scrape_webpage",
    "description": (
        "Fetch a webpage and extract its main text content. "
        "Useful for reading company about pages, blog posts, bios, and articles. "
        "Returns cleaned text without navigation, ads, or footers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to scrape."},
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default: 5000).",
                "default": 5000,
            },
        },
        "required": ["url"],
    },
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
)
def _fetch_url(url: str) -> str:
    """Fetch a URL and return raw HTML."""
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=15,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def _extract_text(html: str, max_chars: int = 5000) -> str:
    """Extract readable text from HTML, removing nav/footer/script elements."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
        tag.decompose()

    # Try to find main content area
    main = soup.find("main") or soup.find("article") or soup.find(role="main")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"

    return text


def execute(url: str, max_chars: int = 5000) -> str:
    """Scrape a webpage and return its text content."""
    try:
        html = _fetch_url(url)
        text = _extract_text(html, max_chars)
        return json.dumps({"url": url, "content": text, "length": len(text)})
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        return json.dumps({"error": f"HTTP {status} fetching {url}", "url": url})
    except Exception as e:
        return json.dumps({"error": f"Failed to scrape {url}: {e}", "url": url})

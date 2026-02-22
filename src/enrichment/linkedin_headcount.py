"""Estimate engineering headcount via public signals."""
from __future__ import annotations

import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})


def estimate_engineering_headcount(company_name: str, domain: str) -> Optional[int]:
    """Estimate engineering headcount from public Google/LinkedIn search signals."""
    queries = [
        f'site:linkedin.com/in "{company_name}" engineer',
        f'site:linkedin.com/in "{company_name}" software developer',
    ]
    counts = []
    for query in queries:
        try:
            resp = SESSION.get(
                "https://www.google.com/search",
                params={"q": query},
                timeout=8,
            )
            if resp.status_code == 200:
                match = re.search(r"About ([\d,]+) results", resp.text)
                if match:
                    counts.append(int(match.group(1).replace(",", "")))
        except Exception as e:
            logger.debug(f"LinkedIn headcount estimate failed: {e}")

    if not counts:
        return None

    avg = sum(counts) // len(counts)
    # Apply 0.3 ratio heuristic (LinkedIn search vastly overcounts)
    estimate = max(1, int(avg * 0.3))
    return min(estimate, 10_000)

"""Main enrichment orchestrator. Collects data from all sources and synthesizes with Claude."""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Optional

import anthropic
import requests
from bs4 import BeautifulSoup

from .github_fetcher import fetch_github
from .job_scraper import scrape_jobs
from .linkedin_headcount import estimate_engineering_headcount
from .mobile_app_detector import detect_mobile_apps
from .models import (
    AIInsights,
    Acquisition,
    CompetitorMove,
    EnrichmentData,
    FundingRound,
    LeadershipPerson,
)
from .tech_detector import detect_technologies

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def _fetch_page(url: str, timeout: int = 10) -> tuple[Optional[str], dict]:
    try:
        resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text, dict(resp.headers)
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
    return None, {}


def _extract_text(html: str, max_chars: int = 8000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)[:max_chars]


def _extract_social_links(html: str) -> dict[str, Optional[str]]:
    result: dict[str, Optional[str]] = {
        "linkedin": None, "twitter": None, "github": None, "crunchbase": None
    }
    patterns = {
        "linkedin": r"https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9\-]+)",
        "twitter": r"https?://(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]+)",
        "github": r"https?://github\.com/([a-zA-Z0-9\-]+)",
        "crunchbase": r"https?://(?:www\.)?crunchbase\.com/organization/([a-zA-Z0-9\-]+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            result[key] = m.group(0)
    return result


def _ai_extract(client: anthropic.Anthropic, website_text: str, domain: str) -> dict:
    """Use Claude to extract structured company data from website text."""
    prompt = f"""Extract structured company information for domain: {domain}

Website content:
{website_text[:5000]}

Return ONLY a JSON object with these fields (use null for unknown):
{{
  "company_name": string,
  "description": string,
  "long_description": string,
  "founded_year": number | null,
  "employee_count": number | null,
  "employee_count_range": string | null,
  "hq_city": string | null,
  "hq_state": string | null,
  "hq_country": string | null,
  "industry": string | null,
  "industry_keywords": [strings],
  "total_funding_raised": string | null,
  "current_valuation": string | null,
  "latest_funding_round": {{"type": string, "amount": string, "date": string, "investors": [strings]}} | null,
  "all_funding_rounds": [],
  "ceo": {{"name": string, "linkedin_url": string | null}} | null,
  "founders": [{{"name": string, "role": string | null}}],
  "recent_news": [strings],
  "growth_stage": "Early Stage" | "Growth" | "Late Stage" | "Public" | null,
  "competitive_landscape": [strings],
  "key_differentiators": [strings],
  "recent_product_launches": [strings],
  "recent_acquisitions": [],
  "competitor_moves": []
}}"""

    try:
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        msg = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception as e:
        logger.warning(f"AI extraction failed for {domain}: {e}")
        return {}


def _compute_confidence(data: EnrichmentData) -> tuple[int, str]:
    score = 0
    if data.company_name:
        score += 10
    if data.description:
        score += 10
    if data.employee_count or data.employee_count_range:
        score += 10
    if data.total_funding_raised:
        score += 10
    if data.latest_funding_round:
        score += 10
    if data.hq_city or data.hq_country:
        score += 5
    if data.founded_year:
        score += 5
    if data.ceo:
        score += 5
    if data.technographic and data.technographic.all_technologies:
        score += 10
    if data.hiring and data.hiring.open_positions > 0:
        score += 10
    if data.github_activity:
        score += 5
    if data.ai_insights:
        score += 10

    score = min(score, 100)
    quality = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return score, quality


def enrich_domain(domain: str, company_name: Optional[str] = None) -> EnrichmentData:
    """
    Full company enrichment for a domain.
    Collects data from website, GitHub, job boards, and synthesizes with Claude AI.
    """
    domain = (
        domain.lower().strip()
        .removeprefix("http://")
        .removeprefix("https://")
        .removeprefix("www.")
        .rstrip("/")
    )

    data = EnrichmentData(domain=domain, company_name=company_name, website=f"https://{domain}")
    sources: list[str] = []
    html_content: Optional[str] = None
    headers: dict = {}

    # Parallel data collection
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            "website": executor.submit(_fetch_page, f"https://{domain}"),
            "github": executor.submit(fetch_github, company_name or domain.split(".")[0], domain),
        }
        if company_name:
            futures["jobs"] = executor.submit(scrape_jobs, domain, company_name)

        results: dict = {}
        for key, future in futures.items():
            try:
                results[key] = future.result(timeout=20)
            except Exception as e:
                logger.debug(f"Task {key} failed: {e}")
                results[key] = None

    # Website
    if results.get("website"):
        html_content, headers = results["website"]
        if html_content:
            sources.append(f"https://{domain}")

    # GitHub
    github_data = results.get("github")
    if github_data:
        data.github_activity = github_data
        if github_data.org_url:
            data.github_url = github_data.org_url
        sources.append("github.com")

    # Jobs
    hiring_data = results.get("jobs")
    if not hiring_data and company_name:
        try:
            hiring_data = scrape_jobs(domain, company_name)
        except Exception:
            pass
    if hiring_data and hiring_data.open_positions > 0:
        data.hiring = hiring_data
        sources.append("job_boards")

    if html_content:
        # Tech detection
        try:
            tech = detect_technologies(html_content, headers)
            if tech.all_technologies:
                data.technographic = tech
                sources.append("website_html")
        except Exception as e:
            logger.debug(f"Tech detection failed: {e}")

        # Mobile detection
        try:
            mobile = detect_mobile_apps(html_content)
            if mobile.has_ios_app or mobile.has_android_app:
                data.mobile_apps = mobile
        except Exception as e:
            logger.debug(f"Mobile detection failed: {e}")

        # Social links
        try:
            social = _extract_social_links(html_content)
            data.linkedin_url = social.get("linkedin")
            data.twitter_handle = social.get("twitter")
            if not data.github_url:
                data.github_url = social.get("github")
            data.crunchbase_url = social.get("crunchbase")
        except Exception as e:
            logger.debug(f"Social extraction failed: {e}")

        # AI synthesis
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            try:
                client = anthropic.Anthropic(api_key=anthropic_key)
                ai = _ai_extract(client, _extract_text(html_content), domain)
                sources.append("claude_ai")

                if not data.company_name and ai.get("company_name"):
                    data.company_name = ai["company_name"]
                data.description = ai.get("description") or data.description
                data.long_description = ai.get("long_description")
                data.founded_year = ai.get("founded_year")
                data.employee_count = ai.get("employee_count")
                data.employee_count_range = ai.get("employee_count_range")
                data.hq_city = ai.get("hq_city")
                data.hq_state = ai.get("hq_state")
                data.hq_country = ai.get("hq_country")
                data.industry = ai.get("industry")
                data.industry_keywords = ai.get("industry_keywords", [])
                data.total_funding_raised = ai.get("total_funding_raised")
                data.current_valuation = ai.get("current_valuation")

                if ai.get("latest_funding_round") and isinstance(ai["latest_funding_round"], dict):
                    fr = ai["latest_funding_round"]
                    data.latest_funding_round = FundingRound(
                        type=fr.get("type"), amount=fr.get("amount"),
                        date=fr.get("date"), investors=fr.get("investors", []),
                    )
                data.all_funding_rounds = [
                    FundingRound(**fr)
                    for fr in ai.get("all_funding_rounds", [])
                    if isinstance(fr, dict)
                ]

                if ai.get("ceo") and isinstance(ai["ceo"], dict):
                    data.ceo = LeadershipPerson(
                        name=ai["ceo"].get("name", ""),
                        linkedin_url=ai["ceo"].get("linkedin_url"),
                    )
                data.founders = [
                    LeadershipPerson(**f)
                    for f in ai.get("founders", [])
                    if isinstance(f, dict) and f.get("name")
                ]

                data.ai_insights = AIInsights(
                    recent_news=ai.get("recent_news", []),
                    growth_stage=ai.get("growth_stage"),
                    competitive_landscape=ai.get("competitive_landscape", []),
                    key_differentiators=ai.get("key_differentiators", []),
                    recent_product_launches=ai.get("recent_product_launches", []),
                    recent_acquisitions=[
                        Acquisition(**a) for a in ai.get("recent_acquisitions", [])
                        if isinstance(a, dict)
                    ],
                    competitor_moves=[
                        CompetitorMove(**m) for m in ai.get("competitor_moves", [])
                        if isinstance(m, dict)
                    ],
                )
            except Exception as e:
                logger.warning(f"AI extraction error for {domain}: {e}")

    # Engineering headcount estimation
    if not data.engineering_count and data.company_name:
        try:
            data.engineering_count = estimate_engineering_headcount(data.company_name, domain)
        except Exception:
            pass

    # Fallback company name
    if not data.company_name:
        data.company_name = company_name or domain.split(".")[0].replace("-", " ").title()

    data.sources = list(set(sources))
    data.confidence_score, data.data_quality = _compute_confidence(data)
    return data

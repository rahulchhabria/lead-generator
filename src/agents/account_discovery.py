"""Agent 1: Account Discovery - ICP definition → list of target companies."""

from __future__ import annotations

import json
import logging
from typing import Callable

from src.agents.base import BaseAgent
from src.config import APIConfig
from src.models import Account, ICPDefinition
from src.tools import web_search, web_scraper

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a B2B account research specialist. Given an Ideal Customer Profile (ICP), \
use web search to discover companies that match the criteria.

For each company you discover, provide:
- company_name: The company's name
- domain: Their primary website domain (e.g. "acme.io")
- industry: Their industry/sector
- employee_count: Approximate size (e.g. "50-200", "200-500")
- location: Headquarters location
- description: Brief 1-2 sentence description
- relevance_reasoning: Why this company matches the ICP (be specific)

Search strategically:
1. Search for companies by industry + size + geography
2. Look for competitor lists, "companies like X" articles, and industry reports
3. Check funding announcements for companies matching the profile
4. Search for technology-specific directories if the ICP mentions tech stack
5. Scrape relevant pages for more details when needed

IMPORTANT: Return your findings as a valid JSON array of objects. Each object must have \
the fields listed above. Return ONLY the JSON array, no markdown code fences or other text.

Aim for {max_leads} companies. Quality over quantity - each company should clearly match the ICP."""


def build_user_message(icp: ICPDefinition) -> str:
    """Build the input message for the discovery agent."""
    parts = [f"Find companies matching this Ideal Customer Profile:\n\n{icp.description}"]

    if icp.target_roles:
        parts.append(f"\nTarget roles at these companies: {', '.join(icp.target_roles)}")
    if icp.company_size:
        parts.append(f"Company size: {icp.company_size}")
    if icp.industries:
        parts.append(f"Industries: {', '.join(icp.industries)}")
    if icp.geographies:
        parts.append(f"Geographies: {', '.join(icp.geographies)}")
    if icp.technologies:
        parts.append(f"Technologies: {', '.join(icp.technologies)}")
    if icp.exclusions:
        parts.append(f"Exclude these companies/domains: {', '.join(icp.exclusions)}")

    parts.append(f"\nFind approximately {icp.max_leads} companies.")

    return "\n".join(parts)


def build_tools(api_config: APIConfig) -> tuple[list[dict], dict[str, Callable]]:
    """Build tool definitions and handlers for this agent."""
    tools = [web_search.TOOL_DEFINITION, web_scraper.TOOL_DEFINITION]

    handlers = {
        "web_search": lambda query, num_results=10: web_search.execute(
            query, num_results, api_config.serper_api_key
        ),
        "scrape_webpage": lambda url, max_chars=5000: web_scraper.execute(url, max_chars),
    }

    return tools, handlers


def run(agent: BaseAgent, icp: ICPDefinition, api_config: APIConfig) -> list[Account]:
    """Run the account discovery agent.

    Returns a list of Account objects discovered by the agent.
    """
    tools, handlers = build_tools(api_config)
    system = SYSTEM_PROMPT.format(max_leads=icp.max_leads)
    user_msg = build_user_message(icp)

    logger.info(f"Running account discovery for {icp.max_leads} leads")
    raw_response = agent.run(system, user_msg, tools, handlers, max_tokens=8192)

    return parse_accounts(raw_response, icp)


def parse_accounts(response: str, icp: ICPDefinition) -> list[Account]:
    """Parse the agent's JSON response into Account objects."""
    # Try to extract JSON from the response
    text = response.strip()

    # Handle markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON array in the text
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse account discovery response: {text[:500]}")
                return []
        else:
            logger.error(f"No JSON array found in response: {text[:500]}")
            return []

    if not isinstance(data, list):
        data = [data]

    accounts = []
    exclusions = {e.lower() for e in icp.exclusions}

    for item in data:
        domain = item.get("domain", "").lower().strip()
        if not domain:
            continue
        if domain in exclusions:
            continue

        accounts.append(
            Account(
                company_name=item.get("company_name", item.get("name", "Unknown")),
                domain=domain,
                industry=item.get("industry"),
                employee_count=item.get("employee_count"),
                location=item.get("location"),
                description=item.get("description"),
                relevance_reasoning=item.get("relevance_reasoning", ""),
                data_sources=["web_search"],
                source="discovered",
            )
        )

    logger.info(f"Discovered {len(accounts)} accounts")
    return accounts

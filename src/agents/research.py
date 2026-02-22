"""Agent 3: Personalization Research - contacts → personalization dossiers."""

from __future__ import annotations

import json
import logging
from typing import Callable

from src.agents.base import BaseAgent
from src.config import APIConfig
from src.models import Account, Contact, PersonalizationDossier
from src.tools import github_api, web_search, web_scraper

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a personalization research specialist. Given a contact and their company, \
research their public online presence to find genuine personalization hooks for a cold email.

Research areas (find what you can, not all will be available):
- GitHub activity: repos, contributions, languages, open source work
- Blog posts or articles they've written
- Conference talks or speaking engagements
- Education background
- Professional interests and expertise areas
- Community involvement (meetups, forums, etc.)
- Recent company news or announcements they might care about

IMPORTANT RULES:
1. Only use publicly available information
2. Cite the source for every data point you find
3. Focus on genuine interests, not surface-level details
4. Look for conversation starters, not just facts
5. If you find their GitHub username, always check their repos for interesting projects

Return your findings as a valid JSON object with these fields:
- github_username: Their GitHub username if found (string or null)
- github_repos: Notable repos [list of strings like "repo-name: description"]
- github_languages: Programming languages they use [list of strings]
- recent_posts: Blog posts or articles [list of strings like "Title - URL"]
- interests: Professional interests [list of strings]
- education: Education background (string or null)
- open_source_contributions: OSS contributions [list of strings]
- speaking_engagements: Talks or conferences [list of strings]
- personal_details: Other notable public details [list of strings]
- data_sources: URLs/sources for all findings [list of strings]
- raw_research_notes: Freeform summary of what you found (string)

Return ONLY the JSON object, no markdown code fences or other text.
Quality matters more than quantity - one genuine insight beats ten generic facts."""


def build_tools(api_config: APIConfig) -> tuple[list[dict], dict[str, Callable]]:
    """Build tool definitions and handlers for research agent."""
    tools = [
        web_search.TOOL_DEFINITION,
        web_scraper.TOOL_DEFINITION,
        github_api.USER_INFO_TOOL,
        github_api.USER_REPOS_TOOL,
    ]

    handlers: dict[str, Callable] = {
        "web_search": lambda query, num_results=10: web_search.execute(
            query, num_results, api_config.serper_api_key
        ),
        "scrape_webpage": lambda url, max_chars=5000: web_scraper.execute(url, max_chars),
        "github_user_info": lambda username: github_api.user_info(
            username, api_config.github_token
        ),
        "github_user_repos": lambda username, sort="updated", limit=10: github_api.user_repos(
            username, api_config.github_token, sort, limit
        ),
    }

    return tools, handlers


def build_user_message(contact: Contact, account: Account) -> str:
    """Build the input message for the research agent."""
    parts = [
        "Research this person for email personalization:",
        f"  Name: {contact.full_name}",
        f"  Title: {contact.title or 'Unknown'}",
        f"  Email: {contact.email or 'Unknown'}",
        f"  Company: {account.company_name} ({account.domain})",
    ]
    if account.industry:
        parts.append(f"  Industry: {account.industry}")
    if contact.linkedin_url:
        parts.append(f"  LinkedIn: {contact.linkedin_url}")

    parts.append(
        "\nFind genuine personalization hooks - things that show you "
        "actually know who they are and what they care about."
    )

    return "\n".join(parts)


def run(
    agent: BaseAgent,
    contact: Contact,
    account: Account,
    api_config: APIConfig,
) -> PersonalizationDossier:
    """Run the personalization research agent for a single contact.

    Returns a PersonalizationDossier with research findings.
    """
    tools, handlers = build_tools(api_config)
    user_msg = build_user_message(contact, account)

    logger.info(f"Researching {contact.full_name} at {account.company_name}")
    raw_response = agent.run(SYSTEM_PROMPT, user_msg, tools, handlers, max_tokens=4096)

    return parse_dossier(raw_response, contact)


def parse_dossier(response: str, contact: Contact) -> PersonalizationDossier:
    """Parse the agent's JSON response into a PersonalizationDossier."""
    text = response.strip()

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse research response for {contact.full_name}: {text[:500]}")
                return PersonalizationDossier(
                    raw_research_notes=f"Failed to parse research. Raw response: {text[:1000]}",
                    data_sources=["web_search"],
                )
        else:
            logger.error(f"No JSON object in research response for {contact.full_name}: {text[:500]}")
            return PersonalizationDossier(
                raw_research_notes=f"No structured data found. Raw response: {text[:1000]}",
                data_sources=["web_search"],
            )

    return PersonalizationDossier(
        github_username=data.get("github_username"),
        github_repos=data.get("github_repos", []),
        github_languages=data.get("github_languages", []),
        recent_posts=data.get("recent_posts", []),
        interests=data.get("interests", []),
        education=data.get("education"),
        open_source_contributions=data.get("open_source_contributions", []),
        speaking_engagements=data.get("speaking_engagements", []),
        personal_details=data.get("personal_details", []),
        raw_research_notes=data.get("raw_research_notes", ""),
        data_sources=data.get("data_sources", ["web_search"]),
    )

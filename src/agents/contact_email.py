"""Agent 2: Contact & Email Finder - approved accounts → contacts with emails."""

from __future__ import annotations

import json
import logging
from typing import Callable

from src.agents.base import BaseAgent
from src.config import APIConfig
from src.models import Account, Contact
from src.tools import email_patterns, email_verifier, hunter, web_search, web_scraper

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a B2B contact finder. Given a target company and desired roles, \
find real people who work there and discover their email addresses.

For each contact you find, provide:
- first_name: Their first name
- last_name: Their last name
- title: Their job title
- email: Their email address (best guess if not confirmed)
- email_confidence: 0-100 confidence score
- email_source: How you found/derived the email
- linkedin_url: LinkedIn profile URL if found

{email_strategy}

Research strategy:
1. Search for the company + target roles to find people
2. Look at company team/about pages
3. Check LinkedIn profiles mentioned in search results
4. For each person found, determine their email address
5. Verify emails when possible

IMPORTANT: Return your findings as a valid JSON array of objects with the fields above. \
Return ONLY the JSON array, no markdown code fences or other text.

Find contacts matching these roles: {target_roles}"""

HUNTER_STRATEGY = """Email discovery strategy (Hunter.io available):
1. First try hunter_domain_search to find known emails at the domain
2. If you find the target person, use their email directly
3. If not, use hunter_email_finder with the person's name + domain
4. As a fallback, generate_email_patterns + hunter_email_verifier
5. Mark email_source as 'hunter_domain', 'hunter_finder', or 'hunter_verified_pattern'"""

FREE_STRATEGY = """Email discovery strategy (free mode - no Hunter.io):
1. Search the web for the person's email (company pages, conference talks, etc.)
2. Use generate_email_patterns to create candidate emails
3. Use verify_email_dns to check if the domain accepts email
4. The most common B2B pattern is first.last@domain.com
5. Mark email_source as 'web_found', 'pattern_dns', or 'pattern_guessed'
6. Set confidence lower for pattern-guessed emails (30-50) vs web-found (60-80)"""


def build_tools(api_config: APIConfig) -> tuple[list[dict], dict[str, Callable]]:
    """Build tool definitions and handlers, adapting to available APIs."""
    tools = [
        web_search.TOOL_DEFINITION,
        web_scraper.TOOL_DEFINITION,
        email_patterns.TOOL_DEFINITION,
        email_verifier.TOOL_DEFINITION,
    ]

    handlers: dict[str, Callable] = {
        "web_search": lambda query, num_results=10: web_search.execute(
            query, num_results, api_config.serper_api_key
        ),
        "scrape_webpage": lambda url, max_chars=5000: web_scraper.execute(url, max_chars),
        "generate_email_patterns": lambda first_name, last_name, domain: email_patterns.execute(
            first_name, last_name, domain
        ),
        "verify_email_dns": lambda email: email_verifier.execute(email),
    }

    if api_config.has_hunter:
        tools.extend([
            hunter.DOMAIN_SEARCH_TOOL,
            hunter.EMAIL_FINDER_TOOL,
            hunter.EMAIL_VERIFIER_TOOL,
        ])
        handlers.update({
            "hunter_domain_search": lambda domain, limit=10, department="": hunter.domain_search(
                domain, api_config.hunter_api_key, limit, department
            ),
            "hunter_email_finder": lambda domain, first_name, last_name: hunter.email_finder(
                domain, first_name, last_name, api_config.hunter_api_key
            ),
            "hunter_email_verifier": lambda email: hunter.email_verifier(
                email, api_config.hunter_api_key
            ),
        })

    return tools, handlers


def build_user_message(account: Account, target_roles: list[str]) -> str:
    """Build the input message for the contact finder agent."""
    parts = [
        "Find contacts at this company:",
        f"  Company: {account.company_name}",
        f"  Domain: {account.domain}",
    ]
    if account.industry:
        parts.append(f"  Industry: {account.industry}")
    if account.employee_count:
        parts.append(f"  Size: {account.employee_count}")
    if account.location:
        parts.append(f"  Location: {account.location}")
    if account.description:
        parts.append(f"  Description: {account.description}")

    roles_str = ", ".join(target_roles) if target_roles else "senior leadership, decision makers"
    parts.append(f"\nTarget roles: {roles_str}")
    parts.append("\nFind 1-3 contacts matching the target roles.")

    return "\n".join(parts)


def run(
    agent: BaseAgent,
    account: Account,
    target_roles: list[str],
    api_config: APIConfig,
) -> list[Contact]:
    """Run the contact & email finder for a single account.

    Returns a list of Contact objects found at the company.
    """
    tools, handlers = build_tools(api_config)

    email_strategy = HUNTER_STRATEGY if api_config.has_hunter else FREE_STRATEGY
    roles_str = ", ".join(target_roles) if target_roles else "senior leadership"
    system = SYSTEM_PROMPT.format(email_strategy=email_strategy, target_roles=roles_str)
    user_msg = build_user_message(account, target_roles)

    logger.info(f"Finding contacts at {account.domain}")
    raw_response = agent.run(system, user_msg, tools, handlers, max_tokens=4096)

    return parse_contacts(raw_response, account)


def parse_contacts(response: str, account: Account) -> list[Contact]:
    """Parse the agent's JSON response into Contact objects."""
    text = response.strip()

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse contact response for {account.domain}: {text[:500]}")
                return []
        else:
            logger.error(f"No JSON array in contact response for {account.domain}: {text[:500]}")
            return []

    if not isinstance(data, list):
        data = [data]

    contacts = []
    for item in data:
        first_name = item.get("first_name", "").strip()
        last_name = item.get("last_name", "").strip()
        if not first_name or not last_name:
            continue

        contacts.append(
            Contact(
                first_name=first_name,
                last_name=last_name,
                title=item.get("title"),
                email=item.get("email"),
                email_confidence=item.get("email_confidence"),
                email_verified=item.get("email_verified", False),
                email_source=item.get("email_source", "unknown"),
                linkedin_url=item.get("linkedin_url"),
                data_sources=["web_search", "hunter" if "hunter" in item.get("email_source", "") else "pattern"],
            )
        )

    logger.info(f"Found {len(contacts)} contacts at {account.domain}")
    return contacts

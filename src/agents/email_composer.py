"""Agent 4: Email Composer - dossiers → personalized cold emails."""

from __future__ import annotations

import json
import logging

from src.agents.base import BaseAgent
from src.models import (
    Account,
    CampaignConfig,
    Contact,
    DraftEmail,
    PersonalizationDossier,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a cold email copywriter who writes genuinely personalized outreach emails. \
You craft emails that feel like they were written by a real person who took the time to learn about the recipient.

Rules:
1. Under {max_words} words (body only, excluding signature)
2. Start with a personalization hook based on the research dossier
3. The hook must be SPECIFIC - reference something real about them (a repo, a post, a talk, etc.)
4. One clear CTA: {cta_type}
5. Tone: {tone} - write like a smart person sending a quick note, not a marketer
6. NO generic compliments ("I was impressed by your work")
7. NO superlatives or hype words
8. NO bullet points or formatted lists in the body
9. Keep it conversational - one or two short paragraphs max
10. End with the provided unsubscribe text and physical address

Sender info:
- Name: {sender_name}
- Title: {sender_title}
- Company: {sender_company}
- Value proposition: {value_proposition}

Return your output as a valid JSON object with:
- subject_line: Email subject (under 60 chars, no clickbait)
- body: Full email body including greeting and sign-off
- personalization_hooks: List of specific hooks you used [list of strings]

Return ONLY the JSON object, no markdown code fences or other text."""


def build_user_message(
    contact: Contact,
    account: Account,
    dossier: PersonalizationDossier,
    config: CampaignConfig,
) -> str:
    """Build the input message for the email composer."""
    parts = [
        "Write a cold email for this contact:",
        "\nRecipient:",
        f"  Name: {contact.full_name}",
        f"  Title: {contact.title or 'Unknown'}",
        f"  Company: {account.company_name} ({account.domain})",
    ]

    if account.industry:
        parts.append(f"  Industry: {account.industry}")

    parts.append("\nPersonalization Research:")

    if dossier.github_username:
        parts.append(f"  GitHub: github.com/{dossier.github_username}")
    if dossier.github_repos:
        parts.append(f"  Notable repos: {', '.join(dossier.github_repos[:5])}")
    if dossier.github_languages:
        parts.append(f"  Languages: {', '.join(dossier.github_languages[:5])}")
    if dossier.recent_posts:
        parts.append(f"  Recent posts/articles: {'; '.join(dossier.recent_posts[:3])}")
    if dossier.interests:
        parts.append(f"  Interests: {', '.join(dossier.interests[:5])}")
    if dossier.education:
        parts.append(f"  Education: {dossier.education}")
    if dossier.open_source_contributions:
        parts.append(f"  OSS contributions: {', '.join(dossier.open_source_contributions[:3])}")
    if dossier.speaking_engagements:
        parts.append(f"  Speaking: {', '.join(dossier.speaking_engagements[:3])}")
    if dossier.personal_details:
        parts.append(f"  Other details: {', '.join(dossier.personal_details[:3])}")
    if dossier.raw_research_notes:
        parts.append(f"  Research notes: {dossier.raw_research_notes[:500]}")

    parts.append("\nUnsubscribe footer to include at the end:")
    parts.append(f"  {config.unsubscribe_text}")
    parts.append(f"  {config.physical_address}")

    return "\n".join(parts)


def run(
    agent: BaseAgent,
    contact: Contact,
    account: Account,
    dossier: PersonalizationDossier,
    config: CampaignConfig,
) -> DraftEmail:
    """Run the email composer for a single contact.

    Returns a DraftEmail with the composed email.
    """
    system = SYSTEM_PROMPT.format(
        max_words=config.max_words,
        cta_type=config.cta_type,
        tone=config.tone,
        sender_name=config.sender_name,
        sender_title=config.sender_title,
        sender_company=config.sender_company,
        value_proposition=config.value_proposition or "not specified - craft based on context",
    )

    user_msg = build_user_message(contact, account, dossier, config)

    logger.info(f"Composing email for {contact.full_name}")
    raw_response = agent.generate(system, user_msg, max_tokens=2048)

    return parse_email(raw_response, config)


def parse_email(response: str, config: CampaignConfig) -> DraftEmail:
    """Parse the agent's JSON response into a DraftEmail."""
    text = response.strip()

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                logger.error(f"Failed to parse email response: {text[:500]}")
                return DraftEmail(
                    subject_line="[PARSE ERROR] Review needed",
                    body=text[:2000],
                    personalization_hooks=[],
                    tone=config.tone,
                )
        else:
            logger.error(f"No JSON object in email response: {text[:500]}")
            return DraftEmail(
                subject_line="[PARSE ERROR] Review needed",
                body=text[:2000],
                personalization_hooks=[],
                tone=config.tone,
            )

    body = data.get("body", "")

    # Check for unsubscribe text
    has_unsub = config.unsubscribe_text.lower()[:20] in body.lower() if body else False
    has_addr = config.physical_address.lower()[:20] in body.lower() if body else False

    return DraftEmail(
        subject_line=data.get("subject_line", "No subject"),
        body=body,
        personalization_hooks=data.get("personalization_hooks", []),
        tone=config.tone,
        includes_unsubscribe=has_unsub,
        includes_physical_address=has_addr,
    )

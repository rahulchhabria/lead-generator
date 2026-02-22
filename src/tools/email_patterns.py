"""Email pattern generation - creates candidate email addresses for a person at a domain."""

from __future__ import annotations

import json

TOOL_DEFINITION = {
    "name": "generate_email_patterns",
    "description": (
        "Generate common email pattern variations for a person at a company domain. "
        "Returns a list of candidate email addresses to test/verify. "
        "Use this when you know someone's name and company but not their email."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "first_name": {"type": "string", "description": "Person's first name."},
            "last_name": {"type": "string", "description": "Person's last name."},
            "domain": {"type": "string", "description": "Company domain (e.g. 'acme.com')."},
        },
        "required": ["first_name", "last_name", "domain"],
    },
}


def execute(first_name: str, last_name: str, domain: str) -> str:
    """Generate email pattern candidates."""
    first = first_name.lower().strip()
    last = last_name.lower().strip()
    domain = domain.lower().strip()

    if not first or not last or not domain:
        return json.dumps({"error": "first_name, last_name, and domain are all required"})

    patterns = [
        f"{first}.{last}@{domain}",
        f"{first}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}{last[0]}@{domain}",
        f"{first}{last}@{domain}",
        f"{last}.{first}@{domain}",
        f"{first}_{last}@{domain}",
        f"{first[0]}.{last}@{domain}",
        f"{first}-{last}@{domain}",
        f"{last}@{domain}",
    ]

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return json.dumps(
        {
            "first_name": first_name,
            "last_name": last_name,
            "domain": domain,
            "patterns": unique,
            "count": len(unique),
            "note": "Most common B2B pattern is first.last@domain. Verify before using.",
        }
    )

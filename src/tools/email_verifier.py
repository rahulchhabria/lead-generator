"""Free email verification using DNS MX record lookups.

Fallback when Hunter.io is not configured. Checks:
1. Valid email syntax
2. Domain has MX records (can receive email)
3. Domain is not a known disposable email provider

Does NOT do SMTP verification (risky for sender reputation).
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

TOOL_DEFINITION = {
    "name": "verify_email_dns",
    "description": (
        "Verify an email address using free DNS checks. "
        "Checks syntax validity and whether the domain has mail servers (MX records). "
        "Does NOT verify if the specific mailbox exists. "
        "Use this when Hunter.io is not available."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "Email address to verify."},
        },
        "required": ["email"],
    },
}

# Minimal set of known disposable email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "10minutemail.com", "trashmail.com", "yopmail.com", "sharklasers.com",
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _check_mx_records(domain: str) -> tuple[bool, list[str]]:
    """Check if domain has MX records."""
    try:
        import dns.resolver

        answers = dns.resolver.resolve(domain, "MX")
        mx_hosts = [str(r.exchange).rstrip(".") for r in answers]
        return True, mx_hosts
    except ImportError:
        logger.warning("dnspython not installed. Install with: pip install dnspython")
        return False, ["dnspython not installed - cannot check MX"]
    except Exception:
        return False, []


def execute(email: str) -> str:
    """Verify an email address using DNS checks."""
    email = email.strip().lower()

    # Syntax check
    if not EMAIL_REGEX.match(email):
        return json.dumps(
            {
                "email": email,
                "valid_syntax": False,
                "has_mx": False,
                "confidence": 0,
                "reason": "Invalid email syntax",
            }
        )

    domain = email.split("@")[1]

    # Disposable check
    if domain in DISPOSABLE_DOMAINS:
        return json.dumps(
            {
                "email": email,
                "valid_syntax": True,
                "has_mx": True,
                "is_disposable": True,
                "confidence": 0,
                "reason": "Disposable email domain",
            }
        )

    # MX record check
    has_mx, mx_hosts = _check_mx_records(domain)

    if has_mx:
        confidence = 40  # Syntax OK + MX exists, but mailbox unverified
        reason = "Syntax valid, domain has mail servers. Mailbox not verified."
    else:
        confidence = 10
        reason = "Domain may not accept email (no MX records found)."

    return json.dumps(
        {
            "email": email,
            "valid_syntax": True,
            "has_mx": has_mx,
            "mx_hosts": mx_hosts[:3],
            "is_disposable": False,
            "confidence": confidence,
            "reason": reason,
        }
    )

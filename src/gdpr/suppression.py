"""Suppression list management - opt-outs, bounces, manual suppression."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.database import Database

logger = logging.getLogger(__name__)


def add_suppression(db: Database, email: str, reason: str = "manual"):
    """Add a single email to the suppression list."""
    db.add_to_suppression(email, reason)
    logger.info(f"Suppressed: {email} (reason: {reason})")


def bulk_suppress_from_csv(db: Database, csv_path: str, reason: str = "bulk_import"):
    """Import a CSV of emails to suppress (one email per row or 'email' column)."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Suppression file not found: {csv_path}")

    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        # Detect if it's a simple list or has headers
        sample = f.read(1024)
        f.seek(0)

        if "," in sample.split("\n")[0]:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get("email", "").strip().lower()
                if email:
                    db.add_to_suppression(email, reason)
                    count += 1
        else:
            for line in f:
                email = line.strip().lower()
                if email and "@" in email:
                    db.add_to_suppression(email, reason)
                    count += 1

    logger.info(f"Bulk suppressed {count} emails from {csv_path}")
    return count


def is_suppressed(db: Database, email: str) -> bool:
    """Check if an email is suppressed."""
    return db.is_suppressed(email)


def handle_bounce(db: Database, email: str):
    """Mark an email as bounced (suppress future sends)."""
    add_suppression(db, email, "bounced")


def handle_unsubscribe(db: Database, email: str):
    """Process an unsubscribe request."""
    add_suppression(db, email, "unsubscribed")
    db.log_gdpr_action(email, "unsubscribed", "email", "user_request")

"""GDPR compliance utilities - data source logging and audit trail."""

from __future__ import annotations

import logging

from src.database import Database

logger = logging.getLogger(__name__)


def log_data_collection(
    db: Database,
    email: str,
    field: str,
    source: str,
):
    """Log a data collection event for GDPR audit trail.

    Args:
        db: Database instance.
        email: Contact's email (or identifier).
        field: What data was collected (e.g. 'email', 'company_info', 'github_profile').
        source: Where it came from (e.g. 'hunter.io', 'web_search', 'github_api').
    """
    db.log_gdpr_action(email, "collected", field, source)


def log_data_usage(
    db: Database,
    email: str,
    usage: str,
):
    """Log how data was used (e.g. 'email_composed', 'exported_csv')."""
    db.log_gdpr_action(email, "used", usage, "pipeline")


def log_data_deletion(
    db: Database,
    email: str,
):
    """Log that data was deleted per GDPR request."""
    db.log_gdpr_action(email, "deleted", "all", "user_request")


def check_suppression(db: Database, email: str) -> bool:
    """Check if an email is on the suppression list.

    Returns True if the email should NOT be contacted.
    """
    return db.is_suppressed(email)


def forget_contact(db: Database, email: str):
    """Execute GDPR right-to-be-forgotten.

    Deletes all data for the email and adds it to suppression list.
    """
    logger.info(f"GDPR deletion request for {email}")
    db.forget_contact(email)
    logger.info(f"All data deleted for {email}, added to suppression list")

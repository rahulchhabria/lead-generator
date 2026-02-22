"""CSV export for approved leads."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.database import Database

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "first_name",
    "last_name",
    "email",
    "email_confidence",
    "email_verified",
    "title",
    "company",
    "domain",
    "industry",
    "company_size",
    "location",
    "linkedin_url",
    "github_url",
    "subject_line",
    "email_body",
    "personalization_hooks",
    "data_sources",
    "campaign_id",
]


def export_csv(db: Database, campaign_id: str, output_path: str | None = None) -> str:
    """Export approved leads to CSV.

    Args:
        db: Database instance.
        campaign_id: Campaign to export.
        output_path: Custom output path. Defaults to output/<campaign_id>.csv.

    Returns:
        Path to the exported CSV file.
    """
    if not output_path:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / f"{campaign_id}.csv")

    data = db.get_export_data(campaign_id)

    if not data:
        logger.warning(f"No approved leads to export for campaign {campaign_id}")
        return ""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(data)

    logger.info(f"Exported {len(data)} leads to {output_path}")
    return output_path

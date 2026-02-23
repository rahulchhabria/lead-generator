"""Export API routes."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.web.auth import get_current_user

router = APIRouter(tags=["exports"])


def _get_db():
    from src.config import load_api_config
    from src.database import Database
    api_config = load_api_config()
    return Database(api_config.db_path)


@router.get("/{campaign_id}/csv")
def export_campaign_csv(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Export approved leads for a campaign as CSV."""
    db = _get_db()
    try:
        campaign = db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        owner = db.get_campaign_owner(campaign_id)
        if owner and owner != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        rows = db.get_export_data(campaign_id)
        if not rows:
            raise HTTPException(status_code=404, detail="No approved leads to export")

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=campaign_{campaign_id}.csv"},
        )
    finally:
        db.close()


@router.get("/enrichment/csv")
def export_enrichment_csv(current_user: dict = Depends(get_current_user)):
    """Export enrichment data for the team as CSV."""
    db = _get_db()
    try:
        records = db.list_enrichments(limit=10000, team_id=current_user["team_id"])
        if not records:
            raise HTTPException(status_code=404, detail="No enrichment data found")

        flat_rows = []
        for r in records:
            flat_rows.append({
                "domain": r.get("domain"),
                "company_name": r.get("company_name"),
                "description": r.get("description"),
                "founded_year": r.get("founded_year"),
                "employee_count": r.get("employee_count"),
                "employee_count_range": r.get("employee_count_range"),
                "engineering_count": r.get("engineering_count"),
                "industry": r.get("industry"),
                "hq_city": r.get("hq_city"),
                "hq_country": r.get("hq_country"),
                "total_funding_raised": r.get("total_funding_raised"),
                "growth_stage": (r.get("ai_insights") or {}).get("growth_stage"),
                "tech_stack": ", ".join((r.get("technographic") or {}).get("all_technologies", [])),
                "open_positions": (r.get("hiring") or {}).get("open_positions", 0),
                "linkedin_url": r.get("linkedin_url"),
                "github_url": r.get("github_url"),
                "data_quality": r.get("data_quality"),
                "confidence_score": r.get("confidence_score"),
                "last_enriched_at": r.get("last_enriched_at"),
            })

        output = io.StringIO()
        if flat_rows:
            writer = csv.DictWriter(output, fieldnames=flat_rows[0].keys())
            writer.writeheader()
            writer.writerows(flat_rows)
        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=enrichment_export.csv"},
        )
    finally:
        db.close()

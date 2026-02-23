"""Account management API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.web.auth import get_current_user

router = APIRouter(tags=["accounts"])


def _get_db():
    from src.config import load_api_config
    from src.database import Database
    api_config = load_api_config()
    return Database(api_config.db_path)


def _enriched_domains(db, team_id: str) -> set[str]:
    try:
        rows = db.conn.execute(
            "SELECT domain FROM enrichment_data WHERE team_id = ?", (team_id,)
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


@router.get("/")
def list_accounts(campaign_id: Optional[str] = None, status: Optional[str] = None,
                  limit: int = 100, current_user: dict = Depends(get_current_user)):
    """List accounts, optionally filtered by campaign or status."""
    from src.models import LeadStatus
    db = _get_db()
    try:
        if campaign_id:
            owner = db.get_campaign_owner(campaign_id)
            if owner is None or owner != current_user["id"]:
                raise HTTPException(status_code=403, detail="Access denied")
            st = LeadStatus(status) if status else None
            accounts = db.get_accounts(campaign_id, st)
        else:
            accounts = db.get_all_accounts(limit=limit, user_id=current_user["id"])

        enriched = _enriched_domains(db, current_user["team_id"])
        return [
            {
                "id": a.id, "campaign_id": a.campaign_id, "company_name": a.company_name,
                "domain": a.domain, "industry": a.industry, "employee_count": a.employee_count,
                "location": a.location, "description": a.description,
                "status": a.status.value, "source": a.source,
                "has_enrichment": a.domain in enriched,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in accounts
        ]
    finally:
        db.close()


@router.get("/{account_id}")
def get_account(account_id: int, current_user: dict = Depends(get_current_user)):
    """Get account with full enrichment data and contacts."""
    db = _get_db()
    try:
        account = db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        owner = db.get_campaign_owner(account.campaign_id)
        if owner is None or owner != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        result = {
            "id": account.id, "campaign_id": account.campaign_id,
            "company_name": account.company_name, "domain": account.domain,
            "industry": account.industry, "employee_count": account.employee_count,
            "location": account.location, "description": account.description,
            "relevance_reasoning": account.relevance_reasoning,
            "status": account.status.value, "source": account.source,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        }

        result["enrichment"] = db.get_enrichment(account.domain, team_id=current_user["team_id"])

        contacts = db.get_contacts_for_account(account_id)
        result["contacts"] = [
            {
                "id": c.id, "full_name": c.full_name, "title": c.title,
                "email": c.email, "email_confidence": c.email_confidence,
                "email_verified": c.email_verified, "status": c.status.value,
                "linkedin_url": c.linkedin_url,
            }
            for c in contacts
        ]

        return result
    finally:
        db.close()


@router.post("/{account_id}/enrich")
def trigger_enrichment(account_id: int, current_user: dict = Depends(get_current_user)):
    """Trigger enrichment for a specific account."""
    from src.web.background import job_manager

    db = _get_db()
    try:
        account = db.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        owner = db.get_campaign_owner(account.campaign_id)
        if owner is None or owner != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        domain = account.domain
        company_name = account.company_name
    finally:
        db.close()

    team_id = current_user["team_id"]
    job = job_manager.create_job(f"Enrich {domain}", user_id=current_user["id"])

    def _run(job, domain, company_name, team_id):
        from src.enrichment.engine import enrich_domain
        from src.config import load_api_config
        from src.database import Database
        api_config = load_api_config()
        db = Database(api_config.db_path)
        try:
            job.update(message=f"Enriching {domain}...")
            data = enrich_domain(domain, company_name)
            db.upsert_enrichment(data, team_id=team_id)
            return data.model_dump(mode="json")
        finally:
            db.close()

    job_manager.run_in_thread(job, _run, domain, company_name, team_id)
    return {"job_id": job.job_id, "status": "started"}

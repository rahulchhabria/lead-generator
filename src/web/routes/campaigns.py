"""Campaign management API routes."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["campaigns"])


def _get_db():
    from src.config import load_api_config
    from src.database import Database
    api_config = load_api_config()
    return Database(api_config.db_path)


def _enriched_domains(db) -> set[str]:
    try:
        rows = db.conn.execute("SELECT domain FROM enrichment_data").fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _campaign_summary(campaign, db) -> dict:
    from src.models import LeadStatus
    accounts = db.get_accounts(campaign.id)
    contacts = db.get_contacts(campaign.id)
    approved = [c for c in contacts if c.status == LeadStatus.EMAIL_APPROVED]
    return {
        "id": campaign.id,
        "current_stage": campaign.current_stage.value,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
        "account_count": len(accounts),
        "contact_count": len(contacts),
        "approved_count": len(approved),
        "has_icp": campaign.icp_json is not None,
        "has_domains": campaign.domains_json is not None,
    }


@router.get("/")
def list_campaigns():
    db = _get_db()
    try:
        campaigns = db.list_campaigns()
        return [_campaign_summary(c, db) for c in campaigns]
    finally:
        db.close()


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str):
    db = _get_db()
    try:
        campaign = db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        summary = _campaign_summary(campaign, db)
        if campaign.icp_json:
            summary["icp"] = json.loads(campaign.icp_json)
        if campaign.domains_json:
            summary["domains"] = json.loads(campaign.domains_json)
        if campaign.config_json:
            summary["config"] = json.loads(campaign.config_json)
        return summary
    finally:
        db.close()


class CreateCampaignRequest(BaseModel):
    icp: Optional[dict] = None
    domains: Optional[list[dict]] = None
    target_roles: Optional[list[str]] = None
    config: Optional[dict] = None
    auto_approve: bool = False


@router.post("/")
def create_campaign(req: CreateCampaignRequest):
    """Create and start a new campaign (runs pipeline in background)."""
    from src.web.background import job_manager
    from src.models import ICPDefinition, DomainList, DomainEntry, CampaignConfig

    if not req.icp and not req.domains:
        raise HTTPException(status_code=400, detail="Provide either icp or domains")

    icp = ICPDefinition(**req.icp) if req.icp else None
    domain_list = None
    if req.domains:
        entries = [DomainEntry(**d) if isinstance(d, dict) else d for d in req.domains]
        domain_list = DomainList(target_roles=req.target_roles or [], domains=entries)

    config = CampaignConfig(**(req.config or {}))

    job = job_manager.create_job("Campaign starting…")

    def _run_pipeline(job, icp, domain_list, config):
        from src.pipeline import Pipeline
        from src.config import load_api_config
        from src.database import Database

        api_config = load_api_config()
        db = Database(api_config.db_path)
        try:
            pipeline = Pipeline(
                api_config=api_config,
                db=db,
                campaign_config=config,
                on_status=lambda msg: job.update(message=msg),
                on_review=None,  # auto-approve in API mode
            )
            campaign_id = pipeline.run_new(icp=icp, domains=domain_list)
            job.result = {"campaign_id": campaign_id}
        finally:
            db.close()

    job_manager.run_in_thread(job, _run_pipeline, icp, domain_list, config)
    return {"campaign_id": None, "job_id": job.job_id, "status": "started"}


@router.post("/{campaign_id}/advance")
def advance_campaign(campaign_id: str):
    """Resume a campaign from its last checkpoint."""
    from src.web.background import job_manager
    from src.models import CampaignConfig
    from src.config import load_api_config
    from src.database import Database

    db = _get_db()
    try:
        campaign = db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        config = CampaignConfig.model_validate_json(campaign.config_json or "{}")
    finally:
        db.close()

    job = job_manager.create_job(f"Resume {campaign_id}")

    def _resume(job, campaign_id, config):
        from src.pipeline import Pipeline
        from src.config import load_api_config
        from src.database import Database

        api_config = load_api_config()
        db = Database(api_config.db_path)
        try:
            pipeline = Pipeline(
                api_config=api_config,
                db=db,
                campaign_config=config,
                on_status=lambda msg: job.update(message=msg),
                on_review=None,
            )
            pipeline.resume(campaign_id)
            job.result = {"campaign_id": campaign_id}
        finally:
            db.close()

    job_manager.run_in_thread(job, _resume, campaign_id, config)
    return {"job_id": job.job_id, "status": "resuming"}


@router.get("/{campaign_id}/accounts")
def get_campaign_accounts(campaign_id: str, status: Optional[str] = None):
    from src.models import LeadStatus
    db = _get_db()
    try:
        campaign = db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        st = LeadStatus(status) if status else None
        accounts = db.get_accounts(campaign_id, st)
        enriched = _enriched_domains(db)
        return [
            {
                "id": a.id, "company_name": a.company_name, "domain": a.domain,
                "industry": a.industry, "employee_count": a.employee_count,
                "location": a.location, "status": a.status.value, "source": a.source,
                "description": a.description, "relevance_reasoning": a.relevance_reasoning,
                "has_enrichment": a.domain in enriched,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in accounts
        ]
    finally:
        db.close()


@router.get("/{campaign_id}/contacts")
def get_campaign_contacts(campaign_id: str, status: Optional[str] = None):
    from src.models import LeadStatus
    db = _get_db()
    try:
        campaign = db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        st = LeadStatus(status) if status else None
        contacts = db.get_contacts(campaign_id, st)
        accounts = {a.id: a for a in db.get_accounts(campaign_id)}
        return [
            {
                "id": c.id, "account_id": c.account_id, "full_name": c.full_name,
                "first_name": c.first_name, "last_name": c.last_name,
                "title": c.title, "email": c.email,
                "email_confidence": c.email_confidence, "email_verified": c.email_verified,
                "status": c.status.value, "linkedin_url": c.linkedin_url,
                "company_name": accounts[c.account_id].company_name if c.account_id in accounts else None,
                "domain": accounts[c.account_id].domain if c.account_id in accounts else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in contacts
        ]
    finally:
        db.close()


@router.get("/{campaign_id}/emails")
def get_campaign_emails(campaign_id: str):
    db = _get_db()
    try:
        emails = db.get_draft_emails(campaign_id)
        contacts = {c.id: c for c in db.get_contacts(campaign_id)}
        accounts = {a.id: a for a in db.get_accounts(campaign_id)}
        result = []
        for e in emails:
            contact = contacts.get(e.contact_id)
            account = accounts.get(contact.account_id) if contact else None
            result.append({
                "id": e.id, "contact_id": e.contact_id,
                "subject_line": e.subject_line, "body": e.body,
                "personalization_hooks": e.personalization_hooks,
                "tone": e.tone, "status": e.status.value,
                "contact_name": contact.full_name if contact else None,
                "contact_email": contact.email if contact else None,
                "company_name": account.company_name if account else None,
            })
        return result
    finally:
        db.close()


@router.post("/{campaign_id}/accounts/review")
def review_accounts(campaign_id: str, req: dict):
    from src.models import LeadStatus
    db = _get_db()
    try:
        approved_ids = req.get("approved_ids", [])
        rejected_ids = req.get("rejected_ids", [])
        if approved_ids:
            db.batch_update_account_status(approved_ids, LeadStatus.APPROVED)
        if rejected_ids:
            db.batch_update_account_status(rejected_ids, LeadStatus.REJECTED)
        return {"approved": len(approved_ids), "rejected": len(rejected_ids)}
    finally:
        db.close()


@router.post("/{campaign_id}/contacts/review")
def review_contacts(campaign_id: str, req: dict):
    from src.models import LeadStatus
    db = _get_db()
    try:
        approved_ids = req.get("approved_ids", [])
        rejected_ids = req.get("rejected_ids", [])
        if approved_ids:
            db.batch_update_contact_status(approved_ids, LeadStatus.CONTACT_APPROVED)
        if rejected_ids:
            db.batch_update_contact_status(rejected_ids, LeadStatus.REJECTED)
        return {"approved": len(approved_ids), "rejected": len(rejected_ids)}
    finally:
        db.close()


@router.post("/{campaign_id}/emails/review")
def review_emails(campaign_id: str, req: dict):
    from src.models import LeadStatus
    db = _get_db()
    try:
        approved_ids = req.get("approved_ids", [])
        rejected_ids = req.get("rejected_ids", [])
        if approved_ids:
            db.batch_update_draft_email_status(approved_ids, LeadStatus.EMAIL_APPROVED)
        if rejected_ids:
            db.batch_update_draft_email_status(rejected_ids, LeadStatus.REJECTED)
        return {"approved": len(approved_ids), "rejected": len(rejected_ids)}
    finally:
        db.close()

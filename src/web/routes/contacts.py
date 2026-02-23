"""Contact management API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.web.auth import get_current_user

router = APIRouter(tags=["contacts"])


def _get_db():
    from src.config import load_api_config
    from src.database import Database
    api_config = load_api_config()
    return Database(api_config.db_path)


@router.get("/")
def list_contacts(campaign_id: Optional[str] = None, status: Optional[str] = None,
                  domain: Optional[str] = None, limit: int = 100,
                  current_user: dict = Depends(get_current_user)):
    from src.models import LeadStatus
    db = _get_db()
    try:
        if domain:
            # Filter by domain but only show contacts from user's campaigns
            rows = db.conn.execute(
                """SELECT a.id FROM accounts a
                   JOIN campaigns c ON a.campaign_id = c.id
                   WHERE a.domain = ? AND c.user_id = ?""",
                (domain, current_user["id"]),
            ).fetchall()
            account_ids = [r[0] for r in rows]
            contacts = []
            for aid in account_ids:
                contacts.extend(db.get_contacts_for_account(aid))
            accounts = {}
            for aid in account_ids:
                a = db.get_account(aid)
                if a:
                    accounts[a.id] = a
        elif campaign_id:
            owner = db.get_campaign_owner(campaign_id)
            if owner is None or owner != current_user["id"]:
                raise HTTPException(status_code=403, detail="Access denied")
            st = LeadStatus(status) if status else None
            contacts = db.get_contacts(campaign_id, st)
            accounts = {a.id: a for a in db.get_accounts(campaign_id)}
        else:
            contacts = db.get_all_contacts(limit=limit, user_id=current_user["id"])
            account_ids = list({c.account_id for c in contacts})
            accounts = {}
            for aid in account_ids:
                a = db.get_account(aid)
                if a:
                    accounts[a.id] = a

        return [
            {
                "id": c.id, "account_id": c.account_id, "campaign_id": c.campaign_id,
                "full_name": c.full_name, "title": c.title, "email": c.email,
                "email_confidence": c.email_confidence, "email_verified": c.email_verified,
                "email_source": c.email_source, "status": c.status.value,
                "linkedin_url": c.linkedin_url,
                "company_name": accounts[c.account_id].company_name if c.account_id in accounts else None,
                "domain": accounts[c.account_id].domain if c.account_id in accounts else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in contacts
        ]
    finally:
        db.close()


@router.get("/{contact_id}")
def get_contact(contact_id: int, current_user: dict = Depends(get_current_user)):
    """Get full contact with dossier, emails, and account enrichment."""
    db = _get_db()
    try:
        contact = db.get_contact(contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        owner = db.get_campaign_owner(contact.campaign_id)
        if owner is None or owner != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        account = db.get_account(contact.account_id)
        dossier = db.get_dossier_for_contact(contact_id)

        result = {
            "id": contact.id, "full_name": contact.full_name,
            "first_name": contact.first_name, "last_name": contact.last_name,
            "title": contact.title, "email": contact.email,
            "email_confidence": contact.email_confidence,
            "email_verified": contact.email_verified, "email_source": contact.email_source,
            "linkedin_url": contact.linkedin_url, "status": contact.status.value,
            "company": {
                "name": account.company_name if account else None,
                "domain": account.domain if account else None,
                "industry": account.industry if account else None,
            },
            "dossier": None,
            "emails": [],
            "account_enrichment": None,
        }

        if dossier:
            result["dossier"] = {
                "github_username": dossier.github_username,
                "github_repos": dossier.github_repos,
                "github_languages": dossier.github_languages,
                "recent_posts": dossier.recent_posts,
                "interests": dossier.interests,
                "education": dossier.education,
                "open_source_contributions": dossier.open_source_contributions,
                "speaking_engagements": dossier.speaking_engagements,
                "personal_details": dossier.personal_details,
            }

        emails = [e for e in db.get_draft_emails(contact.campaign_id) if e.contact_id == contact_id]
        result["emails"] = [
            {
                "id": e.id, "subject_line": e.subject_line,
                "body": e.body, "status": e.status.value,
                "personalization_hooks": e.personalization_hooks,
            }
            for e in emails
        ]

        if account:
            result["account_enrichment"] = db.get_enrichment(account.domain)

        return result
    finally:
        db.close()

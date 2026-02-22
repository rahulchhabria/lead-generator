"""SQLite database schema and CRUD operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.models import (
    Account,
    Campaign,
    Contact,
    DraftEmail,
    LeadStatus,
    PersonalizationDossier,
    PipelineStage,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    icp_json TEXT,
    domains_json TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    current_stage TEXT NOT NULL DEFAULT 'discovery',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
    company_name TEXT NOT NULL,
    domain TEXT NOT NULL,
    industry TEXT,
    employee_count TEXT,
    location TEXT,
    description TEXT,
    relevance_reasoning TEXT DEFAULT '',
    data_sources TEXT DEFAULT '[]',
    source TEXT DEFAULT 'discovered',
    status TEXT DEFAULT 'discovered',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    title TEXT,
    email TEXT,
    email_confidence INTEGER,
    email_verified BOOLEAN DEFAULT 0,
    email_source TEXT,
    linkedin_url TEXT,
    data_sources TEXT DEFAULT '[]',
    status TEXT DEFAULT 'contact_found',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dossiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
    github_username TEXT,
    github_repos TEXT DEFAULT '[]',
    github_languages TEXT DEFAULT '[]',
    recent_posts TEXT DEFAULT '[]',
    interests TEXT DEFAULT '[]',
    education TEXT,
    open_source_contributions TEXT DEFAULT '[]',
    speaking_engagements TEXT DEFAULT '[]',
    personal_details TEXT DEFAULT '[]',
    raw_research_notes TEXT DEFAULT '',
    data_sources TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS draft_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    dossier_id INTEGER NOT NULL REFERENCES dossiers(id),
    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
    subject_line TEXT NOT NULL,
    body TEXT NOT NULL,
    personalization_hooks TEXT DEFAULT '[]',
    tone TEXT DEFAULT 'casual',
    includes_unsubscribe BOOLEAN DEFAULT 1,
    includes_physical_address BOOLEAN DEFAULT 1,
    status TEXT DEFAULT 'email_drafted',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gdpr_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_email TEXT,
    action TEXT NOT NULL,
    data_field TEXT,
    source TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppression_list (
    email TEXT PRIMARY KEY,
    reason TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enrichment_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    company_name TEXT,
    description TEXT,
    long_description TEXT,
    founded_year INTEGER,
    employee_count INTEGER,
    employee_count_range TEXT,
    engineering_count INTEGER,
    hq_city TEXT,
    hq_state TEXT,
    hq_country TEXT,
    industry TEXT,
    industry_keywords TEXT DEFAULT '[]',
    total_funding_raised TEXT,
    current_valuation TEXT,
    latest_funding_round TEXT,
    all_funding_rounds TEXT DEFAULT '[]',
    ceo TEXT,
    founders TEXT DEFAULT '[]',
    recent_leadership_changes TEXT DEFAULT '[]',
    technographic TEXT,
    mobile_apps TEXT,
    hiring TEXT,
    github_activity TEXT,
    linkedin_url TEXT,
    twitter_handle TEXT,
    github_url TEXT,
    crunchbase_url TEXT,
    ai_insights TEXT,
    data_quality TEXT DEFAULT 'low',
    confidence_score INTEGER DEFAULT 0,
    sources TEXT DEFAULT '[]',
    last_enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    enrichment_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """SQLite database manager for the pipeline."""

    def __init__(self, db_path: str = "data/pipeline.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # --- Campaigns ---

    def create_campaign(self, campaign: Campaign) -> Campaign:
        self.conn.execute(
            """INSERT INTO campaigns (id, icp_json, domains_json, config_json, current_stage)
               VALUES (?, ?, ?, ?, ?)""",
            (
                campaign.id,
                campaign.icp_json,
                campaign.domains_json,
                campaign.config_json,
                campaign.current_stage.value,
            ),
        )
        self.conn.commit()
        return campaign

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        row = self.conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not row:
            return None
        return Campaign(
            id=row["id"],
            icp_json=row["icp_json"],
            domains_json=row["domains_json"],
            config_json=row["config_json"],
            current_stage=PipelineStage(row["current_stage"]),
        )

    def update_campaign_stage(self, campaign_id: str, stage: PipelineStage):
        self.conn.execute(
            "UPDATE campaigns SET current_stage = ?, updated_at = ? WHERE id = ?",
            (stage.value, datetime.now(timezone.utc).isoformat(), campaign_id),
        )
        self.conn.commit()

    def list_campaigns(self) -> list[Campaign]:
        rows = self.conn.execute(
            "SELECT * FROM campaigns ORDER BY created_at DESC"
        ).fetchall()
        return [
            Campaign(
                id=r["id"],
                icp_json=r["icp_json"],
                domains_json=r["domains_json"],
                config_json=r["config_json"],
                current_stage=PipelineStage(r["current_stage"]),
            )
            for r in rows
        ]

    # --- Accounts ---

    def insert_account(self, account: Account) -> int:
        cursor = self.conn.execute(
            """INSERT INTO accounts
               (campaign_id, company_name, domain, industry, employee_count,
                location, description, relevance_reasoning, data_sources, source, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account.campaign_id,
                account.company_name,
                account.domain,
                account.industry,
                account.employee_count,
                account.location,
                account.description,
                account.relevance_reasoning,
                json.dumps(account.data_sources),
                account.source,
                account.status.value,
                account.error_message,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_accounts(
        self, campaign_id: str, status: Optional[LeadStatus] = None
    ) -> list[Account]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM accounts WHERE campaign_id = ? AND status = ?",
                (campaign_id, status.value),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM accounts WHERE campaign_id = ?", (campaign_id,)
            ).fetchall()
        return [self._row_to_account(r) for r in rows]

    def update_account_status(self, account_id: int, status: LeadStatus):
        self.conn.execute(
            "UPDATE accounts SET status = ? WHERE id = ?", (status.value, account_id)
        )
        self.conn.commit()

    def batch_update_account_status(self, account_ids: list[int], status: LeadStatus):
        if not account_ids:
            return
        placeholders = ",".join("?" for _ in account_ids)
        self.conn.execute(
            f"UPDATE accounts SET status = ? WHERE id IN ({placeholders})",
            [status.value, *account_ids],
        )
        self.conn.commit()

    def _row_to_account(self, row) -> Account:
        return Account(
            id=row["id"],
            campaign_id=row["campaign_id"],
            company_name=row["company_name"],
            domain=row["domain"],
            industry=row["industry"],
            employee_count=row["employee_count"],
            location=row["location"],
            description=row["description"],
            relevance_reasoning=row["relevance_reasoning"],
            data_sources=json.loads(row["data_sources"] or "[]"),
            source=row["source"],
            status=LeadStatus(row["status"]),
            error_message=row["error_message"],
        )

    # --- Contacts ---

    def insert_contact(self, contact: Contact) -> int:
        cursor = self.conn.execute(
            """INSERT INTO contacts
               (account_id, campaign_id, first_name, last_name, full_name,
                title, email, email_confidence, email_verified, email_source,
                linkedin_url, data_sources, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                contact.account_id,
                contact.campaign_id,
                contact.first_name,
                contact.last_name,
                contact.full_name,
                contact.title,
                contact.email,
                contact.email_confidence,
                contact.email_verified,
                contact.email_source,
                contact.linkedin_url,
                json.dumps(contact.data_sources),
                contact.status.value,
                contact.error_message,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_contacts(
        self, campaign_id: str, status: Optional[LeadStatus] = None
    ) -> list[Contact]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM contacts WHERE campaign_id = ? AND status = ?",
                (campaign_id, status.value),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM contacts WHERE campaign_id = ?", (campaign_id,)
            ).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def get_contact(self, contact_id: int) -> Optional[Contact]:
        row = self.conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_contact(row)

    def update_contact_status(self, contact_id: int, status: LeadStatus):
        self.conn.execute(
            "UPDATE contacts SET status = ? WHERE id = ?", (status.value, contact_id)
        )
        self.conn.commit()

    def batch_update_contact_status(self, contact_ids: list[int], status: LeadStatus):
        if not contact_ids:
            return
        placeholders = ",".join("?" for _ in contact_ids)
        self.conn.execute(
            f"UPDATE contacts SET status = ? WHERE id IN ({placeholders})",
            [status.value, *contact_ids],
        )
        self.conn.commit()

    def _row_to_contact(self, row) -> Contact:
        return Contact(
            id=row["id"],
            account_id=row["account_id"],
            campaign_id=row["campaign_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            full_name=row["full_name"],
            title=row["title"],
            email=row["email"],
            email_confidence=row["email_confidence"],
            email_verified=bool(row["email_verified"]),
            email_source=row["email_source"],
            linkedin_url=row["linkedin_url"],
            data_sources=json.loads(row["data_sources"] or "[]"),
            status=LeadStatus(row["status"]),
            error_message=row["error_message"],
        )

    # --- Dossiers ---

    def insert_dossier(self, dossier: PersonalizationDossier) -> int:
        cursor = self.conn.execute(
            """INSERT INTO dossiers
               (contact_id, campaign_id, github_username, github_repos,
                github_languages, recent_posts, interests, education,
                open_source_contributions, speaking_engagements,
                personal_details, raw_research_notes, data_sources)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dossier.contact_id,
                dossier.campaign_id,
                dossier.github_username,
                json.dumps(dossier.github_repos),
                json.dumps(dossier.github_languages),
                json.dumps(dossier.recent_posts),
                json.dumps(dossier.interests),
                dossier.education,
                json.dumps(dossier.open_source_contributions),
                json.dumps(dossier.speaking_engagements),
                json.dumps(dossier.personal_details),
                dossier.raw_research_notes,
                json.dumps(dossier.data_sources),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_dossier_for_contact(self, contact_id: int) -> Optional[PersonalizationDossier]:
        row = self.conn.execute(
            "SELECT * FROM dossiers WHERE contact_id = ?", (contact_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_dossier(row)

    def get_dossiers(self, campaign_id: str) -> list[PersonalizationDossier]:
        rows = self.conn.execute(
            "SELECT * FROM dossiers WHERE campaign_id = ?", (campaign_id,)
        ).fetchall()
        return [self._row_to_dossier(r) for r in rows]

    def _row_to_dossier(self, row) -> PersonalizationDossier:
        return PersonalizationDossier(
            id=row["id"],
            contact_id=row["contact_id"],
            campaign_id=row["campaign_id"],
            github_username=row["github_username"],
            github_repos=json.loads(row["github_repos"] or "[]"),
            github_languages=json.loads(row["github_languages"] or "[]"),
            recent_posts=json.loads(row["recent_posts"] or "[]"),
            interests=json.loads(row["interests"] or "[]"),
            education=row["education"],
            open_source_contributions=json.loads(row["open_source_contributions"] or "[]"),
            speaking_engagements=json.loads(row["speaking_engagements"] or "[]"),
            personal_details=json.loads(row["personal_details"] or "[]"),
            raw_research_notes=row["raw_research_notes"],
            data_sources=json.loads(row["data_sources"] or "[]"),
        )

    # --- Draft Emails ---

    def insert_draft_email(self, email: DraftEmail) -> int:
        cursor = self.conn.execute(
            """INSERT INTO draft_emails
               (contact_id, dossier_id, campaign_id, subject_line, body,
                personalization_hooks, tone, includes_unsubscribe,
                includes_physical_address, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                email.contact_id,
                email.dossier_id,
                email.campaign_id,
                email.subject_line,
                email.body,
                json.dumps(email.personalization_hooks),
                email.tone,
                email.includes_unsubscribe,
                email.includes_physical_address,
                email.status.value,
                email.error_message,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_draft_emails(
        self, campaign_id: str, status: Optional[LeadStatus] = None
    ) -> list[DraftEmail]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM draft_emails WHERE campaign_id = ? AND status = ?",
                (campaign_id, status.value),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM draft_emails WHERE campaign_id = ?", (campaign_id,)
            ).fetchall()
        return [self._row_to_draft_email(r) for r in rows]

    def update_draft_email_status(self, email_id: int, status: LeadStatus):
        self.conn.execute(
            "UPDATE draft_emails SET status = ? WHERE id = ?", (status.value, email_id)
        )
        self.conn.commit()

    def batch_update_draft_email_status(self, email_ids: list[int], status: LeadStatus):
        if not email_ids:
            return
        placeholders = ",".join("?" for _ in email_ids)
        self.conn.execute(
            f"UPDATE draft_emails SET status = ? WHERE id IN ({placeholders})",
            [status.value, *email_ids],
        )
        self.conn.commit()

    def _row_to_draft_email(self, row) -> DraftEmail:
        return DraftEmail(
            id=row["id"],
            contact_id=row["contact_id"],
            dossier_id=row["dossier_id"],
            campaign_id=row["campaign_id"],
            subject_line=row["subject_line"],
            body=row["body"],
            personalization_hooks=json.loads(row["personalization_hooks"] or "[]"),
            tone=row["tone"],
            includes_unsubscribe=bool(row["includes_unsubscribe"]),
            includes_physical_address=bool(row["includes_physical_address"]),
            status=LeadStatus(row["status"]),
            error_message=row["error_message"],
        )

    # --- GDPR ---

    def log_gdpr_action(self, email: str, action: str, field: str = "", source: str = ""):
        self.conn.execute(
            "INSERT INTO gdpr_log (contact_email, action, data_field, source) VALUES (?, ?, ?, ?)",
            (email, action, field, source),
        )
        self.conn.commit()

    def is_suppressed(self, email: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM suppression_list WHERE email = ?", (email.lower(),)
        ).fetchone()
        return row is not None

    def add_to_suppression(self, email: str, reason: str = "manual"):
        self.conn.execute(
            "INSERT OR IGNORE INTO suppression_list (email, reason) VALUES (?, ?)",
            (email.lower(), reason),
        )
        self.conn.commit()

    def forget_contact(self, email: str):
        """GDPR right-to-be-forgotten: remove all data for an email."""
        email = email.lower()
        self.conn.execute(
            "DELETE FROM draft_emails WHERE contact_id IN (SELECT id FROM contacts WHERE email = ?)",
            (email,),
        )
        self.conn.execute(
            "DELETE FROM dossiers WHERE contact_id IN (SELECT id FROM contacts WHERE email = ?)",
            (email,),
        )
        self.conn.execute("DELETE FROM contacts WHERE email = ?", (email,))
        self.add_to_suppression(email, "deletion_requested")
        self.log_gdpr_action(email, "deleted", "all")

    # --- Export helpers ---

    def get_export_data(self, campaign_id: str) -> list[dict]:
        """Get all approved emails with full context for CSV export."""
        rows = self.conn.execute(
            """
            SELECT
                c.first_name, c.last_name, c.full_name, c.email,
                c.email_confidence, c.email_verified, c.title,
                c.linkedin_url, c.data_sources as contact_sources,
                a.company_name, a.domain, a.industry, a.employee_count, a.location,
                d.github_username, d.data_sources as dossier_sources,
                e.subject_line, e.body, e.personalization_hooks
            FROM draft_emails e
            JOIN contacts c ON e.contact_id = c.id
            JOIN accounts a ON c.account_id = a.id
            LEFT JOIN dossiers d ON e.dossier_id = d.id
            WHERE e.campaign_id = ? AND e.status = ?
            """,
            (campaign_id, LeadStatus.EMAIL_APPROVED.value),
        ).fetchall()

        results = []
        for r in rows:
            github_url = ""
            if r["github_username"]:
                github_url = f"https://github.com/{r['github_username']}"

            contact_sources = json.loads(r["contact_sources"] or "[]")
            dossier_sources = json.loads(r["dossier_sources"] or "[]")
            all_sources = list(set(contact_sources + dossier_sources))

            results.append(
                {
                    "first_name": r["first_name"],
                    "last_name": r["last_name"],
                    "email": r["email"],
                    "email_confidence": r["email_confidence"],
                    "email_verified": r["email_verified"],
                    "title": r["title"],
                    "company": r["company_name"],
                    "domain": r["domain"],
                    "industry": r["industry"],
                    "company_size": r["employee_count"],
                    "location": r["location"],
                    "linkedin_url": r["linkedin_url"],
                    "github_url": github_url,
                    "subject_line": r["subject_line"],
                    "email_body": r["body"],
                    "personalization_hooks": ", ".join(
                        json.loads(r["personalization_hooks"] or "[]")
                    ),
                    "data_sources": ", ".join(all_sources),
                    "campaign_id": campaign_id,
                }
            )
        return results

    # --- Enrichment ---

    def upsert_enrichment(self, data) -> None:
        """Insert or update enrichment data for a domain."""
        import json
        from datetime import datetime, timezone

        def _dump(obj):
            if obj is None:
                return None
            if hasattr(obj, "model_dump"):
                return json.dumps(obj.model_dump(mode="json"))
            if isinstance(obj, list):
                return json.dumps([
                    (item.model_dump(mode="json") if hasattr(item, "model_dump") else item)
                    for item in obj
                ])
            return json.dumps(obj)

        self.conn.execute(
            """INSERT INTO enrichment_data
               (domain, company_name, description, long_description,
                founded_year, employee_count, employee_count_range, engineering_count,
                hq_city, hq_state, hq_country, industry, industry_keywords,
                total_funding_raised, current_valuation, latest_funding_round, all_funding_rounds,
                ceo, founders, recent_leadership_changes, technographic, mobile_apps,
                hiring, github_activity, linkedin_url, twitter_handle, github_url, crunchbase_url,
                ai_insights, data_quality, confidence_score, sources, last_enriched_at, enrichment_error)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(domain) DO UPDATE SET
                company_name=excluded.company_name,
                description=excluded.description,
                long_description=excluded.long_description,
                founded_year=excluded.founded_year,
                employee_count=excluded.employee_count,
                employee_count_range=excluded.employee_count_range,
                engineering_count=excluded.engineering_count,
                hq_city=excluded.hq_city, hq_state=excluded.hq_state, hq_country=excluded.hq_country,
                industry=excluded.industry, industry_keywords=excluded.industry_keywords,
                total_funding_raised=excluded.total_funding_raised,
                current_valuation=excluded.current_valuation,
                latest_funding_round=excluded.latest_funding_round,
                all_funding_rounds=excluded.all_funding_rounds,
                ceo=excluded.ceo, founders=excluded.founders,
                recent_leadership_changes=excluded.recent_leadership_changes,
                technographic=excluded.technographic, mobile_apps=excluded.mobile_apps,
                hiring=excluded.hiring, github_activity=excluded.github_activity,
                linkedin_url=excluded.linkedin_url, twitter_handle=excluded.twitter_handle,
                github_url=excluded.github_url, crunchbase_url=excluded.crunchbase_url,
                ai_insights=excluded.ai_insights, data_quality=excluded.data_quality,
                confidence_score=excluded.confidence_score, sources=excluded.sources,
                last_enriched_at=excluded.last_enriched_at, enrichment_error=excluded.enrichment_error""",
            (
                data.domain, data.company_name, data.description, data.long_description,
                data.founded_year, data.employee_count, data.employee_count_range, data.engineering_count,
                data.hq_city, data.hq_state, data.hq_country, data.industry,
                json.dumps(data.industry_keywords),
                data.total_funding_raised, data.current_valuation,
                _dump(data.latest_funding_round), _dump(data.all_funding_rounds),
                _dump(data.ceo), _dump(data.founders), json.dumps(data.recent_leadership_changes),
                _dump(data.technographic), _dump(data.mobile_apps),
                _dump(data.hiring), _dump(data.github_activity),
                data.linkedin_url, data.twitter_handle, data.github_url, data.crunchbase_url,
                _dump(data.ai_insights), data.data_quality, data.confidence_score,
                json.dumps(data.sources),
                datetime.now(timezone.utc).isoformat(),
                data.enrichment_error,
            ),
        )
        self.conn.commit()

    def get_enrichment(self, domain: str) -> Optional[dict]:
        """Get enrichment data for a domain as a dict."""
        import json
        row = self.conn.execute(
            "SELECT * FROM enrichment_data WHERE domain = ?", (domain,)
        ).fetchone()
        if not row:
            return None
        return self._enrichment_row_to_dict(row)

    def list_enrichments(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List all enrichments with pagination."""
        rows = self.conn.execute(
            "SELECT * FROM enrichment_data ORDER BY last_enriched_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._enrichment_row_to_dict(r) for r in rows]

    def _enrichment_row_to_dict(self, row) -> dict:
        import json

        def _load(val):
            if val is None:
                return None
            try:
                return json.loads(val)
            except Exception:
                return val

        return {
            "domain": row["domain"],
            "company_name": row["company_name"],
            "description": row["description"],
            "long_description": row["long_description"],
            "founded_year": row["founded_year"],
            "employee_count": row["employee_count"],
            "employee_count_range": row["employee_count_range"],
            "engineering_count": row["engineering_count"],
            "hq_city": row["hq_city"],
            "hq_state": row["hq_state"],
            "hq_country": row["hq_country"],
            "industry": row["industry"],
            "industry_keywords": _load(row["industry_keywords"]) or [],
            "total_funding_raised": row["total_funding_raised"],
            "current_valuation": row["current_valuation"],
            "latest_funding_round": _load(row["latest_funding_round"]),
            "all_funding_rounds": _load(row["all_funding_rounds"]) or [],
            "ceo": _load(row["ceo"]),
            "founders": _load(row["founders"]) or [],
            "recent_leadership_changes": _load(row["recent_leadership_changes"]) or [],
            "technographic": _load(row["technographic"]),
            "mobile_apps": _load(row["mobile_apps"]),
            "hiring": _load(row["hiring"]),
            "github_activity": _load(row["github_activity"]),
            "linkedin_url": row["linkedin_url"],
            "twitter_handle": row["twitter_handle"],
            "github_url": row["github_url"],
            "crunchbase_url": row["crunchbase_url"],
            "ai_insights": _load(row["ai_insights"]),
            "data_quality": row["data_quality"],
            "confidence_score": row["confidence_score"],
            "sources": _load(row["sources"]) or [],
            "last_enriched_at": row["last_enriched_at"],
            "enrichment_error": row["enrichment_error"],
        }

    def get_account(self, account_id: int) -> Optional[Account]:
        """Get a single account by ID."""
        row = self.conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_account(row)

    def get_all_accounts(self, limit: int = 100) -> list[Account]:
        """Get accounts across all campaigns."""
        rows = self.conn.execute(
            "SELECT * FROM accounts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_account(r) for r in rows]

    def get_all_contacts(self, limit: int = 100) -> list[Contact]:
        """Get contacts across all campaigns."""
        rows = self.conn.execute(
            "SELECT * FROM contacts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_contact(r) for r in rows]

    def get_contacts_for_account(self, account_id: int) -> list[Contact]:
        """Get all contacts for a specific account."""
        rows = self.conn.execute(
            "SELECT * FROM contacts WHERE account_id = ?", (account_id,)
        ).fetchall()
        return [self._row_to_contact(r) for r in rows]


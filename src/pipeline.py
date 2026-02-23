"""Pipeline orchestrator - runs agents in sequence with checkpoint/resume."""

from __future__ import annotations

import logging
import uuid
from typing import Callable, Optional

import anthropic

from src.agents import account_discovery, contact_email, email_composer, research
from src.agents.base import BaseAgent
from src.config import APIConfig
from src.database import Database
from src.enrichment.engine import enrich_domain
from src.models import (
    Account,
    Campaign,
    CampaignConfig,
    DomainList,
    ICPDefinition,
    LeadStatus,
    PipelineStage,
)

logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates the multi-agent lead generation pipeline.

    Callbacks allow the CLI (or future GUI) to handle I/O.
    """

    def __init__(
        self,
        api_config: APIConfig,
        db: Database,
        campaign_config: CampaignConfig,
        on_status: Callable[[str], None] | None = None,
        on_review: Callable[[str, list], list[int]] | None = None,
    ):
        """
        Args:
            api_config: API configuration with keys.
            db: Database instance for persistence.
            campaign_config: Campaign-level settings.
            on_status: Callback for status messages. Signature: (message) -> None.
            on_review: Callback for human review. Signature: (stage, items) -> list of approved IDs.
                       If None, all items are auto-approved.
        """
        self.api_config = api_config
        self.db = db
        self.config = campaign_config
        self.on_status = on_status or (lambda msg: None)
        self.on_review = on_review
        self.client = anthropic.Anthropic(api_key=api_config.anthropic_api_key)
        self.agent = BaseAgent(self.client, api_config.claude_model)

    def run_new(
        self,
        icp: Optional[ICPDefinition] = None,
        domains: Optional[DomainList] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Start a new pipeline campaign.

        Args:
            icp: ICP definition (for account discovery).
            domains: Domain list (skip discovery).
            user_id: Owner user ID for multi-tenant scoping.

        Returns:
            campaign_id
        """
        if not icp and not domains:
            raise ValueError("Either icp or domains must be provided")

        campaign_id = str(uuid.uuid4())[:8]
        target_roles = []

        if icp:
            target_roles = icp.target_roles

        if domains:
            if domains.target_roles:
                target_roles = domains.target_roles

        # Determine starting stage
        if domains and domains.domains:
            start_stage = PipelineStage.CONTACT_FINDING
        else:
            start_stage = PipelineStage.DISCOVERY

        campaign = Campaign(
            id=campaign_id,
            icp_json=icp.model_dump_json() if icp else None,
            domains_json=domains.model_dump_json() if domains else None,
            config_json=self.config.model_dump_json(),
            current_stage=start_stage,
        )
        self.db.create_campaign(campaign, user_id=user_id)

        self.on_status(f"Campaign {campaign_id} created. Starting at {start_stage.value}...")

        # If domains provided, insert them as pre-approved accounts
        if domains and domains.domains:
            for entry in domains.domains:
                account = Account(
                    campaign_id=campaign_id,
                    company_name=entry.company_name or entry.domain,
                    domain=entry.domain,
                    description=entry.notes,
                    source="provided",
                    status=LeadStatus.APPROVED,
                    data_sources=["user_provided"],
                )
                self.db.insert_account(account)

            self.on_status(f"Loaded {len(domains.domains)} domains as pre-approved accounts.")

        return self.resume(campaign_id, target_roles)

    def resume(self, campaign_id: str, target_roles: list[str] | None = None) -> str:
        """Resume a pipeline from its last checkpoint.

        Returns:
            campaign_id
        """
        campaign = self.db.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Recover target roles from stored data
        if not target_roles:
            target_roles = []
            if campaign.icp_json:
                icp = ICPDefinition.model_validate_json(campaign.icp_json)
                target_roles = icp.target_roles
            if campaign.domains_json:
                dl = DomainList.model_validate_json(campaign.domains_json)
                if dl.target_roles:
                    target_roles = dl.target_roles

        stage = campaign.current_stage

        if stage == PipelineStage.DISCOVERY:
            self._run_discovery(campaign_id)
            stage = PipelineStage.DISCOVERY_REVIEW

        if stage == PipelineStage.DISCOVERY_REVIEW:
            self._review_accounts(campaign_id)
            stage = PipelineStage.CONTACT_FINDING

        if stage == PipelineStage.CONTACT_FINDING:
            self._run_contact_finding(campaign_id, target_roles)
            stage = PipelineStage.CONTACT_REVIEW

        if stage == PipelineStage.CONTACT_REVIEW:
            self._review_contacts(campaign_id)
            stage = PipelineStage.RESEARCH

        if stage == PipelineStage.RESEARCH:
            self._run_research(campaign_id)
            stage = PipelineStage.RESEARCH_REVIEW

        if stage == PipelineStage.RESEARCH_REVIEW:
            self._review_research(campaign_id)
            stage = PipelineStage.EMAIL_COMPOSITION

        if stage == PipelineStage.EMAIL_COMPOSITION:
            self._run_email_composition(campaign_id)
            stage = PipelineStage.EMAIL_REVIEW

        if stage == PipelineStage.EMAIL_REVIEW:
            self._review_emails(campaign_id)
            stage = PipelineStage.EXPORT

        if stage == PipelineStage.EXPORT:
            self.db.update_campaign_stage(campaign_id, PipelineStage.COMPLETED)
            self.on_status(f"Pipeline complete for campaign {campaign_id}!")

        return campaign_id

    # --- Stage implementations ---

    def _run_discovery(self, campaign_id: str):
        """Stage 1: Account Discovery."""
        campaign = self.db.get_campaign(campaign_id)
        if not campaign or not campaign.icp_json:
            self.on_status("No ICP defined - skipping discovery.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.CONTACT_FINDING)
            return

        icp = ICPDefinition.model_validate_json(campaign.icp_json)
        self.on_status(f"Discovering accounts for ICP: {icp.description[:100]}...")

        try:
            accounts = account_discovery.run(self.agent, icp, self.api_config)
        except Exception as e:
            logger.error(f"Account discovery failed: {e}")
            self.on_status(f"Account discovery failed: {e}")
            accounts = []

        for account in accounts:
            account.campaign_id = campaign_id
            self.db.insert_account(account)
            self.db.log_gdpr_action(
                account.domain, "collected", "company_info", "web_search"
            )

        self.on_status(f"Discovered {len(accounts)} accounts.")
        self.db.update_campaign_stage(campaign_id, PipelineStage.DISCOVERY_REVIEW)

    def _review_accounts(self, campaign_id: str):
        """Human review of discovered accounts."""
        accounts = self.db.get_accounts(campaign_id, LeadStatus.DISCOVERED)

        if not accounts:
            self.on_status("No accounts to review.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.CONTACT_FINDING)
            return

        if self.on_review:
            approved_ids = self.on_review("accounts", accounts)
            all_ids = [a.id for a in accounts if a.id]

            approved_set = set(approved_ids)
            rejected_ids = [aid for aid in all_ids if aid not in approved_set]

            self.db.batch_update_account_status(approved_ids, LeadStatus.APPROVED)
            self.db.batch_update_account_status(rejected_ids, LeadStatus.REJECTED)

            self.on_status(
                f"Accounts: {len(approved_ids)} approved, {len(rejected_ids)} rejected."
            )
        else:
            # Auto-approve all
            all_ids = [a.id for a in accounts if a.id]
            self.db.batch_update_account_status(all_ids, LeadStatus.APPROVED)
            self.on_status(f"Auto-approved {len(all_ids)} accounts.")

        self._enrich_approved_accounts(campaign_id)
        self.db.update_campaign_stage(campaign_id, PipelineStage.CONTACT_FINDING)

    def _enrich_approved_accounts(self, campaign_id: str):
        """Enrich approved accounts using the enrichment engine (best-effort, skips cached)."""
        accounts = self.db.get_accounts(campaign_id, LeadStatus.APPROVED)
        to_enrich = [a for a in accounts if not self.db.get_enrichment(a.domain)]
        if not to_enrich:
            return

        self.on_status(f"Enriching {len(to_enrich)} accounts...")
        enriched = 0
        for account in to_enrich:
            try:
                data = enrich_domain(account.domain, account.company_name)
                self.db.upsert_enrichment(data)
                enriched += 1
            except Exception as e:
                logger.warning(f"Enrichment failed for {account.domain}: {e}")

        self.on_status(f"Enriched {enriched}/{len(to_enrich)} accounts.")

    def _run_contact_finding(self, campaign_id: str, target_roles: list[str]):
        """Stage 2: Contact & Email Finding."""
        # Enrich any accounts not yet enriched (handles domain-list campaigns that skip review)
        self._enrich_approved_accounts(campaign_id)

        accounts = self.db.get_accounts(campaign_id, LeadStatus.APPROVED)

        if not accounts:
            self.on_status("No approved accounts - skipping contact finding.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.CONTACT_REVIEW)
            return

        self.on_status(f"Finding contacts at {len(accounts)} accounts...")

        total_contacts = 0
        failed = 0

        for account in accounts:
            try:
                # Check suppression before processing
                contacts = contact_email.run(
                    self.agent, account, target_roles, self.api_config
                )

                for c in contacts:
                    # Check suppression list
                    if c.email and self.db.is_suppressed(c.email):
                        logger.info(f"Skipping suppressed email: {c.email}")
                        continue

                    c.account_id = account.id
                    c.campaign_id = campaign_id
                    self.db.insert_contact(c)

                    if c.email:
                        self.db.log_gdpr_action(
                            c.email, "collected", "email", c.email_source or "agent"
                        )

                    total_contacts += 1

            except Exception as e:
                logger.error(f"Contact finding failed for {account.domain}: {e}")
                self.db.update_account_status(account.id, LeadStatus.FAILED)
                failed += 1

        self.on_status(
            f"Found {total_contacts} contacts across {len(accounts) - failed} accounts "
            f"({failed} failed)."
        )
        self.db.update_campaign_stage(campaign_id, PipelineStage.CONTACT_REVIEW)

    def _review_contacts(self, campaign_id: str):
        """Human review of discovered contacts."""
        contacts = self.db.get_contacts(campaign_id, LeadStatus.CONTACT_FOUND)

        if not contacts:
            self.on_status("No contacts to review.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.RESEARCH)
            return

        if self.on_review:
            approved_ids = self.on_review("contacts", contacts)
            all_ids = [c.id for c in contacts if c.id]

            approved_set = set(approved_ids)
            rejected_ids = [cid for cid in all_ids if cid not in approved_set]

            self.db.batch_update_contact_status(approved_ids, LeadStatus.CONTACT_APPROVED)
            self.db.batch_update_contact_status(rejected_ids, LeadStatus.REJECTED)

            self.on_status(
                f"Contacts: {len(approved_ids)} approved, {len(rejected_ids)} rejected."
            )
        else:
            all_ids = [c.id for c in contacts if c.id]
            self.db.batch_update_contact_status(all_ids, LeadStatus.CONTACT_APPROVED)
            self.on_status(f"Auto-approved {len(all_ids)} contacts.")

        self.db.update_campaign_stage(campaign_id, PipelineStage.RESEARCH)

    def _run_research(self, campaign_id: str):
        """Stage 3: Personalization Research."""
        contacts = self.db.get_contacts(campaign_id, LeadStatus.CONTACT_APPROVED)

        if not contacts:
            self.on_status("No approved contacts - skipping research.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.RESEARCH_REVIEW)
            return

        self.on_status(f"Researching {len(contacts)} contacts...")

        researched = 0
        failed = 0

        for contact in contacts:
            # Get the account for context
            accounts = self.db.get_accounts(campaign_id)
            account = None
            for a in accounts:
                if a.id == contact.account_id:
                    account = a
                    break

            if not account:
                logger.error(f"Account not found for contact {contact.full_name}")
                failed += 1
                continue

            try:
                dossier = research.run(self.agent, contact, account, self.api_config)
                dossier.contact_id = contact.id
                dossier.campaign_id = campaign_id
                self.db.insert_dossier(dossier)
                self.db.update_contact_status(contact.id, LeadStatus.RESEARCHED)

                for source in dossier.data_sources:
                    self.db.log_gdpr_action(
                        contact.email or contact.full_name,
                        "collected",
                        "personalization_data",
                        source,
                    )

                researched += 1
            except Exception as e:
                logger.error(f"Research failed for {contact.full_name}: {e}")
                self.db.update_contact_status(contact.id, LeadStatus.FAILED)
                failed += 1

        self.on_status(f"Researched {researched} contacts ({failed} failed).")
        self.db.update_campaign_stage(campaign_id, PipelineStage.RESEARCH_REVIEW)

    def _review_research(self, campaign_id: str):
        """Human review of research dossiers - lightweight, mostly informational."""
        contacts = self.db.get_contacts(campaign_id, LeadStatus.RESEARCHED)

        if not contacts:
            self.on_status("No research to review.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.EMAIL_COMPOSITION)
            return

        if self.on_review:
            # Build review items: contact + dossier pairs
            review_items = []
            for contact in contacts:
                dossier = self.db.get_dossier_for_contact(contact.id)
                review_items.append({"contact": contact, "dossier": dossier})

            approved_ids = self.on_review("research", review_items)
            # For research review, approved_ids are contact IDs to proceed with
            # Non-approved contacts get set back - but typically all proceed
            self.on_status(f"{len(approved_ids)} contacts proceeding to email composition.")
        else:
            self.on_status(f"Auto-approved research for {len(contacts)} contacts.")

        self.db.update_campaign_stage(campaign_id, PipelineStage.EMAIL_COMPOSITION)

    def _run_email_composition(self, campaign_id: str):
        """Stage 4: Email Composition."""
        contacts = self.db.get_contacts(campaign_id, LeadStatus.RESEARCHED)

        if not contacts:
            self.on_status("No researched contacts - skipping email composition.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.EMAIL_REVIEW)
            return

        config = CampaignConfig.model_validate_json(
            self.db.get_campaign(campaign_id).config_json
        )

        self.on_status(f"Composing emails for {len(contacts)} contacts...")

        composed = 0
        failed = 0

        for contact in contacts:
            # Get account and dossier
            accounts = self.db.get_accounts(campaign_id)
            account = None
            for a in accounts:
                if a.id == contact.account_id:
                    account = a
                    break

            dossier = self.db.get_dossier_for_contact(contact.id)

            if not account or not dossier:
                logger.error(f"Missing data for {contact.full_name}")
                failed += 1
                continue

            try:
                draft = email_composer.run(
                    self.agent, contact, account, dossier, config
                )
                draft.contact_id = contact.id
                draft.dossier_id = dossier.id
                draft.campaign_id = campaign_id
                self.db.insert_draft_email(draft)
                self.db.update_contact_status(contact.id, LeadStatus.EMAIL_DRAFTED)
                composed += 1
            except Exception as e:
                logger.error(f"Email composition failed for {contact.full_name}: {e}")
                self.db.update_contact_status(contact.id, LeadStatus.FAILED)
                failed += 1

        self.on_status(f"Composed {composed} emails ({failed} failed).")
        self.db.update_campaign_stage(campaign_id, PipelineStage.EMAIL_REVIEW)

    def _review_emails(self, campaign_id: str):
        """Human review of draft emails."""
        drafts = self.db.get_draft_emails(campaign_id, LeadStatus.EMAIL_DRAFTED)

        if not drafts:
            self.on_status("No emails to review.")
            self.db.update_campaign_stage(campaign_id, PipelineStage.EXPORT)
            return

        if self.on_review:
            # Build review items: contact + email pairs
            review_items = []
            for draft in drafts:
                contact = self.db.get_contact(draft.contact_id)
                review_items.append({"contact": contact, "email": draft})

            approved_ids = self.on_review("emails", review_items)
            all_ids = [d.id for d in drafts if d.id]

            approved_set = set(approved_ids)
            rejected_ids = [did for did in all_ids if did not in approved_set]

            self.db.batch_update_draft_email_status(approved_ids, LeadStatus.EMAIL_APPROVED)
            self.db.batch_update_draft_email_status(rejected_ids, LeadStatus.REJECTED)

            self.on_status(
                f"Emails: {len(approved_ids)} approved, {len(rejected_ids)} rejected."
            )
        else:
            all_ids = [d.id for d in drafts if d.id]
            self.db.batch_update_draft_email_status(all_ids, LeadStatus.EMAIL_APPROVED)
            self.on_status(f"Auto-approved {len(all_ids)} emails.")

        self.db.update_campaign_stage(campaign_id, PipelineStage.EXPORT)

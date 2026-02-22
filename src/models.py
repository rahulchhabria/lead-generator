"""Pydantic data models for the lead generation pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LeadStatus(str, Enum):
    DISCOVERED = "discovered"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONTACT_FOUND = "contact_found"
    CONTACT_APPROVED = "contact_approved"
    RESEARCHED = "researched"
    EMAIL_DRAFTED = "email_drafted"
    EMAIL_APPROVED = "email_approved"
    FAILED = "failed"
    OPTED_OUT = "opted_out"


class PipelineStage(str, Enum):
    DISCOVERY = "discovery"
    DISCOVERY_REVIEW = "discovery_review"
    CONTACT_FINDING = "contact_finding"
    CONTACT_REVIEW = "contact_review"
    RESEARCH = "research"
    RESEARCH_REVIEW = "research_review"
    EMAIL_COMPOSITION = "email_composition"
    EMAIL_REVIEW = "email_review"
    EXPORT = "export"
    COMPLETED = "completed"


class ICPDefinition(BaseModel):
    """Flexible ICP input - natural language plus optional structured fields."""

    description: str = Field(..., description="Natural language ICP description")
    target_roles: list[str] = Field(
        default_factory=list, description="e.g. ['CTO', 'VP Engineering']"
    )
    company_size: Optional[str] = Field(None, description="e.g. '50-500 employees'")
    industries: list[str] = Field(default_factory=list, description="e.g. ['SaaS', 'FinTech']")
    geographies: list[str] = Field(default_factory=list, description="e.g. ['US', 'EU', 'UK']")
    technologies: list[str] = Field(
        default_factory=list, description="e.g. ['Python', 'Kubernetes']"
    )
    exclusions: list[str] = Field(
        default_factory=list, description="Companies/domains to exclude"
    )
    max_leads: int = Field(default=50, ge=1, le=500)


class DomainEntry(BaseModel):
    """A single domain in a user-provided domain list."""

    domain: str
    company_name: Optional[str] = None
    notes: Optional[str] = None


class DomainList(BaseModel):
    """User-provided list of target domains (skip account discovery)."""

    target_roles: list[str] = Field(
        default_factory=list, description="Roles to find at these companies"
    )
    domains: list[DomainEntry] = Field(default_factory=list)


class Account(BaseModel):
    """A target company discovered by Agent 1 or provided by the user."""

    id: Optional[int] = None
    campaign_id: str = ""
    company_name: str
    domain: str
    industry: Optional[str] = None
    employee_count: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    relevance_reasoning: str = Field(
        default="", description="Why this company matches the ICP"
    )
    data_sources: list[str] = Field(default_factory=list)
    source: str = Field(default="discovered", description="'discovered' or 'provided'")
    status: LeadStatus = LeadStatus.DISCOVERED
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Contact(BaseModel):
    """A person at an approved account, found by Agent 2."""

    id: Optional[int] = None
    account_id: int = 0
    campaign_id: str = ""
    first_name: str
    last_name: str
    full_name: str = ""
    title: Optional[str] = None
    email: Optional[str] = None
    email_confidence: Optional[int] = Field(None, ge=0, le=100)
    email_verified: bool = False
    email_source: Optional[str] = Field(
        None, description="'hunter_finder', 'hunter_domain', 'pattern_dns', etc."
    )
    linkedin_url: Optional[str] = None
    data_sources: list[str] = Field(default_factory=list)
    status: LeadStatus = LeadStatus.CONTACT_FOUND
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context):
        if not self.full_name:
            self.full_name = f"{self.first_name} {self.last_name}"


class PersonalizationDossier(BaseModel):
    """Deep research on a contact, built by Agent 3."""

    id: Optional[int] = None
    contact_id: int = 0
    campaign_id: str = ""
    github_username: Optional[str] = None
    github_repos: list[str] = Field(default_factory=list)
    github_languages: list[str] = Field(default_factory=list)
    recent_posts: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    education: Optional[str] = None
    open_source_contributions: list[str] = Field(default_factory=list)
    speaking_engagements: list[str] = Field(default_factory=list)
    personal_details: list[str] = Field(default_factory=list)
    raw_research_notes: str = ""
    data_sources: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DraftEmail(BaseModel):
    """A cold email draft written by Agent 4."""

    id: Optional[int] = None
    contact_id: int = 0
    dossier_id: int = 0
    campaign_id: str = ""
    subject_line: str
    body: str
    personalization_hooks: list[str] = Field(default_factory=list)
    tone: str = "casual"
    includes_unsubscribe: bool = True
    includes_physical_address: bool = True
    status: LeadStatus = LeadStatus.EMAIL_DRAFTED
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CampaignConfig(BaseModel):
    """Campaign-level configuration loaded from YAML."""

    sender_name: str = "Your Name"
    sender_title: str = "Your Title"
    sender_company: str = "Your Company"
    sender_email: str = "you@example.com"
    physical_address: str = "123 Main St, City, State ZIP"
    tone: str = "casual"
    max_words: int = 150
    cta_type: str = "meeting"
    unsubscribe_text: str = (
        "Not interested? Reply 'unsubscribe' and I'll remove you immediately."
    )
    daily_send_limit: int = 100
    email_min_confidence: int = 50
    skip_unverified_emails: bool = False
    research_depth: str = "standard"
    value_proposition: str = ""


class Campaign(BaseModel):
    """A pipeline campaign run."""

    id: str
    icp_json: Optional[str] = None
    domains_json: Optional[str] = None
    config_json: str = ""
    current_stage: PipelineStage = PipelineStage.DISCOVERY
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

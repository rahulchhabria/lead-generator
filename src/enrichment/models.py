"""Pydantic models for company enrichment data."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class TechStack(BaseModel):
    name: str
    category: str
    confidence: str = "detected"
    version: Optional[str] = None


class FundingRound(BaseModel):
    type: Optional[str] = None
    amount: Optional[str] = None
    date: Optional[str] = None
    investors: list[str] = Field(default_factory=list)
    valuation: Optional[str] = None


class JobPosting(BaseModel):
    title: str
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    url: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    description: Optional[str] = None


class DepartmentHiring(BaseModel):
    engineering: int = 0
    sales: int = 0
    marketing: int = 0
    customer_success: int = 0
    operations: int = 0
    other: int = 0


class HiringData(BaseModel):
    open_positions: int = 0
    job_listings: list[JobPosting] = Field(default_factory=list)
    department_breakdown: DepartmentHiring = Field(default_factory=DepartmentHiring)
    top_skills: list[str] = Field(default_factory=list)
    hiring_velocity: int = 0


class TechnographicData(BaseModel):
    frontend_frameworks: list[TechStack] = Field(default_factory=list)
    backend_frameworks: list[TechStack] = Field(default_factory=list)
    databases: list[TechStack] = Field(default_factory=list)
    cloud_providers: list[TechStack] = Field(default_factory=list)
    analytics: list[TechStack] = Field(default_factory=list)
    observability: list[TechStack] = Field(default_factory=list)
    payments: list[TechStack] = Field(default_factory=list)
    customer_support: list[TechStack] = Field(default_factory=list)
    marketing: list[TechStack] = Field(default_factory=list)
    auth: list[TechStack] = Field(default_factory=list)
    cdn: list[TechStack] = Field(default_factory=list)
    infrastructure: list[TechStack] = Field(default_factory=list)
    all_technologies: list[str] = Field(default_factory=list)


class GitHubData(BaseModel):
    org_name: Optional[str] = None
    org_url: Optional[str] = None
    public_repos: int = 0
    total_stars: int = 0
    total_forks: int = 0
    top_repos: list[dict] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    language_breakdown: dict[str, float] = Field(default_factory=dict)
    recent_commits_30d: int = 0
    contributors_30d: int = 0


class MobileApp(BaseModel):
    name: Optional[str] = None
    app_id: Optional[str] = None
    url: str
    detection_method: str


class MobileApps(BaseModel):
    has_ios_app: bool = False
    has_android_app: bool = False
    ios_apps: list[MobileApp] = Field(default_factory=list)
    android_apps: list[MobileApp] = Field(default_factory=list)


class LeadershipPerson(BaseModel):
    name: str
    role: Optional[str] = None
    linkedin_url: Optional[str] = None


class CompetitorMove(BaseModel):
    competitor: str
    event: str
    date: Optional[str] = None
    impact: Optional[str] = None


class Acquisition(BaseModel):
    company_acquired: str
    date: Optional[str] = None
    amount: Optional[str] = None
    description: Optional[str] = None


class AIInsights(BaseModel):
    recent_news: list[str] = Field(default_factory=list)
    growth_stage: Optional[str] = None
    competitive_landscape: list[str] = Field(default_factory=list)
    key_differentiators: list[str] = Field(default_factory=list)
    recent_product_launches: list[str] = Field(default_factory=list)
    recent_acquisitions: list[Acquisition] = Field(default_factory=list)
    competitor_moves: list[CompetitorMove] = Field(default_factory=list)


class EnrichmentData(BaseModel):
    """Full company enrichment data."""
    domain: str
    company_name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    long_description: Optional[str] = None

    founded_year: Optional[int] = None
    employee_count: Optional[int] = None
    employee_count_range: Optional[str] = None
    engineering_count: Optional[int] = None
    hq_city: Optional[str] = None
    hq_state: Optional[str] = None
    hq_country: Optional[str] = None
    industry: Optional[str] = None
    industry_keywords: list[str] = Field(default_factory=list)

    total_funding_raised: Optional[str] = None
    latest_funding_round: Optional[FundingRound] = None
    all_funding_rounds: list[FundingRound] = Field(default_factory=list)
    current_valuation: Optional[str] = None

    ceo: Optional[LeadershipPerson] = None
    founders: list[LeadershipPerson] = Field(default_factory=list)
    recent_leadership_changes: list[str] = Field(default_factory=list)

    technographic: Optional[TechnographicData] = None
    mobile_apps: Optional[MobileApps] = None
    hiring: Optional[HiringData] = None
    github_activity: Optional[GitHubData] = None

    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    github_url: Optional[str] = None
    crunchbase_url: Optional[str] = None

    ai_insights: Optional[AIInsights] = None

    data_quality: str = "low"
    confidence_score: int = 0
    sources: list[str] = Field(default_factory=list)
    last_enriched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    enrichment_error: Optional[str] = None

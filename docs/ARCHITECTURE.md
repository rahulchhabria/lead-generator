# Architecture: Prospect Intelligence Platform

## Overview

Prospect Intelligence is a unified B2B sales research platform that combines:
1. **Company Enrichment** - Deep firmographic, technographic, and hiring data for any domain
2. **Lead Generation Pipeline** - Multi-agent AI pipeline that discovers companies, finds contacts, researches them, and drafts personalized emails
3. **Campaign Management** - Full campaign lifecycle with human review at each stage

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Prospect Intelligence Platform                     │
│                                                                       │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │   Enrichment    │  │  Lead Generation │  │   Campaign Mgmt   │  │
│  │                 │  │    Pipeline      │  │                   │  │
│  │ • Single domain │  │                  │  │ • Create/resume   │  │
│  │ • Bulk upload   │  │ 1. ICP Discovery │  │ • Human review    │  │
│  │ • Library view  │  │ 2. Contact Find  │  │ • Stage progress  │  │
│  │ • CSV export    │  │ 3. Research      │  │ • CSV export      │  │
│  │                 │  │ 4. Email Compose │  │                   │  │
│  └────────┬────────┘  └────────┬─────────┘  └─────────┬─────────┘  │
│           │                    │                       │             │
│           └────────────────────┼───────────────────────┘            │
│                                │                                     │
│  ┌─────────────────────────────▼──────────────────────────────────┐ │
│  │                       FastAPI Backend                           │ │
│  │  /api/enrichment  /api/campaigns  /api/accounts  /api/contacts │ │
│  └─────────────────────────────┬──────────────────────────────────┘ │
│                                │                                     │
│  ┌─────────────────────────────▼──────────────────────────────────┐ │
│  │                    SQLite Database                              │ │
│  │  campaigns / accounts / contacts / dossiers /                  │ │
│  │  draft_emails / enrichment_data / gdpr_log / suppression_list  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### `src/enrichment/` — Company Enrichment Engine
Ported from the TypeScript `local-enrichment-tool`. Pure Python, no Node.js dependency.

| File | Purpose |
|------|---------|
| `engine.py` | Main orchestrator: fetches website, runs all sub-modules in parallel, calls Claude for AI synthesis |
| `tech_detector.py` | Detects 50+ technologies from HTML (React, AWS, Sentry, etc.) |
| `job_scraper.py` | Scrapes Greenhouse, Lever, Ashby, and company careers pages |
| `github_fetcher.py` | Fetches GitHub org data: repos, stars, languages |
| `linkedin_headcount.py` | Estimates engineering headcount via Google/LinkedIn |
| `mobile_app_detector.py` | Detects iOS/Android apps from HTML |
| `models.py` | Pydantic models for all enrichment data structures |

**Enrichment flow:**
```
domain input
    │
    ├── fetch website HTML (parallel)
    ├── scrape job boards (parallel)
    └── fetch GitHub org (parallel)
            │
            ├── tech_detector(html)
            ├── mobile_app_detector(html)
            ├── extract social links
            └── Claude AI synthesis (structured extraction)
                        │
                        ▼
               EnrichmentData model
                        │
                   save to DB
```

### `src/agents/` — AI Agents (Lead Generation Pipeline)
Each agent uses Claude's tool-use capability in an agentic loop.

| Agent | Role | Tools Used |
|-------|------|-----------|
| `account_discovery.py` | Find companies matching ICP | web_search, web_scraper |
| `contact_email.py` | Find people + verify emails | web_search, web_scraper, hunter.io, email_patterns |
| `research.py` | Deep research on contacts | web_search, web_scraper, github_api |
| `email_composer.py` | Write personalized cold emails | (uses dossier data, no tools) |

### `src/pipeline.py` — Pipeline Orchestrator
Manages the 10-stage pipeline with checkpoint/resume support. Integrates enrichment as an automatic step after account approval.

```
DISCOVERY → DISCOVERY_REVIEW → [AUTO-ENRICH] → CONTACT_FINDING →
CONTACT_REVIEW → RESEARCH → RESEARCH_REVIEW → EMAIL_COMPOSITION →
EMAIL_REVIEW → EXPORT → COMPLETED
```

### `src/web/` — FastAPI Web Server
REST API for all platform features. Background job system for long-running tasks.

### `src/database.py` — Unified SQLite Layer
Single database for all data: pipeline data + enrichment data.

---

## Data Flow

### Use Case 1: Single Domain Enrichment
```
User enters domain → POST /api/enrichment/single →
    engine.enrich_domain(domain) →
        parallel: fetch_html, scrape_jobs, fetch_github →
        tech_detector, mobile_detector, social_extractor →
        claude_ai_synthesis →
    upsert_enrichment(db) →
Return EnrichmentData
```

### Use Case 2: Bulk Enrichment
```
User uploads CSV → POST /api/enrichment/upload →
    parse CSV → create background Job →
    for each domain: enrich_domain() → upsert_enrichment() →
    Job status polls via GET /api/jobs/{job_id}
```

### Use Case 3: ICP → Enriched Accounts with Contacts
```
User defines ICP → POST /api/campaigns/ →
    AccountDiscoveryAgent(icp) → discover companies →
    [auto-enrich all discovered accounts] →
    ContactFindingAgent(accounts) → find contacts →
    ResearchAgent(contacts) → build dossiers →
    EmailComposerAgent(dossiers) → draft emails →
Campaign: accounts + enrichment + contacts + emails
```

---

## Database Schema

```
campaigns           - One per pipeline run
accounts            - Target companies (discovered or provided)
contacts            - People at accounts
dossiers            - Research data per contact
draft_emails        - AI-composed outreach emails
enrichment_data     - Company enrichment (shared, domain-keyed)
gdpr_log            - Audit trail for GDPR compliance
suppression_list    - Emails that opted out
```

The `enrichment_data` table is **shared across campaigns** - enrichment for `stripe.com` is cached and reused across all campaigns.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Backend | Python 3.11, FastAPI, Pydantic v2 |
| Database | SQLite (WAL mode) → PostgreSQL-ready |
| CLI | Typer + Rich |
| Web Scraping | requests, BeautifulSoup4 |
| Frontend | React 18, TypeScript, Tailwind CSS, Vite |
| State Management | TanStack Query (React Query) |
| Background Jobs | Threading (local) → Celery-ready |
| Container | Docker + Docker Compose |

---

## API Reference

Full interactive docs available at `http://localhost:8000/api/docs` (Swagger UI) when the server is running.

### Key Endpoints

```
GET  /api/health                        - Health check
GET  /api/status                        - API key status

POST /api/enrichment/single             - Enrich one domain
POST /api/enrichment/bulk               - Bulk enrich (background job)
POST /api/enrichment/upload             - Upload CSV/YAML for bulk enrich
GET  /api/enrichment/                   - List all enriched companies
GET  /api/enrichment/{domain}           - Get enrichment for domain

POST /api/campaigns/                    - Create + start campaign
GET  /api/campaigns/                    - List campaigns
GET  /api/campaigns/{id}                - Campaign details
GET  /api/campaigns/{id}/accounts       - Campaign accounts
GET  /api/campaigns/{id}/contacts       - Campaign contacts
GET  /api/campaigns/{id}/emails         - Campaign draft emails
POST /api/campaigns/{id}/accounts/review - Approve/reject accounts
POST /api/campaigns/{id}/contacts/review - Approve/reject contacts
POST /api/campaigns/{id}/emails/review  - Approve/reject emails

GET  /api/accounts/                     - All accounts (all campaigns)
GET  /api/accounts/{id}                 - Account detail + enrichment + contacts
POST /api/accounts/{id}/enrich          - Trigger enrichment for account

GET  /api/contacts/                     - All contacts (all campaigns)
GET  /api/contacts/{id}                 - Contact detail + dossier + emails

GET  /api/exports/{campaign_id}/csv     - Export campaign to CSV
GET  /api/exports/enrichment/csv        - Export enrichments to CSV

GET  /api/jobs/{job_id}                 - Background job status
```

---

## Adding New Data Sources

To add a new enrichment data source:

1. Create `src/enrichment/my_source.py` with a function `fetch_my_data(domain, company_name) -> dict`
2. Add the new fields to `src/enrichment/models.py` → `EnrichmentData`
3. Call your function in `src/enrichment/engine.py` → `enrich_domain()` (add to ThreadPoolExecutor)
4. Map the result to the `EnrichmentData` model
5. Add corresponding columns to `enrichment_data` table in `src/database.py`

---

## Background Jobs

Long-running tasks (bulk enrichment, campaign pipeline) run in background threads via `src/web/background.py`.

For production with multiple workers, replace the in-memory `JobManager` with:
- **Celery + Redis**: Full task queue with persistence, retries, monitoring
- **RQ (Redis Queue)**: Simpler alternative to Celery

The `Job` interface is designed to be a drop-in replacement.

---

## Future Improvements

- [ ] PostgreSQL migration with Alembic
- [ ] Celery task queue for distributed processing
- [ ] WebSocket real-time updates (instead of polling)
- [ ] User accounts + team workspaces
- [ ] CRM integrations (Salesforce, HubSpot export)
- [ ] Email sequence builder (multi-step outreach)
- [ ] Analytics dashboard (reply rates, open rates)
- [ ] Rate limiting on AI calls (cost control)
- [ ] Apollo.io / ZoomInfo enrichment integration
- [ ] LinkedIn Sales Navigator integration

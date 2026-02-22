# Prospect Intelligence

Unified B2B prospect research and lead generation platform. Combines deep company enrichment with an AI-powered multi-agent outreach pipeline.

## What It Does

**Company Enrichment** — Research any company before you reach out:
- Firmographics: employees, funding, leadership, location, founded year
- Technographics: 50+ technologies detected (React, AWS, Sentry, etc.)
- Hiring intelligence: open roles, departments, top skills
- GitHub activity: repos, languages, stars
- AI insights: growth stage, competitors, recent news

**Lead Generation Pipeline** — Full end-to-end AI outreach pipeline:
1. ICP-based company discovery (AI finds companies matching your criteria)
2. OR: upload your own domain list
3. Auto-enrich all accounts with company data
4. Find decision-maker contacts with verified emails
5. Deep research on each contact (GitHub, blog posts, interests)
6. AI-composed personalized cold emails
7. Human review at each stage
8. Export to CSV

**Campaign Management** — Full lifecycle tracking with checkpoint/resume.

---

## Quick Start

### Prerequisites
- Python 3.11+
- `ANTHROPIC_API_KEY` (required)
- Optional: `SERPER_API_KEY`, `HUNTER_API_KEY`, `GITHUB_TOKEN`

### Install

```bash
git clone <repo>
cd lead-generator
pip install -e .
cp .env.example .env
# Edit .env with your API keys
```

### CLI Usage

```bash
# Enrich a single domain
leadgen enrich stripe.com

# Bulk enrich from CSV
leadgen enrich-bulk my_domains.csv

# Run a new campaign from ICP
leadgen run config/example_icp.yaml --config config/default_campaign.yaml

# Run a campaign from domain list
leadgen run --domains config/example_domains.yaml --config config/default_campaign.yaml

# Resume a paused campaign
leadgen resume <campaign_id>

# Start the web UI
leadgen serve
# Open http://localhost:8000
```

### Web UI

```bash
# Backend only (serves API + React app)
leadgen serve

# Or with Docker (full stack)
docker compose up
# Open http://localhost:3000
```

---

## Project Structure

```
src/
├── enrichment/          # Company enrichment engine
│   ├── engine.py        # Main orchestrator
│   ├── tech_detector.py # Tech stack detection
│   ├── job_scraper.py   # Job board scraping
│   ├── github_fetcher.py
│   ├── linkedin_headcount.py
│   ├── mobile_app_detector.py
│   └── models.py
├── agents/              # AI agents (lead gen pipeline)
│   ├── base.py
│   ├── account_discovery.py
│   ├── contact_email.py
│   ├── research.py
│   └── email_composer.py
├── web/                 # FastAPI web server
│   ├── main.py
│   ├── background.py    # Background job manager
│   └── routes/
│       ├── campaigns.py
│       ├── enrichment.py
│       ├── accounts.py
│       ├── contacts.py
│       ├── exports.py
│       └── jobs.py
├── tools/               # Shared tools (search, email, etc.)
├── pipeline.py          # Pipeline orchestrator
├── cli.py               # Typer CLI
├── models.py            # Pydantic models
└── database.py          # SQLite CRUD

frontend/                # React + TypeScript + Tailwind UI
├── src/
│   ├── pages/           # Dashboard, Enrichment, Campaigns, etc.
│   ├── components/      # Reusable UI components
│   └── api/client.ts    # Type-safe API client

docs/
├── ARCHITECTURE.md      # Full architecture documentation
└── HOSTING.md           # Guide for internal hosted deployment
```

---

## API Keys

| Key | Purpose | Required? |
|-----|---------|-----------|
| `ANTHROPIC_API_KEY` | Claude AI for all agents | **Yes** |
| `SERPER_API_KEY` | Google Search (falls back to DuckDuckGo) | No |
| `HUNTER_API_KEY` | Email finding + verification | No |
| `GITHUB_TOKEN` | Higher GitHub rate limits | No |

---

## Hosting

See [`docs/HOSTING.md`](docs/HOSTING.md) for a complete guide on deploying this as an internal shared service behind SSO/Sentry login.

**TL;DR**: Docker Compose is included. Add an oauth2-proxy in front for auth. Swap SQLite for PostgreSQL for multi-user production use.

---

## GDPR Compliance

Built-in compliance features:
- Audit log for all data collection
- Right to be forgotten: `leadgen forget <email>`
- Suppression list for opted-out contacts
- All data collection uses public sources only

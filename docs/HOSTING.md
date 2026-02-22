# Hosting Guide: Prospect Intelligence as an Internal Service

This document is a handoff guide for internal engineering teams to take the local tool and deploy it as a shared internal service, secured behind Sentry login (or any SSO provider).

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      Internal Network / VPN                       │
│                                                                    │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────────────────┐ │
│  │  Browser  │───▶│  nginx/    │───▶│  FastAPI Backend         │ │
│  │  (React)  │    │  Auth Proxy │    │  (Python 3.11)           │ │
│  └──────────┘    └─────────────┘    │  • /api/campaigns        │ │
│                        │            │  • /api/enrichment        │ │
│                  ┌─────▼──────┐     │  • /api/accounts         │ │
│                  │  Sentry /  │     │  • /api/contacts         │ │
│                  │  Auth0 /   │     └──────────┬───────────────┘ │
│                  │  Okta SSO  │                │                  │
│                  └────────────┘     ┌──────────▼───────────────┐ │
│                                     │  SQLite (dev) /           │ │
│                                     │  PostgreSQL (prod)        │ │
│                                     └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Choose a Hosting Platform

### Option A: Single EC2 / VM (Simplest)
- Launch a `t3.medium` or larger instance
- Install Docker + Docker Compose
- Clone repo, set `.env`, run `docker compose -f docker-compose.prod.yml up -d`
- Put behind an ALB or nginx with SSL

### Option B: ECS / Fargate (Recommended for scale)
- Build and push Docker images to ECR
- Create ECS service for backend (1+ tasks)
- Serve frontend via S3 + CloudFront
- RDS PostgreSQL for persistent storage

### Option C: Internal Kubernetes
- Use provided Dockerfiles to build images
- Write K8s manifests (Deployment + Service + Ingress)
- Use Secrets for API keys
- PVC for SQLite or swap to PostgreSQL

---

## Step 2: Add Authentication (Sentry / SSO)

The app currently has **no auth**. Here are two ways to add it:

### Option A: Sentry Auth Proxy (Easiest)
Sentry can act as an SSO identity provider via their internal tools. You can put the app behind [oauth2-proxy](https://github.com/oauth2-proxy/oauth2-proxy) configured with Sentry's OIDC endpoint.

```nginx
# nginx.prod.conf - add this before your location blocks
auth_request /oauth2/auth;
error_page 401 = /oauth2/sign_in;

location /oauth2/ {
    proxy_pass http://oauth2-proxy:4180;
}
```

```yaml
# docker-compose.prod.yml addition
oauth2-proxy:
  image: quay.io/oauth2-proxy/oauth2-proxy:v7.6.0
  environment:
    - OAUTH2_PROXY_PROVIDER=oidc
    - OAUTH2_PROXY_OIDC_ISSUER_URL=https://sentry.io/  # or your internal SSO URL
    - OAUTH2_PROXY_CLIENT_ID=${SSO_CLIENT_ID}
    - OAUTH2_PROXY_CLIENT_SECRET=${SSO_CLIENT_SECRET}
    - OAUTH2_PROXY_COOKIE_SECRET=${COOKIE_SECRET}
    - OAUTH2_PROXY_EMAIL_DOMAINS=yourcompany.com
    - OAUTH2_PROXY_HTTP_ADDRESS=0.0.0.0:4180
    - OAUTH2_PROXY_UPSTREAM=http://frontend:80
```

### Option B: JWT Auth in FastAPI (More control)
The backend is pre-wired for JWT. Add these to `src/web/main.py`:

```python
# Already stubbed - implement in src/web/auth.py
from jose import JWTError, jwt
from fastapi.security import HTTPBearer

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"

# Add to routes that need auth:
# async def protected_route(token: str = Depends(verify_token)):
```

Add a `/api/auth/login` endpoint that validates against your SSO and returns a JWT. The React frontend stores it in localStorage and sends as `Authorization: Bearer <token>`.

### Option C: Cloudflare Access (Zero Trust)
If you use Cloudflare, put the app behind Cloudflare Access with your identity provider. Zero configuration changes needed in the app.

---

## Step 3: Swap SQLite → PostgreSQL

For multi-user shared deployment, replace SQLite with PostgreSQL:

1. Add `psycopg2-binary` and `SQLAlchemy>=2.0` to `pyproject.toml`
2. Set `DATABASE_URL=postgresql://user:pass@host:5432/prospect_intel` in env
3. Update `src/database.py` to use SQLAlchemy with the connection URL
4. Run schema migrations (use Alembic)

The `SCHEMA` string in `database.py` is standard SQL and will work on PostgreSQL with minor adjustments (e.g., `AUTOINCREMENT` → `SERIAL`).

---

## Step 4: API Keys Management

Store secrets in your secret manager, not in `.env` files:

| Secret | Purpose | Where to store |
|--------|---------|----------------|
| `ANTHROPIC_API_KEY` | Claude AI (required) | AWS Secrets Manager / Vault |
| `SERPER_API_KEY` | Web search | AWS Secrets Manager / Vault |
| `HUNTER_API_KEY` | Email finding | AWS Secrets Manager / Vault |
| `GITHUB_TOKEN` | GitHub data | AWS Secrets Manager / Vault |
| `SECRET_KEY` | JWT signing | AWS Secrets Manager / Vault |
| `SENTRY_DSN` | Error tracking | Environment variable |

---

## Step 5: GDPR / Compliance Considerations

The app already has GDPR compliance built in:
- **Audit log**: All data collection logged in `gdpr_log` table
- **Right to be forgotten**: `leadgen forget <email>` or `DELETE /api/contacts/{id}` (add endpoint)
- **Suppression list**: Emails that opted out are never contacted again
- **Data minimization**: Only collects publicly available data

For a hosted service, additionally:
- Add a data retention policy (auto-delete leads older than 90 days)
- Document your legal basis for processing (legitimate interest for B2B outreach)
- Add a privacy notice to the UI

---

## Step 6: Production Checklist

Before going live:

- [ ] SSL/TLS certificate configured (Let's Encrypt or internal CA)
- [ ] Auth proxy / SSO configured and tested
- [ ] All API keys in secret manager (not in code or `.env`)
- [ ] PostgreSQL set up with daily backups
- [ ] Sentry DSN configured for error tracking
- [ ] Rate limiting on enrichment endpoints (costly Claude calls)
- [ ] Log aggregation (CloudWatch / Datadog / Elastic)
- [ ] Health check endpoint monitored: `GET /api/health`
- [ ] Graceful shutdown configured
- [ ] Resource limits set in Docker/K8s (prevent runaway enrichment jobs)

---

## Recommended Internal Service Architecture

```
Sales Team Browsers
        │
        ▼
Cloudflare Access (SSO gate) ──► Identity Provider (Okta/Sentry)
        │
        ▼
Internal ALB / nginx (HTTPS)
        │
   ┌────┴────┐
   │         │
   ▼         ▼
Frontend   Backend API
(S3/CF or  (ECS Fargate,
 nginx)     2 tasks min)
                │
         ┌──────┴──────┐
         │              │
         ▼              ▼
    PostgreSQL      External APIs
    (RDS Multi-AZ)  (Anthropic, Serper,
                     Hunter, GitHub)
```

---

## Environment Variables Reference

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (graceful degradation if missing)
SERPER_API_KEY=...          # Better web search (falls back to DuckDuckGo)
HUNTER_API_KEY=...          # Email finding (falls back to pattern+DNS)
GITHUB_TOKEN=...            # Higher GitHub rate limits (60→5000/hr)

# Web server
PORT=8000
SECRET_KEY=...              # JWT signing key (generate with: openssl rand -hex 32)

# Database
DB_PATH=data/pipeline.db    # SQLite path (local)
DATABASE_URL=...            # PostgreSQL URL (production)

# Monitoring
SENTRY_DSN=...
```

---

## Questions?

Contact the original developer or file an issue in the repository.

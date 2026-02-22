"""Enrichment API routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.web.background import job_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["enrichment"])


def _get_db():
    from src.config import load_api_config
    from src.database import Database
    api_config = load_api_config()
    return Database(api_config.db_path)


class EnrichRequest(BaseModel):
    domain: str
    company_name: Optional[str] = None
    force_refresh: bool = False


class BulkEnrichRequest(BaseModel):
    domains: list[dict]


@router.post("/single")
def enrich_single(req: EnrichRequest):
    """Enrich a single domain (synchronous, cached)."""
    db = _get_db()
    try:
        if not req.force_refresh:
            existing = db.get_enrichment(req.domain)
            if existing:
                return existing

        from src.enrichment.engine import enrich_domain
        data = enrich_domain(req.domain, req.company_name)
        db.upsert_enrichment(data)
        return data.model_dump(mode="json")
    except Exception as e:
        logger.exception(f"Enrichment failed for {req.domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/bulk")
def enrich_bulk(req: BulkEnrichRequest):
    """Start bulk enrichment job in the background."""
    if not req.domains:
        raise HTTPException(status_code=400, detail="No domains provided")

    job = job_manager.create_job(f"Bulk enrichment: {len(req.domains)} domains")

    def _run(job, domains):
        from src.enrichment.engine import enrich_domain
        from src.config import load_api_config
        from src.database import Database

        api_config = load_api_config()
        db = Database(api_config.db_path)
        results = []
        total = len(domains)
        try:
            for i, entry in enumerate(domains):
                domain = entry.get("domain", "")
                if not domain:
                    continue
                job.update(
                    progress=int(i / total * 100),
                    message=f"Enriching {domain} ({i+1}/{total})",
                )
                try:
                    data = enrich_domain(domain, entry.get("company_name"))
                    db.upsert_enrichment(data)
                    results.append({"domain": domain, "status": "success",
                                    "company_name": data.company_name, "data_quality": data.data_quality})
                except Exception as e:
                    results.append({"domain": domain, "status": "error", "error": str(e)})
            return results
        finally:
            db.close()

    job_manager.run_in_thread(job, _run, req.domains)
    return {"job_id": job.job_id, "status": "started", "total": len(req.domains)}


@router.post("/upload")
async def upload_domains(file: UploadFile = File(...)):
    """Upload a CSV or YAML file of domains for bulk enrichment."""
    content = await file.read()
    text = content.decode("utf-8")
    domains = []

    if file.filename and file.filename.endswith(".csv"):
        import csv, io
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            domain = row.get("domain") or row.get("Domain") or row.get("DOMAIN")
            if domain:
                domains.append({
                    "domain": domain.strip(),
                    "company_name": row.get("company_name") or row.get("Company") or None,
                })
    else:
        import yaml
        raw = yaml.safe_load(text)
        if isinstance(raw, list):
            domains = raw
        elif isinstance(raw, dict) and "domains" in raw:
            domains = raw["domains"]

    if not domains:
        raise HTTPException(status_code=400, detail="No domains found in file")

    return enrich_bulk(BulkEnrichRequest(domains=domains))


@router.get("/")
def list_enrichments(limit: int = 50, offset: int = 0):
    """List all enriched accounts."""
    db = _get_db()
    try:
        return db.list_enrichments(limit=limit, offset=offset)
    finally:
        db.close()


@router.get("/{domain:path}")
def get_enrichment(domain: str, force_refresh: bool = False):
    """Get enrichment data for a specific domain."""
    db = _get_db()
    try:
        if not force_refresh:
            existing = db.get_enrichment(domain)
            if existing:
                return existing
        from src.enrichment.engine import enrich_domain
        data = enrich_domain(domain)
        db.upsert_enrichment(data)
        return data.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

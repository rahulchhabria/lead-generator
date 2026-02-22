"""Background job status routes."""
from fastapi import APIRouter, HTTPException

from src.web.background import job_manager

router = APIRouter(tags=["jobs"])


@router.get("/")
def list_jobs():
    """List all background jobs."""
    return [j.to_dict() for j in job_manager.list_jobs()]


@router.get("/{job_id}")
def get_job(job_id: str):
    """Get status of a background job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

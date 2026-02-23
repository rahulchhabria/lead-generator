"""Background job status routes."""
from fastapi import APIRouter, Depends, HTTPException

from src.web.auth import get_current_user
from src.web.background import job_manager

router = APIRouter(tags=["jobs"])


@router.get("/")
def list_jobs(current_user: dict = Depends(get_current_user)):
    """List background jobs for the current user."""
    return [j.to_dict() for j in job_manager.list_jobs(user_id=current_user["id"])]


@router.get("/{job_id}")
def get_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """Get status of a background job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

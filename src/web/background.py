"""Background job management for long-running tasks."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class Job:
    def __init__(self, job_id: str, description: str, user_id: Optional[str] = None):
        self.job_id = job_id
        self.description = description
        self.user_id = user_id
        self.status = "pending"
        self.progress = 0
        self.message: Optional[str] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update(self, status: str = None, progress: int = None, message: str = None):
        if status:
            self.status = status
        if progress is not None:
            self.progress = progress
        if message is not None:
            self.message = message
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class JobManager:
    """Thread-safe job manager for background tasks."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, description: str, user_id: Optional[str] = None) -> Job:
        job_id = str(uuid.uuid4())[:8]
        job = Job(job_id=job_id, description=description, user_id=user_id)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, user_id: Optional[str] = None) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        if user_id:
            return [j for j in jobs if j.user_id == user_id]
        return jobs

    def run_in_thread(self, job: Job, fn: Callable, *args, **kwargs) -> Job:
        """Run a function in a background thread, updating job status."""
        def _wrapper():
            job.update(status="running", progress=0, message="Starting...")
            try:
                result = fn(job, *args, **kwargs)
                job.result = result
                job.update(status="completed", progress=100, message="Done")
            except Exception as e:
                logger.exception(f"Job {job.job_id} failed: {e}")
                job.error = str(e)
                job.update(status="failed", message=f"Error: {e}")

        t = threading.Thread(target=_wrapper, daemon=True)
        t.start()
        return job


# Global singleton
job_manager = JobManager()

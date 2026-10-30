from fastapi import APIRouter, Request

from meetinglog.domain import Job
from meetinglog.jobs.repository import JobRepository

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=Job)
def get(request: Request, job_id: str):
    return JobRepository(request.app.state.db).get(job_id)


@router.post("/{job_id}/cancel", response_model=Job)
def cancel(request: Request, job_id: str):
    repository = JobRepository(request.app.state.db)
    repository.cancel(job_id)
    return repository.get(job_id)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
import uuid

from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate, JobStatusUpdate, JobResponse

router = APIRouter(prefix="/companies/{company_id}/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse)
def create_job(
    company_id: uuid.UUID,
    payload: JobCreate,
    db: Session = Depends(get_db),
):
    job = Job(company_id=company_id, **payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobResponse])
def list_jobs(
    company_id: uuid.UUID,
    scheduled_date: date | None = None,
    status: JobStatus | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Job).filter_by(company_id=company_id)
    if scheduled_date:
        query = query.filter(Job.scheduled_date == scheduled_date)
    if status:
        query = query.filter(Job.status == status)
    return query.order_by(Job.scheduled_date, Job.window_start).all()


@router.get("/{job_id}", response_model=JobResponse)
def get_job(company_id: uuid.UUID, job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(Job).filter_by(id=job_id, company_id=company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}/status")
def update_job_status(
    company_id: uuid.UUID,
    job_id: uuid.UUID,
    payload: JobStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update a job's status — called by the tech when they arrive or complete."""
    job = db.query(Job).filter_by(id=job_id, company_id=company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = payload.status
    if payload.actual_arrival:
        job.actual_arrival = payload.actual_arrival
    if payload.actual_completion:
        job.actual_completion = payload.actual_completion
    db.commit()
    return {"status": "ok", "job_status": job.status}

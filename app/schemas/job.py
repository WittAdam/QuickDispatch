import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.models.job import JobPriority, JobStatus


class JobCreate(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = None
    customer_address: str
    lat: float
    lon: float
    scheduled_date: date
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    estimated_duration_minutes: int = 60
    required_skills: list[str] = []
    priority: JobPriority = JobPriority.normal
    job_type: Optional[str] = None
    notes: Optional[str] = None


class JobStatusUpdate(BaseModel):
    status: JobStatus
    actual_arrival: Optional[datetime] = None
    actual_completion: Optional[datetime] = None


class JobResponse(JobCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    status: JobStatus
    jobber_job_id: Optional[str] = None
    actual_arrival: Optional[datetime] = None
    actual_completion: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

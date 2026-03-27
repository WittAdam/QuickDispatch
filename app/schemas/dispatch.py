import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.models.job import JobPriority, JobStatus


class RouteJobDetail(BaseModel):
    sequence: int
    job_id: uuid.UUID
    customer_name: str
    customer_address: str
    job_type: Optional[str]
    priority: JobPriority
    status: JobStatus
    estimated_arrival: Optional[datetime]
    estimated_departure: Optional[datetime]
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    estimated_duration_minutes: int
    travel_minutes_from_prev: Optional[int]
    is_time_window_violated: bool
    violation_minutes: Optional[int]

    class Config:
        from_attributes = True


class TechRouteResponse(BaseModel):
    technician_id: uuid.UUID
    technician_name: str
    route_id: uuid.UUID
    route_date: date
    total_travel_minutes: int
    total_job_minutes: int
    violation_count: int
    last_optimized_at: Optional[datetime]
    optimization_notes: Optional[str]
    jobs: list[RouteJobDetail]


class DailyRoutesResponse(BaseModel):
    date: date
    routes: list[TechRouteResponse]
    unassigned_jobs: list[dict]


class InsertionOption(BaseModel):
    rank: int
    technician_id: uuid.UUID
    technician_name: str
    insert_at_sequence: int
    estimated_arrival: datetime
    travel_delta_minutes: int
    downstream_violations: int
    downstream_violation_minutes: int
    disruption_score: float
    note: str


class InsertionOptionsResponse(BaseModel):
    job_id: uuid.UUID
    options: list[InsertionOption]
    auto_assigned: Optional[InsertionOption] = None


class ApplyInsertionRequest(BaseModel):
    job_id: uuid.UUID
    technician_id: uuid.UUID
    insert_at_sequence: int


class BuildRoutesRequest(BaseModel):
    date: date
    company_id: uuid.UUID

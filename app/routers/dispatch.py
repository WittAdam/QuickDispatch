from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
import uuid

from app.core.database import get_db
from app.models.company import Company
from app.models.job import Job, JobStatus
from app.models.route import Route, RouteJob
from app.schemas.dispatch import (
    BuildRoutesRequest,
    DailyRoutesResponse,
    TechRouteResponse,
    RouteJobDetail,
    InsertionOption,
    InsertionOptionsResponse,
    ApplyInsertionRequest,
)
from app.services.scheduler import build_daily_routes, get_insertion_options, apply_insertion

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


def _get_company_or_404(db: Session, company_id: uuid.UUID) -> Company:
    company = db.query(Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _build_route_response(route: Route) -> TechRouteResponse:
    """Convert a Route DB object into the dispatcher dashboard response format."""
    jobs = []
    for rj in route.ordered_jobs:
        j = rj.job
        jobs.append(RouteJobDetail(
            sequence=rj.sequence,
            job_id=j.id,
            customer_name=j.customer_name,
            customer_address=j.customer_address,
            job_type=j.job_type,
            priority=j.priority,
            status=j.status,
            estimated_arrival=rj.estimated_arrival,
            estimated_departure=rj.estimated_departure,
            window_start=j.window_start,
            window_end=j.window_end,
            estimated_duration_minutes=j.estimated_duration_minutes,
            travel_minutes_from_prev=rj.travel_minutes_from_prev,
            is_time_window_violated=rj.is_time_window_violated,
            violation_minutes=rj.violation_minutes,
        ))
    return TechRouteResponse(
        technician_id=route.technician.id,
        technician_name=route.technician.name,
        route_id=route.id,
        route_date=route.route_date,
        total_travel_minutes=route.total_travel_minutes,
        total_job_minutes=route.total_job_minutes,
        violation_count=route.violation_count,
        last_optimized_at=route.last_optimized_at,
        optimization_notes=route.optimization_notes,
        jobs=jobs,
    )


@router.post("/build-daily-routes")
def build_routes(payload: BuildRoutesRequest, db: Session = Depends(get_db)):
    """
    Optimize and build all routes for a given date.
    Call this at the start of each day or after major schedule changes.
    """
    company = _get_company_or_404(db, payload.company_id)
    return build_daily_routes(db, company, payload.date)


@router.get("/daily-routes", response_model=DailyRoutesResponse)
def get_daily_routes(
    company_id: uuid.UUID,
    target_date: date,
    db: Session = Depends(get_db),
):
    """Main dispatcher dashboard view — all routes and jobs for a date."""
    company = _get_company_or_404(db, company_id)

    routes = db.query(Route).filter_by(company_id=company.id, route_date=target_date).all()
    for route in routes:
        for rj in route.route_jobs:
            _ = rj.job  # trigger lazy load

    unassigned = (
        db.query(Job)
        .filter(
            Job.company_id == company.id,
            Job.scheduled_date == target_date,
            Job.status == JobStatus.pending,
        )
        .all()
    )

    return DailyRoutesResponse(
        date=target_date,
        routes=[_build_route_response(r) for r in routes],
        unassigned_jobs=[
            {"id": str(j.id), "customer": j.customer_name, "priority": j.priority,
             "required_skills": j.required_skills}
            for j in unassigned
        ],
    )


@router.post("/insert-urgent", response_model=InsertionOptionsResponse)
def insert_urgent(
    company_id: uuid.UUID,
    job_id: uuid.UUID,
    auto_assign: bool = False,
    db: Session = Depends(get_db),
):
    """
    Score insertion options for a new or urgent job.
    Returns the top 3 ranked options. Set auto_assign=true to skip the choice.
    """
    company = _get_company_or_404(db, company_id)
    job = db.query(Job).filter_by(id=job_id, company_id=company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.pending, JobStatus.scheduled):
        raise HTTPException(status_code=400, detail=f"Job is already {job.status}")

    options = get_insertion_options(db, company, job)
    if not options:
        raise HTTPException(status_code=422, detail="No eligible technicians for this job")

    response_options = [
        InsertionOption(
            rank=i + 1,
            technician_id=opt.technician.id,
            technician_name=opt.technician.name,
            insert_at_sequence=opt.insert_at_sequence,
            estimated_arrival=opt.estimated_arrival,
            travel_delta_minutes=opt.travel_delta_minutes,
            downstream_violations=opt.downstream_violations,
            downstream_violation_minutes=opt.downstream_violation_minutes,
            disruption_score=round(opt.disruption_score, 2),
            note=opt.note,
        )
        for i, opt in enumerate(options)
    ]

    auto_assigned = None
    if auto_assign:
        best = options[0]
        apply_insertion(db, company, job, best.technician.id, best.insert_at_sequence)
        auto_assigned = response_options[0]

    return InsertionOptionsResponse(
        job_id=job_id,
        options=response_options,
        auto_assigned=auto_assigned,
    )


@router.post("/apply-insertion")
def apply_insertion_endpoint(
    company_id: uuid.UUID,
    payload: ApplyInsertionRequest,
    db: Session = Depends(get_db),
):
    """Apply a dispatcher-chosen insertion and recalculate all downstream ETAs."""
    company = _get_company_or_404(db, company_id)
    job = db.query(Job).filter_by(id=payload.job_id, company_id=company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    route = apply_insertion(db, company, job, payload.technician_id, payload.insert_at_sequence)
    return _build_route_response(route)


@router.get("/violations")
def get_violations(
    company_id: uuid.UUID,
    target_date: date,
    db: Session = Depends(get_db),
):
    """All time window violations across all routes for a date."""
    _get_company_or_404(db, company_id)

    violated = (
        db.query(RouteJob)
        .join(RouteJob.route)
        .join(RouteJob.job)
        .filter(
            Route.company_id == company_id,
            Route.route_date == target_date,
            RouteJob.is_time_window_violated == True,
        )
        .all()
    )

    return {
        "date": str(target_date),
        "violation_count": len(violated),
        "violations": [
            {
                "job_id": str(rj.job_id),
                "customer": rj.job.customer_name,
                "technician_id": str(rj.route.technician_id),
                "estimated_arrival": rj.estimated_arrival,
                "window_end": rj.job.window_end,
                "violation_minutes": rj.violation_minutes,
            }
            for rj in violated
        ],
    }

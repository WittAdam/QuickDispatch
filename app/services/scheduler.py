"""
Scheduler service — bridges the optimizer and the database.

This layer reads technicians and jobs from the DB, calls the optimizer,
then writes the results back. It owns all route-related DB writes.
"""
import uuid
from datetime import date, datetime
from sqlalchemy.orm import Session, selectinload

from app.models.company import Company
from app.models.technician import Technician
from app.models.job import Job, JobStatus
from app.models.route import Route, RouteJob
from app.services.optimizer import (
    ScheduledStop,
    InsertionScore,
    optimize_route,
    find_best_insertions,
    _work_start_datetime,
    _simulate_route_timing,
)


def _get_or_create_route(
    db: Session,
    company_id: uuid.UUID,
    tech_id: uuid.UUID,
    route_date: date,
) -> Route:
    """Fetch the existing route for this tech+date or create a blank one."""
    route = db.query(Route).filter_by(technician_id=tech_id, route_date=route_date).first()
    if not route:
        route = Route(company_id=company_id, technician_id=tech_id, route_date=route_date)
        db.add(route)
        db.flush()
    return route


def _write_stops_to_db(db: Session, route: Route, stops: list[ScheduledStop]) -> None:
    """
    Replace all route_jobs for this route with the new optimized stops.
    Updates job statuses and route totals at the same time.
    """
    db.query(RouteJob).filter_by(route_id=route.id).delete()

    total_travel = 0
    total_job = 0

    for stop in stops:
        rj = RouteJob(
            route_id=route.id,
            job_id=stop.job.id,
            sequence=stop.sequence,
            estimated_arrival=stop.estimated_arrival,
            estimated_departure=stop.estimated_departure,
            travel_minutes_from_prev=stop.travel_minutes_from_prev,
            is_time_window_violated=stop.is_time_window_violated,
            violation_minutes=stop.violation_minutes if stop.is_time_window_violated else None,
        )
        db.add(rj)
        stop.job.status = JobStatus.scheduled
        total_travel += stop.travel_minutes_from_prev or 0
        total_job += stop.job.estimated_duration_minutes

    route.total_travel_minutes = total_travel
    route.total_job_minutes = total_job
    route.last_optimized_at = datetime.utcnow()

    violations = sum(1 for s in stops if s.is_time_window_violated)
    route.optimization_notes = f"{violations} time window violation(s) flagged" if violations else None


def build_daily_routes(db: Session, company: Company, target_date: date) -> dict:
    """
    Full-day optimization: assign all pending jobs to technicians.

    Safe to call multiple times — each call fully replaces existing routes.
    Typically called at the start of each day or after major schedule changes.
    """
    techs: list[Technician] = db.query(Technician).filter_by(
        company_id=company.id, is_active=True
    ).all()

    if not techs:
        return {"error": "No active technicians found", "routes_built": 0}

    jobs: list[Job] = (
        db.query(Job)
        .filter(
            Job.company_id == company.id,
            Job.scheduled_date == target_date,
            Job.status.in_([JobStatus.pending, JobStatus.scheduled]),
        )
        .order_by(Job.priority.desc(), Job.window_start.asc().nullslast())
        .all()
    )

    if not jobs:
        return {"routes_built": 0, "jobs_assigned": 0, "unassigned_jobs": []}

    assigned_ids: set[uuid.UUID] = set()
    tech_stops: dict[uuid.UUID, list[ScheduledStop]] = {}

    for tech in techs:
        # Only offer jobs that haven't been claimed by a previous technician
        eligible = [
            j for j in jobs
            if tech.can_handle_job(j.required_skills) and j.id not in assigned_ids
        ]
        stops = optimize_route(tech, eligible, company, target_date)
        tech_stops[tech.id] = stops
        for stop in stops:
            assigned_ids.add(stop.job.id)

    unassigned = [j for j in jobs if j.id not in assigned_ids]

    for tech in techs:
        stops = tech_stops.get(tech.id, [])
        if not stops:
            continue
        route = _get_or_create_route(db, company.id, tech.id, target_date)
        _write_stops_to_db(db, route, stops)

    db.commit()

    return {
        "routes_built": sum(1 for t in techs if tech_stops.get(t.id)),
        "jobs_assigned": len(assigned_ids),
        "unassigned_jobs": [
            {"id": str(j.id), "customer": j.customer_name, "priority": j.priority}
            for j in unassigned
        ],
    }


def get_insertion_options(
    db: Session,
    company: Company,
    job: Job,
    top_n: int = 3,
) -> list[InsertionScore]:
    """
    Return the top N insertion options for an unscheduled job across all eligible techs.
    Called when an emergency arrives or the dispatcher wants to manually assign a job.
    """
    techs: list[Technician] = db.query(Technician).filter_by(
        company_id=company.id, is_active=True
    ).all()

    eligible = [t for t in techs if t.can_handle_job(job.required_skills)]
    if not eligible:
        return []

    tech_stops: dict[uuid.UUID, list[ScheduledStop]] = {}

    for tech in eligible:
        route = (
            db.query(Route)
            .filter_by(technician_id=tech.id, route_date=job.scheduled_date)
            .options(selectinload(Route.route_jobs).selectinload(RouteJob.job))
            .first()
        )
        if route:
            tech_stops[tech.id] = [
                ScheduledStop(
                    job=rj.job,
                    sequence=rj.sequence,
                    estimated_arrival=rj.estimated_arrival,
                    estimated_departure=rj.estimated_departure,
                    travel_minutes_from_prev=rj.travel_minutes_from_prev or 0,
                    is_time_window_violated=rj.is_time_window_violated,
                    violation_minutes=rj.violation_minutes or 0,
                )
                for rj in route.ordered_jobs
            ]
        else:
            tech_stops[tech.id] = []

    return find_best_insertions(eligible, tech_stops, job, company, job.scheduled_date, top_n)


def apply_insertion(
    db: Session,
    company: Company,
    job: Job,
    technician_id: uuid.UUID,
    insert_at_sequence: int,
) -> Route:
    """
    Apply a dispatcher-chosen insertion: place the job at the given position,
    recalculate all downstream ETAs, and save to DB.
    """
    tech = db.query(Technician).filter_by(id=technician_id).first()
    if not tech:
        raise ValueError(f"Technician {technician_id} not found")

    route = _get_or_create_route(db, company.id, tech.id, job.scheduled_date)
    db.refresh(route)

    current_stops = [
        ScheduledStop(
            job=rj.job,
            sequence=rj.sequence,
            estimated_arrival=rj.estimated_arrival,
            estimated_departure=rj.estimated_departure,
            travel_minutes_from_prev=rj.travel_minutes_from_prev or 0,
        )
        for rj in route.ordered_jobs
    ]

    # Build new stop list with the job inserted at the right position
    new_stops: list[ScheduledStop] = []
    seq = 1

    for i, stop in enumerate(current_stops):
        if i == insert_at_sequence:
            new_stops.append(ScheduledStop(
                job=job, sequence=seq,
                estimated_arrival=datetime.utcnow(),
                estimated_departure=datetime.utcnow(),
                travel_minutes_from_prev=0,
            ))
            seq += 1
        stop.sequence = seq
        new_stops.append(stop)
        seq += 1

    if insert_at_sequence >= len(current_stops):
        new_stops.append(ScheduledStop(
            job=job, sequence=seq,
            estimated_arrival=datetime.utcnow(),
            estimated_departure=datetime.utcnow(),
            travel_minutes_from_prev=0,
        ))

    start_time = _work_start_datetime(company, job.scheduled_date)
    final_stops = _simulate_route_timing(tech, new_stops, company, start_time)

    _write_stops_to_db(db, route, final_stops)
    job.status = JobStatus.scheduled
    db.commit()
    db.refresh(route)

    return route

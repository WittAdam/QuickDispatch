"""
Core dispatch optimization engine.

Uses a greedy nearest-neighbor algorithm with time window awareness.
Simple enough to be fast and explainable, smart enough to create real value.

The main functions:
  optimize_route()      — build a full day's route for one technician
  score_insertion()     — score inserting one job at one position
  find_best_insertions() — find top N options across all techs for a new job
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional

from app.models.company import Company
from app.models.job import Job, JobPriority
from app.models.technician import Technician
from app.services.travel import get_travel_minutes, travel_delta_minutes


@dataclass
class ScheduledStop:
    """
    A job placed at a specific position in a route with computed timing.
    This lives in memory during optimization — written to DB after.
    """
    job: Job
    sequence: int
    estimated_arrival: datetime
    estimated_departure: datetime
    travel_minutes_from_prev: int
    is_time_window_violated: bool = False
    violation_minutes: int = 0


@dataclass
class InsertionScore:
    """
    Full scored result of inserting a job at one position for one technician.
    Returned to the dispatcher so they can review options and choose.
    """
    technician: Technician
    job: Job
    insert_at_sequence: int
    travel_delta_minutes: int
    downstream_violations: int
    downstream_violation_minutes: int
    estimated_arrival: datetime
    disruption_score: float
    note: str = ""


def _work_start_datetime(company: Company, target_date: date) -> datetime:
    """Returns the datetime when the workday starts for this company on the given date."""
    return datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        company.work_start_hour,
        0, 0,
    )


def _simulate_route_timing(
    tech: Technician,
    stops: list[ScheduledStop],
    company: Company,
    start_time: datetime,
) -> list[ScheduledStop]:
    """
    Walk through a route and calculate exact arrival/departure times for every stop.
    Also flags any time window violations.

    Called after every route change to keep ETAs accurate.
    """
    if not stops:
        return stops

    current_time = start_time
    prev_lat, prev_lon = tech.effective_location()

    for stop in stops:
        job = stop.job

        travel_mins = get_travel_minutes(
            prev_lat, prev_lon,
            job.lat, job.lon,
            company.avg_speed_kmh,
            company.road_factor,
        )

        arrival = current_time + timedelta(minutes=travel_mins)

        # If arriving before window opens, tech waits
        if job.has_time_window() and arrival < job.window_start:
            arrival = job.window_start

        departure = arrival + timedelta(minutes=job.estimated_duration_minutes)

        # Check for late arrival
        violated = False
        violation_mins = 0
        if job.has_time_window() and arrival > job.window_end:
            violated = True
            violation_mins = int((arrival - job.window_end).total_seconds() / 60)

        stop.estimated_arrival = arrival
        stop.estimated_departure = departure
        stop.travel_minutes_from_prev = travel_mins
        stop.is_time_window_violated = violated
        stop.violation_minutes = violation_mins

        current_time = departure + timedelta(minutes=company.buffer_minutes)
        prev_lat, prev_lon = job.lat, job.lon

    return stops


def optimize_route(
    tech: Technician,
    jobs: list[Job],
    company: Company,
    target_date: date,
) -> list[ScheduledStop]:
    """
    Build an optimized route for one technician using greedy nearest-neighbor.

    How it works:
    1. Start at the tech's current location (or home base)
    2. Score every remaining unvisited job
    3. Pick the best scoring job, add it to the route
    4. Repeat from the new position until all jobs are placed
    5. Final pass recalculates all ETAs accurately

    Scoring favors: nearby jobs, urgent jobs, jobs with tight time windows.
    """
    eligible = [j for j in jobs if tech.can_handle_job(j.required_skills)]
    if not eligible:
        return []

    start_time = _work_start_datetime(company, target_date)
    current_time = start_time
    current_lat, current_lon = tech.effective_location()

    remaining = list(eligible)
    route: list[ScheduledStop] = []
    sequence = 1

    work_end_time = datetime(
        target_date.year, target_date.month, target_date.day,
        company.work_end_hour, 0, 0
    )

    while remaining:
        # Stop if tech has hit the max jobs limit for the day
        if len(route) >= company.max_jobs_per_day:
            break

        # Stop if current time is past the end of the workday
        if current_time >= work_end_time:
            break

        best_job: Optional[Job] = None
        best_score = float("inf")

        for job in remaining:
            travel_mins = get_travel_minutes(
                current_lat, current_lon,
                job.lat, job.lon,
                company.avg_speed_kmh,
                company.road_factor,
            )
            projected_arrival = current_time + timedelta(minutes=travel_mins)

            # Skip this job if completing it would push past end of workday
            projected_departure = projected_arrival + timedelta(minutes=job.estimated_duration_minutes)
            if projected_departure > work_end_time + timedelta(hours=1):
                continue

            score = float(travel_mins)

            # Time window pressure — pull jobs with closing windows earlier
            if job.has_time_window():
                minutes_until_close = (
                    job.window_end - projected_arrival
                ).total_seconds() / 60

                if minutes_until_close < 0:
                    # Already late — penalize heavily
                    score += abs(minutes_until_close) * company.violation_penalty_per_minute
                elif minutes_until_close < 60:
                    # Tight window — prioritize
                    score -= 30.0

            # Priority bonus — negative score = system prefers this job
            priority_adjustments = {
                JobPriority.emergency: -50.0,
                JobPriority.high: -15.0,
                JobPriority.normal: 0.0,
                JobPriority.low: 10.0,
            }
            score += priority_adjustments[job.priority]

            if score < best_score:
                best_score = score
                best_job = job

        if best_job is None:
            break

        travel_mins = get_travel_minutes(
            current_lat, current_lon,
            best_job.lat, best_job.lon,
            company.avg_speed_kmh,
            company.road_factor,
        )
        arrival = current_time + timedelta(minutes=travel_mins)

        if best_job.has_time_window() and arrival < best_job.window_start:
            arrival = best_job.window_start

        departure = arrival + timedelta(minutes=best_job.estimated_duration_minutes)

        route.append(ScheduledStop(
            job=best_job,
            sequence=sequence,
            estimated_arrival=arrival,
            estimated_departure=departure,
            travel_minutes_from_prev=travel_mins,
        ))

        current_time = departure + timedelta(minutes=company.buffer_minutes)
        current_lat, current_lon = best_job.lat, best_job.lon
        remaining.remove(best_job)
        sequence += 1

    return _simulate_route_timing(tech, route, company, start_time)


def score_insertion(
    tech: Technician,
    new_job: Job,
    insert_at_sequence: int,
    current_stops: list[ScheduledStop],
    company: Company,
    start_time: datetime,
) -> InsertionScore:
    """
    Score the cost of inserting new_job at a specific position in a tech's route.

    insert_at_sequence=0 → insert before all jobs (becomes first job of day)
    insert_at_sequence=N → insert after the Nth job
    """
    # Determine surrounding locations
    if insert_at_sequence == 0:
        prev_lat, prev_lon = tech.effective_location()
    else:
        prev = current_stops[insert_at_sequence - 1]
        prev_lat, prev_lon = prev.job.lat, prev.job.lon

    if insert_at_sequence < len(current_stops):
        nxt = current_stops[insert_at_sequence]
        next_lat: Optional[float] = nxt.job.lat
        next_lon: Optional[float] = nxt.job.lon
    else:
        next_lat = next_lon = None

    delta = travel_delta_minutes(
        prev_lat, prev_lon,
        new_job.lat, new_job.lon,
        next_lat, next_lon,
        company.avg_speed_kmh,
        company.road_factor,
    )

    # When would the tech arrive at the new job
    if insert_at_sequence == 0:
        base_time = start_time
    else:
        prev_s = current_stops[insert_at_sequence - 1]
        base_time = prev_s.estimated_departure + timedelta(minutes=company.buffer_minutes)

    travel_to_new = get_travel_minutes(
        prev_lat, prev_lon,
        new_job.lat, new_job.lon,
        company.avg_speed_kmh,
        company.road_factor,
    )
    new_arrival = base_time + timedelta(minutes=travel_to_new)

    # Simulate downstream delays
    downstream_violations = 0
    total_violation_minutes = 0
    shifted_time = new_arrival + timedelta(
        minutes=new_job.estimated_duration_minutes + company.buffer_minutes
    )
    shifted_lat, shifted_lon = new_job.lat, new_job.lon

    for i in range(insert_at_sequence, len(current_stops)):
        stop = current_stops[i]
        travel = get_travel_minutes(
            shifted_lat, shifted_lon,
            stop.job.lat, stop.job.lon,
            company.avg_speed_kmh,
            company.road_factor,
        )
        shifted_arrival = shifted_time + timedelta(minutes=travel)

        if stop.job.has_time_window() and shifted_arrival > stop.job.window_end:
            downstream_violations += 1
            total_violation_minutes += int(
                (shifted_arrival - stop.job.window_end).total_seconds() / 60
            )

        shifted_time = shifted_arrival + timedelta(
            minutes=stop.job.estimated_duration_minutes + company.buffer_minutes
        )
        shifted_lat, shifted_lon = stop.job.lat, stop.job.lon

    disruption_score = (
        delta * 1.0
        + total_violation_minutes * company.violation_penalty_per_minute
        - new_job.priority_weight * 10.0
    )

    if downstream_violations == 0:
        note = "No downstream violations"
    elif downstream_violations == 1:
        note = f"1 job may run {total_violation_minutes}min late"
    else:
        note = f"{downstream_violations} jobs affected, {total_violation_minutes}min total delay"

    return InsertionScore(
        technician=tech,
        job=new_job,
        insert_at_sequence=insert_at_sequence,
        travel_delta_minutes=delta,
        downstream_violations=downstream_violations,
        downstream_violation_minutes=total_violation_minutes,
        estimated_arrival=new_arrival,
        disruption_score=disruption_score,
        note=note,
    )


def find_best_insertions(
    eligible_techs: list[Technician],
    tech_routes: dict[uuid.UUID, list[ScheduledStop]],
    new_job: Job,
    company: Company,
    target_date: date,
    top_n: int = 3,
) -> list[InsertionScore]:
    """
    Find the top N insertion options across all eligible technicians.

    Returns ranked options so the dispatcher can choose.
    Best option = lowest disruption score.
    """
    all_options: list[InsertionScore] = []
    start_time = _work_start_datetime(company, target_date)

    for tech in eligible_techs:
        if not tech.can_handle_job(new_job.required_skills):
            continue

        stops = tech_routes.get(tech.id, [])

        for position in range(len(stops) + 1):
            score = score_insertion(
                tech=tech,
                new_job=new_job,
                insert_at_sequence=position,
                current_stops=stops,
                company=company,
                start_time=start_time,
            )
            all_options.append(score)

    all_options.sort(key=lambda s: s.disruption_score)

    # Keep only the best position per technician
    seen: set[uuid.UUID] = set()
    deduplicated: list[InsertionScore] = []
    for opt in all_options:
        if opt.technician.id not in seen:
            deduplicated.append(opt)
            seen.add(opt.technician.id)

    return deduplicated[:top_n]

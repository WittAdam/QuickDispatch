import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Integer, Boolean, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Route(Base):
    """
    One technician's ordered job list for a single day.
    Rebuilt by the optimizer each time routes are recalculated.
    """
    __tablename__ = "routes"
    __table_args__ = (UniqueConstraint("technician_id", "route_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("technicians.id"), nullable=False)
    route_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Computed totals — updated after every optimization run
    total_travel_minutes: Mapped[int] = mapped_column(Integer, default=0)
    total_job_minutes: Mapped[int] = mapped_column(Integer, default=0)

    last_optimized_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Human-readable notes from the last optimization pass
    # e.g. "2 time window violations flagged"
    optimization_notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    technician: Mapped["Technician"] = relationship(back_populates="routes")
    route_jobs: Mapped[list["RouteJob"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteJob.sequence",
    )

    @property
    def ordered_jobs(self) -> list["RouteJob"]:
        return sorted(self.route_jobs, key=lambda rj: rj.sequence)

    @property
    def violation_count(self) -> int:
        return sum(1 for rj in self.route_jobs if rj.is_time_window_violated)


class RouteJob(Base):
    """
    A single job within a route, with its position and calculated arrival time.
    sequence=1 means first job of the day, sequence=2 is second, and so on.
    """
    __tablename__ = "route_jobs"
    __table_args__ = (
        UniqueConstraint("route_id", "sequence"),
        UniqueConstraint("route_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("routes.id"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)

    # Position in the day's route — 1 is first, 2 is second, etc.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    # Calculated by the optimizer — when will the tech arrive and leave
    estimated_arrival: Mapped[Optional[datetime]] = mapped_column(DateTime)
    estimated_departure: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # How many minutes of driving from the previous job (or home base)
    travel_minutes_from_prev: Mapped[Optional[int]] = mapped_column(Integer)

    # Set to True if the tech will arrive after the customer's promised window
    is_time_window_violated: Mapped[bool] = mapped_column(Boolean, default=False)
    violation_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    route: Mapped["Route"] = relationship(back_populates="route_jobs")
    job: Mapped["Job"] = relationship(back_populates="route_job")

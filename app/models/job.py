import uuid
import enum
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, ForeignKey, ARRAY, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class JobPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    emergency = "emergency"


class JobStatus(str, enum.Enum):
    pending = "pending"          # created, not yet on a route
    scheduled = "scheduled"      # assigned to a technician
    en_route = "en_route"        # tech is driving there
    in_progress = "in_progress"  # tech is on site
    completed = "completed"
    cancelled = "cancelled"


# Used in optimization scoring — higher weight = system tries harder to assign early
PRIORITY_WEIGHTS: dict[str, float] = {
    "low": 0.5,
    "normal": 1.0,
    "high": 3.0,
    "emergency": 10.0,
}


class Job(Base):
    """
    A single service job to be dispatched.
    Jobs are the core unit of work in QuickDispatch.
    """
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)

    # Customer information
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50))
    customer_address: Mapped[str] = mapped_column(Text, nullable=False)

    # GPS coordinates — required for route calculation
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    # What day this job is booked for
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Optional time window promised to the customer
    # e.g. "we'll be there between 10am and 12pm"
    window_start: Mapped[Optional[datetime]] = mapped_column(DateTime)
    window_end: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # How long the job is expected to take on site
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)

    # Skills the assigned tech must have — e.g. ["gas_certified"]
    required_skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    priority: Mapped[JobPriority] = mapped_column(
        SAEnum(JobPriority), default=JobPriority.normal, nullable=False
    )

    # Type of service — e.g. "water_heater_install", "drain_cleaning", "ac_tune_up"
    job_type: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Jobber integration — stores the Jobber job ID so we can sync back
    jobber_job_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Status tracking
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), default=JobStatus.pending, nullable=False
    )
    actual_arrival: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_completion: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="jobs")
    route_job: Mapped[Optional["RouteJob"]] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def priority_weight(self) -> float:
        return PRIORITY_WEIGHTS[self.priority]

    def has_time_window(self) -> bool:
        return self.window_start is not None and self.window_end is not None

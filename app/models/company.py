import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Company(Base):
    """
    Represents a business using QuickDispatch.
    Every technician, job, and route belongs to a company.
    This is what makes the system multi-tenant — one database, many businesses.
    """
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Timezone for displaying times to the dispatcher (e.g. "America/Chicago")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")

    # Working hours in local time — techs won't be scheduled outside these
    work_start_hour: Mapped[int] = mapped_column(Integer, default=8)
    work_end_hour: Mapped[int] = mapped_column(Integer, default=18)

    # Travel estimation — tune these per company based on their city/area
    avg_speed_kmh: Mapped[float] = mapped_column(Float, default=40.0)
    road_factor: Mapped[float] = mapped_column(Float, default=1.3)

    # Buffer time added between jobs (parking, setup, wrap-up)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=15)

    # How heavily to penalize time window violations in optimization scoring
    violation_penalty_per_minute: Mapped[float] = mapped_column(Float, default=5.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    technicians: Mapped[list["Technician"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

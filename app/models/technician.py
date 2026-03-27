import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Technician(Base):
    """
    A field technician employed by a company.
    Techs have skill tags that must match job requirements for assignment.
    """
    __tablename__ = "technicians"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))

    # Home base — where the tech starts and ends their day
    home_lat: Mapped[float] = mapped_column(Float, nullable=False)
    home_lon: Mapped[float] = mapped_column(Float, nullable=False)

    # Live GPS location — updated by tech app or manually by dispatcher
    # Falls back to home_lat/home_lon if stale or missing
    current_lat: Mapped[Optional[float]] = mapped_column(Float)
    current_lon: Mapped[Optional[float]] = mapped_column(Float)
    last_location_update: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Skill tags — e.g. ["plumbing", "gas_certified", "commercial"]
    # A job requiring ["gas_certified"] can only go to techs with that tag
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="technicians")
    routes: Mapped[list["Route"]] = relationship(
        back_populates="technician", cascade="all, delete-orphan"
    )

    def effective_location(self) -> tuple[float, float]:
        """
        Best known location for routing.
        Uses live GPS if updated within the last hour, otherwise home base.
        """
        if (
            self.current_lat is not None
            and self.current_lon is not None
            and self.last_location_update is not None
        ):
            age_seconds = (datetime.utcnow() - self.last_location_update).total_seconds()
            if age_seconds < 3600:
                return (self.current_lat, self.current_lon)
        return (self.home_lat, self.home_lon)

    def can_handle_job(self, required_skills: list[str]) -> bool:
        """Returns True if the tech has every skill the job requires."""
        if not required_skills:
            return True
        return all(skill in self.skills for skill in required_skills)

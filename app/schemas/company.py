import uuid
from datetime import datetime
from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    timezone: str = "America/New_York"
    work_start_hour: int = 8
    work_end_hour: int = 18
    avg_speed_kmh: float = 40.0
    road_factor: float = 1.3
    buffer_minutes: int = 15
    violation_penalty_per_minute: float = 5.0


class CompanyResponse(CompanyCreate):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

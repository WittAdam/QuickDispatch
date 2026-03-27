import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TechnicianCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    home_lat: float
    home_lon: float
    skills: list[str] = []


class TechnicianUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[list[str]] = None
    is_active: Optional[bool] = None


class LocationUpdate(BaseModel):
    lat: float
    lon: float


class TechnicianResponse(TechnicianCreate):
    id: uuid.UUID
    company_id: uuid.UUID
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

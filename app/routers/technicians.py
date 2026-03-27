from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.core.database import get_db
from app.models.technician import Technician
from app.schemas.technician import (
    TechnicianCreate, TechnicianUpdate, TechnicianResponse, LocationUpdate
)

router = APIRouter(prefix="/companies/{company_id}/technicians", tags=["technicians"])


@router.post("", response_model=TechnicianResponse)
def create_technician(
    company_id: uuid.UUID,
    payload: TechnicianCreate,
    db: Session = Depends(get_db),
):
    tech = Technician(company_id=company_id, **payload.model_dump())
    db.add(tech)
    db.commit()
    db.refresh(tech)
    return tech


@router.get("", response_model=list[TechnicianResponse])
def list_technicians(
    company_id: uuid.UUID,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(Technician).filter_by(company_id=company_id)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.all()


@router.patch("/{tech_id}", response_model=TechnicianResponse)
def update_technician(
    company_id: uuid.UUID,
    tech_id: uuid.UUID,
    payload: TechnicianUpdate,
    db: Session = Depends(get_db),
):
    tech = db.query(Technician).filter_by(id=tech_id, company_id=company_id).first()
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tech, field, value)
    db.commit()
    db.refresh(tech)
    return tech


@router.put("/{tech_id}/location")
def update_location(
    company_id: uuid.UUID,
    tech_id: uuid.UUID,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
):
    """Update a technician's live GPS location."""
    tech = db.query(Technician).filter_by(id=tech_id, company_id=company_id).first()
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")
    tech.current_lat = payload.lat
    tech.current_lon = payload.lon
    tech.last_location_update = datetime.utcnow()
    db.commit()
    return {"status": "ok"}

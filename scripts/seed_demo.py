"""
QuickDispatch Demo Seed Script

Populates the database with a realistic demo scenario for Dallas, TX:
  - 1 company: "Lone Star HVAC & Plumbing"
  - 4 technicians with different skill sets
  - 12 pre-booked jobs spread across the city
  - 1 emergency job (used to demo real-time insertion)

Run this after starting the API:
  python scripts/seed_demo.py

Then visit http://localhost:8000/docs to explore the API.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.technician import Technician
from app.models.job import Job, JobPriority, JobStatus

# Demo date — today
DEMO_DATE = date.today()

# Work start reference for time windows
def work_dt(hour: int, minute: int = 0) -> datetime:
    return datetime(DEMO_DATE.year, DEMO_DATE.month, DEMO_DATE.day, hour, minute)


def seed():
    db = SessionLocal()
    try:
        # ─────────────────────────────────────────
        # COMPANY
        # ─────────────────────────────────────────
        company = Company(
            name="Lone Star HVAC & Plumbing",
            timezone="America/Chicago",
            work_start_hour=7,
            work_end_hour=18,
            avg_speed_kmh=45.0,   # Dallas suburban — faster than dense cities
            road_factor=1.25,
            buffer_minutes=15,
            violation_penalty_per_minute=5.0,
        )
        db.add(company)
        db.flush()
        print(f"✓ Company created: {company.name} (ID: {company.id})")

        # ─────────────────────────────────────────
        # TECHNICIANS — each has a different skill set
        # ─────────────────────────────────────────
        techs_data = [
            {
                "name": "Marcus Johnson",
                "phone": "214-555-0101",
                "home_lat": 32.7767,   # Dallas downtown area
                "home_lon": -96.7970,
                "skills": ["hvac", "refrigeration", "commercial"],
            },
            {
                "name": "Carlos Rivera",
                "phone": "214-555-0102",
                "home_lat": 32.8998,   # North Dallas / Plano area
                "home_lon": -96.7640,
                "skills": ["plumbing", "drain_cleaning", "gas_certified", "commercial"],
            },
            {
                "name": "Derek Thompson",
                "phone": "214-555-0103",
                "home_lat": 32.7068,   # South Dallas / Duncanville area
                "home_lon": -96.8308,
                "skills": ["hvac", "plumbing", "electrical"],
            },
            {
                "name": "Ashley Wu",
                "phone": "214-555-0104",
                "home_lat": 32.9483,   # Far north — McKinney area
                "home_lon": -96.6989,
                "skills": ["hvac", "commercial", "gas_certified"],
            },
        ]

        techs = []
        for t in techs_data:
            tech = Technician(company_id=company.id, **t)
            db.add(tech)
            techs.append(tech)
        db.flush()
        for t in techs:
            print(f"  ✓ Technician: {t.name} | Skills: {t.skills}")

        # ─────────────────────────────────────────
        # JOBS — realistic Dallas addresses with time windows
        # ─────────────────────────────────────────
        jobs_data = [
            # Morning jobs with tight windows
            {
                "customer_name": "Robert & Linda Hayes",
                "customer_phone": "214-555-1001",
                "customer_address": "4521 Oak Lawn Ave, Dallas, TX 75219",
                "lat": 32.8072, "lon": -96.8197,
                "window_start": work_dt(8, 0), "window_end": work_dt(10, 0),
                "estimated_duration_minutes": 90,
                "required_skills": ["hvac"],
                "priority": JobPriority.normal,
                "job_type": "ac_tune_up",
                "notes": "Annual AC maintenance. System is 7 years old.",
            },
            {
                "customer_name": "Sunset Grille Restaurant",
                "customer_phone": "214-555-1002",
                "customer_address": "2100 N Akard St, Dallas, TX 75201",
                "lat": 32.7893, "lon": -96.8017,
                "window_start": work_dt(8, 0), "window_end": work_dt(9, 30),
                "estimated_duration_minutes": 60,
                "required_skills": ["plumbing", "commercial"],
                "priority": JobPriority.high,
                "job_type": "drain_cleaning",
                "notes": "Commercial kitchen drain backed up. Restaurant opens at 11am.",
            },
            {
                "customer_name": "Patricia Nguyen",
                "customer_phone": "214-555-1003",
                "customer_address": "7834 Greenville Ave, Dallas, TX 75231",
                "lat": 32.8631, "lon": -96.7556,
                "window_start": work_dt(9, 0), "window_end": work_dt(11, 0),
                "estimated_duration_minutes": 120,
                "required_skills": ["hvac"],
                "priority": JobPriority.normal,
                "job_type": "ac_replacement",
                "notes": "Full AC unit replacement. Unit has been quoted and parts are ready.",
            },
            {
                "customer_name": "James & Maria Kowalski",
                "customer_phone": "214-555-1004",
                "customer_address": "3901 Swiss Ave, Dallas, TX 75204",
                "lat": 32.7942, "lon": -96.7742,
                "window_start": work_dt(10, 0), "window_end": work_dt(12, 0),
                "estimated_duration_minutes": 75,
                "required_skills": ["plumbing"],
                "priority": JobPriority.normal,
                "job_type": "water_heater_repair",
                "notes": "Water heater leaking from bottom. Customer thinks it needs replacing.",
            },
            {
                "customer_name": "Northpark Office Complex",
                "customer_phone": "214-555-1005",
                "customer_address": "8750 N Central Expy, Dallas, TX 75231",
                "lat": 32.8710, "lon": -96.7712,
                "window_start": work_dt(10, 0), "window_end": work_dt(14, 0),
                "estimated_duration_minutes": 180,
                "required_skills": ["hvac", "commercial"],
                "priority": JobPriority.normal,
                "job_type": "hvac_commercial_service",
                "notes": "Quarterly maintenance on 3 rooftop units. Access via building manager.",
            },
            # Midday jobs
            {
                "customer_name": "David Chen",
                "customer_phone": "214-555-1006",
                "customer_address": "15203 Addison Rd, Addison, TX 75001",
                "lat": 32.9563, "lon": -96.8289,
                "window_start": work_dt(11, 0), "window_end": work_dt(13, 0),
                "estimated_duration_minutes": 60,
                "required_skills": ["plumbing", "gas_certified"],
                "priority": JobPriority.normal,
                "job_type": "gas_line_inspection",
                "notes": "Smell of gas near stove. Must be gas certified.",
            },
            {
                "customer_name": "Williamsburg HOA Pool",
                "customer_phone": "214-555-1007",
                "customer_address": "4400 Belt Line Rd, Addison, TX 75001",
                "lat": 32.9528, "lon": -96.8205,
                "window_start": work_dt(12, 0), "window_end": work_dt(15, 0),
                "estimated_duration_minutes": 90,
                "required_skills": ["plumbing"],
                "priority": JobPriority.low,
                "job_type": "pump_repair",
                "notes": "Pool pump running but not circulating. Low priority — pool is closed.",
            },
            {
                "customer_name": "Sandra Williams",
                "customer_phone": "214-555-1008",
                "customer_address": "6201 Gaston Ave, Dallas, TX 75214",
                "lat": 32.8017, "lon": -96.7408,
                "window_start": work_dt(13, 0), "window_end": work_dt(15, 0),
                "estimated_duration_minutes": 60,
                "required_skills": ["hvac"],
                "priority": JobPriority.normal,
                "job_type": "thermostat_replacement",
                "notes": "Smart thermostat install. Customer purchased Nest unit themselves.",
            },
            # Afternoon jobs
            {
                "customer_name": "Thomas & Grace Patel",
                "customer_phone": "214-555-1009",
                "customer_address": "1923 Abrams Rd, Dallas, TX 75214",
                "lat": 32.8310, "lon": -96.7502,
                "window_start": work_dt(14, 0), "window_end": work_dt(17, 0),
                "estimated_duration_minutes": 90,
                "required_skills": ["plumbing"],
                "priority": JobPriority.normal,
                "job_type": "bathroom_remodel_rough_in",
                "notes": "Rough-in plumbing for bathroom addition. Plans provided.",
            },
            {
                "customer_name": "Lakewood Church Annex",
                "customer_phone": "214-555-1010",
                "customer_address": "3005 E Grand Ave, Dallas, TX 75223",
                "lat": 32.7940, "lon": -96.7390,
                "window_start": work_dt(14, 0), "window_end": work_dt(17, 0),
                "estimated_duration_minutes": 120,
                "required_skills": ["hvac", "commercial"],
                "priority": JobPriority.normal,
                "job_type": "hvac_commercial_service",
                "notes": "HVAC not cooling in fellowship hall. Sunday service is critical.",
            },
            {
                "customer_name": "Michael Torres",
                "customer_phone": "214-555-1011",
                "customer_address": "9876 Forest Ln, Dallas, TX 75243",
                "lat": 32.9014, "lon": -96.7350,
                "estimated_duration_minutes": 45,
                "required_skills": [],  # Any tech can handle this
                "priority": JobPriority.low,
                "job_type": "faucet_replacement",
                "notes": "Kitchen faucet dripping. Customer has already purchased replacement.",
            },
            {
                "customer_name": "Briarwood Apartments",
                "customer_phone": "214-555-1012",
                "customer_address": "11411 E Northwest Hwy, Dallas, TX 75218",
                "lat": 32.8485, "lon": -96.6973,
                "window_start": work_dt(15, 0), "window_end": work_dt(17, 30),
                "estimated_duration_minutes": 60,
                "required_skills": ["plumbing"],
                "priority": JobPriority.normal,
                "job_type": "leak_repair",
                "notes": "Unit 4B has leak coming through ceiling from unit 5B above.",
            },
        ]

        for j in jobs_data:
            job = Job(
                company_id=company.id,
                scheduled_date=DEMO_DATE,
                status=JobStatus.pending,
                **j,
            )
            db.add(job)

        db.flush()
        print(f"\n  ✓ {len(jobs_data)} jobs created for {DEMO_DATE}")

        # ─────────────────────────────────────────
        # EMERGENCY JOB — used to demo real-time insertion
        # ─────────────────────────────────────────
        emergency = Job(
            company_id=company.id,
            customer_name="Frank Deluca",
            customer_phone="214-555-9911",
            customer_address="5500 Lemmon Ave, Dallas, TX 75209",
            lat=32.8248,
            lon=-96.8259,
            scheduled_date=DEMO_DATE,
            estimated_duration_minutes=60,
            required_skills=["plumbing"],
            priority=JobPriority.emergency,
            job_type="burst_pipe",
            notes="EMERGENCY: Pipe burst in kitchen. Water actively flooding. Must respond immediately.",
            status=JobStatus.pending,
        )
        db.add(emergency)
        db.flush()
        print(f"  ✓ Emergency job created: {emergency.customer_name} — {emergency.job_type}")
        print(f"    Emergency job ID: {emergency.id}")

        db.commit()

        print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QuickDispatch Demo Data Loaded Successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Company ID : {company.id}
  Date       : {DEMO_DATE}
  Techs      : {len(techs)}
  Jobs       : {len(jobs_data)} regular + 1 emergency

  Next steps:
  1. Build routes:
     POST /dispatch/build-daily-routes
     Body: {{"company_id": "{company.id}", "date": "{DEMO_DATE}"}}

  2. View the schedule:
     GET /dispatch/daily-routes?company_id={company.id}&target_date={DEMO_DATE}

  3. Demo emergency insertion:
     POST /dispatch/insert-urgent?company_id={company.id}&job_id={emergency.id}

  API docs: http://localhost:8000/docs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """)

    except Exception as e:
        db.rollback()
        print(f"✗ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

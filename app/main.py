from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.database import Base, engine
from app.routers import companies, technicians, jobs, dispatch
import os

# Create all database tables on startup
# In production, replace this with: alembic upgrade head
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="QuickDispatch",
    description="AI-powered dispatch optimization for field service businesses",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router)
app.include_router(technicians.router)
app.include_router(jobs.router)
app.include_router(dispatch.router)


@app.get("/health", tags=["system"])
def health_check():
    """Quick check that the API is running."""
    return {"status": "ok", "version": "0.1.0", "app": settings.app_name}


@app.get("/dashboard", tags=["system"])
def serve_dashboard():
    """Serve the dispatcher dashboard."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard.html")
    return FileResponse(path)

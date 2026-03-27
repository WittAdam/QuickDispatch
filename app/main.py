from fastapi import FastAPI
from app.core.config import settings
from app.core.database import Base, engine
from app.routers import companies, technicians, jobs, dispatch

# Create all database tables on startup
# In production, replace this with: alembic upgrade head
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="QuickDispatch",
    description="AI-powered dispatch optimization for field service businesses",
    version="0.1.0",
)

app.include_router(companies.router)
app.include_router(technicians.router)
app.include_router(jobs.router)
app.include_router(dispatch.router)


@app.get("/health", tags=["system"])
def health_check():
    """Quick check that the API is running."""
    return {"status": "ok", "version": "0.1.0", "app": settings.app_name}

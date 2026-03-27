from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    All configuration loaded from environment variables.
    Copy .env.example to .env and fill in values before running.
    """
    database_url: str = "postgresql://dispatch:dispatch@localhost:5432/dispatch"
    app_name: str = "QuickDispatch"
    debug: bool = False

    # Travel time provider — "mock" uses Haversine formula, "google_maps" uses real API
    travel_provider: str = "mock"
    google_maps_api_key: str = ""

    # Jobber OAuth — required for Jobber CRM integration
    jobber_client_id: str = ""
    jobber_client_secret: str = ""
    jobber_redirect_uri: str = "http://localhost:8000/integrations/jobber/callback"

    class Config:
        env_file = ".env"


settings = Settings()

"""
Jobber CRM Adapter

Handles all communication between QuickDispatch and Jobber.
Jobber uses a GraphQL API — this adapter translates their data format
into our internal models and pushes optimized routes back to Jobber.

Setup steps (when ready to connect for real):
  1. Create a Jobber developer account at developer.getjobber.com
  2. Create an app, get client_id and client_secret
  3. Add them to your .env file
  4. Direct your client to GET /integrations/jobber/connect
  5. They authorize, get redirected back, token is stored
"""
import httpx
from datetime import date, datetime
from typing import Optional

from app.core.config import settings


JOBBER_API_URL = "https://api.getjobber.com/api/graphql"
JOBBER_AUTH_URL = "https://api.getjobber.com/api/oauth/authorize"
JOBBER_TOKEN_URL = "https://api.getjobber.com/api/oauth/token"


class JobberAdapter:
    """
    All Jobber API calls go through this class.
    One instance per connected company (each has their own access token).
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-JOBBER-GRAPHQL-VERSION": "2024-01-15",
        }

    def _run_query(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query against the Jobber API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = httpx.post(
            JOBBER_API_URL,
            json=payload,
            headers=self.headers,
            timeout=15.0,
        )
        response.raise_for_status()
        return response.json()

    # ─────────────────────────────────────────
    # Fetch technicians from Jobber
    # ─────────────────────────────────────────

    def fetch_technicians(self) -> list[dict]:
        """
        Pull all team members from Jobber and return them in our internal format.
        Jobber calls them "users" — we map them to our Technician model.
        """
        query = """
        query GetTeamMembers {
          users(filter: { status: ACTIVE }) {
            nodes {
              id
              name {
                full
              }
              email {
                raw
              }
              phone {
                friendly
              }
            }
          }
        }
        """
        data = self._run_query(query)
        users = data.get("data", {}).get("users", {}).get("nodes", [])

        technicians = []
        for user in users:
            technicians.append({
                "jobber_user_id": user["id"],
                "name": user["name"]["full"],
                "email": user.get("email", {}).get("raw"),
                "phone": user.get("phone", {}).get("friendly"),
                # Note: Jobber doesn't store home base coordinates
                # You'll need to enter these manually or geocode from address
                "home_lat": None,
                "home_lon": None,
                "skills": [],
            })

        return technicians

    # ─────────────────────────────────────────
    # Fetch jobs from Jobber
    # ─────────────────────────────────────────

    def fetch_jobs_for_date(self, target_date: date) -> list[dict]:
        """
        Pull all jobs scheduled for a specific date from Jobber.
        Maps Jobber's "job" structure to our internal Job format.
        """
        date_str = target_date.isoformat()

        query = """
        query GetJobs($startDate: ISO8601DateTime!, $endDate: ISO8601DateTime!) {
          jobs(filter: {
            startAt: { gte: $startDate, lte: $endDate }
          }) {
            nodes {
              id
              title
              jobNumber
              jobStatus
              startAt
              endAt
              duration
              instructions
              client {
                id
                name
                phones {
                  number
                }
              }
              property {
                address {
                  street
                  city
                  province
                  postalCode
                  country
                  coordinates {
                    latitude
                    longitude
                  }
                }
              }
              assignedTo {
                nodes {
                  id
                  name { full }
                }
              }
            }
          }
        }
        """

        variables = {
            "startDate": f"{date_str}T00:00:00Z",
            "endDate": f"{date_str}T23:59:59Z",
        }

        data = self._run_query(query, variables)
        jobber_jobs = data.get("data", {}).get("jobs", {}).get("nodes", [])

        jobs = []
        for jj in jobber_jobs:
            coords = (
                jj.get("property", {})
                .get("address", {})
                .get("coordinates", {})
            )
            address = jj.get("property", {}).get("address", {})
            address_str = ", ".join(filter(None, [
                address.get("street"),
                address.get("city"),
                address.get("province"),
                address.get("postalCode"),
            ]))

            lat = coords.get("latitude")
            lon = coords.get("longitude")

            # Skip jobs without coordinates — can't route them
            if not lat or not lon:
                continue

            client = jj.get("client", {})
            phones = client.get("phones", [])
            phone = phones[0]["number"] if phones else None

            duration_minutes = int(jj.get("duration", 3600) / 60)

            jobs.append({
                "jobber_job_id": jj["id"],
                "customer_name": client.get("name", "Unknown"),
                "customer_phone": phone,
                "customer_address": address_str,
                "lat": lat,
                "lon": lon,
                "scheduled_date": target_date,
                "estimated_duration_minutes": duration_minutes,
                "notes": jj.get("instructions"),
                "priority": "normal",  # Jobber doesn't have priority — default to normal
                "required_skills": [],
            })

        return jobs

    # ─────────────────────────────────────────
    # Push optimized schedule back to Jobber
    # ─────────────────────────────────────────

    def update_job_assignment(self, jobber_job_id: str, jobber_user_id: str) -> bool:
        """
        Assign a Jobber job to a specific team member.
        Called after optimization to push the new schedule back to Jobber.
        """
        mutation = """
        mutation AssignJob($jobId: EncodedId!, $userId: EncodedId!) {
          jobEdit(id: $jobId, attributes: {
            assignedTo: [$userId]
          }) {
            job {
              id
              assignedTo { nodes { id } }
            }
            userErrors {
              message
              path
            }
          }
        }
        """
        variables = {"jobId": jobber_job_id, "userId": jobber_user_id}
        data = self._run_query(mutation, variables)
        errors = data.get("data", {}).get("jobEdit", {}).get("userErrors", [])
        return len(errors) == 0


# ─────────────────────────────────────────
# OAuth flow helpers
# ─────────────────────────────────────────

def get_authorization_url(state: str) -> str:
    """
    Build the URL to redirect the user to for Jobber OAuth authorization.
    The user clicks this, logs into Jobber, and approves the connection.
    """
    params = (
        f"?client_id={settings.jobber_client_id}"
        f"&redirect_uri={settings.jobber_redirect_uri}"
        f"&response_type=code"
        f"&state={state}"
    )
    return JOBBER_AUTH_URL + params


def exchange_code_for_token(code: str) -> dict:
    """
    After the user approves, Jobber sends a code to our callback URL.
    This function exchanges that code for a real access token.
    Returns: { access_token, refresh_token, expires_in }
    """
    response = httpx.post(
        JOBBER_TOKEN_URL,
        data={
            "client_id": settings.jobber_client_id,
            "client_secret": settings.jobber_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.jobber_redirect_uri,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """
    Access tokens expire. Use the refresh token to get a new one
    without requiring the user to log in again.
    """
    response = httpx.post(
        JOBBER_TOKEN_URL,
        data={
            "client_id": settings.jobber_client_id,
            "client_secret": settings.jobber_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()

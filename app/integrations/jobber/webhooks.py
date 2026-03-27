"""
Jobber Webhook Handler

Jobber sends POST requests to our /integrations/jobber/webhook endpoint
whenever something changes in the connected account — new job, job updated,
job completed, etc.

This file processes those events and triggers the appropriate QuickDispatch action.
Most importantly: when a new urgent job is created, we automatically score
insertion options and optionally auto-assign it.
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(prefix="/integrations/jobber", tags=["jobber"])


# Jobber webhook event types we care about
WEBHOOK_EVENTS = {
    "JOB_CREATE": "new job booked — trigger insertion scoring",
    "JOB_UPDATE": "job changed — may need rescheduling",
    "JOB_COMPLETE": "job done — update status in QuickDispatch",
    "JOB_DELETE": "job cancelled — remove from route",
}


@router.post("/webhook")
async def jobber_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives real-time events from Jobber.

    When Jobber sends us a JOB_CREATE event, we:
    1. Pull the full job details from Jobber
    2. Create it in our database
    3. Score insertion options across all techs
    4. Auto-assign if it's marked urgent, otherwise flag for dispatcher

    Note: In production, verify the webhook signature from Jobber headers
    to ensure the request is genuinely from Jobber.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("webHookEvent", {}).get("event")
    topic = payload.get("webHookEvent", {}).get("topic")

    if not event_type:
        return {"status": "ignored", "reason": "no event type"}

    # TODO: Look up the company by Jobber account ID
    # jobber_account_id = payload.get("accountId")
    # company = db.query(Company).filter_by(jobber_account_id=jobber_account_id).first()

    if topic == "JOB" and event_type == "CREATED":
        # New job created in Jobber — pull details and add to QuickDispatch
        # job_id = payload.get("webHookEvent", {}).get("itemId")
        # TODO: fetch job from Jobber, create in DB, score insertion
        return {"status": "received", "action": "job_create_queued"}

    if topic == "JOB" and event_type == "UPDATED":
        return {"status": "received", "action": "job_update_queued"}

    if topic == "JOB" and event_type == "COMPLETED":
        return {"status": "received", "action": "job_complete_queued"}

    return {"status": "received", "action": "no_handler"}


@router.get("/connect")
def connect_jobber(company_id: str):
    """
    Step 1 of Jobber OAuth: redirect user to Jobber to authorize QuickDispatch.
    In production, store company_id in the state parameter so we know
    which company to link the token to when they come back.
    """
    from app.integrations.jobber.adapter import get_authorization_url
    url = get_authorization_url(state=company_id)
    return {"authorization_url": url, "instructions": "Direct the user to this URL"}


@router.get("/callback")
def jobber_oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Step 2 of Jobber OAuth: Jobber redirects here after user approves.
    Exchange the code for an access token and store it.
    """
    from app.integrations.jobber.adapter import exchange_code_for_token
    try:
        token_data = exchange_code_for_token(code)
        # TODO: Store token_data["access_token"] and token_data["refresh_token"]
        # linked to the company identified by state (=company_id)
        return {
            "status": "connected",
            "company_id": state,
            "message": "Jobber account connected. Store the access token securely.",
            "expires_in": token_data.get("expires_in"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

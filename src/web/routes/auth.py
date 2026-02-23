"""Authentication API routes: signup, login, current user."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.web.auth import create_access_token, get_current_user, verify_google_token

router = APIRouter(tags=["auth"])


def _get_db():
    from src.config import load_api_config
    from src.database import Database
    api_config = load_api_config()
    return Database(api_config.db_path)


class SignupRequest(BaseModel):
    google_token: str
    team_name: str


class LoginRequest(BaseModel):
    google_token: str


@router.post("/signup")
async def signup(req: SignupRequest):
    """Create a new team and admin user via Google OAuth."""
    google_info = await verify_google_token(req.google_token)
    email = google_info["email"]
    name = google_info["name"]
    picture = google_info.get("picture")

    # Extract domain from email
    domain = email.split("@")[1]

    db = _get_db()
    try:
        # Check if team already exists for this domain
        existing_team = db.get_team_by_domain(domain)
        if existing_team:
            raise HTTPException(
                status_code=409,
                detail=f"A team already exists for the domain {domain}",
            )

        # Check if user already exists
        existing_user = db.get_user_by_email(email)
        if existing_user:
            raise HTTPException(status_code=409, detail="User already exists")

        # Create team
        team_name = req.team_name.strip()
        if not team_name:
            raise HTTPException(status_code=400, detail="Team name is required")
        team_id = str(uuid.uuid4())
        team = db.create_team(team_id, team_name, domain)

        # Create admin user
        user_id = str(uuid.uuid4())
        user = db.create_user(
            user_id=user_id,
            team_id=team_id,
            email=email,
            name=name,
            avatar_url=picture,
            role="admin",
        )

        token = create_access_token(user_id, email, team_id, "admin")
        return {"token": token, "user": user, "team": team}
    finally:
        db.close()


@router.post("/login")
async def login(req: LoginRequest):
    """Log in with Google OAuth. Accepts existing users or invited users."""
    google_info = await verify_google_token(req.google_token)
    email = google_info["email"]
    name = google_info["name"]
    picture = google_info.get("picture")

    db = _get_db()
    try:
        # Check if user already exists
        user = db.get_user_by_email(email)

        if user:
            if user["status"] != "active":
                raise HTTPException(status_code=403, detail="Your account has been disabled")

            team = db.get_team(user["team_id"])
            token = create_access_token(user["id"], email, user["team_id"], user["role"])
            return {"token": token, "user": user, "team": team}

        # User doesn't exist — check for pending invitation
        invitation = db.get_pending_invitation_by_email(email)
        if not invitation:
            raise HTTPException(
                status_code=403,
                detail="No account found. Ask your team admin for an invitation.",
            )

        # Check invitation expiry
        expires_at = datetime.fromisoformat(invitation["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            db.update_invitation_status(invitation["id"], "expired")
            raise HTTPException(
                status_code=403,
                detail="Your invitation has expired. Ask your admin for a new one.",
            )

        # Verify email domain matches team
        team = db.get_team(invitation["team_id"])
        if not team:
            raise HTTPException(status_code=403, detail="Team not found")

        email_domain = email.split("@")[1]
        if email_domain != team["allowed_domain"]:
            raise HTTPException(
                status_code=403,
                detail=f"Your email domain doesn't match this team ({team['allowed_domain']})",
            )

        # Create new member user
        user_id = str(uuid.uuid4())
        user = db.create_user(
            user_id=user_id,
            team_id=team["id"],
            email=email,
            name=name,
            avatar_url=picture,
            role="member",
        )

        # Mark invitation as accepted
        db.update_invitation_status(invitation["id"], "accepted")

        token = create_access_token(user_id, email, team["id"], "member")
        return {"token": token, "user": user, "team": team}
    finally:
        db.close()


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get the current authenticated user and their team."""
    db = _get_db()
    try:
        team = db.get_team(current_user["team_id"])
        return {"user": current_user, "team": team}
    finally:
        db.close()

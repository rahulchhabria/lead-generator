"""Team management API routes: members, invitations."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.web.auth import get_current_user, require_admin

router = APIRouter(tags=["team"])


def _get_db():
    from src.config import load_api_config
    from src.database import Database
    api_config = load_api_config()
    return Database(api_config.db_path)


@router.get("/")
def get_team(current_user: dict = Depends(get_current_user)):
    """Get current user's team info."""
    db = _get_db()
    try:
        team = db.get_team(current_user["team_id"])
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        return team
    finally:
        db.close()


@router.get("/members")
def list_members(current_user: dict = Depends(get_current_user)):
    """List all team members."""
    db = _get_db()
    try:
        return db.list_team_members(current_user["team_id"])
    finally:
        db.close()


class InviteRequest(BaseModel):
    email: str


@router.post("/invitations")
def create_invitation(req: InviteRequest, current_user: dict = Depends(require_admin)):
    """Invite a new member by email (admin only)."""
    email = req.email.strip().lower()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    db = _get_db()
    try:
        team = db.get_team(current_user["team_id"])
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Validate email domain matches team
        email_domain = email.split("@")[1]
        if email_domain != team["allowed_domain"]:
            raise HTTPException(
                status_code=400,
                detail=f"Email domain must be @{team['allowed_domain']}",
            )

        # Check if user already exists
        existing_user = db.get_user_by_email(email)
        if existing_user:
            raise HTTPException(status_code=409, detail="User already exists on this team")

        # Check for existing pending invitation
        existing_invite = db.get_pending_invitation_by_email(email)
        if existing_invite and existing_invite["team_id"] == team["id"]:
            raise HTTPException(status_code=409, detail="Invitation already pending for this email")

        # Create invitation (expires in 7 days)
        invitation_id = str(uuid.uuid4())
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        invitation = db.create_invitation(
            invitation_id=invitation_id,
            team_id=team["id"],
            email=email,
            invited_by=current_user["id"],
            expires_at=expires_at,
        )
        return invitation
    finally:
        db.close()


@router.get("/invitations")
def list_invitations(current_user: dict = Depends(require_admin)):
    """List all team invitations (admin only)."""
    db = _get_db()
    try:
        return db.list_team_invitations(current_user["team_id"])
    finally:
        db.close()


@router.delete("/invitations/{invitation_id}")
def cancel_invitation(invitation_id: str, current_user: dict = Depends(require_admin)):
    """Cancel a pending invitation (admin only)."""
    db = _get_db()
    try:
        invitation = db.get_invitation(invitation_id)
        if not invitation or invitation["team_id"] != current_user["team_id"]:
            raise HTTPException(status_code=404, detail="Invitation not found")
        db.delete_invitation(invitation_id)
        return {"status": "cancelled"}
    finally:
        db.close()


@router.delete("/members/{user_id}")
def remove_member(user_id: str, current_user: dict = Depends(require_admin)):
    """Remove a team member (admin only, cannot remove self)."""
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    db = _get_db()
    try:
        user = db.get_user(user_id)
        if not user or user["team_id"] != current_user["team_id"]:
            raise HTTPException(status_code=404, detail="User not found")
        db.update_user_status(user_id, "disabled")
        return {"status": "removed"}
    finally:
        db.close()

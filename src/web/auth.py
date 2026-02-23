"""Authentication utilities: JWT tokens, Google OAuth verification, FastAPI dependencies."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def _get_secret_key() -> str:
    key = os.environ.get("SECRET_KEY", "")
    if not key:
        raise RuntimeError("SECRET_KEY environment variable is required for authentication")
    return key


def create_access_token(user_id: str, email: str, team_id: str, role: str) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "email": email,
        "team_id": team_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])


async def verify_google_token(id_token: str) -> dict:
    """Verify a Google ID token and return user info.

    Returns dict with keys: email, name, picture.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    data = resp.json()

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not google_client_id:
        raise HTTPException(status_code=500, detail="Server misconfigured: GOOGLE_CLIENT_ID not set")
    if data.get("aud") != google_client_id:
        raise HTTPException(status_code=401, detail="Token audience mismatch")

    if data.get("email_verified") != "true" and data.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Email not verified")

    return {
        "email": data["email"].lower(),
        "name": data.get("name", data.get("email", "").split("@")[0]),
        "picture": data.get("picture"),
    }


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    from src.config import load_api_config
    from src.database import Database

    api_config = load_api_config()
    db = Database(api_config.db_path)
    try:
        user = db.get_user(payload["sub"])
    finally:
        db.close()

    if not user or user["status"] != "active":
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: require the current user to be an admin."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

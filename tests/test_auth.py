"""Tests for src/web/auth.py -- JWT tokens, Google OAuth, FastAPI dependencies."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from jose import jwt, JWTError

from src.web.auth import (
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_HOURS,
    create_access_token,
    decode_token,
    get_current_user,
    require_admin,
    verify_google_token,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SECRET = "test-secret-key-for-jwt-signing-1234567890abcdef"
GOOGLE_CLIENT_ID = "test-google-client-id.apps.googleusercontent.com"


def _make_request(*, auth_header: str | None = None) -> MagicMock:
    """Build a mock FastAPI Request with optional Authorization header."""
    request = MagicMock()
    if auth_header is None:
        request.headers.get.return_value = ""
    else:
        request.headers.get.return_value = auth_header
    return request


# ---------------------------------------------------------------------------
# TestCreateAccessToken
# ---------------------------------------------------------------------------
class TestCreateAccessToken:
    def test_creates_valid_jwt(self):
        token = create_access_token("u1", "a@b.com", "t1", "admin")
        assert isinstance(token, str)
        parts = token.split(".")
        assert len(parts) == 3  # header.payload.signature

    def test_token_contains_required_claims(self):
        token = create_access_token("user-42", "alice@acme.com", "team-7", "member")
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        assert payload["sub"] == "user-42"
        assert payload["email"] == "alice@acme.com"
        assert payload["team_id"] == "team-7"
        assert payload["role"] == "member"
        assert "exp" in payload

    def test_token_expiry_is_24_hours(self):
        before = datetime.now(timezone.utc)
        token = create_access_token("u1", "a@b.com", "t1", "admin")
        after = datetime.now(timezone.utc)

        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # JWT exp is an integer timestamp so sub-second precision is lost.
        # Allow a 2-second tolerance to account for truncation and execution time.
        expected_low = before + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS) - timedelta(seconds=2)
        expected_high = after + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS) + timedelta(seconds=2)
        assert expected_low <= exp <= expected_high


# ---------------------------------------------------------------------------
# TestDecodeToken
# ---------------------------------------------------------------------------
class TestDecodeToken:
    def test_decode_valid_token(self):
        token = create_access_token("u1", "a@b.com", "t1", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "u1"
        assert payload["email"] == "a@b.com"
        assert payload["team_id"] == "t1"
        assert payload["role"] == "admin"

    def test_decode_expired_token_raises(self):
        expired_payload = {
            "sub": "u1",
            "email": "a@b.com",
            "team_id": "t1",
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)
        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_tampered_token_raises(self):
        token = create_access_token("u1", "a@b.com", "t1", "admin")
        # Flip a character in the signature portion
        tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        with pytest.raises(JWTError):
            decode_token(tampered)

    def test_decode_wrong_secret_raises(self):
        payload = {
            "sub": "u1",
            "email": "a@b.com",
            "team_id": "t1",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, "wrong-secret-key-totally-different", algorithm=ALGORITHM)
        with pytest.raises(JWTError):
            decode_token(token)


# ---------------------------------------------------------------------------
# TestGetCurrentUser
# ---------------------------------------------------------------------------
class TestGetCurrentUser:
    def test_valid_token_returns_user(self, db, team_alpha, admin_alpha, token_for, monkeypatch):
        db_path = db.db_path
        monkeypatch.setattr("src.config.load_api_config", lambda: MagicMock(db_path=db_path))
        monkeypatch.setattr("src.database.Database", lambda path: db)

        token = token_for(admin_alpha)
        request = _make_request(auth_header=f"Bearer {token}")
        user = get_current_user(request)

        assert user["id"] == admin_alpha["id"]
        assert user["email"] == admin_alpha["email"]
        assert user["role"] == "admin"

    def test_missing_auth_header_returns_401(self):
        request = _make_request(auth_header="")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401

    def test_expired_token_returns_401(self, monkeypatch):
        expired_payload = {
            "sub": "u1",
            "email": "a@b.com",
            "team_id": "t1",
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)
        request = _make_request(auth_header=f"Bearer {token}")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401

    def test_disabled_user_returns_401(self, db, team_alpha, admin_alpha, token_for, monkeypatch):
        db_path = db.db_path
        monkeypatch.setattr("src.config.load_api_config", lambda: MagicMock(db_path=db_path))
        monkeypatch.setattr("src.database.Database", lambda path: db)

        db.update_user_status(admin_alpha["id"], "disabled")

        token = token_for(admin_alpha)
        request = _make_request(auth_header=f"Bearer {token}")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# TestRequireAdmin
# ---------------------------------------------------------------------------
class TestRequireAdmin:
    def test_admin_passes(self):
        admin_user = {
            "id": "u1", "email": "a@b.com", "team_id": "t1",
            "role": "admin", "status": "active", "name": "Admin",
        }
        result = require_admin(current_user=admin_user)
        assert result["id"] == "u1"
        assert result["role"] == "admin"

    def test_member_returns_403(self):
        member_user = {
            "id": "u2", "email": "m@b.com", "team_id": "t1",
            "role": "member", "status": "active", "name": "Member",
        }
        with pytest.raises(HTTPException) as exc_info:
            require_admin(current_user=member_user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# TestVerifyGoogleToken
# ---------------------------------------------------------------------------
class TestVerifyGoogleToken:
    @pytest.mark.asyncio
    async def test_valid_token_returns_user_info(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "aud": GOOGLE_CLIENT_ID,
            "email": "alice@example.com",
            "email_verified": "true",
            "name": "Alice Smith",
            "picture": "https://photo.example.com/alice.jpg",
        }

        async def mock_get(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await verify_google_token("good-id-token")
        assert result["email"] == "alice@example.com"
        assert result["name"] == "Alice Smith"
        assert result["picture"] == "https://photo.example.com/alice.jpg"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_token"}

        async def mock_get(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        with pytest.raises(HTTPException) as exc_info:
            await verify_google_token("bad-token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_audience_mismatch_returns_401(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "aud": "wrong-client-id.apps.googleusercontent.com",
            "email": "alice@example.com",
            "email_verified": "true",
            "name": "Alice",
        }

        async def mock_get(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        with pytest.raises(HTTPException) as exc_info:
            await verify_google_token("token-with-wrong-aud")
        assert exc_info.value.status_code == 401
        assert "audience" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_missing_client_id_returns_500(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "aud": GOOGLE_CLIENT_ID,
            "email": "alice@example.com",
            "email_verified": "true",
            "name": "Alice",
        }

        async def mock_get(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "")

        with pytest.raises(HTTPException) as exc_info:
            await verify_google_token("some-token")
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_email_normalized_to_lowercase(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "aud": GOOGLE_CLIENT_ID,
            "email": "Alice.Smith@EXAMPLE.COM",
            "email_verified": "true",
            "name": "Alice Smith",
        }

        async def mock_get(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

        result = await verify_google_token("token-mixed-case")
        assert result["email"] == "alice.smith@example.com"

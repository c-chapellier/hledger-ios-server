"""JWT and OAuth state management for authentication."""

import jwt
import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException
from ..config import config

# Simple state cache for CSRF protection
_state_cache: dict = {}


def generate_state() -> str:
    """Generate random CSRF state token."""
    state = secrets.token_urlsafe(32)
    _state_cache[state] = datetime.utcnow()
    return state


def verify_state(state: str) -> bool:
    """Verify state is valid and not expired (10 min)."""
    if state not in _state_cache:
        return False
    created = _state_cache[state]
    if datetime.utcnow() - created > timedelta(minutes=10):
        del _state_cache[state]
        return False
    del _state_cache[state]  # One-time use
    return True


def create_jwt(user_id: str, github_username: str, access_token: str) -> str:
    """Create signed JWT token (valid for 365 days)."""
    payload = {
        "user_id": user_id,
        "github_username": github_username,
        "access_token": access_token,
        "exp": datetime.utcnow() + timedelta(days=config.JWT_EXPIRATION_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def verify_jwt(token: str) -> dict:
    """Verify and decode JWT."""
    print("Verifying JWT token:", token)
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

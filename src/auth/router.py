"""GitHub OAuth authentication endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import uuid
import logging
from .security import generate_state, verify_state, create_jwt, verify_jwt
from ..config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()

@router.get("/github/initiate")
async def initiate_github_auth():
    """Initiate GitHub OAuth flow"""
    state = generate_state()
    auth_url = f"https://github.com/login/oauth/authorize?client_id={config.GITHUB_CLIENT_ID}&redirect_uri={config.GITHUB_REDIRECT_URI}&scope=repo&state={state}"
    return {"auth_url": auth_url}


@router.get("/github/callback")
async def github_callback(code: str, state: str):
    """Handle GitHub OAuth callback and return JWT token"""
    if not verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": config.GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"}
        )

    token_data = response.json()
    if "error" in token_data:
        raise HTTPException(status_code=400, detail=token_data.get("error_description"))

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received")

    # Get GitHub user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )

    if user_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get user info: " + user_response.text)

    user_data = user_response.json()
    github_username = user_data["login"]

    # Generate stable user_id based on GitHub username
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, github_username))

    jwt_token = create_jwt(user_id, github_username, access_token)

    logger.info(f"Successfully authenticated user: {github_username}")

    return {
        "token": jwt_token,
        "user_id": user_id,
        "username": github_username,
        "expires_in": 365 * 24 * 3600,  # 1 year in seconds
    }


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Extract and validate user from JWT token"""
    return verify_jwt(credentials.credentials)

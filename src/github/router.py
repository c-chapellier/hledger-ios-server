from fastapi import APIRouter, HTTPException
from github import Github
import git
import os
from pathlib import Path
from typing import Dict, Any
import httpx

from ..gzip_handler import GzipRoute

from dotenv import load_dotenv
load_dotenv()

router = APIRouter(prefix="/github", tags=["github"], route_class=GzipRoute)

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/github/callback")

# In-memory token storage (in production, use a database)
tokens: Dict[str, Dict[str, Any]] = {}

class GitHubOAuth:
    def __init__(self):
        self.client_id = GITHUB_CLIENT_ID
        self.client_secret = GITHUB_CLIENT_SECRET
        self.redirect_uri = GITHUB_REDIRECT_URI

    def get_authorization_url(self, state: str) -> str:
        return f"https://github.com/login/oauth/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&scope=repo&state={state}"

oauth = GitHubOAuth()

@router.get("/auth")
async def github_auth():
    """Initiate GitHub OAuth flow"""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    state = "github_oauth_state"  # In production, generate a secure random state
    auth_url = oauth.get_authorization_url(state)
    return {"auth_url": auth_url}

@router.get("/callback")
async def github_callback(code: str, state: str):
    """Handle GitHub OAuth callback"""
    if state != "github_oauth_state":
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"}
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    token_data = response.json()
    if "error" in token_data:
        raise HTTPException(status_code=400, detail=token_data["error"])

    # Store token (in production, associate with user session)
    tokens["user_token"] = token_data
    print(f"GitHub token stored: {token_data}")

    return {"message": "Authentication successful", "token_stored": True}

@router.get("/repos")
async def list_repositories():
    """List user's GitHub repositories"""
    if "user_token" not in tokens:
        raise HTTPException(status_code=401, detail="Not authenticated with GitHub")

    token = tokens["user_token"]
    g = Github(token["access_token"])

    try:
        repos = []
        for repo in g.get_user().get_repos():
            repos.append({
                "id": repo.id,
                "name": repo.name,
                "full_name": repo.full_name,
                "private": repo.private,
                "html_url": repo.html_url,
                "description": repo.description,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
            })
        repos.sort(key=lambda r: r["updated_at"] or "", reverse=True)
        print(f"Fetched {len(repos)} repositories for user")
        print(f"Repository names: {[repo['name'] for repo in repos]}")
        print(f"Repos {repos}")
        return {"repositories": repos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}")

@router.post("/clone/{owner}/{repo}")
async def clone_repository(owner: str, repo: str):
    """Clone a repository and parse journal files"""
    if "user_token" not in tokens:
        raise HTTPException(status_code=401, detail="Not authenticated with GitHub")

    token = tokens["user_token"]

    repos_dir = Path("./repos")
    repos_dir.mkdir(exist_ok=True)

    user_repos_dir = repos_dir / owner
    user_repos_dir.mkdir(exist_ok=True)

    repo_path = user_repos_dir / repo

    try:
        repo_url = f"https://{token['access_token']}@github.com/{owner}/{repo}.git"
        git.Repo.clone_from(repo_url, repo_path)
        print(f"Cloned repository to {repo_path} with {len(list(repo_path.rglob("*.journal")))} journals")
        return {}
    except git.GitCommandError as e:
        raise HTTPException(status_code=400, detail=f"Failed to clone repository: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing repository: {str(e)}")

# list user's cloned journals (list of files in repos/{owner}/**/*.journal)
@router.get("/journals/{owner}")
async def list_cloned_repositories(owner: str):
    repos_dir = Path("./repos") / owner
    if not repos_dir.exists():
        raise HTTPException(status_code=404, detail="No repositories found for this user")
    
    journals = []
    for journal_file in repos_dir.rglob("*.journal"):
        journals.append(
            str(journal_file.resolve().relative_to(repos_dir.resolve()))
        )
    print(f"Found {len(journals)} journal files for user {owner}")
    return {"journals": journals}

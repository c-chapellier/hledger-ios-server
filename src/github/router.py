from fastapi import APIRouter, HTTPException, Depends
from github import Github
import git
import os
from pathlib import Path
import logging

from ..gzip_handler import GzipRoute
from ..auth.router import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["github"], route_class=GzipRoute)

@router.get("/repos")
async def list_repositories(current_user: dict = Depends(get_current_user)):
    """List user's GitHub repositories"""
    access_token = current_user["access_token"]
    github_username = current_user["github_username"]

    g = Github(access_token)

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
        logger.info(f"Fetched {len(repos)} repositories for user {github_username}")
        return repos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}")

@router.post("/clone/{repo}")
async def clone_repository(
    repo: str,
    current_user: dict = Depends(get_current_user)
):
    """Clone repository"""
    access_token = current_user["access_token"]
    username = current_user["github_username"]

    # Create user-specific directory
    repos_dir = Path(f"./repos/{username}")
    repos_dir.mkdir(parents=True, exist_ok=True)

    repo_path = repos_dir / repo

    try:
        repo_url = f"https://{access_token}@github.com/{username}/{repo}.git"
        git.Repo.clone_from(repo_url, repo_path)
        logger.info(f"Cloned repository {username}/{repo} for user {username}")
        return {"message": "Repository cloned successfully"}
    except git.GitCommandError as e:
        raise HTTPException(status_code=400, detail=f"Git error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/journals")
async def list_cloned_journals(
    current_user: dict = Depends(get_current_user)
):
    """List available journals in the user's cloned repositories"""
    username = current_user["github_username"]
    repos_dir = Path(f"./repos/{username}")

    if not repos_dir.exists():
        logger.info(f"No repositories found for user {username}")
        return []

    journals = []
    for journal_file in repos_dir.rglob("*.journal"):
        journals.append(str(journal_file.resolve().relative_to(repos_dir.resolve())))

    logger.info(f"Found {len(journals)} journal files for user {username}")
    return journals

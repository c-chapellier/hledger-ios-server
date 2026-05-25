from fastapi import HTTPException
from pathlib import Path
import logging
import git
from ..db.db import DB

logger = logging.getLogger(__name__)

class Git:

    @staticmethod
    def _get_git_repo(journal_path: Path, username: str) -> git.Repo:
        try:
            # Get the user's base directory for security validation
            user_base_path = DB.get_user_path(username)
            
            # Ensure journal_path is within user's directory
            if not journal_path.resolve().as_posix().startswith(user_base_path.resolve().as_posix()):
                logger.error(f"Security violation: journal path {journal_path} is outside user directory for {username}")
                raise HTTPException(status_code=403, detail="Security violation: path outside user directory")
            
            # Find the git repository root by walking up the directory tree, but only within user's folder
            repo_path = journal_path.parent
            while repo_path != repo_path.parent:  # Stop at filesystem root
                # Security check: ensure we don't go outside user's directory
                if not repo_path.resolve().as_posix().startswith(user_base_path.resolve().as_posix()):
                    logger.warning(f"Git search reached outside user directory for {username}, stopping search")
                    break
                
                if (repo_path / ".git").exists():
                    logger.info(f"Found git repo at {repo_path} for user {username}")
                    return git.Repo(repo_path)
                repo_path = repo_path.parent
            
            logger.warning(f"No git repository found for journal at {journal_path}")
            raise HTTPException(status_code=404, detail="Git repository not found for the specified journal")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error finding git repository: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to find git repository: {str(e)}")

    @staticmethod
    def pull_repository(journal_path: Path, username: str) -> None:
        repo = Git._get_git_repo(journal_path, username)
        try:
            repo.remotes.origin.pull(ff_only=True) # Pull only if fast-forward (no merge conflicts)
            logger.info(f"Successfully pulled repository for {journal_path} for user {username}")
            return
        except git.GitCommandError as e:
            error_msg = str(e)
            if "fatal: Not possible to fast-forward" in error_msg:
                logger.warning(f"Git pull rejected (not fast-forward) for {journal_path}: {error_msg}")
                raise HTTPException(status_code=409, detail="Repository has diverged from remote (not a fast-forward)")
            else:
                logger.error(f"Git pull failed for {journal_path}: {error_msg}")
                raise HTTPException(status_code=500, detail=f"Failed to pull repository: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error pulling repository for {journal_path}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to pull repository: {str(e)}")

    @staticmethod
    def add_commit_push_repository(journal_path: Path, username: str, commit_message: str) -> None:
        repo = Git._get_git_repo(journal_path, username)
        try:
            repo.index.add("*")
            repo.index.commit(commit_message)
            origin = repo.remote('origin')
            origin.push()
            logger.info(f"Successfully pushed repository for {username}: {commit_message}")
        except git.GitCommandError as e:
            error_msg = str(e)
            logger.error(f"Git push failed for {username}: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Failed to push repository: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error pushing repository for {username}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to push repository: {str(e)}")

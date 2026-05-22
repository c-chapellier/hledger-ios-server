from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
import subprocess
import json
import logging
import git
from .models import Account, Transaction, Posting
from ..gzip_handler import GzipRoute
from ..auth.router import get_current_user
from ..db.db import DB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"], route_class=GzipRoute)


async def validate_journal_path(
    journal: str,
    current_user: dict = Depends(get_current_user)
) -> Path:
    username = current_user["github_username"]
    
    try:
        journal_path = DB.get_journal_path(username, journal)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=f"Security violation: {str(e)}")
    
    if not journal_path.exists():
        raise HTTPException(status_code=404, detail=f"Journal not found at path: {journal_path}")
    
    return journal_path


def pull_repository(journal_path: Path, username: str) -> None:
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
                try:
                    repo = git.Repo(repo_path)
                    repo.remotes.origin.pull(ff_only=True) # Pull only if fast-forward (no merge conflicts)
                    logger.info(f"Successfully pulled repository {repo_path} for user {username}")
                    return
                except git.GitCommandError as e:
                    error_msg = str(e)
                    if "fatal: Not possible to fast-forward" in error_msg:
                        logger.warning(f"Git pull rejected (not fast-forward) for {repo_path}: {error_msg}")
                        raise HTTPException(status_code=409, detail="Repository has diverged from remote (not a fast-forward)")
                    else:
                        logger.error(f"Git pull failed for {repo_path}: {error_msg}")
                        raise HTTPException(status_code=500, detail=f"Failed to pull repository: {error_msg}")
            repo_path = repo_path.parent
        
        # If no git repo found, log and continue (might be a local directory)
        logger.warning(f"No git repository found for journal at {journal_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error pulling repository: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to sync repository: {str(e)}")


@router.get("/transactions/{journal:path}")
async def get_transactions(
    journal_path: Path = Depends(validate_journal_path),
    current_user: dict = Depends(get_current_user)
) -> list[Transaction]:
    """Get all transactions from a journal"""
    username = current_user["github_username"]
    logger.info(f"User {username} requesting transactions from {journal_path}")
    
    pull_repository(journal_path, username)
    
    try:
        result = subprocess.run(
            ["hledger", "print", "--explicit", "--output-format=json", "-f", str(journal_path)],
            capture_output=True,
            text=True,
            check=True
        )
        raw_transactions = json.loads(result.stdout)
        
        # Reformat the transactions
        formatted_transactions: list[Transaction] = []
        for tx in raw_transactions:
            formatted_tx = Transaction(
                index=tx["tindex"],
                date=tx["tdate"],
                description=tx["tdescription"],
                postings=[]
            )
            for posting in tx["tpostings"]:
                amount = posting["pamount"][0]["aquantity"]["floatingPoint"] if posting["pamount"] else None
                formatted_posting = Posting(
                    account=posting["paccount"],
                    amount=amount
                )
                formatted_tx.postings.append(formatted_posting)
            formatted_transactions.append(formatted_tx)
        
        logger.info(f"Successfully retrieved {len(formatted_transactions)} transactions for {username}/{journal_path.name}")
        return formatted_transactions
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to run hledger for {username}/{journal_path.name}: {e.stderr or str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse hledger JSON output for {username}/{journal_path.name}: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error retrieving transactions for {username}/{journal_path.name}: {str(e)}")


@router.get("/accounts/{journal:path}")
async def get_balances(
    journal_path: Path = Depends(validate_journal_path),
    current_user: dict = Depends(get_current_user)
) -> list[Account]:
    """Get all accounts from a journal"""
    username = current_user["github_username"]
    logger.info(f"User {username} requesting accounts from {journal_path}")
    
    pull_repository(journal_path, username)
    
    try:
        result = subprocess.run(
            ["hledger", "balance", "--output-format=json", "-f", str(journal_path)],
            capture_output=True,
            text=True,
            check=True
        )
        raw_accounts = json.loads(result.stdout)
        
        formatted_accounts: list[Account] = []
        for acc in raw_accounts[0]:
            formatted_acc = Account(
                name=acc[0],
                balance=acc[3][0]["aquantity"]["floatingPoint"]
            )
            formatted_accounts.append(formatted_acc)
        
        logger.info(f"Successfully retrieved {len(formatted_accounts)} accounts for {username}/{journal_path.name}")
        return formatted_accounts
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to run hledger for {username}/{journal_path.name}: {e.stderr or str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse hledger JSON output for {username}/{journal_path.name}: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error retrieving accounts for {username}/{journal_path.name}: {str(e)}")

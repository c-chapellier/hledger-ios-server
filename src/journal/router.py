from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
import subprocess
import json
import logging
import git
from datetime import datetime
from .models import Account, Transaction, Posting, CreateTransactionRequest, FileListResponse
from ..gzip_handler import GzipRoute
from ..auth.router import get_current_user
from ..db.db import DB
from ..git.git import Git

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


@router.get("/transactions/{journal:path}")
async def get_transactions(
    journal_path: Path = Depends(validate_journal_path),
    current_user: dict = Depends(get_current_user)
) -> list[Transaction]:
    """Get all transactions from a journal"""
    username = current_user["github_username"]
    logger.info(f"User {username} requesting transactions from {journal_path}")
    
    Git.pull_repository(journal_path, username)
    
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
    
    Git.pull_repository(journal_path, username)
    
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


@router.get("/files/{journal:path}")
async def get_journal_files(
    journal: str,
    current_user: dict = Depends(get_current_user)
) -> FileListResponse:
    """Get all available journal files for a given journal file/directory"""
    username = current_user["github_username"]
    
    try:
        journal_path = DB.get_journal_path(username, journal)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=f"Security violation: {str(e)}")
    
    if not journal_path.exists():
        raise HTTPException(status_code=404, detail=f"Journal not found at path: {journal_path}")
    
    logger.info(f"User {username} requesting journal files from {journal_path}")
    
    Git.pull_repository(journal_path, username)

    try:
        # Use hledger files command to get all included journal files
        result = subprocess.run(
            ["hledger", "files", "-f", str(journal_path)],
            capture_output=True,
            text=True,
            check=True
        )
        
        files = result.stdout.strip().split('\n')
        # Filter out empty lines and convert to relative paths
        user_base_path = DB.get_user_path(username)
        relative_files = []
        
        for file_path in files:
            if file_path.strip():
                try:
                    rel_path = str(Path(file_path).resolve().relative_to(user_base_path.resolve()))
                    relative_files.append(rel_path)
                except ValueError:
                    # File is outside user directory, skip it
                    logger.warning(f"Skipping file outside user directory: {file_path}")
                    continue
        
        logger.info(f"Retrieved {len(relative_files)} journal files for {username}")
        return FileListResponse(files=relative_files)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to run hledger files: {e.stderr or str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error retrieving journal files: {str(e)}")


@router.post("/transactions")
async def create_transaction(
    request: CreateTransactionRequest,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Create a new transaction in a journal file"""
    username = current_user["github_username"]
    
    try:
        journal_path = DB.get_journal_path(username, request.journal)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=f"Security violation: {str(e)}")
    if not journal_path.exists():
        raise HTTPException(status_code=404, detail=f"Journal not found at path: {journal_path}")
    if len(request.postings) != 2:
        raise HTTPException(status_code=400, detail="Exactly 2 postings are required")
    
    logger.info(f"User {username} creating transaction in {journal_path}")

    Git.pull_repository(journal_path, username)
    
    try:
        
        # Format the transaction in hledger format
        transaction_text = f"{request.date}\n{request.description}"
        if request.comment:
            transaction_text += f"; {request.comment}"
        transaction_text += "\n"
        for posting in request.postings:
            if posting.amount is not None:
                transaction_text += f"{posting.account}\n{posting.amount}\n"
        # add postings without amount at the end to have balancing
        for posting in request.postings:
            if posting.amount is None:
                transaction_text += f"{posting.account}\n\n"

        result = subprocess.run(
            ["hledger", "add", "-f", str(journal_path)],
            input=transaction_text + "\ny\n.\n",
            capture_output=True,
            text=True,
            check=True
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
        
        logger.info(f"Successfully added transaction to {journal_path} using hledger add")

        Git.add_commit_push_repository(journal_path, username, f"[HLEDGER SERVER] Add transaction: {request.description} on {request.date}")
        
        return {
            "message": "Transaction created successfully",
            "success": True
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"hledger add failed for {username}: {e.stderr or str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to add transaction: {e.stderr or str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating transaction for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")

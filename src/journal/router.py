from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
import subprocess
import json
import logging
from .models import Account, Transaction, Posting
from ..gzip_handler import GzipRoute
from ..auth.router import get_current_user
from ..db.db import DB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"], route_class=GzipRoute)

@router.get("/transactions/{journal:path}")
async def get_transactions(
    journal: str,
    current_user: dict = Depends(get_current_user)
) -> list[Transaction]:
    """Get all transactions from a journal"""
    username = current_user["github_username"]
    logger.info(f"User {username} requesting transactions from {journal}")
    
    try:
        journal_path = DB.get_journal_path(username, journal)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=f"Security violation: {str(e)}")
    
    if not journal_path.exists():
        raise HTTPException(status_code=404, detail=f"Journal not found at path : {journal_path}")
    
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
        
        logger.info(f"Successfully retrieved {len(formatted_transactions)} transactions for {username}/{journal}")
        return formatted_transactions
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to run hledger for {username}/{journal}: {e.stderr or str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse hledger JSON output for {username}/{journal}: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error retrieving transactions for {username}/{journal}: {str(e)}")


@router.get("/accounts/{journal:path}")
async def get_balances(
    journal: str,
    current_user: dict = Depends(get_current_user)
) -> list[Account]:
    """Get all accounts from a journal"""
    username = current_user["github_username"]
    logger.info(f"User {username} requesting accounts from {journal}")
    
    try:
        journal_path = DB.get_journal_path(username, journal)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=f"Security violation: {str(e)}")
    
    if not journal_path.exists():
        raise HTTPException(status_code=404, detail=f"Journal not found at path: {journal_path}")
    
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
        
        logger.info(f"Successfully retrieved {len(formatted_accounts)} accounts for {username}/{journal}")
        return formatted_accounts
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to run hledger for {username}/{journal}: {e.stderr or str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse hledger JSON output for {username}/{journal}: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error retrieving accounts for {username}/{journal}: {str(e)}")

from fastapi import APIRouter, HTTPException
from pathlib import Path
import subprocess
import json
from fastapi import APIRouter
from .models import Transaction, Posting
from dotenv import load_dotenv
load_dotenv()

from ..gzip_handler import GzipRoute

router = APIRouter(prefix="/missions", tags=["missions"], route_class=GzipRoute)

@router.get("/transactions/{owner}/{journal:path}")
async def get_transactions(owner: str, journal: str) -> list[Transaction]:
    """Get all transactions from a journal"""
    journal_path = Path("./repos") / owner / journal
    if not journal_path.exists():
        raise HTTPException(status_code=404, detail="Journal not found")
    
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
        
        return formatted_transactions
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to run hledger: {e}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse hledger output: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

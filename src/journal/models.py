from typing import Optional

from pydantic import BaseModel

class Transaction(BaseModel):
    index: int
    date: str
    description: str
    postings: list[Posting]

class Posting(BaseModel):
    account: str
    amount: Optional[float] = None

class Account(BaseModel):
    name: str
    balance: float

class CreateTransactionRequest(BaseModel):
    """Request body for creating a new transaction"""
    journal: str  # Journal file path (relative to user's repos directory)
    date: str  # YYYY-MM-DD
    description: str
    postings: list[Posting]
    comment: Optional[str] = None

class FileListResponse(BaseModel):
    """Response for listing available journal files"""
    files: list[str]  # List of journal file paths relative to user's repos directory

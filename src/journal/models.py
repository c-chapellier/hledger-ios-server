from typing import Optional

from pydantic import BaseModel

class Transaction(BaseModel):
    index: int
    date: str
    description: str
    postings: list[Posting]

class Posting(BaseModel):
    account: str
    amount: Optional[float]

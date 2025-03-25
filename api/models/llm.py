from pydantic import BaseModel
from typing import List, Optional

class EmailDocument(BaseModel):
    id: str
    text: str
    score: Optional[float] = None

class LLMQueryWithDocuments(BaseModel):
    query: str
    documents: List[EmailDocument]

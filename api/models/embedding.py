from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class EmbeddingMetadata(BaseModel):
    folder: Optional[str] = None
    from_email: Optional[str] = None
    subject: Optional[str] = None
    from_name: Optional[str] = None
    vector: Optional[List[float]] = None
    created: Optional[int] = None

class EmbeddingMatch(BaseModel):
    message_id: str
    score: Optional[float] = None
    created: Optional[int] = None
    metadata: Optional[EmbeddingMetadata] = None
    text: Optional[str] = None

class EmbeddingResponse(BaseModel):
    address: str
    matches: Optional[List[EmbeddingMatch]] = None
    model: Optional[str] = None
    knee: Optional[int] = None # knee-point detection (suggested number of matches)

class EmbeddingRequest(BaseModel):
    message_id: str
    address: str
    model: Optional[str] = None

class EmbeddingUpsertRequest(BaseModel):
    message_id: str
    address: str
    metadata: EmbeddingMetadata

class DeleteRequest(BaseModel):
    message_ids: List[str]
    address: str
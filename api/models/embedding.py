from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class EmbeddingMetadata(BaseModel):
    folder: str
    from_email: str
    subject: Optional[str] = None
    from_name: Optional[str] = None
    vector: Optional[List[float]] = None
    created: Optional[int] = None

class EmbeddingMatch(BaseModel):
    message_id: str
    score: Optional[float] = None
    created: Optional[int] = None
    metadata: Optional[EmbeddingMetadata] = None

class EmbeddingResponse(BaseModel):
    address: str
    matches: List[EmbeddingMatch]
    model: Optional[str] = None

class EmbeddingRequest(BaseModel):
    message_id: str
    address: str
    model: Optional[str] = None

class EmbeddingUpsertRequest(BaseModel):
    message_id: str
    address: str
    metadata: EmbeddingMetadata
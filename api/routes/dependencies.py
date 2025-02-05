from fastapi import Request
from api.services.couchdb_service import CouchDBService
from api.services.embedding_service import EmbeddingService
from api.services.pinecone_service import PineconeService
from api.services.embedding_task_queue import EmbeddingTaskQueue
from fastapi.security import OAuth2PasswordBearer
from typing_extensions import Annotated

# Dependency functions to retrieve services from app.state
def get_couchdb_service(request: Request) -> CouchDBService:
    return request.app.state.couchdb_service

def get_embedding_service(request: Request) -> EmbeddingService:
    return request.app.state.embedding_service

def get_pinecone_service(request: Request) -> PineconeService:
    return request.app.state.pinecone_service

def get_embedding_task_queue(request: Request) -> EmbeddingTaskQueue:
    return request.app.state.embedding_task_queue

reuseable_oauth = OAuth2PasswordBearer(
    tokenUrl="/api/token",
    scheme_name="JWT"
)
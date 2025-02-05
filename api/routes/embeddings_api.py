
from tools.optimal_embeddings_model.data_types.email import Email
from ..models.embedding import EmbeddingMatch, EmbeddingMetadata, EmbeddingResponse, EmbeddingRequest, EmbeddingUpsertRequest
from fastapi import APIRouter, Depends, HTTPException
from ..services.couchdb_service import CouchDBService
from ..services.embedding_service import EmbeddingService
from ..services.pinecone_service import PineconeService
from ..services.embedding_task_queue import EmbeddingTaskQueue
from .dependencies import get_couchdb_service, get_embedding_service, get_pinecone_service, get_embedding_task_queue
from fastapi import Query, Security
from api.routes.extend_token_middleware import verify_and_extend_token
from api.models.system_user import SystemUser

from typing import List

router = APIRouter()

def create_metadata(email: Email):
    """
    Create metadata for the email (helper method)
    """
    if email.created is None:
        raise InvalidUsage("Email created date is missing")
    if email.folder is None:
        raise InvalidUsage("Email folder is missing")
    metadata = {
        "created": email.created,
        "folder": email.folder,
        "from_name": email.sender_name,
        "from": email.sender_email,
    }
    return metadata

@router.post("/api/v1/embedding/{address}/message/{message_id}", response_model=EmbeddingResponse, response_model_exclude_none=True) 
async def upsert_embedding_by_message_id(
    message_id: str,
    address: str,
    couchdb_service: CouchDBService = Depends(get_couchdb_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    embedding_task_queue: EmbeddingTaskQueue = Depends(get_embedding_task_queue),
    user: SystemUser = Security(verify_and_extend_token),
):
    """
    Upsert email embedding by message ID
    """
    email = couchdb_service.get_message_by_id(message_id, address)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    metadata = create_metadata(email)
    embeddings = embedding_service.create_embedding(email)
    embedding_task_queue.upsert_embedding(address, message_id, embeddings[0].tolist(), metadata)

    return EmbeddingResponse(
        address=address,
        matches=[EmbeddingMatch(
            message_id=message_id,
            created=metadata.get("created", None),
            metadata=EmbeddingMetadata(
                subject=email.subject,
                folder=metadata.get("folder", None),
                from_email=metadata.get("from", None),
                from_name=metadata.get("from_name", None)
            )
        )],
        model=embedding_service.embedding_model
    )

@router.post("/api/v1/embedding", response_model=EmbeddingResponse, response_model_exclude_none=True)
async def upsert_embedding(
    body: EmbeddingUpsertRequest,
    couchdb_service: CouchDBService = Depends(get_couchdb_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    pinecone_service: PineconeService = Depends(get_pinecone_service),
    embedding_task_queue: EmbeddingTaskQueue = Depends(get_embedding_task_queue),
    user: SystemUser = Security(verify_and_extend_token),
):
    """
    Upsert email embedding (intendet for storing encrypted embeddings)
    """
    if body.metadata is None:
        raise HTTPException(status_code=400, detail="Metadata is missing")
    if body.metadata.vector is None:
        raise HTTPException(status_code=400, detail="Vector is missing")
    if body.metadata.created is None:
        raise HTTPException(status_code=400, detail="Created date is missing")
        
    try:
        request_vector = body.metadata.vector
        # validate request vector for dimensions and type
        if len(request_vector) != embedding_service.model.config.hidden_size:
            raise ValueError("Invalid vector size")
        if not all(isinstance(x, float) for x in request_vector):
            raise ValueError("Invalid vector type")
        
        metadata = body.metadata.dict()
        metadata.pop("vector", None) # remove vector from metadata

        # damn...didn't notice from is reserved keyword
        from_name = metadata.get("from_name", None)
        metadata.pop("from_name", None) 
        if from_name is not None:
            metadata["from"] = from_name
        
        embedding_task_queue.upsert_embedding(body.address, body.message_id, request_vector, metadata)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    matches = []
    matches.append(EmbeddingMatch(
        message_id=body.message_id,
        created=metadata.get("created", None),
        metadata=EmbeddingMetadata(
            subject=metadata.get("subject", None),
            folder=metadata.get("folder", None),
            from_email=metadata.get("from", None),
            from_name=metadata.get("from_name", None)
        )
    ))
    return EmbeddingResponse(
        address=body.address,
        matches=matches,
        model=embedding_service.embedding_model
    )

@router.get("/api/v1/embedding", response_model=EmbeddingResponse,  response_model_exclude_none=True)
async def query_embedding(
    address: str = Query(..., description="The address of the user"),
    query: str = Query(..., description="The query string"),
    top_k: int = Query(10, description="The number of top results to return"),
    folder: str = Query(None, description="The folder to search in"),
    beforeTimestamp: int = Query(None, description="The timestamp to search before"),
    afterTimestamp: int = Query(None, description="The timestamp to search after"),
    from_email: str = Query(None, description="The email to search from"),
    pinecone_service: PineconeService = Depends(get_pinecone_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    couchdb_service: CouchDBService = Depends(get_couchdb_service),
    user: SystemUser = Security(verify_and_extend_token),
):
    """
    Query embeddings
    """
    vector = embedding_service.embedder.embed([query])

    # query embedding
    response = pinecone_service.query(
        address=address, 
        query_embedding=vector[0].tolist(), 
        top_k=top_k, 
        folder=folder, 
        beforeTimestamp=beforeTimestamp, 
        afterTimestamp=afterTimestamp, 
        from_email=from_email
    )
    matches = response.matches or []
    output_matches:List[EmbeddingMatch] = []
    all_ids = [match.id for match in matches]
    
    # retrieve all document by id from the couch database (for display purposes)
    emails = couchdb_service.get_bulk_by_id(address, all_ids)
    email_dict = {email.message_id: email for email in emails}

    for match in matches:
        metadata = match.metadata or {}
        output_matches.append(EmbeddingMatch(
            message_id=match.id,
            score=match.score,
            created=metadata.get("created", None),
            metadata=EmbeddingMetadata(
                subject=email_dict[match.id].subject,
                folder=metadata.get("folder", None),
                from_email=metadata.get("from", None),
                from_name=metadata.get("from_name", None),
            )
        ))

    resp:EmbeddingResponse = EmbeddingResponse(
        address=address,
        matches=output_matches,
        model=embedding_service.embedding_model
    )
    
    return resp

@router.delete("/api/v1/embedding", response_model=EmbeddingResponse)
async def delete_message_by_id(
    body: EmbeddingRequest,
    pinecone_service: PineconeService = Depends(get_pinecone_service),
    user: dict = Depends(verify_and_extend_token),
):
    """
    Delete a message embedding by ID.
    """
    try:
        pinecone_service.delete(body.message_id, body.address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={"message": "Embedding deleted successfully"})


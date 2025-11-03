
from tools.optimal_embeddings_model.data_types.email import Email
from ..models.embedding import EmbeddingMatch, EmbeddingMetadata, EmbeddingResponse, EmbeddingRequest, EmbeddingUpsertRequest, DeleteRequest
from fastapi import APIRouter, Depends, HTTPException
from ..services.couchdb_service import CouchDBService
from ..services.embedding_service import EmbeddingService
from ..services.pinecone_service import PineconeService
from ..services.embedding_task_queue import EmbeddingTaskQueue
from ..services.llm_service import LLMService
from .dependencies import get_couchdb_service, get_embedding_service, get_pinecone_service, get_embedding_task_queue, get_llm_service
from fastapi import Query, Security
from api.routes.extend_token_middleware import verify_and_extend_token
from api.models.system_user import SystemUser
from ..models.errors import UnsupportedMessageTypeError, NotFoundError, UnauthorizedError
from queue import Queue
import threading
import asyncio
from loguru import logger
import json
from typing import List
import traceback
from api.utils.query_composer import QueryComposer
from kneed import KneeLocator
import datetime
from api.models.llm import EmailDocument

router = APIRouter()

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

    embedding_task_queue.upsert_embedding(address, message_id)

    return EmbeddingResponse(
        address=address,
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
        
        metadata = body.metadata.model_dump()
        del metadata["vector"]

        # remove None values from metadata
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        # get the email from the database
        message = couchdb_service.get_raw_message_by_id(body.message_id, body.address)
        if message is None:
            raise ValueError(f"Email not found for message_id: {body.message_id}, address: {body.address}")

        # preventing multiple inserts, skip adding to index if already exists
        if message.get("search", False):
            return EmbeddingResponse(
                address=body.address,
                model=embedding_service.embedding_model
            )

        pinecone_service.upsert(body.address, body.message_id, request_vector, metadata)
        
        # if upsert successfull 
        message["search"] = True
        couchdb_service.put_message(message, body.address)
    except ValueError as e:
        logger.debug(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        logger.debug(f"NotFoundError: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.debug(f"Exception: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

    return EmbeddingResponse(
        address=body.address,
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
    llm_service: LLMService = Depends(get_llm_service),
    user: SystemUser = Security(verify_and_extend_token),
):
    """
    Query embeddings
    """
    try:
        short_query = query
        pinecone_filter = {"sort": "NO_SORT", "timestampBefore": None, "timestampAfter": None, "fromEmail": None}
        try:
            result = await llm_service.selfquery(query)
            result_json = json.loads(result)
            logger.debug(f"LLM result JSON: {result_json}")
            short_query = result_json.get("query", query)
            if short_query == "":
                short_query = query
            short_query = "query: " + short_query

            query_composer = QueryComposer()
            pinecone_filter = query_composer.compose(result_json)
            if pinecone_filter.sort == "NO_SORT" or pinecone_filter.sort is None or pinecone_filter.sort == "":
                print("no sort")
            else:
                print(f"sorting by created {pinecone_filter.sort}")
            beforeTimestamp = pinecone_filter.timestampBefore
            afterTimestamp = pinecone_filter.timestampAfter
            from_email = pinecone_filter.fromEmail

        except Exception as e:
            logger.debug(f"Exception: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # logger.debug(f"LLM result JSON: {result_json}")

        vector = embedding_service.embedder.embed(short_query)
        
        # query embedding
        search_top_number = top_k
        if pinecone_filter.sort is None or pinecone_filter.sort == "" or pinecone_filter.sort == "NO_SORT":
            search_top_number = top_k * 5
        elif pinecone_filter.sort == "desc":
            # since we are sorting by desc, we need to search for the most recent messages
            # we will search for the most recent 90 days
            afterTimestamp = int(datetime.datetime.now().timestamp() * 1000 - (90 * 24 * 60 * 60 * 1000))
            search_top_number = 300
        elif pinecone_filter.sort == "asc":
            # since we are sorting by asc, we need to search for the oldest messages
            # we will skip today's messages
            beforeTimestamp = int(datetime.datetime.now().timestamp() * 1000 - (1 * 24 * 60 * 60 * 1000))
            search_top_number = 1000
        
        response = pinecone_service.query(
            address=address, 
            query_embedding=vector.tolist(), 
            top_k=search_top_number, # 5 times more results than requested (to account for filtering and sorting)
            folder=folder, 
            beforeTimestamp=beforeTimestamp, 
            afterTimestamp=afterTimestamp, 
            from_email=from_email
        )
        matches = response.matches or []
        output_matches:List[EmbeddingMatch] = []

        # knee-point detection
        knee = len(matches)
        if len(matches) > 3:
            # print scores to console
            kl = KneeLocator(
                range(len(matches)),
                [match.score for match in matches],
                curve="convex",
                direction="decreasing"
            )
            knee = kl.knee
            
        logger.debug(f"suggested knee point: {knee}")

        all_ids = [match.id for match in matches]
        
        # retrieve all document by id from the couch database (for display purposes)
        if len(all_ids) > 0:
            emails, missing_ids = couchdb_service.get_bulk_by_id(address, all_ids, pinecone_filter.sort)
            if missing_ids:
                logger.debug(f"missing ids in database: {missing_ids}") 
                asyncio.create_task(pinecone_service.delete_by_ids_async(missing_ids, address))
                logger.debug(f"deleted {len(missing_ids)} messages from Pinecone")

            email_dict = {email.message_id: email for email in emails if email is not None}

        for match in matches:
            match_id = match.id.replace("+", " ") # i don't know what exactly couchdb does but i know it doesn't like + in there
            metadata = match.metadata or {}
            # check if match_id is in the email_dict
            subject = None
            if match_id not in email_dict:
                subject = metadata.get("subject", None)
            else:
                subject = email_dict[match_id].subject

            output_matches.append(EmbeddingMatch(
                message_id=match.id,
                score=match.score,
                created=metadata.get("created", None),
                metadata=EmbeddingMetadata(
                    subject=subject,
                    folder=metadata.get("folder", None),
                    from_email=metadata.get("from_email", None),
                    from_name=metadata.get("from_name", None),
                )
            ))

        # clip results to top_k
        output_matches = output_matches[:top_k]

        # rerank here
        if len(output_matches) > 3:
            email_docs = {}
            # collect top_k output matches as email documents
            for match in output_matches:
                if match.message_id in email_dict:
                    email = email_dict[match.message_id]
                    if email.subject is None and (email.sentences is None or len(email.sentences) == 0):
                        continue
                    email_docs[match.message_id] = EmailDocument(
                        id=match.message_id,
                        text=".".join(email.sentences),
                        score=match.score
                    )
                
            reranked_results = pinecone_service.rerank(query, list[EmailDocument](email_docs.values()))    # convert to list to avoid type error
            score_lookup_map = {result["id"]: result["score"] for result in reranked_results["results"]}
            # overwrite scores in output_matches
            for match in output_matches:
                if match.message_id in score_lookup_map:
                    match.score = score_lookup_map[match.message_id]
                    # clip sentences to 200 characters
                    if email_docs[match.message_id] is not None:
                        if len(email_docs[match.message_id].text) > 200:
                            match.text = email_docs[match.message_id].text[:200]
                        else:
                            match.text = email_docs[match.message_id].text
            output_matches = sorted(output_matches, key=lambda m: m.score, reverse=True)

        resp:EmbeddingResponse = EmbeddingResponse(
            address=address,
            matches=output_matches,
            model=embedding_service.embedding_model,
            knee=knee
        )
        return resp
    except NotFoundError as e:
        logger.debug(f"Not found error: {e}")
        resp:EmbeddingResponse = EmbeddingResponse(
            address=address,
            matches=[],
            model=embedding_service.embedding_model
        )
        return resp
    except Exception as e:
        logger.debug(f"Exception: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/v1/embedding")
async def delete_message_by_ids(
    body: DeleteRequest,
    pinecone_service: PineconeService = Depends(get_pinecone_service),
    user: dict = Depends(verify_and_extend_token),
    status_code: int = 204, # no content on success
):
    """
    Delete a message embedding by ID.
    """
    try:
        # Delete from Pinecone asynchronously in background
        if body.message_ids:
            asyncio.create_task(pinecone_service.delete_by_ids_async(body.message_ids, body.address))
    except Exception as e:
        logger.debug(f"Exception: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))



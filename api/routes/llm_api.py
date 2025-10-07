from fastapi import APIRouter
from ..models.llm import LLMQueryWithDocuments
from ..services.llm_service import LLMService
from fastapi import Depends
from .dependencies import get_llm_service
import json
from ..services.pinecone_service import PineconeService
from .dependencies import get_pinecone_service

router = APIRouter()

@router.post("/api/v1/rerank")
async def rerank(
    queryWithDocuments: LLMQueryWithDocuments,
    llm_service: LLMService = Depends(get_llm_service),
    pinecone_service: PineconeService = Depends(get_pinecone_service),
):
    """
    Rerank a message using a LLM.
    """
    if len(queryWithDocuments.documents) == 0:
        return { "results": [] }
    reranked_results = pinecone_service.rerank(queryWithDocuments.query, queryWithDocuments.documents)
    return reranked_results

@router.post("/api/v1/llm/insights")
async def insights(
    queryWithDocuments: LLMQueryWithDocuments,
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Extract insights from a message using a LLM.
    """
    if len(queryWithDocuments.documents) == 0:
        return { "query": queryWithDocuments.query, "results": [], "answer": "No results found" }
    insights = llm_service.extract_insights(queryWithDocuments)
    insights_json = json.loads(insights)
    return insights_json

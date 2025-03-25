from fastapi import APIRouter
from ..models.llm import LLMQueryWithDocuments
from ..services.llm_service import LLMService
from fastapi import Depends
from .dependencies import get_llm_service
import json

router = APIRouter()

@router.post("/api/v1/rerank")
async def rerank(
    queryWithDocuments: LLMQueryWithDocuments,
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Rerank a message using a LLM.
    """
    reranked_results = llm_service.rerank(queryWithDocuments.query, queryWithDocuments.documents)
    # reranked_results_json = json.loads(reranked_results)
    return reranked_results

@router.post("/api/v1/llm/insights")
async def insights(
    queryWithDocuments: LLMQueryWithDocuments,
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Extract insights from a message using a LLM.
    """
    insights = llm_service.extract_insights(queryWithDocuments)
    insights_json = json.loads(insights)
    return insights_json

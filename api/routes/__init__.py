from fastapi import APIRouter
from .health_check import router as healthcheck_router
from .embeddings_api import router as embeddings_router
from .token_api import router as token_router
from .llm_api import router as llm_router

main_router = APIRouter()

main_router.include_router(healthcheck_router)
main_router.include_router(embeddings_router)
main_router.include_router(token_router)
main_router.include_router(llm_router)

@main_router.get("/")
async def index():
    return {"message": "Mailio AI API!"}
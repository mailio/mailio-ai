from fastapi import APIRouter, Request, Depends
from ..models.health_check import HealthCheckResponse
from typing import Dict
from config import get_config

router = APIRouter()

@router.get("/api/healthcheck", response_model=HealthCheckResponse)
async def health_check(config: Dict = Depends(get_config)):
    return {
        "status": "ok",
        "version": config.get("version", "0.0.4")
    }
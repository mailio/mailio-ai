from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from logging_handler import use_logginghandler
import datetime
import argparse
import sys
from enum import Enum
from api.services.couchdb_service import CouchDBService
from api.services.embedding_service import EmbeddingService
from api.services.pinecone_service import PineconeService
from api.services.embedding_task_queue import EmbeddingTaskQueue, start_embedding_worker
# from api.routes.extend_token_middleware import AutoExtendTokenMiddleware
import os
import multiprocessing


# config
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")
from config import cfg, get_config

# routes
from api.routes import main_router

app = FastAPI(
    title="Email Embeddings API",
    description="API for creating and managing email embeddings",
    version="0.1",
    contact={
        "name": "Igor Rendulic",
        "url": "http://localhost:8888/docs",
        "email": "igor@mail.io"
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html"
    }
)

logger = use_logginghandler()

if cfg and cfg.get("cors_origins", None):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.get("cors_origins"),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

cfg = get_config()
app.state.config = cfg
app.state.couchdb_service = CouchDBService(cfg)
app.state.embedding_service = EmbeddingService(cfg)
app.state.pinecone_service = PineconeService.get_instance(cfg, dimension=app.state.embedding_service.model.config.hidden_size)
app.state.embedding_task_queue = EmbeddingTaskQueue(cfg)

# app.add_middleware(AutoExtendTokenMiddleware)

# start embedding worker
queues = [app.state.embedding_task_queue.queue.name]
redis_conn = app.state.embedding_task_queue.redis_conn

for i in range(min(multiprocessing.cpu_count(), 2)): # max 2 workers
    multiprocessing.Process(target=start_embedding_worker, args=(queues,cfg, )).start()

app.include_router(main_router)

EXCEPTION_LOG_LEVELS = {
    "HTTPException": "error",  # Default HTTPException logs as "error"
    "UnsupportedMessageTypeError": "warning",
    "NotFoundError": "warning",
    "UnauthorizedError": "warning",
    "InvalidUsageError": "warning",
    "ValueError": "error",
}

@app.exception_handler(HTTPException)
async def unified_exception_handler(request: Request, exc: HTTPException):
    """Handles multiple HTTP exceptions dynamically."""
    
    log_level = EXCEPTION_LOG_LEVELS.get(exc.__class__.__name__, "error")  # Default to "error"
    
    log_message = f"{exc.__class__.__name__}: {exc.detail}"
    
    # Log at the appropriate level
    if log_level == "info":
        logger.info(log_message)
    elif log_level == "warning":
        logger.warning(log_message)
    elif log_level == "error":
        logger.error(log_message, exc_info=True)  # Logs full traceback

    sys.stdout.flush()  # Ensure logs appear immediately

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )

# if __name__ == '__main__':
#     # run the embedding workers
#     uvicorn.run("main:app", host="0.0.0.0", port=8888, log_level="info", reload=True)
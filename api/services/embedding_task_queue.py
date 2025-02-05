from typing import Dict, List
from rq import Queue, Worker
from redis import Redis
from api.services.pinecone_service import PineconeService
import logging
from logging_handler import use_logginghandler
import signal

use_logginghandler()

def create_embedding(address:str, message_id:str , metadata: Dict, vector: List[float], cfg:Dict, dimension:int):
    # create an embedding from a message id
    pc_service = PineconeService.get_instance(cfg, dimension=dimension)
    try:
        # remove from metadata all fields with None 
        metadata = {k: v for k, v in metadata.items() if v is not None}
        pc_service.upsert(address, message_id, vector, metadata)
    except Exception as e:
        logging.error(f"Error upserting embedding for message_id: {message_id}, address: {address}, error: {e}")
        raise e

class EmbeddingTaskQueue:
    def __init__(self, cfg: Dict, dimension: int = 1024):
        redis_cfg = cfg.get("redis")
        if redis_cfg is None:
            raise ValueError("Redis configuration is missing")
        redis_host = redis_cfg.get("host")
        redis_port = redis_cfg.get("port")
        redis_db = redis_cfg.get("db")
        username = redis_cfg.get("username")
        password = redis_cfg.get("password")
        # check if any of the settings are missing
        if redis_host is None:
            raise ValueError("Redis host is missing")
        if redis_port is None:
            raise ValueError("Redis port is missing")
        if redis_db is None:
            raise ValueError("Redis db is missing")
        redisConnection = Redis(host=redis_host, port=redis_port, db=redis_db, username=username, password=password)
        self.redis_conn = redisConnection
        self.dimension = dimension
        self.cfg = cfg
        self.queue = Queue("default_embedding_queue", connection=redisConnection)

    def upsert_embedding(self, address, message_id, vector, metadata):
        job = self.queue.enqueue(create_embedding, address, message_id, metadata, vector, self.cfg, self.dimension)
    
def start_embedding_worker(queues:List[str], cfg:Dict):
    redis_cfg = cfg.get("redis")
    if redis_cfg is None:
        raise ValueError("Redis configuration is missing")
    redis_host = redis_cfg.get("host")
    redis_port = redis_cfg.get("port")
    redis_db = redis_cfg.get("db")
    username = redis_cfg.get("username")
    password = redis_cfg.get("password")
    # check if any of the settings are missing
    if redis_host is None:
        raise ValueError("Redis host is missing")
    if redis_port is None:
        raise ValueError("Redis port is missing")
    if redis_db is None:
        raise ValueError("Redis db is missing")
    redis_conn = Redis(host=redis_host, port=redis_port, db=redis_db, username=username, password=password)

    worker = Worker(queues, connection=redis_conn)

    def handle_shutdown(signum, frame):
        """Graceful shutdown handler."""
        print(f"Received shutdown signal {signum}, stopping worker...")
        worker.stop()  # Stop the worker loop
        redis_conn.close()  # Close Redis connection
        sys.exit(0)  # Exit cleanly

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        worker.work()
    except KeyboardInterrupt:
        handle_shutdown(signal.SIGINT, None)
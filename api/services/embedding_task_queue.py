from typing import Dict, List
from rq import Queue, Worker, Retry
from redis import Redis, ConnectionError
from api.services.pinecone_service import PineconeService
from api.services.couchdb_service import CouchDBService
from api.services.embedding_service import EmbeddingService
import logging
from logging_handler import use_logginghandler
import signal
import sys
from tools.optimal_embeddings_model.data_types.email import Email
import os
import json
import time
import traceback

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")
from config import cfg, get_config

use_logginghandler()

cfg = get_config()
REDIS_QUEUE = "default_embedding_queue"
MAX_RETRIES = 3
RETRY_DELAY = 5 # seconds delay before re-queuing failed task

def create_metadata(email: Email):
    """
    Create metadata for the email (helper method)
    """
    if email.created is None:
        raise ValueError("Email created date is missing")
    if email.folder is None:
        raise ValueError("Email folder is missing")
    metadata = {
        "created": email.created,
        "folder": email.folder,
        "from_name": email.sender_name,
        "from_email": email.sender_email,
    }
    return metadata

def init_redis(cfg: Dict):
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

    # check if the host is localhost or 127.0.0.1
    use_ssl = not (redis_host == "localhost" or redis_host == "127.0.0.1")

    redisConnection = Redis(host=redis_host, port=redis_port, db=redis_db, username=username, password=password, retry_on_timeout=True, socket_keepalive=True, socket_connect_timeout=15, decode_responses=True, ssl=use_ssl)
    if redisConnection.ping():
        logging.info(f"Connected to Redis at {redis_host}:{redis_port}/{redis_db}")
    else:
        logging.error(f"Could not connect to Redis at {redis_host}:{redis_port}/{redis_db} username: {username}, password: {password}")   
        raise ValueError(f"Could not connect to Redis at {redis_host}:{redis_port}/{redis_db}")
    return redisConnection

def create_embedding(cfg:Dict):
    # create an embedding from a message id
    db_service = CouchDBService(cfg)
    embedding_service = EmbeddingService(cfg)
    pc_service = PineconeService(cfg, dimension=embedding_service.model.config.hidden_size)

    r = init_redis(cfg)

    while True:
        try:
            # move from queue to processing queue
            task = r.brpop(REDIS_QUEUE, timeout=15)
            if task:
                try:
                    task_data = json.loads(task[1])
                    message_id = task_data.get("message_id")
                    address = task_data.get("address")
                    retry_count = task_data.get("retry_count", 0)

                    if message_id is None or address is None:
                        raise ValueError("Message ID or address is missing")

                    message, email = db_service.get_message_by_id(message_id, address)
                    if email is None:
                        raise ValueError(f"Email not found for message_id: {message_id}, address: {address}")

                    metadata = create_metadata(email)
                    vector = embedding_service.create_embedding(email)

                    # remove from metadata all fields with None 
                    metadata = {k: v for k, v in metadata.items() if v is not None}
                    pc_service.upsert(address, message_id, vector.tolist(), metadata)

                    # after successfull upsert, update the message with flag: search: true
                    message["search"] = True
                    db_service.put_message(message, address)
                    logging.info(f"Successfully upserted embedding for message_id: {message_id}, address: {address}")
                except Exception as e:
                    logging.error(f"Error processing message_id: {message_id}, address: {address}, error: {e}")
                    # if error, requeue the message
                    if retry_count >= MAX_RETRIES:
                        logging.error(f"Max retries reached for message_id: {message_id}, address: {address}")
                    else:
                        task_data["retry_count"] = retry_count + 1
                        time.sleep(RETRY_DELAY)
                        r.rpush(REDIS_QUEUE, json.dumps(task_data))
                        logging.info(f"Requeued message_id: {message_id}, address: {address}")
        except ConnectionError as e:
            logging.error(f"Redis connection error: {e}... retrying in 3 seconds")
            # Print full error details
            logging.error(traceback.format_exc()) 

            time.sleep(3)
            r = init_redis(cfg)
        except Exception as e:
            logging.error(f"error in processing queue {e}")
            raise e

class EmbeddingTaskQueue:
    def __init__(self, cfg: Dict, dimension: int = 1024):
        self.redis_conn = init_redis(cfg)
        self.dimension = dimension
        self.cfg = cfg

    def upsert_embedding(self, address, message_id):
        """
        Upsert an embedding to the queue
        """
        payload = {
            "address": address,
            "message_id": message_id,
            "retry_count": 0   
        }
        p = json.dumps(payload)
        self.redis_conn.rpush(REDIS_QUEUE, p)
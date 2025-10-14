import logging
from config import get_config
from api.services.couchdb_service import CouchDBService
from api.services.pinecone_service import PineconeService
from api.services.embedding_service import EmbeddingService
from logging_handler import configure_logging
from datetime import datetime, timedelta, UTC
from api.services.embedding_task_queue import create_metadata
from tools.optimal_embeddings_model.data_types.email import Email
from typing import Tuple, List
import time

# Initialize config
cfg = get_config()
couchdb_service = CouchDBService(cfg)
pinecone_service = PineconeService(cfg)
embedding_service = EmbeddingService(cfg)

# Initialize logging on import
configure_logging(cfg)

# Module-scoped logger
logger = logging.getLogger(__name__)

def list_subscribers():
    """
    List all subscribers
    """
    subs = couchdb_service.get_all_subscribed_users()
    logger.info("Fetched %d subscribed users", len(subs))
    return subs

def list_latest_emails(address: str) -> Tuple[List[dict], List[Email]]:
    """
    List the latest emails for a subscriber (that have search=False, undefined or empty)
    Args:
        address: str: The address of the subscriber
    Returns:
        Tuple[List[dict], List[Email]]: messages = raw docs for update later, Email specific objects for embedding
    """
    # --- Compute epoch for 3 months ago ---
    three_months_ago = datetime.now(UTC) - timedelta(days=90)
    epoch_ms = int(three_months_ago.timestamp() * 1000)

    messages, latest_emails = couchdb_service.get_latest_emails(address, epoch_ms)
    logger.info("address=%s latest_emails=%d since=%s", address, len(latest_emails), three_months_ago.isoformat())
    return messages, latest_emails


def sync_embeddings():
    """
    Sync embeddings from couchdb to pinecone
    """
    logger.info("Starting embeddings sync run")
    try:
        subscribers = list_subscribers()
    except Exception as e:
        logger.exception("Failed to list subscribers: %s", e)
        return

    processed_total = 0
    for address in subscribers:
        logger.info("Processing subscriber address=%s", address)
        try:
            couchdb_service.ensure_indexes(address)
            messages, latest_emails = list_latest_emails(address)
            for message, email in zip(messages, latest_emails):
                try:
                    # # Embed + upsert into Pinecone
                    message_id = email.message_id
                    metadata = create_metadata(email)
                    vector = embedding_service.create_embedding(email)

                    # remove from metadata all fields with None 
                    metadata = {k: v for k, v in metadata.items() if v is not None}
                    pinecone_service.upsert(address, message_id, vector[0].tolist(), metadata)

                    # after successfull upsert, update the message with flag: search: true
                    message["search"] = True
                    couchdb_service.put_message(message, address)
                    processed_total += 1
                    logger.debug("upserted message_id=%s rev=%s", getattr(email, "message_id", None), getattr(email, "_rev", None))
                except Exception as e:
                    logger.exception("address=%s message_id=%s embed/upsert failed: %s", address, getattr(email, "message_id", None), e)
        except Exception as e:
            logger.exception("address=%s failed during ensure_indexes/get_latest_emails: %s", address, e)

    logger.info("Embeddings sync finished: processed_total=%d", processed_total)
    time.sleep(2) # sleep for 2 seconds to flush the logs

if __name__ == "__main__":
    logger.info("__main__ invoked for index sync")
    sync_embeddings()
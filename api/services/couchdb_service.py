from ibmcloudant.cloudant_v1 import CloudantV1, BulkGetQueryDocument
from ibm_cloud_sdk_core.authenticators import BasicAuthenticator
from ibm_cloud_sdk_core.api_exception import ApiException
from typing import Dict, List, Tuple
import binascii
from ..models.errors import NotFoundError, UnauthorizedError, InvalidUsageError
from logging_handler import use_logginghandler
from tools.optimal_embeddings_model.data_types.email import Email, MessageType
from tools.optimal_embeddings_model.mailio_ai_libs.collect_emails import extract_message_type, extract_html, extract_text, extract_subject, extract_sender, extract_folder, extract_message_id, extract_created, message_to_sentences
import threading
import traceback
import urllib.parse
import time

logger = use_logginghandler()

class CouchDBService:
    """
    A service for interacting with CouchDB
    The closest I could find for docs: https://ibm.github.io/cloudant-python-sdk/docs/0.7.0/apidocs/ibmcloudant/ibmcloudant.cloudant_v1.html
    DetailedResponse object: https://github.com/IBM/python-sdk-core/blob/db16465c0451828c431bf5e22b1c59e63285bcf4/ibm_cloud_sdk_core/detailed_response.py#L23
    """
    
    def __init__(self, cfg: dict):
        """
        Initialize the CouchDB service
        Args:
            cfg: dict: The configuration for the CouchDB service
        """
        couch_cfg:Dict = cfg.get("couchdb")
        if couch_cfg is None:
            raise ValueError("CouchDB configuration is missing")
        if couch_cfg.get("host") is None:
            raise ValueError("CouchDB host is missing")
        if couch_cfg.get("username") is None:
            raise ValueError("CouchDB user is missing")
        if couch_cfg.get("password") is None:
            raise ValueError("CouchDB password is missing")

        auth = BasicAuthenticator(couch_cfg.get("username"), couch_cfg.get("password"))
        client = CloudantV1(authenticator=auth)
        client.set_service_url(couch_cfg.get("host"))
        self.client = client

    def get_db(self, db_name:str):
        """
        Get a CouchDB database
        Args:
            db_name: str: The name of the database to get
        Returns:
            dict: The database information
        """
        db = self.client.get_database_information(db=db_name)
        return db

    def message_to_email(self, doc:dict, skip_non_smtp: bool = False) -> Email:
        """
        Convert a message to an Email object. It also clears up the HTML tags 
        and chunks the email body into paragraphs suitable for ML processing (embeddings)
        Args:
            message: dict: The message to convert
        Returns:
            Email: The Email object
        """
        msg_type = extract_message_type(doc)

        # list only SMTP emails
        if msg_type is None or msg_type != "application/mailio-smtp+json":
            if skip_non_smtp:
                return None
            folder = extract_folder(doc)
            message_id = extract_message_id(doc)
            created = extract_created(doc)
            return Email(message_type=MessageType.TEXT, sentences=[], subject=None, sender_name=None, sender_email=None, message_id=message_id, folder=folder, created=created)
            # raise UnsupportedMessageTypeError("Unsupported message type: " + str(msg_type))

        message = extract_html(doc)
        message_type = MessageType.HTML
        if message is None:
            message = extract_text(doc)
            message_type = MessageType.TEXT
        
        subject = extract_subject(doc)
        s_name, s_email = extract_sender(doc)
        folder = extract_folder(doc)
        message_id = extract_message_id(doc)
        if isinstance(subject, list):
            subject = ".".join(filter(lambda s: s.strip(), subject))
        if isinstance(message_id, list):
            raise ValueError("Message ID is a list")
        created = extract_created(doc)
        sentences = message_to_sentences(message_type, message)
        email = Email(message_type=message_type, sentences=sentences, subject=subject, sender_name=s_name, sender_email=s_email, message_id=message_id, folder=folder, created=created)
        return email
        

    def address_to_db_name(self, address:str) -> str:
        """
        Convert an address to a database name
        Args:
            address: str: The address to convert
        Returns:
            str: The database name
        """
        return "userdb-" + binascii.hexlify(address.encode()).decode()

    def get_raw_message_by_id(self, _id:str, address:str) -> Dict:
        """
        Get a raw message by its ID
        Args:
            _id: str: The ID of the message to get
            address: str: The address of the user
        Returns:
            dict: The message
        """
        if not _id or not address:
            raise ValueError("Invalid message ID or address")
        
        try:
            db_name = self.address_to_db_name(address)
            escaped_id = _id.replace("+", " ") # i don't know what exactly couchdb does with the id, but it's better to escape it
            message = self.client.get_document(db_name, escaped_id).get_result()
            return message
        except ApiException as e:
            if e.status_code == 404:
                raise NotFoundError(address)
            if e.status_code == 401 or e.status_code == 403:
                raise UnauthorizedError()
                
            raise InvalidUsageError()
        except Exception as e:
            # print stack trace
            logger.error(f"Error getting message by ID: {_id}, address: {address}, error: {e}")    
            traceback.print_exc()
            raise e
    
    def get_message_by_id(self, _id:str, address:str) -> Email:
        """
        Get a message by its ID
        Args:
            _id: str: The ID of the message to get
        Returns:
            dict: The message
        """
        if not _id or not address:
            raise ValueError("Invalid message ID or address")
        
        try:
            db_name = self.address_to_db_name(address)
            escaped_id = _id.replace("+", " ") # i don't know what exactly couchdb does with the id, but it's better to escape it
            message = self.client.get_document(db_name, escaped_id).get_result()
            email = self.message_to_email(message)
            # returns original message and email from database
            return message, email
        except ApiException as e:
            if e.status_code == 404:
                raise NotFoundError(address)
            if e.status_code == 401 or e.status_code == 403:
                raise UnauthorizedError()
                
            raise InvalidUsageError()
        except Exception as e:
            # print stack trace
            logger.error(f"Error getting message by ID: {_id}, address: {address}, error: {e}")    
            traceback.print_exc()
            raise e

    def put_message(self, message:Dict, address:str) -> Dict:
        """
        Put a document into the database
        Args:
            message: dict: The message to put
        Returns:
            dict: The response from the database
        """
        if not message or not address:
            raise ValueError("Invalid message or address")
        
        try:
            db_name = self.address_to_db_name(address)
            response = self.client.put_document(db=db_name, doc_id=message.get("_id"), document=message).get_result()
            return response
        except ApiException as e:
            if e.status_code == 401 or e.status_code == 403:
                raise UnauthorizedError()
            raise e

    def get_bulk_by_id(self, address:str, ids:List[str]) -> Tuple[List[Email], List[str]]:
        """
        Get a list of messages by their IDs
        Args:
            ids: List[str]: The IDs of the messages to get
        Returns:
            List[dict]: The messages
        """
        if len(ids) == 0:
            return []
        
        messages = []
        doc_ids = []
        for _id in ids:
            escaped_id = _id.replace("+", " ") # i don't know what exactly couchdb does but i know it doesn't like + in there
            doc = BulkGetQueryDocument(id=escaped_id)
            doc_ids.append(doc)
        
        missing: List[str] = []
        try:
            db_name = self.address_to_db_name(address)
            bulk_get_results = self.client.post_bulk_get(db=db_name, docs=doc_ids, latest=True, revs=False).get_result()
            for result in bulk_get_results.get("results", []):
                got_ok = False
                for entry in result.get("docs", []):
                    ok_doc = entry.get("ok")
                    if ok_doc and not ok_doc.get("_deleted", False):
                        email = self.message_to_email(ok_doc)
                        if email is not None:
                            messages.append(email)
                            got_ok = True
                            break
                if not got_ok:
                    missing.append(result.get("id"))
        except ApiException as e:
            if e.status_code == 404:
                raise NotFoundError(address)
            if e.status_code == 401 or e.status_code == 403:
                raise UnauthorizedError()
            raise e

        return messages, missing

    def get_all_subscribed_users(self) -> List[str]:
        """
        Get all subscribed users
        """
        response = self.client.post_all_docs(
            db='subscription',
            include_docs=True,
            limit=100
        ).get_result()

        users = []
        for row in response.get("rows", []):
            doc = row.get("doc")
            if doc.get("stripeSubscriptionPlan") is not None:
                users.append(doc.get("address"))
        return users

    def get_latest_emails(self, address: str, from_epoch_ms: int) -> Tuple[List[dict], List[Email]]:
        """
        Get the latest emails for a user
        Args:
            address: str: The address of the user
            from_epoch_ms: int: The epoch time to get emails from
        Returns:
            Tuple[List[dict], List[Email]]: messages = raw docs for update later, Email specific objects for embedding
        """
        FIXED_FOLDERS = ["inbox", "sent", "archive", "goodreads"]
        selector = {
        "$and": [
            {"folder": {"$in": FIXED_FOLDERS}},
            {
                "$or": [
                    {"search": {"$exists": False}},
                    {"search": {"$eq": ""}},
                        {"search": {"$eq": None}},
                    ]
                },
                {"created": {"$gte": from_epoch_ms}},
            ]
        }
        db_name = self.address_to_db_name(address)
        latest_emails = []
        messages = []
        bookmark = None
        page = 0
        while True:
            response = self.client.post_find(
                db=db_name,
                selector=selector,
                limit=100,
                bookmark=bookmark,
                use_index=["ddoc_search_emb_indices", "idx_folder_created_pfs"]
            ).get_result()
            docs = response.get("docs", [])
            if not docs:
                break
            
            # Filter out None emails and keep corresponding messages
            filtered_messages = []
            filtered_emails = []
            for doc in docs:
                email = self.message_to_email(doc, skip_non_smtp=True)
                if email is not None:
                    filtered_messages.append(doc)
                    filtered_emails.append(email)
            
            messages.extend(filtered_messages)
            latest_emails.extend(filtered_emails)
            bookmark = response.get("bookmark")
            if not bookmark:
                break
            page += 1

        return messages, latest_emails

    def ensure_indexes(self, address: str = None) -> bool:
        """
        Ensure indexes are created
        Returns:
            bool: True if indexes are created, False otherwise
        """
        if not address:
            raise ValueError("Address is required")

        INDEX_NAME = "idx_folder_created_pfs"
        
        # create index for created field
        db_name = self.address_to_db_name(address)
        desired_fields = [{"folder": "asc"}, {"created": "asc"}]
        idxs = self.client.get_indexes_information(db=db_name).get_result().get("indexes", [])
        for idx in idxs:
            if idx.get("type") != "json":
                continue
            if idx.get("name") == INDEX_NAME and idx.get("def", {}).get("fields") == desired_fields:
                # already good
                return True
        
        # create index
        try:
            FIXED_FOLDERS = ["inbox", "sent", "archive", "goodreads"]
            pfs_selector = {"folder": {"$in": FIXED_FOLDERS}}
            self.client.post_index(
                db=db_name,
                ddoc="ddoc_search_emb_indices",     # stable design doc name
                name=INDEX_NAME,
                type="json",
                index={"fields": desired_fields, "partial_filter_selector": pfs_selector},
            )
            return True
        except ApiException as e:
            if e.status_code == 400:
                logger.error(f"Error creating index: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return False
            if e.status_code == 401 or e.status_code == 403:
                logger.error(f"Unauthorized error creating index: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return False
            logger.error(f"Error creating index: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating index: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
from ibmcloudant.cloudant_v1 import CloudantV1, BulkGetQueryDocument
from ibm_cloud_sdk_core.authenticators import BasicAuthenticator
from ibm_cloud_sdk_core.api_exception import ApiException
from typing import Dict, List
import binascii
from ..models.errors import UnsupportedMessageTypeError, NotFoundError, UnauthorizedError
from logging_handler import use_logginghandler
from tools.optimal_embeddings_model.data_types.email import Email, MessageType
from tools.optimal_embeddings_model.mailio_ai_libs.collect_emails import extract_message_type, extract_html, extract_text, extract_subject, extract_sender, extract_folder, extract_message_id, extract_created, message_to_sentences

# logger = use_logginghandler()

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
        client.set_disable_ssl_verification(True)
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

    def message_to_email(self, doc:dict) -> Email:
        """
        Convert a message to an Email object. It also clears up the HTML tags 
        and chunks the email body into paragraphs suitable for ML processing (embeddings)
        Args:
            message: dict: The message to convert
        Returns:
            Email: The Email object
        """
        msg_type = extract_message_type(doc)

        # skip encrypted emails, list only SMTP emails
        if msg_type is None or msg_type != "application/mailio-smtp+json":
            raise UnsupportedMessageTypeError("Unsupported message type: " + str(msg_type))

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
            message = self.client.get_document(db_name, _id).get_result()
            email = self.message_to_email(message)
            return email
        except ApiException as e:
            if e.status_code == 404:
                raise NotFoundError
            if e.status_code == 401 or e.status_code == 403:
                raise UnauthorizedError
                
            raise InvalidUsageError

    def get_bulk_by_id(self, address:str, ids:List[str]) -> List[Email]:
        """
        Get a list of messages by their IDs
        Args:
            ids: List[str]: The IDs of the messages to get
        Returns:
            List[dict]: The messages
        """
        if not ids:
            raise ValueError("Invalid message IDs")
        
        messages = []
        doc_ids = []
        for _id in ids:
            if not _id:
                continue
            doc = BulkGetQueryDocument(id=_id)
            doc_ids.append(doc)
        
        try:
            db_name = self.address_to_db_name(address)
            bulk_get_results = self.client.post_bulk_get(db=db_name, docs=doc_ids).get_result()
            for r in bulk_get_results["results"]:
                if "error" in r:
                    continue
                message = r["docs"][0]
                if "ok" in message:
                    message = message["ok"]
                email = self.message_to_email(message)
                messages.append(email)
        except ApiException as e:
            if e.status_code == 404:
                raise NotFoundError
            if e.status_code == 401 or e.status_code == 403:
                raise UnauthorizedError
            raise e
            # try:
            #     message = self.client.get_document(_id).get_result()
            #     email = self.message_to_email(message)
            #     messages.append(email)
            # except ApiException as e:
            #     if e.status_code == 404:
            #         continue
            #     if e.status_code == 401 or e.status_code == 403:
            #         raise UnauthorizedError
                
            #     raise InvalidUsageError

        return messages


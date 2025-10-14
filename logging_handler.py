import logging
import json
import sys
import os
try:
    from google.cloud import logging as gcloud_logging
    from google.cloud.logging_v2.handlers import CloudLoggingHandler
    _GCP_LOGGING_AVAILABLE = True
except Exception:
    _GCP_LOGGING_AVAILABLE = False
from google.oauth2 import service_account

logger = None

def use_logginghandler():
    global logger
    if logger is not None:
        return logger
        
    l = logging.getLogger()
    l.setLevel("INFO")
    handler = logging.StreamHandler(sys.stdout)
    l.addHandler(handler)
    logger = l
    return logger
    

def configure_logging(cfg: dict):
    """Configure logging for local and GCP Cloud Logging.

    If the Google Cloud Logging client is available and credentials/project are present,
    attach a CloudLoggingHandler to the root logger. Otherwise, fall back to a standard
    StreamHandler to stdout with a useful format.
    """
    root = logging.getLogger()
    # Avoid duplicate handlers on reloads
    if getattr(configure_logging, "_configured", False):
        return

    root.setLevel(logging.INFO)

    if _GCP_LOGGING_AVAILABLE:
        try:
            project_id = cfg.get("logging", {}).get("projectId")
            credentials_path = cfg.get("logging", {}).get("loggingCredentialsPath")
            logging_id = cfg.get("logging", {}).get("loggingId")

            creds = None
            if credentials_path:
                try:
                    creds = service_account.Credentials.from_service_account_file(credentials_path)
                    root.info(f"Using explicit credentials from {credentials_path}")
                except Exception as e:
                    root.warning(f"Failed to load credentials file {credentials_path}: {e}")

            client = gcloud_logging.Client(project=project_id, credentials=creds)
            handler = CloudLoggingHandler(client, name=logging_id)
            # Remove pre-existing default handlers to avoid duplicate logs
            for h in list(root.handlers):
                root.removeHandler(h)
            root.addHandler(handler)
            configure_logging._configured = True
            root.info("Cloud Logging handler attached (google-cloud-logging)")
            return
        except Exception as e:
            # Fall back to stdout
            pass

    # Fallback: structured-ish stdout logging
    stream = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s index_sync_embeddings %(process)d:%(threadName)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    stream.setFormatter(formatter)
    # Remove pre-existing default handlers to avoid duplicate logs
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(stream)
    configure_logging._configured = True
    root.info("Stdout logging configured (fallback)")
# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/import_to_pinecone.ipynb.

# %% auto 0
__all__ = ['project_root', 'DEFAULT_FOLDERS', 'load_config', 'connect_pinecone', 'get_db_name', 'connect_couchdb',
           'load_embedder', 'import_to_pinecode', 'main']

# %% ../nbs/import_to_pinecone.ipynb 1
import yaml
from typing import Dict
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec
from tqdm.auto import tqdm
import binascii
from ibmcloudant.cloudant_v1 import CloudantV1
from ibm_cloud_sdk_core.authenticators import BasicAuthenticator
import nltk
import os
import sys
from transformers import AutoTokenizer, AutoModel
import torch.nn.functional as F
import torch
import numpy as np
import argparse

project_root = os.path.abspath(os.path.join(os.getcwd(), '..'))
sys.path.append(project_root)

from tools.optimal_embeddings_model.mailio_ai_libs.collect_emails import list_emails
from tools.optimal_embeddings_model.mailio_ai_libs.create_embeddings import Embedder

# %% ../nbs/import_to_pinecone.ipynb 3
def load_config(path:str) -> Dict:
    with open(path, 'r') as f:
        config = yaml.safe_load(f)
    return config

# %% ../nbs/import_to_pinecone.ipynb 4
def connect_pinecone(cfg:Dict) -> Pinecone:
    pinecone_cfg = cfg.get("pinecone")
    pc = Pinecone(api_key=pinecone_cfg.get("api_key"))
    spec = ServerlessSpec(cloud=pinecone_cfg.get("cloud"), region=pinecone_cfg.get("region"))
    index = pc.Index(host=pinecone_cfg.get("index_name"))
    return index

# %% ../nbs/import_to_pinecone.ipynb 5
def get_db_name(address:str) -> str:
    return "userdb-" + binascii.hexlify(address.encode()).decode() 

def connect_couchdb(cfg:Dict) -> CloudantV1:
    couch_cfg = cfg.get("couchdb")
    auth = BasicAuthenticator(couch_cfg.get("username"), couch_cfg.get("password"))
    client = CloudantV1(authenticator=auth)
    client.set_service_url(couch_cfg.get("host"))
    client.set_disable_ssl_verification(True)
    return client

# %% ../nbs/import_to_pinecone.ipynb 6
# load transformers model
def load_embedder(cfg: Dict) -> Embedder:
    model_id = cfg.get("ai").get("embedding_model")
    print(f"Loading model {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id)

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"device: {device}")
    model.to(device)

    embedder = Embedder(model, tokenizer)
    return embedder

# %% ../nbs/import_to_pinecone.ipynb 7
# default folders for import
DEFAULT_FOLDERS = ["archive", "sent"]

def import_to_pinecode(client, index, embedder:Embedder, user_db: str, address:str, folders: str, batch_size:int = 500):
    """
    Import emails from couchdb to pinecone index
    Args:
        client: CloudantV1 client
        embedder: Embedder object
        user_db: user db name
        folders: list of folders to import
        batch_size: batch size for import
    Results:
        None
    """
    processed = 0

    for folder in folders:
        bookmark = ""
        while True:
            for emails, new_bookmark in list_emails(client, user_db, folder, bookmark=bookmark, limit=batch_size):
                if len(emails) == 0:
                    bookmark = None
                    break
                
                # prepare data for import
                vectors = []
                for e in tqdm(emails, desc=f"Importing {folder}", unit="email"):
                    sentences = []
                    if e.subject:
                        sentences.append(e.subject)
                    sentences.extend(e.sentences)

                    metadata = {
                        "created": e.created,
                        "from": e.sender_email,
                        "from_name": e.sender_name,
                        "folder": e.folder,
                    }
                    text = " ".join(sentences)

                    if not text.strip():
                        print(f"Empty email {e.message_id}, subject: {e.subject}, text: {text}, from: {e.sender_email}")    
                        continue

                    embedding = embedder.embed(text)

                    vector = {
                        "id": e.message_id,
                        "values": embedding[0].tolist(),
                        "metadata": metadata,
                    }
                    vectors.append(vector)
                    processed += 1
                
                # upsert to pinecone
                index.upsert(vectors=vectors, namespace=address)

                bookmark = new_bookmark
            if not bookmark:
                break

    print(f"Processed {processed} emails")


# %% ../nbs/import_to_pinecone.ipynb 8
def main(address:str):
    cfg = load_config('../config.yaml')
    client = connect_couchdb(cfg)
    index = connect_pinecone(cfg)
    embedder = load_embedder(cfg)
    user_db = get_db_name(address)
    import_to_pinecode(client, index, embedder, user_db, address, DEFAULT_FOLDERS)

# %% ../nbs/import_to_pinecone.ipynb 12
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the main function with an address argument.")
    parser.add_argument("address", type=str, help="The address to process")
    args = parser.parse_args()
    address = args.address
    if not address:
        print("Please provide an address")
        sys.exit(1)
    main(address)

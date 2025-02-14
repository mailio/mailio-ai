from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec
from typing import Dict, List
from pinecone.data.index import QueryResponse
import threading
from urllib.parse import urlparse

class PineconeService:

    def __init__(self, cfg: Dict, dimension: int = 1024, metric: str = 'cosine'):
        """
        Initialize the Pinecone service
        Args:
            cfg: dict: The configuration for the Pinecone service
        """
        pinecone_cfg: Dict = cfg.get("pinecone")
        if pinecone_cfg is None:
            raise ValueError("Pinecone configuration is missing")
        if pinecone_cfg.get("api_key") is None:
            raise ValueError("Pinecone API key is missing")
        if pinecone_cfg.get("index_name") is None:
            raise ValueError("Pinecone index name is missing")
        if pinecone_cfg.get("region") is None:
            raise ValueError("Pinecone region is missing")
        if pinecone_cfg.get("cloud") is None:
            raise ValueError("Pinecone cloud is missing")
        
        self.dimension = dimension
        self.region = pinecone_cfg.get("region")
        self.cloud = pinecone_cfg.get("cloud")

        # get index name from the host url and remove the -index suffix
        name = pinecone_cfg.get("index_name")
        parsed_url = urlparse(name)
        name = parsed_url.netloc
        name = name.split(".")[0]
        parts = name.rsplit("-", 1) 
        name = parts[0]
        self.index_name = name

        self.pc = Pinecone(api_key=pinecone_cfg.get("api_key"))
        spec = ServerlessSpec(cloud=self.cloud, region=self.region)

        existing_indexes = [
            index_info["name"] for index_info in self.pc.list_indexes()
        ]
        if self.index_name not in existing_indexes:
            # if does not exist, create index
            self.pc.create_index(
                self.index_name,
                dimension=dimension,  # dimensionality of minilm
                metric='cosine',
                spec=spec
            )
            # wait for index to be initialized
            while not self.pc.describe_index(self.index_name).status['ready']:
                time.sleep(1)
            
            # connect to index
        self.index = self.pc.Index(self.index_name)

    
    def index_stats(self):
        stats = index.describe_index_stats()
        return stats

    def upsert(self, address:str, embedding_id: str, vector: List[float], metadata: Dict):
        """
        Upsert the embeddings to the Pinecone index
        """
        vectors = []
        vectors.append({
            "id": embedding_id,
            "values": vector,
            "metadata": metadata
        })
        self.index.upsert(vectors, namespace=address)

    def query(self, address:str, query_embedding: List[float], top_k: int = 50, folder:str = None, beforeTimestamp: int = None, afterTimestamp: int = None, from_email: str = None) -> QueryResponse:
        """
        Query the Pinecone index
        Args:
            address: str: The address to query (namespace)
            query_embedding: List[float]: The query vector
            top_k: int: The number of results to return
            folder: str: The folder to search
            beforeTimestamp: int: The timestamp to search before
            afterTimestamp: int: The timestamp to search after
            from_email: str: The email to search from
        Returns:
            dict: The query results
        """
        query_filter = {}
        if afterTimestamp and beforeTimestamp:
            query_filter["created"] = {"$and": [ 
                { "created" : {"$gte": afterTimestamp}},
                { "created" : {"$lte": beforeTimestamp}}
            ]}
        if afterTimestamp and not beforeTimestamp:
            query_filter["created"] = {"$lte": beforeTimestamp}
        
        if beforeTimestamp and not afterTimestamp:
            query_filter["created"] = {"$gte": afterTimestamp}
        
        if from_email:
            query_filter["from_email"] = {"sender_email": { "$eq": from_email}}
        
        if folder:
            query_filter["folder"] = {"folder": {"$eq": folder}}

        if len(query_filter) == 0:
            query_filter = None

        results = self.index.query(vector=query_embedding, filter=query_filter, top_k=top_k, namespace=address, include_metadata=True)

        return results

    def delete(self, message_id:str, address:str):
        """
        Delete the embeddings from the Pinecone index
        Args:
            message_id: str: The message ID to delete
        """
        self.index.delete(message_id, namespace=address)
        


from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec
from typing import Dict, List
from pinecone.db_data.models import QueryResponse
from urllib.parse import urlparse
import time
from ..models.llm import LLMQueryWithDocuments, EmailDocument
from loguru import logger

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
        query_filter["$and"] = []
        if afterTimestamp and beforeTimestamp:
            query_filter["$and"].append({"created": {"$gte": afterTimestamp, "$lte": beforeTimestamp}})

        if afterTimestamp and not beforeTimestamp:
            query_filter["$and"].append({"created": {"$gte": afterTimestamp}})
        
        if beforeTimestamp and not afterTimestamp:
            query_filter["$and"].append({"created": {"$lte": beforeTimestamp}})
        
        if from_email:
            query_filter["$and"].append({"from_email": {"$in": [from_email]}})
        
        if folder:
            query_filter["$and"].append({"folder": {"$eq": folder}})

        if len(query_filter["$and"]) == 0:
            query_filter = None

        logger.debug(f"query_filter: {query_filter}")

        results = self.index.query(vector=query_embedding, filter=query_filter, top_k=top_k, namespace=address, include_metadata=True)

        return results

    def delete(self, message_id:str, address:str):
        """
        Delete the embeddings from the Pinecone index
        Args:
            message_id: str: The message ID to delete
        """
        self.index.delete(message_id, namespace=address)

    def delete_by_ids(self, message_ids: List[str], address: str):
        """
        Delete the embeddings from the Pinecone index by message IDs
        """
        self.index.delete(ids=message_ids, namespace=address)

    def rerank(self, query: str, documents: List[EmailDocument]):
        """
        Rerank the documents based on the query
        """
        start_time = time.time()
        pinecone_docs = []
        for document in documents:
            pinecone_docs.append({
                "id": document.id,
                "text": document.text
            })
        result = self.pc.inference.rerank(
            model="bge-reranker-v2-m3",
            query=query,
            documents=pinecone_docs,
            top_n=len(documents),
            parameters={
                "truncate": "END"
            },
            return_documents=False
        )
        reranked_results = []
        reranked = result.rerank_result
        data = reranked.data
        for item in data:
            _id = documents[item.index].id
            reranked_results.append({
                "id": _id,
                "score": item.score
            })
        end_time = time.time()
        print(f"Reranking took {end_time - start_time} seconds")
        return {"results": reranked_results}
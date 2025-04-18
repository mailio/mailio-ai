# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_chunking.ipynb.

# %% auto 0
__all__ = ['project_root', 'CustomEmbeddings', 'Chunker']

# %% ../nbs/02_chunking.ipynb 1
from langchain_text_splitters import TokenTextSplitter, SentenceTransformersTokenTextSplitter
from transformers import PreTrainedModel, PreTrainedTokenizer
from langchain_core.embeddings import Embeddings
from transformers import AutoTokenizer, AutoModel
import os
import sys
import json
from typing import List

project_root = os.path.abspath(os.path.join(os.getcwd(), '../../..'))
sys.path.append(project_root)

from tools.optimal_embeddings_model.data_types.email import Email, MessageType

# %% ../nbs/02_chunking.ipynb 2
class CustomEmbeddings:
    """Embed search docs.

    Args:
        texts: List of text to embed.

    Returns:
        List of embeddings.
    """
    def __init__(self, model: PreTrainedModel, tokenizer: PreTrainedTokenizer):
        self.model = model
        self.tokenizer = tokenizer
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.model.encode(text).tolist() for text in texts]
        

# %% ../nbs/02_chunking.ipynb 3
# create a chunker object
class Chunker:
    def __init__(self, tokenizer: PreTrainedTokenizer, chunk_size:int=250, chunk_overlap:int=0):
        # self.chunker = SemanticChunker(embeddings=custom_embeddings, breakpoint_threshold_type=threshold_type, breakpoint_threshold_amount=threshold_amount)
        # self.chunker = TokenTextSplitter.from_huggingface_tokenizer(tokenizer=tokenizer, chunk_size=chunk_size, chunk_overlap=chunk_overlap, keep_whitespace=True)
        self.chunker = SentenceTransformersTokenTextSplitter.from_huggingface_tokenizer(tokenizer=tokenizer, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    def chunk(self, text:str):
        chunks = self.chunker.split_text(text)
        return chunks



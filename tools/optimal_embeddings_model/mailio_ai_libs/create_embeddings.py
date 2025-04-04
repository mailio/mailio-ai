# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_create_embeddings.ipynb.

# %% auto 0
__all__ = ['project_root', 'Embedder']

# %% ../nbs/02_create_embeddings.ipynb 1
from typing import List, Optional
import torch
from transformers import PreTrainedModel, PreTrainedTokenizer, BatchEncoding
from transformers import AutoTokenizer, AutoModel
from sentence_transformers.models import Pooling
import sys
import os
import json
import numpy as np
import time
from tqdm.auto import tqdm
import torch.nn.functional as F

# sys.path.append("..")  # Adds the parent directory to sys path
project_root = os.path.abspath(os.path.join(os.getcwd(), '../../..'))
sys.path.append(project_root)

from tools.optimal_embeddings_model.data_types.email import Email, MessageType
from tools.optimal_embeddings_model.mailio_ai_libs.chunking import Chunker

# from mailio_ai_libs.chunking import Chunker
# from data_types.email import Email, MessageType

# %% ../nbs/02_create_embeddings.ipynb 4
class Embedder:

    def __init__(self, model: PreTrainedModel, tokenizer: PreTrainedTokenizer):
        self.model = model
        self.model.eval()
        self.tokenizer = tokenizer
        self.max_length = self.model.config.max_position_embeddings  # Model-specific max lengt
        self.chunker = Chunker(tokenizer, chunk_size=self.max_length-2, chunk_overlap=0)

    def batch_embed(self, documents:List[List[str]]) -> np.ndarray:
        """
        Generate embeddings for a list of documents.
        """
        all_chunks = []          # To hold all text chunks for every document.
        doc_chunk_counts = []    # To record how many chunks each document produced.
        
        # Loop over each document (which is a list of strings).
        for doc in documents:
            # Join the list of strings into one text, and then chunk it.
            text = ". ".join(doc)
            chunks = self.chunker.chunk(text)
            doc_chunk_counts.append(len(chunks))
            all_chunks.extend(chunks)
        
        # Batch tokenize all chunks at once.
        inputs = self.tokenizer(all_chunks, padding=True, truncation=True, return_tensors="pt")
        inputs = inputs.to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Get embeddings for each chunk.
        chunk_embeddings = self.mean_pooling(outputs, inputs['attention_mask'])
        
        # Now, regroup the chunk embeddings back into document embeddings.
        doc_embeddings = []
        index = 0
        for count in doc_chunk_counts:
            # For each document, you can aggregate its chunk embeddings (here we take the mean).
            doc_emb = chunk_embeddings[index:index+count].mean(dim=0)
            doc_embeddings.append(doc_emb)
            index += count
    
        # Return the final document embeddings as a numpy array.
        return torch.stack(doc_embeddings).cpu().numpy()
    
    def embed(self, text:List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            text (List[str]): List of input texts.
            chunk_size (Optional[int]): If text is too long, split it into chunks of this size. If None, no chunking is done.
        
        Returns:
            numpy.ndarray: Embeddings for the input texts.
        """
        
        # Tokenize the input text
        chunks = self.chunker.chunk(".".join(text))
        embeddings = []

        input_texts = []
        for ch in chunks:
            input_texts.append(ch)
        
        inputs = self.tokenizer(input_texts, padding=True, truncation=True, return_tensors="pt")
        inputs = inputs.to(self.model.device)

        with torch.no_grad():
            # Forward pass
            outputs = self.model(**inputs)
        
        # Perform pooling.
        sentence_embeddings = self.mean_pooling(outputs, inputs['attention_mask'])

        # Convert to numpy array and return
        # Move tensors in the list to CPU and convert them to numpy arrays
        return sentence_embeddings.cpu().numpy()

        #Mean Pooling - Take attention mask into account for correct averaging
    def mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)



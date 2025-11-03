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

class Embedder:

    def __init__(self, model: PreTrainedModel, tokenizer: PreTrainedTokenizer):
        self.model = model
        self.model.eval()
        self.tokenizer = tokenizer
        self.max_length = self.model.config.max_position_embeddings  # Model-specific max lengt

    def batch_embed(self, documents:List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of documents.
        """
        
        # Batch tokenize all chunks at once.
        inputs = self.tokenizer(documents, max_length=self.max_length, padding=True, truncation=True, return_tensors="pt")
        inputs = inputs.to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Get embeddings for each chunk.
        embeddings = self.mean_pooling(outputs, inputs['attention_mask'])
        embeddings = F.normalize(embeddings, p=2, dim=1)
    
        # Return the final document embeddings as a numpy array.
        return embeddings.cpu().numpy()
    
    def embed(self, text:str) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            text (List[str]): List of input texts.
            chunk_size (Optional[int]): If text is too long, split it into chunks of this size. If None, no chunking is done.
        
        Returns:
            numpy.ndarray: Embeddings for the input texts.
        """
        
        # Tokenize the input text
        inputs = self.tokenizer(text, max_length=self.max_length, padding=True, truncation=True, return_tensors="pt")
        inputs = inputs.to(self.model.device)

        with torch.no_grad():
            # Forward pass
            outputs = self.model(**inputs)
        
        # Perform pooling.
        sentence_embeddings = self.mean_pooling(outputs, inputs['attention_mask'])
        sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)

        # Convert to numpy array and return
        # Move tensors in the list to CPU and convert them to numpy arrays
        return sentence_embeddings.cpu().numpy()[0]

        #Mean Pooling - Take attention mask into account for correct averaging
    def mean_pooling(self, model_output, attention_mask):
        last_hidden = model_output.last_hidden_state.masked_fill(~attention_mask[..., None].bool(), 0.0)
        return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]



from transformers import AutoTokenizer, AutoModel
from tools.optimal_embeddings_model.data_types.email import Email, MessageType
from tools.optimal_embeddings_model.mailio_ai_libs.create_embeddings import Embedder
import torch
from typing import List, Dict
import threading

class EmbeddingService:
    """
    Embedding service to get embeddings for the email
    """
    
    def __init__(self, cfg: dict):
        """
        Initialize the Embedding service
        Args:
            cfg: dict: The configuration for the Embedding service
        """
        if cfg.get("embedding_model") is None:
            raise ValueError("Embedding model is missing")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"EmbeddingService using device: {self.device}")
        self.embedding_model = cfg.get("embedding_model")
        self.tokenizer = AutoTokenizer.from_pretrained(self.embedding_model)
        self.model = AutoModel.from_pretrained(self.embedding_model)
        self.model.to(self.device)
        self.model.eval() # set to evaluation mode
        self.embedder = Embedder(self.model, self.tokenizer)    
    

    def create_passage_text(self, email: Email) -> str:
        """
        Create a passage text for the email
        Args:
            email: Email: The email to create passage text for
        
        Returns:
            str: The passage text for the email
        """
        text = ""
       
        # add subject
        text += "passage: "
        if email.subject:
            text += "Subject: " + email.subject

        # append content
        if len(email.sentences) > 0:
            sentences_text = "Body: " + ".".join(email.sentences)
            text += "\n" + sentences_text

        return text

    def create_batched_embedding(self, emails: List[Email]) -> torch.Tensor:
        """
        Create embeddings for the list of emails
        Args:
            emails: list[Email]: The list of emails to create embeddings for
        
        Returns:
            torch.Tensor: The embeddings for the list of emails
        """
        # prepare list of lists
        all_sentences = []
        for email in emails:
            sentences = self.create_sentence_list(email)
            all_sentences.append(sentences)

        embeddings = self.embedder.batch_embed(all_sentences)

        return embeddings

    def create_embedding(self, email:Email) -> torch.Tensor:
        """
        Create embeddings for the email
        Args:
            email: Email: The email to create embeddings for
        
        Returns:
            torch.Tensor: The embeddings for the email
        """
        text = self.create_passage_text(email)
        embeddings = self.embedder.embed(text)
        return embeddings
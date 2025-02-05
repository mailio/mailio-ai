from transformers import AutoTokenizer, AutoModel
from tools.optimal_embeddings_model.data_types.email import Email, MessageType
from tools.optimal_embeddings_model.mailio_ai_libs.create_embeddings import Embedder
import torch

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
        self.embedding_model = cfg.get("embedding_model")
        self.tokenizer = AutoTokenizer.from_pretrained(self.embedding_model)
        self.model = AutoModel.from_pretrained(self.embedding_model)
        self.model.to(self.device)
        self.model.eval() # set to evaluation mode
        self.embedder = Embedder(self.model, self.tokenizer)
        
    def create_embedding(self, email:Email) -> torch.Tensor:
        """
        Create embeddings for the email
        Args:
            email: Email: The email to create embeddings for
        
        Returns:
            torch.Tensor: The embeddings for the email
        """
        text = []
        # add subject
        if email.subject:
            text.append(email.subject)

        # append content
        if len(email.sentences) > 0:
            text.extend(email.sentences)

        embeddings = self.embedder.embed(text)
        return embeddings
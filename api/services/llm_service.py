from typing import Dict
from ..models.llm import LLMQueryWithDocuments, EmailDocument
from openai import OpenAI
from typing import List
import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from api.services.llm_service_prompt import selfquery_prompt, insights_prompt
import torch
import time
import os
from datetime import datetime
class LLMService:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        self.openai = OpenAI(api_key=cfg["openai"]["api_key"])
        self.model_name = cfg["openai"]["model"]
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

    def rerank_selfhosted(self, query: LLMQueryWithDocuments, documents: List[EmailDocument]):
        """
        Rerank the documents based on the query using a self-hosted model (BGE Reranker)
        Uncomment the code to use the self-hosted model
        """
        document_content = []  
        query_content = []
        for document in documents:
            document_content.append(document.text)
            query_content.append(query)

        # measure time taken to execute the following code
        start_time = time.time()

        features = self.tokenizer(
            query_content,
            document_content,
            padding=True,
            truncation=True,
            return_tensors="pt"
        )

        with torch.no_grad():
            scores = self.model(**features).logits
            scores = scores.tolist()
        
        end_time = time.time()
        print(f"Time taken to execute the reranking: {end_time - start_time} seconds")

        scores = [{"score": score[0], "id": document.id} for score, document in zip(scores, documents)]
        return {"results": scores}

            
    def extract_insights(self, queryWithDocuments: LLMQueryWithDocuments):
        email_content_json = [
            {
                "id": document.id,
                "text": document.text
            }
            for document in queryWithDocuments.documents
        ]
        prompt = insights_prompt.format(query=queryWithDocuments.query)

        start_time = time.time()

        response = self.openai.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(email_content_json)}
            ],
            response_format={"type": "json_object"}
        )

        end_time = time.time()
        print(f"Time taken to execute the insights extraction: {end_time - start_time} seconds")

        return response.choices[0].message.content

    def selfquery(self, query: str):
        today = datetime.now().strftime("%Y-%m-%d")
        formatted_prompt = selfquery_prompt.format(today=today)
        response = self.openai.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": formatted_prompt}, {"role": "user", "content": query}],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

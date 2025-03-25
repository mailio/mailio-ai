from typing import Dict
from ..models.llm import LLMQueryWithDocuments, EmailDocument
from openai import OpenAI
from typing import List
import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import time
import os

class LLMService:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        self.openai = OpenAI(api_key=cfg["openai"]["api_key"])
        self.model_name = cfg["openai"]["model"]
        os.environ["TOKENIZERS_PARALLELISM"] = "false"

        self.insight_prompt = """
            Check the list of emails and extract insights from them.
            Make sensible decision whether to include numbers section as described below based on the query and the content of the emails:  
            Query: {query}
            Return the insights in JSON format. Example:
            {{
                "query": "project updates",
                "results": [
                    {{
                        "id": "123",
                        "insight": {{
                            "status": "Server migration completed",
                            "outcome": "System running smoothly",
                            "action_needed": "None"
                        }},
                        "numbers": [
                            {{
                                "value": "$3.00",
                                "description": "Usage charges for 2025-02 in USD"
                            }},
                            {{
                                "value": "$3.00",
                                "description": "Amound paid for 2025-02 in USD"
                            }}
                        ],
                    }},
                    {{
                        "id": "456",
                        "insight": {{
                            "status": "Design approved by client",
                            "next_step": "Development starts next week",
                            "action_needed": "Prepare for development phase"
                        }},
                        "numbers": []
                    }}
                ]
            }}
            
        """
        self.cross_encoder_model_name = 'BAAI/bge-reranker-base'
        self.model = AutoModelForSequenceClassification.from_pretrained(self.cross_encoder_model_name, trust_remote_code=True)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = self.model.to(self.device)
        self.model.eval()
        print(f"Cross encoder model {self.cross_encoder_model_name} running on: {self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.cross_encoder_model_name, trust_remote_code=True)


    def rerank(self, query: LLMQueryWithDocuments, documents: List[EmailDocument]):

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
        prompt = self.insight_prompt.format(query=queryWithDocuments.query)
        print(prompt)

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

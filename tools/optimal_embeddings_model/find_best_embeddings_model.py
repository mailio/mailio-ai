from typing import List, Optional, Tuple, Dict, Set
import torch
from transformers import PreTrainedModel, PreTrainedTokenizer, BatchEncoding
from transformers import AutoTokenizer, AutoModel
from sentence_transformers.models import Pooling
import sys
import os
import gc
import json
import numpy as np
import time
import pandas as pd
from tqdm.auto import tqdm
import yaml
import logging
from dotenv import load_dotenv
import argparse

# mailio ai libs imports
from mailio_ai_libs.create_embeddings import Embedder
from data_types.email import Email
from mailio_ai_libs.semantic_search_evaluator import MailioInformationRetrievalEvaluator, SimilarityFunction

# load .env file
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")   

def load_config(config_path):
    """ 
    Load Yaml Configuration with the list of models and other settings.

    Args:
        config_path (str): Path to the YAML configuration file.
    """
    with open(config_path, "r") as file:
        CONFIG = yaml.safe_load(file)
    return CONFIG

def memory_cleanup(model:PreTrainedModel, tokenizer: PreTrainedTokenizer, embedder: Embedder):
    """
    cleanup the memory after each run
    """
    del model
    del tokenizer
    del embedder
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()  # MPS equivalent (PyTorch 2.0+)

def create_embeddings(embedder: Embedder, files:List, output_folder:str, force_embedding_creation:bool = False) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Create embeddings for the given sentences
    It will save the embeddings to a file to a datafolder with the model name
    Args:
        model: PreTrainedModel
        tokenizer: PreTrainedTokenizer
        embedder: Embedder
        files: List of jsonl files to read the data from
    Returns:
        np_emebddings: numpy array vstack of embeddings
        embeddings_index: numpy array of message_ids
        average_time: average time taken to embed a sentence
    """
    emebddings_filename = "embeddings"
    
    all_embeddings_index = []
    all_embeddings = []
    all_embeddings_timing = []

    # check if embeddings already exists
    if not force_embedding_creation:
        if os.path.exists(os.path.join(output_folder, f"{emebddings_filename}.npy")) and \
           os.path.exists(os.path.join(output_folder, f"{emebddings_filename}_index.npy")):
            with open(os.path.join(output_folder, f"{emebddings_filename}.npy"), 'rb') as f:
                np_emebddings = np.load(f)
            
            with open(os.path.join(output_folder, f"{emebddings_filename}_index.npy"), 'rb') as f:
                embeddings_index = np.load(f)
            
            return np_emebddings, embeddings_index, 0

    # create embeddings
    for file in files:
        with open(file, 'r') as f:
            jsonl = f.read()

        data = jsonl.split('\n')
        data = [json.loads(d) for d in data if d]
        for item in tqdm(data, desc="Creating embeddings for {}".format(file)):
            email = Email.from_dict(item)
            text = []
            if email.sender_name:
                text.append(f"sent from {email.sender_name}")
            if email.subject:
                text = [email.subject]
            if len(email.sentences) > 0:
                text.extend(email.sentences)
            
            if len(text) == 0: # nothing to embed
                continue
            
            start_time = time.time()
            embeddings = embedder.embed(text)
            elapsed_time = time.time() - start_time
            all_embeddings_timing.append(elapsed_time)

            # collect embeddings and associated index
            all_embeddings.extend(embeddings)
            all_embeddings_index.extend([email.message_id] * len(embeddings))

            assert len(all_embeddings_index) == len(all_embeddings)

    # stack embeddings
    np_emebddings = np.vstack(all_embeddings)
    embeddings_index = np.array(all_embeddings_index)

    # Save the embeddings to a file
    with open(os.path.join(output_folder, f"{emebddings_filename}.npy"), 'wb') as f:
        np.save(f, np_emebddings)

    with open(os.path.join(output_folder, f"{emebddings_filename}_index.npy"), 'wb') as f:
        np.save(f, embeddings_index)
  
    average_time = sum(all_embeddings_timing) / len(all_embeddings_timing)
    
    return np_emebddings, embeddings_index, average_time

def load_evaluation_dataset(embedder:Embedder, datasetpath:str, output_folder:str):
    """
    Load the evaluation dataset, create embeddings and save them to a file if they don't exist
    Args:
        datasetpath: Path to the dataset
        embedder: Embedder object
        output_folder: Output folder to save the embeddings
    Returns:
        embeddings: numpy array vstack of embeddings
    """
    with open(datasetpath, 'r') as f:
        jsonl = f.read()

    data = jsonl.split('\n')
    data = [json.loads(d) for d in data if d]

    # check if embeddings for the dataset already exists
    if os.path.exists(f"{output_folder}/query_embeddings.npy"):
        logger.info(f"Query Embeddings already exists in folder {output_folder}")
        embs = np.load(f"{output_folder}/query_embeddings.npy", allow_pickle=True)
        return embs
    else:
        query_embeddings = []
        for json_line in tqdm(data, desc="Embedding queries into {}".format(output_folder)):
            if json_line:
                query = json_line["query"]
                query_emb = embedder.embed([query])
                query_embeddings.extend(query_emb)

        embeddings = np.vstack(query_embeddings)
        
        os.makedirs(output_folder, exist_ok=True)
        np.save(f"{output_folder}/query_embeddings.npy", embeddings)

        return embeddings

def create_ground_truth(df_queries:pd.DataFrame, embeddings_index:np.ndarray) -> Dict[int, Set[int]]:
    """
    Create the ground truth for the evaluation dataset
    Args:
        embeddings_index: numpy array of message_ids
        df_queries: DataFrame of queries
    Returns:
        ground_truth: Dictionary of ground truth
    """
    ground_truth = dict[int, Set[int]]()
    for idx, row in df_queries.iterrows():
        email_id = row["id"]
        # find in embeddings index it's index
        emb_index_set = set(np.where(embeddings_index == email_id)[0])
        ground_truth[idx] = emb_index_set
    return ground_truth

def main(config):
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    # Config settings
    data_dir = config.get("data_folder")
    models = config.get("models")
    force_embedding_creation = config.get("force_embedding_creation", False)  # Default to False if missing
    evaluation_datasetpath = config.get("evaluation_dataset")
    results_output_filepath = config.get("results_output")

    # Validate required settings
    required_settings = {
        "data_folder": data_dir,
        "models": models,
        "evaluation_dataset": evaluation_datasetpath,
        "results_output": results_output_filepath
    }

    missing_settings = [key for key, value in required_settings.items() if not value]
    if missing_settings:
        logger.error(f"Missing required configuration settings: {', '.join(missing_settings)}")
        sys.exit(1)

    # list all jsonl files from the "traning" set
    # Get full paths of all .jsonl files in the directory
    files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".jsonl") and os.path.isfile(os.path.join(data_dir, f))]
    if len(files) == 0:
        logger.error(f"No jsonl files found in {data_dir}")
        sys.exit(1)

    results = []

    for model_id in models:
        # initialize the model and tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModel.from_pretrained(model_id)
        model.to(device)

        # initialize the embedder
        embedder = Embedder(model, tokenizer)

        output_subfolder = model_id.split("/")[-1]
        output_folder = f"{data_dir}/{output_subfolder}"
        os.makedirs(output_folder, exist_ok=True)

        # Create embeddings for model
        embeddings, curpus_index, avg_embedding_time = create_embeddings(embedder, files, output_folder, force_embedding_creation)
        logger.info(f"Average embedding time for {model_id}: {avg_embedding_time:.4f} seconds")

        # Load the evaluation (query) embeddings for model evaluation
        ground_truth_embeddings = load_evaluation_dataset(embedder, evaluation_datasetpath, output_folder)

        # Move embeddings to the selected device
        corpus_embeddings = torch.from_numpy(embeddings).to(device)
        query_embeddings = torch.from_numpy(ground_truth_embeddings).to(device)

        # normalize the embeddings if necessary (not required for cosine similarity)
        # corpus_embeddings = F.normalize(corpus_embeddings, p=2, dim=1)
        # query_embeddings = F.normalize(query_embeddings, p=2, dim=1)

        # evaluate the embedding model
        logger.info(f"Evaluating the model {model_id}")
        df_queries = pd.read_json(evaluation_datasetpath, lines=True)
        ground_truth = create_ground_truth(df_queries, curpus_index)
        ir_evaluator = MailioInformationRetrievalEvaluator(ground_truth, corpus_embeddings, query_embeddings, similarity_functions=[SimilarityFunction.COSINE])

        # Evaluate the model
        metrics = ir_evaluator.run()
        for name, score in metrics.items():

            logger.info(f"----------------- Similarity function: {name} ----------------")
            ir_evaluator.output_scores(score)

            problematic_queries = ir_evaluator.get_problematic_queries()
            problematic_queries_texts = []
            # convert 
            if len(problematic_queries) > 0:
                for idx in problematic_queries:
                    problematic_queries_texts.append(df_queries.iloc[idx]["query"])

            results.append({
                "model_id": model_id,
                "similarity_function": name,
                "problematic_queries_count": len(problematic_queries),
                "problematic_queries": problematic_queries_texts,
                "avg_embedding_time": avg_embedding_time,
                **score,
            })

            # create pandas jsonl DataFrame from all results and save to output results
            df_results = pd.DataFrame(results)
            df_results.to_json(results_output_filepath, orient="records", lines=True)

        # cleanup the memory
        memory_cleanup(model, tokenizer, embedder)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load and use a YAML configuration file.")
    parser.add_argument(
        "--config", 
        type=str, 
        required=True, 
        help="Path to the YAML configuration file."
    )
    args = parser.parse_args()
    config = load_config(args.config)
    main(config)
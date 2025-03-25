<!--
This file contains the README documentation for the Mailio AI project.
-->
# Mailio AI

Mailio AI is an open-source project aimed at providing intelligent email management solutions using machine learning and artificial intelligence. The project includes features such as email classification, spam detection, and automated responses.

## Features

- **Email Search**: Semantic search using Pinecone and sentence transformers from HuggingFace

## Tools

- **Optimal Embeddings Model**: [Find best performing embedding model based on input data](https://github.com/mailio/mailio-ai/tree/main/tools)

## Installation

To install Mailio AI, clone the repository and install the required dependencies:

```bash
git clone https://github.com/mailio/mailio-ai.git
cd mailio-ai
pip install -r requirements.txt
```

## Configuration

Mailio AI uses a configuration file `config.yaml` to manage settings and `.env` to manage secrets (passwords, api keys, ...). 

Below is an example of the configuration file:

```yaml
version: 0.0.1

cors_origins: 
  - https://*.example.com

jwt:
  secret_key: myjwtsecretkey
  expiration: 2592000 # seconds (24*60*60*30)
  algorithm: HS256
  sliding_expiration_threshold: 300 # seconds (5 minutes)


embedding_model: jinaai/jina-embeddings-v3

pinecone:
  index_name: myindex-...
  cloud: aws
  region: us-east-1
  metric: cosine

redis:
  host: localhost
  port: 6379
  username: default
  db: 3
```

`.env example`:
```bash
JWT_SECRET_KEY=...
SYSTEM_USERNAME=...
SYSTEM_PASSWORD=...
PINECONE_API_KEY=...
OPEN_AI_KEY=...
REDIS_PASSWORD=...
```

Replace the values with your actual configuration details.

## Usage

To start using Mailio AI, run the main script:

```bash
uvicorn main:app --reload
```

To start with fastapi dev server:
```bash
fastapi dev main.py
```

Setup `VSCode` or `Cursor`: 

```
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python Debugger: Current File",
            "type": "debugpy",
            "request": "launch",
            "module": "uvicorn",
            "console": "integratedTerminal",
            "args": [
                "main:app",
                "--port",
                "8888",
                "--reload"
            ]
        }
    ]
}
```

## Contribution

We welcome contributions from the community. To contribute to Mailio AI, follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Make your changes and commit them with descriptive messages.
4. Push your changes to your fork.
5. Create a pull request to the main repository.

Please ensure your code adheres to the project's coding standards and includes appropriate tests.

## License

Mailio AI is licensed under the MIT License. See the `LICENSE` file for more details.


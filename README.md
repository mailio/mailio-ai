<!--
This file contains the README documentation for the Mailio AI project.
-->
# Mailio AI

Mailio AI is an open-source project aimed at providing intelligent email management solutions using machine learning and artificial intelligence. The project includes features such as email classification, spam detection, and automated responses.

## Features

- **Email Search**: Semantic search using Pinecone and sentence transformers from HuggingFace
- **LLM Integration**: OpenAI integration for intelligent email processing and responses
- **Vector Database**: Pinecone integration for efficient similarity search
- **Task Queue**: Redis-based background processing for embedding generation
- **Authentication**: JWT-based authentication system
- **Health Monitoring**: Built-in health check endpoints
- **Docker Support**: Containerized deployment with Docker and Docker Compose
- **Kubernetes Ready**: Complete K8s deployment configurations

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

### Local Development

To start using Mailio AI, run the main script:

```bash
uvicorn main:app --reload
```

To start with fastapi dev server:
```bash
fastapi dev main.py
```

### Docker Deployment

Build and run with Docker:

```bash
docker build -t mailio-ai .
docker run -p 8000:8000 --env-file .env -v ./config.yaml:/app/config.yaml:ro mailio-ai
```

Or use Docker Compose:

```bash
docker-compose up -d
```

### API Endpoints

Once running, the API will be available at `http://localhost:8000` with the following main endpoints:

- `GET /` - API status
- `GET /health` - Health check
- `POST /embeddings/` - Create embeddings
- `POST /embeddings/search` - Search embeddings
- `POST /token/` - Authentication
- `POST /llm/` - LLM operations

Interactive API documentation is available at `http://localhost:8000/docs`

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

## Deployment

### Kubernetes Deployment

The project includes comprehensive Kubernetes deployment configurations in the `deployment/` directory:

- **ConfigMap**: Application configuration
- **Secrets**: Sensitive environment variables
- **Deployment**: Main application deployment
- **CronJob**: Index synchronization job

Deploy to Kubernetes:

```bash
kubectl apply -f deployment/
```

### Index Synchronization

`index_sync_embeddings.py` is a sub-project for synchronization of vector database with the email database. 

Check `.github/workflows/deploy.yaml` for k8s deployment strategy. 

Manually starting a k8s cron job: 
```bash
kubectl create job \
  --from=cronjob/mailio-index-sweeper \
  mailio-index-sweeper-now-$(date +%s)
```

### Production Considerations

- **Environment Variables**: Ensure all required environment variables are set
- **Resource Limits**: Configure appropriate CPU and memory limits for your deployment
- **Scaling**: The application supports horizontal scaling with multiple replicas
- **Monitoring**: Health check endpoints are available for monitoring
- **Security**: Use proper secrets management for production deployments

## Architecture

The application is built with a modular architecture:

- **API Layer**: FastAPI-based REST API with automatic documentation
- **Services**: Business logic layer for embeddings, LLM, and database operations
- **Models**: Data models and validation schemas
- **Routes**: API endpoint definitions and request handling
- **Background Processing**: Redis-based task queue for async operations

## Dependencies

Key dependencies include:
- **FastAPI**: Modern web framework for building APIs
- **Pinecone**: Vector database for similarity search
- **Redis**: In-memory data store for task queues
- **Transformers**: HuggingFace transformers for embeddings
- **OpenAI**: LLM integration
- **CouchDB**: Document database integration

## Contribution

We welcome contributions from the community. To contribute to Mailio AI, follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Make your changes and commit them with descriptive messages.
4. Push your changes to your fork.
5. Create a pull request to the main repository.

Please ensure your code adheres to the project's coding standards and includes appropriate tests.

## Troubleshooting

### Common Issues

1. **Connection Errors**: Ensure all external services (Pinecone, Redis, CouchDB) are accessible and credentials are correct
2. **Memory Issues**: The embedding models can be memory-intensive; consider using smaller models for development
3. **Port Conflicts**: Default port is 8000; use `--port` flag to specify a different port
4. **Environment Variables**: Ensure all required environment variables are set in your `.env` file

### Debug Mode

Run with debug logging:
```bash
uvicorn main:app --reload --log-level debug
```

### Health Checks

Check application health:
```bash
curl http://localhost:8000/health
```

## License

Mailio AI is licensed under the MIT License. See the `LICENSE` file for more details.


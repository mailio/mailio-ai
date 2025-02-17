# Mailio AI Kubernetes Deployment

Hey there! Welcome to the Mailio AI Kubernetes deployment guide. This README will walk you through the components of the deployment and how to get your application up and running on your cluster. Let's dive in!

---

## Overview

This deployment leverages three key Kubernetes resources:

- **ConfigMap (`mailio-ai-config`)**  
  Contains the configuration file (`config.yaml`) for the Mailio AI app. This file includes settings for CORS, JWT, the embedding model, CouchDB, Pinecone, and Redis.

- **Secret (`mailio-ai-secrets`)**  
  Stores sensitive data like JWT secret keys, CouchDB and Redis passwords, Pinecone API key, etc. The values here are Base64 encoded for security.

- **Deployment (`mailio-ai`)**  
  Deploys the Mailio AI container. It uses the configuration file from the ConfigMap and pulls in secrets as environment variables.

---

## Kubernetes Resources Breakdown

### 1. ConfigMap: `mailio-ai-config`

This ConfigMap holds your application's configuration in `config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mailio-ai-config
data:
  config.yaml: |
    version: 0.0.1

    cors_origins: 
      - https://*.mail.io

    jwt:
      expiration: 2592000 # seconds (24*60*60*30)
      algorithm: HS256
      sliding_expiration_threshold: 300 # seconds (5 minutes)

    embedding_model: intfloat/e5-small-v2

    couchdb:
      host: http://localhost:5984
      username: admin

    pinecone:
      index_name: https://myindex-....pinecone.io
      cloud: aws
      region: us-east-1
      metric: cosine

    redis:
      host: 127.0.0.1
      port: 6379
      username: default
      db: 3

### 2. Secret: mailio-ai-secrets

This Secret stores your sensitive configuration details:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mailio-ai-secrets
type: Opaque
data:
  jwt_secret_key: YWJj  # Base64 encoded value of "abc"
  system_username: YWJj  # Base64 encoded value of "abc"
  system_password: ZGVm  # Base64 encoded value of "def"
  couchdb_password: WU9VUlBBU1NXT1JE  # Base64 encoded value of "YOURPASSWORD"
  pinecone_api_key: cGNrc19hYmM=  # Base64 encoded value of "pcks_abc"
  redis_password: WU9VUlBBU1NXT1JE  # Base64 encoded value of "YOURPASSWORD"
```

### 3. Deployment: mailio-ai

The Deployment runs the Mailio AI container with the proper configuration and secrets mounted:

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mailio-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mailio-ai
  template:
    metadata:
      labels:
        app: mailio-ai
    spec:
      containers:
        - name: mailio-ai
          image: mailio/mailio-ai:latest  # Replace with actual image if needed
          ports:
            - containerPort: 8000
          volumeMounts:
            - name: config-volume
              mountPath: "/app/config.yaml"  # Mount as a file
              subPath: "config.yaml"         # Extract only this file
          env: 
            - name: CONFIG_FILE
              value: "/app/config.yaml"  # Reference path for config file
            - name: JWT_SECRET_KEY
              valueFrom: 
                secretKeyRef:
                  name: mailio-ai-secrets
                  key: jwt_secret_key
            - name: SYSTEM_USERNAME
              valueFrom:
                secretKeyRef:
                  name: mailio-ai-secrets
                  key: system_username
            - name: SYSTEM_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mailio-ai-secrets
                  key: system_password
            - name: COUCHDB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mailio-ai-secrets
                  key: couchdb_password
            - name: PINECONE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: mailio-ai-secrets
                  key: pinecone_api_key
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mailio-ai-secrets
                  key: redis_password
      volumes:
        - name: config-volume
          configMap:
            name: mailio-ai-config  # This matches the ConfigMap name
```

## How to Deploy

1.	Prepare Your Environment:
- Make sure you have a Kubernetes cluster running.
- Install and configure kubectl.
2.	Update Your Configuration:
- Adjust the values in config.yaml inside the ConfigMap if needed.
- Update the Secret values, ensuring they are correctly Base64 encoded.
3.	Apply the Configuration:

Save the YAML above into a file (e.g., mailio-ai-deployment.yaml) and deploy it:

```bash
kubectl apply -f mailio-ai-deployment.yaml
```

4.	Verify the Deployment:

Check that your Pods are running:

```
kubectl get pods
```

5. Access your application

Depending on your cluster setup, expose the service using a LoadBalancer, NodePort, or Ingress.

## Customization

Feel free to tweak the configuration settings to suit your environment:
- Change the cors_origins if you need different domains.
- Adjust JWT expiration, algorithm, or sliding expiration thresholds.
- Update connection details for CouchDB, Pinecone, and Redis.

## Contributing

Found a bug or have an idea for improvement? Feel free to open an issue or submit a pull request. We’re always happy to collaborate!


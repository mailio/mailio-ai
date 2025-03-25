import yaml
import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    Configuration class
    """
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")
            self.config_path = Path(CONFIG_PATH)
        if not self.config_path.exists():
            raise ValueError(f"Configuration file {self.config_path} not found")
        self.data = self.load_config(self.config_path)

    def load_config(self, path:str):
        """
        Load yaml configuration file
        """
        config = None
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        return config

    def get(self, key: str, default=None):
        """
        Get configuration value with a fallback default
        """
        return self.data.get(key, default)   

# Initialize the config instance globally
cfg = Config()

def get_config() -> Dict:
    """
    Get the global configuration instance
    """
    cfg_jwt = cfg.data.get("jwt", None)
    if cfg_jwt:
        cfg.data["jwt"]["system_username"] = os.environ.get("SYSTEM_USERNAME", default=None)
        cfg.data["jwt"]["system_password"] = os.environ.get("SYSTEM_PASSWORD", default=None)
        cfg.data["jwt"]["secret_key"] = os.environ.get("JWT_SECRET_KEY", default=None)
    cfg_couchdb = cfg.data.get("couchdb", None)  
    if cfg_couchdb:
        cfg.data["couchdb"]["password"] = os.environ.get("COUCHDB_PASSWORD", default=None)
    cfg_redis = cfg.data.get("redis", None)
    if cfg_redis:
        cfg.data["redis"]["password"] = os.environ.get("REDIS_PASSWORD", default=None)
    cfg_pinecone = cfg.data.get("pinecone", None)
    if cfg_pinecone:
        cfg.data["pinecone"]["api_key"] = os.environ.get("PINECONE_API_KEY", default=None)
    cfg_openai = cfg.data.get("openai", None)
    if cfg_openai:
        cfg.data["openai"]["api_key"] = os.environ.get("OPENAI_API_KEY", default=None)
    return cfg.data
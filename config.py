import yaml
import os
from pathlib import Path
from typing import Dict

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
    return cfg.data
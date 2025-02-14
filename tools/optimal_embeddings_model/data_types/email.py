from dataclasses import dataclass, field, asdict
from dacite import from_dict, Config
from enum import Enum
from typing import List, Optional, Dict, Any

# Custom encoder function for JSON serialization
def json_encoder(obj):
    if isinstance(obj, Enum):
        return obj.value  # Convert Enum to its value for JSON serialization
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

class MessageType(Enum):
    HTML = "html"
    TEXT = "text"

@dataclass
class Email:
    folder: str
    message_type: MessageType
    sender_name: str
    sender_email: str
    message_id: str
    created: int
    subject: Optional[str] = None
    sentences: Optional[List[str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict):
        config = Config(
            cast=[MessageType], 
            strict=True, 
            check_types=True
        )

        return from_dict(data_class=cls, data=data, config=config)

    def to_dict(cls) -> Dict[str, Any]:
        """Convert the Email instance to a dictionary, ensuring proper Enum serialization."""
        return asdict(cls, dict_factory=lambda x: {k: (v.value if isinstance(v, Enum) else v) for k, v in x})

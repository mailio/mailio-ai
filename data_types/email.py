from dataclasses import dataclass, field
from dacite import from_dict, Config
from enum import Enum
from typing import List, Optional

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
        return from_dict(data_class=cls, data=data, config=Config(cast=[MessageType]))
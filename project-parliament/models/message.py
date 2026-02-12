"""メッセージ データモデル"""
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Dict, Any


class MessageType(Enum):
    AI_MESSAGE = "ai_message"
    SYSTEM = "system"
    PROPOSAL = "proposal"
    VOTE = "vote"


@dataclass
class Message:
    id: str
    type: MessageType
    ai_id: str
    ai_name: str
    icon: str
    avatar_color: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """フロントエンド向け辞書表現"""
        return {
            "id": self.id,
            "type": self.type.value,
            "ai_id": self.ai_id,
            "ai_name": self.ai_name,
            "icon": self.icon,
            "avatar_color": self.avatar_color,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

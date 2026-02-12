"""AIエージェント データモデル"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict


class AgentStatus(Enum):
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ONLINE = "online"
    ERROR = "error"


@dataclass
class AIAgent:
    id: str
    name: str
    service: str  # "anthropic" / "openai" / "gemini"
    role: str  # "chair" / "leader" / "worker" / "critic"
    role_label: str
    icon: str
    avatar_color: str
    has_voting_right: bool
    description: str
    status: AgentStatus = AgentStatus.OFFLINE
    conversation_history: List[Dict] = field(default_factory=list)

    @classmethod
    def from_profile(cls, ai_id: str, profile: dict) -> "AIAgent":
        """AI_PROFILESの辞書エントリからAIAgentインスタンスを生成"""
        return cls(
            id=ai_id,
            name=profile["name"],
            service=profile["service"],
            role=profile["role"],
            role_label=profile["role_label"],
            icon=profile["icon"],
            avatar_color=profile["avatar_color"],
            has_voting_right=profile["can_vote"],
            description=profile["description"],
        )

    def to_dict(self) -> dict:
        """フロントエンド向け辞書表現"""
        return {
            "id": self.id,
            "name": self.name,
            "service": self.service,
            "role": self.role,
            "role_label": self.role_label,
            "icon": self.icon,
            "avatar_color": self.avatar_color,
            "has_voting_right": self.has_voting_right,
            "description": self.description,
            "status": self.status.value,
        }

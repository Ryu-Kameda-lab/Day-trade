"""稟議書・投票 データモデル"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class Vote:
    voter_id: str
    vote: str  # "support" / "oppose"
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "voter_id": self.voter_id,
            "vote": self.vote,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Proposal:
    id: str
    submitted_by: str
    timestamp: datetime
    strategy: str  # "long" / "short"
    pair: str  # "BTC/USDT" etc.
    entry_price: float
    take_profit: float
    stop_loss: float
    reasoning: str
    votes: Dict[str, Optional[Vote]] = field(default_factory=dict)
    status: str = "voting"  # "voting" / "approved" / "rejected" / "reviewing" / "finalized"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "submitted_by": self.submitted_by,
            "timestamp": self.timestamp.isoformat(),
            "strategy": self.strategy,
            "pair": self.pair,
            "entry_price": self.entry_price,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "reasoning": self.reasoning,
            "votes": {
                k: v.to_dict() if v else None
                for k, v in self.votes.items()
            },
            "status": self.status,
        }

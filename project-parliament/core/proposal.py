"""稟議書管理 - ProposalManager"""
import uuid
from datetime import datetime
from typing import Dict, Optional

from models.proposal import Proposal, Vote
from config import AI_PROFILES


class ProposalManager:
    """稟議書のライフサイクルを管理する"""

    def __init__(self):
        self.proposals: Dict[str, Proposal] = {}

    def create_proposal(self, submitted_by: str, data: dict) -> Proposal:
        """
        新しい稟議書を作成する。

        Args:
            submitted_by: 提出者のAI ID
            data: 稟議書データ (strategy, pair, entry_price, take_profit, stop_loss, reasoning)
        Returns:
            作成されたProposalインスタンス
        """
        proposal_id = str(uuid.uuid4())

        # 投票権者の票を初期化（Noneは未投票を表す）
        voters = {
            ai_id: None
            for ai_id, profile in AI_PROFILES.items()
            if profile["can_vote"]
        }

        proposal = Proposal(
            id=proposal_id,
            submitted_by=submitted_by,
            timestamp=datetime.now(),
            strategy=data.get("strategy", "long"),
            pair=data.get("pair", "BTC/USDT"),
            entry_price=float(data.get("entry_price", 0)),
            take_profit=float(data.get("take_profit", 0)),
            stop_loss=float(data.get("stop_loss", 0)),
            reasoning=data.get("reasoning", ""),
            votes=voters,
            status="voting",
        )

        self.proposals[proposal_id] = proposal
        return proposal

    def submit_for_voting(self, proposal_id: str) -> Optional[Proposal]:
        """稟議書を投票フェーズに移行する"""
        proposal = self.proposals.get(proposal_id)
        if proposal:
            proposal.status = "voting"
        return proposal

    def start_brushup(self, proposal_id: str) -> Optional[Proposal]:
        """稟議書のブラッシュアップフェーズを開始する"""
        proposal = self.proposals.get(proposal_id)
        if proposal:
            proposal.status = "reviewing"
        return proposal

    def finalize(self, proposal_id: str, final_data: Optional[dict] = None) -> Optional[Proposal]:
        """
        稟議書を最終版として確定する。

        Args:
            proposal_id: 稟議書ID
            final_data: 更新データ（任意）
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return None

        if final_data:
            if "strategy" in final_data:
                proposal.strategy = final_data["strategy"]
            if "pair" in final_data:
                proposal.pair = final_data["pair"]
            if "entry_price" in final_data:
                proposal.entry_price = float(final_data["entry_price"])
            if "take_profit" in final_data:
                proposal.take_profit = float(final_data["take_profit"])
            if "stop_loss" in final_data:
                proposal.stop_loss = float(final_data["stop_loss"])
            if "reasoning" in final_data:
                proposal.reasoning = final_data["reasoning"]

        proposal.status = "finalized"
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """稟議書を取得する"""
        return self.proposals.get(proposal_id)

    def get_active_proposals(self) -> list:
        """アクティブ（finalized以外）な稟議書一覧を返す"""
        return [
            p for p in self.proposals.values()
            if p.status not in ("finalized", "rejected")
        ]

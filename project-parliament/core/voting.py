"""投票ロジック - VotingManager"""
from datetime import datetime
from typing import Optional

from models.proposal import Proposal, Vote


# 投票権者リスト
VOTERS = ["claude_chair", "gpt_leader", "gem_leader"]


class VotingManager:
    """投票の実行とコンセンサス判定を管理する"""

    def __init__(self):
        self.voters = list(VOTERS)

    def cast_vote(
        self,
        proposal: Proposal,
        voter_id: str,
        vote: str,
        reason: str,
    ) -> bool:
        """
        投票を実行する。

        Args:
            proposal: 対象の稟議書
            voter_id: 投票者のAI ID
            vote: "support" / "oppose"
            reason: 投票理由
        Returns:
            投票が正常に記録されたかどうか
        """
        if voter_id not in self.voters:
            return False

        if proposal.status != "voting":
            return False

        if vote not in ("support", "oppose"):
            return False

        proposal.votes[voter_id] = Vote(
            voter_id=voter_id,
            vote=vote,
            reason=reason,
            timestamp=datetime.now(),
        )
        return True

    def check_consensus(self, proposal: Proposal) -> str:
        """
        コンセンサスを判定する。

        提出者以外の全投票権者が賛成で "approved"、
        反対が1つでもあれば "rejected"、
        未投票があれば "pending"。

        Returns: "approved" / "rejected" / "pending"
        """
        non_submitter_voters = [
            vid for vid in self.voters if vid != proposal.submitted_by
        ]

        for voter_id in non_submitter_voters:
            vote_obj = proposal.votes.get(voter_id)
            if vote_obj is None:
                return "pending"
            if vote_obj.vote == "oppose":
                return "rejected"

        return "approved"

    def get_voting_status(self, proposal: Proposal) -> dict:
        """
        投票状況のサマリを返す。

        Returns:
            {
                "total_voters": int,
                "voted": int,
                "support": int,
                "oppose": int,
                "pending": int,
                "votes": { voter_id: { ... } or None },
                "consensus": "approved" / "rejected" / "pending",
            }
        """
        voted = 0
        support = 0
        oppose = 0
        pending_count = 0
        votes_detail = {}

        for voter_id in self.voters:
            vote_obj = proposal.votes.get(voter_id)
            if vote_obj is not None:
                voted += 1
                if vote_obj.vote == "support":
                    support += 1
                else:
                    oppose += 1
                votes_detail[voter_id] = vote_obj.to_dict()
            else:
                pending_count += 1
                votes_detail[voter_id] = None

        return {
            "total_voters": len(self.voters),
            "voted": voted,
            "support": support,
            "oppose": oppose,
            "pending": pending_count,
            "votes": votes_detail,
            "consensus": self.check_consensus(proposal),
        }

from datetime import datetime

from core.voting import VotingManager
from models.proposal import Proposal


def make_proposal(submitted_by: str = "gpt_leader") -> Proposal:
    return Proposal(
        id="p1",
        submitted_by=submitted_by,
        timestamp=datetime.now(),
        strategy="long",
        pair="BTC/USDT",
        entry_price=1.0,
        take_profit=1.1,
        stop_loss=0.9,
        reasoning="test",
        votes={"claude_chair": None, "gpt_leader": None, "gem_leader": None},
        status="voting",
    )


def test_voting_status_excludes_submitter_from_required_votes():
    manager = VotingManager()
    proposal = make_proposal(submitted_by="gpt_leader")

    status = manager.get_voting_status(proposal)

    assert status["total_voters"] == 2
    assert status["pending"] == 2
    assert "gpt_leader" not in status["votes"]


def test_consensus_approved_when_non_submitters_support():
    manager = VotingManager()
    proposal = make_proposal(submitted_by="gpt_leader")

    assert manager.cast_vote(proposal, "claude_chair", "support", "ok")
    assert manager.cast_vote(proposal, "gem_leader", "support", "ok")

    status = manager.get_voting_status(proposal)
    assert status["consensus"] == "approved"

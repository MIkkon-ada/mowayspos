from app import models
from app.domain import project_lifecycle as PL


def test_pending_kickoff_has_a_canonical_lifecycle_and_audit_models():
    assert PL.normalize("pending_kickoff") == "pending_kickoff"
    assert "pending_kickoff" in PL.ALL_STATUSES
    assert models.KickoffAgentRun.__tablename__ == "kickoff_agent_runs"
    assert models.KickoffChangeProposal.__tablename__ == "kickoff_change_proposals"

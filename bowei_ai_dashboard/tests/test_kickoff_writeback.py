import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.kickoff_writeback import confirm_kickoff_start


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_confirm_start_rejects_pending_proposal():
    db = _db()
    db.add_all([models.Project(id=1, name="P", status="pending_kickoff"), models.KickoffAgentRun(id=1, project_id=1, status="submitted"), models.KickoffChangeProposal(run_id=1, proposal_type="update", target_type="task")])
    db.commit()
    with pytest.raises(HTTPException, match="未审核"):
        confirm_kickoff_start(1, "Coach", db)


def test_confirm_start_activates_after_approved_no_change():
    db = _db()
    db.add_all([models.Project(id=1, name="P", status="pending_kickoff"), models.KickoffAgentRun(id=1, project_id=1, status="submitted", result_json=json.dumps({"summary": "无调整"})), models.KickoffChangeProposal(run_id=1, proposal_type="no_change", target_type="", review_status="approved")])
    db.commit()
    project, meeting = confirm_kickoff_start(1, "Coach", db)
    assert project.status == "active"
    assert meeting.meeting_type == "kickoff"

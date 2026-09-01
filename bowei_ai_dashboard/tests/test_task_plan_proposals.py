from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.services.task_plan_proposals import apply_text_plan_proposals, create_text_plan_proposal_run


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeAI:
    def invoke_chat(self, *_args, **_kwargs):
        return type("Result", (), {
            "text": json.dumps({"plans": [
                {
                    "title": "整理客户清单",
                    "expected_output": "可核对的客户清单",
                    "assignee_id": 2,
                    "collaborator_ids": [],
                    "status": "未开始",
                    "evidence": {
                        "title": "整理客户清单并形成可核对的客户清单",
                        "expected_output": "整理客户清单并形成可核对的客户清单",
                        "assignee_id": "由李四负责",
                    },
                },
                {
                    "title": "安排客户访谈",
                    "expected_output": "访谈纪要",
                    "assignee_id": None,
                    "collaborator_ids": [],
                    "status": "未开始",
                    "evidence": {
                        "title": "随后安排客户访谈并输出访谈纪要",
                        "expected_output": "随后安排客户访谈并输出访谈纪要",
                    },
                },
            ]}, ensure_ascii=False),
            "model_code": "fake-chat",
            "invocation_log_id": 7,
        })()


def _seed(db: Session):
    db.add_all([
        models.Person(id=1, name="王五", is_active=True),
        models.Person(id=2, name="李四", is_active=True),
        models.Project(id=10, name="示例项目", status="active", is_active=True),
        models.ProjectMember(project_id=10, person_id=1, person_name_snapshot="王五", role="owner"),
        models.ProjectMember(project_id=10, person_id=2, person_name_snapshot="李四", role="member"),
        models.Task(id=20, project_id=10, key_task="客户交付", owner="王五", status="进行中"),
        models.SubTask(id=30, task_id=20, title="客户交付", assignee="王五", status="进行中"),
    ])
    db.commit()


def test_text_analysis_persists_multiple_auditable_drafts_for_selected_key_task(db):
    _seed(db)
    source = "由李四负责整理客户清单并形成可核对的客户清单，随后安排客户访谈并输出访谈纪要。"

    run = create_text_plan_proposal_run(
        project_id=10,
        key_task_id=30,
        source_text=source,
        created_by_person_id=1,
        actor="owner",
        db=db,
        ai_service=FakeAI(),
    )

    proposals = db.query(models.TaskPlanProposal).filter_by(run_id=run.id).order_by(models.TaskPlanProposal.id).all()
    assert run.key_task_id == 30
    assert run.status == "ready_for_review"
    assert len(proposals) == 2
    assert proposals[0].status == "ready"
    assert proposals[1].status == "needs_confirmation"
    assert json.loads(proposals[0].plan_json)["assignee_id"] == 2
    assert json.loads(proposals[1].validation_json)["state"] == "needs_confirmation"


def test_apply_revalidates_selected_drafts_atomically(db):
    _seed(db)
    run = create_text_plan_proposal_run(
        project_id=10,
        key_task_id=30,
        source_text="由李四负责整理客户清单并形成可核对的客户清单，随后安排客户访谈并输出访谈纪要。",
        created_by_person_id=1,
        actor="owner",
        db=db,
        ai_service=FakeAI(),
    )
    proposals = db.query(models.TaskPlanProposal).filter_by(run_id=run.id).order_by(models.TaskPlanProposal.id).all()
    second = json.loads(proposals[1].plan_json)
    second["assignee_id"] = 2
    proposals[1].plan_json = json.dumps(second, ensure_ascii=False)
    proposals[1].status = "ready"
    first = json.loads(proposals[0].plan_json)
    first["collaborator_ids"] = [999]
    proposals[0].plan_json = json.dumps(first, ensure_ascii=False)
    db.commit()

    with pytest.raises(HTTPException, match="负责人或协作人不属于该项目"):
        apply_text_plan_proposals(run=run, proposal_ids=[proposal.id for proposal in proposals], actor="owner", actor_person_id=1, db=db)
    assert db.query(models.ExecutionSchedule).count() == 0

    first["collaborator_ids"] = []
    proposals[0].plan_json = json.dumps(first, ensure_ascii=False)
    db.commit()
    created = apply_text_plan_proposals(run=run, proposal_ids=[proposal.id for proposal in proposals], actor="owner", actor_person_id=1, db=db)

    assert len(created) == 2
    assert db.query(models.ExecutionSchedule).filter_by(subtask_id=30, plan_type="month").count() == 2
    assert all(proposal.status == "executed" and proposal.created_plan_id for proposal in proposals)

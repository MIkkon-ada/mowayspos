from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.domain import issue_flow as IF
from app.domain import submission_status as SS
from app.domain import task_status as TS
from app.services.project_close import evaluate_project_close, parse_residual_items


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(models.Project(id=1, name="Close Project", status="active", is_active=True))
    session.commit()
    return session


def _materials() -> dict:
    return {
        "summary": "Project complete",
        "objective_result": "Objectives achieved",
        "unfinished_items": [],
        "remaining_risks": [],
        "handover_plan": "Handover complete",
        "retrospective": "Retrospective complete",
    }


def _codes(items: list[dict]) -> dict[str, int]:
    return {item["code"]: item["count"] for item in items}


def test_active_submissions_and_card_states_are_counted_once_per_submission():
    db = _db()
    db.add_all(
        [
            models.UpdateSubmission(
                project_id=1,
                transcript_text="owner",
                confirm_status=SS.S_NEW,
                human_result_json="{}",
            ),
            models.UpdateSubmission(
                project_id=1,
                transcript_text="coordinator",
                confirm_status=SS.S_WAITING_COORDINATOR,
                human_result_json=json.dumps(
                    {"task_reports": [{"confirmation_status": "transferred_to_coordinator"}]}
                ),
            ),
            models.UpdateSubmission(
                project_id=1,
                transcript_text="coach",
                confirm_status=SS.S_WAITING_CEO,
                human_result_json=json.dumps(
                    {"task_reports": [{"confirmation_status": "pending_ceo_decision"}]}
                ),
            ),
            models.UpdateSubmission(
                project_id=2,
                transcript_text="other project",
                confirm_status=SS.S_NEW,
            ),
        ]
    )
    db.commit()

    blockers, _warnings = evaluate_project_close(db, 1, _materials())

    assert _codes(blockers) == {
        "pending_confirmations": 3,
        "waiting_coordinator": 1,
        "waiting_project_coach": 1,
    }


def test_card_level_waiting_states_are_detected_from_human_result():
    db = _db()
    db.add_all(
        [
            models.UpdateSubmission(
                project_id=1,
                transcript_text="card coordinator",
                confirm_status=SS.S_NEW,
                human_result_json=json.dumps(
                    {
                        "task_reports": [
                            {"confirmation_status": "transferred_to_coordinator"},
                            {"confirmation_status": "transferred_to_coordinator"},
                        ]
                    }
                ),
            ),
            models.UpdateSubmission(
                project_id=1,
                transcript_text="card coach",
                confirm_status=SS.S_NEW,
                human_result_json=json.dumps(
                    {"task_reports": [{"confirmation_status": "pending_ceo_decision"}]}
                ),
            ),
        ]
    )
    db.commit()

    blockers, _warnings = evaluate_project_close(db, 1, _materials())

    assert _codes(blockers)["pending_confirmations"] == 2
    assert _codes(blockers)["waiting_coordinator"] == 1
    assert _codes(blockers)["waiting_project_coach"] == 1


def test_decision_issues_achievement_submissions_and_member_changes_block_close():
    db = _db()
    db.add_all(
        [
            models.Issue(
                project_id=1,
                issue_type=IF.TYPE_DECISION,
                description="Decision required",
                status=IF.STATUS_PENDING_DECISION,
            ),
            models.Issue(
                project_id=1,
                issue_type=IF.TYPE_DECISION,
                description="Already closed",
                status=IF.STATUS_CLOSED,
            ),
            models.AchievementSubmission(
                project_id=1,
                related_task_id=1,
                name="Pending asset",
                status="待确认",
            ),
            models.MemberChangeRequest(
                project_id=1,
                action="add",
                target_person_id=9,
                to_role="member",
                status="pending",
            ),
        ]
    )
    db.commit()

    blockers, _warnings = evaluate_project_close(db, 1, _materials())

    assert _codes(blockers) == {
        "pending_decision_issues": 1,
        "pending_achievement_submissions": 1,
        "pending_member_change_requests": 1,
    }


def test_incomplete_or_corrupt_persisted_materials_are_a_blocker_and_safe_to_read():
    db = _db()
    row = models.ProjectCloseRequest(
        project_id=1,
        summary="",
        objective_result="Objectives",
        unfinished_items_json="not-json",
        remaining_risks_json="{}",
        handover_plan="Handover",
        retrospective="Retrospective",
    )
    db.add(row)
    db.commit()

    blockers, _warnings = evaluate_project_close(db, 1, row)

    assert _codes(blockers)["incomplete_close_materials"] == 1
    assert parse_residual_items(row.unfinished_items_json) == ([], False)
    assert parse_residual_items(row.remaining_risks_json) == ([], False)


def test_unfinished_key_tasks_and_open_non_decision_issues_are_warnings_only():
    db = _db()
    task = models.Task(project_id=1, key_task="Workstream", status=TS.S_IN_PROGRESS)
    db.add(task)
    db.flush()
    db.add_all(
        [
            models.SubTask(task_id=task.id, title="Open", assignee="Owner", status=TS.S_IN_PROGRESS),
            models.SubTask(task_id=task.id, title="Done", assignee="Owner", status=TS.S_COMPLETED),
            models.SubTask(
                task_id=task.id,
                title="Deleted",
                assignee="Owner",
                status=TS.S_IN_PROGRESS,
                is_deleted=True,
            ),
            models.Issue(
                project_id=1,
                issue_type=IF.TYPE_ISSUE,
                description="Open issue",
                status=IF.STATUS_PENDING,
            ),
            models.Issue(
                project_id=1,
                issue_type=IF.TYPE_ISSUE,
                description="Closed issue",
                status=IF.STATUS_RESOLVED,
            ),
        ]
    )
    db.commit()

    blockers, warnings = evaluate_project_close(db, 1, _materials())

    assert blockers == []
    assert _codes(warnings) == {"unfinished_key_tasks": 1, "open_non_decision_issues": 1}

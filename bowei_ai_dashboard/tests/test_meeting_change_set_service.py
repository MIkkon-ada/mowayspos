from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.meeting_change_set import (
    build_meeting_plan_snapshot,
    validate_meeting_change_proposal,
)


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_plan(db):
    active = models.Task(
        id=1,
        project_id=7,
        key_task="Existing workstream",
        owner="Known owner",
        coordinator="Known coordinator",
        collaborators="Known collaborator",
        plan_time="2026-08",
        status="In progress",
        key_achievement="Old achievement",
        completion_standard="Old standard",
    )
    deleted = models.Task(
        id=2,
        project_id=7,
        key_task="Deleted workstream",
        owner="Deleted owner",
        is_deleted=True,
    )
    other_project = models.Task(
        id=3,
        project_id=8,
        key_task="Other project workstream",
        owner="Other owner",
    )
    db.add_all([active, deleted, other_project])
    db.flush()
    db.add_all(
        [
            models.SubTask(
                id=11,
                task_id=active.id,
                title="Existing subtask",
                assignee="Known assignee",
                plan_time="2026-08-01",
                completion_criteria="Old criterion",
                status="In progress",
                notes="Old note",
            ),
            models.SubTask(
                id=12,
                task_id=active.id,
                title="Deleted subtask",
                assignee="Deleted assignee",
                is_deleted=True,
            ),
            models.SubTask(
                id=13,
                task_id=deleted.id,
                title="Subtask under deleted workstream",
                assignee="Deleted assignee",
            ),
        ]
    )
    db.commit()
    return active, deleted


def _valid_update_workstream():
    return {
        "action": "update_workstream",
        "target": {"workstream_id": 1},
        "proposed": {"completion_standard": "Approved standard"},
        "evidence": ["Speaker 1: use the approved standard."],
        "reason": "The meeting explicitly revised the standard.",
        "confidence": 0.92,
    }


def test_snapshot_contains_only_live_project_plan_rows_and_never_mutates_them():
    db = _db_session()
    active, _deleted = _seed_plan(db)
    before = {
        "tasks": db.query(models.Task).count(),
        "subtasks": db.query(models.SubTask).count(),
        "standard": db.get(models.Task, active.id).completion_standard,
        "subtask_status": db.get(models.SubTask, 11).status,
    }

    snapshot = build_meeting_plan_snapshot(7, db)

    assert snapshot == {
        "project_id": 7,
        "workstreams": [
            {
                "id": 1,
                "key_task": "Existing workstream",
                "owner": "Known owner",
                "coordinator": "Known coordinator",
                "collaborators": "Known collaborator",
                "plan_time": "2026-08",
                "status": "In progress",
                "key_achievement": "Old achievement",
                "completion_standard": "Old standard",
                "subtasks": [
                    {
                        "id": 11,
                        "title": "Existing subtask",
                        "assignee": "Known assignee",
                        "plan_time": "2026-08-01",
                        "completion_criteria": "Old criterion",
                        "status": "In progress",
                        "notes": "Old note",
                    }
                ],
            }
        ],
    }
    assert db.query(models.Task).count() == before["tasks"]
    assert db.query(models.SubTask).count() == before["subtasks"]
    assert db.get(models.Task, active.id).completion_standard == before["standard"]
    assert db.get(models.SubTask, 11).status == before["subtask_status"]


def test_valid_update_workstream_uses_frozen_before_value_and_does_not_mutate_rows():
    db = _db_session()
    active, _deleted = _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)

    normalized = validate_meeting_change_proposal(_valid_update_workstream(), snapshot)

    assert normalized == {
        "action": "update_workstream",
        "target": {"project_id": 7, "workstream_id": 1},
        "before": {
            "key_task": "Existing workstream",
            "owner": "Known owner",
            "coordinator": "Known coordinator",
            "collaborators": "Known collaborator",
            "plan_time": "2026-08",
            "status": "In progress",
            "key_achievement": "Old achievement",
            "completion_standard": "Old standard",
        },
        "proposed": {"completion_standard": "Approved standard"},
        "evidence": ["Speaker 1: use the approved standard."],
        "reason": "The meeting explicitly revised the standard.",
        "confidence": 0.92,
        "validation": {"state": "ready", "errors": []},
    }
    assert db.get(models.Task, active.id).completion_standard == "Old standard"


def test_unknown_target_missing_evidence_or_reason_blocks_proposal():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)

    normalized = validate_meeting_change_proposal(
        {
            "action": "update_subtask",
            "target": {"subtask_id": 9999},
            "proposed": {"status": "Done"},
            "evidence": [],
            "reason": "  ",
            "confidence": 0.5,
        },
        snapshot,
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": [
            "target subtask_id is not present in snapshot",
            "evidence must contain at least one non-empty string",
            "reason must be a non-empty string",
        ],
    }


def test_create_workstream_requires_key_task():
    db = _db_session()
    _seed_plan(db)

    normalized = validate_meeting_change_proposal(
        {
            "action": "create_workstream",
            "target": {},
            "proposed": {"owner": "Known owner"},
            "evidence": ["Speaker 1: create a new workstream."],
            "reason": "A new workstream was explicitly requested.",
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": ["create_workstream requires proposed.key_task"],
    }


def test_create_subtask_requires_title_and_parent_workstream():
    db = _db_session()
    _seed_plan(db)

    normalized = validate_meeting_change_proposal(
        {
            "action": "create_subtask",
            "target": {},
            "proposed": {"assignee": "Known assignee"},
            "evidence": ["Speaker 1: create the follow-up task."],
            "reason": "The follow-up was explicitly assigned.",
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": [
            "create_subtask requires target.workstream_id",
            "create_subtask requires proposed.title",
        ],
    }


def test_unknown_proposed_field_is_removed_and_blocks_proposal():
    db = _db_session()
    _seed_plan(db)
    proposal = _valid_update_workstream()
    proposal["proposed"]["problem_note"] = "This field is not editable here."

    normalized = validate_meeting_change_proposal(
        proposal,
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized["proposed"] == {"completion_standard": "Approved standard"}
    assert normalized["validation"] == {
        "state": "blocked",
        "errors": ["proposed contains unsupported fields: problem_note"],
    }


def test_unknown_assignee_requires_review_without_mutating_the_plan():
    db = _db_session()
    active, _deleted = _seed_plan(db)
    before_count = db.query(models.SubTask).count()

    normalized = validate_meeting_change_proposal(
        {
            "action": "create_subtask",
            "target": {"workstream_id": active.id},
            "proposed": {"title": "New follow-up", "assignee": "New person"},
            "evidence": ["Speaker 2: New person will own the follow-up."],
            "reason": "The meeting explicitly assigned the follow-up.",
            "confidence": 0.8,
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized["validation"] == {
        "state": "needs_review",
        "errors": ["assignee is not present in the frozen plan and requires review"],
    }
    assert db.query(models.SubTask).count() == before_count

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.domain import task_status as TS
from app.services.meeting_change_set import (
    build_meeting_plan_snapshot,
    validate_meeting_change_proposal as _validate_meeting_change_proposal,
)


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_plan(db):
    db.add_all(
        [
            models.Project(id=7, name="Project 7"),
            models.Project(id=8, name="Project 8"),
            models.Person(id=1, name="Known owner", is_active=True),
            models.Person(id=2, name="Known coordinator", is_active=True),
            models.Person(id=3, name="Known collaborator", is_active=True),
            models.Person(id=4, name="Known assignee", is_active=True),
            models.Person(id=5, name="Member without task", is_active=True),
            models.Person(id=6, name="Inactive member", is_active=False),
            models.Person(id=7, name="Active nonmember", is_active=True),
        ]
    )
    db.flush()
    db.add_all(
        [
            models.ProjectMember(project_id=7, person_id=1, role="owner"),
            models.ProjectMember(project_id=7, person_id=2, role="project_ceo"),
            models.ProjectMember(project_id=7, person_id=3, role="member"),
            models.ProjectMember(project_id=7, person_id=4, role="member"),
            models.ProjectMember(project_id=7, person_id=5, role="member"),
            models.ProjectMember(project_id=7, person_id=6, role="member"),
        ]
    )
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


def _transcript_for(proposal):
    evidence = proposal.get("evidence") if isinstance(proposal, dict) else []
    return "\n".join(item for item in evidence if isinstance(item, str)) or "Meeting transcript."


def _validate_with_transcript(proposal, snapshot):
    return _validate_meeting_change_proposal(
        proposal,
        snapshot,
        transcript_text=_transcript_for(proposal),
    )


def validate_meeting_change_proposal(proposal, snapshot, transcript_text=None):
    if transcript_text is None:
        return _validate_with_transcript(proposal, snapshot)
    return _validate_meeting_change_proposal(
        proposal,
        snapshot,
        transcript_text=transcript_text,
    )


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
        "member_names": [
            "Known assignee",
            "Known collaborator",
            "Known coordinator",
            "Known owner",
            "Member without task",
        ],
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

    proposal = _valid_update_workstream()
    normalized = validate_meeting_change_proposal(
        proposal,
        snapshot,
        transcript_text=_transcript_for(proposal),
    )

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

    proposal = {
            "action": "update_subtask",
            "target": {"subtask_id": 9999},
            "proposed": {"status": "completed"},
            "evidence": [],
            "reason": "  ",
            "confidence": 0.5,
    }
    normalized = validate_meeting_change_proposal(
        proposal,
        snapshot,
        transcript_text=_transcript_for(proposal),
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

    proposal = {
            "action": "create_workstream",
            "target": {},
            "proposed": {"owner": "Known owner"},
            "evidence": ["Speaker 1: create a new workstream."],
            "reason": "A new workstream was explicitly requested.",
            "confidence": 0.5,
    }
    normalized = validate_meeting_change_proposal(
        proposal,
        build_meeting_plan_snapshot(7, db),
        transcript_text=_transcript_for(proposal),
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": ["create_workstream requires proposed.key_task"],
    }


def test_create_subtask_requires_title_and_parent_workstream():
    db = _db_session()
    _seed_plan(db)

    proposal = {
            "action": "create_subtask",
            "target": {},
            "proposed": {"assignee": "Known assignee"},
            "evidence": ["Speaker 1: create the follow-up task."],
            "reason": "The follow-up was explicitly assigned.",
            "confidence": 0.5,
    }
    normalized = validate_meeting_change_proposal(
        proposal,
        build_meeting_plan_snapshot(7, db),
        transcript_text=_transcript_for(proposal),
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": [
            "create_subtask requires target.parent_workstream_id",
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
        transcript_text=_transcript_for(proposal),
    )

    assert normalized["proposed"] == {"completion_standard": "Approved standard"}
    assert normalized["validation"] == {
        "state": "blocked",
        "errors": ["proposed contains unsupported fields: problem_note"],
    }


def test_valid_create_workstream_is_normalized_against_the_frozen_project():
    db = _db_session()
    _seed_plan(db)

    normalized = validate_meeting_change_proposal(
        {
            "action": "create_workstream",
            "target": {},
            "proposed": {"key_task": "New workstream", "owner": "Known owner"},
            "evidence": ["Speaker 1: create the new workstream."],
            "reason": "The new workstream was explicitly agreed.",
            "confidence": 0.7,
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized == {
        "action": "create_workstream",
        "target": {"project_id": 7},
        "before": {},
        "proposed": {"key_task": "New workstream", "owner": "Known owner"},
        "evidence": ["Speaker 1: create the new workstream."],
        "reason": "The new workstream was explicitly agreed.",
        "confidence": 0.7,
        "validation": {"state": "ready", "errors": []},
    }


def test_valid_create_subtask_is_normalized_against_its_parent_workstream():
    db = _db_session()
    active, _deleted = _seed_plan(db)

    normalized = validate_meeting_change_proposal(
        {
            "action": "create_subtask",
            "target": {"parent_workstream_id": active.id},
            "proposed": {"title": "New follow-up", "assignee": "Known assignee"},
            "evidence": ["Speaker 1: create the follow-up."],
            "reason": "The follow-up was explicitly assigned.",
            "confidence": 0.8,
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized == {
        "action": "create_subtask",
        "target": {"project_id": 7, "parent_workstream_id": 1},
        "before": {},
        "proposed": {"title": "New follow-up", "assignee": "Known assignee"},
        "evidence": ["Speaker 1: create the follow-up."],
        "reason": "The follow-up was explicitly assigned.",
        "confidence": 0.8,
        "validation": {"state": "ready", "errors": []},
    }


def test_valid_update_subtask_uses_frozen_parent_and_before_values():
    db = _db_session()
    _seed_plan(db)

    normalized = validate_meeting_change_proposal(
        {
            "action": "update_subtask",
            "target": {"subtask_id": 11},
            "proposed": {"notes": "Updated note"},
            "evidence": ["Speaker 2: record the updated note."],
            "reason": "The meeting explicitly added the note.",
            "confidence": 0.75,
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized == {
        "action": "update_subtask",
        "target": {"project_id": 7, "parent_workstream_id": 1, "subtask_id": 11},
        "before": {
            "assignee": "Known assignee",
            "completion_criteria": "Old criterion",
            "notes": "Old note",
            "plan_time": "2026-08-01",
            "status": "In progress",
            "title": "Existing subtask",
        },
        "proposed": {"notes": "Updated note"},
        "evidence": ["Speaker 2: record the updated note."],
        "reason": "The meeting explicitly added the note.",
        "confidence": 0.75,
        "validation": {"state": "ready", "errors": []},
    }


def test_empty_update_proposed_fields_are_blocked_for_both_target_types():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)

    workstream = validate_meeting_change_proposal(
        {
            "action": "update_workstream",
            "target": {"workstream_id": 1},
            "proposed": {},
            "evidence": ["Speaker 1: review the workstream."],
            "reason": "The workstream was discussed.",
            "confidence": 0.5,
        },
        snapshot,
    )
    subtask = validate_meeting_change_proposal(
        {
            "action": "update_subtask",
            "target": {"subtask_id": 11},
            "proposed": {},
            "evidence": ["Speaker 1: review the subtask."],
            "reason": "The subtask was discussed.",
            "confidence": 0.5,
        },
        snapshot,
    )

    assert workstream["validation"] == {
        "state": "blocked",
        "errors": ["update proposal must include at least one allowed field"],
    }
    assert subtask["validation"] == {
        "state": "blocked",
        "errors": ["update proposal must include at least one allowed field"],
    }


def test_unknown_owner_is_blocked_without_mutating_the_plan():
    db = _db_session()
    _seed_plan(db)
    before_count = db.query(models.Task).count()

    normalized = validate_meeting_change_proposal(
        {
            "action": "create_workstream",
            "target": {},
            "proposed": {"key_task": "New workstream", "owner": "New owner"},
            "evidence": ["Speaker 2: New owner will own the workstream."],
            "reason": "The meeting explicitly assigned the workstream.",
            "confidence": 0.8,
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": ["owner requires review for nonmember or inactive names: New owner"],
    }
    assert db.query(models.Task).count() == before_count


def test_unknown_assignee_is_blocked_without_mutating_the_plan():
    db = _db_session()
    active, _deleted = _seed_plan(db)
    before_count = db.query(models.SubTask).count()

    normalized = validate_meeting_change_proposal(
        {
            "action": "create_subtask",
            "target": {"parent_workstream_id": active.id},
            "proposed": {"title": "New follow-up", "assignee": "New person"},
            "evidence": ["Speaker 2: New person will own the follow-up."],
            "reason": "The meeting explicitly assigned the follow-up.",
            "confidence": 0.8,
        },
        build_meeting_plan_snapshot(7, db),
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": ["assignee requires review for nonmember or inactive names: New person"],
    }
    assert db.query(models.SubTask).count() == before_count


def test_forged_evidence_excerpt_is_blocked_when_transcript_is_supplied():
    db = _db_session()
    _seed_plan(db)
    proposal = _valid_update_workstream()
    proposal["evidence"] = ["Speaker 9: approve an unmentioned change."]

    normalized = validate_meeting_change_proposal(
        proposal,
        build_meeting_plan_snapshot(7, db),
        transcript_text="Speaker 1: use the approved standard.",
    )

    assert normalized["validation"] == {
        "state": "blocked",
        "errors": ["evidence excerpts must occur in transcript_text"],
    }


def test_missing_or_blank_transcript_blocks_proposals():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)

    missing = _validate_meeting_change_proposal(_valid_update_workstream(), snapshot)
    blank = _validate_meeting_change_proposal(
        _valid_update_workstream(),
        snapshot,
        transcript_text="   ",
    )

    assert missing["validation"] == {
        "state": "blocked",
        "errors": ["transcript_text must be a non-empty string"],
    }
    assert blank["validation"] == {
        "state": "blocked",
        "errors": ["transcript_text must be a non-empty string"],
    }


def test_member_names_use_active_project_members_including_roles_without_tasks():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)

    assert snapshot["member_names"] == [
        "Known assignee",
        "Known collaborator",
        "Known coordinator",
        "Known owner",
        "Member without task",
    ]
    normalized = validate_meeting_change_proposal(
        {
            "action": "update_workstream",
            "target": {"workstream_id": 1},
            "proposed": {
                "owner": "Member without task",
                "coordinator": "Known coordinator",
                "collaborators": "Known owner, Known collaborator，Member without task",
            },
            "evidence": ["Speaker 1: assign the listed project members."],
            "reason": "The meeting explicitly reassigned the workstream.",
            "confidence": 0.9,
        },
        snapshot,
    )

    assert normalized["validation"] == {"state": "ready", "errors": []}


def test_inactive_or_nonmember_people_are_blocked_for_all_workstream_people_fields():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)

    inactive_owner = validate_meeting_change_proposal(
        {
            "action": "update_workstream",
            "target": {"workstream_id": 1},
            "proposed": {"owner": "Inactive member"},
            "evidence": ["Speaker 1: assign an inactive member."],
            "reason": "The assignment was discussed.",
            "confidence": 0.5,
        },
        snapshot,
    )
    nonmember_coordinator = validate_meeting_change_proposal(
        {
            "action": "update_workstream",
            "target": {"workstream_id": 1},
            "proposed": {"coordinator": "Active nonmember"},
            "evidence": ["Speaker 1: appoint an outsider."],
            "reason": "The appointment was discussed.",
            "confidence": 0.5,
        },
        snapshot,
    )
    mixed_collaborators = validate_meeting_change_proposal(
        {
            "action": "update_workstream",
            "target": {"workstream_id": 1},
            "proposed": {"collaborators": "Known owner, Inactive member，Active nonmember"},
            "evidence": ["Speaker 1: assign the listed collaborators."],
            "reason": "The collaboration was discussed.",
            "confidence": 0.5,
        },
        snapshot,
    )

    assert inactive_owner["validation"] == {
        "state": "blocked",
        "errors": ["owner requires review for nonmember or inactive names: Inactive member"],
    }
    assert nonmember_coordinator["validation"] == {
        "state": "blocked",
        "errors": ["coordinator requires review for nonmember or inactive names: Active nonmember"],
    }
    assert mixed_collaborators["validation"] == {
        "state": "blocked",
        "errors": [
            "collaborators requires review for nonmember or inactive names: Inactive member, Active nonmember"
        ],
    }


def test_database_length_and_status_constraints_block_proposals():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)
    base = {
        "action": "create_workstream",
        "target": {},
        "evidence": ["Speaker 1: create a constrained workstream."],
        "reason": "The workstream was explicitly created.",
        "confidence": 0.8,
    }

    too_long = validate_meeting_change_proposal(
        {
            **base,
            "proposed": {
                "key_task": "x" * 201,
                "owner": "Known owner",
            },
        },
        snapshot,
    )
    invalid_status = validate_meeting_change_proposal(
        {
            **base,
            "proposed": {
                "key_task": "Valid title",
                "owner": "Known owner",
                "status": "invented_status",
            },
        },
        snapshot,
    )

    assert too_long["validation"] == {
        "state": "blocked",
        "errors": ["proposed.key_task exceeds 200 characters"],
    }
    assert invalid_status["validation"] == {
        "state": "blocked",
        "errors": ["proposed.status is not an allowed task status"],
    }

    unsupported_english_alias = validate_meeting_change_proposal(
        {
            **base,
            "proposed": {
                "key_task": "Valid title",
                "owner": "Known owner",
                "status": "Completed",
            },
        },
        snapshot,
    )
    assert unsupported_english_alias["validation"] == {
        "state": "blocked",
        "errors": ["proposed.status is not an allowed task status"],
    }


def test_invalid_confidence_values_are_blocked():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)

    for value in (
        None,
        "not-a-number",
        float("nan"),
        float("inf"),
        float("-inf"),
        -0.01,
        1.01,
    ):
        proposal = _valid_update_workstream()
        proposal["confidence"] = value

        normalized = validate_meeting_change_proposal(proposal, snapshot)

        assert normalized["confidence"] == 0.0
        assert normalized["validation"] == {
            "state": "blocked",
            "errors": ["confidence must be a finite number between 0 and 1"],
        }


def test_proposed_field_output_has_stable_allowlist_order():
    db = _db_session()
    _seed_plan(db)
    snapshot = build_meeting_plan_snapshot(7, db)
    base = {
        "action": "update_workstream",
        "target": {"workstream_id": 1},
        "evidence": ["Speaker 1: update owner and status."],
        "reason": "The meeting explicitly updated both fields.",
        "confidence": 0.6,
    }

    first = validate_meeting_change_proposal(
        {**base, "proposed": {"status": "completed", "owner": "Known owner"}},
        snapshot,
    )
    second = validate_meeting_change_proposal(
        {**base, "proposed": {"owner": "Known owner", "status": "completed"}},
        snapshot,
    )

    assert list(first["proposed"]) == list(second["proposed"]) == ["owner", "status"]
    assert first["proposed"] == second["proposed"] == {
        "owner": "Known owner",
        "status": TS.S_COMPLETED,
    }

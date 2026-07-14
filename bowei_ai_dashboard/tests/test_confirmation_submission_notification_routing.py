"""Submission-level notification recipients and deep-link routing."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import (
    ceo_decide,
    coordinator_feedback,
    escalate_ceo,
    resubmit,
)
from app.services import notify
from tests.test_execution_submission_to_work_progress_flow import _make_session


PROJECT_A_ID = 1
PROJECT_B_ID = 2


def _person(person_id: int, name: str, *, system_role: str = "normal_member"):
    return models.Person(
        id=person_id,
        name=name,
        system_role=system_role,
        is_active=True,
    )


def _seed_notification_team(db):
    people = {
        "member_a": _person(1, "MEMBER-A"),
        "owner_a1": _person(2, "OWNER-A1"),
        "owner_a2": _person(3, "OWNER-A2"),
        "coord_a1": _person(4, "COORD-A1"),
        "coord_a2": _person(5, "COORD-A2"),
        "coach_a": _person(6, "COACH-A"),
        "ceo_system": _person(7, "CEO-SYSTEM", system_role="company_ceo"),
        "admin": _person(8, "ADMIN", system_role="super_admin"),
        "owner_b": _person(9, "OWNER-B"),
        "coord_b": _person(10, "COORD-B"),
        "coach_b": _person(11, "COACH-B"),
    }
    db.add_all(list(people.values()))
    db.flush()

    accounts = {}
    for key, person in people.items():
        username = f"account_{key}"
        accounts[key] = username
        db.add(
            models.Account(
                username=username,
                password_hash="x",
                person_id=person.id,
                status="active",
                is_tech_admin=False,
            )
        )

    db.add_all(
        [
            models.Project(
                id=PROJECT_A_ID,
                name="Project A",
                status="active",
                is_active=True,
            ),
            models.Project(
                id=PROJECT_B_ID,
                name="Project B",
                status="active",
                is_active=True,
            ),
        ]
    )
    db.flush()

    db.add_all(
        [
            models.ProjectMember(
                project_id=PROJECT_A_ID,
                person_id=people["member_a"].id,
                role="member",
            ),
            models.ProjectMember(
                project_id=PROJECT_A_ID,
                person_id=people["owner_a1"].id,
                role="owner",
            ),
            models.ProjectMember(
                project_id=PROJECT_A_ID,
                person_id=people["owner_a2"].id,
                role="owner",
            ),
            models.ProjectMember(
                project_id=PROJECT_A_ID,
                person_id=people["coord_a1"].id,
                role="coordinator",
            ),
            models.ProjectMember(
                project_id=PROJECT_A_ID,
                person_id=people["coord_a2"].id,
                role="coordinator",
            ),
            models.ProjectMember(
                project_id=PROJECT_A_ID,
                person_id=people["coach_a"].id,
                role="project_ceo",
            ),
            models.ProjectMember(
                project_id=PROJECT_B_ID,
                person_id=people["owner_b"].id,
                role="owner",
            ),
            models.ProjectMember(
                project_id=PROJECT_B_ID,
                person_id=people["coord_b"].id,
                role="coordinator",
            ),
            models.ProjectMember(
                project_id=PROJECT_B_ID,
                person_id=people["coach_b"].id,
                role="project_ceo",
            ),
        ]
    )
    db.commit()
    return {"people": people, "accounts": accounts}


def _submission(db, team, status: str, *, submitter_key: str = "member_a"):
    submitter = team["people"][submitter_key]
    row = models.UpdateSubmission(
        project_id=PROJECT_A_ID,
        submitter=submitter.name,
        submitter_id=submitter.id,
        source_type="人工录入",
        title="Project A submission",
        transcript_text="notification routing test",
        ai_result_json="{}",
        human_result_json=json.dumps({"task_reports": []}),
        confirm_status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _notifications(db, notification_type: str):
    return (
        db.query(models.Notification)
        .filter(models.Notification.type == notification_type)
        .order_by(models.Notification.id)
        .all()
    )


def _assert_exact_recipients(db, notification_type: str, expected_ids: set[int]):
    rows = _notifications(db, notification_type)
    assert [row.recipient_id for row in rows] == sorted(expected_ids)
    assert len(rows) == len(expected_ids)
    assert all(row.project_id == PROJECT_A_ID for row in rows)
    return rows


def _assert_submission_link(row, *, view: str, submission_id: int):
    assert row.link == (
        f"/work/confirmations?view={view}"
        f"&projectId={PROJECT_A_ID}&submissionId={submission_id}"
    )
    assert "cardIndex" not in row.link
    assert "/project/" not in row.link


def test_strict_owner_helper_filters_roles_and_preserves_legacy_helper():
    db = _make_session()
    team = _seed_notification_team(db)
    people = team["people"]

    assert notify.project_strict_owner_ids(PROJECT_A_ID, db) == [
        people["owner_a1"].id,
        people["owner_a2"].id,
    ]
    assert notify.project_owner_ids(PROJECT_A_ID, db) == [
        people["owner_a1"].id,
        people["owner_a2"].id,
        people["coord_a1"].id,
        people["coord_a2"].id,
    ]


def test_strict_owner_helper_deduplicates_person_ids_stably():
    class DuplicateOwnerQuery:
        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def all(self):
            return [
                SimpleNamespace(person_id=2),
                SimpleNamespace(person_id=2),
                SimpleNamespace(person_id=None),
                SimpleNamespace(person_id=3),
                SimpleNamespace(person_id=2),
            ]

    class DuplicateOwnerDb:
        def query(self, model):
            assert model is models.ProjectMember
            return DuplicateOwnerQuery()

    assert notify.project_strict_owner_ids(PROJECT_A_ID, DuplicateOwnerDb()) == [2, 3]


def test_resubmit_notifies_only_project_a_owners_with_exact_link():
    db = _make_session()
    team = _seed_notification_team(db)
    row = _submission(db, team, SS.S_RETURNED)

    resubmit(
        row.id,
        schemas.ResubmitRequest(
            supplement_note="updated",
            operator=team["accounts"]["member_a"],
        ),
        current_user=team["accounts"]["member_a"],
        db=db,
    )

    rows = _assert_exact_recipients(
        db,
        "submission_resubmitted",
        {team["people"]["owner_a1"].id, team["people"]["owner_a2"].id},
    )
    for notification in rows:
        _assert_submission_link(notification, view="all", submission_id=row.id)


def test_resubmit_does_not_notify_submitter_when_submitter_is_owner():
    db = _make_session()
    team = _seed_notification_team(db)
    row = _submission(db, team, SS.S_RETURNED, submitter_key="owner_a1")

    resubmit(
        row.id,
        schemas.ResubmitRequest(
            supplement_note="owner update",
            operator=team["accounts"]["owner_a1"],
        ),
        current_user=team["accounts"]["owner_a1"],
        db=db,
    )

    _assert_exact_recipients(
        db,
        "submission_resubmitted",
        {team["people"]["owner_a2"].id},
    )


def test_coordinator_feedback_notifies_only_project_a_owners():
    db = _make_session()
    team = _seed_notification_team(db)
    row = _submission(db, team, SS.S_WAITING_COORDINATOR)

    coordinator_feedback(
        row.id,
        schemas.WorkflowNoteRequest(
            note="coordinator note",
            operator=team["accounts"]["coord_a1"],
        ),
        current_user=team["accounts"]["coord_a1"],
        db=db,
    )

    rows = _assert_exact_recipients(
        db,
        "coordinator_feedback",
        {team["people"]["owner_a1"].id, team["people"]["owner_a2"].id},
    )
    for notification in rows:
        _assert_submission_link(notification, view="all", submission_id=row.id)


def test_coordinator_feedback_excludes_caller_who_is_also_an_owner():
    db = _make_session()
    team = _seed_notification_team(db)
    db.add(
        models.ProjectMember(
            project_id=PROJECT_A_ID,
            person_id=team["people"]["owner_a1"].id,
            role="coordinator",
        )
    )
    db.commit()
    row = _submission(db, team, SS.S_WAITING_COORDINATOR)

    coordinator_feedback(
        row.id,
        schemas.WorkflowNoteRequest(
            note="owner acting as coordinator",
            operator=team["accounts"]["owner_a1"],
        ),
        current_user=team["accounts"]["owner_a1"],
        db=db,
    )

    _assert_exact_recipients(
        db,
        "coordinator_feedback",
        {team["people"]["owner_a2"].id},
    )


def test_escalate_ceo_notifies_only_project_coach_with_exact_link():
    db = _make_session()
    team = _seed_notification_team(db)
    row = _submission(db, team, SS.S_PENDING_OWNER)

    escalate_ceo(
        row.id,
        schemas.WorkflowNoteRequest(
            note="coach decision needed",
            operator=team["accounts"]["owner_a1"],
        ),
        current_user=team["accounts"]["owner_a1"],
        db=db,
    )

    rows = _assert_exact_recipients(
        db,
        "escalate_ceo",
        {team["people"]["coach_a"].id},
    )
    _assert_submission_link(rows[0], view="ceo", submission_id=row.id)


def test_ceo_decide_notifies_only_project_a_owners_with_exact_link():
    db = _make_session()
    team = _seed_notification_team(db)
    row = _submission(db, team, SS.S_WAITING_CEO)

    result = ceo_decide(
        row.id,
        schemas.WorkflowNoteRequest(
            note="approved with guidance",
            operator=team["accounts"]["coach_a"],
        ),
        current_user=team["accounts"]["coach_a"],
        db=db,
    )

    rows = _assert_exact_recipients(
        db,
        "ceo_decided",
        {team["people"]["owner_a1"].id, team["people"]["owner_a2"].id},
    )
    for notification in rows:
        _assert_submission_link(notification, view="all", submission_id=row.id)
    assert result["submission"]["ceo_note"] == "approved with guidance"
    assert result["submission"]["confirm_status"] == SS.S_CEO_DECIDED

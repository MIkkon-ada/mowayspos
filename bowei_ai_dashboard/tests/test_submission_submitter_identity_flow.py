"""N4-P3-R3-FIX-2A: submission submitter identity compatibility tests."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import reject, resubmit, withdraw
from app.routers.updates import list_updates
from tests.test_execution_submission_to_work_progress_flow import _make_session


def _seed_team(db):
    submitter = models.Person(
        id=1, name="提交人姓名", system_role="normal_member", is_active=True
    )
    same_name_other = models.Person(
        id=2, name="提交人姓名", system_role="normal_member", is_active=True
    )
    owner = models.Person(
        id=3, name="项目负责人", system_role="normal_member", is_active=True
    )
    coordinator = models.Person(
        id=4, name="项目统筹", system_role="normal_member", is_active=True
    )
    coach = models.Person(
        id=5, name="企业教练", system_role="normal_member", is_active=True
    )
    company_ceo = models.Person(
        id=6, name="公司CEO", system_role="company_ceo", is_active=True
    )
    tech_admin = models.Person(
        id=7, name="技术管理员", system_role="super_admin", is_active=True
    )
    db.add_all(
        [
            submitter,
            same_name_other,
            owner,
            coordinator,
            coach,
            company_ceo,
            tech_admin,
            models.Account(
                username="submitter_account",
                password_hash="x",
                person_id=submitter.id,
                status="active",
            ),
            models.Account(
                username="other_account",
                password_hash="x",
                person_id=same_name_other.id,
                status="active",
            ),
            models.Account(
                username="owner",
                password_hash="x",
                person_id=owner.id,
                status="active",
            ),
            models.Account(
                username="coordinator",
                password_hash="x",
                person_id=coordinator.id,
                status="active",
            ),
            models.Account(
                username="coach",
                password_hash="x",
                person_id=coach.id,
                status="active",
            ),
            models.Account(
                username="company_ceo",
                password_hash="x",
                person_id=company_ceo.id,
                status="active",
            ),
            models.Account(
                username="tech_admin",
                password_hash="x",
                person_id=tech_admin.id,
                status="active",
                is_tech_admin=True,
            ),
        ]
    )
    db.flush()

    project = models.Project(id=1, name="身份测试项目", status="active", is_active=True)
    db.add(project)
    db.flush()
    db.add_all(
        [
            models.ProjectMember(project_id=1, person_id=submitter.id, role="member"),
            models.ProjectMember(project_id=1, person_id=same_name_other.id, role="member"),
            models.ProjectMember(project_id=1, person_id=owner.id, role="owner"),
            models.ProjectMember(project_id=1, person_id=coordinator.id, role="coordinator"),
            models.ProjectMember(project_id=1, person_id=coach.id, role="project_ceo"),
        ]
    )
    db.commit()
    return {
        "submitter": submitter,
        "same_name_other": same_name_other,
        "owner": owner,
        "coordinator": coordinator,
        "coach": coach,
        "company_ceo": company_ceo,
        "tech_admin": tech_admin,
        "project": project,
    }


def _submission(
    db,
    *,
    submitter: str,
    submitter_id: int | None,
    status: str = SS.S_NEW,
    title: str = "身份测试提交",
):
    row = models.UpdateSubmission(
        project_id=1,
        submitter=submitter,
        submitter_id=submitter_id,
        source_type="人工录入",
        title=title,
        transcript_text="身份测试",
        ai_result_json="{}",
        human_result_json=json.dumps({"task_reports": []}, ensure_ascii=False),
        confirm_status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _ids(rows):
    return {row["id"] for row in rows}


class TestMineQueryIdentity:
    def test_new_submission_matches_person_id_when_username_differs_from_name(self):
        db = _make_session()
        team = _seed_team(db)
        mine = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
        )

        rows = list_updates(mine=True, current_user="submitter_account", db=db)

        assert _ids(rows) == {mine.id}

    def test_new_submission_is_not_exposed_to_other_account_with_same_name(self):
        db = _make_session()
        team = _seed_team(db)
        mine = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
        )

        rows = list_updates(mine=True, current_user="other_account", db=db)

        assert mine.id not in _ids(rows)

    @pytest.mark.parametrize("legacy_submitter", ["submitter_account", "提交人姓名"])
    def test_legacy_submission_matches_username_or_person_name(self, legacy_submitter):
        db = _make_session()
        _seed_team(db)
        legacy = _submission(db, submitter=legacy_submitter, submitter_id=None)

        rows = list_updates(mine=True, current_user="submitter_account", db=db)

        assert _ids(rows) == {legacy.id}


class TestSubmitterNotificationIdentity:
    def test_reject_notification_uses_submitter_id_without_account_name_lookup(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
        )

        reject(
            row.id,
            schemas.RejectRequest(reason="请补充", operator="owner"),
            current_user="owner",
            db=db,
        )

        notification = db.query(models.Notification).filter_by(
            type="submission_rejected"
        ).one()
        assert notification.recipient_id == team["submitter"].id
        assert notification.recipient == team["submitter"].name

    @pytest.mark.parametrize(
        ("legacy_submitter", "expected_person_id"),
        [("submitter_account", 1), ("提交人姓名", 1)],
    )
    def test_reject_notification_preserves_legacy_string_resolution(
        self, legacy_submitter, expected_person_id
    ):
        db = _make_session()
        _seed_team(db)
        row = _submission(db, submitter=legacy_submitter, submitter_id=None)

        reject(
            row.id,
            schemas.RejectRequest(reason="请补充", operator="owner"),
            current_user="owner",
            db=db,
        )

        notification = db.query(models.Notification).filter_by(
            type="submission_rejected"
        ).one()
        assert notification.recipient_id == expected_person_id


class TestResubmitIdentity:
    def test_submitter_can_resubmit_by_person_id(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
            status=SS.S_RETURNED,
        )

        result = resubmit(
            row.id,
            schemas.ResubmitRequest(supplement_note="已补充"),
            current_user="submitter_account",
            db=db,
        )

        assert result["submission"]["confirm_status"] == SS.S_PENDING_OWNER

    def test_same_name_other_account_cannot_resubmit_new_submission(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
            status=SS.S_RETURNED,
        )

        with pytest.raises(HTTPException) as exc:
            resubmit(
                row.id,
                schemas.ResubmitRequest(),
                current_user="other_account",
                db=db,
            )

        assert exc.value.status_code == 403

    @pytest.mark.parametrize("legacy_submitter", ["submitter_account", "提交人姓名"])
    def test_legacy_submitter_can_resubmit_by_username_or_name(self, legacy_submitter):
        db = _make_session()
        _seed_team(db)
        row = _submission(
            db,
            submitter=legacy_submitter,
            submitter_id=None,
            status=SS.S_RETURNED,
        )

        result = resubmit(
            row.id,
            schemas.ResubmitRequest(),
            current_user="submitter_account",
            db=db,
        )

        assert result["submission"]["confirm_status"] == SS.S_PENDING_OWNER

    def test_tech_admin_does_not_gain_resubmit_permission(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
            status=SS.S_RETURNED,
        )

        with pytest.raises(HTTPException) as exc:
            resubmit(
                row.id,
                schemas.ResubmitRequest(operator="tech_admin"),
                current_user="tech_admin",
                db=db,
            )

        assert exc.value.status_code == 403


class TestWithdrawIdentity:
    def test_submitter_can_withdraw_by_person_id(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
        )

        result = withdraw(row.id, current_user="submitter_account", db=db)

        assert result["submission"]["confirm_status"] == SS.S_WITHDRAWN

    @pytest.mark.parametrize("legacy_submitter", ["submitter_account", "提交人姓名"])
    def test_legacy_submitter_can_withdraw_by_username_or_name(self, legacy_submitter):
        db = _make_session()
        _seed_team(db)
        row = _submission(db, submitter=legacy_submitter, submitter_id=None)

        result = withdraw(row.id, current_user="submitter_account", db=db)

        assert result["submission"]["confirm_status"] == SS.S_WITHDRAWN

    @pytest.mark.parametrize(
        "actor", ["other_account", "owner", "coordinator", "coach", "company_ceo"]
    )
    def test_non_submitter_roles_cannot_withdraw(self, actor):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
        )

        with pytest.raises(HTTPException) as exc:
            withdraw(row.id, current_user=actor, db=db)

        assert exc.value.status_code == 403

    def test_tech_admin_keeps_existing_withdraw_permission(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
        )

        result = withdraw(row.id, current_user="tech_admin", db=db)

        assert result["submission"]["confirm_status"] == SS.S_WITHDRAWN

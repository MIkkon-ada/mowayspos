"""N4-P3-FIX-1B: 单卡转统筹反馈闭环后端行为测试。"""
from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.domain import submission_status as SS
from app.routers import confirmations as confirmations_router
from app.routers.confirmations import (
    assign,
    confirm,
    confirm_task_card,
    counts,
    escalate_ceo,
    escalate_task_card_to_ceo,
    mark_unrecognized,
    pending,
    reject,
    reject_final,
    reject_task_card,
    save,
    transfer_coordinator,
    transfer_task_card_to_coordinator,
    withdraw,
)
from tests.test_confirmation_card_coach_flow import (
    _get_card_status,
    _seed_card_coach_team,
    _submit,
    _submit_two_cards,
)
from tests.test_confirmation_coordinator_flow import _seed_coordinator_team
from tests.test_execution_submission_to_work_progress_flow import _make_session


coordinator_feedback_task_card = getattr(
    confirmations_router,
    "coordinator_feedback_task_card",
    None,
)


def test_card_coordinator_feedback_post_route_is_registered():
    route = next(
        (
            item
            for item in confirmations_router.router.routes
            if item.path == "/api/confirmations/{submission_id}/cards/{card_index}/coordinator-feedback"
        ),
        None,
    )
    assert route is not None
    assert route.methods == {"POST"}


def _card_payload(title: str = "任务卡1", status: str = "") -> dict:
    report = {
        "title": title,
        "completed": f"{title}进展",
        "confirmation_status": status,
    }
    return report


def _make_card_submission(
    db,
    project_id: int = 1,
    *,
    statuses: tuple[str, ...] = ("", "pending"),
    title: str = "双卡提交",
) -> models.UpdateSubmission:
    data = {
        "summary": title,
        "task": {},
        "achievements": [],
        "issues": [],
        "task_reports": [
            _card_payload(f"任务卡{index + 1}", status)
            for index, status in enumerate(statuses)
        ],
    }
    row = models.UpdateSubmission(
        project_id=project_id,
        submitter="member",
        title=title,
        source_type="任务进展",
        transcript_text="测试进展",
        confirm_status=SS.S_PENDING_OWNER,
        ai_result_json=json.dumps(data, ensure_ascii=False),
        human_result_json=json.dumps(data, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    return row


def _add_project_two_coordinator(db) -> models.Person:
    person = models.Person(id=7, name="项目B统筹", system_role="normal_member", is_active=True)
    db.add_all([
        person,
        models.Account(
            username="coordinator_b",
            password_hash="x",
            person_id=person.id,
            status="active",
        ),
        models.ProjectMember(project_id=2, person_id=person.id, role="coordinator"),
    ])
    db.flush()
    return person


def _transfer_card(db, submission_id: int, card_index: int = 0, *, actor: str = "owner"):
    return transfer_task_card_to_coordinator(
        submission_id,
        card_index,
        schemas.WorkflowNoteRequest(note="请统筹评估", operator=actor),
        current_user=actor,
        db=db,
    )


def _feedback_card(db, submission_id: int, card_index: int = 0, *, actor: str = "coordinator"):
    return coordinator_feedback_task_card(
        submission_id,
        card_index,
        schemas.WorkflowNoteRequest(note="建议按计划推进", operator=actor),
        current_user=actor,
        db=db,
    )


class TestCardTransferToCoordinator:
    def test_owner_transfer_persists_request_fields_and_preserves_other_cards(self):
        db = _make_session()
        _seed_card_coach_team(db)
        sid = _submit_two_cards(db, _seedless_team(db))

        result = _transfer_card(db, sid)

        row = db.get(models.UpdateSubmission, sid)
        data = json.loads(row.human_result_json)
        report = data["task_reports"][0]
        assert result["submission"]["confirm_status"] == SS.S_PENDING_OWNER
        assert report["confirmation_status"] == "transferred_to_coordinator"
        assert report["confirmation_note"] == "请统筹评估"
        assert report["confirmation_operator"] == "owner"
        assert report["confirmation_at"]
        assert report["coordinator_request_note"] == "请统筹评估"
        assert report["coordinator_request_operator"] == "owner"
        assert report["coordinator_requested_at"]
        assert not data["task_reports"][1].get("confirmation_status")

    def test_tech_admin_can_transfer(self):
        db = _make_session()
        _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=("",))
        assert _transfer_card(db, row.id, actor="tech_admin")["ok"] is True

    @pytest.mark.parametrize("actor", ["member", "coordinator", "coach", "公司CEO"])
    def test_non_owner_roles_cannot_transfer(self, actor: str):
        db = _make_session()
        _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=("",))
        with pytest.raises(HTTPException) as exc:
            _transfer_card(db, row.id, actor=actor)
        assert exc.value.status_code == 403

    @pytest.mark.parametrize(
        "status",
        [
            "transferred_to_coordinator",
            "coordinator_given",
            "pending_ceo_decision",
            "ceo_decided",
            "confirmed",
            "returned",
        ],
    )
    def test_rejects_duplicate_or_non_transferable_card_status(self, status: str):
        db = _make_session()
        _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=(status,))
        with pytest.raises(HTTPException) as exc:
            _transfer_card(db, row.id)
        assert exc.value.status_code == 409

    def test_transfer_writes_precise_notification_and_log(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=("",))

        _transfer_card(db, row.id)

        notifications = db.query(models.Notification).filter(
            models.Notification.type == "confirmation_card_transferred_to_coordinator",
        ).all()
        assert len(notifications) == 1
        notification = notifications[0]
        assert notification.recipient_id == team["coordinator"].id
        assert notification.project_id == team["project"].id
        assert "双卡提交" in notification.body
        assert "第 1 张" in notification.body
        assert "任务卡1" in notification.body
        assert "请统筹评估" in notification.body
        assert notification.link == (
            f"/work/confirmations?view=coordinator&projectId=1"
            f"&submissionId={row.id}&cardIndex=0"
        )

        log = db.query(models.OperationLog).filter(
            models.OperationLog.action == "confirmation_card_forward_to_coordinator",
            models.OperationLog.target_id == row.id,
        ).one()
        after = json.loads(log.after_json)
        assert log.project_id == 1
        assert after == {
            "card_index": 0,
            "card_title": "任务卡1",
            "note": "请统筹评估",
            "project_id": 1,
        }


class TestCoordinatorCardPending:
    def test_more_than_500_unrelated_owner_items_cannot_hide_card_pending(self):
        db = _make_session()
        _seed_coordinator_team(db)
        target = _make_card_submission(db, statuses=("",), title="真实统筹待办")
        _transfer_card(db, target.id)
        target.updated_at = datetime(2020, 1, 1)
        for index in range(501):
            noise = _make_card_submission(db, statuses=("pending",), title=f"无关待确认{index}")
            noise.updated_at = datetime(2030, 1, 1)
        db.flush()

        result = pending(
            tab="coordinator",
            include_card_level=True,
            current_user="coordinator",
            db=db,
        )

        assert {item["id"] for item in result} == {target.id}
        assert counts(current_user="coordinator", db=db)["coordinator_total"] == 1

    def test_include_card_level_controls_card_items_and_returns_all_indices_once(self):
        db = _make_session()
        _seed_coordinator_team(db)
        row = _make_card_submission(db, statuses=("", "", "pending"))
        _transfer_card(db, row.id, 0)
        _transfer_card(db, row.id, 2)

        assert pending(
            tab="coordinator", include_card_level=False,
            current_user="coordinator", db=db,
        ) == []
        result = pending(
            tab="coordinator", include_card_level=True,
            current_user="coordinator", db=db,
        )
        assert len(result) == 1
        assert result[0]["id"] == row.id
        assert result[0]["coordinator_decision_scope"] == "card"
        assert result[0]["pending_coordinator_card_indices"] == [0, 2]

    @pytest.mark.parametrize("actor", ["owner", "coach", "公司CEO"])
    def test_card_pending_is_hidden_from_non_coordinator_reviewers(self, actor: str):
        db = _make_session()
        _seed_coordinator_team(db)
        row = _make_card_submission(db, statuses=("",))
        _transfer_card(db, row.id)
        assert pending(
            tab="coordinator", include_card_level=True,
            current_user=actor, db=db,
        ) == []

    def test_member_cannot_open_coordinator_pending(self):
        db = _make_session()
        _seed_coordinator_team(db)
        row = _make_card_submission(db, statuses=("",))
        _transfer_card(db, row.id)
        with pytest.raises(HTTPException) as exc:
            pending(
                tab="coordinator", include_card_level=True,
                current_user="member", db=db,
            )
        assert exc.value.status_code == 403

    def test_coordinator_only_sees_own_project_and_tech_admin_sees_all(self):
        db = _make_session()
        _seed_coordinator_team(db)
        own = _make_card_submission(db, project_id=1, statuses=("",), title="项目A")
        other = _make_card_submission(db, project_id=2, statuses=("",), title="项目B")
        _transfer_card(db, own.id)
        _transfer_card(db, other.id, actor="tech_admin")

        coord_result = pending(
            tab="coordinator", include_card_level=True,
            current_user="coordinator", db=db,
        )
        admin_result = pending(
            tab="coordinator", include_card_level=True,
            current_user="tech_admin", db=db,
        )
        assert {item["id"] for item in coord_result} == {own.id}
        assert {item["id"] for item in admin_result} == {own.id, other.id}


class TestCoordinatorTotalWithCards:
    def test_counts_are_scoped_per_project_and_tech_admin_sees_all(self):
        db = _make_session()
        _seed_coordinator_team(db)
        _add_project_two_coordinator(db)
        project_a = _make_card_submission(db, project_id=1, statuses=("",), title="项目A待办")
        project_b = _make_card_submission(db, project_id=2, statuses=("",), title="项目B待办")
        _transfer_card(db, project_a.id)
        _transfer_card(db, project_b.id)

        assert counts(current_user="coordinator", db=db)["coordinator_total"] == 1
        assert counts(current_user="coordinator_b", db=db)["coordinator_total"] == 1
        assert counts(current_user="tech_admin", db=db)["coordinator_total"] == 2
        assert counts(current_user="owner", db=db)["coordinator_total"] == 0
        assert counts(current_user="coach", db=db)["coordinator_total"] == 0
        assert counts(current_user="公司CEO", db=db)["coordinator_total"] == 0

    def test_multiple_pending_cards_count_as_one_submission(self):
        db = _make_session()
        _seed_coordinator_team(db)
        row = _make_card_submission(db, statuses=("", ""))
        _transfer_card(db, row.id, 0)
        _transfer_card(db, row.id, 1)
        assert counts(current_user="coordinator", db=db)["coordinator_total"] == 1

    def test_submission_and_card_scopes_are_counted_by_unique_submission(self):
        db = _make_session()
        _seed_coordinator_team(db)
        submission_scope = _make_card_submission(db, statuses=("",), title="整条")
        submission_scope.confirm_status = SS.S_WAITING_COORDINATOR
        card_scope = _make_card_submission(db, statuses=("",), title="单卡")
        _transfer_card(db, card_scope.id)
        db.flush()

        result = pending(
            tab="coordinator", include_card_level=True,
            current_user="coordinator", db=db,
        )
        scopes = {item["id"]: item["coordinator_decision_scope"] for item in result}
        assert scopes == {submission_scope.id: "submission", card_scope.id: "card"}
        assert counts(current_user="coordinator", db=db)["coordinator_total"] == 2


class TestCoordinatorCardFeedback:
    def test_feedback_notification_goes_only_to_owner_not_other_coordinators(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        second_coordinator = models.Person(
            id=7,
            name="第二统筹",
            system_role="normal_member",
            is_active=True,
        )
        db.add_all([
            second_coordinator,
            models.Account(
                username="coordinator_2",
                password_hash="x",
                person_id=second_coordinator.id,
                status="active",
            ),
            models.ProjectMember(
                project_id=1,
                person_id=second_coordinator.id,
                role="coordinator",
            ),
            models.ProjectMember(
                project_id=1,
                person_id=team["owner"].id,
                role="coordinator",
            ),
        ])
        row = _make_card_submission(db, statuses=("",))
        _transfer_card(db, row.id)

        _feedback_card(db, row.id)

        notifications = db.query(models.Notification).filter(
            models.Notification.type == "confirmation_card_coordinator_feedback",
        ).all()
        assert len(notifications) == 1
        assert notifications[0].recipient_id == team["owner"].id

    def test_coordinator_from_another_project_cannot_feedback(self):
        db = _make_session()
        _seed_coordinator_team(db)
        _add_project_two_coordinator(db)
        row = _make_card_submission(db, project_id=2, statuses=("",))
        _transfer_card(db, row.id)

        with pytest.raises(HTTPException) as exc:
            _feedback_card(db, row.id, actor="coordinator")
        assert exc.value.status_code == 403
        assert _feedback_card(db, row.id, actor="coordinator_b")["ok"] is True

    def test_coordinator_feedback_persists_fields_preserves_request_and_notifies_owner(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit_two_cards(db, team)
        _transfer_card(db, sid)

        result = _feedback_card(db, sid)

        row = db.get(models.UpdateSubmission, sid)
        data = json.loads(row.human_result_json)
        report = data["task_reports"][0]
        assert result["submission"]["confirm_status"] == SS.S_PENDING_OWNER
        assert report["confirmation_status"] == "coordinator_given"
        assert report["coordinator_note"] == "建议按计划推进"
        assert report["coordinator_operator"] == "coordinator"
        assert report["coordinator_feedback_at"]
        assert report["coordinator_request_note"] == "请统筹评估"
        assert report["coordinator_request_operator"] == "owner"
        assert report["coordinator_requested_at"]
        assert not data["task_reports"][1].get("confirmation_status")

        notification = db.query(models.Notification).filter(
            models.Notification.type == "confirmation_card_coordinator_feedback",
        ).one()
        assert notification.recipient_id == team["owner"].id
        assert notification.link == (
            f"/work/confirmations?view=all&projectId=1"
            f"&submissionId={sid}&cardIndex=0"
        )
        assert "第 1 张" in notification.body
        assert "任务卡1" in notification.body
        assert "建议按计划推进" in notification.body

        log = db.query(models.OperationLog).filter(
            models.OperationLog.action == "confirmation_card_coordinator_feedback",
            models.OperationLog.target_id == sid,
        ).one()
        assert json.loads(log.after_json) == {
            "card_index": 0,
            "card_title": "任务卡1",
            "note": "建议按计划推进",
            "project_id": 1,
        }

    def test_tech_admin_can_feedback(self):
        db = _make_session()
        _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=("",))
        _transfer_card(db, row.id)
        assert _feedback_card(db, row.id, actor="tech_admin")["ok"] is True

    @pytest.mark.parametrize("actor", ["owner", "member", "coach", "公司CEO"])
    def test_non_coordinator_roles_cannot_feedback(self, actor: str):
        db = _make_session()
        _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=("",))
        _transfer_card(db, row.id)
        with pytest.raises(HTTPException) as exc:
            _feedback_card(db, row.id, actor=actor)
        assert exc.value.status_code == 403

    def test_wrong_card_status_returns_409(self):
        db = _make_session()
        _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=("pending",))
        with pytest.raises(HTTPException) as exc:
            _feedback_card(db, row.id)
        assert exc.value.status_code == 409

    def test_wrong_submission_status_returns_409(self):
        db = _make_session()
        _seed_card_coach_team(db)
        row = _make_card_submission(db, statuses=("transferred_to_coordinator",))
        row.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()
        with pytest.raises(HTTPException) as exc:
            _feedback_card(db, row.id)
        assert exc.value.status_code == 409


class TestPendingCoordinatorBypassProtection:
    def test_confirming_another_card_cannot_erase_pending_coordinator_state(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit_two_cards(db, team)
        _transfer_card(db, sid, 0)
        row = db.get(models.UpdateSubmission, sid)
        forged = json.loads(row.human_result_json)
        forged["task_reports"][0].pop("confirmation_status", None)
        forged["task_reports"][0].pop("coordinator_request_note", None)

        result = confirm_task_card(
            sid,
            1,
            schemas.ConfirmRequest(operator="owner", human_result=forged),
            current_user="owner",
            db=db,
        )

        assert result["ok"] is True
        persisted = json.loads(db.get(models.UpdateSubmission, sid).human_result_json)
        assert persisted["task_reports"][0]["confirmation_status"] == "transferred_to_coordinator"
        assert persisted["task_reports"][0]["coordinator_request_note"] == "请统筹评估"

    def test_confirming_feedback_card_preserves_coordinator_history(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        _transfer_card(db, sid)
        _feedback_card(db, sid)
        row = db.get(models.UpdateSubmission, sid)
        forged = json.loads(row.human_result_json)
        for field in (
            "coordinator_request_note",
            "coordinator_request_operator",
            "coordinator_requested_at",
            "coordinator_note",
            "coordinator_operator",
            "coordinator_feedback_at",
        ):
            forged["task_reports"][0].pop(field, None)

        confirm_task_card(
            sid,
            0,
            schemas.ConfirmRequest(operator="owner", human_result=forged),
            current_user="owner",
            db=db,
        )

        report = json.loads(db.get(models.UpdateSubmission, sid).human_result_json)["task_reports"][0]
        assert report["confirmation_status"] == "confirmed"
        assert report["coordinator_request_note"] == "请统筹评估"
        assert report["coordinator_note"] == "建议按计划推进"
        assert report["coordinator_operator"] == "coordinator"

    def test_pending_card_blocks_owner_card_actions(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        _transfer_card(db, sid)

        operations = [
            lambda: confirm_task_card(
                sid, 0, schemas.ConfirmRequest(operator="owner"),
                current_user="owner", db=db,
            ),
            lambda: reject_task_card(
                sid, 0, schemas.RejectRequest(reason="退回", operator="owner"),
                current_user="owner", db=db,
            ),
            lambda: escalate_task_card_to_ceo(
                sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
                current_user="owner", db=db,
            ),
        ]
        for operation in operations:
            with pytest.raises(HTTPException) as exc:
                operation()
            assert exc.value.status_code == 409

    @pytest.mark.parametrize(
        ("operation", "actor"),
        [
            ("save", "owner"),
            ("confirm", "owner"),
            ("reject", "owner"),
            ("transfer", "owner"),
            ("escalate", "owner"),
            ("withdraw", "tech_admin"),
            ("reject_final", "owner"),
            ("mark_unrecognized", "owner"),
            ("assign", "owner"),
        ],
    )
    def test_pending_card_blocks_submission_actions(self, operation: str, actor: str):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        _transfer_card(db, sid)
        row = db.get(models.UpdateSubmission, sid)
        data = json.loads(row.human_result_json)
        calls = {
            "save": lambda: save(
                sid, schemas.ConfirmationSaveRequest(human_result=data),
                current_user=actor, db=db,
            ),
            "confirm": lambda: confirm(
                sid, schemas.ConfirmRequest(operator=actor),
                current_user=actor, db=db,
            ),
            "reject": lambda: reject(
                sid, schemas.RejectRequest(reason="退回", operator=actor),
                current_user=actor, db=db,
            ),
            "transfer": lambda: transfer_coordinator(
                sid, schemas.WorkflowNoteRequest(note="整条转交", operator=actor),
                current_user=actor, db=db,
            ),
            "escalate": lambda: escalate_ceo(
                sid, schemas.WorkflowNoteRequest(note="上报", operator=actor),
                current_user=actor, db=db,
            ),
            "withdraw": lambda: withdraw(sid, current_user=actor, db=db),
            "reject_final": lambda: reject_final(
                sid, schemas.RejectRequest(reason="不入库", operator=actor),
                current_user=actor, db=db,
            ),
            "mark_unrecognized": lambda: mark_unrecognized(
                sid, schemas.RejectRequest(reason="人工处理", operator=actor),
                current_user=actor, db=db,
            ),
            "assign": lambda: assign(
                sid, schemas.AssignRequest(assignee="项目负责人", operator=actor),
                current_user=actor, db=db,
            ),
        }
        with pytest.raises(HTTPException) as exc:
            calls[operation]()
        assert exc.value.status_code == 409

    @pytest.mark.parametrize("action", ["confirm", "reject", "escalate"])
    def test_owner_can_continue_after_feedback(self, action: str):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team, transcript_text=f"反馈后{action}")
        _transfer_card(db, sid)
        _feedback_card(db, sid)

        if action == "confirm":
            result = confirm_task_card(
                sid, 0, schemas.ConfirmRequest(operator="owner"),
                current_user="owner", db=db,
            )
            assert result["ok"] is True
            assert _get_card_status(db, sid, 0) == "confirmed"
        elif action == "reject":
            result = reject_task_card(
                sid, 0, schemas.RejectRequest(reason="补充", operator="owner"),
                current_user="owner", db=db,
            )
            assert result["ok"] is True
            assert _get_card_status(db, sid, 0) == "returned"
        else:
            result = escalate_task_card_to_ceo(
                sid, 0, schemas.WorkflowNoteRequest(note="请教练决策", operator="owner"),
                current_user="owner", db=db,
            )
            assert result["ok"] is True
            assert _get_card_status(db, sid, 0) == "pending_ceo_decision"


def _seedless_team(db):
    """Return the already-seeded project objects expected by _submit_two_cards."""
    return {
        "project": db.get(models.Project, 1),
        "subtask": db.get(models.SubTask, 1),
    }

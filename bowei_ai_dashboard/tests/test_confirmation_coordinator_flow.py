"""N4-P3-FIX-1A: 整条提交统筹反馈闭环 — 后端行为测试。

覆盖：
- coordinator tab 只返回 WAITING_COORDINATOR_FEEDBACK
- coordinator 只看到自己负责项目
- 两个项目中只担任项目A coordinator → 只看到项目A
- 纯 company_ceo → 空
- owner → 空
- project_ceo → 空
- tech_admin → 全部
- coordinator_total 与列表唯一 submission 数一致
- owner 转统筹后 coordinator 收到通知
- coordinator 反馈后状态为 S_COORDINATOR_GIVEN
- 非 coordinator 调用返回 403
- 错误状态调用返回 409
"""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import (
    transfer_coordinator,
    coordinator_feedback,
    pending,
    counts,
)
from tests.test_execution_submission_to_work_progress_flow import _make_session


# ── 种子数据 ──────────────────────────────────────────────────────

def _seed_coordinator_team(db):
    """项目团队：owner + coordinator + project_ceo + member + tech_admin + company_ceo。"""
    owner_p = models.Person(id=1, name="项目负责人", system_role="normal_member", is_active=True)
    coord_p = models.Person(id=2, name="统筹人", system_role="normal_member", is_active=True)
    coach_p = models.Person(id=3, name="企业教练", system_role="normal_member", is_active=True)
    member_p = models.Person(id=4, name="普通成员", system_role="normal_member", is_active=True)
    tech_p = models.Person(id=5, name="技术管理员", system_role="super_admin", is_active=True)
    ceo_p = models.Person(id=6, name="公司CEO", system_role="company_ceo", is_active=True)

    db.add_all([
        owner_p, coord_p, coach_p, member_p, tech_p, ceo_p,
        models.Account(username="owner", password_hash="x", person_id=owner_p.id, status="active"),
        models.Account(username="coordinator", password_hash="x", person_id=coord_p.id, status="active"),
        models.Account(username="coach", password_hash="x", person_id=coach_p.id, status="active"),
        models.Account(username="member", password_hash="x", person_id=member_p.id, status="active"),
        models.Account(username="tech_admin", password_hash="x", person_id=tech_p.id, status="active", is_tech_admin=True),
        models.Account(username="公司CEO", password_hash="x", person_id=ceo_p.id, status="active"),
    ])
    db.flush()

    # 项目 A：coordinator 担任 coordinator 的项目
    project_a = models.Project(id=1, name="项目A", status="active")
    # 项目 B：coordinator 不担任 coordinator
    project_b = models.Project(id=2, name="项目B", status="active")
    db.add_all([project_a, project_b])
    db.flush()

    db.add_all([
        # 项目 A
        models.ProjectMember(project_id=1, person_id=owner_p.id, role="owner"),
        models.ProjectMember(project_id=1, person_id=coord_p.id, role="coordinator"),
        models.ProjectMember(project_id=1, person_id=coach_p.id, role="project_ceo"),
        models.ProjectMember(project_id=1, person_id=member_p.id, role="member"),
        # 项目 B：coordinator 不在其中
        models.ProjectMember(project_id=2, person_id=owner_p.id, role="owner"),
        models.ProjectMember(project_id=2, person_id=coach_p.id, role="project_ceo"),
        models.ProjectMember(project_id=2, person_id=member_p.id, role="member"),
    ])
    db.flush()

    return {
        "owner": owner_p,
        "coordinator": coord_p,
        "coach": coach_p,
        "member": member_p,
        "tech_admin": tech_p,
        "ceo": ceo_p,
        "project_a": project_a,
        "project_b": project_b,
    }


def _make_submission(db, project_id: int, submitter: str, title: str = "测试提交") -> models.UpdateSubmission:
    """创建一条初始状态 submission。"""
    sub = models.UpdateSubmission(
        id=None,
        project_id=project_id,
        submitter=submitter,
        title=title,
        source_type="语音更新",
        transcript_text="",
        confirm_status=SS.S_NEW,
        ai_result_json=json.dumps({"summary": title, "task": {}, "achievements": [], "issues": []}),
        human_result_json=json.dumps({
            "summary": title, "task": {}, "achievements": [], "issues": [],
            "task_reports": [],
        }),
    )
    db.add(sub)
    db.flush()
    return sub


def _make_submission_owner_actionable(db, project_id: int) -> models.UpdateSubmission:
    """创建一条 S_PENDING_OWNER 状态的提交（owner 可操作）。"""
    sub = _make_submission(db, project_id, "普通成员")
    sub.confirm_status = SS.S_PENDING_OWNER
    db.flush()
    return sub


# ── coordinator tab 查询 ──────────────────────────────────────────

class TestCoordinatorTabQuery:
    """测试 coordinator tab 只返回 WAITING_COORDINATOR_FEEDBACK。"""

    def test_coordinator_sees_only_own_projects(self):
        """coordinator 只看到自己负责项目。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)

        # 项目 A：WAITING_COORDINATOR
        sub_a = _make_submission(db, 1, "普通成员")
        sub_a.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        # 项目 B：WAITING_COORDINATOR（coordinator 不负责）
        sub_b = _make_submission(db, 2, "普通成员")
        sub_b.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = pending(
            tab="coordinator",
            project_id=None,
            current_user="coordinator",
            db=db,
        )
        assert len(result) == 1
        assert result[0]["id"] == sub_a.id

    def test_owner_sees_empty(self):
        """owner 看到空列表。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = pending(tab="coordinator", project_id=None, current_user="owner", db=db)
        assert len(result) == 0

    def test_project_ceo_sees_empty(self):
        """project_ceo 看到空列表。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = pending(tab="coordinator", project_id=None, current_user="coach", db=db)
        assert len(result) == 0

    def test_company_ceo_sees_empty(self):
        """纯 company_ceo 看到空列表。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = pending(tab="coordinator", project_id=None, current_user="公司CEO", db=db)
        assert len(result) == 0

    def test_tech_admin_sees_all(self):
        """tech_admin 看到全部项目。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)

        sub_a = _make_submission(db, 1, "普通成员")
        sub_a.confirm_status = SS.S_WAITING_COORDINATOR
        sub_b = _make_submission(db, 2, "普通成员")
        sub_b.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = pending(tab="coordinator", project_id=None, current_user="tech_admin", db=db)
        assert len(result) == 2
        ids = {r["id"] for r in result}
        assert sub_a.id in ids
        assert sub_b.id in ids

    def test_only_returns_waiting_coordinator_feedback(self):
        """coordinator tab 只返回 WAITING_COORDINATOR_FEEDBACK 状态。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)

        sub_coord = _make_submission(db, 1, "普通成员")
        sub_coord.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        sub_other = _make_submission(db, 1, "普通成员")
        sub_other.confirm_status = SS.S_NEW
        db.flush()

        result = pending(tab="coordinator", project_id=None, current_user="coordinator", db=db)
        assert len(result) == 1
        assert result[0]["id"] == sub_coord.id

    def test_member_sees_empty(self):
        """member 无法访问确认中心，返回 403。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        with pytest.raises(HTTPException) as exc:
            pending(tab="coordinator", project_id=None, current_user="member", db=db)
        assert exc.value.status_code == 403


# ── coordinator_total 计数 ────────────────────────────────────────

class TestCoordinatorTotal:
    """测试 coordinator_total 与列表唯一 submission 数一致。"""

    def test_coordinator_total_matches_pending_count(self):
        """仅当前 coordinator 在项目 A 中看到 1 条待办。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)

        sub_a = _make_submission(db, 1, "普通成员")
        sub_a.confirm_status = SS.S_WAITING_COORDINATOR
        sub_b = _make_submission(db, 2, "普通成员")
        sub_b.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = counts(current_user="coordinator", db=db)
        assert result.get("coordinator_total") == 1

    def test_owner_coordinator_total_zero(self):
        """owner 的 coordinator_total 为 0。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = counts(current_user="owner", db=db)
        assert result.get("coordinator_total") == 0

    def test_project_ceo_coordinator_total_zero(self):
        """project_ceo 的 coordinator_total 为 0。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = counts(current_user="coach", db=db)
        assert result.get("coordinator_total") == 0

    def test_company_ceo_coordinator_total_zero(self):
        """纯 company_ceo 的 coordinator_total 为 0。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = counts(current_user="公司CEO", db=db)
        assert result.get("coordinator_total") == 0

    def test_member_coordinator_total_zero(self):
        """member 无法访问确认中心，counts 返回 403。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        with pytest.raises(HTTPException) as exc:
            counts(current_user="member", db=db)
        assert exc.value.status_code == 403

    def test_tech_admin_coordinator_total_all(self):
        """tech_admin 的 coordinator_total 统计全部项目。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)

        sub_a = _make_submission(db, 1, "普通成员")
        sub_a.confirm_status = SS.S_WAITING_COORDINATOR
        sub_b = _make_submission(db, 2, "普通成员")
        sub_b.confirm_status = SS.S_WAITING_COORDINATOR
        db.flush()

        result = counts(current_user="tech_admin", db=db)
        assert result.get("coordinator_total") == 2


# ── transfer_coordinator 通知 ─────────────────────────────────────

class TestTransferCoordinatorNotification:
    """测试 owner 转统筹后 coordinator 收到通知。"""

    def test_notification_sent_to_coordinator(self):
        """转统筹后 coordinator 收到通知，link 包含正确参数。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission_owner_actionable(db, 1)

        payload = schemas.WorkflowNoteRequest(note="请协调人看看", operator="owner")
        transfer_coordinator(submission_id=sub.id, payload=payload, current_user="owner", db=db)

        # 检查通知
        notifs = db.query(models.Notification).filter(
            models.Notification.type == "submission_transferred_to_coordinator",
        ).all()
        assert len(notifs) == 1
        n = notifs[0]
        assert n.recipient_id == seed["coordinator"].id
        assert n.project_id == 1
        link = n.link or ""
        assert "view=coordinator" in link
        assert "projectId=1" in link
        assert f"submissionId={sub.id}" in link

    def test_submission_status_after_transfer(self):
        """转统筹后状态为 S_WAITING_COORDINATOR。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission_owner_actionable(db, 1)

        payload = schemas.WorkflowNoteRequest(note="请审核", operator="owner")
        result = transfer_coordinator(submission_id=sub.id, payload=payload, current_user="owner", db=db)

        updated = result["submission"]
        assert updated["confirm_status"] == SS.S_WAITING_COORDINATOR


# ── coordinator_feedback ──────────────────────────────────────────

class TestCoordinatorFeedback:
    """测试 coordinator 反馈。"""

    def test_feedback_changes_status(self):
        """coordinator 反馈后状态为 S_COORDINATOR_GIVEN。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission_owner_actionable(db, 1)

        # 先转统筹
        payload = schemas.WorkflowNoteRequest(note="请审核", operator="owner")
        transfer_coordinator(submission_id=sub.id, payload=payload, current_user="owner", db=db)

        # coordinator 反馈
        feedback_payload = schemas.WorkflowNoteRequest(note="同意，建议推进", operator="coordinator")
        result = coordinator_feedback(submission_id=sub.id, payload=feedback_payload, current_user="coordinator", db=db)

        updated = result["submission"]
        assert updated["confirm_status"] == SS.S_COORDINATOR_GIVEN

    def test_coordinator_note_saved(self):
        """coordinator_note 正确保存。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission_owner_actionable(db, 1)

        payload = schemas.WorkflowNoteRequest(note="请审核", operator="owner")
        transfer_coordinator(submission_id=sub.id, payload=payload, current_user="owner", db=db)

        feedback_payload = schemas.WorkflowNoteRequest(note="我的统筹意见", operator="coordinator")
        result = coordinator_feedback(submission_id=sub.id, payload=feedback_payload, current_user="coordinator", db=db)

        updated = result["submission"]
        assert updated["coordinator_note"] == "我的统筹意见"

    def test_owner_receives_notification(self):
        """coordinator 反馈后 owner 收到通知，link 正确。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission_owner_actionable(db, 1)

        payload = schemas.WorkflowNoteRequest(note="请审核", operator="owner")
        transfer_coordinator(submission_id=sub.id, payload=payload, current_user="owner", db=db)

        feedback_payload = schemas.WorkflowNoteRequest(note="反馈意见", operator="coordinator")
        coordinator_feedback(submission_id=sub.id, payload=feedback_payload, current_user="coordinator", db=db)

        notifs = db.query(models.Notification).filter(
            models.Notification.type == "coordinator_feedback",
        ).all()
        assert len(notifs) == 1
        n = notifs[0]
        assert n.recipient_id == seed["owner"].id
        assert n.project_id == 1
        link = n.link or ""
        assert "view=all" in link
        assert "projectId=1" in link
        assert f"submissionId={sub.id}" in link

    def test_non_coordinator_gets_403(self):
        """非 coordinator 调用返回 403。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission_owner_actionable(db, 1)

        payload = schemas.WorkflowNoteRequest(note="请审核", operator="owner")
        transfer_coordinator(submission_id=sub.id, payload=payload, current_user="owner", db=db)

        feedback_payload = schemas.WorkflowNoteRequest(note="test", operator="member")
        with pytest.raises(HTTPException) as exc:
            coordinator_feedback(submission_id=sub.id, payload=feedback_payload, current_user="member", db=db)
        assert exc.value.status_code == 403

    def test_wrong_status_gets_409(self):
        """错误状态调用返回 409。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission(db, 1, "普通成员")
        sub.confirm_status = SS.S_NEW
        db.flush()

        feedback_payload = schemas.WorkflowNoteRequest(note="test", operator="coordinator")
        with pytest.raises(HTTPException) as exc:
            coordinator_feedback(submission_id=sub.id, payload=feedback_payload, current_user="coordinator", db=db)
        assert exc.value.status_code == 409

    def test_tech_admin_can_feedback(self):
        """tech_admin 可以兜底反馈。"""
        db = _make_session()
        seed = _seed_coordinator_team(db)
        sub = _make_submission_owner_actionable(db, 1)

        payload = schemas.WorkflowNoteRequest(note="请审核", operator="owner")
        transfer_coordinator(submission_id=sub.id, payload=payload, current_user="owner", db=db)

        feedback_payload = schemas.WorkflowNoteRequest(note="管理员兜底反馈", operator="tech_admin")
        result = coordinator_feedback(submission_id=sub.id, payload=feedback_payload, current_user="tech_admin", db=db)

        assert result["submission"]["confirm_status"] == SS.S_COORDINATOR_GIVEN

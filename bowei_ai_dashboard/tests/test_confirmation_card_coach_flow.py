"""N4-P2-P: 单卡企业教练决策闭环 — 后端行为测试。

覆盖：
- 单卡上报：权限、状态校验、通知、日志
- 待办查询：include_card_level 参数
- 单卡批示：权限、状态校验、通知、日志
- 防绕过：卡片级和提交级操作被 pending_ceo_decision 阻断
- 批示后继续处理：owner 可确认/退回已批示卡
"""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import (
    confirm,
    confirm_task_card,
    reject,
    reject_task_card,
    reject_final,
    transfer_coordinator,
    transfer_task_card_to_coordinator,
    escalate_ceo,
    escalate_task_card_to_ceo,
    ceo_decide,
    ceo_decide_task_card,
    pending,
    save,
    withdraw,
    mark_unrecognized,
    assign,
)
from tests.test_execution_submission_to_work_progress_flow import _make_session


# ── 种子数据 ──────────────────────────────────────────────────────

def _seed_card_coach_team(db):
    """项目团队：owner + project_ceo + member + coordinator + tech_admin。"""
    owner_p = models.Person(id=1, name="项目负责人", system_role="normal_member", is_active=True)
    coach_p = models.Person(id=2, name="企业教练", system_role="normal_member", is_active=True)
    member_p = models.Person(id=3, name="普通成员", system_role="normal_member", is_active=True)
    coord_p = models.Person(id=4, name="统筹人", system_role="normal_member", is_active=True)
    tech_p = models.Person(id=5, name="技术管理员", system_role="super_admin", is_active=True)
    ceo_p = models.Person(id=6, name="公司CEO", system_role="company_ceo", is_active=True)

    db.add_all([
        owner_p, coach_p, member_p, coord_p, tech_p, ceo_p,
        models.Account(username="owner", password_hash="x", person_id=owner_p.id, status="active"),
        models.Account(username="coach", password_hash="x", person_id=coach_p.id, status="active"),
        models.Account(username="member", password_hash="x", person_id=member_p.id, status="active"),
        models.Account(username="coordinator", password_hash="x", person_id=coord_p.id, status="active"),
        models.Account(username="tech_admin", password_hash="x", person_id=tech_p.id, status="active", is_tech_admin=True),
        models.Account(username="公司CEO", password_hash="x", person_id=ceo_p.id, status="active"),
    ])
    db.flush()

    project = models.Project(id=1, name="测试项目", status="active", is_active=True)
    db.add(project)
    db.flush()

    db.add_all([
        models.ProjectMember(project_id=1, person_id=owner_p.id, person_name_snapshot=owner_p.name, role="owner"),
        models.ProjectMember(project_id=1, person_id=coach_p.id, person_name_snapshot=coach_p.name, role="project_ceo"),
        models.ProjectMember(project_id=1, person_id=member_p.id, person_name_snapshot=member_p.name, role="member"),
        models.ProjectMember(project_id=1, person_id=coord_p.id, person_name_snapshot=coord_p.name, role="coordinator"),
    ])
    db.flush()

    task = models.Task(id=1, project_id=1, key_task="测试重点工作", special_project="测试项目", owner="项目负责人", status="进行中")
    db.add(task)
    db.flush()

    subtask = models.SubTask(id=1, task_id=task.id, title="测试关键任务", assignee="普通成员", status="进行中", plan_time="2026-07-01")
    db.add(subtask)
    db.commit()

    return {
        "owner": owner_p, "coach": coach_p, "member": member_p,
        "coordinator": coord_p, "tech_admin": tech_p, "ceo": ceo_p,
        "project": project, "task": task, "subtask": subtask,
    }


def _submit(db, team, submitter="member", title="进展更新") -> int:
    """提交一条进展（单卡），返回 submission_id。"""
    import asyncio
    from app.routers.updates import create_update

    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "测试进展",
                "title": "测试任务卡标题",
                "achievements": [{"name": "测试成果", "achievement_type": "技术成果"}],
                "subtask_issues": [],
            },
        ],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title=title,
        transcript_text="测试进展",
        submitter=team[submitter].name if submitter in team else submitter,
        human_result=human_result,
    )
    result = asyncio.run(create_update(payload, current_user=submitter, db=db))
    return result["submission"]["id"]


def _submit_two_cards(db, team) -> int:
    """提交两条任务卡的进展，返回 submission_id。"""
    import asyncio
    from app.routers.updates import create_update

    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "卡1进展",
                "title": "任务卡1",
                "achievements": [{"name": "成果1", "achievement_type": "技术成果"}],
                "subtask_issues": [],
            },
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "卡2进展",
                "title": "任务卡2",
                "achievements": [{"name": "成果2", "achievement_type": "技术成果"}],
                "subtask_issues": [],
            },
        ],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="双卡进展",
        transcript_text="双卡进展",
        submitter="member",
        human_result=human_result,
    )
    result = asyncio.run(create_update(payload, current_user="member", db=db))
    return result["submission"]["id"]


# ── 辅助 ──────────────────────────────────────────────────────────

def _get_card_status(db, submission_id: int, card_index: int) -> str:
    row = db.get(models.UpdateSubmission, submission_id)
    data = json.loads(row.human_result_json)
    reports = data.get("task_reports") or []
    report = reports[card_index]
    return (report.get("confirmation_status") or "").strip()


# ════════════════════════════════════════════════════════════════════
# 一、单卡上报
# ════════════════════════════════════════════════════════════════════

class TestCardEscalate:
    """单卡上报企业教练。"""

    def test_owner_can_escalate_card(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)

        result = escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅", operator="owner"),
            current_user="owner", db=db,
        )
        assert result["ok"] is True
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_PENDING_OWNER

    def test_non_owner_cannot_escalate(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)

        with pytest.raises(HTTPException) as exc:
            escalate_task_card_to_ceo(
                sid, 0, schemas.WorkflowNoteRequest(note="x", operator="member"),
                current_user="member", db=db,
            )
        assert exc.value.status_code == 403

    def test_tech_admin_can_escalate(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)

        result = escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="admin escalate", operator="tech_admin"),
            current_user="tech_admin", db=db,
        )
        assert result["ok"] is True
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"

    def test_cannot_escalate_already_pending_card(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)

        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="第一次上报", operator="owner"),
            current_user="owner", db=db,
        )
        with pytest.raises(HTTPException) as exc:
            escalate_task_card_to_ceo(
                sid, 0, schemas.WorkflowNoteRequest(note="重复上报", operator="owner"),
                current_user="owner", db=db,
            )
        assert exc.value.status_code == 409

    def test_card_escalate_keeps_submission_status(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)

        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅", operator="owner"),
            current_user="owner", db=db,
        )
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_PENDING_OWNER  # 主状态不变

    def test_card_escalate_other_cards_unchanged(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit_two_cards(db, team)

        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅卡0", operator="owner"),
            current_user="owner", db=db,
        )
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"
        assert _get_card_status(db, sid, 1) == ""  # 卡1 不变


# ════════════════════════════════════════════════════════════════════
# 二、待办查询
# ════════════════════════════════════════════════════════════════════

class TestPendingWithCardLevel:
    """include_card_level 参数。"""

    def test_default_pending_excludes_card_level(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        # tab=ceo 默认不包含卡片级
        result = pending(tab="ceo", include_card_level=False, current_user="coach", db=db)
        ids = {item["id"] for item in result}
        assert sid not in ids  # card-level 不应出现

    def test_include_card_level_returns_card_items(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="coach", db=db)
        ids = {item["id"] for item in result}
        assert sid in ids

    def test_card_items_have_ceo_decision_scope(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="coach", db=db)
        card_items = [item for item in result if item["id"] == sid]
        assert len(card_items) == 1
        assert card_items[0]["ceo_decision_scope"] == "card"
        assert card_items[0]["pending_ceo_card_indices"] == [0]

    def test_submission_level_ceo_items_have_correct_scope(self):
        """提交级 S_WAITING_CEO 记录应显示 scope=submission。"""
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        # 整条上报
        escalate_ceo(
            sid, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="coach", db=db)
        sub_items = [item for item in result if item["id"] == sid]
        assert len(sub_items) == 1
        assert sub_items[0]["ceo_decision_scope"] == "submission"
        assert sub_items[0]["pending_ceo_card_indices"] == []

    def test_project_ceo_only_sees_own_project(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="coach", db=db)
        ids = {item["id"] for item in result}
        assert sid in ids

    def test_company_ceo_without_project_role_cannot_see(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="公司CEO", db=db)
        ids = {item["id"] for item in result}
        assert sid not in ids  # company_ceo 无 project_ceo 角色

    def test_owner_cannot_see_ceo_pending(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="owner", db=db)
        ids = {item["id"] for item in result}
        assert sid not in ids  # owner 不可见企业教练待办

    def test_member_cannot_access_confirmation_center(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        # member has no confirmation center access → 403
        with pytest.raises(HTTPException) as exc:
            pending(tab="ceo", include_card_level=True, current_user="member", db=db)
        assert exc.value.status_code == 403

    def test_tech_admin_can_see_card_level(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="tech_admin", db=db)
        ids = {item["id"] for item in result}
        assert sid in ids


# ════════════════════════════════════════════════════════════════════
# 三、单卡批示
# ════════════════════════════════════════════════════════════════════

class TestCardCeoDecide:
    """单卡企业教练批示。"""

    def _setup_pending_card(self, db, team):
        """上报一张卡到 pending_ceo_decision，返回 sid。"""
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅", operator="owner"),
            current_user="owner", db=db,
        )
        return sid

    def test_project_ceo_can_decide_card(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        result = ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意方案", operator="coach"),
            current_user="coach", db=db,
        )
        assert result["ok"] is True
        assert _get_card_status(db, sid, 0) == "ceo_decided"

    def test_card_ceo_decide_writes_fields(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意方案", operator="coach"),
            current_user="coach", db=db,
        )
        row = db.get(models.UpdateSubmission, sid)
        data = json.loads(row.human_result_json)
        report = data["task_reports"][0]
        assert report["confirmation_status"] == "ceo_decided"
        assert report["ceo_note"] == "同意方案"
        assert report["ceo_operator"] == "coach"
        assert "ceo_decided_at" in report
        assert report["ceo_decided_at"]  # 不为空

    def test_card_ceo_decide_preserves_original_escalation_fields(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意方案", operator="coach"),
            current_user="coach", db=db,
        )
        row = db.get(models.UpdateSubmission, sid)
        data = json.loads(row.human_result_json)
        report = data["task_reports"][0]
        # 原上报字段应保留
        assert report.get("confirmation_operator") == "owner"
        assert report.get("confirmation_note") == "请教练审阅"

    def test_card_ceo_decide_keeps_submission_status(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意方案", operator="coach"),
            current_user="coach", db=db,
        )
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_PENDING_OWNER

    def test_card_ceo_decide_only_affects_target_card(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit_two_cards(db, team)
        # 两张卡都上报
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅卡0", operator="owner"),
            current_user="owner", db=db,
        )
        escalate_task_card_to_ceo(
            sid, 1, schemas.WorkflowNoteRequest(note="请教练审阅卡1", operator="owner"),
            current_user="owner", db=db,
        )

        # 只批示卡0
        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意卡0", operator="coach"),
            current_user="coach", db=db,
        )
        assert _get_card_status(db, sid, 0) == "ceo_decided"
        assert _get_card_status(db, sid, 1) == "pending_ceo_decision"  # 卡1 仍是等待

    def test_non_pending_card_409(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="x", operator="coach"),
                current_user="coach", db=db,
            )
        assert exc.value.status_code == 409

    def test_nonexistent_card_404(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 99, schemas.WorkflowNoteRequest(note="x", operator="coach"),
                current_user="coach", db=db,
            )
        assert exc.value.status_code == 404

    def test_company_ceo_without_project_role_cannot_decide(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="CEO feedback", operator="公司CEO"),
                current_user="公司CEO", db=db,
            )
        assert exc.value.status_code == 403

    def test_owner_cannot_decide(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="owner decide", operator="owner"),
                current_user="owner", db=db,
            )
        assert exc.value.status_code == 403

    def test_tech_admin_can_decide(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_pending_card(db, team)

        result = ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="tech_admin decide", operator="tech_admin"),
            current_user="tech_admin", db=db,
        )
        assert result["ok"] is True


# ════════════════════════════════════════════════════════════════════
# 四、防绕过
# ════════════════════════════════════════════════════════════════════

class TestPendingCeoBlock:
    """pending_ceo_decision 阻止绕过操作。"""

    def _setup(self, db, team):
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )
        return sid

    # ── 卡片级 ────────────────────────────────

    def test_pending_ceo_card_cannot_confirm(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            confirm_task_card(sid, 0, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
        assert exc.value.status_code == 409

    def test_pending_ceo_card_cannot_reject(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            reject_task_card(sid, 0, schemas.RejectRequest(reason="退回", operator="owner"), current_user="owner", db=db)
        assert exc.value.status_code == 409

    def test_pending_ceo_card_cannot_transfer_coordinator(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            transfer_task_card_to_coordinator(
                sid, 0, schemas.WorkflowNoteRequest(note="转统筹", operator="owner"),
                current_user="owner", db=db,
            )
        assert exc.value.status_code == 409

    def test_pending_ceo_card_cannot_double_escalate(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            escalate_task_card_to_ceo(
                sid, 0, schemas.WorkflowNoteRequest(note="重复", operator="owner"),
                current_user="owner", db=db,
            )
        assert exc.value.status_code == 409

    # ── 提交级 ────────────────────────────────

    def test_pending_ceo_card_blocks_confirm_all(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            confirm(sid, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
        assert exc.value.status_code == 409

    def test_pending_ceo_card_blocks_reject_all(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            reject(sid, schemas.RejectRequest(reason="退回", operator="owner"), current_user="owner", db=db)
        assert exc.value.status_code == 409

    def test_pending_ceo_card_blocks_reject_final(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            reject_final(sid, schemas.RejectRequest(reason="不入库", operator="owner"), current_user="owner", db=db)
        assert exc.value.status_code == 409

    def test_pending_ceo_card_blocks_transfer_coordinator_all(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            transfer_coordinator(
                sid, schemas.WorkflowNoteRequest(note="转统筹", operator="owner"),
                current_user="owner", db=db,
            )
        assert exc.value.status_code == 409

    def test_pending_ceo_card_blocks_escalate_ceo_all(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        with pytest.raises(HTTPException) as exc:
            escalate_ceo(
                sid, schemas.WorkflowNoteRequest(note="上报CEO", operator="owner"),
                current_user="owner", db=db,
            )
        assert exc.value.status_code == 409


# ════════════════════════════════════════════════════════════════════
# 五、批示后继续处理
# ════════════════════════════════════════════════════════════════════

class TestPostCeoDecideOwnerActions:
    """CEO 批示后 owner 可继续处理。"""

    def _setup_decided(self, db, team):
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )
        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意方案", operator="coach"),
            current_user="coach", db=db,
        )
        return sid

    def test_owner_can_confirm_decided_card(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_decided(db, team)

        result = confirm_task_card(sid, 0, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
        assert result["ok"] is True
        assert _get_card_status(db, sid, 0) == "confirmed"

    def test_owner_can_reject_decided_card(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup_decided(db, team)

        result = reject_task_card(
            sid, 0, schemas.RejectRequest(reason="需修改", operator="owner"),
            current_user="owner", db=db,
        )
        assert result["ok"] is True
        assert _get_card_status(db, sid, 0) == "returned"

    def test_confirm_decided_card_only_affects_target(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit_two_cards(db, team)

        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报卡0", operator="owner"),
            current_user="owner", db=db,
        )
        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意卡0", operator="coach"),
            current_user="coach", db=db,
        )
        confirm_task_card(sid, 0, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)

        assert _get_card_status(db, sid, 0) == "confirmed"
        assert _get_card_status(db, sid, 1) == ""  # 卡1 不受影响

    def test_all_cards_confirmed_sets_submission_confirmed(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit_two_cards(db, team)

        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报卡0", operator="owner"),
            current_user="owner", db=db,
        )
        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意卡0", operator="coach"),
            current_user="coach", db=db,
        )
        confirm_task_card(sid, 0, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
        confirm_task_card(sid, 1, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)

        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CONFIRMED


# ════════════════════════════════════════════════════════════════════
# 六、回归：提交级流程不变
# ════════════════════════════════════════════════════════════════════

class TestRegression:
    """确认提交级 escalate-ceo / ceo-decide 不受影响。"""

    def test_submission_escalate_ceo_works(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)

        result = escalate_ceo(
            sid, schemas.WorkflowNoteRequest(note="请教练决策", operator="owner"),
            current_user="owner", db=db,
        )
        assert result["ok"] is True
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_WAITING_CEO

    def test_submission_ceo_decide_works(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_ceo(
            sid, schemas.WorkflowNoteRequest(note="请教练决策", operator="owner"),
            current_user="owner", db=db,
        )

        result = ceo_decide(
            sid, schemas.WorkflowNoteRequest(note="同意", operator="coach"),
            current_user="coach", db=db,
        )
        assert result["ok"] is True
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CEO_DECIDED

    def test_old_decision_page_pending_not_affected(self):
        """旧 DecisionPage 默认查询不应包含卡片级事项。"""
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = pending(tab="ceo", current_user="coach", db=db)
        ids = {item["id"] for item in result}
        assert sid not in ids  # 默认不包含卡片级


# ════════════════════════════════════════════════════════════════════
# 七、human_result 绕过防护（Section 三）
# ════════════════════════════════════════════════════════════════════

class TestHumanResultBypass:
    """confirm_task_card 不能通过 human_result 覆盖绕过 pending_ceo_decision。"""

    def test_human_result_cannot_overwrite_pending_ceo_card(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        # 验证数据库状态
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"

        # 尝试通过 human_result 移除 confirmation_status 绕过
        bypass_payload = schemas.ConfirmRequest(
            operator="owner",
            human_result={
                "task_reports": [
                    {
                        "result_type": "subtask_progress",
                        "type": "progress",
                        "matched_subtask_id": team["subtask"].id,
                        "completed": "绕过写入",
                        "title": "被覆盖的卡",
                        # 故意不传 confirmation_status
                    }
                ]
            },
        )
        with pytest.raises(HTTPException) as exc:
            confirm_task_card(sid, 0, bypass_payload, current_user="owner", db=db)
        assert exc.value.status_code == 409

        # 数据库卡片状态仍为 pending_ceo_decision
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"

        # human_result_json 未被覆盖
        row = db.get(models.UpdateSubmission, sid)
        data = json.loads(row.human_result_json)
        report = data["task_reports"][0]
        assert report.get("confirmation_status") == "pending_ceo_decision"
        # 没有产生业务写入（completed 未被覆盖）
        assert report.get("completed") == "测试进展"

    def test_human_result_cannot_overwrite_confirmation_status(self):
        """即使 human_result 显式设置 confirmation_status=confirmed 也不可绕过。"""
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        bypass_payload = schemas.ConfirmRequest(
            operator="owner",
            human_result={
                "task_reports": [
                    {
                        "confirmation_status": "confirmed",  # 试图模拟已确认
                        "matched_subtask_id": team["subtask"].id,
                        "completed": "绕过写入",
                    }
                ]
            },
        )
        with pytest.raises(HTTPException) as exc:
            confirm_task_card(sid, 0, bypass_payload, current_user="owner", db=db)
        assert exc.value.status_code == 409
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"


# ════════════════════════════════════════════════════════════════════
# 八、不可达路径防护（Section 四）
# ════════════════════════════════════════════════════════════════════

class TestPendingCeoBlockMore:
    """pending_ceo_decision 阻止 save / withdraw / mark-unrecognized。"""

    def _setup(self, db, team):
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )
        return sid

    def test_pending_ceo_card_blocks_save(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        row_before = db.get(models.UpdateSubmission, sid)
        old_status = row_before.confirm_status
        old_json = row_before.human_result_json

        with pytest.raises(HTTPException) as exc:
            save(
                sid,
                schemas.ConfirmationSaveRequest(human_result={"task_reports": []}),
                current_user="owner",
                db=db,
            )
        assert exc.value.status_code == 409

        # submission 主状态未变化
        row_after = db.get(models.UpdateSubmission, sid)
        assert row_after.confirm_status == old_status
        # human_result_json 未被覆盖
        assert row_after.human_result_json == old_json
        # 目标卡仍为 pending_ceo_decision
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"

    def test_pending_ceo_card_blocks_withdraw(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        row_before = db.get(models.UpdateSubmission, sid)
        old_status = row_before.confirm_status

        with pytest.raises(HTTPException) as exc:
            withdraw(sid, current_user="tech_admin", db=db)  # tech_admin 可代撤
        assert exc.value.status_code == 409

        # submission 主状态未变化
        row_after = db.get(models.UpdateSubmission, sid)
        assert row_after.confirm_status == old_status
        # 目标卡仍为 pending_ceo_decision
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"

    def test_pending_ceo_card_blocks_mark_unrecognized(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)

        row_before = db.get(models.UpdateSubmission, sid)
        old_status = row_before.confirm_status

        with pytest.raises(HTTPException) as exc:
            mark_unrecognized(
                sid,
                schemas.RejectRequest(reason="需人工处理", operator="owner"),
                current_user="owner",
                db=db,
            )
        assert exc.value.status_code == 409

        # submission 主状态未变化
        row_after = db.get(models.UpdateSubmission, sid)
        assert row_after.confirm_status == old_status
        # 目标卡仍为 pending_ceo_decision
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"


class TestAssignSafeWithPendingCard:
    """assign 不破坏 pending_ceo_decision 卡片。"""

    def test_assign_preserves_pending_ceo_cards(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        result = assign(
            sid,
            schemas.AssignRequest(assignee="新负责人", operator="owner"),
            current_user="owner",
            db=db,
        )
        assert result["ok"] is True

        # assign 后 pending_ceo_decision 卡片仍存在
        assert _get_card_status(db, sid, 0) == "pending_ceo_decision"
        # submission 主状态保持 S_PENDING_OWNER
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_PENDING_OWNER

    def test_assign_does_not_block_ceo_pending_query(self):
        """assign 后企业教练待办仍可查询。"""
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )

        assign(
            sid,
            schemas.AssignRequest(assignee="新负责人", operator="owner"),
            current_user="owner",
            db=db,
        )

        result = pending(tab="ceo", include_card_level=True, current_user="coach", db=db)
        ids = {item["id"] for item in result}
        assert sid in ids


# ════════════════════════════════════════════════════════════════════
# 九、企业教练批示主状态校验（Section 五）
# ════════════════════════════════════════════════════════════════════

class TestCardCeoDecideStatusCheck:
    """单卡批示必须在 S_PENDING_OWNER 主状态下。"""

    def _make_pending(self, db, team):
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="上报", operator="owner"),
            current_user="owner", db=db,
        )
        return sid

    def test_rejected_when_withdrawn(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._make_pending(db, team)

        # 先撤回（需要先绕过 pending_ceo 阻截？不行。
        # 这里用直接修改数据库模拟撤回后的状态
        row = db.get(models.UpdateSubmission, sid)
        row.confirm_status = SS.S_WITHDRAWN
        db.commit()

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="批示", operator="coach"),
                current_user="coach", db=db,
            )
        assert exc.value.status_code == 409

    def test_rejected_when_needs_revision(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._make_pending(db, team)

        row = db.get(models.UpdateSubmission, sid)
        row.confirm_status = SS.S_NEEDS_REVISION
        db.commit()

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="批示", operator="coach"),
                current_user="coach", db=db,
            )
        assert exc.value.status_code == 409

    def test_rejected_when_confirmed(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._make_pending(db, team)

        row = db.get(models.UpdateSubmission, sid)
        row.confirm_status = SS.S_CONFIRMED
        db.commit()

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="批示", operator="coach"),
                current_user="coach", db=db,
            )
        assert exc.value.status_code == 409

    def test_rejected_when_waiting_coordinator(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._make_pending(db, team)

        row = db.get(models.UpdateSubmission, sid)
        row.confirm_status = SS.S_WAITING_COORDINATOR
        db.commit()

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="批示", operator="coach"),
                current_user="coach", db=db,
            )
        assert exc.value.status_code == 409

    def test_rejected_when_submission_waiting_ceo(self):
        """整条提交已 S_WAITING_CEO 时不可用单卡批示接口。"""
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._make_pending(db, team)

        row = db.get(models.UpdateSubmission, sid)
        row.confirm_status = SS.S_WAITING_CEO
        db.commit()

        with pytest.raises(HTTPException) as exc:
            ceo_decide_task_card(
                sid, 0, schemas.WorkflowNoteRequest(note="批示", operator="coach"),
                current_user="coach", db=db,
            )
        assert exc.value.status_code == 409

    def test_allowed_when_pending_owner(self):
        """S_PENDING_OWNER 时允许正常批示。"""
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._make_pending(db, team)

        # 确认当前是 S_PENDING_OWNER
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_PENDING_OWNER

        result = ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意", operator="coach"),
            current_user="coach", db=db,
        )
        assert result["ok"] is True


# ════════════════════════════════════════════════════════════════════
# 十、通知与日志真实数据库断言（Section 七）
# ════════════════════════════════════════════════════════════════════

class TestNotificationAndLogDB:
    """验证通知和日志真实写入数据库。"""

    def _setup(self, db, team):
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅", operator="owner"),
            current_user="owner", db=db,
        )
        return sid

    # ── 上报通知 ────────────────────────────────

    def test_escalate_notification_sent_to_coach(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅", operator="owner"),
            current_user="owner", db=db,
        )

        notifications = (
            db.query(models.Notification)
            .filter(models.Notification.type == "confirmation_card_escalate_ceo")
            .all()
        )
        assert len(notifications) >= 1

        # 通知接收人为 project_ceo
        coach_notifications = [
            n for n in notifications
            if n.recipient_id == team["coach"].id
        ]
        assert len(coach_notifications) >= 1

        n = coach_notifications[0]
        # 标题包含任务卡标题
        assert "测试任务卡标题" in n.title
        # 正文包含提交标题
        assert "进展更新" in n.body
        # 正文包含任务卡序号（第 1 张）
        assert "第 1 张" in n.body
        # 正文包含上报说明
        assert "请教练审阅" in n.body
        # link 包含 view=ceo
        assert "view=ceo" in n.link
        # link 包含 projectId
        assert f"projectId={team['project'].id}" in n.link
        # link 包含 submissionId
        assert f"submissionId={sid}" in n.link
        # link 包含 cardIndex
        assert "cardIndex=0" in n.link

    def test_escalate_notification_not_sent_to_company_ceo(self):
        """company_ceo 无项目角色不应收到卡片级上报通知。"""
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅", operator="owner"),
            current_user="owner", db=db,
        )

        notifications = (
            db.query(models.Notification)
            .filter(models.Notification.type == "confirmation_card_escalate_ceo")
            .filter(models.Notification.recipient_id == team["ceo"].id)
            .all()
        )
        assert len(notifications) == 0

    # ── 批示通知 ────────────────────────────────

    def test_ceo_decide_notification_sent_to_owner(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)
        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意该方案", operator="coach"),
            current_user="coach", db=db,
        )

        notifications = (
            db.query(models.Notification)
            .filter(models.Notification.type == "confirmation_card_ceo_decided")
            .all()
        )
        assert len(notifications) >= 1

        # 通知接收人为 owner
        owner_notifications = [
            n for n in notifications
            if n.recipient_id == team["owner"].id
        ]
        assert len(owner_notifications) >= 1

        n = owner_notifications[0]
        # 标题包含任务卡标题
        assert "测试任务卡标题" in n.title
        # 正文包含提交标题
        assert "进展更新" in n.body
        # 正文包含任务卡序号
        assert "第 1 张" in n.body
        # 正文包含批示内容
        assert "同意该方案" in n.body
        # link 包含 view=all
        assert "view=all" in n.link
        # link 包含 projectId
        assert f"projectId={team['project'].id}" in n.link
        # link 包含 submissionId
        assert f"submissionId={sid}" in n.link
        # link 包含 cardIndex
        assert "cardIndex=0" in n.link

    # ── 操作日志 ────────────────────────────────

    def test_escalate_log_written(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = _submit(db, team)
        escalate_task_card_to_ceo(
            sid, 0, schemas.WorkflowNoteRequest(note="请教练审阅", operator="owner"),
            current_user="owner", db=db,
        )

        logs = (
            db.query(models.OperationLog)
            .filter(models.OperationLog.action == "confirmation_card_escalate_to_coach")
            .filter(models.OperationLog.target_type == "confirmation")
            .filter(models.OperationLog.target_id == sid)
            .all()
        )
        assert len(logs) >= 1

        log = logs[0]
        # after 数据包含 card_index, card_title, note
        after_data = json.loads(log.after_json or "{}")
        assert after_data.get("card_index") == 0
        assert after_data.get("card_title") == "测试任务卡标题"
        assert after_data.get("note") == "请教练审阅"

    def test_ceo_decide_log_written(self):
        db = _make_session()
        team = _seed_card_coach_team(db)
        sid = self._setup(db, team)
        ceo_decide_task_card(
            sid, 0, schemas.WorkflowNoteRequest(note="同意该方案", operator="coach"),
            current_user="coach", db=db,
        )

        logs = (
            db.query(models.OperationLog)
            .filter(models.OperationLog.action == "confirmation_card_coach_decision")
            .filter(models.OperationLog.target_type == "confirmation")
            .filter(models.OperationLog.target_id == sid)
            .all()
        )
        assert len(logs) >= 1

        log = logs[0]
        after_data = json.loads(log.after_json or "{}")
        assert after_data.get("card_index") == 0
        assert after_data.get("card_title") == "测试任务卡标题"
        assert after_data.get("note") == "同意该方案"

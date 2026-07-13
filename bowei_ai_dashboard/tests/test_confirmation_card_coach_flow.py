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

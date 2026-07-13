"""N4-P2-E-FIX company_ceo 兼任项目 owner 确认权限修复 — 测试。

覆盖：
- company_ceo + project owner → confirm 允许
- company_ceo + project owner → confirm_task_card 允许
- company_ceo 非项目 owner → confirm 403
- company_ceo 非项目 owner → confirm_task_card 403
- project_ceo 非 owner → confirm 403
- coordinator 非 owner → confirm 403
- normal_member → confirm 403
- tech_admin → confirm 允许
- owner 确认自己提交 → 允许
- confirm_status 正确变更
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.routers.confirmations import confirm, confirm_task_card
from app.domain import submission_status as SS

from tests.test_execution_submission_to_work_progress_flow import _make_session


# ── 自定义种子数据 ──────────────────────────────────────────────

def _seed_ceo_owner_team(db):
    """company_ceo 同时是项目 owner 的团队。

    persons: 冯海林(ceo+owner), 企业教练, 普通成员, 统筹人
    """
    ceo_owner = models.Person(id=1, name="冯海林", system_role="company_ceo", is_active=True)
    coach = models.Person(id=2, name="企业教练", system_role="normal_member", is_active=True)
    member = models.Person(id=3, name="普通成员", system_role="normal_member", is_active=True)
    coordinator = models.Person(id=4, name="统筹人", system_role="normal_member", is_active=True)

    db.add_all([
        ceo_owner, coach, member, coordinator,
        models.Account(username="冯海林", password_hash="x", person_id=ceo_owner.id, status="active"),
        models.Account(username="coach", password_hash="x", person_id=coach.id, status="active"),
        models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
        models.Account(username="coordinator", password_hash="x", person_id=coordinator.id, status="active"),
    ])
    db.flush()

    project = models.Project(
        id=1, name="测试项目", status="active", is_active=True,
        description="CEO owner 测试项目",
    )
    db.add(project)
    db.flush()

    db.add_all([
        models.ProjectMember(project_id=1, person_id=ceo_owner.id, person_name_snapshot=ceo_owner.name, role="owner"),
        models.ProjectMember(project_id=1, person_id=coach.id, person_name_snapshot=coach.name, role="project_ceo"),
        models.ProjectMember(project_id=1, person_id=member.id, person_name_snapshot=member.name, role="member"),
        models.ProjectMember(project_id=1, person_id=coordinator.id, person_name_snapshot=coordinator.name, role="coordinator"),
    ])
    db.flush()

    task = models.Task(
        id=1, project_id=1, key_task="测试重点工作", special_project="测试项目",
        owner="冯海林", status="进行中",
    )
    db.add(task)
    db.flush()

    subtask = models.SubTask(
        id=1, task_id=task.id, title="测试关键任务",
        assignee="普通成员", status="进行中",
        plan_time="2026-07-01", completion_criteria="测试通过",
    )
    db.add(subtask)
    db.commit()

    return {
        "ceo_owner": ceo_owner, "coach": coach, "member": member,
        "coordinator": coordinator,
        "project": project, "task": task, "subtask": subtask,
    }


def _seed_ceo_not_owner_team(db):
    """company_ceo 不是任何项目成员（与旧 _seed_execution_team 一致）。"""
    ceo = models.Person(id=1, name="公司CEO", system_role="company_ceo", is_active=True)
    owner = models.Person(id=2, name="项目负责人", system_role="normal_member", is_active=True)
    member = models.Person(id=3, name="普通成员", system_role="normal_member", is_active=True)

    db.add_all([
        ceo, owner, member,
        models.Account(username="公司CEO", password_hash="x", person_id=ceo.id, status="active"),
        models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"),
        models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
    ])
    db.flush()

    project = models.Project(id=1, name="测试项目", status="active", is_active=True)
    db.add(project)
    db.flush()

    db.add_all([
        models.ProjectMember(project_id=1, person_id=owner.id, person_name_snapshot=owner.name, role="owner"),
        models.ProjectMember(project_id=1, person_id=member.id, person_name_snapshot=member.name, role="member"),
    ])
    db.flush()

    task = models.Task(
        id=1, project_id=1, key_task="测试重点工作", special_project="测试项目",
        owner="项目负责人", status="进行中",
    )
    db.add(task)
    db.flush()

    subtask = models.SubTask(
        id=1, task_id=task.id, title="测试关键任务",
        assignee="普通成员", status="进行中",
    )
    db.add(subtask)
    db.commit()

    return {
        "ceo": ceo, "owner": owner, "member": member,
        "project": project, "task": task, "subtask": subtask,
    }


def _seed_tech_admin_team(db):
    """tech_admin 团队。"""
    tech = models.Person(id=1, name="技术管理员", system_role="super_admin", is_active=True)
    member = models.Person(id=2, name="普通成员", system_role="normal_member", is_active=True)

    db.add_all([
        tech, member,
        models.Account(username="tech_admin", password_hash="x", person_id=tech.id, status="active",
                       is_tech_admin=True),
        models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
    ])
    db.flush()

    project = models.Project(id=1, name="测试项目", status="active", is_active=True)
    db.add(project)
    db.flush()

    db.add_all([
        models.ProjectMember(project_id=1, person_id=tech.id, person_name_snapshot=tech.name, role="owner"),
        models.ProjectMember(project_id=1, person_id=member.id, person_name_snapshot=member.name, role="member"),
    ])
    db.flush()

    task = models.Task(
        id=1, project_id=1, key_task="测试重点工作", special_project="测试项目",
        owner="技术管理员", status="进行中",
    )
    db.add(task)
    db.flush()

    subtask = models.SubTask(
        id=1, task_id=task.id, title="测试关键任务",
        assignee="普通成员", status="进行中",
    )
    db.add(subtask)
    db.commit()

    return {
        "tech_admin": tech, "member": member,
        "project": project, "task": task, "subtask": subtask,
    }


# ── 辅助 ────────────────────────────────────────────────────────

def _submit(db, team) -> int:
    """提交一条进展，返回 submission_id。"""
    from app.routers.updates import create_update

    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "测试进展",
                "achievements": [{"name": "测试成果", "achievement_type": "技术成果"}],
                "subtask_issues": [],
            },
        ],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="进展更新",
        transcript_text="测试进展",
        submitter=team["member"].name,
        human_result=human_result,
    )
    result = asyncio.run(create_update(payload, current_user="member", db=db))
    return result["submission"]["id"]


# ── 测试 ────────────────────────────────────────────────────────

class TestCeoOwnerConfirmation:
    """company_ceo + project owner 应能确认入库。"""

    def test_ceo_owner_confirm_allowed(self):
        """company_ceo + project owner 确认入库允许。"""
        db = _make_session()
        team = _seed_ceo_owner_team(db)
        sid = _submit(db, team)

        result = confirm(sid, schemas.ConfirmRequest(operator="冯海林"),
                        current_user="冯海林", db=db)
        assert result["ok"] is True
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CONFIRMED
        assert row.confirmed_by == "冯海林"

    def test_ceo_owner_confirm_task_card_allowed(self):
        """company_ceo + project owner 单卡确认允许。"""
        db = _make_session()
        team = _seed_ceo_owner_team(db)
        sid = _submit(db, team)

        result = confirm_task_card(sid, 0, schemas.ConfirmRequest(operator="冯海林"),
                                   current_user="冯海林", db=db)
        assert result["ok"] is True
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CONFIRMED


class TestCeoNotOwnerDenied:
    """company_ceo 但不是项目 owner 应被拒绝。"""

    def test_ceo_not_owner_confirm_403(self):
        """company_ceo 非 owner 确认入库 403。"""
        db = _make_session()
        team = _seed_ceo_not_owner_team(db)
        sid = _submit(db, team)

        with pytest.raises(HTTPException) as exc:
            confirm(sid, schemas.ConfirmRequest(operator="公司CEO"),
                   current_user="公司CEO", db=db)
        assert exc.value.status_code == 403

    def test_ceo_not_owner_confirm_task_card_403(self):
        """company_ceo 非 owner 单卡确认 403。"""
        db = _make_session()
        team = _seed_ceo_not_owner_team(db)
        sid = _submit(db, team)

        with pytest.raises(HTTPException) as exc:
            confirm_task_card(sid, 0, schemas.ConfirmRequest(operator="公司CEO"),
                            current_user="公司CEO", db=db)
        assert exc.value.status_code == 403


class TestProjectCeoDenied:
    """project_ceo 但不是 owner 应被拒绝。"""

    def test_project_ceo_confirm_403(self):
        """project_ceo 非 owner 确认入库 403。"""
        db = _make_session()
        team = _seed_ceo_owner_team(db)
        sid = _submit(db, team)

        with pytest.raises(HTTPException) as exc:
            confirm(sid, schemas.ConfirmRequest(operator="coach"),
                   current_user="coach", db=db)
        assert exc.value.status_code == 403


class TestCoordinatorDenied:
    """coordinator 但不是 owner 应被拒绝。"""

    def test_coordinator_confirm_403(self):
        """coordinator 非 owner 确认入库 403。"""
        db = _make_session()
        team = _seed_ceo_owner_team(db)
        sid = _submit(db, team)

        with pytest.raises(HTTPException) as exc:
            confirm(sid, schemas.ConfirmRequest(operator="coordinator"),
                   current_user="coordinator", db=db)
        assert exc.value.status_code == 403


class TestNormalMemberDenied:
    """普通成员应被拒绝。"""

    def test_normal_member_confirm_403(self):
        """normal_member 确认入库 403。"""
        db = _make_session()
        team = _seed_ceo_owner_team(db)
        sid = _submit(db, team)

        with pytest.raises(HTTPException) as exc:
            confirm(sid, schemas.ConfirmRequest(operator="member"),
                   current_user="member", db=db)
        assert exc.value.status_code == 403


class TestTechAdminAllowed:
    """tech_admin 全局可确认。"""

    def test_tech_admin_confirm_allowed(self):
        """tech_admin 确认入库允许。"""
        db = _make_session()
        team = _seed_tech_admin_team(db)
        sid = _submit(db, team)

        result = confirm(sid, schemas.ConfirmRequest(operator="tech_admin"),
                        current_user="tech_admin", db=db)
        assert result["ok"] is True
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CONFIRMED


class TestOwnerSelfSubmit:
    """owner 确认自己提交的 submission。"""

    def test_owner_confirm_own_submission_allowed(self):
        """owner 确认自己的提交允许。"""
        db = _make_session()
        # 使用 ceo_not_owner team, 但用 owner 提交并确认
        team = _seed_ceo_not_owner_team(db)

        # owner 自己提交
        from app.routers.updates import create_update
        human_result = {
            "task_reports": [
                {
                    "result_type": "subtask_progress",
                    "type": "progress",
                    "matched_subtask_id": team["subtask"].id,
                    "completed": "测试进展",
                    "achievements": [{"name": "测试成果", "achievement_type": "技术成果"}],
                    "subtask_issues": [],
                },
            ],
            "special_project": team["project"].name,
        }
        payload = schemas.ExtractRequest(
            project_id=team["project"].id,
            source_type="任务进展",
            title="owner自己提交",
            transcript_text="owner提交",
            submitter=team["owner"].name,
            human_result=human_result,
        )
        result = asyncio.run(create_update(payload, current_user="owner", db=db))
        sid = result["submission"]["id"]

        confirm_result = confirm(sid, schemas.ConfirmRequest(operator="owner"),
                                current_user="owner", db=db)
        assert confirm_result["ok"] is True
        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CONFIRMED
        assert row.confirmed_by == "owner"


class TestConfirmStatusCorrect:
    """确认后状态正确变更。"""

    def test_confirm_status_becomes_confirmed(self):
        """整体确认后 confirm_status 变为已入库。"""
        db = _make_session()
        team = _seed_ceo_owner_team(db)
        sid = _submit(db, team)

        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status != SS.S_CONFIRMED  # 待确认

        confirm(sid, schemas.ConfirmRequest(operator="冯海林"),
               current_user="冯海林", db=db)

        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CONFIRMED

    def test_confirm_task_card_status_correct(self):
        """单卡确认后 confirm_status 变为已入库。"""
        db = _make_session()
        team = _seed_ceo_owner_team(db)
        sid = _submit(db, team)

        confirm_task_card(sid, 0, schemas.ConfirmRequest(operator="冯海林"),
                         current_user="冯海林", db=db)

        row = db.get(models.UpdateSubmission, sid)
        assert row.confirm_status == SS.S_CONFIRMED

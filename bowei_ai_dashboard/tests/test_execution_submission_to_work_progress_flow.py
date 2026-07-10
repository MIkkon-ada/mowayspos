"""
N4-P0-C 执行闭环测试：提交 → 确认 → 入库 → 工作推进表可见

验证最小执行闭环是否真实跑通，不依赖真实 AI 服务。
"""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.domain import submission_status as SS
from app.routers.updates import create_update
from app.routers.confirmations import confirm
from app.routers.tasks import get_task_updates
from app.routers.subtasks import get_subtask_detail


# ── 测试辅助 ────────────────────────────────────────────────────

def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_execution_team(db):
    """创建完整的执行闭环测试团队：
    - project_ceo（企业教练）
    - owner（项目负责人/PM）
    - member（普通成员，也是关键任务责任人）
    - company_ceo（纯公司CEO，无项目角色）
    """
    owner = models.Person(id=1, name="项目负责人", system_role="normal_member", is_active=True)
    coach = models.Person(id=2, name="企业教练", system_role="normal_member", is_active=True)
    member = models.Person(id=3, name="普通成员", system_role="normal_member", is_active=True)
    company_ceo = models.Person(id=4, name="公司CEO", system_role="company_ceo", is_active=True)

    db.add_all([
        owner, coach, member, company_ceo,
        models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"),
        models.Account(username="coach", password_hash="x", person_id=coach.id, status="active"),
        models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
        models.Account(username="company_ceo", password_hash="x", person_id=company_ceo.id, status="active"),
    ])
    db.flush()

    active_project = models.Project(
        id=1, name="测试项目", status="active", is_active=True,
        description="N4-P0-C 测试项目",
    )
    db.add(active_project)
    db.flush()

    db.add_all([
        models.ProjectMember(project_id=1, person_id=coach.id, person_name_snapshot=coach.name, role="project_ceo"),
        models.ProjectMember(project_id=1, person_id=owner.id, person_name_snapshot=owner.name, role="owner"),
        models.ProjectMember(project_id=1, person_id=member.id, person_name_snapshot=member.name, role="member"),
    ])

    task = models.Task(
        id=1, project_id=1, key_task="测试重点工作", special_project="测试项目",
        owner="项目负责人", status="进行中", completion_standard="通过闭环测试",
        source_type="人工录入",
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
        "owner": owner, "coach": coach, "member": member,
        "company_ceo": company_ceo,
        "project": active_project, "task": task, "subtask": subtask,
    }


# ── 流程一：提交进展进入待确认 ───────────────────────────────────

def test_flow1_submit_progress_creates_pending_submission():
    """成员提交工作进展后，生成 UpdateSubmission，状态为待确认，不直接入库。"""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "result_type": "subtask_progress",
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "完成了前端页面优化",
                "next_plan": "下一步做后端接口联调",
                "achievements": [
                    {"name": "前端页面优化完成", "achievement_type": "技术成果"},
                ],
                "subtask_issues": [
                    {"description": "接口文档不完整，需协调后端补充", "issue_type": "问题", "priority": "高"},
                ],
            },
        ],
        "completed_items": ["完成了前端页面优化"],
        "next_plan": "下一步做后端接口联调",
        "special_project": team["project"].name,
        "key_task_issues": [],
    }

    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title=f"{team['task'].key_task} 进展更新",
        transcript_text="完成了前端页面优化，下一步做后端接口联调，接口文档不完整需要协调",
        submitter=team["member"].name,
        human_result=human_result,
    )

    result = asyncio.run(create_update(payload, current_user="member", db=db))
    submission = result["submission"]

    # 断言：生成 UpdateSubmission
    assert submission["id"] is not None
    assert submission["project_id"] == team["project"].id
    assert submission["submitter"] == team["member"].name
    # 状态必须是待确认
    assert submission["confirm_status"] == SS.S_NEW
    # 提交阶段 related_task_id 为 None（确认后才设置）
    row = db.get(models.UpdateSubmission, submission["id"])
    assert row.related_task_id is None
    # 提交阶段不直接写入正式成果库
    achievements = db.query(models.Achievement).filter_by(source_submission_id=submission["id"]).all()
    assert len(achievements) == 0, "提交阶段不应直接写入成果表"
    issues = db.query(models.Issue).filter_by(source_submission_id=submission["id"]).all()
    assert len(issues) == 0, "提交阶段不应直接写入问题表"


def test_flow1_submit_without_human_result_does_not_call_real_ai():
    """如果传 human_result，不会走 AI extractor；如果完全不传也会用规则引擎。"""
    db = _make_session()
    team = _seed_execution_team(db)

    # 带 human_result 的提交
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="进展更新",
        transcript_text="测试文本",
        submitter=team["member"].name,
        human_result={"completed_items": ["测试完成项"]},
    )
    result = asyncio.run(create_update(payload, current_user="member", db=db))
    assert result["submission"]["confirm_status"] == SS.S_NEW
    # 确认 human_result 被正确存储
    row = db.get(models.UpdateSubmission, result["submission"]["id"])
    stored = json.loads(row.human_result_json or "{}")
    assert stored.get("completed_items") == ["测试完成项"]


def test_flow1_non_active_project_rejects_submission():
    """非 active 项目不应接受正式汇报。"""
    db = _make_session()
    team = _seed_execution_team(db)

    # 把项目改为非 active
    team["project"].status = "pending_review"
    team["project"].is_active = False
    db.commit()

    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="进展更新",
        transcript_text="测试文本",
        submitter=team["member"].name,
        human_result={"completed_items": ["test"]},
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        asyncio.run(create_update(payload, current_user="member", db=db))
    assert exc.value.status_code == 409
    assert "暂不能提交" in str(exc.value.detail)


# ── 流程二：PM 确认入库 ─────────────────────────────────────────

def test_flow2_owner_confirm_writes_to_tables_and_sets_related_task_id():
    """Owner 确认后：UpdateSubmission → 已入库，related_task_id 设置，
    Achievement/Issue 写入，SubTask 更新。"""
    db = _make_session()
    team = _seed_execution_team(db)

    # 第一步：成员提交
    human_result = {
        "result_type": "subtask_progress",
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "完成了前端页面优化",
                "next_plan": "下一步做后端接口联调",
                "achievements": [
                    {"name": "成果A：页面优化", "achievement_type": "技术成果"},
                ],
                "subtask_issues": [
                    {"description": "问题B：接口文档缺失", "issue_type": "问题", "priority": "高"},
                ],
            },
        ],
        "completed_items": ["完成了前端页面优化"],
        "next_plan": "下一步做后端接口联调",
        "special_project": team["project"].name,
        "key_task_issues": [],
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title=f"{team['task'].key_task} 进展更新",
        transcript_text="完成了前端页面优化，下一步做后端接口联调",
        submitter=team["member"].name,
        human_result=human_result,
    )
    sub_result = asyncio.run(create_update(payload, current_user="member", db=db))
    submission_id = sub_result["submission"]["id"]

    # 第二步：Owner 确认入库
    confirm_payload = schemas.ConfirmRequest(operator="owner")
    confirm_result = confirm(submission_id, confirm_payload, current_user="owner", db=db)

    assert confirm_result["ok"] is True
    row = db.get(models.UpdateSubmission, submission_id)
    assert row.confirm_status == SS.S_CONFIRMED, f"status should be 已入库, got {row.confirm_status}"
    assert row.related_task_id == team["task"].id, "确认后应设置 related_task_id"
    assert row.confirmed_by == "owner"

    # 断言：成果已写入
    achievements = db.query(models.Achievement).filter_by(source_submission_id=submission_id).all()
    assert len(achievements) >= 1, "确认后应写入成果"
    assert any("页面优化" in (a.name or "") for a in achievements)

    # 断言：问题已写入
    issues = db.query(models.Issue).filter_by(source_submission_id=submission_id).all()
    assert len(issues) >= 1, "确认后应写入问题"
    assert any("接口文档" in (i.description or "") for i in issues)

    # 断言：SubTask 已更新
    subtask = db.get(models.SubTask, team["subtask"].id)
    assert subtask.source_submission_id == submission_id
    assert "完成了前端页面优化" in (subtask.notes or "")


def test_flow2_owner_confirm_does_not_change_project_lifecycle():
    """确认入库不应改变项目生命周期状态。"""
    db = _make_session()
    team = _seed_execution_team(db)

    project_before = db.get(models.Project, team["project"].id)

    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "更新了文档",
                "achievements": [{"name": "文档更新", "achievement_type": "文档产出"}],
                "subtask_issues": [],
            },
        ],
        "completed_items": ["更新了文档"],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="进展更新",
        transcript_text="更新了文档",
        submitter=team["member"].name,
        human_result=human_result,
    )
    sub_result = asyncio.run(create_update(payload, current_user="member", db=db))

    confirm(sub_result["submission"]["id"], schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    project_after = db.get(models.Project, team["project"].id)
    assert project_after.status == project_before.status, "项目 status 不应改变"
    assert project_after.is_active == project_before.is_active, "项目 is_active 不应改变"
    assert project_after.status != "draft"
    assert project_after.status != "pending_review"


def test_flow2_company_ceo_cannot_confirm():
    """纯 company_ceo（无项目 project_ceo 角色）不能绕过 owner 确认入库。"""
    db = _make_session()
    team = _seed_execution_team(db)

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
    sub_result = asyncio.run(create_update(payload, current_user="member", db=db))

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        confirm(sub_result["submission"]["id"], schemas.ConfirmRequest(operator="company_ceo"),
                current_user="company_ceo", db=db)
    assert exc.value.status_code == 403, "company_ceo 不可确认入库"


def test_flow2_project_ceo_cannot_confirm():
    """project_ceo（企业教练）不能确认入库，只有 owner 可以。"""
    db = _make_session()
    team = _seed_execution_team(db)

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
    sub_result = asyncio.run(create_update(payload, current_user="member", db=db))

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        confirm(sub_result["submission"]["id"], schemas.ConfirmRequest(operator="coach"),
                current_user="coach", db=db)
    assert exc.value.status_code == 403, "project_ceo 不可确认入库"


# ── 流程三：工作推进表可读取更新 ─────────────────────────────────

def test_flow3_task_updates_shows_confirmed_submission():
    """确认后，GET /api/tasks/{task_id}/updates 能查到确认后的进展记录。"""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "完成了核心功能开发",
                "achievements": [{"name": "核心功能开发完成", "achievement_type": "技术成果"}],
                "subtask_issues": [],
            },
        ],
        "completed_items": ["完成了核心功能开发"],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title=f"{team['task'].key_task} 进展",
        transcript_text="完成了核心功能开发",
        submitter=team["member"].name,
        human_result=human_result,
    )
    sub_result = asyncio.run(create_update(payload, current_user="member", db=db))
    submission_id = sub_result["submission"]["id"]

    # 确认前：task updates 不应包含此提交（related_task_id 为 null）
    updates_before = get_task_updates(team["task"].id, current_user="owner", db=db)
    assert not any(u["id"] == submission_id for u in updates_before), \
        "确认前不应出现在工作推进表 updates 中"

    # Owner 确认
    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    # 确认后：task updates 应包含此提交
    updates_after = get_task_updates(team["task"].id, current_user="owner", db=db)
    assert any(u["id"] == submission_id for u in updates_after), \
        "确认后应在工作推进表 updates 中可见"


def test_flow3_subtask_detail_shows_source_submission_and_related_data():
    """关键任务详情接口能看到 source_submission / related_achievements / related_issues。"""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "完成了UI优化",
                "achievements": [
                    {"name": "UI 优化成果", "achievement_type": "技术成果"},
                ],
                "subtask_issues": [
                    {"description": "兼容性问题", "issue_type": "问题", "priority": "中"},
                ],
            },
        ],
        "completed_items": ["完成了UI优化"],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="进展更新",
        transcript_text="完成了UI优化，兼容性有问题",
        submitter=team["member"].name,
        human_result=human_result,
    )
    sub_result = asyncio.run(create_update(payload, current_user="member", db=db))
    submission_id = sub_result["submission"]["id"]
    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    detail = get_subtask_detail(team["subtask"].id, current_user="owner", db=db)

    # 断言 source_submission
    assert detail.get("source_submission") is not None
    assert detail["source_submission"]["id"] == submission_id
    assert detail["source_submission"]["submitter"] == team["member"].name

    # 断言 related_achievements
    assert len(detail.get("related_achievements", [])) >= 1
    assert any("UI 优化" in (a.get("name") or "") for a in detail["related_achievements"])

    # 断言 related_issues
    assert len(detail.get("related_issues", [])) >= 1
    assert any("兼容性" in (i.get("description") or "") for i in detail["related_issues"])


def test_flow3_full_roundtrip_closed_loop():
    """端到端闭环：提交 → 确认 → 工作推进表可见。"""
    db = _make_session()
    team = _seed_execution_team(db)

    # Step 1: 成员提交
    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "端到端测试通过",
                "achievements": [
                    {"name": "闭环测试通过", "achievement_type": "文档产出"},
                ],
                "subtask_issues": [
                    {"description": "发现一处延迟风险", "issue_type": "风险", "priority": "高"},
                ],
            },
        ],
        "completed_items": ["端到端测试通过"],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="闭环验证",
        transcript_text="端到端测试通过",
        submitter=team["member"].name,
        human_result=human_result,
    )

    # 提交
    result = asyncio.run(create_update(payload, current_user="member", db=db))
    sub = result["submission"]
    assert sub["confirm_status"] == SS.S_NEW

    # 提交前 project 是 active
    project = db.get(models.Project, team["project"].id)
    assert project.status == "active"
    assert project.is_active is True

    # 确认
    confirm(sub["id"], schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    # 确认后：状态为已入库
    row = db.get(models.UpdateSubmission, sub["id"])
    assert row.confirm_status == SS.S_CONFIRMED
    assert row.related_task_id == team["task"].id

    # 确认后 project 状态不变
    project = db.get(models.Project, team["project"].id)
    assert project.status == "active"
    assert project.is_active is True

    # 工作推进表可读
    updates = get_task_updates(team["task"].id, current_user="owner", db=db)
    assert any(u["id"] == sub["id"] for u in updates)

    # 关键任务详情可读
    detail = get_subtask_detail(team["subtask"].id, current_user="owner", db=db)
    assert detail["source_submission"]["id"] == sub["id"]
    assert len(detail["related_achievements"]) >= 1
    assert len(detail["related_issues"]) >= 1


def test_flow3_unconfirmed_submission_not_in_task_updates():
    """确认前的提交（related_task_id 为 null）不出现在工作推进表。"""
    db = _make_session()
    team = _seed_execution_team(db)

    # 提交但不确认
    human_result = {
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "未确认的进展",
                "achievements": [],
                "subtask_issues": [],
            },
        ],
        "special_project": team["project"].name,
    }
    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="任务进展",
        title="未确认进展",
        transcript_text="未确认的进展",
        submitter=team["member"].name,
        human_result=human_result,
    )
    sub_result = asyncio.run(create_update(payload, current_user="member", db=db))

    # 确认前 related_task_id 是 None
    row = db.get(models.UpdateSubmission, sub_result["submission"]["id"])
    assert row.related_task_id is None

    # task updates 不应包含此未确认提交
    updates = get_task_updates(team["task"].id, current_user="owner", db=db)
    assert not any(u["id"] == sub_result["submission"]["id"] for u in updates), \
        "未确认提交不应出现在工作推进表 updates 中（业务口径：确认后才显示）"

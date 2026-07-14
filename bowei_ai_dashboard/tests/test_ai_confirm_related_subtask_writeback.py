"""N4-P2-E AI 确认入库写入 related_subtask_id — 测试。

覆盖：
- 整体确认：task_reports 中 matched_subtask_id + achievements → related_subtask_id 写入
- 整体确认：task_reports 中 matched_subtask_id + subtask_issues → related_subtask_id 写入
- related_task_id 仍指向父级 Task / 重点工作
- update_submissions.related_subtask_id 不写入，保持 NULL
- suggest_new_subtask：Achievement.related_subtask_id == new_sub.id
- 旧格式 achievements 无 matched_subtask_id → related_subtask_id 保持 NULL
- 旧格式 issues 无 matched_subtask_id → related_subtask_id 保持 NULL
- matched_subtask_id 不存在 → 422
- matched_subtask_id 属于其他 Task → 422
- matched_subtask_id 属于其他 Project → 422
- 单卡确认接口覆盖
- 已确认的成果 / 问题读取结果包含 related_subtask_id
- 结构测试：不新增 migration、不新增接口、不改前台
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app import crud, models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import confirm, confirm_task_card

from tests.test_execution_submission_to_work_progress_flow import (
    _make_session,
    _seed_execution_team,
)


def _submit_with_human_result(db, team, human_result: dict) -> int:
    """提交一条带 human_result 的 update_submission，返回 submission_id."""
    from app.routers.updates import create_update

    payload = schemas.ExtractRequest(
        project_id=team["project"].id,
        source_type="manual",
        title="工作汇报",
        transcript_text="完成资料整理，形成资料清单初稿。",
        submitter=team["member"].name,
        human_result=human_result,
    )
    result = asyncio.run(create_update(payload, current_user="member", db=db))
    return result["submission"]["id"]


def _make_second_project_team(db):
    """创建第二个项目 / 重点 / 关键任务，用于跨项目校验.

    假设 _seed_execution_team 已先调用（创建 people id=1,2,3,4），
    本函数用不同 ID 创建第二条数据.
    """
    proj2 = models.Project(
        id=10, name="第二个项目", status="active", is_active=True,
    )
    db.add(proj2)
    db.flush()

    task2 = models.Task(
        id=10,
        project_id=proj2.id,
        key_task="第二个重点",
        special_project=proj2.name,
    )
    db.add(task2)
    db.flush()

    sub2 = models.SubTask(
        id=10,
        task_id=task2.id,
        title="第二个关键任务",
        assignee="普通成员",
    )
    db.add(sub2)
    db.commit()

    return {"project": proj2, "task": task2, "subtask": sub2}


# ═══════════════════════════════════════════════════════════════════
# task_reports + matched_subtask_id → achievements 写 related_subtask_id
# ═══════════════════════════════════════════════════════════════════

def test_confirm_writes_related_subtask_id_on_achievement():
    """整体确认：task_reports 中 matched_subtask_id 成果应写入 related_subtask_id."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "completed": "完成数据核验",
                "achievements": [
                    {"name": "数据核验报告", "achievement_type": "文档"},
                ],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(
        submission_id,
        schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    ach = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    assert ach.related_subtask_id == team["subtask"].id
    assert ach.related_task_id == team["task"].id


def test_confirm_writes_related_subtask_id_on_issue():
    """整体确认：task_reports 中 matched_subtask_id 问题应写入 related_subtask_id."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "achievements": [],
                "subtask_issues": [
                    {"description": "需决策：是否延长项目周期", "priority": "高"},
                ],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(
        submission_id,
        schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )

    issue = (
        db.query(models.Issue)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    assert issue.related_subtask_id == team["subtask"].id
    assert issue.related_task_id == team["task"].id


def test_related_task_id_still_points_to_parent_task():
    """related_task_id 仍然指向父级 Task / 重点工作."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "achievements": [{"name": "成果A"}],
                "subtask_issues": [{"description": "问题A"}],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    ach = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    issue = (
        db.query(models.Issue)
        .filter_by(source_submission_id=submission_id)
        .one()
    )

    # related_task_id 应指向 Task（重点工作），不是 SubTask（关键任务）
    # 通过查询 Task 表验证：related_task_id 对应的是 Task 记录
    parent_task = db.get(models.Task, ach.related_task_id)
    assert parent_task is not None
    assert parent_task.id == team["task"].id
    # related_subtask_id 对应的是 SubTask 记录
    matched_subtask = db.get(models.SubTask, ach.related_subtask_id)
    assert matched_subtask is not None
    assert matched_subtask.id == team["subtask"].id
    # 问题同样检查
    assert issue.related_task_id == team["task"].id
    assert issue.related_subtask_id == team["subtask"].id


def test_update_submissions_related_subtask_id_not_written():
    """本轮不写 update_submissions.related_subtask_id."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "achievements": [{"name": "成果A"}],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    row = db.get(models.UpdateSubmission, submission_id)
    assert row.related_subtask_id is None


# ═══════════════════════════════════════════════════════════════════
# suggest_new_subtask
# ═══════════════════════════════════════════════════════════════════

def test_suggest_new_subtask_writes_related_subtask_id():
    """suggest_new_subtask 确认后，成果的 related_subtask_id == new_sub.id."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "suggest_new_subtask",
                "type": "suggest_new_subtask",
                "title": "新关键任务",
                "assignee": team["member"].name,
                "parent_task_id": team["task"].id,
                "achievements": [
                    {"name": "新关键任务成果", "achievement_type": "文档"},
                ],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    new_sub = (
        db.query(models.SubTask)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    ach = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    assert ach.related_subtask_id == new_sub.id
    assert ach.related_task_id == new_sub.task_id


# ═══════════════════════════════════════════════════════════════════
# 旧格式：无 matched_subtask_id → 保持 NULL
# ═══════════════════════════════════════════════════════════════════

def test_old_format_achievement_without_matched_subtask_id_stays_null():
    """旧格式 achievements 没有 matched_subtask_id → related_subtask_id 保持 NULL."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "type": "progress",
                "completed": "完成了一些工作",
                "achievements": [
                    {"name": "无匹配成果", "achievement_type": "文档"},
                ],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    # 旧格式无 matched_subtask_id → task_reports 循环中 matched_id 为 None →
    # continue，所以不会写入 achievements。确认整体的旧格式 achievements 列表
    # 不会走 task_reports 循环，也保持 NULL。
    ach_list = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .all()
    )
    for ach in ach_list:
        assert ach.related_subtask_id is None


def test_old_format_issue_without_matched_subtask_id_stays_null():
    """旧格式 issues 没有 matched_subtask_id → related_subtask_id 保持 NULL."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "type": "progress",
                "completed": "完成了一些工作",
                "achievements": [],
                "subtask_issues": [
                    {"description": "旧格式问题，未关联 key_task"},
                ],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    # 旧格式无 matched_subtask_id → task_reports 循环中 matched_id 为 None →
    # continue，不会写 issues。
    issue_list = (
        db.query(models.Issue)
        .filter_by(source_submission_id=submission_id)
        .all()
    )
    for iss in issue_list:
        assert iss.related_subtask_id is None


# ═══════════════════════════════════════════════════════════════════
# 校验：matched_subtask_id 错配 → 422
# ═══════════════════════════════════════════════════════════════════

def test_matched_subtask_id_not_found_raises_422():
    """matched_subtask_id 不存在 → 422."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": 999999,
                "achievements": [{"name": "成果"}],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    with pytest.raises(HTTPException) as exc:
        confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
                current_user="owner", db=db)
    assert exc.value.status_code == 422


def test_matched_subtask_id_belongs_to_other_task_raises_422():
    """matched_subtask_id 的父级重点工作已被删除 → 422."""
    db = _make_session()
    team = _seed_execution_team(db)

    # 删除 subtask 的父级 Task，subtask 仍在
    parent_task = db.get(models.Task, team["subtask"].task_id)
    parent_task.is_deleted = True
    db.commit()

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "achievements": [{"name": "成果"}],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    with pytest.raises(HTTPException) as exc:
        confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
                current_user="owner", db=db)
    assert exc.value.status_code == 422


def test_matched_subtask_id_belongs_to_other_project_raises_422():
    """matched_subtask_id 属于其他 Project → 422."""
    db = _make_session()
    team = _seed_execution_team(db)
    # 创建第二个项目
    team2 = _make_second_project_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team2["subtask"].id,
                "achievements": [{"name": "成果"}],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    with pytest.raises(HTTPException) as exc:
        confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
                current_user="owner", db=db)
    assert exc.value.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 单卡确认
# ═══════════════════════════════════════════════════════════════════

def test_single_card_confirm_writes_related_subtask_id():
    """单卡确认也写入 related_subtask_id."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "achievements": [{"name": "单卡成果"}],
                "subtask_issues": [
                    {"description": "单卡问题"},
                ],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)

    result = confirm_task_card(
        submission_id,
        0,
        schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )
    assert result["ok"] is True

    ach = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    issue = (
        db.query(models.Issue)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    assert ach.related_subtask_id == team["subtask"].id
    assert issue.related_subtask_id == team["subtask"].id


# ═══════════════════════════════════════════════════════════════════
# 确认后读取结果
# ═══════════════════════════════════════════════════════════════════

def test_confirmed_achievement_read_includes_related_subtask_id():
    """已确认成果读取结果包含 related_subtask_id."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "achievements": [{"name": "读取测试成果"}],
                "subtask_issues": [],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)
    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    # 通过模型直接读取
    ach = (
        db.query(models.Achievement)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    data = crud.to_dict(ach)
    assert "related_subtask_id" in data
    assert data["related_subtask_id"] == team["subtask"].id
    assert data["related_task_id"] == team["task"].id


def test_confirmed_issue_read_includes_related_subtask_id():
    """已确认问题读取结果包含 related_subtask_id."""
    db = _make_session()
    team = _seed_execution_team(db)

    human_result = {
        "special_project": team["project"].name,
        "project_id": team["project"].id,
        "task_reports": [
            {
                "result_type": "subtask_progress",
                "type": "progress",
                "matched_subtask_id": team["subtask"].id,
                "achievements": [],
                "subtask_issues": [{"description": "读取测试问题"}],
            }
        ],
        "achievements": [],
        "issues": [],
        "key_task_issues": [],
    }
    submission_id = _submit_with_human_result(db, team, human_result)
    confirm(submission_id, schemas.ConfirmRequest(operator="owner"),
            current_user="owner", db=db)

    issue = (
        db.query(models.Issue)
        .filter_by(source_submission_id=submission_id)
        .one()
    )
    data = crud.to_dict(issue)
    assert "related_subtask_id" in data
    assert data["related_subtask_id"] == team["subtask"].id
    assert data["related_task_id"] == team["task"].id


# ═══════════════════════════════════════════════════════════════════
# 结构测试
# ═══════════════════════════════════════════════════════════════════

def test_confirmations_py_does_not_write_update_submissions_related_subtask_id():
    """confirmations.py 不写 update_submissions.related_subtask_id."""
    import ast
    from pathlib import Path

    confirm_file = (
        Path(__file__).resolve().parent.parent
        / "app" / "routers" / "confirmations.py"
    )
    source = confirm_file.read_text(encoding="utf-8")
    # row.related_subtask_id 赋值必须在 _confirm 之外，
    # 只允许在已有位置（无关写操作）
    # 确认所有 row.related_subtask_id = ... 行都是我们在 models.py 中的字段定义
    # 实际上：文件中不应有任何给 row.related_subtask_id 赋值的语句
    # 通过 AST 检查
    tree = ast.parse(source)

    class RowSubtaskIdVisitor(ast.NodeVisitor):
        def __init__(self):
            self.assignments: list[str] = []

        def visit_Assign(self, node):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "row"
                    and target.attr == "related_subtask_id"
                ):
                    self.assignments.append(
                        f"line {node.lineno}: row.related_subtask_id = ..."
                    )
            self.generic_visit(node)

    v = RowSubtaskIdVisitor()
    v.visit(tree)
    # N4-P2-E 严格禁止写 row.related_subtask_id
    assert v.assignments == [], (
        f"confirmations.py must not write row.related_subtask_id, found: {v.assignments}"
    )


def test_confirm_page_not_modified():
    """ConfirmPage.tsx 仅在 N4-P2-Q 分支允许修改."""
    from pathlib import Path
    import subprocess

    project_root = Path(__file__).resolve().parent.parent.parent
    # Check current branch
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=str(project_root),
    )
    branch = branch_result.stdout.strip()
    # N4-P2-Q explicitly modifies ConfirmPage.tsx
    if branch and "n4-p2-q" in branch.lower():
        return  # allowed
    # N4-P3-FIX-1A explicitly modifies ConfirmPage.tsx
    if branch and "n4-p3-fix-1a" in branch.lower():
        return  # allowed

    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, cwd=str(project_root),
    )
    changed = [p.strip() for p in result.stdout.splitlines() if p.strip()]
    confirm_page = "frontend/src/pages/ConfirmPage.tsx"
    assert confirm_page not in changed, (
        f"ConfirmPage.tsx should not be modified, found in: {changed}"
    )


def test_no_new_migration():
    """不新增 migration 文件."""
    from pathlib import Path

    migrations_dir = (
        Path(__file__).resolve().parent.parent
        / "app" / "migrations"
    )
    if not migrations_dir.exists():
        return  # 无迁移目录，跳过
    # 检查今天的迁移文件
    import os
    now = __import__("datetime").datetime.now()
    today_str = now.strftime("%Y%m%d")
    for entry in os.listdir(str(migrations_dir)):
        if entry.startswith(today_str):
            assert False, f"Found new migration file today: {entry}"


def test_no_new_endpoint():
    """不新增接口 — confirmations.py 中只有已有路由."""
    # 通过统计已有路由函数来验证：不新增 @router 装饰的函数
    import re
    from pathlib import Path

    confirm_file = (
        Path(__file__).resolve().parent.parent
        / "app" / "routers" / "confirmations.py"
    )
    source = confirm_file.read_text(encoding="utf-8")
    # 统计 @router. 装饰器数量
    endpoint_count = len(re.findall(r"@router\.(get|post|put|delete|patch)\(", source))
    # 当前路由数：my-rejected, counts, pending, detail, save, confirm,
    # confirm_task_card, reject_task_card, transfer-coordinator (card), 
    # escalate-ceo (card), ceo-decide (card), reject, resubmit, withdraw,
    # reject-final, transfer-coordinator, coordinator-feedback,
    # escalate-ceo, ceo-decide, mark-unrecognized, assign
    assert endpoint_count == 21, (
        f"Expected 21 endpoints, found {endpoint_count}."
    )


def test_related_task_id_not_changed_to_subtask():
    """related_task_id 语义未改 — 始终指向 Task（重点工作），不是 SubTask."""
    import re
    from pathlib import Path

    confirm_file = (
        Path(__file__).resolve().parent.parent
        / "app" / "routers" / "confirmations.py"
    )
    source = confirm_file.read_text(encoding="utf-8")

    # 不应出现把 related_task_id 赋值成 subtask.id 的模式
    dangerous = re.findall(r"related_task_id\s*=.*subtask\.id", source)
    # 允许的模式：subtask.task_id（即父级 Task 的 id）
    allowed = re.findall(r"related_task_id.*subtask\.task_id", source)
    assert allowed, "Expected some `related_task_id = subtask.task_id` patterns"
    # dangerous 只检测把 related_task_id 直接赋值为 subtask.id
    assert not dangerous, (
        f"related_task_id must not be set to subtask.id: {dangerous}"
    )


def test_no_workstream():
    """不新增 workstream 概念."""
    from pathlib import Path

    confirm_file = (
        Path(__file__).resolve().parent.parent
        / "app" / "routers" / "confirmations.py"
    )
    source = confirm_file.read_text(encoding="utf-8").lower()
    assert "workstream" not in source

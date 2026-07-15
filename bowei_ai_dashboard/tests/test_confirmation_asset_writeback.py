"""FIX-2C-2: deterministic task_reports asset writeback contract."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.routers.confirmations import confirm
from tests.test_ai_confirm_related_subtask_writeback import (
    _make_second_project_team,
    _submit_with_human_result,
)
from tests.test_execution_submission_to_work_progress_flow import (
    _make_session,
    _seed_execution_team,
)


B_LONG = "接口读取权限尚未开通，导致自动核验无法继续，需要项目负责人协调技术部门开通权限"
B_SHORT = "接口读取权限尚未开通，导致自动核验无法继续"


def _report(team, *, achievements=None, issues=None, subtask_id=None):
    return {
        "result_type": "subtask_progress",
        "type": "progress",
        "matched_subtask_id": subtask_id or team["subtask"].id,
        "matched_subtask_title": team["subtask"].title,
        "completed": "完成核验",
        "achievements": achievements or [],
        "subtask_issues": issues or [],
    }


def _result(
    team,
    *,
    reports=None,
    achievements=None,
    key_task_issues=None,
    issues=None,
    pending_items=None,
    write_achievements=True,
    write_issues=True,
):
    return {
        "special_project": team["project"].name,
        "task": {
            "write_mode": "task_reports",
            "write_task": False,
            "key_task": team["task"].key_task,
            "status": "进行中",
        },
        "task_reports": reports if reports is not None else [_report(team)],
        "achievements": achievements or [],
        "key_task_issues": key_task_issues or [],
        "issues": issues or [],
        "pending_items": pending_items or [],
        "write_task_reports_achievements": write_achievements,
        "write_task_reports_issues": write_issues,
    }


def _confirm_result(db, team, data):
    submission_id = _submit_with_human_result(db, team, data)
    confirm(
        submission_id,
        schemas.ConfirmRequest(operator="owner"),
        current_user="owner",
        db=db,
    )
    achievements = db.query(models.Achievement).filter(
        models.Achievement.source_submission_id == submission_id
    ).all()
    issues = db.query(models.Issue).filter(
        models.Issue.source_submission_id == submission_id
    ).all()
    return submission_id, achievements, issues


def _fresh():
    db = _make_session()
    return db, _seed_execution_team(db)


def test_w1_report_assets_write_once_with_subtask_attribution():
    db, team = _fresh()
    data = _result(team, reports=[_report(
        team,
        achievements=[{"name": "核验报告", "achievement_type": "文档"}],
        issues=[{"description": "接口阻塞", "issue_type": "问题"}],
    )])
    submission_id, achievements, issues = _confirm_result(db, team, data)

    assert len(achievements) == len(issues) == 1
    assert achievements[0].related_subtask_id == team["subtask"].id
    assert issues[0].related_subtask_id == team["subtask"].id
    assert achievements[0].source_submission_id == submission_id
    assert issues[0].source_submission_id == submission_id


def test_w2_achievement_flag_off_keeps_only_report_issue():
    db, team = _fresh()
    data = _result(
        team,
        reports=[_report(team, achievements=[{"name": "核验报告"}], issues=[{"description": "接口阻塞"}])],
        write_achievements=False,
        write_issues=True,
    )
    _, achievements, issues = _confirm_result(db, team, data)
    assert achievements == []
    assert len(issues) == 1


@pytest.mark.parametrize("frontend_shape", [False, True])
def test_w3_top_level_assets_write_with_task_but_without_subtask(frontend_shape):
    db, team = _fresh()
    top_issue = {"description": "提交级数据阻塞", "issue_type": "待协调"}
    data = _result(
        team,
        reports=[_report(team)],
        achievements=[{"name": "提交级核验总报告", "write_achievement": True}],
        key_task_issues=[top_issue] if frontend_shape else [],
        issues=[] if frontend_shape else [top_issue],
        pending_items=[] if frontend_shape else [top_issue],
    )
    _, achievements, issues = _confirm_result(db, team, data)

    assert len(achievements) == len(issues) == 1
    assert achievements[0].related_task_id == team["task"].id
    assert issues[0].related_task_id == team["task"].id
    assert achievements[0].related_subtask_id is None
    assert issues[0].related_subtask_id is None


def test_w4_empty_assets_write_nothing():
    db, team = _fresh()
    _, achievements, issues = _confirm_result(db, team, _result(team))
    assert achievements == []
    assert issues == []


def test_duplicate_achievement_prefers_report_attribution():
    db, team = _fresh()
    data = _result(
        team,
        reports=[_report(team, achievements=[{"name": "《数据核验报告 V1.0》"}])],
        achievements=[
            {"name": "数据核验报告v1.0"},
            {"name": "  数据核验报告 V1.0  "},
        ],
    )
    _, achievements, _ = _confirm_result(db, team, data)
    assert len(achievements) == 1
    assert achievements[0].related_subtask_id == team["subtask"].id


def test_duplicate_issue_across_all_sources_prefers_report_attribution():
    db, team = _fresh()
    data = _result(
        team,
        reports=[_report(team, issues=[{"description": "问题：接口权限未开通导致自动核验无法继续"}])],
        key_task_issues=[{"description": "接口权限未开通导致自动核验无法继续"}],
        issues=[{"description": "风险：接口权限未开通导致自动核验无法继续"}],
        pending_items=[{"description": "接口权限未开通导致自动核验无法继续"}],
    )
    _, _, issues = _confirm_result(db, team, data)
    assert len(issues) == 1
    assert issues[0].related_subtask_id == team["subtask"].id


def test_duplicate_report_assets_on_same_subtask_write_once_each():
    db, team = _fresh()
    duplicate_report = _report(
        team,
        achievements=[{"name": "重复任务卡成果"}, {"name": "《重复任务卡成果》"}],
        issues=[
            {"description": "接口读取权限尚未开通导致自动核验无法继续"},
            {"description": "接口读取权限仍未开通导致自动核验无法继续"},
        ],
    )
    _, achievements, issues = _confirm_result(db, team, _result(team, reports=[duplicate_report]))
    assert len(achievements) == 1
    assert len(issues) == 1
    assert achievements[0].related_subtask_id == team["subtask"].id
    assert issues[0].related_subtask_id == team["subtask"].id


def test_audit_b_near_duplicate_issue_writes_once():
    db, team = _fresh()
    data = _result(
        team,
        reports=[_report(team, issues=[{"description": B_SHORT}])],
        key_task_issues=[{"description": B_LONG}],
    )
    _, _, issues = _confirm_result(db, team, data)
    assert len(issues) == 1
    assert issues[0].description == B_SHORT
    assert issues[0].related_subtask_id == team["subtask"].id


def test_different_real_issues_are_not_merged():
    db, team = _fresh()
    data = _result(
        team,
        reports=[_report(team)],
        key_task_issues=[{"description": "接口权限未开通导致自动核验无法继续"}],
        issues=[{"description": "客户数据未提供导致人工核验无法继续"}],
    )
    _, _, issues = _confirm_result(db, team, data)
    assert {issue.description for issue in issues} == {
        "接口权限未开通导致自动核验无法继续",
        "客户数据未提供导致人工核验无法继续",
    }


def test_same_issue_on_two_subtasks_keeps_both_attributions():
    db, team = _fresh()
    second = models.SubTask(task_id=team["task"].id, title="第二关键任务", assignee=team["member"].name)
    db.add(second)
    db.commit()
    data = _result(team, reports=[
        _report(team, issues=[{"description": "共同接口阻塞"}]),
        _report(team, issues=[{"description": "共同接口阻塞"}], subtask_id=second.id),
    ])
    _, _, issues = _confirm_result(db, team, data)
    assert len(issues) == 2
    assert {issue.related_subtask_id for issue in issues} == {team["subtask"].id, second.id}


@pytest.mark.parametrize(
    ("write_achievements", "write_issues", "achievement_count", "issue_count"),
    [(True, True, 2, 2), (False, True, 0, 2), (True, False, 2, 0), (False, False, 0, 0)],
)
def test_write_flags_cover_report_and_submission_assets(
    write_achievements, write_issues, achievement_count, issue_count
):
    db, team = _fresh()
    data = _result(
        team,
        reports=[_report(team, achievements=[{"name": "任务卡成果"}], issues=[{"description": "任务卡问题"}])],
        achievements=[{"name": "提交级成果", "write_achievement": True}],
        key_task_issues=[{"description": "提交级问题", "write_issue": True}],
        write_achievements=write_achievements,
        write_issues=write_issues,
    )
    _, achievements, issues = _confirm_result(db, team, data)
    assert len(achievements) == achievement_count
    assert len(issues) == issue_count


def test_item_level_flags_are_respected_for_top_level_assets():
    db, team = _fresh()
    data = _result(
        team,
        achievements=[{"name": "不写成果", "write_achievement": False}],
        key_task_issues=[{"description": "不写问题", "write_issue": False}],
    )
    _, achievements, issues = _confirm_result(db, team, data)
    assert achievements == []
    assert issues == []


def test_invalid_matched_subtask_is_rejected_with_422():
    db, team = _fresh()
    submission_id = _submit_with_human_result(db, team, _result(team, reports=[_report(team, subtask_id=99999)]))
    with pytest.raises(HTTPException) as exc:
        confirm(submission_id, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
    assert exc.value.status_code == 422


def test_cross_project_matched_subtask_is_rejected_without_asset_write():
    db, team = _fresh()
    other = _make_second_project_team(db)
    data = _result(
        team,
        reports=[_report(team, achievements=[{"name": "越权成果"}], issues=[{"description": "越权问题"}], subtask_id=other["subtask"].id)],
    )
    submission_id = _submit_with_human_result(db, team, data)
    with pytest.raises(HTTPException) as exc:
        confirm(submission_id, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
    assert exc.value.status_code == 422
    assert db.query(models.Achievement).filter(models.Achievement.source_submission_id == submission_id).count() == 0
    assert db.query(models.Issue).filter(models.Issue.source_submission_id == submission_id).count() == 0


def test_second_confirm_is_rejected_and_does_not_duplicate_assets():
    db, team = _fresh()
    data = _result(team, reports=[_report(team, achievements=[{"name": "一次成果"}], issues=[{"description": "一次问题"}])])
    submission_id, achievements, issues = _confirm_result(db, team, data)
    with pytest.raises(HTTPException) as exc:
        confirm(submission_id, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)
    assert exc.value.status_code == 409
    assert len(achievements) == len(issues) == 1
    assert db.query(models.Achievement).filter(models.Achievement.source_submission_id == submission_id).count() == 1
    assert db.query(models.Issue).filter(models.Issue.source_submission_id == submission_id).count() == 1


def test_written_assets_have_valid_project_task_and_submission_references():
    db, team = _fresh()
    submission_id, achievements, issues = _confirm_result(
        db,
        team,
        _result(team, achievements=[{"name": "提交成果"}], key_task_issues=[{"description": "提交问题"}]),
    )
    for asset in [*achievements, *issues]:
        assert asset.project_id == team["project"].id
        assert asset.related_task_id == team["task"].id
        assert asset.related_subtask_id is None
        assert asset.source_submission_id == submission_id
        assert db.get(models.Project, asset.project_id) is not None
        assert db.get(models.Task, asset.related_task_id) is not None

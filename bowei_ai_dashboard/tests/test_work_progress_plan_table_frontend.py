from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_task_management_page_has_execution_and_plan_table_views():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    for expected in [
        "PlanTableView",
        "viewMode",
        "执行视图",
        "计划表视图",
        "ensurePlanTableSubTasksLoaded",
        "fetchSubTasks(task.id, false)",
        "taskSubMap",
    ]:
        assert expected in source


def test_plan_table_view_hides_status_stat_cards():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    for expected in [
        "viewMode === 'execution' &&",
        "Status chips",
        "未启动",
        "进行中",
        "已完成",
        "延期",
        "暂缓",
    ]:
        assert expected in source


def test_plan_table_view_hides_execution_only_actions():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    for expected in [
        "viewMode === 'execution' && (",
        "plan-execution-actions",
        "在办",
        "回收站",
        "操作",
    ]:
        assert expected in source


def test_plan_table_view_has_required_excel_like_columns_and_merging():
    source = _frontend_source("components/task-management/PlanTableView.tsx")

    for expected in [
        "目标与重点工作计划表",
        "colSpan={TABLE_HEADERS.length}",
        "plan-table-title-row",
        "plan-table-excel",
        "plan-table-cell",
        "目标",
        "重点工作",
        "评价标准",
        "序号",
        "关键任务",
        "责任人",
        "计划开始时间",
        "计划结束时间",
        "rowSpan",
        "parsePlanTimeRange",
        "border-slate-300",
        "px-2 py-1",
        "w-[120px]",
        "暂无工作推进表数据",
        "可先在项目立项阶段填写工作推进表雏形，或在执行视图中新建重点工作。",
    ]:
        assert expected in source


def test_plan_table_view_reuses_task_subtask_fields_without_new_hierarchy_terms():
    source = _frontend_source("components/task-management/PlanTableView.tsx")

    for expected in [
        "project.objectives",
        "project.description",
        "未填写项目目标",
        "task.key_task",
        "task.completion_standard",
        "task.key_achievement",
        "未填写评价标准",
        "subtask.title",
        "subtask.assignee",
        "task.owner",
        "subtask.plan_time",
        "task.plan_time",
        "暂无关键任务",
    ]:
        assert expected in source

    lowered = source.lower()
    assert "workstream" not in lowered
    assert "第四层" not in source


def test_plan_table_view_weakens_placeholders_without_detail_page_terms():
    source = _frontend_source("components/task-management/PlanTableView.tsx")

    for expected in [
        "plan-table-placeholder",
        "text-slate-400",
        "text-[11px]",
        "未填写项目目标",
        "未填写评价标准",
        "暂无关键任务",
    ]:
        assert expected in source

    assert "详情页" not in source

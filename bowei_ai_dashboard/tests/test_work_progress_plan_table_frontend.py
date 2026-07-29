from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"
PAGE = (ROOT / "pages" / "TaskManagementPage.tsx").read_text(encoding="utf-8")
PLAN = (ROOT / "components" / "task-management" / "PlanTableViewV2.tsx").read_text(encoding="utf-8")


def test_task_management_provides_execution_and_plan_table_modes():
    for symbol in ["PlanTableViewV2", "viewMode", "ensurePlanTableSubTasksLoaded", "fetchSubTasksBatch(missingIds, false)", "taskSubMap"]:
        assert symbol in PAGE


def test_plan_table_reuses_project_task_and_subtask_data():
    for symbol in ["project.objectives", "task.key_task", "subtask.title", "subtask.assignee", "parseProgressTimeline"]:
        assert symbol in PLAN


def test_plan_table_has_excel_style_structure_and_empty_state():
    for symbol in ["v2-", "rowSpan", "暂无"]:
        assert symbol in PLAN

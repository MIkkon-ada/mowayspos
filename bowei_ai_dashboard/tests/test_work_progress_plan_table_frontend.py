from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"
PAGE = (ROOT / "pages" / "TaskManagementPage.tsx").read_text(encoding="utf-8")
PLAN = (ROOT / "components" / "task-management" / "PlanTableViewV2.tsx").read_text(encoding="utf-8")


def test_task_management_provides_plan_table_and_subtask_data_loading():
    for symbol in ["PlanTableViewV2", "ensurePlanTableSubTasksLoaded", "fetchSubTasksBatch(missingIds, false)", "taskSubMap"]:
        assert symbol in PAGE


def test_plan_table_reuses_project_and_key_task_data():
    for symbol in ["project.objectives", "task.key_task", "TaskStandardModal", "ProjectStandardModal"]:
        assert symbol in PLAN


def test_plan_table_has_excel_style_structure_and_empty_state():
    for symbol in ["v2-", "rowSpan", "暂无"]:
        assert symbol in PLAN

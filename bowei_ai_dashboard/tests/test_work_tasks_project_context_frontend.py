from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_work_tasks_sidebar_entry_carries_current_project_context():
    source = _frontend_source("domain/authFlow.ts")

    assert "if (page === 'table' && currentProjectId !== null)" in source
    assert "`/work/tasks?projectId=${currentProjectId}`" in source


def test_work_tasks_without_project_context_does_not_fetch_global_task_list():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    assert "effectiveTaskProjectId" in source
    assert "requiresProjectSelection" in source
    assert "autoSelectedTaskProjectId" in source
    assert "TASK_PROJECT_CONTEXT_REQUIRED_MESSAGE" in source
    assert "TASK_PROJECT_CONTEXT_EMPTY_MESSAGE" in source
    assert "fetchTasks(pid, showDeleted)" not in source
    assert "fetchTasks(pid, effectiveDeleted)" not in source


def test_work_tasks_project_context_handles_single_and_multiple_projects():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    assert "availableTaskProjects" in source
    assert "availableTaskProjects.length === 1" in source
    assert "setAutoSelectedTaskProjectId(availableTaskProjects[0].id)" in source
    assert "<select" in source
    assert "value={String(effectiveTaskProjectId ?? '')}" in source
    assert "onChange={(event) => {" in source


def test_work_tasks_error_messages_are_project_context_aware():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    assert "TASK_PROJECT_CONTEXT_MISSING_ENTRY_MESSAGE" in source
    assert "TASK_PROJECT_PERMISSION_DENIED_MESSAGE" in source
    assert "任务列表加载失败，请刷新重试" not in source


def test_work_tasks_project_context_does_not_change_backend_or_forbidden_scope():
    route_source = _frontend_source("app/routes.tsx")
    page_source = _frontend_source("pages/TaskManagementPage.tsx")

    assert '<Route path="tasks" element={<TaskManagementPage />} />' in route_source
    for forbidden in ["Workstream", "workstream", "第四层", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in page_source

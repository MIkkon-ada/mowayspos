from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_active_work_progress_uses_project_members_for_key_task_assignment():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    assert "getProjectMembers" in source
    assert "projectMembersByProject" in source
    assert "ensureProjectMembersLoaded" in source
    assert "person_name_snapshot" in source
    assert "SubTaskAssignmentModal" in source
    assert "assignmentMembers" in source

    # 关键任务执行期派发不能从全员 people 列表直接选人。
    assert "apiGet<Person[]>('/api/people')" not in source


def test_active_work_progress_gates_create_and_edit_by_role_and_project_status():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    for expected in [
        "canManageProjectWork",
        "isProjectActive",
        "canAssignSubTasks",
        "openSubTaskAssignment",
        "项目尚未进入执行阶段，暂不能维护执行期关键任务。",
        "新增关键任务",
        "编辑关键任务",
    ]:
        assert expected in source

    # 成员可以更新自己的状态，但不能看到结构派发入口；结构派发必须走 canManageProjectWork。
    assert "canEditSubTaskStatus" in source
    assert "canAssignSubTasks" in source


def test_key_task_assignment_modal_keeps_existing_subtask_payload_contract():
    source = _frontend_source("pages/TaskManagementPage.tsx")

    for expected in [
        "关键任务名称",
        "责任人",
        "协助人",
        "时间段",
        "备注 / 标准",
        "createSubTask(taskId",
        "updateSubTask(editingSubTask.id",
        "project_id: projectId",
        "title:",
        "assignee:",
        "plan_time:",
        "completion_criteria:",
        "notes:",
    ]:
        assert expected in source

    # helper 只能兼容写入现有 notes/备注，不允许偷偷扩展接口 payload。
    assert "helper:" not in source
    assert "Workstream" not in source
    assert "第四层" not in source
    assert "客户侧" not in source
    assert "过程支持" not in source
    assert "过程保障" not in source

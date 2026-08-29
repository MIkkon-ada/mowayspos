from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_owner_submit_modal_contains_work_progress_draft_controls():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "工作推进方案",
        "新增重点工作",
        "新增关键任务",
        "重点工作名称",
        "目标成果 / 验收标准",
        "责任人",
        "协助人",
        "时间段",
        "备注 / 标准",
        "work_progress_draft",
    ]:
        assert expected in source

    for forbidden in ["计划开始", "计划结束", "评价标准"]:
        assert forbidden not in source


def test_owner_submit_modal_builds_work_progress_draft_submit_payload():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")
    api_source = _frontend_source("api/projects.ts")

    for expected in [
        "work_progress_draft?: ProjectWorkProgressTaskDraft[]",
        "export type ProjectWorkProgressTaskDraft",
        "export type ProjectWorkProgressSubTaskDraft",
        "title: string",
        "description?: string",
        "owner?: string",
        "helper?: string",
        "plan_start?: string",
        "plan_end?: string",
        "subtasks?: ProjectWorkProgressSubTaskDraft[]",
        "evaluation_standard?: string",
        "assignee?: string",
        "assignee_id?: number",
        "helper_ids?: number[]",
    ]:
        assert expected in api_source

    for expected in [
        "function toPayloadDraft(tasks: LocalTaskDraft[]): ProjectWorkProgressTaskDraft[]",
        "title: task.title.trim()",
        "description: task.description.trim()",
        "owner: task.owner.trim()",
        "helper: task.helper.trim()",
        "plan_start: task.plan_start",
        "plan_end: task.plan_end",
        "subtasks: task.subtasks",
        "title: subtask.title.trim()",
        "evaluation_standard: subtask.evaluation_standard.trim()",
        "assignee: subtask.assignee.trim()",
        "assignee_id: subtask.assigneeId || undefined",
        "helper_ids: subtask.helperIds",
        "helper: subtask.helper.trim()",
        "plan_start: subtask.plan_start",
        "plan_end: subtask.plan_end",
        "const workProgressDraft = toSubmitDraft(currentAiDraft())",
        "currentAiDraft",
        "toCurrentDraft",
        "const result = await ownerSubmitProfile(project.id, {",
        "work_progress_draft: workProgressDraft",
        "基础信息由管理层维护",
    ]:
        assert expected in source
    assert "...fillForm" not in source


def test_owner_submit_modal_uses_people_picker_for_key_tasks():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in ["fetchPeople", "AssigneePicker", "HelperPicker", "assigneeId", "helperIds", "helperIds.includes"]:
        assert expected in source
    assert 'placeholder="责任人"' not in source


def test_project_review_view_contains_work_progress_draft_summary_and_list():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "getDraftSummary",
        "buildDraftRows",
        "DraftProgressTable",
        "summary.taskCount",
        "summary.subtaskCount",
        "draftRows.length",
    ]:
        assert expected in source


def test_owner_submit_modal_requires_at_least_one_subtask_before_submit():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "const workProgressDraft = toSubmitDraft(currentAiDraft())",
        "currentAiDraft",
        "workProgressDraft.reduce",
        "task.subtasks?.length",
        "请至少添加一个关键任务",
        "ownerSubmitProfile(project.id, {",
        "work_progress_draft: workProgressDraft",
    ]:
        assert expected in source


def test_owner_submit_modal_defers_raw_assignee_resolution_to_submission():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "task.subtasks?.some((subtask) => !subtask.assignee_id && !subtask.assignee?.trim())" in source
    assert "请为每个关键任务填写负责人" in source
    assert "task.subtasks?.some((subtask) => !subtask.assignee_id)" not in source


def test_owner_submit_modal_shows_imported_assignee_pending_server_resolution():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "rawName={subtask.assignee}" in source
    assert "待自动添加：{rawName.trim()}" in source
    assert "将在提交时自动添加或匹配人员" in source


def test_owner_submit_modal_shows_imported_helpers_pending_server_resolution():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")
    helper_picker = source.split("function HelperPicker", maxsplit=1)[1].split("export function OwnerSubmitWorkbench", maxsplit=1)[0]

    assert "rawName={subtask.helper}" in source
    assert "rawName: string" in helper_picker
    assert "待自动添加：{rawName.trim()}" in helper_picker
    assert "将在提交时自动添加或匹配人员" in helper_picker


def test_project_approve_modal_contains_work_progress_draft_summary():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "function ProjectApproveModal",
        "draftSummary",
        "draftRows",
        "工作推进表雏形",
        "重点工作数量",
        "关键任务数量",
        "暂无工作推进表雏形",
        "详细内容可在项目详情面板查看",
        "draftRows.slice(0, 3)",
    ]:
        assert expected in source

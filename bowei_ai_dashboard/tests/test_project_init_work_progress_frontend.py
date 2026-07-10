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
        "helper: subtask.helper.trim()",
        "plan_start: subtask.plan_start",
        "plan_end: subtask.plan_end",
        "const workProgressDraft = toPayloadDraft(draftTasks)",
        "const result = await ownerSubmitProfile(project.id, {",
        "...fillForm",
        "work_progress_draft: workProgressDraft",
    ]:
        assert expected in source


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
        "const workProgressDraft = toPayloadDraft(draftTasks)",
        "workProgressDraft.reduce",
        "task.subtasks?.length",
        "请至少添加一个关键任务",
        "ownerSubmitProfile(project.id, {",
        "work_progress_draft: workProgressDraft",
    ]:
        assert expected in source


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

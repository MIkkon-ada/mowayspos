from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _frontend_source(relative_path: str) -> str:
    return (_repo_root() / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_owner_submit_modal_uses_final_workbench_structure():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "项目核心信息",
        "项目名称",
        "项目周期 / 时间段",
        "项目完成准则 / 验收标准",
        "补充详细信息",
        "客户名称",
        "项目背景",
        "补充说明",
        "工作推进方案",
    ]:
        assert expected in source

    assert "<details" in source, "补充详细信息应使用默认折叠区域"
    assert "预期交付物" not in source, "不应再把预期交付物作为显眼字段"


def test_owner_submit_modal_task_and_subtask_semantics_are_finalized():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "重点工作名称",
        "目标成果 / 验收标准",
        "关键任务",
        "责任人",
        "协助人",
        "时间段",
        "备注 / 标准",
    ]:
        assert expected in source

    for forbidden in [
        "重点工作责任人",
        "重点工作协助人",
        "重点工作开始日期",
        "重点工作结束日期",
        "计划开始",
        "计划结束",
    ]:
        assert forbidden not in source

    assert "评价标准" not in source, "关键任务不应再把评价标准作为强字段文案"


def test_owner_submit_modal_keeps_payload_contract_with_period_helpers():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "function composeProjectPeriod",
        "function parseProjectPeriod",
        "function composeTaskPeriod",
        "function parseTaskPeriod",
        "function toPayloadDraft",
        "const workProgressDraft = toPayloadDraft(draftTasks)",
        "ownerSubmitProfile(project.id, {",
        "work_progress_draft: workProgressDraft",
        "plan_start: subtask.plan_start",
        "plan_end: subtask.plan_end",
    ]:
        assert expected in source


def test_owner_submit_modal_does_not_import_external_visual_dependencies():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")
    package_json = (_repo_root() / "frontend" / "package.json").read_text(encoding="utf-8")

    for forbidden in [
        "fonts.googleapis.com",
        "Material Symbols",
        "material-symbols",
        "cdn.tailwindcss.com",
        "Workstream",
        "workstream",
        "第四层",
        "客户侧",
        "过程支持",
        "过程保障",
    ]:
        assert forbidden not in source
        assert forbidden not in package_json

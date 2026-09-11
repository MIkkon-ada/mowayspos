from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_owner_submit_modal_has_current_three_zone_workbench_layout():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "owner-submit-workbench-shell",
        "owner-submit-workbench-header",
        "owner-submit-workbench-main",
        "owner-submit-workbench-columns",
        "owner-submit-workbench-footer",
        "bg-[#f7f9fc]",
        "overflow-y-auto",
        "shrink-0",
    ]:
        assert expected in source
    # Do not reject the valid `min-h-[72px]` footer class by substring match.
    assert "className=\"h-[72px]" not in source


def test_owner_submit_workbench_fills_the_page_area_without_modal_framing():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "owner-submit-workbench-shell flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-[#f7f9fc]" in source
    assert "w-[96vw]" not in source
    assert "max-w-[1560px]" not in source
    assert "owner-submit-workbench-shell mx-auto" not in source
    assert "owner-submit-workbench-shell flex min-h-0 w-full flex-1 flex-col overflow-hidden rounded-xl" not in source
    assert "owner-submit-workbench-shell flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-[#f7f9fc] text-slate-900 shadow-[0_18px_50px_rgba(15,23,42,0.16)]" not in source
    assert "w-[820px]" not in source
    assert "max-w-[1280px]" not in source


def test_project_core_info_is_current_left_sidebar():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "owner-submit-left-pane",
        "lg:w-[360px]",
        "owner-submit-right-pane",
        "min-w-0 flex-1",
        "sticky",
    ]:
        assert expected in source


def test_project_info_area_uses_current_compact_card_style():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "owner-submit-project-summary owner-submit-project-summary-display owner-submit-core-card",
        "rounded-2xl border border-slate-200 bg-white",
        "项目概览",
        "项目编号",
        "项目状态",
        "项目周期",
        "项目目标",
        "项目背景",
        "补充说明",
        "项目说明",
        "项目角色",
    ]:
        assert expected in source


def test_ai_preview_warning_is_scoped_to_preview_instead_of_wrapping_workplan():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "bg-amber-50/40" not in source
    assert 'data-testid="owner-submit-ai-preview"' in source
    assert "border border-amber-200 bg-amber-50" in source


def test_task_group_uses_current_compact_card_style():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "owner-submit-workplan-heading",
        "owner-submit-b-split",
        "owner-submit-title-display",
        "owner-submit-goal-result",
        "验收标准 / 关键成果",
        "推进流程",
        "owner-submit-subtask-table",
        "lg:min-w-0",
    ]:
        assert expected in source


def test_subtask_uses_current_table_like_layout():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "<table",
        "owner-submit-subtask-table",
        "border-separate border-spacing-0",
        "thead",
        "tbody",
        "时间段",
        "评价指标",
        "owner-submit-subtask-drag-handle",
        "owner-submit-date-icon",
        "owner-submit-subtask-delete-icon",
    ]:
        assert expected in source


def test_owner_submit_modal_keeps_task_and_subtask_semantics():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "subtask.assignee",
        "subtask.helper",
        "subtask.plan_start",
        "subtask.plan_end",
        "subtask.evaluation_standard",
        "工作推进方案",
    ]:
        assert expected in source
    for forbidden in ["Workstream", "workstream", "客户伙伴", "过程支持", "过程保障"]:
        assert forbidden not in source


def test_payload_compatibility_uses_latest_ai_aware_draft():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "function toPayloadDraft" in source
    assert "currentAiDraft" in source
    assert "toCurrentDraft" in source
    assert "toSubmitDraft" in source
    assert "const workProgressDraft = toSubmitDraft(currentAiDraft())" in source
    assert "work_progress_draft: workProgressDraft" in source
    assert "buildAiMergePreview" in source


def test_ai_merge_preview_is_confirmed_before_form_is_replaced():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "OwnerSubmitAiPanel" in source
    assert "data-testid=\"owner-submit-ai-preview\"" in source
    assert "confirmAiPreview" in source
    assert "applyMergedDraftToForm(latestPreview.draft)" in source
    assert "buildAiMergePreview(current, savedAiDraftRef.current" in source
    assert "applyMergedDraftToForm(aiPreview.draft)" not in source


def test_original_submit_validation_and_single_submit_path_remain():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "if (workProgressDraft.length === 0)" in source
    assert "workProgressDraft.reduce" in source
    assert "if (subtaskCount === 0)" in source
    assert "!subtask.assignee_id" in source
    assert source.count("ownerSubmitProfile(") == 1
    assert "setFillLoading(true)" in source

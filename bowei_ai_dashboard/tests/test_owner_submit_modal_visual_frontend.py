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
    assert "h-[72px]" not in source


def test_owner_submit_modal_width_uses_current_workbench_limits():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "w-[96vw]" in source
    assert "max-w-[1560px]" in source
    assert "mx-auto" in source
    assert "w-[820px]" not in source
    assert "max-w-[1280px]" not in source


def test_project_core_info_is_current_left_sidebar():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "owner-submit-left-pane",
        "lg:w-[280px]",
        "xl:w-[300px]",
        "owner-submit-right-pane",
        "flex-1 min-w-0",
        "sticky",
    ]:
        assert expected in source


def test_project_info_area_uses_current_compact_card_style():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for expected in [
        "owner-submit-core-card",
        "rounded-2xl border border-slate-200 bg-white",
        "shadow-[0_8px_24px_rgba(15,23,42,0.05)]",
        "space-y-5",
        "基础信息由管理层维护",
        "owner-submit-project-summary-display",
        "owner-submit-project-period-display",
        "项目完成准则 / 验收标准",
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
        "owner-submit-task-group",
        "overflow-hidden rounded-2xl border border-slate-200 bg-white",
        "owner-submit-task-group-header",
        "bg-slate-50",
        "md:grid-cols-2",
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
        "border-none bg-transparent p-0",
        "时间段",
        "备注 / 标准",
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

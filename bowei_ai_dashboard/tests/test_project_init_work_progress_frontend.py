from __future__ import annotations

from pathlib import Path


def test_owner_submit_modal_contains_work_progress_draft_controls():
    root = Path(__file__).resolve().parents[2]
    source = (root / "frontend" / "src" / "features" / "settings" / "OwnerSubmitModal.tsx").read_text(
        encoding="utf-8"
    )

    for expected in [
        "工作推进表雏形",
        "新增重点工作",
        "新增关键任务",
        "重点工作说明",
        "责任人",
        "协助人",
        "计划开始",
        "计划结束",
        "评价标准",
        "work_progress_draft",
    ]:
        assert expected in source


def test_project_review_view_contains_work_progress_draft_summary_and_list():
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "frontend" / "src" / "features" / "settings" / "ProjectsMgmtSection.tsx"
    ).read_text(encoding="utf-8")

    for expected in [
        "getDraftSummary",
        "buildDraftRows",
        "DraftProgressTable",
        "summary.taskCount",
        "summary.subtaskCount",
        "draftRows.length",
    ]:
        assert expected in source

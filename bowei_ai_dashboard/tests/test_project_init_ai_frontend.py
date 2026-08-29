from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_owner_submit_ai_panel_exposes_upload_progress_preview_and_apply_states():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")

    for expected in [
        "AI 从文件生成",
        "读取文件",
        "提取结构",
        "匹配人员",
        "生成草稿",
        "疑似重复",
        "待确认",
        "应用到推进表",
        "setInterval",
        "1500",
        'accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"',
        "onApplyDraft",
        "definite_duplicate",
        "possible_duplicate",
        "source_label",
        "attachment_id",
    ]:
        assert expected in source


def test_owner_submit_ai_panel_does_not_apply_to_backend_or_render_untrusted_html():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")

    assert "applyInitAnalysisRun" not in source
    assert "dangerouslySetInnerHTML" not in source


def test_owner_submit_ai_warning_preview_labels_ambiguous_inactive_and_unmatched_people():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")
    for label in ("低置信度", "人员匹配不明确", "人员已停用", "未匹配人员"):
        assert label in source


def test_owner_submit_ai_preview_offers_rerun_for_existing_attachments():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")
    preview_source = source.split("{panelState === 'preview' && run && draft && (", maxsplit=1)[1]

    assert "重新分析" in preview_source
    assert "onClick={() => void startAnalysis()}" in preview_source


def test_owner_submit_ai_rerun_resets_preview_choices_and_rejects_duplicate_starts():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")
    start_analysis_source = source.split("async function startAnalysis()", maxsplit=1)[1].split("async function retryAnalysis()", maxsplit=1)[0]

    assert "const analysisStartInFlightRef = useRef(false)" in source
    assert "if (!canBeginAnalysisRequest(analysisStartInFlightRef.current)) return" in start_analysis_source
    assert "analysisStartInFlightRef.current = true" in start_analysis_source
    assert "function resetAnalysisPreview()" in source
    assert "resetAnalysisPreview()" in start_analysis_source
    assert "analysisStartInFlightRef.current = false" in start_analysis_source


def test_owner_submit_ai_failed_rerun_of_completed_preview_starts_a_new_analysis():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")
    retry_analysis_source = source.split("async function retryAnalysis()", maxsplit=1)[1].split("function setDecision", maxsplit=1)[0]

    assert "if (!run || run.status !== 'failed')" in retry_analysis_source
    assert "await startAnalysis()" in retry_analysis_source


def test_owner_submit_ai_failed_run_retry_resets_preview_choices_and_rejects_duplicates():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")
    retry_analysis_source = source.split("async function retryAnalysis()", maxsplit=1)[1].split("function setDecision", maxsplit=1)[0]

    assert "if (!canBeginAnalysisRequest(analysisStartInFlightRef.current)) return" in retry_analysis_source
    assert "analysisStartInFlightRef.current = true" in retry_analysis_source
    assert "resetAnalysisPreview()" in retry_analysis_source
    assert "setRun(undefined)" in retry_analysis_source
    assert "analysisStartInFlightRef.current = false" in retry_analysis_source

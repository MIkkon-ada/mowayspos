from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_voice_update_page_defaults_to_all_work_and_keeps_deep_link_binding():
    source = _frontend_source("pages/VoiceUpdatePage.tsx")

    assert "searchParams.get('projectId')" in source
    assert "isProjectActive" in source
    assert "activeProjects" in source
    assert "useState<VoiceReportScope>('all')" in source
    assert "setReportScope('task')" in source
    assert "setSelectedProjectId(requestedProject.id)" in source
    assert "else setReportScope('project')" in source


def test_voice_update_page_blocks_project_only_for_scoped_reports():
    page_source = _frontend_source("pages/VoiceUpdatePage.tsx")
    submit_panel_source = _frontend_source("features/voice-update/VoiceUpdateSubmitPanel.tsx")
    submission_hook_source = _frontend_source("features/voice-update/useVoiceSubmission.ts")

    assert "reportScope === 'all'" in page_source
    assert "reportScope === 'task'" in page_source
    assert "projectSubmitBlockedReason" in page_source
    assert "projectSubmitBlockedReason={projectSubmitBlockedReason}" in page_source

    assert "projectSubmitBlockedReason" in submit_panel_source
    assert ": projectSubmitBlockedReason" in submit_panel_source
    assert "&& !hasMissingSuggestionOwner" in submit_panel_source
    assert "disabled={!canSubmit}" in submit_panel_source
    assert "AI 自动识别" not in submit_panel_source

    assert "reportScope === 'task' && !projectId" in submission_hook_source
    assert "reportScope !== 'task'" in submission_hook_source


def test_voice_extract_and_submit_requests_are_scope_aware():
    extraction_source = _frontend_source("features/voice-update/useVoiceExtraction.ts")
    submission_source = _frontend_source("features/voice-update/useVoiceSubmission.ts")

    assert "reportScope === 'all' ? undefined" in extraction_source
    assert "report_scope: reportScope" in extraction_source
    assert "...(projectId ? { project_id: projectId } : {})" in extraction_source
    assert "project_id: projectId" in submission_source
    assert "createUpdateBatch" in submission_source


def test_project_scoped_voice_entry_carries_project_id():
    source = _frontend_source("domain/authFlow.ts")

    assert "if (page === 'voice' && currentProjectId !== null)" in source
    assert "`/work/submit?projectId=${currentProjectId}`" in source
    assert "voice: '/work/submit'" not in source


def test_work_submit_project_binding_does_not_change_backend_or_routes_or_forbidden_scope():
    route_source = _frontend_source("app/routes.tsx")
    page_source = _frontend_source("pages/VoiceUpdatePage.tsx")
    hook_source = _frontend_source("features/voice-update/useVoiceSubmission.ts")

    assert '<Route path="submit" element={<VoiceUpdatePage />} />' in route_source
    assert "Workstream" not in page_source
    assert "workstream" not in page_source.lower()
    for forbidden in ["第四层", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in page_source
        assert forbidden not in hook_source

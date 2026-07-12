from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_voice_update_page_uses_url_manual_and_single_active_project_binding():
    source = _frontend_source("pages/VoiceUpdatePage.tsx")

    assert "searchParams.get('projectId')" in source
    assert "isProjectActive" in source
    assert "activeProjects" in source
    assert "activeProjects.length === 1" in source
    assert "setSelectedProjectId(activeProjects[0].id)" in source
    assert "<select" in source
    assert "所属项目：请选择项目" in source
    assert "AI 负责提取内容，项目归属以你选择的项目为准。" in source


def test_voice_update_page_blocks_missing_or_non_active_project_before_extract_and_submit():
    page_source = _frontend_source("pages/VoiceUpdatePage.tsx")
    submit_panel_source = _frontend_source("features/voice-update/VoiceUpdateSubmitPanel.tsx")
    submission_hook_source = _frontend_source("features/voice-update/useVoiceSubmission.ts")

    expected_inactive_message = "项目尚未进入执行阶段，暂不能提交正式工作汇报，请完成立项审核后再提交。"
    expected_missing_message = "请先选择所属项目，再提交给负责人。"

    assert expected_inactive_message in page_source
    assert expected_missing_message in page_source
    assert "projectSubmitBlockedReason" in page_source
    assert "handleBoundProjectExtract" in page_source
    assert "projectExtractBlockedReason" in page_source
    assert "projectSubmitBlockedReason={projectSubmitBlockedReason}" in page_source

    assert "projectSubmitBlockedReason" in submit_panel_source
    assert "disabled={phase === 'extracting' || !text.trim() || Boolean(projectSubmitBlockedReason)}" in submit_panel_source
    assert "disabled={phase === 'submitting' || hasMissingSuggest || Boolean(projectSubmitBlockedReason)}" in submit_panel_source
    assert "AI 自动识别" not in submit_panel_source

    assert "if (!projectId)" in submission_hook_source
    assert expected_missing_message in submission_hook_source


def test_voice_extract_and_submit_requests_require_project_id_payload():
    extraction_source = _frontend_source("features/voice-update/useVoiceExtraction.ts")
    submission_source = _frontend_source("features/voice-update/useVoiceSubmission.ts")

    assert "if (!selectedProjectId)" in extraction_source
    assert "请先选择所属项目，再进行 AI 提取。" in extraction_source
    assert "project_id: projectId" in extraction_source
    assert "project_id: projectId" in submission_source
    assert "...(projectId ? { project_id: projectId } : {})" not in extraction_source
    assert "...(projectId ? { project_id: projectId } : {})" not in submission_source


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

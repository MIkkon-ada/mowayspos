from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_asset_pages_sidebar_entries_carry_current_project_context():
    source = _frontend_source("domain/authFlow.ts")

    assert "if (page === 'achievements' && currentProjectId !== null)" in source
    assert "`/work/achievements?projectId=${currentProjectId}`" in source
    assert "if (page === 'issues' && currentProjectId !== null)" in source
    assert "`/work/issues?projectId=${currentProjectId}`" in source


def test_asset_pages_keep_global_fallback_without_project_context():
    source = _frontend_source("domain/authFlow.ts")

    assert "achievements: '/work/achievements'" in source
    assert "issues: '/work/issues'" in source


def test_existing_voice_and_table_project_context_navigation_is_unchanged():
    source = _frontend_source("domain/authFlow.ts")

    assert "if (page === 'voice' && currentProjectId !== null)" in source
    assert "`/work/submit?projectId=${currentProjectId}`" in source
    assert "if (page === 'table' && currentProjectId !== null)" in source
    assert "`/work/tasks?projectId=${currentProjectId}`" in source


def test_asset_pages_project_context_does_not_add_backend_contract_or_forbidden_scope():
    auth_source = _frontend_source("domain/authFlow.ts")
    route_source = _frontend_source("app/routes.tsx")

    assert '<Route path="achievements" element={<AchievementsPage />} />' in route_source
    assert '<Route path="issues" element={<IssuesPage />} />' in route_source
    assert "/api/" not in auth_source
    for forbidden in ["Workstream", "workstream", "第四层", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in auth_source

"""FIX-2D: legacy confirmation route preserves project context."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTES = ROOT / "frontend" / "src" / "app" / "routes.tsx"


def _source() -> str:
    return ROUTES.read_text(encoding="utf-8")


def _project_routes(source: str) -> str:
    start = source.index('path="/project/:projectId"')
    end = source.index('path="/client/*"', start)
    return source[start:end]


def _legacy_redirect(source: str) -> str:
    start = source.index("function LegacyProjectRedirect")
    end = source.index("function LegacyMemberProjectRedirect", start)
    return source[start:end]


def test_project_legacy_route_and_confirmation_child_still_exist():
    source = _source()
    project = _project_routes(source)
    assert 'path="/project/:projectId"' in source
    assert re.search(r'<Route\s+path="confirm"', project)


def test_confirmation_child_targets_work_confirmations_with_project_id():
    project = _project_routes(_source())
    match = re.search(
        r'<Route\s+path="confirm"\s+element=\{'
        r'<LegacyProjectRedirect\s+to="/work/confirmations"\s+includeProjectId\s*/>'
        r'\}\s*/>',
        project,
    )
    assert match is not None


def test_legacy_redirect_builds_project_id_query_and_keeps_replace():
    helper = _legacy_redirect(_source())
    assert "includeProjectId && projectId" in helper
    assert "`${to}?projectId=${projectId}`" in helper
    assert "<Navigate to={target} replace />" in helper


def test_formal_confirmation_route_is_unchanged_and_unique():
    source = _source()
    assert '<Route path="confirmations" element={<ConfirmPage />} />' in source
    assert source.count("<ConfirmPage />") == 1


def test_decisions_still_use_legacy_coach_decision_redirect():
    project = _project_routes(_source())
    assert '<Route path="decisions" element={<LegacyCoachDecisionRedirect />} />' in project
    assert "params.set('view', 'ceo')" in _source()


def test_project_route_still_uses_existing_auth_and_project_guards():
    source = _source()
    start = source.index('path="/project/:projectId"')
    wrapper = source[start:source.index(">", source.index("</RequireAuth>", start)) + 1]
    assert "<RequireAuth>" in wrapper
    assert "<RequireProject>" in wrapper
    assert "</RequireProject>" in wrapper
    assert "</RequireAuth>" in wrapper


def test_other_legacy_routes_keep_their_existing_redirect_types():
    project = _project_routes(_source())
    assert '<Route path="tasks" element={<LegacyProjectRedirect to="/work/tasks" includeProjectId />} />' in project
    assert '<Route path="mytasks" element={<LegacyMemberProjectRedirect />} />' in project
    assert '<Route path="decisions" element={<LegacyCoachDecisionRedirect />} />' in project


def test_test_contract_has_no_repository_history_dependency():
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = ["git " + value for value in ("diff", "status", "rev-parse")]
    forbidden.extend(["." + "git", "8eb1958f" + "e777d1200672e0b7f8db54a167ec5c81"])
    assert all(value not in source for value in forbidden)

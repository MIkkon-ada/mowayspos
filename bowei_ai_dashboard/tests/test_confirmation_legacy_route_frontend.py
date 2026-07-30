"""Compatibility routing contract for the current confirmation workspace."""

from pathlib import Path


ROUTES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "routes.tsx"


def _routes() -> str:
    return ROUTES.read_text(encoding="utf-8")


def test_legacy_coach_decision_route_redirects_to_confirmation_workspace():
    source = _routes()
    start = source.index("function LegacyCoachDecisionRedirect")
    end = source.index("function ConfirmationCenterRoute", start)
    body = source[start:end]
    assert "params.set('view', 'ceo')" in body
    assert "<Navigate" in body and "replace" in body


def test_confirmation_route_uses_the_reviewer_only_workspace_guard():
    source = _routes()
    assert "function ConfirmationCenterRoute" in source
    assert "<Route path=\"confirmations\" element={<ConfirmationCenterRoute />} />" in source
    assert "currentUser?.is_tech_admin" in source


def test_project_legacy_decision_route_keeps_compatibility_redirect():
    source = _routes()
    assert "<Route path=\"decisions\" element={<LegacyCoachDecisionRedirect />} />" in source

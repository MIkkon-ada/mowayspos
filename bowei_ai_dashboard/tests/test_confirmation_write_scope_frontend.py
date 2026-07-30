"""Write-destination controls in the current inline owner action panel."""

from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "ConfirmPage.tsx"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_asset_write_toggles_have_independent_state():
    source = _page()
    assert "const [writeToAchievements, setWriteToAchievements]" in source
    assert "const [writeToIssues, setWriteToIssues]" in source


def test_owner_panel_renders_two_real_asset_destination_switches():
    source = _page()
    assert "role=\"switch\"" in source
    assert "aria-checked={writeToAchievements}" in source
    assert "aria-checked={writeToIssues}" in source
    assert "setWriteToAchievements((value) => !value)" in source
    assert "setWriteToIssues((value) => !value)" in source


def test_asset_switches_use_submission_lock_and_keep_task_write_fixed():
    source = _page()
    assert "disabled={submissionActionsLocked}" in source
    assert "工作推进表始终写入；成果和问题按现有开关处理。" in source
    assert "{viewMode === 'all' && canUseOwnerActions" in source

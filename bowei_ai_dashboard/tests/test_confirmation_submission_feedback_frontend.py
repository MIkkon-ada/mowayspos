"""Feedback contract for the inline confirmation workspace."""

from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "ConfirmPage.tsx"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_page_uses_shared_action_feedback_state():
    source = _page()
    assert "const [actionSuccess, setActionSuccess]" in source
    assert "const [actionError, setActionError]" in source
    assert "setActionSuccess(" in source
    assert "setActionError(" in source


def test_inline_card_detail_shows_read_only_coordinator_and_coach_notes():
    source = _page()
    assert "activeCard.coordinatorNote" in source
    assert "activeCard.ceoNote" in source
    assert "协调人建议" in source
    assert "企业教练决策" in source


def test_owner_actions_remain_separate_from_coordinator_and_coach_panels():
    source = _page()
    assert "{viewMode === 'all' && canUseOwnerActions" in source
    assert "{viewMode === 'coordinator'" in source
    assert "{viewMode === 'ceo'" in source


def test_status_changing_handlers_refresh_their_queues():
    source = _page()
    assert "await reloadCoordinatorItems()" in source
    assert "reloadCoachItems()" in source
    assert "setItems((prev)" in source

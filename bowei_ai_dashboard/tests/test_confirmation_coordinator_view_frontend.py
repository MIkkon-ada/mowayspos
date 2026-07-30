"""Structural contract for the current inline coordinator review workspace."""

from pathlib import Path


PAGE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "ConfirmPage.tsx"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_coordinator_actions_are_project_role_scoped():
    source = _page()
    assert "const canCoordinatorAct" in source
    assert "selectedProjectRoles.includes('coordinator')" in source
    assert "currentUser?.is_ceo" not in source[source.index("const canCoordinatorAct"):source.index("const canCoachAct")]


def test_coordinator_queue_loads_card_level_records():
    source = _page()
    assert "getPending(coordProjectId, 'coordinator', { includeCardLevel: true })" in source
    assert "pending_coordinator_card_indices" in source


def test_inline_coordinator_panel_accepts_feedback_for_selected_card():
    source = _page()
    assert "{viewMode === 'coordinator'" in source
    assert "value={coordinatorCardNote}" in source
    assert "onClick={handleCoordinatorCardFeedback}" in source
    assert "coordinatorFeedbackTaskCard(" in source


def test_coordinator_reload_selects_the_next_pending_card_or_clears_selection():
    source = _page()
    start = source.index("function reloadCoordinatorItems")
    body = source[start:source.index("function reloadCoachItems", start)]
    assert "setSelectedCardIndex(indices[0])" in body
    assert "setSelected(null)" in body
    assert "setSelectedCardIndex(0)" in body


def test_owner_actions_remain_locked_while_card_waits_for_coordinator():
    source = _page()
    assert "const cardWaitingCoordinator" in source
    assert "disabled={acting || projectArchived || cardWaitingCoordinator}" in source
    assert "!cardWaitingCoordinator && activeCard.confirmationStatus !== 'coordinator_given'" in source

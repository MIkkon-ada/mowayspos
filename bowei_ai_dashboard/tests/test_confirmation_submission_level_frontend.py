"""Submission-level action contract for the inline confirmation workspace."""

from pathlib import Path

PAGE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "ConfirmPage.tsx"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_owner_actions_are_scoped_to_owner_review_queue():
    source = _page()
    assert "{viewMode === 'all' && canUseOwnerActions" in source
    assert "submissionActionsLocked" in source
    assert "projectArchived" in source


def test_submission_and_card_actions_use_the_current_handlers():
    source = _page()
    assert "handleTaskCardDecision" in source
    assert "handleConfirm" in source
    assert "handleDecision" in source
    assert "setPendingAction('return')" in source
    assert "setPendingAction('transfer')" in source
    assert "setPendingAction('ceo')" in source


def test_submission_actions_respect_pending_card_locks_and_status_sets():
    source = _page()
    assert "hasPendingSubmissionCards" in source
    assert "SS.TRANSFERABLE_TO_COORDINATOR" in source
    assert "SS.ESCALATABLE_TO_CEO" in source


def test_confirmation_center_does_not_restore_submitter_history_view():
    source = _page()
    assert "viewMode === 'mine'" not in source
    assert "fetchMyUpdates" not in source


def test_write_feedback_is_shared_by_all_review_panels():
    source = _page()
    assert "actionSuccess" in source
    assert "actionError" in source
    assert "activeCard.coordinatorNote" in source
    assert "activeCard.ceoNote" in source

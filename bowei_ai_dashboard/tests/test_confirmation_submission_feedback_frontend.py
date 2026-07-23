"""Submission-level persistent feedback and owner decision-note display tests."""

from __future__ import annotations

from pathlib import Path


PAGE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "src"
    / "pages"
    / "ConfirmPage.tsx"
)


def _page() -> str:
    return PAGE_PATH.read_text(encoding="utf-8")


def _between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.find(start_marker)
    end = source.find(end_marker, start + len(start_marker))
    assert start >= 0, f"missing start marker: {start_marker}"
    assert end > start, f"missing end marker: {end_marker}"
    return source[start:end]


def _extract_function(source: str, name: str) -> str:
    start = source.find(f"function {name}(")
    assert start >= 0, f"missing function: {name}"
    brace = source.index("{", source.index(")", start))
    depth = 1
    cursor = brace + 1
    while depth and cursor < len(source):
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    assert depth == 0
    return source[start:cursor]


def _main_panel(source: str) -> str:
    return _between(
        source,
        "{/* Right: detail panel */}",
        "{cardDetailOpen && activeCard && activeReviewCard",
    )


class TestPersistentPageFeedback:
    def test_feedback_is_mounted_before_selected_condition(self):
        panel = _main_panel(_page())
        feedback = panel.find("{/* Page-level action feedback */}")
        selected = panel.find("{selected ? (")

        assert feedback >= 0
        assert selected > feedback

    def test_main_panel_renders_each_feedback_state_once(self):
        panel = _main_panel(_page())

        assert panel.count("{actionError &&") == 1
        assert panel.count("{actionSuccess &&") == 1

    def test_feedback_and_selected_null_empty_state_share_panel(self):
        panel = _main_panel(_page())
        feedback = panel.find("{/* Page-level action feedback */}")
        selected = panel.find("{selected ? (")
        empty = panel.find("← 点击左侧列表查看详情")

        assert 0 <= feedback < selected < empty
        assert "actionError" in panel[feedback:selected]
        assert "actionSuccess" in panel[feedback:selected]

    def test_coordinator_success_and_refresh_failure_messages_remain(self):
        handler = _extract_function(_page(), "handleCoordinatorFeedback")

        assert "await reloadCoordinatorItems()" in handler
        assert "统筹意见已提交，事项已返回项目负责人。" in handler
        assert "统筹意见已提交，但待办列表刷新失败，请手动刷新页面。" in handler

    def test_reload_removes_completed_item_instead_of_reinserting_it(self):
        reload_body = _extract_function(_page(), "reloadCoordinatorItems")

        assert "setItems(d)" in reload_body
        assert "d.find((item) => item.id === selected.id)" in reload_body
        assert "setSelected(null)" in reload_body
        assert "setCardDetailOpen(false)" in reload_body
        assert "setItems((prev)" not in reload_body

    def test_card_modal_local_feedback_remains(self):
        page = _page()
        modal = _between(
            page,
            "{cardDetailOpen && activeCard && activeReviewCard",
            "{/* Operation log — collapsible */}",
        )

        assert "{actionError &&" in modal
        assert "{actionSuccess &&" in modal


class TestOwnerCoordinatorFeedbackDisplay:
    def test_uses_coordinator_note_in_read_only_all_view_block(self):
        block = _between(
            _page(),
            "{/* Submission coordinator feedback display */}",
            "{/* Submission coach decision display */}",
        )

        assert "viewMode === 'all'" in block
        assert "selected.coordinator_note?.trim()" in block
        assert "{selected.coordinator_note}" in block
        assert "统筹反馈意见" in block
        assert "textarea" not in block
        assert "selected.reject_reason" not in block

    def test_coordinator_note_is_not_hidden_by_submission_status(self):
        block = _between(
            _page(),
            "{/* Submission coordinator feedback display */}",
            "{/* Submission coach decision display */}",
        )

        for status_guard in ("selectedStatus", "isConfirmed", "SS."):
            assert status_guard not in block


class TestOwnerCoachDecisionDisplay:
    def test_uses_ceo_note_in_read_only_all_view_block(self):
        block = _between(
            _page(),
            "{/* Submission coach decision display */}",
            "{/* Submission-level owner actions */}",
        )

        assert "viewMode === 'all'" in block
        assert "selected.ceo_note?.trim()" in block
        assert "{selected.ceo_note}" in block
        assert "企业教练批示" in block
        assert "textarea" not in block
        assert "selected.reject_reason" not in block

    def test_ceo_note_is_not_hidden_by_submission_status(self):
        block = _between(
            _page(),
            "{/* Submission coach decision display */}",
            "{/* Submission-level owner actions */}",
        )

        for status_guard in ("selectedStatus", "isConfirmed", "SS."):
            assert status_guard not in block


class TestDisplayOrderAndPermissionBoundaries:
    def test_submission_context_order_precedes_owner_actions(self):
        page = _page()
        markers = [
            "{/* Page-level action feedback */}",
            "提交人补充说明",
            "{/* Submission coordinator feedback display */}",
            "{/* Submission coach decision display */}",
            "{/* Submission-level owner actions */}",
            "{/* Task card overview */}",
        ]
        positions = [page.find(marker) for marker in markers]

        assert all(position >= 0 for position in positions)
        assert positions == sorted(positions)

    def test_owner_actions_stay_all_view_and_owner_only(self):
        owner = _between(
            _page(),
            "{/* Submission-level owner actions */}",
            "{/* Task card overview */}",
        )

        assert "viewMode === 'all'" in owner
        assert "canUseOwnerActions" in owner
        assert "SS.OWNER_ACTIONABLE.has(selectedStatus)" in owner
        assert "viewMode === 'coordinator'" not in owner
        assert "viewMode === 'ceo'" not in owner
        assert "viewMode === 'mine'" not in owner

    def test_decided_submission_keeps_transfer_buttons_status_limited(self):
        owner = _between(
            _page(),
            "{/* Submission-level owner actions */}",
            "{/* Task card overview */}",
        )

        assert "SS.TRANSFERABLE_TO_COORDINATOR.has(selectedStatus)" in owner
        assert "SS.ESCALATABLE_TO_CEO.has(selectedStatus)" in owner
        assert "整条确认入库" in owner
        assert "整条退回提交人" in owner

    def test_submission_and_card_buttons_remain(self):
        page = _page()
        for label in (
            "整条确认入库",
            "整条退回提交人",
            "整条转交统筹人",
            "整条转交企业教练",
            "单卡统筹反馈",
            "提交企业教练批示",
        ):
            assert label in page

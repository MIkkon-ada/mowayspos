"""N4-P3-FIX-1B: 单卡统筹前端结构与分支测试。"""
from __future__ import annotations

from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read(path: str) -> str:
    return (FRONTEND_DIR / path).read_text(encoding="utf-8")


def _extract_function(source: str, name: str) -> str:
    start = source.find(f"function {name}")
    if start < 0:
        return ""
    brace = source.index("{", source.index("(", start))
    depth = 1
    cursor = brace + 1
    while depth and cursor < len(source):
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    return source[start:cursor]


def _type_region(source: str, name: str, following: str) -> str:
    start = source.find(f"export type {name}")
    end = source.find(f"export type {following}", start + 1)
    assert start >= 0 and end > start
    return source[start:end]


def _card_modal_regions(source: str) -> tuple[str, str]:
    modal = source.find("cardDetailOpen && activeCard && activeReviewCard")
    coordinator = source.find("viewMode === 'coordinator'", modal)
    owner = source.find("viewMode === 'all'", coordinator)
    assert modal >= 0 and coordinator > modal and owner > coordinator
    return source[coordinator:owner], source[owner:]


class TestCoordinatorCardApiAndTypes:
    def test_api_posts_to_card_feedback_route(self):
        source = _read("api/confirmations.ts")
        body = _extract_function(source, "coordinatorFeedbackTaskCard")
        assert body
        assert "cardIndex: number" in body
        assert "`/api/confirmations/${id}/cards/${cardIndex}/coordinator-feedback`" in body
        assert "{ note, operator }" in body

    def test_confirmation_item_has_coordinator_scope_fields(self):
        source = _read("types.ts")
        region = source[source.index("export type ConfirmationItem"):]
        assert "coordinator_decision_scope?: 'submission' | 'card'" in region
        assert "pending_coordinator_card_indices?: number[]" in region

    def test_task_card_type_has_request_and_feedback_fields(self):
        source = _read("domain/confirmationTaskCards.ts")
        region = _type_region(source, "ConfirmationTaskCard", "ReviewCardViewModel")
        for field in (
            "coordinatorRequestNote: string",
            "coordinatorRequestOperator: string",
            "coordinatorRequestedAt: string",
            "coordinatorNote: string",
            "coordinatorOperator: string",
            "coordinatorFeedbackAt: string",
        ):
            assert field in region

    def test_task_report_mapping_reads_all_coordinator_fields(self):
        source = _read("domain/confirmationTaskCards.ts")
        start = source.index("export function buildConfirmationTaskCards")
        body = source[start:]
        assert body
        for mapping in (
            "coordinatorRequestNote: text(report.coordinator_request_note)",
            "coordinatorRequestOperator: text(report.coordinator_request_operator)",
            "coordinatorRequestedAt: text(report.coordinator_requested_at)",
            "coordinatorNote: text(report.coordinator_note)",
            "coordinatorOperator: text(report.coordinator_operator)",
            "coordinatorFeedbackAt: text(report.coordinator_feedback_at)",
        ):
            assert mapping in body


class TestCoordinatorCardLoadingAndDeepLink:
    def test_coordinator_load_includes_card_level(self):
        source = _read("pages/ConfirmPage.tsx")
        start = source.index("} else if (viewMode === 'coordinator') {")
        branch = source[start:source.index("} else {", start)]
        assert "getPending(coordProjectId, 'coordinator', { includeCardLevel: true })" in branch

    def test_pick_item_uses_url_pending_card_or_first_pending_card(self):
        body = _extract_function(_read("pages/ConfirmPage.tsx"), "pickItem")
        assert "item.pending_coordinator_card_indices ?? []" in body
        assert "pendingIndices.includes(urlCardIndex)" in body
        assert "setSelectedCardIndex(pendingIndices[0])" in body

    def test_deep_link_opens_card_detail(self):
        body = _extract_function(_read("pages/ConfirmPage.tsx"), "pickItem")
        coordinator_branch = body[body.find("isCoordinatorView"):]
        assert "urlCardIndex !== undefined" in coordinator_branch
        assert "let shouldOpenCard = false" in body
        assert "shouldOpenCard = urlCardIndex !== undefined && pendingIndices.length > 0" in coordinator_branch
        assert "setCardDetailOpen(shouldOpenCard)" in coordinator_branch

    def test_coordinator_submission_scope_ignores_stale_card_deep_link(self):
        body = _extract_function(_read("pages/ConfirmPage.tsx"), "pickItem")
        card_scope = body.index("isCoordinatorView && item.coordinator_decision_scope === 'card'")
        submission_scope = body.index("else if (isCoordinatorView)", card_scope)
        generic_card_link = body.index("else if (urlCardIndex !== undefined)", submission_scope)
        assert card_scope < submission_scope < generic_card_link

    def test_reload_keeps_submission_and_selects_next_pending_card(self):
        body = _extract_function(_read("pages/ConfirmPage.tsx"), "reloadCoordinatorItems")
        assert "{ includeCardLevel: true }" in body
        assert "d.find((item) => item.id === selected.id)" in body
        assert "same.pending_coordinator_card_indices ?? []" in body
        assert "setSelectedCardIndex(indices[0])" in body

    def test_reload_closes_modal_when_no_items_remain(self):
        body = _extract_function(_read("pages/ConfirmPage.tsx"), "reloadCoordinatorItems")
        assert "setSelected(null)" in body
        assert "setCardDetailOpen(false)" in body

    def test_post_failures_remain_operation_errors(self):
        source = _read("pages/ConfirmPage.tsx")
        for name, post_call in (
            ("handleCoordinatorFeedback", "await coordinatorFeedback("),
            ("handleCoordinatorCardFeedback", "await coordinatorFeedbackTaskCard("),
        ):
            body = _extract_function(source, name)
            assert post_call in body
            assert "setActionError(`操作失败：${msg}`)" in body
            assert body.index(post_call) < body.rindex("catch (err: unknown)")

    def test_reload_failures_are_success_warnings_in_both_handlers(self):
        source = _read("pages/ConfirmPage.tsx")
        warning = "统筹意见已提交，但待办列表刷新失败，请手动刷新页面。"
        for name in ("handleCoordinatorFeedback", "handleCoordinatorCardFeedback"):
            body = _extract_function(source, name)
            assert body.count("try {") >= 2
            assert body.count("catch") >= 2
            assert "await reloadCoordinatorItems()" in body
            assert f"setActionSuccess('{warning}')" in body
            assert ".catch(() => {})" not in body


class TestCoordinatorScopeRendering:
    def test_submission_feedback_section_is_scope_guarded(self):
        source = _read("pages/ConfirmPage.tsx")
        feedback = source.find("提供统筹意见")
        guard = source.rfind("{isCoordinatorView", 0, feedback)
        assert feedback >= 0 and guard >= 0
        assert "selected.coordinator_decision_scope === 'submission'" in source[guard:feedback]

    def test_list_distinguishes_submission_and_card_scope(self):
        source = _read("pages/ConfirmPage.tsx")
        list_region = source[source.index("visibleItems.map"):source.index("{/* Right: detail panel */}")]
        assert "item.coordinator_decision_scope === 'submission'" in list_region
        assert "item.coordinator_decision_scope === 'card'" in list_region
        assert "pending_coordinator_card_indices" in list_region
        assert "张待统筹" in list_region

    def test_coordinator_card_note_has_independent_state(self):
        page = _read("pages/ConfirmPage.tsx")
        assert "const [coordinatorCardNote, setCoordinatorCardNote] = useState('')" in page

    def test_card_feedback_handler_calls_card_api_and_clears_note(self):
        body = _extract_function(_read("pages/ConfirmPage.tsx"), "handleCoordinatorCardFeedback")
        assert body
        assert "coordinatorFeedbackTaskCard(" in body
        assert "selected.id" in body and "activeCardIndex" in body
        assert "coordinatorCardNote" in body
        assert "setCoordinatorCardNote('')" in body
        assert "reloadCoordinatorItems()" in body

    def test_card_feedback_handler_keeps_lock_until_reload_finishes(self):
        body = _extract_function(_read("pages/ConfirmPage.tsx"), "handleCoordinatorCardFeedback")
        assert "await reloadCoordinatorItems()" in body
        assert body.index("await reloadCoordinatorItems()") < body.index("finally")


class TestCoordinatorCardModal:
    def test_pending_card_shows_request_metadata_and_feedback_form(self):
        coordinator, _ = _card_modal_regions(_read("pages/ConfirmPage.tsx"))
        assert "activeCard.confirmationStatus === 'transferred_to_coordinator'" in coordinator
        assert "负责人转交说明" in coordinator
        assert "activeCard.coordinatorRequestNote" in coordinator
        assert "转交人" in coordinator and "转交时间" in coordinator
        assert "value={coordinatorCardNote}" in coordinator
        assert "onClick={handleCoordinatorCardFeedback}" in coordinator

    def test_feedback_card_is_read_only(self):
        coordinator, _ = _card_modal_regions(_read("pages/ConfirmPage.tsx"))
        assert "activeCard.confirmationStatus === 'coordinator_given'" in coordinator
        assert "统筹人已反馈" in coordinator
        assert "activeCard.coordinatorNote" in coordinator
        assert "反馈人" in coordinator and "反馈时间" in coordinator
        read_only = coordinator[coordinator.index("coordinator_given"):]
        assert "handleCoordinatorCardFeedback" not in read_only

    def test_other_cards_show_no_feedback_required(self):
        coordinator, _ = _card_modal_regions(_read("pages/ConfirmPage.tsx"))
        assert "该任务卡不需要统筹反馈。" in coordinator
        for owner_action in ("确认入库", "退回并重新编辑", "转交统筹人", "转交企业教练"):
            assert owner_action not in coordinator

    def test_card_switch_and_modal_close_are_locked(self):
        source = _read("pages/ConfirmPage.tsx")
        card_list = source[source.index("taskCards.map"):source.index("</section>", source.index("taskCards.map"))]
        assert "if (coordinatorInteractionLocked) return" in card_list
        assert "disabled={coordinatorInteractionLocked}" in card_list
        close = source[source.index("onClick={() => setCardDetailOpen(false)}") - 120:source.index("onClick={() => setCardDetailOpen(false)}") + 300]
        assert "disabled={coordinatorInteractionLocked}" in close

    def test_card_feedback_controls_are_locked(self):
        coordinator, _ = _card_modal_regions(_read("pages/ConfirmPage.tsx"))
        textarea = coordinator[coordinator.index("value={coordinatorCardNote}"):]
        assert "disabled={coordinatorActing}" in textarea[:500]
        button = coordinator[coordinator.index("onClick={handleCoordinatorCardFeedback}"):]
        assert "coordinatorActing || !coordinatorCardNote.trim()" in button[:500]


class TestOwnerCoordinatorFeedback:
    def test_waiting_coordinator_disables_every_owner_card_action(self):
        source = _read("pages/ConfirmPage.tsx")
        assert "const cardWaitingCoordinator =\n    activeCard?.confirmationStatus === 'transferred_to_coordinator'" in source
        _, owner = _card_modal_regions(source)
        action_region = owner[:owner.find("该视图下仅查看记录")]
        assert "该任务卡正在等待项目统筹人反馈，反馈完成后可继续处理。" in action_region
        for action in ("confirm", "return", "ceo"):
            marker = f"handleTaskCardDecision('{action}')"
            button = action_region[action_region.index(marker):]
            assert "cardWaitingCoordinator" in button[:500]
        transfer = action_region[action_region.index("handleTaskCardDecision('transfer')") - 250:]
        assert "!cardWaitingCoordinator" in transfer[:500]

    def test_owner_sees_read_only_feedback_before_actions(self):
        _, owner = _card_modal_regions(_read("pages/ConfirmPage.tsx"))
        owner_region = owner[:owner.index("</div>", owner.index("grid grid-cols-1 sm:grid-cols-2")) + 6]
        feedback = owner_region.find("activeCard.confirmationStatus === 'coordinator_given'")
        actions = owner_region.find("handleTaskCardDecision('confirm')")
        assert 0 <= feedback < actions
        assert "统筹反馈内容" in owner_region
        assert "activeCard.coordinatorNote" in owner_region
        assert "反馈人" in owner_region and "反馈时间" in owner_region

    def test_owner_can_confirm_reject_or_escalate_after_feedback_but_not_retransfer(self):
        _, owner = _card_modal_regions(_read("pages/ConfirmPage.tsx"))
        action_region = owner[:owner.find("该视图下仅查看记录")]
        assert "handleTaskCardDecision('confirm')" in action_region
        assert "handleTaskCardDecision('return')" in action_region
        assert "handleTaskCardDecision('ceo')" in action_region
        transfer = action_region.find("handleTaskCardDecision('transfer')")
        assert transfer >= 0
        guard = action_region.rfind("activeCard.confirmationStatus !== 'coordinator_given'", 0, transfer)
        assert guard >= 0
        for action in ("confirm", "return", "ceo"):
            marker = f"handleTaskCardDecision('{action}')"
            button = action_region[action_region.index(marker):]
            assert "cardWaitingCoordinator" in button[:500]


class TestCoordinatorCardStatusLabels:
    def test_status_label_and_tone_cover_feedback_state(self):
        source = _read("pages/ConfirmPage.tsx")
        label = _extract_function(source, "taskCardDecisionLabel")
        tone = _extract_function(source, "taskCardDecisionTone")
        assert "coordinator_given" in label and "统筹已反馈" in label
        assert "coordinator_given" in tone

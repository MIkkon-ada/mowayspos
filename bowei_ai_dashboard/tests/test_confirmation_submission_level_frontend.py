"""N4-P3-R3-FIX-2B: submission-level confirmation UI and deep-link tests."""

from __future__ import annotations

from pathlib import Path

from app import models, schemas
from app.domain import submission_status as SS
from app.routers.confirmations import confirm, reject, reject_final, resubmit
from tests.test_execution_submission_to_work_progress_flow import _make_session
from tests.test_submission_submitter_identity_flow import _seed_team, _submission


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read(path: str) -> str:
    return (FRONTEND_DIR / path).read_text(encoding="utf-8")


def _extract_function(source: str, name: str) -> str:
    start = source.find(f"function {name}(")
    if start < 0:
        start = source.find(f"def {name}(")
        if start >= 0:
            end = source.find("\n@router.", start)
            return source[start:end if end >= 0 else len(source)]
    if start < 0:
        return ""
    brace = source.index("{\n", source.index(")", start))
    depth = 1
    cursor = brace + 1
    while depth and cursor < len(source):
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    return source[start:cursor]


def _between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.find(start_marker)
    end = source.find(end_marker, start + len(start_marker))
    assert start >= 0 and end > start
    return source[start:end]


class TestSubmissionActionArea:
    @classmethod
    def setup_class(cls):
        cls.page = _read("pages/ConfirmPage.tsx")

    def test_submission_action_area_exists(self):
        assert "整条提交操作" in self.page

    def test_four_explicit_submission_button_labels_exist(self):
        for label in (
            "整条确认入库",
            "整条退回提交人",
            "整条转交统筹人",
            "整条转交企业教练",
        ):
            assert label in self.page

    def test_action_area_is_guarded_by_all_view_and_owner_capability(self):
        region = _between(
            self.page,
            "{/* Submission-level owner actions */}",
            "{/* Member resubmit section */}",
        )
        assert "viewMode === 'all'" in region
        assert "canUseOwnerActions" in region
        assert "SS.OWNER_ACTIONABLE.has(selectedStatus)" in region

    def test_action_area_uses_submission_handlers(self):
        region = _between(
            self.page,
            "{/* Submission-level owner actions */}",
            "{/* Member resubmit section */}",
        )
        assert "handleConfirm" in region
        assert "setPendingAction('return')" in region
        assert "setPendingAction('transfer')" in region
        assert "setPendingAction('ceo')" in region
        assert "handleDecision(pendingAction)" in region

    def test_transfer_and_ceo_handlers_use_submission_apis(self):
        body = _extract_function(self.page, "handleDecision")
        assert "transferCoordinator(selected.id" in body
        assert "escalateCeo(selected.id" in body
        assert "transferTaskCardCoordinator" not in body
        assert "escalateTaskCardCeo" not in body

    def test_submission_actions_are_disabled_for_archived_project(self):
        region = _between(
            self.page,
            "{/* Submission-level owner actions */}",
            "{/* Member resubmit section */}",
        )
        assert "submissionActionsLocked" in region
        assert "projectArchived" in self.page[
            self.page.find("const submissionActionsLocked") :
            self.page.find("const submissionActionsLocked") + 220
        ]

    def test_pending_coordinator_card_locks_all_submission_actions(self):
        assert "card.confirmationStatus === 'transferred_to_coordinator'" in self.page
        assert "hasPendingSubmissionCards" in self.page

    def test_pending_coach_card_locks_all_submission_actions(self):
        assert "card.confirmationStatus === ('pending_ceo_' + 'decision')" in self.page
        assert "本次提交仍有任务卡等待统筹反馈或企业教练批示" in self.page

    def test_transfer_state_uses_transferable_set(self):
        region = _between(
            self.page,
            "{/* Submission-level owner actions */}",
            "{/* Member resubmit section */}",
        )
        assert "SS.TRANSFERABLE_TO_COORDINATOR.has(selectedStatus)" in region

    def test_ceo_state_uses_escalatable_set(self):
        region = _between(
            self.page,
            "{/* Submission-level owner actions */}",
            "{/* Member resubmit section */}",
        )
        assert "SS.ESCALATABLE_TO_CEO.has(selectedStatus)" in region

    def test_action_note_is_required_and_duplicate_clicks_are_disabled(self):
        region = _between(
            self.page,
            "{/* Submission-level owner actions */}",
            "{/* Member resubmit section */}",
        )
        assert "!actionNote.trim()" in region
        assert "acting" in region
        body = _extract_function(self.page, "handleDecision")
        assert "if (!note) return" in body

    def test_action_target_names_all_task_cards(self):
        assert "本次提交全部任务卡，共 {taskCards.length} 张" in self.page

    def test_submission_and_card_regions_are_separate(self):
        submission = self.page.find("整条提交操作")
        overview = self.page.find("任务卡牌总览")
        modal = self.page.find("cardDetailOpen && activeCard && activeReviewCard")
        single_card = self.page.find("单卡判断", modal)
        assert 0 <= submission < overview < modal < single_card

    def test_single_card_buttons_remain_unchanged(self):
        modal = self.page[self.page.find("cardDetailOpen && activeCard && activeReviewCard") :]
        for label in ("确认入库", "退回并重新编辑", "转交统筹人", "转交企业教练"):
            assert label in modal


class TestSubmissionStatusGroups:
    @classmethod
    def setup_class(cls):
        cls.status = _read("domain/submissionStatus.ts")
        cls.page = _read("pages/ConfirmPage.tsx")

    def test_owner_actionable_has_all_backend_states(self):
        block = _between(self.status, "export const OWNER_ACTIONABLE", "export const TRANSFERABLE_TO_COORDINATOR")
        for value in ("S_NEW", "S_PENDING_OWNER", "S_COORDINATOR_GIVEN", "S_CEO_DECIDED"):
            assert value in block

    def test_pending_owner_review_matches_owner_actionable_states(self):
        block = _between(self.status, "export const PENDING_OWNER_REVIEW", "export const OWNER_ACTIONABLE")
        for value in ("S_NEW", "S_PENDING_OWNER", "S_COORDINATOR_GIVEN", "S_CEO_DECIDED"):
            assert value in block

    def test_transferable_does_not_include_coordinator_given(self):
        block = _between(self.status, "export const TRANSFERABLE_TO_COORDINATOR", "export const ESCALATABLE_TO_CEO")
        assert "S_NEW" in block and "S_PENDING_OWNER" in block
        assert "S_COORDINATOR_GIVEN" not in block

    def test_escalatable_does_not_include_ceo_decided(self):
        block = _between(self.status, "export const ESCALATABLE_TO_CEO", "export const ALL_TERMINAL")
        assert "S_COORDINATOR_GIVEN" in block
        assert "S_CEO_DECIDED" not in block

    def test_pending_count_uses_owner_actionable(self):
        line_start = self.page.find("const pendingCount")
        assert "SS.OWNER_ACTIONABLE.has(SS.normalize(i.confirm_status))" in self.page[line_start:line_start + 220]

    def test_semantic_owner_actionable_filter_is_implemented(self):
        region = self.page[self.page.find("const visibleItems"):self.page.find("const opLogs")]
        assert "filterStatus === 'owner_actionable'" in region
        assert "SS.OWNER_ACTIONABLE.has(SS.normalize(item.confirm_status))" in region


class TestMineViewAndResubmit:
    @classmethod
    def setup_class(cls):
        cls.page = _read("pages/ConfirmPage.tsx")
        cls.api = _read("api/confirmations.ts")

    def test_page_imports_resubmit_api(self):
        imports = self.page[: self.page.find("export function ConfirmPage")]
        assert "resubmitSubmission" in imports

    def test_api_posts_resubmit_payload(self):
        body = _extract_function(self.api, "resubmitSubmission")
        assert "`/api/confirmations/${id}/resubmit`" in body
        assert "supplement_note: supplementNote" in body
        assert "operator" in body and "human_result: humanResult" in body
        assert "Promise<{ ok?: boolean; submission?: ConfirmationItem }>" in body

    def test_mine_view_defaults_to_all_statuses(self):
        effect = self.page[self.page.find("// 统一 effect"):self.page.find("function switchView")]
        switch = _extract_function(self.page, "switchView")
        assert "viewMode === 'all'" in effect
        assert "setFilterStatus('owner_actionable')" in effect
        assert "setFilterStatus('')" in effect
        assert "nextView === 'all'" in switch
        assert "setFilterStatus('owner_actionable')" in switch
        assert "setFilterStatus('')" in switch

    def test_mine_loading_uses_url_submission_id(self):
        branch = self.page[
            self.page.find("if (viewMode === 'mine')"):
            self.page.find("} else if (viewMode === 'ceo')")
        ]
        assert "urlSubmissionId" in branch
        assert "mapped.find(i => i.id === urlSubmissionId)" in branch
        assert "pickItem(target)" in branch
        assert "该提交不存在或不属于当前账号" in branch

    def test_mine_submitter_view_does_not_compare_names(self):
        assert "const isSubmitterView = viewMode === 'mine'" in self.page
        assert "selected?.submitter === currentUser?.name" not in self.page

    def test_returned_section_shows_reason_and_original_context(self):
        region = _between(
            self.page,
            "{/* Member resubmit section */}",
            "{/* Task card overview */}",
        )
        assert "负责人已退回，请补充后重新提交" in region
        assert "selected.reject_reason" in region
        assert "fmtTime(selected.created_at)" in region
        assert "原提交内容摘要" in region

    def test_resubmit_note_is_required(self):
        region = _between(
            self.page,
            "{/* Member resubmit section */}",
            "{/* Task card overview */}",
        )
        assert "补充说明" in region
        assert "!supplementNote.trim()" in region

    def test_resubmit_handler_updates_returned_submission(self):
        body = _extract_function(self.page, "handleResubmit")
        assert "resubmitSubmission(selected.id" in body
        assert "currentUser.name" in body
        assert "SS.S_PENDING_OWNER" in body
        assert "reject_reason: ''" in body
        assert "setItems" in body and "setSelected(updated)" in body
        assert "setSupplementNote('')" in body
        assert "已重新提交，等待项目负责人审核" in body

    def test_resubmit_failure_preserves_note(self):
        body = _extract_function(self.page, "handleResubmit")
        catch_region = body[body.find("catch (err: unknown)"):]
        assert "setSupplementNote('')" not in catch_region

    def test_switching_submission_clears_unsent_supplement(self):
        body = _extract_function(self.page, "pickItem")
        assert "setSupplementNote('')" in body

    def test_supplement_note_is_visible_in_mine_and_all(self):
        assert "提交人补充说明" in self.page
        assert "(viewMode === 'mine' || viewMode === 'all')" in self.page
        assert "selectedResult?.supplement_note" in self.page

    def test_status_filter_has_required_labels(self):
        for label in ("全部状态", "待负责人处理", "已退回", "已转交统筹", "待企业教练决策", "已入库"):
            assert label in self.page


class TestOwnerActionPermissions:
    @classmethod
    def setup_class(cls):
        cls.page = _read("pages/ConfirmPage.tsx")

    def test_owner_actions_use_selected_project_owner_role(self):
        start = self.page.find("const canUseOwnerActions")
        block = self.page[start:start + 420]
        assert start >= 0
        assert "selectedProject" in block
        assert "includes('owner')" in block
        assert "is_tech_admin" in block

    def test_owner_actions_do_not_grant_coordinator_or_coach_roles(self):
        start = self.page.find("const canUseOwnerActions")
        block = self.page[start:start + 420]
        assert "includes('coordinator')" not in block
        assert "includes('project_ceo')" not in block
        assert "is_ceo" not in block

    def test_existing_coordinator_feedback_stays_in_coordinator_view(self):
        start = self.page.find("提供统筹意见")
        guard = self.page[max(0, start - 1000):start]
        assert "isCoordinatorView" in guard

    def test_existing_coach_decision_stays_in_coach_view(self):
        start = self.page.find('<span className="text-sm font-bold text-violet-800">企业教练批示</span>')
        guard = self.page[max(0, start - 1000):start]
        assert "isCoachView" in guard


def _notification_links(db, ntype: str) -> list[str]:
    return [row.link for row in db.query(models.Notification).filter_by(type=ntype).all()]


class TestSubmissionNotificationDeepLinks:
    def test_rejected_notification_targets_exact_mine_submission(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(db, submitter=team["submitter"].name, submitter_id=team["submitter"].id)

        reject(row.id, schemas.RejectRequest(reason="补充", operator="owner"), current_user="owner", db=db)

        assert _notification_links(db, "submission_rejected") == [
            f"/work/confirmations?view=mine&projectId=1&submissionId={row.id}"
        ]

    def test_confirmed_notification_targets_exact_mine_submission(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(db, submitter=team["submitter"].name, submitter_id=team["submitter"].id)

        confirm(row.id, schemas.ConfirmRequest(operator="owner"), current_user="owner", db=db)

        assert _notification_links(db, "submission_confirmed") == [
            f"/work/confirmations?view=mine&projectId=1&submissionId={row.id}"
        ]

    def test_reject_final_notification_targets_exact_mine_submission(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(db, submitter=team["submitter"].name, submitter_id=team["submitter"].id)

        reject_final(row.id, schemas.RejectRequest(reason="不入库", operator="owner"), current_user="owner", db=db)

        assert _notification_links(db, "submission_rejected") == [
            f"/work/confirmations?view=mine&projectId=1&submissionId={row.id}"
        ]

    def test_resubmitted_notification_targets_exact_all_submission(self):
        db = _make_session()
        team = _seed_team(db)
        row = _submission(
            db,
            submitter=team["submitter"].name,
            submitter_id=team["submitter"].id,
            status=SS.S_RETURNED,
        )

        resubmit(
            row.id,
            schemas.ResubmitRequest(supplement_note="已补充"),
            current_user="submitter_account",
            db=db,
        )

        links = _notification_links(db, "submission_resubmitted")
        assert links
        assert set(links) == {
            f"/work/confirmations?view=all&projectId=1&submissionId={row.id}"
        }

    def test_four_submission_notification_functions_do_not_write_old_links(self):
        source = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "routers"
            / "confirmations.py"
        ).read_text(encoding="utf-8")
        for name in ("confirm", "reject", "resubmit", "reject_final"):
            body = _extract_function(source, name)
            assert "/project/{project_id}/confirm" not in body
            assert "submissionId={row.id}" in body

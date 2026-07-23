"""AI confirmation center stays reviewer-only after submitter history migration."""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIRM_PAGE = PROJECT_ROOT / "frontend" / "src" / "pages" / "ConfirmPage.tsx"
UPDATES_API = PROJECT_ROOT / "frontend" / "src" / "api" / "updates.ts"


@pytest.fixture(scope="module")
def confirm_source() -> str:
    return CONFIRM_PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def updates_api_source() -> str:
    return UPDATES_API.read_text(encoding="utf-8")


def test_title_is_ai_confirm_center(confirm_source: str):
    assert "AI 确认中心" in confirm_source


def test_no_ai_audit_center(confirm_source: str):
    assert "AI 审核中心" not in confirm_source


def test_reviewer_default_to_pending_view(confirm_source: str):
    assert "const defaultViewMode: ConfirmViewMode = 'all'" in confirm_source


def test_confirm_view_mode_has_only_review_queues(confirm_source: str):
    assert "type ConfirmViewMode = 'all' | 'coordinator' | 'ceo'" in confirm_source


def test_submitter_history_tab_removed(confirm_source: str):
    assert "我的提交记录" not in confirm_source


def test_mine_view_removed(confirm_source: str):
    assert "viewMode === 'mine'" not in confirm_source
    assert "switchView('mine')" not in confirm_source


def test_reviewer_has_all_three_queues(confirm_source: str):
    for label in ("待确认", "待统筹", "待决策"):
        assert label in confirm_source


def test_initial_redirect_uses_ref(confirm_source: str):
    assert "initialRedirectDone" in confirm_source


def test_all_project_filter_kept(confirm_source: str):
    assert "全部项目" in confirm_source


def test_no_all_special_project(confirm_source: str):
    assert "全部专项" not in confirm_source


def test_submitter_filter_is_reviewer_filter(confirm_source: str):
    assert "filterSubmitter" in confirm_source
    assert "全部提交人" in confirm_source


def test_list_titles_are_review_queues(confirm_source: str):
    for label in ("待确认事项", "待我统筹", "待我决策"):
        assert label in confirm_source


def test_pending_empty_state_kept(confirm_source: str):
    assert "暂无待确认事项" in confirm_source


def test_submitter_history_empty_state_removed(confirm_source: str):
    assert "暂无提交记录" not in confirm_source


def test_fetch_my_updates_not_imported_by_confirm_center(confirm_source: str):
    assert "fetchMyUpdates" not in confirm_source


def test_fetch_my_updates_remains_for_work_report_history(updates_api_source: str):
    assert "fetchMyUpdates" in updates_api_source


def test_get_pending_still_exists(confirm_source: str):
    assert "getPending" in confirm_source


def test_confirm_submission_call_unchanged(confirm_source: str):
    assert "confirmSubmission" in confirm_source


def test_subtitle_truncate_class(confirm_source: str):
    assert "truncate" in confirm_source


def test_owner_actions_stay_in_all_view(confirm_source: str):
    assert "viewMode === 'all'" in confirm_source
    assert "canUseOwnerActions" in confirm_source


def test_submitter_readonly_hint_removed(confirm_source: str):
    assert "如需处理请切换到" not in confirm_source

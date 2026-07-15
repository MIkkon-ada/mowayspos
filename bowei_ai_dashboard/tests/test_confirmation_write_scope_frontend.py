"""Whole-submission confirmation write-scope controls source-contract tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PAGE_PATH = REPO_ROOT / "frontend" / "src" / "pages" / "ConfirmPage.tsx"
API_PATH = REPO_ROOT / "frontend" / "src" / "api" / "confirmations.ts"
BASELINE = "e8336ac8c26dee4cb1f42661eac43d2c07f27150"


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
    assert depth == 0, f"unbalanced function: {name}"
    return source[start:cursor]


def _owner_actions(source: str) -> str:
    return _between(
        source,
        "{/* Submission-level owner actions */}",
        "{/* Member resubmit section */}",
    )


def _write_scope(source: str) -> str:
    owner = _owner_actions(source)
    start = owner.find('<div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4">')
    end = owner.find('<div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">', start)
    assert start >= 0, "missing write-scope container"
    assert end > start, "missing submission action-button grid"
    return owner[start:end]


class TestWriteScopeDefaultsAndReset:
    def test_whole_submission_defaults_match_card_true_true_semantics(self):
        page = _page()

        assert "const [writeToAchievements, setWriteToAchievements] = useState(true)" in page
        assert "const [writeToIssues, setWriteToIssues] = useState(true)" in page
        assert "const [writeToAchievements, setWriteToAchievements] = useState(false)" not in page

    def test_pick_item_resets_both_independent_choices(self):
        body = _extract_function(_page(), "pickItem")

        assert "setWriteToAchievements(true)" in body
        assert "setWriteToIssues(true)" in body

    def test_switch_view_resets_both_independent_choices(self):
        body = _extract_function(_page(), "switchView")

        assert "setWriteToAchievements(true)" in body
        assert "setWriteToIssues(true)" in body

    def test_reset_is_not_attached_to_a_broad_selected_effect(self):
        page = _page()

        assert page.count("setWriteToAchievements(true)") == 2
        assert page.count("setWriteToIssues(true)") == 2
        effect_regions = page.split("useEffect(")[1:]
        assert all("setWriteToAchievements(true)" not in region.split("}, [", 1)[0] for region in effect_regions)
        assert all("setWriteToIssues(true)" not in region.split("}, [", 1)[0] for region in effect_regions)


class TestRenderedWriteScopeControls:
    def test_scope_is_inside_existing_owner_action_guard_only(self):
        owner = _owner_actions(_page())

        assert owner.count("本次入库范围") == 1
        assert "viewMode === 'all'" in owner
        assert "canUseOwnerActions" in owner
        assert "selected" in owner
        assert "SS.OWNER_ACTIONABLE.has(selectedStatus)" in owner
        assert "viewMode === 'mine'" not in owner
        assert "viewMode === 'coordinator'" not in owner
        assert "viewMode === 'ceo'" not in owner

    def test_scope_explains_fixed_progress_and_optional_asset_destinations(self):
        scope = _write_scope(_page())

        assert "工作推进表" in scope
        assert "必写" in scope or "始终写入" in scope
        assert "成果库" in scope
        assert "问题中心" in scope
        assert "关闭某项后" in scope
        assert "仍会写入工作推进表" in scope

    def test_exactly_two_real_button_switches_are_rendered(self):
        scope = _write_scope(_page())

        assert scope.count('role="switch"') == 2
        assert scope.count('type="button"') == 2
        assert scope.count("<ToggleSwitch") >= 2
        assert "<label" not in scope

    def test_achievement_switch_has_real_state_binding(self):
        scope = _write_scope(_page())

        assert 'role="switch"' in scope
        assert "aria-checked={writeToAchievements}" in scope
        assert "onClick={() => setWriteToAchievements((value) => !value)}" in scope
        assert "<ToggleSwitch on={writeToAchievements}" in scope

    def test_issue_switch_has_real_state_binding(self):
        scope = _write_scope(_page())

        assert 'role="switch"' in scope
        assert "aria-checked={writeToIssues}" in scope
        assert "onClick={() => setWriteToIssues((value) => !value)}" in scope
        assert "<ToggleSwitch on={writeToIssues}" in scope

    def test_both_switches_use_the_whole_submission_lock(self):
        scope = _write_scope(_page())

        assert scope.count("disabled={submissionActionsLocked}") == 2
        assert scope.count("disabled:opacity-50") >= 2
        assert scope.count("disabled:cursor-not-allowed") >= 2

    def test_lock_covers_acting_archived_and_pending_card_states(self):
        page = _page()
        definition = page[page.find("const submissionActionsLocked"):page.find("const activeCardIndex")]

        assert "acting" in definition
        assert "projectArchived" in definition
        assert "hasPendingSubmissionCards" in definition


class TestWriteScopePayloadAndConfirmedDisplay:
    def test_handle_confirm_preserves_all_four_state_bindings(self):
        body = _extract_function(_page(), "handleConfirm")

        assert "write_task_reports_achievements: writeToAchievements" in body
        assert "write_task_reports_issues: writeToIssues" in body
        assert "write_achievement: writeToAchievements" in body
        assert "write_issue: writeToIssues" in body
        assert "write_task_reports_achievements: false" not in body
        assert "write_task_reports_issues: false" not in body

    def test_api_sends_human_result_without_overriding_scope_flags(self):
        api = API_PATH.read_text(encoding="utf-8")
        body = api[api.find("export function confirmSubmission"):api.find("export function rejectSubmission")]

        assert "{ operator, human_result }" in body
        assert "write_task_reports_achievements" not in body
        assert "write_task_reports_issues" not in body

    def test_confirmed_destination_display_keeps_actual_flag_semantics(self):
        page = _page()
        block = page[page.find("const confirmedWrites"):page.find("const taskReports")]

        assert "confirmedWrites.push('工作推进表')" in block
        assert "write_task_reports_achievements === true" in block
        assert "write_achievement === true" in block
        assert "confirmedWrites.push('成果库')" in block
        assert "write_task_reports_issues === true" in block
        assert "write_issue === true" in block
        assert "confirmedWrites.push('问题中心')" in block


class TestFix2C1ScopeBoundary:
    def test_only_authorized_files_are_changed_from_baseline(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", BASELINE],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        changed = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}

        assert changed <= {
            "frontend/src/pages/ConfirmPage.tsx",
            "bowei_ai_dashboard/tests/test_confirmation_write_scope_frontend.py",
        }

    def test_no_fix_2c2_files_are_changed(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", BASELINE],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        changed = result.stdout.replace("\\", "/")

        for forbidden in (
            "frontend/src/domain/confirmationTaskCards.ts",
            "frontend/src/domain/voiceUpdateFlow.ts",
            "bowei_ai_dashboard/app/routers/confirmations.py",
            "bowei_ai_dashboard/app/services/extractor.py",
        ):
            assert forbidden not in changed

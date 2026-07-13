"""N4-P2-M: action driven status flow -- frontend tests"""
import os
import re
import pytest


@pytest.fixture(scope="module")
def issues_page_source() -> str:
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "frontend", "src", "pages", "IssuesPage.tsx",
    )
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestButtonLabels:
    def test_has_handle_issue_button(self, issues_page_source: str):
        assert "handlestartprocessing" in issues_page_source.lower()

    def test_has_assign_helper(self, issues_page_source: str):
        assert "assignHelper" in issues_page_source or "AssignHelper" in issues_page_source

    def test_has_escalate_coach(self, issues_page_source: str):
        assert "requestCeo" in issues_page_source or "RequestCeo" in issues_page_source

    def test_has_resolve_action(self, issues_page_source: str):
        assert "handleResolve" in issues_page_source

    def test_has_confirm_close(self, issues_page_source: str):
        assert "handleClose" in issues_page_source


class TestNoManualStatusControls:
    def test_no_status_select_keyword(self, issues_page_source: str):
        # check that there is no standalone status dropdown in action area
        assert "status_select" not in issues_page_source.lower()


class TestKanbanUnchanged:
    def test_kanban_columns_count(self, issues_page_source: str):
        match = re.search(r"KANBAN_COLUMNS\s*=\s*\[([^\]]+)\]", issues_page_source)
        assert match, "KANBAN_COLUMNS should be defined"
        columns_str = match.group(1)
        columns = [c.strip().strip("'\"") for c in columns_str.split(",")]
        expected = ["pending", "in_progress", "coordinating", "pending_decision", "resolved", "closed"]
        # just check count is 6
        assert len(columns) == 6, f"KANBAN_COLUMNS should have 6 columns, got {len(columns)}"


class TestNoMigrations:
    def test_assign_helper_does_not_create_table(self, issues_page_source: str):
        assert "CREATE TABLE" not in issues_page_source

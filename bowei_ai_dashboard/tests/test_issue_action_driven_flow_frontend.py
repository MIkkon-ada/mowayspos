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


@pytest.fixture(scope="module")
def issue_detail_source() -> str:
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "frontend", "src", "pages", "IssueDetailPage.tsx",
    )
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestDetailActions:
    def test_detail_page_owns_issue_actions(self, issue_detail_source: str):
        assert "fetchIssueById" in issue_detail_source
        assert "doResolve" in issue_detail_source
        assert "doClose" in issue_detail_source

    def test_has_assign_helper(self, issue_detail_source: str):
        assert "assignIssueHelper" in issue_detail_source
        assert "doAssignHelper" in issue_detail_source

    def test_has_escalate_coach(self, issue_detail_source: str):
        assert "requestIssueCeo" in issue_detail_source
        assert "doRequestCeo" in issue_detail_source

    def test_has_resolve_action(self, issue_detail_source: str):
        assert "resolveIssue" in issue_detail_source

    def test_has_confirm_close(self, issue_detail_source: str):
        assert "closeIssue" in issue_detail_source


class TestNoManualStatusControls:
    def test_no_status_select_keyword(self, issues_page_source: str):
        # check that there is no standalone status dropdown in action area
        assert "status_select" not in issues_page_source.lower()


class TestKanbanUnchanged:
    def test_kanban_columns_count(self, issues_page_source: str):
        match = re.search(r"ISSUE_FLOW\s*=\s*\[([^\]]+)\]", issues_page_source)
        assert match, "ISSUE_FLOW should be defined"
        columns_str = match.group(1)
        assert columns_str.count("key:") == 5


class TestNoMigrations:
    def test_assign_helper_does_not_create_table(self, issues_page_source: str):
        assert "CREATE TABLE" not in issues_page_source

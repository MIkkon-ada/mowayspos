"""N4-P2-M: action driven status flow -- backend tests"""
import re
import pytest


@pytest.fixture(scope="module")
def issues_source() -> str:
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "app", "routers", "issues.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_func(source: str, func_name: str) -> str:
    pattern = re.compile(rf"def {re.escape(func_name)}\b")
    match = pattern.search(source)
    if not match:
        return ""
    start = match.start()
    rest = source[start:]
    lines = rest.split("\n")
    body_lines = [lines[0]]
    indent = len(lines[0]) - len(lines[0].lstrip())
    for line in lines[1:]:
        stripped = line.lstrip()
        cur_indent = len(line) - len(stripped)
        if stripped.startswith("def ") and cur_indent <= indent:
            break
        if stripped.startswith("class ") and cur_indent <= indent:
            break
        body_lines.append(line)
    return "\n".join(body_lines)


class TestAssignHelperStatusFlow:
    def test_assign_helper_sets_status_coordinating(self, issues_source: str):
        func_body = _extract_func(issues_source, "assign_helper")
        assert "STATUS_COORDINATING" in func_body

    def test_assign_helper_sets_helper(self, issues_source: str):
        func_body = _extract_func(issues_source, "assign_helper")
        assert "row.helper" in func_body

    def test_assign_helper_still_requires_owner_role(self, issues_source: str):
        func_body = _extract_func(issues_source, "assign_helper")
        assert "PROJECT_ROLE_OWNER_KEY" in func_body

    def test_assign_helper_guards_empty_helper(self, issues_source: str):
        func_body = _extract_func(issues_source, "assign_helper")
        assert "strip()" in func_body


class TestResolveStatusFlow:
    def test_resolve_sets_status_resolved(self, issues_source: str):
        func_body = _extract_func(issues_source, "resolve_issue")
        assert "STATUS_RESOLVED" in func_body

    def test_resolve_still_requires_owner_role(self, issues_source: str):
        func_body = _extract_func(issues_source, "resolve_issue")
        assert "PROJECT_ROLE_OWNER_KEY" in func_body


class TestCloseStatusFlow:
    def test_close_sets_status_closed(self, issues_source: str):
        func_body = _extract_func(issues_source, "close_issue")
        assert "STATUS_CLOSED" in func_body

    def test_close_still_requires_owner_role(self, issues_source: str):
        func_body = _extract_func(issues_source, "close_issue")
        assert "PROJECT_ROLE_OWNER_KEY" in func_body or "require_project_owner_or_admin" in func_body


class TestRequestCeoStatusFlow:
    def test_request_ceo_sets_pending_decision(self, issues_source: str):
        func_body = _extract_func(issues_source, "request_ceo")
        assert "STATUS_PENDING_DECISION" in func_body

    def test_request_ceo_still_requires_owner_or_coord(self, issues_source: str):
        func_body = _extract_func(issues_source, "request_ceo")
        assert "PROJECT_ROLE_OWNER_KEY" in func_body


class TestPatchStatusFlow:
    def test_patch_status_still_exists(self, issues_source: str):
        func_body = _extract_func(issues_source, "patch_status")
        assert "normalize_status" in func_body

    def test_patch_status_still_requires_owner_role(self, issues_source: str):
        func_body = _extract_func(issues_source, "patch_status")
        assert "PROJECT_ROLE_OWNER_KEY" in func_body


class TestCreateIssueUnchanged:
    def test_create_issue_still_sets_reporter(self, issues_source: str):
        func_body = _extract_func(issues_source, "create_issue")
        assert "row.reporter = current_user" in func_body


class TestNoNewEndpoint:
    def test_router_endpoints_unchanged(self, issues_source: str):
        expected = [
            "list_issues", "create_issue", "list_my_issues", "get_issue",
            "update_issue", "delete_issue", "patch_status", "resolve_issue",
            "close_issue", "assign_helper", "request_ceo",
        ]
        for func_name in expected:
            assert re.search(rf"def {re.escape(func_name)}\b", issues_source), f"should have {func_name}"


class TestVisibilityUnchanged:
    def test_can_view_all_still_exists(self, issues_source: str):
        assert "_can_view_project_all_issues" in issues_source

    def test_is_related_still_exists(self, issues_source: str):
        assert "_is_issue_related_to_user" in issues_source

    def test_list_issues_still_uses_visibility_filter(self, issues_source: str):
        func_body = _extract_func(issues_source, "list_issues")
        assert "_can_view_project_all_issues" in func_body

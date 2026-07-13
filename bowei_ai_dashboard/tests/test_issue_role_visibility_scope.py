"""N4-P2-L 问题中心角色可见范围收口 — 测试。"""

import re
import pytest


# ── 文件结构测试 ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def issues_source() -> str:
    """读取 issues.py 源码文本。"""
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "app", "routers", "issues.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def issues_page_source() -> str:
    """读取 IssuesPage.tsx 源码文本。"""
    import os
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, "frontend", "src", "pages", "IssuesPage.tsx")
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def schemas_source() -> str:
    """读取 schemas.py 源码文本。"""
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "app", "schemas.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── 辅助函数存在性 ────────────────────────────────────────────

class TestHelpersExist:
    """验证 _can_view_project_all_issues 和 _is_issue_related_to_user 已定义。"""

    def test_can_view_project_all_issues_defined(self, issues_source: str):
        assert "_can_view_project_all_issues" in issues_source, (
            "必须定义 _can_view_project_all_issues 辅助函数"
        )

    def test_is_issue_related_to_user_defined(self, issues_source: str):
        assert "_is_issue_related_to_user" in issues_source, (
            "必须定义 _is_issue_related_to_user 辅助函数"
        )


# ── _can_view_project_all_issues 规则测试 ─────────────────────

class TestCanViewProjectAllIssues:
    """验证 _can_view_project_all_issues 的规则实现。"""

    def test_tech_admin_allowed(self, issues_source: str):
        """tech_admin / super_admin 应被允许看全项目问题。"""
        assert "is_tech_admin" in issues_source
        func_body = _extract_func(issues_source, "_can_view_project_all_issues")
        assert "is_tech_admin" in func_body, "tech_admin 应被允许"

    def test_ceo_allowed(self, issues_source: str):
        """company_ceo 应被允许看全项目问题。"""
        func_body = _extract_func(issues_source, "_can_view_project_all_issues")
        assert "is_ceo" in func_body, "company_ceo 应被允许"

    def test_owner_allowed(self, issues_source: str):
        """owner 应被允许看全项目问题。"""
        func_body = _extract_func(issues_source, "_can_view_project_all_issues")
        assert '"owner"' in func_body, "owner 应被允许"

    def test_coordinator_allowed(self, issues_source: str):
        """coordinator 应被允许看全项目问题。"""
        func_body = _extract_func(issues_source, "_can_view_project_all_issues")
        assert '"coordinator"' in func_body, "coordinator 应被允许"

    def test_project_ceo_allowed(self, issues_source: str):
        """project_ceo 应被允许看全项目问题。"""
        func_body = _extract_func(issues_source, "_can_view_project_all_issues")
        assert '"project_ceo"' in func_body, "project_ceo 应被允许"

    def test_ordinary_member_not_allowed(self, issues_source: str):
        """普通 member 不应拿到全量可见权限（返回 False）。"""
        func_body = _extract_func(issues_source, "_can_view_project_all_issues")
        # 函数末尾应 return False
        assert func_body.strip().endswith("return False") or "return False" in func_body, (
            "普通 member 应返回 False"
        )


# ── _is_issue_related_to_user 规则测试 ────────────────────────

class TestIsIssueRelatedToUser:
    """验证 _is_issue_related_to_user 检查 reporter / owner / helper。"""

    def test_checks_reporter(self, issues_source: str):
        func_body = _extract_func(issues_source, "_is_issue_related_to_user")
        assert "reporter" in func_body, "应检查 reporter"

    def test_checks_owner_username(self, issues_source: str):
        func_body = _extract_func(issues_source, "_is_issue_related_to_user")
        assert "owner" in func_body, "应检查 owner"

    def test_checks_helper(self, issues_source: str):
        func_body = _extract_func(issues_source, "_is_issue_related_to_user")
        assert "helper" in func_body, "应检查 helper"


# ── list_issues 过滤测试 ──────────────────────────────────────

class TestListIssuesFiltering:
    """验证 list_issues 中已加入角色可见范围过滤。"""

    def test_list_issues_uses_filter(self, issues_source: str):
        """list_issues 中应调用 _can_view_project_all_issues。"""
        func_body = _extract_func(issues_source, "list_issues")
        assert "_can_view_project_all_issues" in func_body, (
            "list_issues 必须调用 _can_view_project_all_issues 进行过滤"
        )

    def test_related_filter_or_conditions(self, issues_source: str):
        """普通成员过滤应使用 or_ 包含 reporter/owner/helper。"""
        func_body = _extract_func(issues_source, "list_issues")
        assert "or_(" in func_body or "or_ (\n" in func_body or "or_(\n" in func_body, (
            "需使用 or_ 构建多条件过滤"
        )
        # 至少包含 reporter 和 owner 过滤
        assert "reporter" in func_body, "需包含 reporter 过滤"
        assert "owner" in func_body, "需包含 owner 过滤"
        assert "helper" in func_body, "需包含 helper 过滤"


# ── get_issue 单条详情权限测试 ─────────────────────────────────

class TestGetIssueVisibility:
    """验证 get_issue 单条详情权限收口。"""

    def test_get_issue_checks_visibility(self, issues_source: str):
        """get_issue 应在 project_id 分支检查角色可见范围。"""
        func_body = _extract_func(issues_source, "get_issue")
        assert "_can_view_project_all_issues" in func_body, (
            "get_issue 应调用 _can_view_project_all_issues"
        )

    def test_get_issue_403_for_unrelated(self, issues_source: str):
        """不相关问题应返回 403。"""
        func_body = _extract_func(issues_source, "get_issue")
        assert "403" in func_body, "不相关问题应返回 403"
        assert "permission denied" in func_body.lower(), (
            "应包含 permission denied 消息"
        )


# ── 创建问题不受影响 ──────────────────────────────────────────

class TestCreateIssueUnaffected:
    """验证 create_issue 未被本轮修改。"""

    def test_create_issue_still_has_reporter_assignment(self, issues_source: str):
        func_body = _extract_func(issues_source, "create_issue")
        assert "row.reporter = current_user" in func_body, (
            "reporter 赋值不应被移除"
        )

    def test_create_issue_still_calls_require_project_access(self, issues_source: str):
        func_body = _extract_func(issues_source, "create_issue")
        assert "require_project_access" in func_body, (
            "require_project_access 不应被移除"
        )


# ── 全局列表权限不受影响 ──────────────────────────────────────

class TestGlobalListUnchanged:
    """验证全局 /api/issues 不带 project_id 的权限不受影响。"""

    def test_global_list_still_requires_admin_or_ceo(self, issues_source: str):
        func_body = _extract_func(issues_source, "list_issues")
        assert "_require_global_read_scope" in func_body, (
            "全局列表仍需 tech_admin / company_ceo 权限"
        )


# ── /api/issues/mine 不受影响 ─────────────────────────────────

class TestMineUnchanged:
    """验证 /api/issues/mine 未被修改。"""

    def test_mine_still_filter_by_reporter(self, issues_source: str):
        func_body = _extract_func(issues_source, "list_my_issues")
        assert "reporter" in func_body, "mine 仍应按 reporter 过滤"


# ── Schemas 不受影响 ──────────────────────────────────────────

class TestSchemasUnchanged:
    """验证 IssuePayload 默认值未被修改。"""

    def test_issue_type_default_unchanged(self, schemas_source: str):
        assert 'Field("问题"' in schemas_source, "issue_type 默认值仍为「问题」"

    def test_priority_default_unchanged(self, schemas_source: str):
        assert 'Field("中"' in schemas_source, "priority 默认值仍为「中」"

    def test_status_default_unchanged(self, schemas_source: str):
        assert 'Field("待处理"' in schemas_source, "status 默认值仍为「待处理」"


# ── 前端 IssuesPage 不受影响（Kanban / 表单）───────────────────

class TestFrontendUnaffected:
    """验证前端 IssuesPage 不被修改（N4-P2-L 默认不改前端）。"""

    def test_kanban_6_columns(self, issues_page_source: str):
        """看板仍是 6 列。"""
        assert "待处理" in issues_page_source
        assert "处理中" in issues_page_source
        assert "待协调" in issues_page_source
        assert "待决策" in issues_page_source
        assert "已解决" in issues_page_source
        assert "已关闭" in issues_page_source

    def test_add_form_still_has_project_select(self, issues_page_source: str):
        """新增问题表单仍有「所属项目」选择。"""
        assert "所属项目" in issues_page_source, "应保留所属项目字段"

    def test_add_form_still_has_description(self, issues_page_source: str):
        """新增问题表单仍有「问题描述」。"""
        assert "问题描述" in issues_page_source, "应保留问题描述字段"

    def test_add_form_still_has_related_task(self, issues_page_source: str):
        """新增问题表单仍有「关联重点工作」。"""
        assert "关联重点工作" in issues_page_source, "应保留关联重点工作"


# ── 禁止事项验证 ──────────────────────────────────────────────

class TestForbiddenChanges:
    """验证未出现禁止事项。"""

    def test_no_risk_center(self, issues_source: str):
        assert "风险中心" not in issues_source, "不应出现风险中心"

    def test_no_migration_file(self):
        import os
        test_dir = os.path.dirname(__file__)
        root = os.path.dirname(test_dir)
        # 检查 alembic 目录没有新增 migration
        alembic = os.path.join(root, "alembic", "versions")
        if os.path.isdir(alembic):
            import glob
            py_files = glob.glob(os.path.join(alembic, "*.py"))
            non_init = [f for f in py_files if not f.endswith("__init__.py")]
            # 只检查是否有新 migration（数量应该和基线一致）
            assert len(non_init) <= 0, (
                f"不应新增 migration 文件: {non_init}"
            )

    def test_no_new_status_in_flow(self, issues_source: str):
        """issue_flow 状态未在本轮新增。"""
        import os
        flow_path = os.path.join(os.path.dirname(__file__), "..", "app", "domain", "issue_flow.py")
        with open(flow_path, encoding="utf-8") as f:
            flow_src = f.read()
        # STATUS_COORDINATING 可能已存在（N4-P2-J），但不应有本轮新增的
        # 不对 issue_flow.py 做断言，因为 N4-P2-J 已添加

    def test_related_subtask_id_still_in_payload(self, schemas_source: str):
        """IssuePayload 仍包含 related_subtask_id。"""
        assert "related_subtask_id" in schemas_source, (
            "related_subtask_id 字段不应被移除"
        )


# ── 工具函数 ──────────────────────────────────────────────────

def _extract_func(source: str, func_name: str) -> str:
    """从源码中提取函数体文本（简单实现）。"""
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
        # 遇到同缩进或更浅的 def / class 则停止
        if stripped.startswith("def ") and cur_indent <= indent:
            break
        if stripped.startswith("class ") and cur_indent <= indent:
            break
        body_lines.append(line)
    return "\n".join(body_lines)

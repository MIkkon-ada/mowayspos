"""N4-P2-N: 普通成员问题视图简化 — 前端结构测试（语义加固版）。"""
import os
import re
import pytest


# ── 辅助函数 ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def issues_page_source() -> str:
    """读取 IssuesPage.tsx 源码文本。"""
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, "frontend", "src", "pages", "IssuesPage.tsx")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_use_memo_body(source: str, variable_name: str) -> str:
    """提取 useMemo(() => { ... }, [...]) 中箭头函数体内容。"""
    # 定位 useMemo(() => {
    pattern = rf"{re.escape(variable_name)}\s*=\s*useMemo\s*\(\s*\(\s*\)\s*=>\s*\{{"
    m = re.search(pattern, source)
    if not m:
        return ""
    start = m.end()
    # 从 start 开始匹配大括号
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
        i += 1
    return source[start:i - 1]


def _extract_jsx_branch(source: str, branch_marker: str) -> str:
    """提取以 branch_marker 开头的 JSX return 分支内容。

    从前面的 return ( 或 <>+<div 开始提取直到该分支末尾的闭合标签。
    使用启发式方法：从 marker 位置向前找到 return，然后向后提取。
    """
    pos = source.find(branch_marker)
    if pos < 0:
        return ""
    # 从该位置向后取足够大的区块（该分支通常是完整的 return JSX）
    # 从 marker 所在行开始向后扫描
    return source[pos:]


def _extract_create_issue_call(source: str) -> str:
    """提取 createIssue({...}) 调用中的参数部分。"""
    m = re.search(r'createIssue\(\s*\{([^}]*)\}\s*\)', source, re.DOTALL)
    if not m:
        return ""
    return m.group(1)


def _member_selection_snippet(source: str) -> str:
    """提取普通成员项目选择分支：从 !hasAnyManagementRole 到分支结束。

    分支结构为:
        if (!hasAnyManagementRole) { return (...); }
        // 管理角色：原项目选择页
        return (...);
    我们取第一个 if 块的内容。
    """
    idx = source.find("!hasAnyManagementRole")
    if idx < 0:
        return ""
    # 找到包含该标记的 if 语句开始
    # 向前找到 "if ("
    start = source.rfind("if (", 0, idx)
    if start < 0:
        return ""
    # 从 "if (" 开始，用大括号计数提取整个 if 块
    brace_pos = source.find("{", start)
    if brace_pos < 0:
        return ""
    depth = 1
    i = brace_pos + 1
    while i < len(source) and depth > 0:
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
        i += 1
    return source[start:i]


def _member_detail_snippet(source: str) -> str:
    """提取普通成员项目详情分支：从 isMemberIssueView 条件判断到分支结束。

    分支结构为:
        if (isMemberIssueView) { return (<><div ...> ... </>); }
        return (...)
    我们取第一个 if 块的 return JSX 内容。
    """
    idx = source.find("if (isMemberIssueView)")
    if idx < 0:
        return ""
    brace_pos = source.find("{", idx)
    if brace_pos < 0:
        return ""
    depth = 1
    i = brace_pos + 1
    while i < len(source) and depth > 0:
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
        i += 1
    return source[idx:i]


# ── 角色判断（提取 useMemo 函数体验证） ──────────────────────────────

class TestRoleChecks:
    """验证角色判断使用正确的函数体内容。"""

    def test_can_view_all_body_includes_roles_and_user_roles(self, issues_page_source: str):
        """canViewAllProjectIssues 函数体包含所有管理角色和 user_roles。"""
        body = _extract_use_memo_body(issues_page_source, "canViewAllProjectIssues")
        assert body, "需存在 canViewAllProjectIssues useMemo"
        assert "is_tech_admin" in body, "应包含 is_tech_admin"
        assert "is_ceo" in body, "应包含 is_ceo"
        assert "'owner'" in body, "应包含 owner"
        assert "'coordinator'" in body, "应包含 coordinator"
        assert "'project_ceo'" in body, "应包含 project_ceo"
        assert "user_roles" in body, "应使用 currentProject.user_roles"

    def test_can_manage_issues_body_only_owner_and_tech_admin(self, issues_page_source: str):
        """canManageIssues 函数体只包含 owner 和 tech_admin。"""
        body = _extract_use_memo_body(issues_page_source, "canManageIssues")
        assert body, "需存在 canManageIssues useMemo"
        assert "is_tech_admin" in body, "应包含 is_tech_admin"
        assert "'owner'" in body, "应包含 owner"
        assert "'coordinator'" not in body, "不应包含 coordinator"
        assert "'project_ceo'" not in body, "不应包含 project_ceo"
        assert "is_ceo" not in body, "不应包含 is_ceo"

    def test_is_member_view_depends_on_can_view_all(self, issues_page_source: str):
        """isMemberIssueView 依赖 Boolean(currentProject) 和 !canViewAllProjectIssues。"""
        # 用正则提取 isMemberIssueView = ... 表达式
        m = re.search(
            r'isMemberIssueView\s*=\s*(.+?)(?:;\s*$|\n)',
            issues_page_source,
            re.MULTILINE,
        )
        assert m, "需存在 isMemberIssueView 赋值"
        expr = m.group(1).strip()
        assert "canViewAllProjectIssues" in expr, "应依赖 canViewAllProjectIssues"
        assert "currentProject" in expr, "应依赖 currentProject"

    def test_has_any_management_role_uses_all_projects(self, issues_page_source: str):
        """hasAnyManagementRole 遍历 projects 的 user_roles。"""
        body = _extract_use_memo_body(issues_page_source, "hasAnyManagementRole")
        assert body, "需存在 hasAnyManagementRole useMemo"
        assert "projects" in body, "应遍历 projects"
        assert "user_roles" in body, "应检查 user_roles"
        assert "'owner'" in body and "'coordinator'" in body and "'project_ceo'" in body, (
            "应包含 owner, coordinator, project_ceo"
        )


# ── 普通成员项目选择分支 ──────────────────────────────────────────

class TestMemberProjectSelection:
    """验证普通成员无管理角色时的项目选择页（基于分支区段）。"""

    def test_member_branch_exists(self, issues_page_source: str):
        """存在 !hasAnyManagementRole 分支。"""
        assert "!hasAnyManagementRole" in issues_page_source, (
            "需存在 !hasAnyManagementRole 分支"
        )

    def test_member_branch_includes_title_and_button(self, issues_page_source: str):
        """成员分支包含「与我相关的问题」和「查看问题」。"""
        snippet = _member_selection_snippet(issues_page_source)
        assert snippet, "未找到成员选择分支"
        assert "与我相关的问题" in snippet, "需包含成员标题"
        assert "查看问题" in snippet, "需包含「查看问题」按钮"
        assert "我的角色" in snippet, "需包含「我的角色」列"

    def test_member_branch_excludes_management_elements(self, issues_page_source: str):
        """成员分支不包含管理统计卡和管理列。"""
        snippet = _member_selection_snippet(issues_page_source)
        assert snippet, "未找到成员选择分支"
        assert "待处理问题" not in snippet, "不应包含管理统计「待处理问题」"
        assert "处理中问题" not in snippet, "不应包含管理统计「处理中问题」"
        assert "待决策事项" not in snippet, "不应包含管理统计「待决策事项」"
        assert "项目负责人" not in snippet, "不应包含「项目负责人」列"
        assert "Coach / 企业教练" not in snippet, "不应包含「Coach / 企业教练」列"
        assert "进入问题中心" not in snippet, "不应包含「进入问题中心」按钮"

    def test_management_selection_still_exists(self, issues_page_source: str):
        """管理项目选择页仍保留。"""
        assert "项目问题中心" in issues_page_source, "管理项目选择页标题应保留"
        assert "进入问题中心" in issues_page_source, "「进入问题中心」按钮应保留"


# ── 普通成员项目详情分支 ──────────────────────────────────────────

class TestMemberProjectDetail:
    """验证普通成员选择项目后的视图（基于分支区段）。"""

    def test_member_detail_branch_exists(self, issues_page_source: str):
        """存在 isMemberIssueView 分支。"""
        assert "isMemberIssueView" in issues_page_source, "需存在 isMemberIssueView 标记"

    def test_member_detail_includes_required_elements(self, issues_page_source: str):
        """成员详情分支包含必要元素。"""
        snippet = _member_detail_snippet(issues_page_source)
        assert snippet, "未找到成员详情分支"
        assert "memberFilteredIssues" in snippet, "需使用 memberFilteredIssues"
        assert "问题摘要" in snippet, "需包含「问题摘要」列"
        assert "我的关系" in snippet, "需包含「我的关系」列"
        assert "查看详情" in snippet, "需包含「查看详情」按钮"
        assert "AddIssueModal" in snippet, "需包含 AddIssueModal"

    def test_member_detail_includes_status_and_columns(self, issues_page_source: str):
        """成员详情包含状态、任务关联和更新时间列。"""
        snippet = _member_detail_snippet(issues_page_source)
        assert snippet, "未找到成员详情分支"
        assert "当前状态" in snippet, "需包含「当前状态」列"
        assert "关联重点工作" in snippet or "关键任务" in snippet, (
            "需包含关联重点工作或关键任务列"
        )
        assert "更新时间" in snippet, "需包含「更新时间」列"

    def test_member_detail_excludes_management_actions(self, issues_page_source: str):
        """成员详情分支不包含任何负责人处理动作。"""
        snippet = _member_detail_snippet(issues_page_source)
        assert snippet, "未找到成员详情分支"
        excluded = [
            "canManageIssues",
            "handleStartProcessing",
            "handleAssignHelper",
            "handleResolve",
            "handleRequestCeo",
            "handleClose",
            "仅项目负责人可执行处理动作",
            "处理问题",
            "指定协助人",
            "提交解决结果",
            "确认关闭",
            "上报Coach",
        ]
        for term in excluded:
            assert term not in snippet, f"成员分支不应包含「{term}」"

    def test_member_detail_has_get_my_relationship(self, issues_page_source: str):
        """成员详情包含 getMyRelationship。"""
        snippet = _member_detail_snippet(issues_page_source)
        assert snippet, "未找到成员详情分支"
        assert "getMyRelationship" in snippet, "需存在 getMyRelationship"

    def test_member_empty_state(self, issues_page_source: str):
        """成员详情包含空状态提示。"""
        snippet = _member_detail_snippet(issues_page_source)
        assert snippet, "未找到成员详情分支"
        assert "当前项目暂无与你相关的问题" in snippet, "需包含成员空状态"


# ── 管理视图回归 ──────────────────────────────────────────────

class TestManagementViewRegression:
    """验证管理角色视图未受影响。"""

    def test_kanban_columns_still_exist(self, issues_page_source: str):
        """KANBAN_COLUMNS 仍存在。"""
        assert "KANBAN_COLUMNS" in issues_page_source, "KANBAN_COLUMNS 仍需存在"

    def test_six_statuses_still_exist(self, issues_page_source: str):
        """六个状态仍存在。"""
        for status in ["待处理", "处理中", "待协调", "待决策", "已解决", "已关闭"]:
            assert status in issues_page_source, f"状态「{status}」仍需存在"

    def test_management_actions_still_exist(self, issues_page_source: str):
        """所有负责人处理动作仍存在。"""
        actions = [
            "handleStartProcessing",
            "handleAssignHelper",
            "handleResolve",
            "handleRequestCeo",
            "handleClose",
            "canManageIssues",
        ]
        for action in actions:
            assert action in issues_page_source, f"{action} 仍需存在"


# ── 新增问题表单回归 ──────────────────────────────────────────

class TestAddIssueFormRegression:
    """验证新增问题表单未被修改（N4-P2-K 口径）。"""

    def test_form_fields_still_exist(self, issues_page_source: str):
        """新增表单必要字段仍存在。"""
        for field in ["问题描述", "关联重点工作", "关联关键任务", "期望解决时间"]:
            assert field in issues_page_source, f"字段「{field}」仍需存在"

    def test_defaults_still_set(self, issues_page_source: str):
        """默认值仍存在（问题类型、优先级、状态）。"""
        assert issue_contains(issues_page_source, "issue_type", "'问题'") or \
               issue_contains(issues_page_source, "issue_type", '"问题"'), (
            "默认 issue_type 仍需为「问题」"
        )
        assert issue_contains(issues_page_source, "priority", "'中'") or \
               issue_contains(issues_page_source, "priority", '"中"'), (
            "默认 priority 仍需为「中」"
        )
        assert issue_contains(issues_page_source, "status", "'待处理'") or \
               issue_contains(issues_page_source, "status", '"待处理"'), (
            "默认 status 仍需为「待处理」"
        )

    def test_source_type_default_still_set(self, issues_page_source: str):
        """source_type 默认值仍为「人工录入」。"""
        assert issue_contains(issues_page_source, "source_type", "'人工录入'") or \
               issue_contains(issues_page_source, "source_type", '"人工录入"'), (
            "source_type 仍需为「人工录入」"
        )

    def test_create_issue_no_owner_or_helper(self, issues_page_source: str):
        """createIssue 调用不包含 owner、helper、need_decision_by。"""
        params = _extract_create_issue_call(issues_page_source)
        assert params, "需找到 createIssue({...}) 调用"
        assert "owner" not in params, "createIssue 不应传 owner"
        assert "helper" not in params, "createIssue 不应传 helper"
        assert "need_decision_by" not in params, "createIssue 不应传 need_decision_by"

    def test_create_issue_has_required_params(self, issues_page_source: str):
        """createIssue 调用包含必要参数。"""
        params = _extract_create_issue_call(issues_page_source)
        assert params, "需找到 createIssue({...}) 调用"
        assert "project_id" in params, "应包含 project_id"
        assert "description" in params, "应包含 description"
        assert "issue_type" in params, "应包含 issue_type"
        assert "priority" in params, "应包含 priority"
        assert "status" in params, "应包含 status"
        assert "source_type" in params, "应包含 source_type"

    def test_save_button_exists(self, issues_page_source: str):
        """新增表单「保存问题」按钮存在。"""
        assert "保存问题" in issues_page_source, "保存问题按钮仍需存在"


# ── 数据请求 ──────────────────────────────────────────────────

class TestDataRequests:
    """验证数据请求使用正确的 API。"""

    def test_uses_fetch_issues_with_project_id(self, issues_page_source: str):
        """调用 fetchIssues(projectId)。"""
        assert "fetchIssues(projectId)" in issues_page_source, (
            "需调用 fetchIssues(projectId)"
        )

    def test_no_fetch_my_issues_import(self, issues_page_source: str):
        """不导入 fetchMyIssues。"""
        assert "fetchMyIssues" not in issues_page_source, (
            "不应导入或调用 fetchMyIssues"
        )

    def test_no_new_api_endpoint(self, issues_page_source: str):
        """不新增 API endpoint。"""
        # 文件仍只导入已知的 issues API 函数
        imports = " ".join([
            line for line in issues_page_source.split("\n")
            if "import" in line and "issues" in line and line.strip().startswith("import")
        ])
        assert "fetchIssues" in imports, "仍需导入 fetchIssues"
        assert "fetchMyIssues" not in imports, "不应导入 fetchMyIssues"


# ── 辅助函数 ──────────────────────────────────────────────────

def issue_contains(source: str, key: str, value: str) -> bool:
    """检查 source 中是否包含 key: value 组合（在 createIssue 调用附近）。"""
    pattern = rf"{re.escape(key)}\s*:\s*{re.escape(value)}"
    return bool(re.search(pattern, source))

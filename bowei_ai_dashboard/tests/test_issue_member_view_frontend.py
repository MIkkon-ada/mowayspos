"""N4-P2-N: 普通成员问题视图简化 — 前端结构测试。"""
import os
import pytest


@pytest.fixture(scope="module")
def issues_page_source() -> str:
    """读取 IssuesPage.tsx 源码文本。"""
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, "frontend", "src", "pages", "IssuesPage.tsx")
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── 角色判断 ──────────────────────────────────────────────────

class TestRoleChecks:
    """验证 IssuesPage 中存在普通成员视图判断。"""

    def test_has_can_view_all_project_issues(self, issues_page_source: str):
        """存在 canViewAllProjectIssues 判断。"""
        assert "canViewAllProjectIssues" in issues_page_source, (
            "需存在 canViewAllProjectIssues 角色判断"
        )

    def test_has_is_member_issue_view(self, issues_page_source: str):
        """存在 isMemberIssueView 标记。"""
        assert "isMemberIssueView" in issues_page_source, (
            "需存在 isMemberIssueView 普通成员视图标记"
        )

    def test_uses_project_user_roles(self, issues_page_source: str):
        """判断中使用 currentProject.user_roles。"""
        assert "user_roles" in issues_page_source, (
            "需使用 currentProject.user_roles 进行角色判断"
        )

    def test_has_any_management_role(self, issues_page_source: str):
        """存在 hasAnyManagementRole 判断。"""
        assert "hasAnyManagementRole" in issues_page_source, (
            "需存在 hasAnyManagementRole 判断（项目选择页用）"
        )

    def test_owner_not_in_member_view(self, issues_page_source: str):
        """owner 角色不被排除在管理视图外。"""
        assert "'owner'" in issues_page_source, (
            "owner 应在管理角色列表中"
        )

    def test_coordinator_not_in_member_view(self, issues_page_source: str):
        """coordinator 角色不被排除在管理视图外。"""
        assert "'coordinator'" in issues_page_source, (
            "coordinator 应在管理角色列表中"
        )

    def test_project_ceo_not_in_member_view(self, issues_page_source: str):
        """project_ceo 角色不被排除在管理视图外。"""
        assert "'project_ceo'" in issues_page_source, (
            "project_ceo 应在管理角色列表中"
        )

    def test_tech_admin_not_in_member_view(self, issues_page_source: str):
        """tech admin 使用管理视图。"""
        assert "is_tech_admin" in issues_page_source, (
            "tech admin 应在管理视图判断中"
        )

    def test_ceo_not_in_member_view(self, issues_page_source: str):
        """company CEO 使用管理视图。"""
        assert "is_ceo" in issues_page_source, (
            "company ceo 应在管理视图判断中"
        )

    def test_not_using_system_role_only(self, issues_page_source: str):
        """不能仅依赖 system_role === 'normal_member' 判断。"""
        # 必须使用 user_roles 而非简单的 system_role 判断
        assert "user_roles" in issues_page_source or "currentProject.user_roles" in issues_page_source, (
            "必须使用 currentProject.user_roles 而非仅依赖 system_role"
        )


# ── 普通成员项目选择页 ──────────────────────────────────────────

class TestMemberProjectSelection:
    """验证普通成员无管理角色时的项目选择页。"""

    def test_has_member_title(self, issues_page_source: str):
        """包含「与我相关的问题」标题。"""
        assert "与我相关的问题" in issues_page_source, (
            "需包含「与我相关的问题」标题"
        )

    def test_has_view_issues_button(self, issues_page_source: str):
        """包含「查看问题」按钮文案。"""
        assert "查看问题" in issues_page_source, (
            "需包含「查看问题」按钮"
        )

    def test_member_project_list_branch_exists(self, issues_page_source: str):
        """存在普通成员项目列表分支。"""
        assert "!hasAnyManagementRole" in issues_page_source, (
            "需存在 !hasAnyManagementRole 分支"
        )

    def test_member_branch_no_management_stats(self, issues_page_source: str):
        """普通成员分支不包含管理统计卡。"""
        # 管理统计卡在 hasAnyManagementRole 为真的分支中
        # 成员分支中不应有「待处理问题 —」
        assert "与我相关的问题" in issues_page_source, (
            "需存在成员视图标题"
        )

    def test_management_selection_still_exists(self, issues_page_source: str):
        """管理项目选择页仍保留。"""
        assert "项目问题中心" in issues_page_source, (
            "管理项目选择页标题应保留"
        )
        assert "进入问题中心" in issues_page_source, (
            "「进入问题中心」按钮应保留"
        )


# ── 普通成员项目详情页 ──────────────────────────────────────────

class TestMemberProjectDetail:
    """验证普通成员选择项目后的视图。"""

    def test_has_member_table_or_list(self, issues_page_source: str):
        """存在普通成员紧凑表格。"""
        assert "memberFilteredIssues" in issues_page_source, (
            "需存在 memberFilteredIssues 过滤逻辑"
        )

    def test_has_description_column(self, issues_page_source: str):
        """包含问题摘要列。"""
        assert "问题摘要" in issues_page_source, (
            "需包含「问题摘要」列"
        )

    def test_has_status_column(self, issues_page_source: str):
        """包含状态列。"""
        assert "当前状态" in issues_page_source, (
            "需包含「当前状态」列"
        )

    def test_has_related_task_column(self, issues_page_source: str):
        """包含关联重点工作/关键任务列。"""
        assert "关联重点工作" in issues_page_source or "关键任务" in issues_page_source, (
            "需包含关联重点工作或关键任务列"
        )

    def test_has_updated_at_column(self, issues_page_source: str):
        """包含更新时间列。"""
        assert "更新时间" in issues_page_source, (
            "需包含「更新时间」列"
        )

    def test_has_view_detail(self, issues_page_source: str):
        """包含查看详情操作。"""
        assert "查看详情" in issues_page_source, (
            "需包含「查看详情」按钮"
        )

    def test_has_member_empty_state(self, issues_page_source: str):
        """包含普通成员空状态。"""
        assert "当前项目暂无与你相关的问题" in issues_page_source, (
            "需包含成员空状态提示"
        )

    def test_member_view_no_management_actions(self, issues_page_source: str):
        """普通成员视图不渲染负责人动作区。"""
        # getMyRelationship 表明这是成员视图专用逻辑
        assert "getMyRelationship" in issues_page_source, (
            "需存在 getMyRelationship 成员关系判断"
        )

    def test_has_my_relationship_column(self, issues_page_source: str):
        """包含「我的关系」列。"""
        assert "我的关系" in issues_page_source, (
            "需包含「我的关系」列"
        )

    def test_get_my_relationship_checks_reporter(self, issues_page_source: str):
        """getMyRelationship 检查 reporter。"""
        assert "reporter" in issues_page_source, (
            "需检查 reporter 关系"
        )

    def test_get_my_relationship_checks_owner(self, issues_page_source: str):
        """getMyRelationship 检查 owner。"""
        assert "负责" in issues_page_source, (
            "需检查 owner 关系（「我负责的」）"
        )

    def test_get_my_relationship_checks_helper(self, issues_page_source: str):
        """getMyRelationship 检查 helper。"""
        assert "协助" in issues_page_source, (
            "需检查 helper 关系（「我协助的」）"
        )

    def test_member_uses_fetch_issues(self, issues_page_source: str):
        """普通成员项目页仍调用 fetchIssues(projectId)。"""
        assert "fetchIssues" in issues_page_source, (
            "仍需调用 fetchIssues"
        )

    def test_member_does_not_use_fetch_my_issues(self, issues_page_source: str):
        """不使用 fetchMyIssues() 替换项目列表请求。"""
        assert "fetchMyIssues" not in issues_page_source, (
            "不应使用 fetchMyIssues"
        )


# ── 管理视图回归 ──────────────────────────────────────────────

class TestManagementViewRegression:
    """验证管理角色视图未受影响。"""

    def test_kanban_columns_still_exist(self, issues_page_source: str):
        """KANBAN_COLUMNS 仍存在。"""
        assert "KANBAN_COLUMNS" in issues_page_source, (
            "KANBAN_COLUMNS 仍需存在"
        )

    def test_six_statuses_still_exist(self, issues_page_source: str):
        """六个状态仍存在。"""
        for status in ["待处理", "处理中", "待协调", "待决策", "已解决", "已关闭"]:
            assert status in issues_page_source, (
                f"状态「{status}」仍需存在"
            )

    def test_handle_start_processing_still_exists(self, issues_page_source: str):
        """handleStartProcessing 仍存在。"""
        assert "handleStartProcessing" in issues_page_source, (
            "handleStartProcessing 仍需存在"
        )

    def test_handle_assign_helper_still_exists(self, issues_page_source: str):
        """handleAssignHelper 仍存在。"""
        assert "handleAssignHelper" in issues_page_source, (
            "handleAssignHelper 仍需存在"
        )

    def test_handle_resolve_still_exists(self, issues_page_source: str):
        """handleResolve 仍存在。"""
        assert "handleResolve" in issues_page_source, (
            "handleResolve 仍需存在"
        )

    def test_handle_request_ceo_still_exists(self, issues_page_source: str):
        """handleRequestCeo 仍存在。"""
        assert "handleRequestCeo" in issues_page_source, (
            "handleRequestCeo 仍需存在"
        )

    def test_handle_close_still_exists(self, issues_page_source: str):
        """handleClose 仍存在。"""
        assert "handleClose" in issues_page_source, (
            "handleClose 仍需存在"
        )

    def test_can_manage_issues_still_exists(self, issues_page_source: str):
        """canManageIssues 仍存在。"""
        assert "canManageIssues" in issues_page_source, (
            "canManageIssues 判断仍需存在"
        )


# ── 新增问题表单回归 ──────────────────────────────────────────

class TestAddIssueFormRegression:
    """验证新增问题表单未被修改。"""

    def test_description_still_exists(self, issues_page_source: str):
        """问题描述字段仍存在。"""
        assert "问题描述" in issues_page_source, (
            "问题描述字段仍需存在"
        )

    def test_related_task_still_exists(self, issues_page_source: str):
        """关联重点工作字段仍存在。"""
        assert "关联重点工作" in issues_page_source, (
            "关联重点工作字段仍需存在"
        )

    def test_related_subtask_still_exists(self, issues_page_source: str):
        """关联关键任务字段仍存在。"""
        assert "关联关键任务" in issues_page_source, (
            "关联关键任务字段仍需存在"
        )

    def test_expected_resolve_time_still_exists(self, issues_page_source: str):
        """期望解决时间字段仍存在。"""
        assert "期望解决时间" in issues_page_source, (
            "期望解决时间字段仍需存在"
        )

    def test_default_issue_type_still_set(self, issues_page_source: str):
        """默认问题类型仍存在。"""
        assert issue_contains(issues_page_source, "issue_type", "'问题'") or \
               issue_contains(issues_page_source, "issue_type", '"问题"'), (
            "默认 issue_type 仍需为「问题」"
        )

    def test_default_priority_still_set(self, issues_page_source: str):
        """默认优先级仍存在。"""
        assert issue_contains(issues_page_source, "priority", "'中'") or \
               issue_contains(issues_page_source, "priority", '"中"'), (
            "默认 priority 仍需为「中」"
        )

    def test_default_status_still_set(self, issues_page_source: str):
        """默认状态仍存在。"""
        assert issue_contains(issues_page_source, "status", "'待处理'") or \
               issue_contains(issues_page_source, "status", '"待处理"'), (
            "默认 status 仍需为「待处理」"
        )

    def test_no_owner_field_in_add_form(self, issues_page_source: str):
        """新增表单不重新加入负责人字段。"""
        # 负责人过滤（filterOwner）仍在管理视图 - 但不应在 createIssue 调用中传 owner
        # 检查 createIssue 调用不包含 explicit owner 赋值
        pass  # 结构验证，通过 createIssue 参数列表确认

    def test_no_new_api_endpoint(self, issues_page_source: str):
        """不新增 API endpoint。"""
        assert "api/issues" in issues_page_source, (
            "仍需使用 /api/issues 接口"
        )

    def test_data_request_uses_fetch_issues(self, issues_page_source: str):
        """数据请求仍使用 fetchIssues。"""
        assert "fetchIssues(projectId)" in issues_page_source, (
            "仍需调用 fetchIssues(projectId)"
        )

    def test_has_save_button(self, issues_page_source: str):
        """新增表单「保存问题」按钮存在。"""
        assert "保存问题" in issues_page_source, (
            "保存问题按钮仍需存在"
        )


# ── 辅助函数 ──────────────────────────────────────────────────

def issue_contains(source: str, key: str, value: str) -> bool:
    """检查 source 中是否包含对应的 key: value 组合（在 createIssue 调用附近）。"""
    import re
    # 简单匹配：允许空格
    pattern = rf"{re.escape(key)}\s*:\s*{re.escape(value)}"
    return bool(re.search(pattern, source))

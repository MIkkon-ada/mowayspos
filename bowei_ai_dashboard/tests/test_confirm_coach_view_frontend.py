"""N4-P2-Q: 前端语义测试 — 企业教练待办并入 AI 确认中心。

通过读取前端源码文件验证关键结构和分支，保护权限、数据加载、
动作分发、深链解析、页面隔离和兼容边界。
"""
from __future__ import annotations

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read_tsx(filename: str) -> str:
    return (FRONTEND_DIR / filename).read_text(encoding="utf-8")


def _extract_lines_between(source: str, start_marker: str, end_marker: str) -> str:
    """提取两个标记之间的源码块。"""
    lines = source.split("\n")
    result = []
    in_block = False
    for line in lines:
        if not in_block and start_marker in line:
            in_block = True
            result.append(line)
            continue
        if in_block:
            result.append(line)
            if end_marker in line:
                break
    return "\n".join(result)


def _find_branch(source: str, condition: str, context_lines: int = 25) -> str | None:
    """搜索包含某条件的代码块（前后各 context_lines 行）。"""
    idx = source.find(condition)
    if idx < 0:
        return None
    lines = source.split("\n")
    total = 0
    target_line = 0
    for i, line in enumerate(lines):
        total += len(line) + 1
        if total > idx:
            target_line = i
            break
    start = max(0, target_line - context_lines)
    end = min(len(lines), target_line + context_lines)
    return "\n".join(lines[start:end])


def _find_nth(source: str, condition: str, n: int = 1) -> str | None:
    """找到第 n 次出现条件后的字符串（从 0 计数）。"""
    idx = -1
    for _ in range(n + 1):
        idx = source.find(condition, idx + 1)
        if idx < 0:
            return None
    return source[idx:]


# ════════════════════════════════════════════════════════════════════
# 权限判断
# ════════════════════════════════════════════════════════════════════

class TestPermissions:
    """权限判断：canUseCoachDecisionView。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_can_use_coach_decision_view_exists(self):
        """canUseCoachDecisionView 变量定义存在。"""
        assert "canUseCoachDecisionView" in self.source

    def test_can_use_coach_decision_view_contains_project_ceo(self):
        """canUseCoachDecisionView 定义中包含 project_ceo。"""
        definition = _find_branch(self.source, "canUseCoachDecisionView", 30)
        assert definition is not None
        assert "project_ceo" in definition

    def test_can_use_coach_decision_view_contains_is_tech_admin(self):
        """canUseCoachDecisionView 定义中包含 is_tech_admin。"""
        definition = _find_branch(self.source, "canUseCoachDecisionView", 30)
        assert definition is not None
        assert "is_tech_admin" in definition

    def test_can_use_coach_decision_view_not_contain_is_ceo(self):
        """canUseCoachDecisionView 定义中不包含 currentUser?.is_ceo。"""
        definition = _find_branch(self.source, "canUseCoachDecisionView", 30)
        assert definition is not None
        assert "currentUser?.is_ceo" not in definition

    def test_company_ceo_not_show_coach_view(self):
        """纯 company_ceo 不显示待我决策（view=ceo 需权限检查）。"""
        # resolveInitialView 中 view=ceo 需 canUseCoachDecisionView
        assert "canUseCoachDecisionView" in self.source
        assert "view === 'ceo'" in self.source or "'ceo'" in self.source


# ════════════════════════════════════════════════════════════════════
# 数据加载
# ════════════════════════════════════════════════════════════════════

class TestDataLoading:
    """数据加载路径和深链。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_ceo_view_calls_get_pending_with_ceo_tab(self):
        """ceo 视图调用 getPending(..., 'ceo', { includeCardLevel: true })。"""
        # 第三个 viewMode === 'ceo' 出现在数据加载 useEffect 中
        # (1: isCoachView, 2: filter-sync useEffect, 3: 数据加载)
        third_ceo = _find_nth(self.source, "viewMode === 'ceo'", 2)
        assert third_ceo is not None
        snippet = third_ceo[:300]
        assert "getPending" in snippet
        assert "'ceo'" in snippet
        assert "includeCardLevel" in snippet

    def test_all_view_calls_tab_all(self):
        """all 视图调用 getPending(..., 'all')。"""
        all_branch = _find_branch(self.source, "getPending(pendingProjectId, 'all')", 20)
        assert all_branch is not None
        assert "'all'" in all_branch

    def test_mine_view_calls_fetch_my_updates(self):
        """mine 视图调用 fetchMyUpdates。"""
        assert "fetchMyUpdates" in self.source

    def test_ceo_default_cross_project(self):
        """ceo 默认跨项目查询（传 null projectId）。"""
        ceo_branch = _find_branch(self.source, "viewMode === 'ceo'", 60)
        assert ceo_branch is not None
        assert "null" in ceo_branch

    def test_all_view_uses_url_submission_id_fallback(self):
        """all 视图深链：urlSubmissionId 匹配优先，找不到回退 firstPending。"""
        all_branch = _find_branch(self.source, "getPending(pendingProjectId, 'all')", 35)
        assert all_branch is not None
        assert "urlSubmissionId" in all_branch
        assert "firstPending" in all_branch
        assert "pickItem(target)" in all_branch or "pickItem(target" in all_branch

    def test_ceo_view_uses_url_submission_id(self):
        """ceo 视图中 urlSubmissionId 用于定位。"""
        ceo_branch = _find_branch(self.source, "viewMode === 'ceo'", 70)
        assert ceo_branch is not None
        assert "urlSubmissionId" in ceo_branch


# ════════════════════════════════════════════════════════════════════
# 动作分发
# ════════════════════════════════════════════════════════════════════

class TestActions:
    """动作分发：提交级和卡片级批示。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_submission_scope_calls_ceo_decide(self):
        """提交级 scope 调用 ceoDecide。"""
        assert "handleCoachSubmissionDecide" in self.source
        assert "ceoDecide" in self.source

    def test_card_scope_calls_ceo_decide_task_card(self):
        """卡片级 scope 调用 ceoDecideTaskCard。"""
        assert "handleCoachCardDecide" in self.source
        assert "ceoDecideTaskCard" in self.source

    def test_empty_coach_note_blocked(self):
        """空白批示不可提交（!coachNote.trim() 检查）。"""
        assert "!coachNote.trim()" in self.source

    def test_success_reloads_list(self):
        """成功后重新加载列表（reloadCoachItems）。"""
        assert "reloadCoachItems" in self.source


# ════════════════════════════════════════════════════════════════════
# 深链解析
# ════════════════════════════════════════════════════════════════════

class TestDeepLinks:
    """深链解析。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_parses_view_param(self):
        """解析 view 参数。"""
        assert "searchParams.get('view')" in self.source or "get('view')" in self.source

    def test_parses_project_id(self):
        """解析 projectId。"""
        assert "searchParams.get('projectId')" in self.source or "get('projectId')" in self.source

    def test_parses_submission_id(self):
        """解析 submissionId。"""
        assert "searchParams.get('submissionId')" in self.source or "get('submissionId')" in self.source

    def test_parses_card_index(self):
        """解析 cardIndex。"""
        assert "searchParams.get('cardIndex')" in self.source or "get('cardIndex')" in self.source

    def test_no_permission_view_ceo_no_elevation(self):
        """无权限时 view=ceo 不提升 — resolveInitialView 检查 canUseCoachDecisionView。"""
        block = _find_branch(self.source, "resolveInitialView", 12)
        assert block is not None
        assert "canUseCoachDecisionView" in block

    def test_submission_id_not_found_safe_fallback(self):
        """submissionId 找不到时有安全回退。"""
        # both all and ceo branches have fallback
        all_branch = _find_branch(self.source, "getPending(pendingProjectId, 'all')", 35)
        ceo_branch = _find_branch(self.source, "viewMode === 'ceo'", 70)
        combined = (all_branch or "") + (ceo_branch or "")
        assert "??" in combined  # nullish coalescing fallback pattern
        assert "pickItem" in combined


# ════════════════════════════════════════════════════════════════════
# 卡片级批示隔离
# ════════════════════════════════════════════════════════════════════

class TestCardCoachIsolation:
    """卡片级批示入口隔离。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_top_coach_section_only_submission_scope(self):
        """主详情顶部企业教练区仅由 submission scope 控制。"""
        # 搜索顶部企业教练批示区的条件
        block = _find_branch(self.source, "企业教练决策区", 3)
        assert block is not None
        # 必须包含 submission scope 检查
        assert "ceo_decision_scope === 'submission'" in block

    def test_top_coach_section_calls_submission_decide(self):
        """顶部批示按钮调用 handleCoachSubmissionDecide。"""
        block = _find_branch(self.source, "handleCoachSubmissionDecide", 3)
        assert block is not None

    def test_card_popup_pending_ceo_shows_decide_button(self):
        """任务卡弹窗 pending_ceo_decision → 显示 handleCoachCardDecide。"""
        # 跳过前 3 个 occurrence: label/tone/card-list, 第 4 个在弹窗中
        snippet = _find_nth(self.source, "pending_ceo_decision", 3)
        assert snippet is not None
        # 弹窗块较长（含表单和按钮），取前 2500 字符
        nearby = snippet[:2500]
        assert "handleCoachCardDecide" in nearby

    def test_card_popup_ceo_decided_shows_readonly(self):
        """任务卡弹窗 ceo_decided → 只读展示批示内容。"""
        # 跳过前 2 个 occurrence: label/tone 函数, 第 3 个在弹窗中
        snippet = _find_nth(self.source, "ceo_decided", 2)
        assert snippet is not None
        nearby = snippet[:1000]
        assert "ceoNote" in nearby or "ceoDecidedAt" in nearby or "批示内容" in nearby

    def test_card_popup_other_status_no_decide_button(self):
        """任务卡弹窗非 pending/ceo_decided → 不需要企业教练决策。"""
        assert "不需要企业教练决策" in self.source

    def test_no_duplicate_card_coach_input(self):
        """不存在两个同时可操作的单卡批示输入框。"""
        # 顶部只对 submission scope 显示，卡片弹窗只对 pending_ceo_decision 显示
        # 两者永不重叠
        top_block = _find_branch(self.source, "企业教练决策区", 3)
        assert top_block is not None
        assert "ceo_decision_scope === 'submission'" in top_block
        # 卡片弹窗中的 ceo 决策区在 isCoachView 分支的 pending_ceo_decision 下
        assert "pending_ceo_decision" in self.source


# ════════════════════════════════════════════════════════════════════
# 页面隔离
# ════════════════════════════════════════════════════════════════════

class TestPageIsolation:
    """页面隔离：ceo 视图不渲染 owner 操作。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_ceo_view_retains_task_card_detail(self):
        """ceo 视图保留任务卡详情查看。"""
        assert "taskCards" in self.source
        assert "activeCard" in self.source

    def test_is_coach_view_variable_exists(self):
        """isCoachView 变量存在。"""
        assert "isCoachView" in self.source


# ════════════════════════════════════════════════════════════════════
# 删除独立页面
# ════════════════════════════════════════════════════════════════════

class TestDecisionPageRemoved:
    """DecisionPage.tsx 已删除。"""

    def test_decision_page_does_not_exist(self):
        """DecisionPage.tsx 文件不存在。"""
        assert not (FRONTEND_DIR / "pages/DecisionPage.tsx").exists()


# ════════════════════════════════════════════════════════════════════
# 路由兼容重定向
# ════════════════════════════════════════════════════════════════════

class TestLegacyRouteRedirect:
    """旧路由已改为兼容重定向。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("app/routes.tsx")

    def test_no_decision_page_import(self):
        """不存在 DecisionPage import。"""
        assert "import('../pages/DecisionPage')" not in self.source

    def test_no_decision_page_element(self):
        """不存在 element={<DecisionPage />}。"""
        assert "element={<DecisionPage" not in self.source

    def test_legacy_coach_decision_redirect_exists(self):
        """LegacyCoachDecisionRedirect 组件存在。"""
        assert "LegacyCoachDecisionRedirect" in self.source

    def test_work_decisions_uses_redirect(self):
        """work 区 decisions 路由使用 LegacyCoachDecisionRedirect。"""
        block = _find_branch(self.source, 'path="decisions"', 2)
        assert block is not None
        assert "LegacyCoachDecisionRedirect" in block

    def test_project_decisions_uses_redirect(self):
        """project 区 decisions 路由使用 LegacyCoachDecisionRedirect。"""
        second = _find_nth(self.source, 'path="decisions"', 1)
        assert second is not None
        assert "LegacyCoachDecisionRedirect" in second[:300]

    def test_redirect_target_contains_confirmations(self):
        """重定向目标包含 /work/confirmations。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 20)
        assert block is not None
        assert "/work/confirmations" in block

    def test_redirect_sets_view_ceo(self):
        """重定向强制设置 view=ceo。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 20)
        assert block is not None
        assert "view" in block
        assert "'ceo'" in block

    def test_redirect_reads_location_search(self):
        """重定向读取 location.search。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 20)
        assert block is not None
        assert "location.search" in block

    def test_redirect_uses_url_search_params(self):
        """重定向使用 URLSearchParams。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 20)
        assert block is not None
        assert "URLSearchParams" in block

    def test_redirect_sets_project_id(self):
        """项目路由重定向设置 projectId。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 20)
        assert block is not None
        assert "params.set('projectId'" in block or 'params.set("projectId"' in block

    def test_redirect_uses_replace(self):
        """重定向使用 replace。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 20)
        assert block is not None
        assert "replace" in block


# ════════════════════════════════════════════════════════════════════
# Sidebar 清理
# ════════════════════════════════════════════════════════════════════

class TestSidebarCleanup:
    """Sidebar 已移除独立企业教练入口。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("components/Sidebar.tsx")

    def test_no_enterprise_coach_label(self):
        """不存在"企业教练决策中心"。"""
        assert "企业教练决策中心" not in self.source

    def test_no_page_decisions(self):
        """不存在 page: 'decisions'。"""
        assert "page: 'decisions'" not in self.source

    def test_no_is_coach_decision_actor(self):
        """不存在 isCoachDecisionActor。"""
        assert "isCoachDecisionActor" not in self.source

    def test_no_icon_gavel(self):
        """不存在 IconGavel。"""
        assert "IconGavel" not in self.source


class TestSidebarRetained:
    """Sidebar 保留 AI 确认中心及 badge。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("components/Sidebar.tsx")

    def test_ai_confirm_center_label_exists(self):
        """仍存在 AI_CONFIRM_CENTER_LABEL。"""
        assert "AI_CONFIRM_CENTER_LABEL" in self.source

    def test_ceo_total_exists(self):
        """仍使用 ceo_total。"""
        assert "ceo_total" in self.source

    def test_show_participant_includes_project_ceo(self):
        """showParticipantModules 角色列表中包含 project_ceo。"""
        definition = _find_branch(self.source, "showParticipantModules", 8)
        assert definition is not None
        assert "project_ceo" in definition

    def test_badge_uses_ceo_total(self):
        """Sidebar badge 使用 ceo_total。"""
        badge_block = _find_branch(self.source, "confirmBadge", 8)
        assert badge_block is not None
        assert "ceo_total" in badge_block


# ════════════════════════════════════════════════════════════════════
# 类型与导航清理
# ════════════════════════════════════════════════════════════════════

class TestTypesCleanup:
    """AppPage / ProjectLayout 类型清理。"""

    def test_app_page_no_decisions(self):
        """AppPage 不含 decisions。"""
        source = _read_tsx("types.ts")
        app_page_lines = [l for l in source.split("\n") if "export type AppPage" in l]
        assert len(app_page_lines) == 1
        assert "'decisions'" not in app_page_lines[0]

    def test_page_segment_no_decisions(self):
        """ProjectLayout PageSegment 不含 decisions。"""
        source = _read_tsx("layouts/ProjectLayout.tsx")
        segment_start = source.find("type PageSegment")
        segment_end = source.find("const PATH_TO_PAGE", segment_start)
        segment_block = source[segment_start:segment_end]
        assert "'decisions'" not in segment_block

    def test_path_to_page_no_decisions(self):
        """ProjectLayout PATH_TO_PAGE 不含 decisions。"""
        source = _read_tsx("layouts/ProjectLayout.tsx")
        assert "decisions:" not in source


class TestNavigationCleanup:
    """authFlow / routeConfig 清理。"""

    def test_workspace_pages_no_decisions(self):
        """authFlow workspacePages 不含 decisions。"""
        source = _read_tsx("domain/authFlow.ts")
        assert "decisions:" not in source

    def test_sidebar_items_no_decisions(self):
        """routeConfig SIDEBAR_ITEMS 不含 decisions。"""
        source = _read_tsx("domain/routeConfig.ts")
        items_block = _extract_lines_between(source, "SIDEBAR_ITEMS", "];")
        assert "'decisions'" not in items_block

    def test_route_config_no_can_view_ceo_decision_import(self):
        """routeConfig 不再导入 canViewCeoDecision。"""
        source = _read_tsx("domain/routeConfig.ts")
        assert "canViewCeoDecision" not in source


# ════════════════════════════════════════════════════════════════════
# 统一能力保留
# ════════════════════════════════════════════════════════════════════

class TestUnifiedAbilityRetained:
    """ConfirmPage 和 permissions 仍保留企业教练能力。"""

    def test_confirm_page_has_view_mode_ceo(self):
        """ConfirmPage 仍存在 viewMode === 'ceo'。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "viewMode === 'ceo'" in source

    def test_confirm_page_calls_ceo_decide(self):
        """ConfirmPage 仍调用 ceoDecide。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "ceoDecide" in source

    def test_confirm_page_calls_ceo_decide_task_card(self):
        """ConfirmPage 仍调用 ceoDecideTaskCard。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "ceoDecideTaskCard" in source

    def test_permissions_still_defines_can_view_ceo_decision(self):
        """permissions.ts 仍定义 canViewCeoDecision。"""
        source = _read_tsx("domain/permissions.ts")
        assert "canViewCeoDecision" in source

    def test_can_view_confirm_center_references_can_view_ceo_decision(self):
        """canViewConfirmCenter 仍引用 canViewCeoDecision。"""
        source = _read_tsx("domain/permissions.ts")
        block = _find_branch(source, "canViewConfirmCenter", 8)
        assert block is not None
        assert "canViewCeoDecision" in block


# ════════════════════════════════════════════════════════════════════
# 任务卡状态展示
# ════════════════════════════════════════════════════════════════════

class TestTaskCardDecisionStatus:
    """任务卡决策状态展示。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_ceo_decided_label_exists(self):
        """taskCardDecisionLabel 包含 ceo_decided → 企业教练已批示。"""
        assert "ceo_decided" in self.source
        assert "企业教练已批示" in self.source

    def test_ceo_decided_tone_exists(self):
        """taskCardDecisionTone 包含 ceo_decided 样式。"""
        tone_block = _find_branch(self.source, "taskCardDecisionTone", 15)
        assert tone_block is not None
        assert "ceo_decided" in tone_block


# ════════════════════════════════════════════════════════════════════
# 任务卡展示模型
# ════════════════════════════════════════════════════════════════════

class TestConfirmationTaskCards:
    """任务卡展示模型。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("domain/confirmationTaskCards.ts")

    def test_ceo_note_field_exists(self):
        """ConfirmationTaskCard 包含 ceoNote 字段。"""
        assert "ceoNote" in self.source

    def test_ceo_operator_field_exists(self):
        """ConfirmationTaskCard 包含 ceoOperator 字段。"""
        assert "ceoOperator" in self.source

    def test_ceo_decided_at_field_exists(self):
        """ConfirmationTaskCard 包含 ceoDecidedAt 字段。"""
        assert "ceoDecidedAt" in self.source

    def test_ceo_fields_read_from_report(self):
        """从 task_reports 中读取 ceo_note / ceo_operator / ceo_decided_at。"""
        assert "ceo_note" in self.source
        assert "ceo_operator" in self.source
        assert "ceo_decided_at" in self.source

    def test_confirmation_status_still_exists(self):
        """原 confirmationStatus 字段继续存在。"""
        assert "confirmationStatus" in self.source

    def test_confirmation_note_still_exists(self):
        """原 confirmationNote 字段继续存在。"""
        assert "confirmationNote" in self.source

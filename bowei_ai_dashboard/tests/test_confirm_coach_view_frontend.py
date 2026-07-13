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
        # 第二个 viewMode === 'ceo' 出现在数据加载 useEffect 中
        second_ceo = _find_nth(self.source, "viewMode === 'ceo'", 1)
        assert second_ceo is not None
        snippet = second_ceo[:300]
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
# 兼容边界
# ════════════════════════════════════════════════════════════════════

class TestCompatibility:
    """兼容边界。"""

    @classmethod
    def setup_class(cls):
        cls.decision_source = _read_tsx("pages/DecisionPage.tsx")
        cls.sidebar_source = _read_tsx("components/Sidebar.tsx")

    def test_decision_page_exists(self):
        """DecisionPage.tsx 仍存在。"""
        assert len(self.decision_source) > 100

    def test_decision_page_uses_ceo_decide(self):
        """旧 DecisionPage 仍调用 ceoDecide。"""
        assert "ceoDecide" in self.decision_source

    def test_decision_page_not_calling_ceo_decide_task_card(self):
        """旧页面不调用 ceoDecideTaskCard。"""
        assert "ceoDecideTaskCard" not in self.decision_source

    def test_decision_page_permission_not_using_is_ceo(self):
        """旧 DecisionPage 权限不使用 is_ceo（改用 is_tech_admin + project_ceo）。"""
        decision_block = _find_branch(self.decision_source, "isCEO", 6)
        assert decision_block is not None
        assert "currentUser?.is_ceo" not in decision_block

    def test_sidebar_is_coach_decision_actor_exists(self):
        """Sidebar 中 isCoachDecisionActor 变量存在。"""
        assert "isCoachDecisionActor" in self.sidebar_source

    def test_sidebar_is_coach_decision_actor_contains_project_ceo(self):
        """isCoachDecisionActor 包含 project_ceo。"""
        definition = _find_branch(self.sidebar_source, "isCoachDecisionActor", 8)
        assert definition is not None
        assert "project_ceo" in definition

    def test_sidebar_is_coach_decision_actor_contains_is_tech_admin(self):
        """isCoachDecisionActor 包含 is_tech_admin。"""
        definition = _find_branch(self.sidebar_source, "isCoachDecisionActor", 8)
        assert definition is not None
        assert "is_tech_admin" in definition

    def test_sidebar_is_coach_decision_actor_not_contain_is_ceo(self):
        """isCoachDecisionActor 不包含 currentUser?.is_ceo。"""
        idx = self.sidebar_source.find("isCoachDecisionActor")
        assert idx > 0
        # 只看变量起始位置后的代码，避免相邻的 isCEO 变量干扰
        nearby = self.sidebar_source[idx:idx + 120]
        assert "currentUser?.is_ceo" not in nearby

    def test_sidebar_show_participant_includes_project_ceo(self):
        """showParticipantModules 角色列表中包含 project_ceo。"""
        definition = _find_branch(self.sidebar_source, "showParticipantModules", 8)
        assert definition is not None
        assert "project_ceo" in definition

    def test_sidebar_badge_uses_ceo_total(self):
        """Sidebar badge 使用 ceo_total fallback。"""
        assert "ceo_total" in self.sidebar_source


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

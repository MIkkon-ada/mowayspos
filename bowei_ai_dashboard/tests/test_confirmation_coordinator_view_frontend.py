"""N4-P3-FIX-1A: 前端语义测试 — 统筹反馈并入 AI 确认中心。

通过读取前端源码文件验证关键结构和分支。
"""
from __future__ import annotations

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read_tsx(filename: str) -> str:
    return (FRONTEND_DIR / filename).read_text(encoding="utf-8")


def _read_txt(filepath: str) -> str:
    return (FRONTEND_DIR / filepath).read_text(encoding="utf-8")


def _extract_function(source: str, func_name: str) -> str:
    """Extract the body of a named function from source code."""
    idx = source.find(f"function {func_name}")
    if idx < 0:
        return ""
    brace_idx = source.index("{", source.index("(", idx))
    depth = 1
    i = brace_idx + 1
    while depth > 0 and i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1
    return source[idx:i]


def _find_nth(source: str, pattern: str, n: int) -> int:
    """Find the nth occurrence (0-indexed) of pattern in source."""
    idx = -1
    for _ in range(n + 1):
        idx = source.find(pattern, idx + 1)
        if idx < 0:
            return -1
    return idx


# ── ConfirmPage.tsx ──────────────────────────────────────────────

class TestConfirmViewMode:
    """测试 ConfirmViewMode 类型定义包含 coordinator。"""

    def test_viewmode_type_includes_coordinator(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = source.find("type ConfirmViewMode")
        assert idx >= 0, "ConfirmViewMode 类型定义必须存在"
        snippet = source[idx:idx + 120]
        assert "'coordinator'" in snippet, (
            "ConfirmViewMode 类型定义必须包含 'coordinator'"
        )

    def test_viewmode_includes_ceo(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = source.find("type ConfirmViewMode")
        assert idx >= 0
        snippet = source[idx:idx + 120]
        assert "'ceo'" in snippet


class TestCoordinatorFeedbackImport:
    """测试导入关系。"""

    def test_coordinator_feedback_imported_from_api(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        import_section = source[:source.find("export function ConfirmPage")]
        assert "coordinatorFeedback" in import_section, (
            "coordinatorFeedback 必须在 import 区导入"
        )

    def test_transfer_coordinator_imported(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        import_section = source[:source.find("export function ConfirmPage")]
        assert "transferCoordinator" in import_section


class TestCanUseCoordinatorView:
    """测试 canUseCoordinatorView 权限判断。"""

    def _get_definition(self) -> str:
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = source.find("canUseCoordinatorView")
        assert idx >= 0, "canUseCoordinatorView 必须存在"
        return source[idx:idx + 400]

    def test_includes_coordinator_role(self):
        snippet = self._get_definition()
        assert "includes('coordinator')" in snippet

    def test_includes_tech_admin(self):
        snippet = self._get_definition()
        assert "is_tech_admin" in snippet

    def test_excludes_is_ceo(self):
        snippet = self._get_definition()
        assert "is_ceo" not in snippet

    def test_excludes_can_view_all(self):
        snippet = self._get_definition()
        assert "can_view_all" not in snippet

    def test_excludes_owner_role(self):
        snippet = self._get_definition()
        assert ".includes('owner')" not in snippet

    def test_excludes_project_ceo_role(self):
        snippet = self._get_definition()
        assert ".includes('project_ceo')" not in snippet


class TestCoordinatorUITab:
    """测试"待我统筹"入口和条件渲染。"""

    def test_tab_button_exists(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "待我统筹" in source

    def test_switch_view_coordinator_call(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "switchView('coordinator')" in source

    def test_tab_guarded_by_can_use(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx_btn = source.find("待我统筹")
        assert idx_btn >= 0
        # 向上搜索更大范围（JSX 元素跨度可能很大）
        before = source[max(0, idx_btn - 500):idx_btn]
        assert "canUseCoordinatorView" in before, (
            "「待我统筹」按钮必须在 canUseCoordinatorView 条件内"
        )

    def test_coordinator_tab_between_all_and_ceo(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx_all = source.find("switchView('all')")
        idx_coord = source.find("switchView('coordinator')")
        idx_ceo = source.find("switchView('ceo')")
        assert idx_all < idx_coord < idx_ceo, (
            f"按钮顺序错误: all@{idx_all} coordinator@{idx_coord} ceo@{idx_ceo}"
        )


class TestDeepLinkFilterSync:
    """测试 viewMode → filterStatus 同步 effect。"""

    def _find_filter_sync_use_effect(self, source: str) -> int:
        """返回依赖 viewMode 且调用 setFilterStatus('') 的 useEffect 起始位置。"""
        import re
        for m in re.finditer(r"useEffect\(\(\)\s*=>\s*\{", source):
            j = source.index("{", m.end())
            brace_depth = 1
            while brace_depth > 0 and j < len(source) - 1:
                j += 1
                if source[j] == "{":
                    brace_depth += 1
                elif source[j] == "}":
                    brace_depth -= 1
            dep_start = source.index("[", j)
            dep_end = source.index("]", dep_start) + 1
            dep_array = source[dep_start:dep_end]
            if "viewMode" in dep_array:
                body = source[m.start():dep_end]
                if "setFilterStatus('')" in body:
                    return m.start()
        return -1

    def test_effect_syncs_filter_status(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = self._find_filter_sync_use_effect(source)
        assert idx >= 0, (
            "必须存在一个 useEffect 依赖 viewMode 并调用 setFilterStatus('')"
        )

    def test_filter_sync_not_only_in_switch_view(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        switch_body = _extract_function(source, "switchView")
        assert switch_body, "switchView 函数必须存在"
        assert "setFilterStatus('')" in switch_body
        # 同时验证有独立 useEffect 做同样的事
        idx = self._find_filter_sync_use_effect(source)
        assert idx >= 0, (
            "除 switchView 外，必须存在独立的 useEffect(viewMode) 同步 filterStatus"
        )

    def test_ceo_view_also_clears_filter(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = self._find_filter_sync_use_effect(source)
        assert idx >= 0
        region = source[idx:idx + 200]
        assert "viewMode === 'ceo'" in region, (
            "useEffect 中 ceo 视图同样必须清空 filterStatus"
        )


class TestCoordinatorDataLoading:
    """测试 coordinator 视图数据加载分支。"""

    def _find_data_loading_coordinator(self) -> tuple[str, int]:
        """找到数据加载 useEffect 中的 coordinator 分支。
        
        viewMode === 'coordinator' 出现在多处，数据加载分支是第3个(0-indexed)：
        0: isCoordinatorView 常量声明
        1: useEffect 中的 filter sync
        2: 数据加载 useEffect 中的 else if
        """
        source = _read_tsx("pages/ConfirmPage.tsx")
        # 实际运行时由于新增代码，需要动态定位：找到 useEffect 中数据加载区域
        # 策略：找到 else if (viewMode === 'coordinator') 模式
        pattern = "else if (viewMode === 'coordinator')"
        idx = source.find(pattern)
        if idx < 0:
            # 回退：找 viewMode === 'coordinator' 且上下文中包含 getPending
            for start in range(0, len(source)):
                pos = source.find("viewMode === 'coordinator'", start)
                if pos < 0:
                    break
                region = source[pos:pos + 1200]
                if "getPending(" in region:
                    return source, pos
                start = pos + 1
        return source, idx

    def test_coordinator_branch_calls_get_pending(self):
        source, idx = self._find_data_loading_coordinator()
        assert idx >= 0, "找不到 coordinator 数据加载分支"
        region = source[idx:idx + 1200]
        assert "getPending(" in region, (
            "coordinator 数据加载分支必须调用 getPending"
        )
        assert "'coordinator'" in region, (
            "coordinator 分支必须传入 'coordinator' 作为 tab 参数"
        )

    def test_coordinator_branch_uses_url_submission_id(self):
        source, idx = self._find_data_loading_coordinator()
        assert idx >= 0
        region = source[idx:idx + 1200]
        assert "urlSubmissionId" in region

    def test_coordinator_branch_finds_target_by_id(self):
        source, idx = self._find_data_loading_coordinator()
        assert idx >= 0
        region = source[idx:idx + 1200]
        assert ".find(" in region or "d.find(" in region

    def test_coordinator_branch_calls_pick_item(self):
        source, idx = self._find_data_loading_coordinator()
        assert idx >= 0
        region = source[idx:idx + 1200]
        assert "pickItem(" in region

    def test_clear_status_filter_not_only_switch_view(self):
        """深链不清空筛选的实现错误时必须检测失败。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        found = TestDeepLinkFilterSync._find_filter_sync_use_effect(
            TestDeepLinkFilterSync(), source
        )
        assert found >= 0, (
            "必须存在独立的 useEffect([viewMode]) 调用 setFilterStatus('')"
        )


class TestPickItemCoordinatorIsolation:
    """测试 pickItem 清空所有状态包括 coordinator。"""

    def test_pick_item_clears_coordinator_note(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        pick_body = _extract_function(source, "pickItem")
        assert pick_body, "pickItem 函数必须存在"
        assert "setCoordinatorNote('')" in pick_body

    def test_pick_item_does_not_clear_coordinator_acting(self):
        """pickItem 不得主动解锁 coordinatorActing，解锁权在 handleCoordinatorFeedback finally。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        pick_body = _extract_function(source, "pickItem")
        assert "setCoordinatorActing(false)" not in pick_body, (
            "pickItem 不得调用 setCoordinatorActing(false)；"
            "解锁只能由 handleCoordinatorFeedback 的 finally 完成"
        )

    def test_pick_item_clears_action_note(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        pick_body = _extract_function(source, "pickItem")
        assert "setActionNote('')" in pick_body

    def test_pick_item_clears_coach_note(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        pick_body = _extract_function(source, "pickItem")
        assert "setCoachNote('')" in pick_body

    def test_pick_item_clears_action_error(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        pick_body = _extract_function(source, "pickItem")
        assert "setActionError(null)" in pick_body

    def test_pick_item_clears_action_success(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        pick_body = _extract_function(source, "pickItem")
        assert "setActionSuccess(null)" in pick_body


class TestCoordinatorFeedbackHandler:
    """测试 handleCoordinatorFeedback 处理函数。"""

    def test_handler_calls_coordinator_feedback_api(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        handler_body = _extract_function(source, "handleCoordinatorFeedback")
        assert handler_body, "handleCoordinatorFeedback 函数必须存在"
        assert "coordinatorFeedback(" in handler_body

    def test_handler_checks_note_not_empty(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        handler_body = _extract_function(source, "handleCoordinatorFeedback")
        assert "coordinatorNote.trim()" in handler_body

    def test_handler_sets_acting_state(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        handler_body = _extract_function(source, "handleCoordinatorFeedback")
        assert "setCoordinatorActing(true)" in handler_body
        assert "setCoordinatorActing(false)" in handler_body

    def test_handler_reloads_after_success(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        handler_body = _extract_function(source, "handleCoordinatorFeedback")
        assert "reloadCoordinatorItems()" in handler_body

    def test_handler_clears_note_after_success(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        handler_body = _extract_function(source, "handleCoordinatorFeedback")
        api_idx = handler_body.find("coordinatorFeedback(")
        clear_idx = handler_body.find("setCoordinatorNote('')", api_idx)
        assert clear_idx > api_idx

    def test_empty_note_disabled_on_button(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "coordinatorActing || !coordinatorNote.trim()" in source


class TestReloadCoordinatorItems:
    """测试 reloadCoordinatorItems 使用 pickItem。"""

    def test_reload_coordinator_items_exists(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "function reloadCoordinatorItems" in source

    def test_reload_uses_pick_item(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        body = _extract_function(source, "reloadCoordinatorItems")
        assert "pickItem(" in body

    def test_reload_not_direct_set_selected_for_next(self):
        """直接 setSelected 会导致状态不完整初始化。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        body = _extract_function(source, "reloadCoordinatorItems")
        set_sel_count = body.count("setSelected(")
        assert set_sel_count <= 1, (
            f"reloadCoordinatorItems 中 setSelected 仅允许 1 次（空列表），"
            f"实际 {set_sel_count} 次"
        )


class TestCoordinatorSuccessMessage:
    """测试成功提示消息。"""

    def test_success_message(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        handler_body = _extract_function(source, "handleCoordinatorFeedback")
        assert "统筹意见已提交，事项已返回项目负责人。" in handler_body


class TestCoordinatorViewIsolation:
    """测试 coordinator 视图不显示 owner/coach 操作区域。"""

    def _get_feedback_section(self) -> tuple[str, int]:
        """定位 coordinator 反馈 UI section。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = source.find("提供统筹意见")
        return source, idx

    def test_coordinator_feedback_section_exists(self):
        _, idx = self._get_feedback_section()
        assert idx >= 0, "必须存在「提供统筹意见」section"

    def test_coordinator_section_shows_transfer_note(self):
        source, idx = self._get_feedback_section()
        assert idx >= 0
        # 获取足够大的区域覆盖整个 section
        region = source[idx:idx + 3000]
        assert "负责人转交说明" in region

    def test_coordinator_section_shows_submitter(self):
        source, idx = self._get_feedback_section()
        assert idx >= 0
        region = source[idx:idx + 3000]
        assert "提交人" in region

    def test_coordinator_section_shows_submit_time(self):
        source, idx = self._get_feedback_section()
        assert idx >= 0
        region = source[idx:idx + 3000]
        assert "提交时间" in region

    def _get_card_modal_coordinator(self):
        """定位任务卡弹窗底部 JSX 中 viewMode === 'coordinator' 分支。
        
        策略：找到任务卡弹窗 JSX 区域（{cardDetailOpen && ...），
        然后在该区域内搜索 coordinator 条件分支。
        """
        source = _read_tsx("pages/ConfirmPage.tsx")
        # cardDetailOpen 在 state 声明和 JSX 中都有，需要找 JSX 区域
        # 使用弹窗特有的标记："cardDetailOpen && activeCard && activeReviewCard"
        idx_modal = source.find("cardDetailOpen && activeCard && activeReviewCard")
        assert idx_modal >= 0, "任务卡弹窗 JSX 必须存在"
        # 从弹窗区域内搜索 coordinator 分支
        idx_coord = source.find("viewMode === 'coordinator'", idx_modal)
        assert idx_coord >= 0, "弹窗底部必须有 coordinator 分支"
        idx_all = source.find("viewMode === 'all'", idx_coord)
        assert idx_all > idx_coord, "coordinator 分支后必须有 all 分支"
        return source, idx_coord, idx_all

    def test_coordinator_modal_before_all_in_chain(self):
        """任务卡弹窗底部条件链中 coordinator 分支必须在 all 之前判断。"""
        _, idx_coord, idx_all = self._get_card_modal_coordinator()
        assert idx_coord < idx_all, (
            "条件链中 coordinator 判断必须在 all 之前"
        )

    def test_coordinator_modal_no_handle_task_card_decision(self):
        source, idx_coord, idx_all = self._get_card_modal_coordinator()
        region = source[idx_coord:idx_all]
        assert "handleTaskCardDecision" not in region

    def test_coordinator_modal_no_confirm_入库(self):
        source, idx_coord, idx_all = self._get_card_modal_coordinator()
        region = source[idx_coord:idx_all]
        assert "确认入库" not in region

    def test_coordinator_modal_no_退回(self):
        source, idx_coord, idx_all = self._get_card_modal_coordinator()
        region = source[idx_coord:idx_all]
        assert "退回并重新编辑" not in region

    def test_coordinator_modal_no_transfer_coordinator_button(self):
        source, idx_coord, idx_all = self._get_card_modal_coordinator()
        region = source[idx_coord:idx_all]
        assert "转交统筹人" not in region

    def test_coordinator_modal_no_企业教练_button(self):
        source, idx_coord, idx_all = self._get_card_modal_coordinator()
        region = source[idx_coord:idx_all]
        assert "转交企业教练" not in region

    def test_coordinator_note_textarea_exists(self):
        source, idx = self._get_feedback_section()
        assert idx >= 0
        region = source[idx:idx + 4000]
        assert "setCoordinatorNote" in region

    def test_coordinator_submit_feedback_button_exists(self):
        source, idx = self._get_feedback_section()
        assert idx >= 0
        region = source[idx:idx + 4000]
        assert "提交反馈" in region


class TestCoordinatorEmptyState:
    """测试空状态文本。"""

    def test_empty_text(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "暂无待你反馈的统筹事项" in source


class TestCoordinatorHeaderText:
    """测试标题和说明文案。"""

    def test_header_description(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "处理项目负责人转交的统筹意见事项。" in source

    def test_left_panel_title(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "待我统筹" in source


class TestCoordinatorInteractionLock:
    """测试 coordinator 视图异步交互锁守卫。"""

    def test_coordinator_interaction_locked_variable(self):
        """coordinatorInteractionLocked 派生变量必须存在。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "coordinatorInteractionLocked" in source, (
            "必须定义 coordinatorInteractionLocked 派生变量"
        )
        idx = source.find("coordinatorInteractionLocked")
        region = source[idx:idx + 100]
        assert "isCoordinatorView" in region
        assert "coordinatorActing" in region

    def test_switch_view_guards_coordinator_acting(self):
        """switchView 函数开头必须包含互动锁守卫。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        switch_body = _extract_function(source, "switchView")
        assert switch_body, "switchView 函数必须存在"
        assert "isCoordinatorView" in switch_body
        assert "coordinatorActing" in switch_body
        # 守卫必须是 switchView 内的第一行逻辑
        guard_idx = switch_body.find("isCoordinatorView && coordinatorActing")
        set_view_idx = switch_body.find("setViewMode(nextView)")
        assert guard_idx >= 0, "switchView 必须包含 isCoordinatorView && coordinatorActing 守卫"
        assert guard_idx < set_view_idx, (
            "互动锁守卫必须在 setViewMode 之前"
        )

    def test_view_switcher_buttons_disabled(self):
        """所有 view switcher 按钮必须设置 disabled={coordinatorInteractionLocked}。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        # 四个按钮的 switchView 调用
        buttons = [
            "switchView('mine')",
            "switchView('all')",
            "switchView('coordinator')",
            "switchView('ceo')",
        ]
        for btn in buttons:
            idx = source.find(btn)
            assert idx >= 0, f"找不到 {btn} 按钮"
            # disabled 在 onClick 之后、className 之前，扩大搜索范围
            after = source[idx:idx + 250]
            assert "disabled={coordinatorInteractionLocked}" in after, (
                f"{btn} 按钮缺少 disabled={{coordinatorInteractionLocked}}"
            )

    def test_list_item_click_guard(self):
        """列表项 onClick 必须包含 coordinatorActing 守卫。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        # 列表项 onClick 中是第 3 次出现（0: 变量声明, 1: switchView, 2: 列表项onClick）
        idx = _find_nth(source, "isCoordinatorView && coordinatorActing", 2)
        assert idx >= 0, (
            "列表项 onClick 中未找到 isCoordinatorView && coordinatorActing 守卫"
        )
        # 验证上下文在 onClick 处理器中
        region = source[idx:idx + 80]
        assert "return" in region, "守卫必须包含 return 语句"

    def test_coordinator_textarea_disabled(self):
        """coordinator 反馈 textarea 必须设置 disabled={coordinatorActing}。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        # 找到 "提供统筹意见" section 附近的 textarea
        idx_fb = source.find("提供统筹意见")
        assert idx_fb >= 0
        region = source[idx_fb:idx_fb + 3500]
        # 找到 coordinatorNote 的 textarea
        ta_idx = region.find("coordinatorNote")
        assert ta_idx >= 0
        ta_region = region[ta_idx:ta_idx + 400]
        assert "disabled={coordinatorActing}" in ta_region, (
            "统筹反馈 textarea 必须设置 disabled={{coordinatorActing}}"
        )


# ── Sidebar.tsx ──────────────────────────────────────────────────

class TestSidebarBadge:
    """测试 Sidebar badge 包含 coordinator_total。"""

    def test_badge_includes_coordinator_total(self):
        source = _read_tsx("components/Sidebar.tsx")
        assert "coordinator_total" in source

    def test_set_confirm_badge_exists(self):
        source = _read_tsx("components/Sidebar.tsx")
        assert "setConfirmBadge" in source


# ── confirmations.ts API ─────────────────────────────────────────

class TestConfirmationAPI:
    """测试 API 层 coordinatorFeedback 函数。"""

    def test_coordinator_feedback_api_exists(self):
        source = _read_tsx("api/confirmations.ts")
        assert "coordinatorFeedback" in source

    def test_coordinator_feedback_route(self):
        source = _read_tsx("api/confirmations.ts")
        assert "coordinator-feedback" in source

    def test_transfer_coordinator_route(self):
        source = _read_tsx("api/confirmations.ts")
        assert "transfer-coordinator" in source

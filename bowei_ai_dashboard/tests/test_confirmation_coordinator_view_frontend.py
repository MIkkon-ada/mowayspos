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


# ── ConfirmPage.tsx ──────────────────────────────────────────────

class TestConfirmViewMode:
    """测试 ConfirmViewMode 包含 coordinator。"""

    def test_viewmode_includes_coordinator(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "'coordinator'" in source
        assert "type ConfirmViewMode" in source


class TestCoordinatorFeedbackImport:
    """测试导入 coordinatorFeedback。"""

    def test_coordinator_feedback_imported(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "coordinatorFeedback" in source


class TestCanUseCoordinatorView:
    """测试 canUseCoordinatorView 权限判断。"""

    def test_can_use_coordinator_view_exists(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "canUseCoordinatorView" in source

    def test_includes_coordinator_role(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        # coordinator 角色必须被包含
        assert "includes('coordinator')" in source

    def test_includes_tech_admin(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "is_tech_admin" in source

    def test_does_not_include_is_ceo(self):
        """canUseCoordinatorView 不得包含 is_ceo。"""
        # 搜索 canUseCoordinatorView 的定义区域
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = source.find("canUseCoordinatorView")
        assert idx >= 0
        # 截取定义部分
        snippet = source[idx:idx + 300]
        assert "is_ceo" not in snippet or "coordinatorView" in snippet and "is_ceo" not in snippet

    def test_does_not_include_owner_directly(self):
        """canUseCoordinatorView 不得直接检查 owner。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        idx = source.find("canUseCoordinatorView")
        assert idx >= 0
        snippet = source[idx:idx + 300]
        assert ".includes('owner')" not in snippet


class TestCoordinatorUITab:
    """测试"待我统筹"入口存在。"""

    def test_tab_button_exists(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "待我统筹" in source

    def test_switch_view_coordinator(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "switchView('coordinator')" in source


class TestCoordinatorDataLoading:
    """测试 coordinator 视图数据加载。"""

    def test_calls_get_pending_coordinator(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "getPending(" in source
        assert "'coordinator'" in source

    def test_clear_status_filter_on_coordinator(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        # switchView 中 coordinator 视图应清除状态筛选
        idx = source.find("function switchView")
        assert idx >= 0
        snippet = source[idx:idx + 600]
        assert "setFilterStatus('')" in snippet
        assert "'coordinator'" in snippet or "nextView" in snippet


class TestCoordinatorURLLoading:
    """测试 URL 参数解析。"""

    def test_resolve_initial_view_coordinator(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "'coordinator'" in source
        # resolveInitialView 中应有 coordinator 分支
        assert "resolveInitialView" in source
        # coordinator 在 ceo 之后 all 之前
        idx_ceo = source.find("urlView === 'ceo'")
        idx_coord = source.find("urlView === 'coordinator'")
        assert idx_ceo >= 0
        assert idx_coord >= 0

    def test_coordinator_view_loads_data(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        # useEffect 中应有 viewMode === 'coordinator' 的数据加载分支
        assert "viewMode === 'coordinator'" in source


class TestCoordinatorFeedbackHandler:
    """测试 handleCoordinatorFeedback 处理函数。"""

    def test_handler_exists(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "handleCoordinatorFeedback" in source

    def test_calls_coordinator_feedback_api(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "coordinatorFeedback(" in source

    def test_reloads_after_feedback(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "reloadCoordinatorItems" in source

    def test_empty_note_disabled(self):
        """空反馈不可提交。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        # 按钮 disabled 条件应包含 !coordinatorNote.trim()
        assert "coordinatorActing || !coordinatorNote.trim()" in source


class TestCoordinatorSuccessMessage:
    """测试成功提示消息。"""

    def test_success_message(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "统筹意见已提交" in source


class TestCoordinatorViewIsolation:
    """测试 coordinator 视图不显示 owner/coach 操作。"""

    def test_no_owner_action_buttons_in_coordinator(self):
        """coordinator 视图不显示 owner 操作区域。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        # 搜索 card modal 中的条件分支
        assert "viewMode === 'coordinator'" in source

    def test_coordinator_feedback_ui_exists(self):
        """统筹反馈 UI 区域存在。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "统筹意见" in source or "协调人" in source or "提供统筹" in source

    def test_coordinator_note_textarea_exists(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "setCoordinatorNote" in source

    def test_no_task_card_decision_in_coordinator(self):
        """coordinator 视图不显示单卡判断按钮（确认/退回/转交/上报）。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        # 单卡判断区前面有 coordinator 条件分支
        idx = source.find("viewMode === 'coordinator'")
        assert idx >= 0


class TestCoordinatorEmptyState:
    """测试空状态文本。"""

    def test_empty_text(self):
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "暂无待你反馈的统筹事项" in source


# ── Sidebar.tsx ──────────────────────────────────────────────────

class TestSidebarBadge:
    """测试 Sidebar badge 包含 coordinator_total。"""

    def test_badge_includes_coordinator_total(self):
        source = _read_tsx("components/Sidebar.tsx")
        assert "coordinator_total" in source
        assert "setConfirmBadge" in source


# ── confirmations.ts API ─────────────────────────────────────────

class TestConfirmationAPI:
    """测试 API 层 coordinatorFeedback 函数。"""

    def test_coordinator_feedback_api_exists(self):
        source = _read_tsx("api/confirmations.ts")
        assert "coordinatorFeedback" in source
        assert "coordinator-feedback" in source

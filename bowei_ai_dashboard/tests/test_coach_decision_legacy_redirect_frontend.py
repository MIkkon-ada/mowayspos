"""N4-P2-R: 旧企业教练决策中心 URL 兼容重定向结构测试。

验证旧 URL 路由已改为兼容跳转，保留查询参数，不使用权限判断提权。
"""
from __future__ import annotations

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read_tsx(filename: str) -> str:
    return (FRONTEND_DIR / filename).read_text(encoding="utf-8")


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


# ════════════════════════════════════════════════════════════════════
# 工作区旧 URL 重定向
# ════════════════════════════════════════════════════════════════════

class TestWorkDecisionsRedirect:
    """/work/decisions → /work/confirmations?view=ceo"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("app/routes.tsx")

    def test_legacy_redirect_component_exists(self):
        """LegacyCoachDecisionRedirect 组件定义存在。"""
        assert "function LegacyCoachDecisionRedirect" in self.source

    def test_redirect_block_contains_confirmations(self):
        """redirect 组件代码中包含 /work/confirmations。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "/work/confirmations" in block

    def test_redirect_block_sets_view_ceo(self):
        """redirect 组件强制设置 view=ceo。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "view" in block
        assert "'ceo'" in block or '"ceo"' in block

    def test_redirect_block_uses_url_search_params(self):
        """redirect 组件使用 new URLSearchParams(location.search)。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "new URLSearchParams" in block
        assert "location.search" in block

    def test_redirect_block_uses_replace(self):
        """redirect 组件使用 Navigate replace。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "replace" in block

    def test_work_decisions_route_uses_redirect(self):
        """/work/decisions 路由使用 LegacyCoachDecisionRedirect。"""
        block = _find_branch(self.source, 'path="decisions"', 2)
        assert block is not None
        assert "LegacyCoachDecisionRedirect" in block


# ════════════════════════════════════════════════════════════════════
# 项目旧 URL 重定向
# ════════════════════════════════════════════════════════════════════

class TestProjectDecisionsRedirect:
    """/project/:projectId/decisions → /work/confirmations?view=ceo&projectId=:projectId"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("app/routes.tsx")

    def test_project_decisions_route_uses_redirect(self):
        """/project/:projectId/decisions 使用 LegacyCoachDecisionRedirect。"""
        second = None
        idx = -1
        for _ in range(2):
            idx = self.source.find('path="decisions"', idx + 1)
            if idx < 0:
                break
            second = self.source[idx:idx + 200]
        assert second is not None
        assert "LegacyCoachDecisionRedirect" in second

    def test_redirect_block_sets_project_id(self):
        """redirect 组件在 projectId 存在时设置 projectId。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "projectId" in block
        # 检查 params.set('projectId', ...) 或类似模式
        assert "params.set" in block


# ════════════════════════════════════════════════════════════════════
# 参数保留
# ════════════════════════════════════════════════════════════════════

class TestQueryParameterPreservation:
    """旧 URL 查询参数保留。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("app/routes.tsx")

    def test_uses_url_search_params_not_manual(self):
        """使用 URLSearchParams 而非手写字符串拼接。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "new URLSearchParams" in block

    def test_params_from_location_search(self):
        """URLSearchParams 初始化自 location.search。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "URLSearchParams(location.search)" in block

    def test_params_to_string(self):
        """使用 params.toString() 序列化参数。"""
        block = _find_branch(self.source, "LegacyCoachDecisionRedirect", 25)
        assert block is not None
        assert "params.toString()" in block


# ════════════════════════════════════════════════════════════════════
# 无权限不提权
# ════════════════════════════════════════════════════════════════════

class TestNoPermissionElevation:
    """redirect 组件不做权限判断，不提权。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("app/routes.tsx")

    @staticmethod
    def _get_redirect_body(source: str) -> str:
        """提取 LegacyCoachDecisionRedirect 函数体（不含前后干扰函数）。"""
        start = source.find("function LegacyCoachDecisionRedirect")
        if start < 0:
            return ""
        next_func = source.find("function AppRoutes", start)
        if next_func < 0:
            next_func = source.find("type SetupState", start)
        if next_func < 0:
            return source[start:]
        return source[start:next_func]

    def test_redirect_has_no_is_ceo_check(self):
        """redirect 组件不判断 is_ceo。"""
        body = self._get_redirect_body(self.source)
        assert len(body) > 50
        assert "is_ceo" not in body

    def test_redirect_has_no_project_ceo_check(self):
        """redirect 组件不判断 project_ceo。"""
        body = self._get_redirect_body(self.source)
        assert len(body) > 50
        assert "project_ceo" not in body

    def test_redirect_has_no_capability_set(self):
        """redirect 组件不设置任何能力字段。"""
        body = self._get_redirect_body(self.source)
        assert len(body) > 50
        capability_words = ["canView", "canUse", "canConfirm"]
        assert not any(w in body for w in capability_words)

    def test_confirm_page_still_controls_permission(self):
        """ConfirmPage 仍通过 canUseCoachDecisionView 控制权限。"""
        source = _read_tsx("pages/ConfirmPage.tsx")
        assert "canUseCoachDecisionView" in source
        # view=ceo 需要权限检查
        ceo_block = _find_branch(source, "viewMode === 'ceo'", 5)
        assert ceo_block is not None

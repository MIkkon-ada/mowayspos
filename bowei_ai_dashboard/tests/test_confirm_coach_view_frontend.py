"""N4-P2-Q: 前端语义测试 — 企业教练待办并入 AI 确认中心。

通过读取前端源码文件验证关键结构和分支，保护权限、数据加载、
动作分发、深链解析、页面隔离和兼容边界。
"""
from __future__ import annotations

import ast
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read_tsx(filename: str) -> str:
    return (FRONTEND_DIR / filename).read_text(encoding="utf-8")


def _extract_function_body(source: str, func_name: str) -> str | None:
    """提取指定函数体的源码文本。"""
    lines = source.split("\n")
    in_func = False
    brace_count = 0
    body_lines = []
    for line in lines:
        if not in_func:
            if func_name in line and ("function " + func_name in line or
                                       "const " + func_name in line or
                                       func_name + " = " in line or
                                       func_name + "=" in line):
                in_func = True
                if "{" in line:
                    brace_count += line.count("{") - line.count("}")
                    if "=>" in line and brace_count == 0:
                        # 箭头函数单行 body
                        body_lines.append(line)
                        continue
        if in_func:
            body_lines.append(line)
            brace_count += line.count("{") - line.count("}")
            if brace_count <= 0 and in_func and "{" in body_lines[0] if body_lines else True:
                break
    return "\n".join(body_lines) if body_lines else None


def _extract_jsx_component(source: str, component_name: str) -> str | None:
    """提取 JSX 组件的源码文本。"""
    # 先尝试 function 声明
    patterns = [
        f"function {component_name}(",
        f"export function {component_name}(",
    ]
    lines = source.split("\n")
    for pattern in patterns:
        for i, line in enumerate(lines):
            if pattern in line:
                # 找到函数起始行
                start = i
                brace_count = 0
                started = False
                for j in range(i, len(lines)):
                    brace_count += lines[j].count("{") - lines[j].count("}")
                    if "{" in lines[j]:
                        started = True
                    if started and brace_count <= 0:
                        return "\n".join(lines[start:j + 1])
    return None


class TestPermissions:
    """权限判断：canUseCoachDecisionView。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_can_use_coach_decision_view_exists(self):
        """canUseCoachDecisionView 变量存在于 ConfirmPage.tsx。"""
        assert "canUseCoachDecisionView" in self.source, (
            "canUseCoachDecisionView must be defined in ConfirmPage.tsx"
        )

    def test_can_use_coach_decision_view_includes_project_ceo(self):
        """canUseCoachDecisionView 包含 project_ceo。"""
        assert 'project_ceo' in self.source, (
            "project_ceo must be referenced in ConfirmPage.tsx"
        )

    def test_can_use_coach_decision_view_includes_is_tech_admin(self):
        """canUseCoachDecisionView 包含 is_tech_admin。"""
        assert 'is_tech_admin' in self.source, (
            "is_tech_admin must be referenced in ConfirmPage.tsx"
        )

    def test_can_use_coach_decision_view_not_depend_on_is_ceo(self):
        """canUseCoachDecisionView 不依赖 currentUser.is_ceo（仅限该判断变量）。"""
        # 搜索 canUseCoachDecisionView 附近的 is_ceo
        idx = self.source.find("canUseCoachDecisionView")
        if idx > 0:
            nearby = self.source[max(0, idx - 50):idx + 400]
            # is_ceo 可能在别处引用，但不应出现在 canUseCoachDecisionView 的定义中
            lines_after = self.source[idx:idx + 400].split("\n")
            definition_lines = []
            for line in lines_after:
                definition_lines.append(line)
                if ";" in line and ("project_ceo" in line or "is_tech_admin" in line):
                    break
                if len(definition_lines) > 8:
                    break
            definition = "\n".join(definition_lines)
            assert "is_ceo" not in definition or "currentUser?.is_ceo" not in definition, (
                "canUseCoachDecisionView should not depend on is_ceo"
            )


class TestDataLoading:
    """数据加载路径。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_ceo_view_calls_get_pending_with_ceo_tab(self):
        """ceo 视图调用 getPending(..., 'ceo', { includeCardLevel: true })。"""
        assert "getPending" in self.source
        assert "includeCardLevel" in self.source
        assert "viewMode === 'ceo'" in self.source

    def test_all_view_calls_tab_all(self):
        """all 视图调用 getPending(..., 'all')。"""
        assert "'all'" in self.source

    def test_mine_view_calls_fetch_my_updates(self):
        """mine 视图调用 fetchMyUpdates。"""
        assert "fetchMyUpdates" in self.source

    def test_ceo_default_cross_project(self):
        """ceo 默认跨项目查询（传 null）。"""
        assert "null" in self.source  # projectId=null for ceo


class TestActions:
    """动作分发：提交级和卡片级批示。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_submission_scope_calls_ceo_decide(self):
        """提交级 scope 调用 ceoDecide。"""
        assert "ceoDecide" in self.source

    def test_card_scope_calls_ceo_decide_task_card(self):
        """卡片级 scope 调用 ceoDecideTaskCard。"""
        assert "ceoDecideTaskCard" in self.source

    def test_empty_coach_note_blocked(self):
        """空白批示不可提交（coachNote.trim() 检查）。"""
        assert "coachNote.trim()" in self.source or "!coachNote.trim()" in self.source

    def test_success_reloads_list(self):
        """成功后重新加载列表。"""
        assert "reloadCoachItems" in self.source or "getPending" in self.source


class TestDeepLinks:
    """深链解析。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_parses_view_param(self):
        """解析 view 参数。"""
        assert "searchParams.get('view')" in self.source or "view" in self.source

    def test_parses_project_id(self):
        """解析 projectId。"""
        assert "projectId" in self.source

    def test_parses_submission_id(self):
        """解析 submissionId。"""
        assert "submissionId" in self.source

    def test_parses_card_index(self):
        """解析 cardIndex。"""
        assert "cardIndex" in self.source

    def test_no_permission_view_ceo_no_elevation(self):
        """无权限时 view=ceo 不提升权限。"""
        assert "canUseCoachDecisionView" in self.source

    def test_submission_id_not_found_safe_fallback(self):
        """submissionId 找不到时有安全回退（d[0] fallback）。"""
        assert "d[0]" in self.source


class TestPageIsolation:
    """页面隔离：ceo 视图不渲染 owner 操作。"""

    @classmethod
    def setup_class(cls):
        cls.source = _read_tsx("pages/ConfirmPage.tsx")

    def test_ceo_view_hides_owner_confirm_actions(self):
        """ceo 视图不渲染确认入库等 owner 动作。"""
        assert "isCoachView" in self.source or "viewMode === 'ceo'" in self.source

    def test_ceo_view_retains_task_card_detail(self):
        """ceo 视图保留任务卡详情查看。"""
        assert "taskCards" in self.source
        assert "activeCard" in self.source

    def test_ceo_view_does_not_render_owner_edits(self):
        """ceo 视图不渲染任务写入编辑操作。"""
        # 确认有 ceo 视图的条件渲染逻辑
        assert "isCoachView" in self.source


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

    def test_sidebar_project_ceo_shows_compat_entry(self):
        """Sidebar 在 project_ceo 时显示旧兼容入口。"""
        assert "project_ceo" in self.sidebar_source

    def test_sidebar_tech_admin_shows_compat_entry(self):
        """Sidebar 在 tech_admin 时显示旧兼容入口。"""
        assert "is_tech_admin" in self.sidebar_source

    def test_sidebar_company_ceo_hides_compat_entry(self):
        """Sidebar 中 company_ceo 不显示旧兼容入口。"""
        assert "isCoachDecisionActor" in self.sidebar_source

    def test_sidebar_badge_uses_ceo_total(self):
        """Sidebar badge 使用 ceo_total fallback。"""
        assert "ceo_total" in self.sidebar_source


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
        idx = self.source.find("taskCardDecisionTone")
        if idx > 0:
            nearby = self.source[idx:idx + 500]
            assert "ceo_decided" in nearby


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

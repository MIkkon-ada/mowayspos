from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_dashboard_supports_global_my_and_project_scopes():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "useSearchParams" in source
    assert "urlProjectId" in source
    assert "type DashboardScope = 'global' | 'my' | 'project'" in source
    assert "scopeMode" in source
    assert "hasProjectDashboardRole" in source


def test_dashboard_non_global_users_default_to_my_scope_not_project_selection():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "canViewGlobalDashboard" in source
    assert "return 'my'" in source
    assert "实时掌握我参与项目的进度、风险、成果与待决策事项" in source
    assert "shouldSelectProjectBeforeLoading" not in source


def test_dashboard_error_messages_distinguish_global_and_project_permission():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "你没有权限查看全局驾驶舱，请选择项目查看。" in source
    assert "你没有权限查看该项目驾驶舱。" in source
    assert "数据加载失败，请稍后重试。" in source
    assert "数据加载失败，请刷新页面重试" not in source


def test_dashboard_my_scope_fetches_each_project_without_global_overview():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "loadMyProjectDashboard" in source
    assert "Promise.allSettled" in source
    assert "projects.map((project) => getOverview(project.id, selectedMonth))" in source
    assert "console.warn('项目驾驶舱数据加载失败'" in source
    assert "暂无可查看的项目驾驶舱数据。" in source
    assert "getOverview(null, selectedMonth)" not in source


def test_dashboard_filter_keeps_dashboard_route_and_limits_global_option():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "canViewGlobalDashboard &&" in source
    assert "/home/dashboard?projectId=" in source
    assert "navigate('/home/dashboard')" in source
    assert "navigate(`/project/${id}`)" not in source
    assert "全部项目" in source
    assert "我的项目" in source
    assert '{canViewGlobalDashboard && <option value="global">全部项目</option>}' in source


def test_dashboard_export_is_guarded_by_my_scope_for_project_roles():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "请选择单个项目后导出周报；多项目周报将在后续聚合导出中支持。" in source
    assert "scopeMode === 'my'" in source
    export_index = source.index("await exportWeeklyReport(scopeMode === 'global' ? null : scopeId, selectedMonth)")
    my_guard_index = source.index("scopeMode === 'my'")
    assert my_guard_index < export_index


def test_sidebar_dashboard_entry_uses_dashboard_default_scope_for_project_roles():
    source = _frontend_source("components/Sidebar.tsx")

    assert "handleNavigate" in source
    assert "navigate('/home/dashboard')" in source
    assert "`/home/dashboard?projectId=${currentProjectId}`" not in source


def test_dashboard_scope_fix_does_not_expand_backend_or_forbidden_concepts():
    page_source = _frontend_source("pages/DashboardPage.tsx")
    sidebar_source = _frontend_source("components/Sidebar.tsx")
    backend_source = (Path(__file__).resolve().parents[1] / "app" / "routers" / "dashboard.py").read_text(encoding="utf-8")

    assert "def _require_global_read_scope" in backend_source
    assert "is_tech_admin" in backend_source
    assert "is_ceo" in backend_source
    for forbidden in ["Workstream", "workstream", "第四层", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in page_source
        assert forbidden not in sidebar_source

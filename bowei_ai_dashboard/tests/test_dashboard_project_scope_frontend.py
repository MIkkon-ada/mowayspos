from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_dashboard_initial_scope_uses_url_or_project_context_not_plain_null_default():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "useSearchParams" in source
    assert "urlProjectId" in source
    assert "initialDashboardScopeId" in source
    assert "const [scopeId, setScopeId] = useState<number | null>(null)" not in source


def test_dashboard_blocks_global_overview_for_project_roles_without_context():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "canViewGlobalDashboard" in source
    assert "shouldSelectProjectBeforeLoading" in source
    assert "请先选择项目后查看驾驶舱" in source
    assert "getOverview(null, selectedMonth)" not in source


def test_dashboard_error_messages_distinguish_global_and_project_permission():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "你没有权限查看全局驾驶舱，请选择项目查看。" in source
    assert "你没有权限查看该项目驾驶舱。" in source
    assert "数据加载失败，请稍后重试。" in source
    assert "数据加载失败，请刷新页面重试" not in source


def test_dashboard_filter_keeps_dashboard_route_and_limits_global_option():
    source = _frontend_source("pages/DashboardPage.tsx")

    assert "canViewGlobalDashboard &&" in source
    assert "/home/dashboard?projectId=" in source
    assert "navigate('/home/dashboard')" in source
    assert "navigate(`/project/${id}`)" not in source
    assert "<option value=\"\">全部专项</option>" not in source


def test_sidebar_dashboard_entry_carries_project_context_for_project_roles():
    source = _frontend_source("components/Sidebar.tsx")

    assert "currentProjectId" in source
    assert "canViewGlobalDashboard" in source
    assert "handleNavigate" in source
    assert "`/home/dashboard?projectId=${currentProjectId}`" in source


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

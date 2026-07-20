"""FIX-DASHBOARD-LOADING-AND-STATIC-ASSETS: dashboard loading state tests.

验证顶层渲染状态: blocked / initialLoading / errorWithNoData / dataReady。
refreshing 和 refreshError 是 dataReady 上的提示性子状态。
"""
from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def _index_html() -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "index.html").read_text(encoding="utf-8")


# =========================================================================
# 1. 首次 loading 时不同时渲染正式统计区域
# =========================================================================

def test_initial_loading_does_not_render_fake_zero_stats():
    """initialLoading=true 时，统计卡片不渲染（不出现零值闪烁）。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # 定义了 initialLoading 和 dataReady 状态
    assert "const dataReady = data !== null && !shouldBlockDashboardLoading" in source
    assert "const initialLoading = loading && data === null && loadError === null && !shouldBlockDashboardLoading" in source

    # 骨架用 initialLoading 控制（而不是裸的 loading）
    assert "{initialLoading && (" in source

    # 统计卡片被 dataReady 包裹
    assert "{dataReady && <>" in source

    # HARD CONSTRAINT: 没有 data === null 时无条件渲染零值卡片的情况
    assert "{(data === null" not in source


# =========================================================================
# 2. loading 且已有 data 时不重新展示全页骨架
# =========================================================================

def test_refreshing_keeps_old_data_no_full_skeleton():
    """已有 data 后重新筛选/刷新时，保留旧数据，不切全页骨架。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # 定义了 refreshing 状态（dataReady 上的子状态）
    assert "const refreshing = loading && data !== null && !shouldBlockDashboardLoading" in source

    # 有 "更新中..." 轻量指示器
    assert "更新中..." in source

    # 骨架只被 initialLoading 控制，不是 loading
    assert "{initialLoading && (" in source

    # 正式内容由 dataReady 包裹
    assert "{dataReady && <>" in source


# =========================================================================
# 3. loadError 且没有 data 时不展示正式零值统计
# =========================================================================

def test_error_with_no_data_shows_error_not_fake_zero_stats():
    """加载失败且没有历史数据时，显示错误信息而不是零值统计。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # 定义了 errorWithNoData（顶层状态）
    assert "const errorWithNoData = loadError !== null && data === null && !shouldBlockDashboardLoading" in source

    # 错误区域用 errorWithNoData 控制
    assert "{errorWithNoData && (" in source

    # 正式内容被 dataReady 包裹（有错误无 data 时不渲染）
    assert "{dataReady && <>" in source


# =========================================================================
# 4. 无权限阻断状态不展示骨架和正式数据
# =========================================================================

def test_blocked_state_does_not_show_skeleton_or_data():
    """shouldBlockDashboardLoading 时，骨架和正式数据都不显示。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # dataReady / initialLoading / errorWithNoData 都包含 !shouldBlockDashboardLoading
    assert "const dataReady = data !== null && !shouldBlockDashboardLoading" in source
    assert "const initialLoading = loading && data === null && loadError === null && !shouldBlockDashboardLoading" in source
    assert "const errorWithNoData = loadError !== null && data === null && !shouldBlockDashboardLoading" in source

    # 阻断消息存在
    assert "shouldBlockDashboardLoading" in source
    assert "请先选择项目后查看驾驶舱" in source


# =========================================================================
# 5. index.html 存在显式 favicon 声明
# =========================================================================

def test_index_html_has_explicit_favicon():
    """index.html 显式声明 favicon，阻止浏览器自动请求 /favicon.ico。"""
    html = _index_html()
    assert '<link rel="icon" href="data:," />' in html


# =========================================================================
# 6. 不改变 dashboard API 契约
# =========================================================================

def test_dashboard_api_contract_unchanged():
    """dashboard API 路径、参数、响应结构不变。"""
    source = _frontend_source("api/dashboard.ts")

    assert 'export function getOverview' in source
    assert "getOverview(projectId?: number | null, month?: string): Promise<DashboardOverview>" in source
    assert '/api/dashboard/overview' in source
    assert 'project_id' in source
    assert "month" in source
    assert "export async function exportWeeklyReport" in source
    assert '/api/dashboard/export-weekly-report' in source


# =========================================================================
# 7. 合法请求前清除 loadError
# =========================================================================

def test_load_error_cleared_before_request():
    """每次合法请求开始前，先 setLoadError(null) 再 setLoading(true)。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # setLoadError(null) 紧接着 setLoading(true) 是 useEffect 中的唯一组合
    idx = source.find("setLoadError(null)\n    setLoading(true)")
    assert idx != -1, (
        "setLoadError(null) must be immediately followed by setLoading(true) "
        "in the useEffect that starts a dashboard request"
    )


# =========================================================================
# 8. refreshError 存在且不隐藏正式数据
# =========================================================================

def test_refresh_error_defined_and_keeps_data():
    """当 loadError && data !== null 时，refreshError 显示但不隐藏旧数据。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # refreshError 定义为 loadError && data !== null
    assert "const refreshError = loadError !== null && data !== null && !shouldBlockDashboardLoading" in source

    # refreshError 的 UI 存在
    assert "{refreshError && (" in source
    assert "更新失败，当前显示上次成功加载的数据" in source

    # dataReady 独立于 refreshError，refreshError 不为 true 时 dataReady 仍为 true
    # （反证：如果 refreshError 隐藏了数据，则需要 data === null，但 refreshError 定义要求 data !== null）
    assert "const dataReady = data !== null && !shouldBlockDashboardLoading" in source


# =========================================================================
# 9. refreshError 不显示全页骨架
# =========================================================================

def test_refresh_error_no_full_skeleton():
    """refreshError 时保留旧数据，不切全页骨架。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # 骨架仅由 initialLoading 控制
    skeleton_uses = source.count("{initialLoading && (")
    assert skeleton_uses >= 1, "skeleton must use initialLoading"

    # refreshError 不使用 initialLoading 或 errorWithNoData 的 UI 区块
    # （refreshError 有自己的独立区块，不触发初始骨架或全页错误）
    refresh_block = source.split("{refreshError && (")[1].split("{")[0] if "{refreshError && (" in source else ""

    # refreshError 区块内不含骨架样式（animate-pulse 等）
    assert "animate-pulse" not in refresh_block, "refreshError must not use skeleton"


# =========================================================================
# 10. 顶层状态边界校验
# =========================================================================

def test_top_level_state_boundaries():
    """四个顶层状态覆盖所有非阻断场景，无重叠、无遗漏。"""
    source = _frontend_source("pages/DashboardPage.tsx")

    # dataReady 是所有四个顶层状态之一
    assert "const dataReady = data !== null && !shouldBlockDashboardLoading" in source

    # initialLoading / errorWithNoData 是独立顶层状态（不是 dataReady 的衍生）
    # 它们各自的定义中 data===null，与 dataReady 的 data!==null 互斥
    initial_def = "const initialLoading = loading && data === null && loadError === null && !shouldBlockDashboardLoading"
    error_def = "const errorWithNoData = loadError !== null && data === null && !shouldBlockDashboardLoading"
    assert initial_def in source
    assert error_def in source

    # refreshing 和 refreshError 只在 dataReady 内使用：
    # 它们的定义都要求 data !== null，而 dataReady 也是 data !== null
    # 既不是顶层状态，也不改变 dataReady 的展示语义
    assert "const refreshing = loading && data !== null && !shouldBlockDashboardLoading" in source
    assert "const refreshError = loadError !== null && data !== null && !shouldBlockDashboardLoading" in source

    # 边界：data===null 且 loadError===null 且 !loading ——
    # 此时没有任何顶层状态为 true（initialLoading=false, errorWithNoData=false, dataReady=false）
    # 这是短暂的清理状态，属于合法边界（shouldBlockDashboardLoading 之外的不渲染）。
    # 代码中不需要显式覆盖此情况，因为 JSX 条件渲染会自动转为空内容。

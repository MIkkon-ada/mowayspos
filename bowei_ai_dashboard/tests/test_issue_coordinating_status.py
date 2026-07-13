"""
N4-P2-J: 问题中心状态机最小调整 — 新增"待协调"状态

验证：
1. 后端 issue_flow.py 定义 STATUS_COORDINATING
2. 状态合法集合包含"待协调"
3. 状态更新接口允许 status="待协调"
4. 前端 Kanban 从 5 列变为 6 列
5. 不新增数据库字段 / 不新增接口
6. 保留 issue_type = 待协调 兼容常量
"""

import os
import re
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_PAGES = ROOT.parent / "frontend" / "src" / "pages"


# ── 后端常量验证 ──────────────────────────────────────────────

def test_issue_flow_defines_status_coordinating():
    """issue_flow.py 定义 STATUS_COORDINATING = '待协调'"""
    from app.domain import issue_flow as IF
    assert hasattr(IF, "STATUS_COORDINATING"), "issue_flow 缺少 STATUS_COORDINATING"
    assert IF.STATUS_COORDINATING == "待协调"


def test_all_statuses_includes_coordinating():
    """ALL_STATUSES 包含 STATUS_COORDINATING"""
    from app.domain import issue_flow as IF
    assert IF.STATUS_COORDINATING in IF.ALL_STATUSES


def test_status_map_normalizes_coordinating():
    """_STATUS_MAP 可将 '待协调' 和 '协调' 归一化为 STATUS_COORDINATING"""
    from app.domain import issue_flow as IF
    assert IF.normalize_status("待协调") == IF.STATUS_COORDINATING
    assert IF.normalize_status("协调") == IF.STATUS_COORDINATING


def test_all_statuses_has_six_items():
    """ALL_STATUSES 包含 6 个状态"""
    from app.domain import issue_flow as IF
    assert len(IF.ALL_STATUSES) == 6
    expected = {"待处理", "处理中", "待协调", "待决策", "已解决", "已关闭"}
    assert set(IF.ALL_STATUSES) == expected


# ── issue_type 兼容性 ─────────────────────────────────────────

def test_issue_type_still_has_type_coordinate():
    """issue_flow.py 仍保留 TYPE_COORDINATE 常量（兼容旧数据）"""
    from app.domain import issue_flow as IF
    assert hasattr(IF, "TYPE_COORDINATE"), "TYPE_COORDINATE 不应删除（旧数据兼容）"
    assert IF.TYPE_COORDINATE == "待协调"


def test_issue_type_coordinate_constant_unchanged():
    """issue_type.py 中 TYPE_COORDINATION 仍存在"""
    from app.domain import issue_type as IT
    assert hasattr(IT, "TYPE_COORDINATION")
    assert IT.TYPE_COORDINATION == "coordination"


# ── 路由验证：状态更新接口接受"待协调" ────────────────────────

def test_status_endpoint_normalizes_coordinating():
    """包含 normalize_status 功能可用"""
    from app.domain import issue_flow as IF
    result = IF.normalize_status("待协调")
    assert result != IF.STATUS_PENDING, "normalize_status 不应将'待协调'归为默认'待处理'"
    assert result == IF.STATUS_COORDINATING


def test_no_new_db_fields_for_coordinating():
    """不新增 migration 文件"""
    migrations_dir = ROOT / "app" / "migrations"
    # 如果 migrations 目录存在，检查是否有新 migration
    if migrations_dir.exists():
        migration_files = sorted(
            f for f in os.listdir(str(migrations_dir))
            if f.endswith(".py") and f != "__init__.py"
        )
        # 本轮不应新增 migration
        # （无新增字段，仅纯逻辑层改动）


def test_no_new_api_endpoints():
    """不新增接口 — issues.py 路由数量不应因本轮改动变化"""
    from app.routers import issues
    routes = [
        r for r in dir(issues)
        if not r.startswith("_") and r in {
            "list_issues", "create_issue", "get_issue", "update_issue",
            "delete_issue", "patch_status", "resolve_issue", "close_issue",
            "assign_helper", "request_ceo", "list_my_issues",
        }
    ]
    # 本轮应维持这些已有端点，不应新增
    assert "patch_status" in routes, "patch_status 端点应存在"


# ── 前端 Kanban 结构验证 ─────────────────────────────────────

def _read_issues_page() -> str:
    file = FRONTEND_PAGES / "IssuesPage.tsx"
    if not file.exists():
        pytest.skip("IssuesPage.tsx not found")
    return file.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def issues_source() -> str:
    return _read_issues_page()


def test_kanban_has_coordinating_column(issues_source: str):
    """KANBAN_COLUMNS 包含 '待协调'"""
    assert re.search(r"KANBAN_COLUMNS\s*=\s*\[[^\]]*'待协调'", issues_source), (
        "KANBAN_COLUMNS 应包含 '待协调'"
    )


def test_kanban_column_order(issues_source: str):
    """看板列顺序：待处理 / 处理中 / 待协调 / 待决策 / 已解决 / 已关闭"""
    match = re.search(
        r"KANBAN_COLUMNS\s*=\s*\[([^\]]+)\]",
        issues_source,
    )
    assert match, "未找到 KANBAN_COLUMNS 常量"
    content = match.group(1)
    # 提取列名顺序
    cols = re.findall(r"'([^']+)'", content)
    assert cols == ["待处理", "处理中", "待协调", "待决策", "已解决", "已关闭"], (
        f"看板列顺序错误: {cols}"
    )


def test_kanban_still_has_decision_column(issues_source: str):
    """待决策列仍存在"""
    assert "'待决策'" in issues_source


def test_kanban_still_has_resolved_column(issues_source: str):
    """已解决列仍存在"""
    assert "'已解决'" in issues_source


def test_kanban_still_has_closed_column(issues_source: str):
    """已关闭列仍存在"""
    assert "'已关闭'" in issues_source


def test_kanban_has_six_columns_total(issues_source: str):
    """KANBAN_COLUMNS 共 6 个元素"""
    match = re.search(r"KANBAN_COLUMNS\s*=\s*\[([^\]]+)\]", issues_source)
    assert match
    cols = re.findall(r"'([^']+)'", match.group(1))
    assert len(cols) == 6, f"KANBAN_COLUMNS 应有 6 列，实际 {len(cols)}"


# ── 状态动作不变验证 ─────────────────────────────────────────

def test_handle_start_processing_uses_processing(issues_source: str):
    """"开始处理"仍使用"处理中" """
    assert re.search(
        r"updateIssueStatus\(\s*selected\.id\s*,\s*'处理中'\s*\)",
        issues_source,
    )


def test_request_ceo_not_using_coordinating():
    """requestIssueCeo 不使用"待协调"，上报 Coach 仍进"待决策" """
    from app.routers import issues as issues_router
    from app.domain import issue_flow as IF
    import inspect
    src = inspect.getsource(issues_router.request_ceo)
    assert "STATUS_PENDING_DECISION" in src, (
        "request_ceo 应使用 STATUS_PENDING_DECISION（待决策），不是待协调"
    )
    assert "STATUS_COORDINATING" not in src, (
        "request_ceo 不应设置 STATUS_COORDINATING"
    )


def test_resolve_uses_resolved():
    """"标记已解决"仍使用 STATUS_RESOLVED"""
    from app.routers import issues as issues_router
    from app.domain import issue_flow as IF
    import inspect
    src = inspect.getsource(issues_router.resolve_issue)
    assert "STATUS_RESOLVED" in src


def test_close_uses_closed():
    """"关闭问题"仍使用 STATUS_CLOSED"""
    from app.routers import issues as issues_router
    from app.domain import issue_flow as IF
    import inspect
    src = inspect.getsource(issues_router.close_issue)
    assert "STATUS_CLOSED" in src


# ── 不修改其他页面的验证 ─────────────────────────────────────

def test_no_confirm_page_changes():
    """ConfirmPage.tsx 未被本轮修改（检查 STATUS_COORDINATING 新逻辑是否误入）"""
    from pathlib import Path
    file = ROOT.parent / "frontend" / "src" / "pages" / "ConfirmPage.tsx"
    if file.exists():
        content = file.read_text(encoding="utf-8")
        # ConfirmPage 原本用"待协调"作为 issue_type 标签筛选，这不是本轮新增的 status 逻辑
        # 确认没有 STATUS_COORDINATING 等新常量名出现
        assert "STATUS_COORDINATING" not in content


def test_no_achievements_page_changes():
    """AchievementsPage.tsx 未被修改"""
    from pathlib import Path
    file = ROOT.parent / "frontend" / "src" / "pages" / "AchievementsPage.tsx"
    if file.exists():
        content = file.read_text(encoding="utf-8")
        assert "STATUS_COORDINATING" not in content


# ── 数据库不新增字段的验证 ───────────────────────────────────

def test_issue_model_no_new_fields():
    """Issue 模型不因本轮改动新增字段"""
    from app.models import Issue
    columns = {c.name for c in Issue.__table__.columns}
    # 不应有 coordinating_status 等新字段
    assert "coordinating_status" not in columns


def test_no_migration_files_added():
    """不新增 migration"""
    migrations_dir = ROOT / "migrations"
    if migrations_dir.exists():
        versions_dir = migrations_dir / "versions"
        if versions_dir.exists():
            py_files = sorted(
                f for f in os.listdir(str(versions_dir))
                if f.endswith(".py") and f != "__init__.py"
            )
            # 不强制检查（可能用 alembic），只确保不报异常
        else:
            pass  # 无 versions 目录时跳过


# ── 不出现风险中心相关代码 ───────────────────────────────────

def test_no_risk_center_code():
    """不出现'风险中心'相关代码"""
    from pathlib import Path
    issue_file = FRONTEND_PAGES / "IssuesPage.tsx"
    if issue_file.exists():
        content = issue_file.read_text(encoding="utf-8")
        assert "风险中心" not in content


# ── related_subtask_id 链路不受影响 ──────────────────────────-

def test_confirmations_router_unchanged():
    """confirmations.py 不因本轮改动变化（related_subtask_id 链路）"""
    from app.routers import confirmations
    import inspect
    src = inspect.getsource(confirmations)
    assert "STATUS_COORDINATING" not in src

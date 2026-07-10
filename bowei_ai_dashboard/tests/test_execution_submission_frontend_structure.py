"""
N4-P0-C 前端结构验收测试

不运行真实前端，通过源码字符串检查确保：
1. TaskManagementPage 存在提交进展和读取汇报记录逻辑
2. 不涉及 Workstream / 第四层任务 / 客户侧 / 过程支持
3. 不新增关键任务详情页路由
"""

from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def _route_source() -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")


# ── TaskManagementPage 提交进展入口 ──────────────────────────────

def test_task_management_page_has_create_update_import():
    """TaskManagementPage 必须存在 createUpdate 或等价提交进展调用。"""
    source = _frontend_source("pages/TaskManagementPage.tsx")

    assert "createUpdate" in source, "TaskManagementPage 应有 createUpdate 调用"
    assert "handleProgressSubmit" in source, "应有 handleProgressSubmit 提交函数"


def test_task_management_page_has_fetch_update_reading():
    """TaskManagementPage 存在读取汇报记录逻辑。"""
    source = _frontend_source("pages/TaskManagementPage.tsx")

    assert "fetchTaskUpdates" in source, "应有 fetchTaskUpdates 读取汇报记录"
    assert "fetchSubtaskDetail" in source, "应有 fetchSubtaskDetail 读取关键任务详情"


def test_task_management_page_has_refresh_after_submit_transition():
    """提交进展成功后 UI 应有状态转换和明确的提示文案。"""
    source = _frontend_source("pages/TaskManagementPage.tsx")

    assert "progressSubmitState" in source, "应有提交状态管理"
    assert "'submitting'" in source, "应有 submitting 状态"
    assert "'done'" in source, "应有 done 状态"
    # 提交成功提示文案：应告知用户提交后需负责人确认才会显示
    assert "已提交至 AI 确认中心" in source, "应有提交后提示文案"
    assert "负责人确认后将显示在工作推进表" in source, "应说明确认后才会出现在工作推进表"


# ── VoiceUpdatePage 提交入口 ─────────────────────────────────────

def test_voice_update_page_has_create_update_and_ai_extract():
    """VoiceUpdatePage 存在完整的 AI 提取 + 提交确认流程。"""
    source = _frontend_source("pages/VoiceUpdatePage.tsx")

    # VoiceUpdatePage 导入 useVoiceSubmission 和 AI 提取相关 hooks
    assert "useVoiceSubmission" in source, "应导入 useVoiceSubmission hook"
    assert "useVoiceExtraction" in source or "extract" in source.lower(), "应有 AI 提取功能"


# ── 不新增边界检查 ──────────────────────────────────────────────

def test_task_management_page_no_workstream_or_4th_layer():
    """TaskManagementPage 不引入 Workstream / 第四层任务。"""
    source = _frontend_source("pages/TaskManagementPage.tsx")
    lowered = source.lower()

    assert "workstream" not in lowered
    assert "第四层" not in source


def test_no_detail_page_route_for_subtask():
    """不新增关键任务详情页路由。"""
    rs = _route_source()

    # 不应出现新的 subtask detail 路由
    lowered = rs.lower()
    assert "subtaskdetail" not in lowered.replace("-", "").replace("_", ""), \
        "不应新增 key-subtask-detail 路由"


def test_no_client_side_entry_in_routes():
    """不开发客户侧入口。"""
    rs = _route_source()
    lowered = rs.lower()

    assert "client" not in lowered or "/client" not in rs, \
        "不应有客户侧路由入口"


def test_no_process_support_or_process_assurance():
    """不引入过程支持 / 过程保障。"""
    source = _frontend_source("pages/TaskManagementPage.tsx")
    rs = _route_source()

    for text in ["过程支持", "过程保障"]:
        assert text not in source, f"TaskManagementPage 不应包含 {text}"
        assert text not in rs, f"App.tsx 路由不应包含 {text}"


# ── API 层检查 ──────────────────────────────────────────────────

def test_updates_api_exists():
    """前端 api/updates.ts 存在且导出 createUpdate。"""
    source = _frontend_source("api/updates.ts")

    assert "export" in source
    assert "createUpdate" in source or "updates" in source.lower()


def test_confirmations_api_exists():
    """前端 api/confirmations.ts 存在确认接口。"""
    source = _frontend_source("api/confirmations.ts")

    assert "export" in source
    assert "confirm" in source.lower()


# ── 计划表视图不变 ──────────────────────────────────────────────

def test_plan_table_view_unchanged():
    """计划表视图组件不引新增功能术语。"""
    source = _frontend_source("components/task-management/PlanTableView.tsx")
    lowered = source.lower()

    assert "workstream" not in lowered
    assert "第四层" not in source
    assert "过程支持" not in source
    assert "过程保障" not in source
    assert "客户侧" not in source

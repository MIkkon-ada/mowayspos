from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


# ── OwnerSubmitModal 工作台布局验收 ────────────────────────────

def test_workbench_has_split_panel_layout():
    """弹窗应使用左右分栏（工作台）布局而非纯纵向堆叠。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "flex flex-1 min-h-0" in source or "flex-row" in source, \
        "应使用左右分栏布局（flex 容器）"
    assert "border-r" in source, \
        "左右栏之间应有分隔线"


def test_workbench_has_left_info_panel():
    """应存在左侧项目基础信息栏。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "项目基础信息" in source
    assert "380px" in source, \
        "左栏应有固定宽度（380px 左右）"


def test_workbench_has_right_work_progress_panel():
    """应存在右侧工作推进表雏形编辑区。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "工作推进表雏形" in source
    # 右栏应为弹性宽度
    assert "flex-1" in source


def test_workbench_modal_width_upgraded():
    """弹窗宽度应升级到 1280px / 96vw。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "min(1280px, 96vw)" in source or "1280" in source, \
        "弹窗宽度应升级到约 1280px 或等效响应式宽度"
    assert "w-[820px]" not in source and "w-[960px]" not in source, \
        "不应再使用 N4-P0-F 及更早的窄宽度"


def test_workbench_header_footer_fixed_content_scrolls():
    """Header/Footer 固定，中间主体可滚动。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "flex-shrink-0" in source, "Header 和 Footer 应有 flex-shrink-0"
    assert "overflow-y-auto" in source, "内容区应可滚动"
    assert "min-h-0" in source, "flex 容器应有 min-h-0 以启用内部滚动"


def test_workbench_left_and_right_scroll_independently():
    """左右两栏应各自独立可滚动或有明确分栏。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    # 至少有两处 overflow-y-auto（左栏和右栏各一）
    count = source.count("overflow-y-auto")
    assert count >= 2, f"左右栏应各自可独立滚动（至少 2 处 overflow-y-auto，实际 {count} 处）"


def test_task_layer_still_title_and_description_only():
    """重点工作层仍只显示标题 + 说明/评价标准（无责任人/协助人/时间输入）。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "task.title" in source, "重点工作标题绑定应存在"
    assert "task.description" in source, "重点工作说明绑定应存在"


def test_key_task_layer_still_has_assignee_helper_timing():
    """关键任务层仍保留责任人、协助人、开始、结束。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "subtask.assignee" in source
    assert "subtask.helper" in source
    assert "subtask.plan_start" in source
    assert "subtask.plan_end" in source
    assert "subtask.evaluation_standard" in source


def test_to_payload_draft_not_broken():
    """toPayloadDraft 没有被破坏。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "function toPayloadDraft" in source
    assert "const workProgressDraft = toPayloadDraft(draftTasks)" in source
    assert "work_progress_draft: workProgressDraft" in source
    # 字段完整性
    assert "title: task.title.trim()" in source
    assert "assignee: subtask.assignee.trim()" in source
    assert "helper: subtask.helper.trim()" in source
    assert "plan_start: subtask.plan_start" in source
    assert "plan_end: subtask.plan_end" in source


def test_no_forbidden_terms_anywhere():
    """弹窗不出现 Workstream / 第四层 / 客户侧 / 过程支持 / 过程保障。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for forbidden in ["Workstream", "workstream", "第四层", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in source, f"OwnerSubmitModal 不应包含 '{forbidden}'"


def test_no_new_detail_page_route():
    """不新增详情页路由（只改 OwnerSubmitModal 文件）。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for forbidden in ["Route", "route", "router", "/owner-submit/", "/workbench"]:
        assert forbidden not in source, \
            f"不应新增路由 '{forbidden}'"


def test_no_plan_table_view_components_changed():
    """不改计划表视图相关组件。"""
    # 本测试只验证 OwnerSubmitModal 范围内没有侵入计划表组件
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for forbidden_term in ["PlanTableView", "ExecutionView", "WorkProgressTable"]:
        assert forbidden_term not in source, \
            f"OwnerSubmitModal 不应引用 '{forbidden_term}'"

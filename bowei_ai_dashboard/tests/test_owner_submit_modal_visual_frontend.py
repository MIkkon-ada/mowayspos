from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


# ── OwnerSubmitModal 视觉布局验收 ──────────────────────────────

def test_owner_submit_modal_has_three_zone_layout():
    """弹窗应按最新确认原型呈现 Header / 左右 Main / Footer 工作台结构。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "owner-submit-workbench-shell" in source
    assert "bg-[#f6f9ff]" in source, "工作台背景应接近原型浅灰蓝"
    assert "owner-submit-workbench-header" in source
    assert "h-[72px]" in source, "Header/Footer 高度应贴近原型 72px"
    assert "owner-submit-workbench-main" in source
    assert "overflow-y-auto" in source, "Main 应滚动"
    assert "owner-submit-workbench-columns" in source, "Main 应是左右两栏工作台"
    assert "flex gap-6 items-start" in source or "flex gap-6" in source, "Main 内容应使用左右 flex 布局"
    assert "owner-submit-workbench-footer" in source
    assert "shrink-0" in source, "Header/Footer 应在 flex 结构中不收缩"
    assert "pb-8" in source or "pb-section-margin" in source, "Main 底部应给 footer 留出空间"


def test_owner_submit_modal_width_is_optimized():
    """弹窗内容宽度应接近最新原型 max-w-[1440px] 左右工作台容器。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "w-[96vw]" in source, "外层仍应是宽弹窗/工作台"
    assert "max-w-[1280px]" in source, "弹窗最大宽度保持合理上限"
    assert "max-w-[1440px]" in source, "主体内容容器必须接近最新原型 max-w-[1440px]"
    assert "mx-auto" in source, "主体内容应居中"
    assert "w-[820px]" not in source, "不应再使用旧 820px 宽度"


def test_project_core_info_is_left_sidebar():
    """项目核心信息应迁移到左侧 360-400px 工作台栏。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "owner-submit-left-pane" in source
    assert "w-[400px]" in source or "w-[380px]" in source or "w-[360px]" in source
    assert "shrink-0" in source
    assert "sticky" in source
    assert "owner-submit-right-pane" in source
    assert "flex-1 min-w-0" in source


def test_project_info_area_uses_compact_grid():
    """项目核心信息区应贴近原型左侧白底卡片。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "owner-submit-core-card" in source
    assert "bg-white" in source
    assert "border" in source
    assert "rounded-xl" in source
    assert "shadow-sm" in source
    assert "space-y-6" in source, "左侧栏内项目字段应纵向紧凑排列"
    assert "rows={3}" in source or "rows={2}" in source, "项目完成准则 textarea 应低高度"
    assert "项目完成准则 / 验收标准" in source


def test_work_progress_area_no_longer_uses_large_amber_box():
    """工作推进表区域不应再使用大面积 amber 色块包裹。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    # 不应有 bg-amber-50/40 之类的大面积背景色块（section 级）
    assert "bg-amber-50/40" not in source, \
        "不应再使用大面积 amber 背景色块包裹整个工作推进表区域"
    # 不应使用 amber-200 边框包裹（旧样式 section）
    assert "border-amber-200" not in source, \
        "不应再使用 amber 边框包裹区域"


def test_task_group_has_compact_style():
    """重点工作组应贴近原型：白底、细边框、rounded-xl、浅灰组头。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "owner-submit-workplan-heading" in source
    assert "owner-submit-task-group" in source
    assert "bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm" in source
    assert "owner-submit-task-group-header" in source
    assert "bg-slate-100/70" in source or "bg-[#eef4fc]" in source
    assert "w-8 h-8" in source, "序号块应接近原型 8x8"
    assert "md:grid-cols-2" in source, "重点工作名称和目标成果应一行两列"


def test_subtask_uses_table_like_layout():
    """关键任务区域必须是原型式 table，而不是普通表单行。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "<table" in source, "关键任务应使用表格化编辑"
    assert "owner-submit-subtask-table" in source
    assert "border-collapse" in source
    assert "thead" in source and "tbody" in source
    assert "hover:bg-slate-50" in source or "hover:bg-[#f6f9ff]" in source
    assert "border-none p-0" in source, "表格输入框应轻量，不像大表单控件"
    assert "时间段" in source and "备注 / 标准" in source


def test_instruction_text_remains_correct():
    """说明文案仍保持正确的业务语义。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "重点工作用于归类工作方向" in source, \
        "应保留：重点工作用于归类工作方向"
    assert "关键任务才需要明确责任人" in source, \
        "应保留：关键任务才需要明确责任人、协助人和计划时间"


def test_key_task_layer_still_retains_assignee_and_timing():
    """关键任务层仍保留责任人、协助人、计划时间。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "subtask.assignee" in source
    assert "subtask.helper" in source
    assert "subtask.plan_start" in source
    assert "subtask.plan_end" in source
    assert "subtask.evaluation_standard" in source


def test_no_forbidden_terms_in_owner_submit_modal():
    """OwnerSubmitModal 不得引入越界术语。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for forbidden in ["Workstream", "workstream", "第四层", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in source, \
            f"OwnerSubmitModal 不应包含 '{forbidden}'"


def test_payload_compatibility_preserved():
    """toPayloadDraft 保持兼容，不受视觉改动影响。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "function toPayloadDraft" in source
    assert "work_progress_draft: workProgressDraft" in source
    assert "const workProgressDraft = toPayloadDraft(draftTasks)" in source

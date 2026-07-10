from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


# ── OwnerSubmitModal 视觉布局验收 ──────────────────────────────

def test_owner_submit_modal_has_three_zone_layout():
    """弹窗应有固定标题、滚动内容、固定底部操作区三层布局。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "flex-shrink-0" in source, "应有固定区域（标题或底部）"
    assert "overflow-y-auto" in source, "内容应可滚动"
    assert "flex-col" in source, "应使用纵向 flex 布局"
    assert "owner-submit-modal-body" in source, "滚动内容区应有稳定结构标识"
    assert "pb-6" in source or "pb-8" in source, "滚动区底部应给 footer 留出呼吸空间"
    assert "owner-submit-modal-footer" in source, "footer 应作为 flex shrink 区域而非覆盖内容"


def test_owner_submit_modal_width_is_optimized():
    """弹窗宽度不应再是 820px 窄布局，应 ≥ 920px。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    # 宽度至少应该是 920px 或更宽；新版允许响应式工作台宽度。
    assert "w-[96vw]" in source or "w-[920px]" in source or "w-[960px]" in source or "w-[940px]" in source \
        or "w-[980px]" in source or "w-[1000px]" in source or "w-[1040px]" in source, \
        "弹窗宽度应 ≥ 920px 或使用 96vw 工作台宽度，不再使用 820px 窄布局"
    assert "max-w-[1280px]" in source, "工作台弹窗应有最大宽度限制"
    assert "w-[820px]" not in source, "不应再使用旧 820px 宽度"


def test_project_info_area_uses_compact_grid():
    """项目基础信息区域应采用紧凑两列或 grid 布局。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    # 应有 grid 布局
    assert "grid" in source
    assert "owner-submit-core-compact" in source, "项目核心信息区应使用 compact 结构标识"
    assert "rows={2}" in source, "项目完成准则 textarea 应控制为较低高度"
    assert (
        "col-span-2" in source
        or "grid-cols-2" in source
        or "md:col-span-2" in source
    ), "应有跨列长文本字段"


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
    """每个重点工作组应有紧凑分组样式而非大卡片。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    # 应仍有"重点工作"的序号标识
    assert "重点工作" in source
    assert "owner-submit-workplan-compact" in source
    assert "owner-submit-task-group-compact" in source
    assert "h-6 w-6" in source or "h-7 w-7" in source, "重点工作序号块应缩小"
    assert "shadow-2xl" not in source, "视觉对齐阶段不应使用重阴影"


def test_subtask_uses_table_like_layout():
    """关键任务区域应使用类表格横向排列，而非纵向堆叠卡片。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "<table" in source, "关键任务应使用表格化编辑"
    assert "owner-submit-subtask-table-compact" in source
    assert "py-1" in source, "关键任务表格行高应压缩"
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

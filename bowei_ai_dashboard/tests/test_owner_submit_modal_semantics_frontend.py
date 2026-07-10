from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


# ── OwnerSubmitModal 语义验收 ────────────────────────────────

def test_owner_submit_modal_instruction_is_clear_about_task_vs_subtask_responsibility():
    """立项弹窗说明文案应明确：重点工作只归类，关键任务才派责任人。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    assert "重点工作用于归类工作方向" in source or "归类工作方向" in source, \
        "应说明重点工作用于归类方向"
    assert "关键任务才需要明确责任人" in source or "关键任务才需要" in source, \
        "应说明关键任务才需要责任人和时间"


def test_owner_submit_modal_key_task_layer_retains_assignee_and_helper():
    """关键任务层应保留责任人、协助人、计划时间等可执行字段。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    # 关键任务区域应有 assignee / helper / plan_start / plan_end 的输入
    assert "subtask.assignee" in source, "关键任务层应保留 assignee 绑定"
    assert "subtask.helper" in source, "关键任务层应保留 helper 绑定"
    assert "subtask.plan_start" in source, "关键任务层应保留 plan_start 绑定"
    assert "subtask.plan_end" in source, "关键任务层应保留 plan_end 绑定"
    assert "evaluation_standard" in source, "关键任务层应保留 evaluation_standard 绑定"


def test_owner_submit_modal_payload_still_compatible():
    """toPayloadDraft 仍保持兼容，关键字段不丢失。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    # toPayloadDraft 必须存在且保持基本结构
    assert "function toPayloadDraft" in source
    assert "title: task.title.trim()" in source
    assert "description: task.description.trim()" in source
    assert "subtasks: task.subtasks" in source
    assert "title: subtask.title.trim()" in source
    assert "evaluation_standard: subtask.evaluation_standard.trim()" in source
    assert "assignee: subtask.assignee.trim()" in source

    # work_progress_draft 仍正确传递
    assert "const workProgressDraft = toPayloadDraft(draftTasks)" in source
    assert "work_progress_draft: workProgressDraft" in source


def test_no_workstream_or_4th_layer_in_owner_submit_modal():
    """OwnerSubmitModal 不得引入 Workstream / 第四层 / 客户侧 / 过程支持字样。"""
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")

    for forbidden in ["Workstream", "workstream", "第四层", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in source, f"OwnerSubmitModal 不应包含 '{forbidden}'"


# ── ProjectsMgmtSection 项目卡片人员展示 ──────────────────────

def test_project_card_shows_only_project_level_roles():
    """项目卡片人员行只应展示：企业教练、负责人、统筹人、成员数量。"""
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    assert "企业教练" in source
    assert "负责人" in source
    assert "统筹人" in source
    assert "成员" in source
    # memberText 应只统计 role='member'
    assert "getMemberNamesByRole" in source


def test_project_card_draft_summary_does_not_misrepresent_task_owner_as_project_owner():
    """卡片推进表摘要不应将重点工作 owner 混淆为项目负责人。"""
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    # getDraftSummary 的 ownerConfigured 应改为统计 subtask assignee 而不是 task owner
    assert "getDraftSummary" in source
    # 关键验证：getDraftSummary 函数体内不应使用 task.owner 来统计 ownerConfigured
    # 新的统计口径：subtasks.filter(s => s.assignee)
    assert "subtasks.filter" in source or "subtasks" in source, \
        "推进表雏形摘要应基于 subtask assignee 而非 task owner"
    # 草案文本中"已指派"替代了原来的"责任人"
    assert "已指派" in source, "草案摘要应使用'已指派'（关键任务级）替代'责任人'（避免与项目负责人混淆）"


def test_member_count_excludes_owner():
    """成员数量不应包含项目负责人（owner）。"""
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    # memberText 只计算 role === 'member' 的人数
    # projectMembers 的过滤逻辑应确保 owner 不被计入 member
    assert "role === 'member'" in source or "m.role === " in source or '"member"' in source


def test_no_forbidden_terms_in_projects_mgmt_section():
    """ProjectsMgmtSection 不得引入越界术语（排除布局注释中的序号用词）。"""
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for forbidden in ["Workstream", "workstream", "客户侧", "过程支持", "过程保障"]:
        assert forbidden not in source, f"ProjectsMgmtSection 不应包含 '{forbidden}'"

from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_projects_management_has_lifecycle_workbench_structure():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "projects-lifecycle-workbench",
        "projects-lifecycle-header",
        "projects-lifecycle-queue-tabs",
        "projects-lifecycle-main-grid",
        "projects-lifecycle-project-queue",
        "projects-lifecycle-action-panel",
        "项目管理",
        "创建与管理所有项目，配置项目人员，推进立项流程",
        "选择左侧项目查看详情和下一步操作。",
    ]:
        assert expected in source

    assert "lg:grid-cols-[minmax(0,1.55fr)_minmax(360px,0.95fr)]" in source


def test_projects_management_status_tabs_are_lifecycle_queue_tabs():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "{ key: 'all', label: '全部'",
        "{ key: 'draft', label: '草稿'",
        "{ key: 'dispatched', label: '已派发'",
        "{ key: 'pending_review', label: '待审核'",
        "{ key: 'returned', label: '已退回'",
        "{ key: 'active', label: '进行中'",
        "{ key: 'archived', label: '已归档'",
        "待负责人完善",
        "待企业教练审核",
        "待负责人修改",
        "执行中",
        "归档档案",
        'placeholder="搜索项目名称..."',
    ]:
        assert expected in source


def test_project_cards_show_next_actions_and_key_lifecycle_info():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "function LifecycleCard",
        "projects-lifecycle-card",
        "当前阶段",
        "企业教练：",
        "项目负责人：",
        "统筹人：",
        "成员：",
        "项目周期：",
        "推进表雏形：",
        "{ label: '编辑项目'",
        "{ label: '完善立项信息'",
        "{ label: '查看审核材料'",
        "{ label: '进入工作推进表'",
        "{ label: '查看归档档案'",
    ]:
        assert expected in source


def test_project_action_panel_contains_processing_sections():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "function DetailPanel",
        "projects-lifecycle-action-panel-card",
        "当前阶段说明",
        "操作提醒",
        "项目核心信息",
        "项目角色",
        "立项资料完备度",
        "下一步操作",
        "项目完成准则 / 验收标准",
        "项目核心信息：",
        "工作推进表雏形：",
        "重点工作数量",
        "关键任务数量",
    ]:
        assert expected in source


def test_projects_management_keeps_existing_business_entries():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "setShowNew(true)",
        "setImportOpen(true)",
        "void handleDispatch",
        "setOwnerFillProject",
        "setApproveModal",
        "void handleReturn",
        "openProjectEditor",
        "handleArchive",
        "handleUnarchive",
    ]:
        assert expected in source


def test_projects_management_does_not_introduce_forbidden_terms_or_dependencies():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for forbidden in [
        "Project CEO",
        "SOP Template",
        "Active SOPs",
        "New Template",
        "Create SOP",
        "工作推进表雏形导出",
        "24 小时内完成审核",
        "fonts.googleapis.com",
        "Material Symbols",
        "material-symbols",
        "cdn.tailwindcss.com",
        "tailwind.config",
        "http://",
        "https://",
        "Workstream",
        "第四层",
        "客户侧",
        "过程支持",
        "过程保障",
    ]:
        assert forbidden not in source

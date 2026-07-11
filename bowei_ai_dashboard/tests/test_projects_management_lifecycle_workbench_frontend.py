from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_projects_management_has_lifecycle_workbench_structure():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "projects-lifecycle-workbench",
        "projects-lifecycle-page-shell",
        "projects-lifecycle-header",
        "projects-lifecycle-queue-tabs",
        "projects-lifecycle-main-grid",
        "projects-lifecycle-project-queue",
        "projects-lifecycle-action-panel",
        "项目管理",
        "创建与管理所有项目，配置项目人员，推进立项流程",
        "只有筛选结果为空时显示项目空状态",
    ]:
        assert expected in source

    assert "max-w-[1440px]" in source
    assert "lg:grid-cols-[minmax(0,1.5fr)_minmax(380px,1fr)]" in source
    assert "bg-[#F8FAFC]" in source or "bg-slate-50" in source
    assert "projects-lifecycle-header rounded-2xl" not in source, \
        "页面标题区不应做成巨大白色卡片"
    assert "projects-lifecycle-header mx-auto flex" in source


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

    assert "projects-lifecycle-queue-tabs mx-auto flex" in source
    assert "projects-lifecycle-tabs-strip" in source
    assert "projects-lifecycle-tab-compact" in source
    assert "border-b-2" in source, "当前 tab 应使用原型式底部蓝色线或轻量高亮"
    assert "rounded-xl border px-3 py-2 text-left" not in source, \
        "状态 tabs 不应做成一排大统计卡片"
    assert "py-1" in source or "py-1.5" in source, "tabs 高度应接近原型紧凑白栏"


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

    assert "projects-lifecycle-card" in source
    assert "projects-lifecycle-queue-card" in source
    assert "projects-lifecycle-card-title-row" in source
    assert "projects-lifecycle-card-stage-row" in source
    assert "projects-lifecycle-card-footer-row" in source
    assert "projects-lifecycle-card-people-line" in source
    assert "absolute left-0 top-0 bottom-0 w-1" in source, \
        "选中卡片应有明显左侧色条"
    assert "px-4 py-3" in source or "p-4" in source, \
        "项目队列卡片应保持紧凑"
    assert "rounded-xl border bg-white" in source


def test_project_queue_card_hierarchy_is_action_queue_not_archive_card():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "projects-lifecycle-card-title-row",
        "projects-lifecycle-card-stage-row",
        "projects-lifecycle-card-people-line",
        "projects-lifecycle-card-meta-row",
        "projects-lifecycle-card-action-row",
    ]:
        assert expected in source

    title_idx = source.index("projects-lifecycle-card-title-row")
    stage_idx = source.index("projects-lifecycle-card-stage-row")
    people_idx = source.index("projects-lifecycle-card-people-line")
    meta_idx = source.index("projects-lifecycle-card-meta-row")
    action_idx = source.index("projects-lifecycle-card-action-row")
    assert title_idx < stage_idx < people_idx < meta_idx < action_idx

    assert "rounded-lg border border-slate-100 bg-slate-50/80" not in source, \
        "左侧项目队列不应再出现大灰色人员信息框"
    assert "border-2 border-[#2170e4]" not in source, \
        "当前选中卡片不要过重，只保留左侧竖线和浅蓝边框"
    assert "border-sky-200" in source or "border-[#b9d7ff]" in source


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

    assert "projects-lifecycle-action-panel-card sticky" in source or "lg:sticky" in source
    assert "projects-lifecycle-panel-header" in source
    assert "projects-lifecycle-panel-reminder" in source
    assert "getReminderToneClass" in source
    assert "projects-lifecycle-panel-section" in source
    assert "projects-lifecycle-panel-pills" in source
    assert "bg-error-container" not in source, "不要照搬原型里的错误色大提醒块"


def test_project_action_panel_is_action_first_not_archive_drawer():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "projects-lifecycle-panel-next-actions",
        "projects-lifecycle-panel-core-info",
        "projects-lifecycle-panel-roles",
        "projects-lifecycle-panel-readiness",
    ]:
        assert expected in source

    header_idx = source.index("projects-lifecycle-panel-header")
    next_idx = source.index("projects-lifecycle-panel-next-actions")
    core_idx = source.index("projects-lifecycle-panel-core-info")
    roles_idx = source.index("projects-lifecycle-panel-roles")
    readiness_idx = source.index("projects-lifecycle-panel-readiness")
    assert header_idx < next_idx < core_idx < roles_idx < readiness_idx

    assert "projects-lifecycle-panel-reminder" not in source[source.index("projects-lifecycle-panel-next-actions"):core_idx], \
        "右侧面板应先呈现下一步操作，再进入信息说明"
    assert "bg-slate-50/60 px-4 py-3" not in source, \
        "右侧不要堆太多灰底信息卡"


def test_project_action_buttons_are_wired_to_visible_results():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "showDraftPreview",
        "setShowDraftPreview",
        "projects-lifecycle-draft-preview",
        "projects-lifecycle-draft-preview-table",
        "projects-lifecycle-archive-feedback",
        "navigate(`/work/tasks?projectId=${project.id}`)",
        "navigate(`/work/tasks?projectId=${selectedProject.id}`)",
    ]:
        assert expected in source

    assert "navigate(`/project/${project.id}/tasks`)" not in source
    assert "navigate(`/project/${selectedProject.id}/tasks`)" not in source

    actions_start = source.index("projects-lifecycle-panel-next-actions")
    actions_source = source[actions_start:]

    pending_section = actions_source[actions_source.index("status === 'pending_review'"):]
    pending_section = pending_section[: pending_section.index("status === 'returned'")]
    assert "onClick={onPreviewDraft}" in pending_section
    assert "onWorkProgress" not in pending_section

    active_section = actions_source[actions_source.index("status === 'active'"):]
    active_section = active_section[: active_section.index("status === 'archived'")]
    assert "onClick={onWorkProgress}" in active_section

    archived_section = actions_source[actions_source.index("status === 'archived'"):]
    archived_section = archived_section[: archived_section.index("</section>", archived_section.index("status === 'archived'"))]
    assert "onClick={onShowArchiveFeedback}" in archived_section


def test_project_draft_preview_uses_workbench_fields_not_legacy_plan_fields():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    preview_start = source.index("projects-lifecycle-draft-preview")
    preview_end = source.index("projects-lifecycle-panel-core-info", preview_start)
    preview_source = source[preview_start:preview_end]

    for expected in [
        "draftSummary.taskCount",
        "draftSummary.subtaskCount",
        "DraftProgressTable",
    ]:
        assert expected in preview_source

    table_source = source[source.index("function DraftProgressTable"):]
    for expected in [
        "keyTask",
        "standard",
        "subTask",
        "assignee",
        "collaborator",
        "planRange",
        "note",
    ]:
        assert expected in table_source

    assert "planStart" not in table_source
    assert "planEnd" not in table_source


def test_projects_management_defaults_to_first_filtered_project():
    source = _frontend_source("features/settings/ProjectsMgmtSection.tsx")

    for expected in [
        "默认选中当前筛选结果的第一个项目",
        "filteredProjects.length === 0",
        "setSelectedProjectId(null)",
        "filteredProjects.some((project) => project.id === selectedProjectId)",
        "setSelectedProjectId(filteredProjects[0].id)",
    ]:
        assert expected in source

    assert "选择左侧项目查看详情和下一步操作。" not in source, \
        "右侧不应默认空白；只有列表为空才显示空状态"


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

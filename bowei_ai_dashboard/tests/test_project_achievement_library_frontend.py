from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


def test_achievement_page_is_project_library_not_pending_submission_center():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "项目成果库" in source
    assert "选择项目成果库" in source
    assert "待确认成果" not in source
    assert "正式成果" not in source
    assert "提交后由项目负责人确认入库" not in source
    assert "提交审核" not in source
    assert "退回修改" not in source
    assert "撤回" not in source


def test_achievement_page_uses_direct_create_achievement_for_manual_registration():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "createAchievement(" in source
    assert "保存入库" in source
    assert "createAchievementSubmission" not in source
    assert "confirmAchievementSubmission" not in source
    assert "rejectAchievementSubmission" not in source
    assert "withdrawAchievementSubmission" not in source
    assert "fetchAchievementSubmissions" not in source


def test_project_achievement_library_has_required_project_and_detail_sections():
    source = _frontend_source("pages/AchievementsPage.tsx")

    for text in [
        "项目名称",
        "项目负责人",
        "Coach / 企业教练",
        "进入成果库",
        "切换项目",
        "登记成果",
        "成果名称",
        "成果类型",
        "关联重点工作 / 关键任务",
        "AI确认入库",
        "手动登记",
        "所属项目",
        "查看原始提交",
        "附件与链接",
        "使用场景与备注",
    ]:
        assert text in source


def test_project_achievement_library_uses_workbench_visual_structure():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "PROJECT ACHIEVEMENT LIBRARY" in source
    assert "achievement-stat-bar" in source
    assert "achievement-project-picker-card" in source
    assert "achievement-workbench-grid" in source
    assert "lg:grid-cols-[minmax(0,1.5fr)_minmax(380px,1fr)]" in source
    assert "achievement-filter-bar" in source
    assert "achievement-detail-panel" in source
    assert "bg-sky-50" in source


def test_achievement_registration_modal_matches_project_library_workbench():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "max-w-4xl" in source
    assert "上下文关联" in source
    assert "成果定义" in source
    assert "grid-cols-12" in source
    assert "col-span-8" in source
    assert "保存入库" in source


def test_project_achievement_registration_fields_and_fixed_types_exist():
    source = _frontend_source("pages/AchievementsPage.tsx")

    for text in [
        "所属项目",
        "关联重点工作",
        "关联关键任务",
        "成果名称",
        "成果类型",
        "版本",
        "标签",
        "文件链接/存储地址",
        "适用场景",
        "成果说明",
        "方案",
        "模板",
        "SOP",
        "Prompt",
        "Agent",
        "文档",
    ]:
        assert text in source


def test_achievement_library_navigation_keeps_global_project_picker_entry():
    auth_source = _frontend_source("domain/authFlow.ts")

    assert "achievements: '/work/achievements'" in auth_source
    assert "`/work/achievements?projectId=${currentProjectId}`" not in auth_source


def test_achievement_library_does_not_add_forbidden_scope_terms():
    source = _frontend_source("pages/AchievementsPage.tsx")

    for forbidden in ["Workstream", "workstream", "第四层", "客户侧", "过程支持", "过程保障", "公司资产库", "资产市场"]:
        assert forbidden not in source

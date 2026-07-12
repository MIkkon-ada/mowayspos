""""
N4-P2-A 关键任务关联展示优化 — 前端防回归测试

验证：
1. AchievementsPage.tsx 和 IssuesPage.tsx 不再硬编码"关键任务：暂未关联"
2. 改为"未指定关键任务"
3. 不出现技术文案
4. 不改核心结构和状态流转
"""

from __future__ import annotations

from pathlib import Path


def _frontend_source(relative_path: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / relative_path).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# 成果库 AchievementsPage
# ══════════════════════════════════════════════════════════════

def test_achievement_page_no_longer_hardcodes_key_task_not_bound():
    source = _frontend_source("pages/AchievementsPage.tsx")

    # 核心校验：删除硬编码的"暂未关联"
    assert "关键任务：暂未关联" not in source
    # 表格列标题"关联重点工作 / 关键任务"仍然保留（这是表头描述，不是数据展示）
    assert "关联重点工作 / 关键任务" in source


def test_achievement_page_contains_key_task_not_specified():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "未指定关键任务" in source


def test_achievement_page_no_technical_disclaimers_in_ui():
    source = _frontend_source("pages/AchievementsPage.tsx")

    for forbidden in [
        "暂未接入入库字段",
        "当前版本暂不落库",
        "暂不落库，后续接入",
        "JSON追溯",
        "数据库无字段",
        "Schema不支持",
    ]:
        assert forbidden not in source, f"不应出现技术文案: {forbidden}"


def test_achievement_page_does_not_submit_related_subtask_id():
    source = _frontend_source("pages/AchievementsPage.tsx")

    # createAchievement 调用不应该传 related_subtask_id
    import re
    call = re.search(r"createAchievement\(\{[^}]+\}\)", source, re.DOTALL)
    assert call is not None, "应能找到 createAchievement 调用"
    assert "related_subtask_id" not in call.group(), (
        "createAchievement payload 不应包含 related_subtask_id"
    )


def test_achievement_registration_keeps_related_key_task():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "关联重点工作" in source
    assert "关联关键任务" in source


def test_achievement_page_keeps_project_selector_unchanged():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "选择项目成果库" in source
    assert "搜索项目名称" in source
    assert "进入成果库" in source


def test_achievement_page_keeps_key_task_field_disabled():
    source = _frontend_source("pages/AchievementsPage.tsx")

    # "关联关键任务" 的 select 应该仍然是 disabled
    import re
    # 查找关联关键任务的 FormSelect，确认 disabled
    assert re.search(
        r'label="关联关键任务".*?disabled',
        source,
        re.DOTALL,
    ), "关联关键任务字段应保持 disabled"


def test_achievement_page_keeps_related_key_task_form():
    source = _frontend_source("pages/AchievementsPage.tsx")

    # related_task_id 仍然在表单中使用
    assert "related_task_id" in source


def test_achievement_page_has_helper_function():
    source = _frontend_source("pages/AchievementsPage.tsx")

    assert "keyTaskLabelForAchievement" in source


# ══════════════════════════════════════════════════════════════
# 问题中心 IssuesPage
# ══════════════════════════════════════════════════════════════

def test_issue_page_no_longer_hardcodes_key_task_not_bound():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "关键任务：暂未关联" not in source


def test_issue_page_contains_key_task_not_specified():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "未指定关键任务" in source


def test_issue_page_no_technical_disclaimers_in_ui():
    source = _frontend_source("pages/IssuesPage.tsx")

    for forbidden in [
        "暂未接入入库字段",
        "当前版本暂不落库",
        "暂不落库，后续接入",
        "JSON追溯",
        "数据库无字段",
        "Schema不支持",
    ]:
        assert forbidden not in source, f"不应出现技术文案: {forbidden}"


def test_issue_page_does_not_submit_related_subtask_id():
    source = _frontend_source("pages/IssuesPage.tsx")

    import re
    call = re.search(r"createIssue\(\{[^}]+\}\)", source, re.DOTALL)
    assert call is not None, "应能找到 createIssue 调用"
    assert "related_subtask_id" not in call.group(), (
        "createIssue payload 不应包含 related_subtask_id"
    )


def test_issue_page_keeps_kanban_structure():
    source = _frontend_source("pages/IssuesPage.tsx")

    for col in ["待处理", "处理中", "待决策", "已解决", "已关闭"]:
        assert col in source, f"看板列应保留: {col}"


def test_issue_page_keeps_start_processing_flow():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "开始处理" in source
    assert "handleStartProcessing" in source
    assert "updateIssueStatus" in source


def test_issue_page_keeps_related_key_task():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "关联重点工作" in source
    assert "关联关键任务" in source


def test_issue_page_keeps_key_task_field_disabled():
    source = _frontend_source("pages/IssuesPage.tsx")

    import re
    # 查找关联关键任务的 select，确认 disabled
    assert re.search(
        r'label="关联关键任务".*?disabled',
        source,
        re.DOTALL,
    ) or re.search(
        r'关联关键任务.*?<select[^>]*disabled',
        source,
        re.DOTALL,
    ), "关联关键任务字段应保持 disabled"


def test_issue_page_keeps_related_task_id_in_form():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "related_task_id" in source


def test_issue_page_has_helper_function():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "keyTaskLabelForIssue" in source


def test_issue_page_keeps_project_selector_unchanged():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "选择项目问题中心" in source
    assert "进入问题中心" in source


def test_issue_page_no_global_scope_leak():
    source = _frontend_source("pages/IssuesPage.tsx")

    assert "问题台账" not in source
    assert "批量删除" not in source

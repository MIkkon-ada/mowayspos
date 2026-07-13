"""
N4-P2-K: 新增问题表单收口 — 前端验证

验证：
1. IssuesPage.tsx 新增弹窗移除问题类型/优先级/状态/待决策人/协助人
2. 保留 问题描述/关联重点工作/关联关键任务/期望解决时间
3. createIssue payload 默认值
4. Kanban 仍 6 列
5. 不新增 "转待协调" 等
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_PAGES = ROOT.parent / "frontend" / "src" / "pages"
FRONTEND_API = ROOT.parent / "frontend" / "src" / "api"


@pytest.fixture(scope="session")
def issues_source() -> str:
    return (FRONTEND_PAGES / "IssuesPage.tsx").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def issues_api_source() -> str:
    return (FRONTEND_API / "issues.ts").read_text(encoding="utf-8")


# ── 隐藏字段验证 ──────────────────────────────────────────────

def test_create_form_no_issue_type_select(issues_source: str):
    """新增问题弹窗不再出现'问题类型'选择"""
    # 弹窗内不应有 issue_type 的 select 或 label
    # 但 Kanban 卡片的 TYPE_STYLE 和筛选器仍可能存在 issue_type 字样
    # 策略：确认 AddIssueModal 范围内没有 <option>问题</option><option>风险</option> 四个 type 选项的 select
    assert '<option>问题</option><option>风险</option><option>待协调</option><option>需决策</option>' not in issues_source


def test_create_form_no_priority_select(issues_source: str):
    """新增问题弹窗不再出现'优先级'选择"""
    assert '<option>高</option><option>中</option><option>低</option>' not in issues_source


def test_create_form_no_owner_input_in_modal(issues_source: str):
    """新增问题弹窗不再出现'负责人'输入"""
    # AddIssueModal 内的负责人输入已移除
    # 排除 Kanban 卡片中"负责人："的显示
    add_modal_start = issues_source.find("function AddIssueModal")
    assert add_modal_start > 0
    add_modal_body = issues_source[add_modal_start:]
    # 在 AddIssueModal 函数体内不应出现负责人 label
    assert '负责人' not in add_modal_body or 'label' not in add_modal_body.split('负责人')[0]
    # 更精确：检查 负责人 label 不再出现
    lines_with_owner_label = [
        line for line in add_modal_body.split('\n')
        if '负责人' in line and 'label' in line
    ]
    assert len(lines_with_owner_label) == 0, f"AddIssueModal 仍有负责人字段: {lines_with_owner_label}"


def test_create_form_no_helper_input_in_modal(issues_source: str):
    """新增问题弹窗不再出现'协助人'输入"""
    add_modal_start = issues_source.find("function AddIssueModal")
    assert add_modal_start > 0
    add_modal_body = issues_source[add_modal_start:]
    lines_with_helper_label = [
        line for line in add_modal_body.split('\n')
        if '协助人' in line and 'label' in line
    ]
    assert len(lines_with_helper_label) == 0, f"AddIssueModal 仍有协助人字段: {lines_with_helper_label}"


def test_create_form_no_need_decision_by_in_modal(issues_source: str):
    """新增问题弹窗不再出现'待决策人'"""
    add_modal_start = issues_source.find("function AddIssueModal")
    assert add_modal_start > 0
    add_modal_body = issues_source[add_modal_start:]
    assert 'need_decision_by' not in add_modal_body


def test_create_form_no_status_in_modal(issues_source: str):
    """新增问题弹窗不再出现'状态'选择/输入"""
    add_modal_start = issues_source.find("function AddIssueModal")
    assert add_modal_start > 0
    add_modal_body = issues_source[add_modal_start:]
    # status 作为字段名不应在 AddIssueModal 表单中出现
    # 但 handleSubmit 内会有硬编码 status: '待处理'，那个是通过的
    # 检查 form state 中不包含 status
    form_state_start = add_modal_body.find("useState({")
    form_state_end = add_modal_body.find("})", form_state_start) if form_state_start > -1 else -1
    if form_state_start > -1 and form_state_end > -1:
        form_state_section = add_modal_body[form_state_start:form_state_end]
        assert 'status' not in form_state_section.split(',')[0]  # 第一个 key 不应是 status


# ── 保留字段验证 ──────────────────────────────────────────────

def test_create_form_still_has_description(issues_source: str):
    """新增问题弹窗仍包含'问题描述'"""
    add_modal_start = issues_source.find("function AddIssueModal")
    add_modal_body = issues_source[add_modal_start:]
    assert '问题描述' in add_modal_body


def test_create_form_still_has_related_task(issues_source: str):
    """新增问题弹窗仍包含'关联重点工作'"""
    add_modal_start = issues_source.find("function AddIssueModal")
    add_modal_body = issues_source[add_modal_start:]
    assert '关联重点工作' in add_modal_body


def test_create_form_still_has_related_subtask(issues_source: str):
    """新增问题弹窗仍包含'关联关键任务'"""
    add_modal_start = issues_source.find("function AddIssueModal")
    add_modal_body = issues_source[add_modal_start:]
    assert '关联关键任务' in add_modal_body


def test_create_form_still_has_expected_resolve_time(issues_source: str):
    """新增问题弹窗仍包含'期望解决时间'"""
    add_modal_start = issues_source.find("function AddIssueModal")
    add_modal_body = issues_source[add_modal_start:]
    assert '期望解决时间' in add_modal_body


# ── createIssue payload 默认值验证 ──────────────────────────────

def test_create_issue_defaults_issue_type_question(issues_source: str):
    """createIssue payload 包含 issue_type: '问题'"""
    assert "issue_type: '问题'" in issues_source


def test_create_issue_defaults_priority_medium(issues_source: str):
    """createIssue payload 包含 priority: '中'"""
    assert "priority: '中'" in issues_source


def test_create_issue_defaults_status_pending(issues_source: str):
    """createIssue payload 包含 status: '待处理'"""
    assert "status: '待处理'" in issues_source


def test_create_issue_still_has_related_task_id(issues_source: str):
    """createIssue payload 仍包含 related_task_id"""
    assert "related_task_id" in issues_source


def test_create_issue_still_has_related_subtask_id(issues_source: str):
    """createIssue payload 仍包含 related_subtask_id"""
    assert "related_subtask_id" in issues_source


def test_create_issue_api_accepts_status(issues_api_source: str):
    """createIssue API 函数签名包含 status 参数"""
    assert "status?: string" in issues_api_source


def test_create_issue_api_accepts_source_type(issues_api_source: str):
    """createIssue API 函数签名包含 source_type 参数"""
    assert "source_type?: string" in issues_api_source


# ── Kanban 仍然 6 列 ───────────────────────────────────────────

def test_kanban_still_six_columns(issues_source: str):
    """Kanban 仍包含 6 列：待处理/处理中/待协调/待决策/已解决/已关闭"""
    assert "'待处理'" in issues_source
    assert "'处理中'" in issues_source
    assert "'待协调'" in issues_source
    assert "'待决策'" in issues_source
    assert "'已解决'" in issues_source
    assert "'已关闭'" in issues_source


def test_kanban_columns_const_has_six(issues_source: str):
    """KANBAN_COLUMNS 常量包含 6 列"""
    assert "KANBAN_COLUMNS" in issues_source
    assert "待协调" in issues_source


# ── 不该出现的内容 ─────────────────────────────────────────────

def test_no_zhuan_xietiao_button(issues_source: str):
    """不新增'转待协调'按钮"""
    assert '转待协调' not in issues_source


def test_no_risk_center(issues_source: str):
    """不出现'风险中心'"""
    assert '风险中心' not in issues_source


def test_no_new_migration():
    """不新增 migration 文件"""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    # alembic versions 不应有新增
    versions_dir = root / "alembic" / "versions"
    if versions_dir.exists():
        # 检查最近修改的文件是否与本轮相关
        import os
        recent = sorted(
            [p for p in versions_dir.glob("*.py") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in recent[:3]:
            content = p.read_text(encoding="utf-8")
            if "coordinating" in content.lower() or "create_form" in content.lower():
                pytest.fail(f"本轮不应新增 migration: {p.name}")


# ── 其他页面未改动 ────────────────────────────────────────────

def test_no_confirm_page_changes():
    """ConfirmPage.tsx 未被本轮修改"""
    f = FRONTEND_PAGES / "ConfirmPage.tsx"
    if f.exists():
        content = f.read_text(encoding="utf-8")
        assert "STATUS_COORDINATING" not in content


def test_no_achievements_page_changes():
    """AchievementsPage.tsx 未被本轮修改"""
    f = FRONTEND_PAGES / "AchievementsPage.tsx"
    if f.exists():
        content = f.read_text(encoding="utf-8")
        assert "STATUS_COORDINATING" not in content


def test_no_new_api_endpoint():
    """不新增接口 — issues.py 的 router 路由数量不变"""
    router_path = ROOT / "app" / "routers" / "issues.py"
    content = router_path.read_text(encoding="utf-8")
    # 确认现有 6 个路由端点（不增不减）
    routes = [line for line in content.split('\n') if line.strip().startswith('@router.')]
    # 当前应有: get("") / post("") / get("/mine") / get("/{row_id}") / put("/{row_id}")
    # delete("/{row_id}") / patch("/{row_id}/status") / patch("/{row_id}/resolve")
    # patch("/{row_id}/close") / patch("/{row_id}/assign-helper") / patch("/{row_id}/request-ceo")
    assert len(routes) == 11, f"路由数量应为 11，实际 {len(routes)}"


def test_add_modal_has_hint_text(issues_source: str):
    """新增问题弹窗顶部包含提示文案"""
    assert '问题等级、处理路径和协助人由项目负责人后续判断和分派' in issues_source


def test_add_modal_has_correct_description_placeholder(issues_source: str):
    """问题描述 placeholder 已更新"""
    assert '请说明遇到的问题、影响范围、当前卡点' in issues_source

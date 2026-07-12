"""
前端 IssuesPage 结构防回归测试
验证：问题中心已改为项目级看板，不是台账表格页面
"""
import re
import pytest


def _read_issues_page() -> str:
    """读取当前 IssuesPage.tsx 内容"""
    from pathlib import Path
    file = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "pages" / "IssuesPage.tsx"
    if not file.exists():
        pytest.skip("IssuesPage.tsx not found")
    return file.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def issues_source() -> str:
    return _read_issues_page()


# ── 必含文案 ────────────────────────────────────────────────

def test_contains_project_issue_center(issues_source: str):
    """页面包含 '项目问题中心'"""
    assert "项目问题中心" in issues_source


def test_contains_select_project_issue_center(issues_source: str):
    """项目选择页包含 '选择项目问题中心'"""
    assert "选择项目问题中心" in issues_source


def test_contains_enter_issue_center(issues_source: str):
    """按钮文案为 '进入问题中心'"""
    assert "进入问题中心" in issues_source


def test_contains_pending(issues_source: str):
    """包含看板列 '待处理'"""
    assert "待处理" in issues_source


def test_contains_processing(issues_source: str):
    """包含看板列 '处理中'"""
    assert "处理中" in issues_source


def test_contains_decision_pending(issues_source: str):
    """包含看板列 '待决策'"""
    assert "待决策" in issues_source


def test_contains_resolved(issues_source: str):
    """包含看板列 '已解决'"""
    assert "已解决" in issues_source


def test_contains_closed(issues_source: str):
    """包含看板列 '已关闭'"""
    assert "已关闭" in issues_source


def test_contains_issue_detail(issues_source: str):
    """右侧面板包含 '问题详情'"""
    assert "问题详情" in issues_source


def test_contains_add_issue(issues_source: str):
    """弹窗包含 '新增问题'"""
    assert "新增问题" in issues_source


def test_contains_save_issue(issues_source: str):
    """保存按钮文案为 '保存问题'"""
    assert "保存问题" in issues_source


def test_contains_ai_confirmed_source(issues_source: str):
    """包含来源标签 'AI确认入库'"""
    assert "AI确认入库" in issues_source


def test_contains_manual_source(issues_source: str):
    """包含来源标签 '手动新增'"""
    assert "手动新增" in issues_source


def test_contains_related_key_task_text(issues_source: str):
    """包含 '关联重点工作'"""
    assert "关联重点工作" in issues_source


def test_contains_related_sub_task_text(issues_source: str):
    """包含 '关联关键任务'"""
    assert "关联关键任务" in issues_source


# ── 不应包含的旧文案 ─────────────────────────────────────────

def test_no_issue_list_as_main_title(issues_source: str):
    """不应包含 '问题清单' 作为主区域标题（已改为看板）"""
    assert "问题清单" not in issues_source


def test_no_batch_delete(issues_source: str):
    """不应包含 '批量删除'"""
    assert "批量删除" not in issues_source


def test_no_issue_ledger(issues_source: str):
    """不应包含 '问题台账'"""
    assert "问题台账" not in issues_source


def test_no_special_project_label(issues_source: str):
    """不应包含 '关联专项'（已统一改为所属项目/重点工作/关键任务）"""
    assert "关联专项" not in issues_source


# ── 数据获取逻辑 ────────────────────────────────────────────

def test_project_kanban_uses_project_id(issues_source: str):
    """
    /work/issues?projectId=xxx 逻辑必须使用 projectId 获取问题
    即 fetchIssues(projectId) 而非 fetchIssues() 无参
    """
    # fetchIssues 调用必须出现在 projectId 有效时才调用
    assert "fetchIssues" in issues_source

    # 必须传递 projectId 参数（不能仅 fetchIssues()）
    # 检查是否有 fetchIssues(projectId) 或 fetchIssues( projectId ) 模式
    assert re.search(r"fetchIssues\(\s*projectId\b", issues_source), (
        "IssuesPage.tsx 应在 fetchIssues 调用中传入 projectId 参数，"
        "不能使用无参 fetchIssues() 拉取全局问题"
    )


def test_kanban_uses_kanban_columns_const(issues_source: str):
    """看板列应通过 KANBAN_COLUMNS 常量驱动"""
    assert "KANBAN_COLUMNS" in issues_source
    # 验证常量包含了所有 5 列
    assert "'待处理'" in issues_source
    assert "'待决策'" in issues_source
    assert "'已关闭'" in issues_source


def test_no_global_issues_on_kanban(issues_source: str):
    """在 projectId 存在时，不允许使用 fetchIssues() 拉全量"""
    # 检查是否有独立的 fetchIssues() 调用（无 projectId 参数）
    # 排除函数定义行和注释
    bare_calls = re.findall(r"fetchIssues\(\s*\)", issues_source)
    assert len(bare_calls) == 0, (
        "不应在项目看板中使用 fetchIssues() 无参调用，"
        "必须传入 projectId 获取项目级问题"
    )


# ── 修复验证：helper 和 related_task_id 已提交 ──────────────────

def test_create_issue_submits_helper(issues_source: str):
    """createIssue 提交应包含 helper"""
    # createIssue 调用中应出现 helper:
    assert re.search(r"createIssue\(\s*\{[^}]*helper:", issues_source), (
        "createIssue 调用必须传入 helper 字段"
    )


def test_create_issue_submits_related_task_id(issues_source: str):
    """createIssue 提交应包含 related_task_id"""
    assert re.search(r"createIssue\(\s*\{[^}]*related_task_id:", issues_source), (
        "createIssue 调用必须传入 related_task_id 字段"
    )


def test_add_modal_contains_related_key_task(issues_source: str):
    """新增问题弹窗包含 '关联重点工作'"""
    # AddIssueModal 区域应包含关联重点工作标签
    assert "关联重点工作" in issues_source


def test_no_version_not_supported(issues_source: str):
    """不应包含 '当前版本暂不落库'"""
    assert "当前版本暂不落库" not in issues_source


def test_no_field_not_connected(issues_source: str):
    """不应包含 '暂未接入入库字段'"""
    assert "暂未接入入库字段" not in issues_source


# ── "开始处理" 状态流转 ────────────────────────────────────

def test_issues_page_imports_update_issue_status(issues_source: str):
    """IssuesPage.tsx 引入了 updateIssueStatus"""
    assert "updateIssueStatus" in issues_source


def test_api_issues_exports_update_issue_status():
    """api/issues.ts 存在 updateIssueStatus 导出"""
    from pathlib import Path
    file = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "api" / "issues.ts"
    if not file.exists():
        pytest.skip("issues.ts not found")
    content = file.read_text(encoding="utf-8")
    assert "updateIssueStatus" in content


def test_start_processing_not_permanently_disabled(issues_source: str):
    """"开始处理"不再是永久 disabled"""
    # 应该有 handleStartProcessing 函数
    assert "handleStartProcessing" in issues_source
    # 不应再包含旧的禁用注释
    assert "no backend endpoint" not in issues_source
    # 不应再包含旧的 title 提示
    assert "开始处理接口暂未接入" not in issues_source


def test_handle_start_processing_calls_update_issue_status(issues_source: str):
    """handleStartProcessing 调用 updateIssueStatus(selected.id, '处理中')"""
    assert re.search(r"updateIssueStatus\(\s*selected\.id\s*,\s*'处理中'\s*\)", issues_source), (
        "handleStartProcessing 应调用 updateIssueStatus(selected.id, '处理中')"
    )


def test_start_processing_shows_success_toast(issues_source: str):
    """成功后显示 '已开始处理' toast"""
    assert "已开始处理" in issues_source


def test_start_processing_respects_project_archived(issues_source: str):
    """项目已归档时开始处理按钮 disabled"""
    # 开始处理按钮应包含 projectArchived 判断
    # 查找按钮 disabled 属性中引用 projectArchived
    assert re.search(
        r'待处理.*?<button[^>]*disabled\s*=\s*\{[^}]*projectArchived',
        issues_source,
        re.DOTALL,
    ) or re.search(
        r'disabled\s*=\s*\{[^}]*projectArchived[^}]*\}',
        issues_source,
    ), "开始处理按钮应在项目归档时 disabled"


def test_start_processing_btn_has_onclick(issues_source: str):
    """"开始处理"按钮绑定了 onClick"""
    # 在"开始处理"按钮附近应有 onClick
    assert re.search(
        r'待处理.*?onClick\s*=\s*\{handleStartProcessing\}',
        issues_source,
        re.DOTALL,
    ), "待处理区域的开始处理按钮应绑定 handleStartProcessing"


def test_kanban_still_five_columns(issues_source: str):
    """看板仍包含五列：待处理 / 处理中 / 待决策 / 已解决 / 已关闭"""
    assert "待处理" in issues_source
    assert "处理中" in issues_source
    assert "待决策" in issues_source
    assert "已解决" in issues_source
    assert "已关闭" in issues_source

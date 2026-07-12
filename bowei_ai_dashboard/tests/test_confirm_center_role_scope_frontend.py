"""Tests for N4-P1-C: AI确认中心职责收口 — ConfirmPage.tsx 前端文案与结构检查"""
import re
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIRM_PAGE = PROJECT_ROOT / "frontend" / "src" / "pages" / "ConfirmPage.tsx"
ISSUES_API = PROJECT_ROOT / "frontend" / "src" / "api" / "issues.ts"
UPDATES_API = PROJECT_ROOT / "frontend" / "src" / "api" / "updates.ts"


@pytest.fixture(scope="module")
def confirm_source() -> str:
    """读取 ConfirmPage.tsx 源码"""
    if not CONFIRM_PAGE.exists():
        pytest.skip("ConfirmPage.tsx not found")
    return CONFIRM_PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def updates_api_source() -> str:
    """读取 updates.ts 源码"""
    if not UPDATES_API.exists():
        pytest.skip("updates.ts not found")
    return UPDATES_API.read_text(encoding="utf-8")


# ── 页面命名修正 ────────────────────────────────────

def test_title_is_ai_confirm_center(confirm_source: str):
    """ConfirmPage.tsx 包含 'AI 确认中心'"""
    assert "AI 确认中心" in confirm_source


def test_no_ai_audit_center(confirm_source: str):
    """ConfirmPage.tsx 不包含 'AI 审核中心'"""
    assert "AI 审核中心" not in confirm_source


# ── 视图职责收口 ────────────────────────────────────

def test_reviewer_default_to_pending_view(confirm_source: str):
    """reviewer 默认进入待确认视图 (defaultViewMode = isReviewer ? 'all' : 'mine')"""
    assert "defaultViewMode" in confirm_source
    assert re.search(
        r"isReviewer\s*\?\s*'all'\s*:\s*'mine'",
        confirm_source,
    ), "defaultViewMode 应使用 isReviewer ? 'all' : 'mine'"


def test_no_all_work_projects_button_for_member(confirm_source: str):
    """普通成员看不到 '待确认' 按钮 — isReviewer && 时才显示"""
    # 待确认按钮应包裹在 isReviewer 条件内
    assert re.search(
        r"isReviewer\s*&&\s*\(",
        confirm_source,
    ) or re.search(
        r"\{isReviewer\s*&&",
        confirm_source,
    ), "待确认按钮应在 isReviewer 条件里显示"


def test_my_submissions_renamed(confirm_source: str):
    """'我的提交' 文案已改成 '我的提交记录'"""
    assert "我的提交记录" in confirm_source


def test_my_submissions_not_just_my_submissions(confirm_source: str):
    """独立字符串 '我的提交' 不应再出现（但'我的提交记录'可以）"""
    # 要确保的是不出现孤立的"我的提交"（没有"记录"后缀）
    # 用更精确的检查：排除 "我的提交记录"
    standalone_my_submissions = re.findall(
        r'(?<!"我的提交记录")我的提交(?!记录)', confirm_source.replace('我的提交记录', '')
    )
    # 由于 replace 可能不够精确，用更简单的方法
    source_minus_full = confirm_source.replace("我的提交记录", "")
    assert "我的提交" not in source_minus_full, (
        "不应出现孤立的'我的提交'文案，应统一使用'我的提交记录'"
    )


def test_reviewer_has_both_views(confirm_source: str):
    """reviewer 显示 '待确认' 和 '我的提交记录'"""
    assert "待确认" in confirm_source
    assert "我的提交记录" in confirm_source


# ── 初始默认视图逻辑 ────────────────────────────────────

def test_initial_redirect_uses_ref(confirm_source: str):
    """使用 useRef 防止 reviewer 切到 mine 后被重复弹回 all"""
    assert "initialRedirectDone" in confirm_source


# ── 筛选器职责调整 ────────────────────────────────────

def test_all_project_filter_renamed(confirm_source: str):
    """'全部专项' 已改成 '全部项目'"""
    assert "全部项目" in confirm_source


def test_no_all_special_project(confirm_source: str):
    """不再出现 '全部专项' 作为筛选主文案"""
    assert "全部专项" not in confirm_source


def test_submitter_filter_hidden_in_mine_view(confirm_source: str):
    """'全部提交人' 筛选器在 mine 视图中隐藏"""
    # 提交人筛选应包裹在 viewMode === 'all' 条件内
    assert re.search(
        r"viewMode\s*===\s*'all'.*?全部提交人",
        confirm_source,
        re.DOTALL,
    ), "提交人筛选器应在 viewMode === 'all' 时才显示"


# ── 列表标题 ────────────────────────────────────

def test_list_title_conditional(confirm_source: str):
    """列表标题应条件显示 '待确认事项' 或 '我的提交记录'"""
    assert "待确认事项" in confirm_source


# ── 空状态 ────────────────────────────────────

def test_empty_state_for_pending_view(confirm_source: str):
    """待确认视图空状态提示"""
    assert "暂无待确认事项" in confirm_source


def test_empty_state_for_mine_view(confirm_source: str):
    """我的提交记录视图空状态提示"""
    assert "暂无提交记录" in confirm_source


# ── 文案统一 ────────────────────────────────────

def test_issue_center_renamed(confirm_source: str):
    """'问题库' 已改成 '问题中心'"""
    assert "问题中心" in confirm_source
    assert "问题库" not in confirm_source


def test_all_work_projects_renamed_to_all_projects(confirm_source: str):
    """'全部专项' 不出现"""
    assert "全部专项" not in confirm_source


# ── API 保留 ────────────────────────────────────

def test_fetch_my_updates_still_exists(updates_api_source: str):
    """fetchMyUpdates 仍保留在 updates.ts"""
    assert "fetchMyUpdates" in updates_api_source


def test_get_pending_still_exists(confirm_source: str):
    """getPending 仍保留（从 confirmations.ts import）"""
    assert "getPending" in confirm_source


# ── confirmSubmission 调用不变 ────────────────────────────────────

def test_confirm_submission_call_unchanged(confirm_source: str):
    """confirmSubmission 调用不变"""
    assert "confirmSubmission" in confirm_source


# ── 副标题 ────────────────────────────────────

def test_subtitle_truncate_class(confirm_source: str):
    """副标题有 truncate 样式类"""
    assert "truncate" in confirm_source


# ── 操作区隐藏 ────────────────────────────────────

def test_view_mode_all_condition_for_actions(confirm_source: str):
    """viewMode === 'all' 包裹单卡判断操作区"""
    # 在卡片详情弹窗区域应有 viewMode === 'all' 的条件判断
    assert "viewMode === 'all'" in confirm_source, (
        "应通过 viewMode === 'all' 控制确认操作区显隐"
    )


def test_mine_view_readonly_hint(confirm_source: str):
    """mine 视图下弹窗操作区有只读提示"""
    assert "如需处理请切换到" in confirm_source

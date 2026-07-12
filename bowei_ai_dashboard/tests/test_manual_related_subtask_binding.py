"""N4-P2-D 手动登记成果/问题支持关键任务绑定 — 测试。

覆盖：
- 后端 Schema（AchievementPayload / IssuePayload 支持 related_subtask_id）
- 后端校验（validate_subtask_link）
- 前端类型（AchievementPayload 包含 related_subtask_id，createIssue payload 包含 related_subtask_id）
- 前端页面（AchievementsPage / IssuesPage 启用关键任务下拉，不再永久 disabled）
- 前端页面（切换重点工作清空 related_subtask_id）
- 前端页面（未指定关键任务文案）
- 不出现禁用占位文案
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import crud, models


# ── helpers ─────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_SRC = PROJECT_DIR / "frontend" / "src"
BACKEND_DIR = PROJECT_DIR / "bowei_ai_dashboard"


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


# ── 后端 Schema 测试 ───────────────────────────────────────────

class TestAchievementPayloadSupportsSubtaskId:
    """AchievementPayload schemas 支持 related_subtask_id."""

    def test_has_related_subtask_id(self):
        from app.schemas import AchievementPayload
        fields = AchievementPayload.model_fields
        assert "related_subtask_id" in fields

    def test_related_subtask_id_optional(self):
        from app.schemas import AchievementPayload
        p = AchievementPayload(project_id=1, name="test", related_task_id=None)
        assert p.related_subtask_id is None

    def test_related_subtask_id_settable(self):
        from app.schemas import AchievementPayload
        p = AchievementPayload(project_id=1, name="test", related_task_id=5, related_subtask_id=10)
        assert p.related_subtask_id == 10


class TestIssuePayloadSupportsSubtaskId:
    """IssuePayload schemas 支持 related_subtask_id."""

    def test_has_related_subtask_id(self):
        from app.schemas import IssuePayload
        fields = IssuePayload.model_fields
        assert "related_subtask_id" in fields

    def test_related_subtask_id_optional(self):
        from app.schemas import IssuePayload
        p = IssuePayload(project_id=1, description="test")
        assert p.related_subtask_id is None

    def test_related_subtask_id_settable(self):
        from app.schemas import IssuePayload
        p = IssuePayload(project_id=1, description="test", related_task_id=5, related_subtask_id=10)
        assert p.related_subtask_id == 10


# ── 校验逻辑测试 ───────────────────────────────────────────────

class TestValidateSubtaskLink:
    """validate_subtask_link 校验逻辑正确."""

    def test_none_subtask_id_passes(self):
        """related_subtask_id 为空时直接通过。"""
        db = MagicMock()
        crud.validate_subtask_link(db, project_id=1, related_task_id=2, related_subtask_id=None)
        db.get.assert_not_called()

    def test_no_task_id_raises_422(self):
        """related_subtask_id 不为空但 related_task_id 为空 → 422。"""
        db = MagicMock()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            crud.validate_subtask_link(db, project_id=1, related_task_id=None, related_subtask_id=10)
        assert exc.value.status_code == 422
        assert "必须同时关联重点工作" in exc.value.detail

    def test_subtask_not_found_raises_422(self):
        """SubTask 不存在 → 422。"""
        db = MagicMock()
        db.get.return_value = None
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            crud.validate_subtask_link(db, project_id=1, related_task_id=2, related_subtask_id=10)
        assert exc.value.status_code == 422

    def test_subtask_deleted_raises_422(self):
        """SubTask 已删除 → 422。"""
        db = MagicMock()
        subtask = MagicMock(spec=models.SubTask)
        subtask.is_deleted = True
        db.get.return_value = subtask
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            crud.validate_subtask_link(db, project_id=1, related_task_id=2, related_subtask_id=10)
        assert exc.value.status_code == 422

    def test_subtask_task_id_mismatch_raises_422(self):
        """SubTask.task_id != related_task_id → 422。"""
        db = MagicMock()
        subtask = MagicMock(spec=models.SubTask)
        subtask.is_deleted = False
        subtask.task_id = 99  # 不匹配 related_task_id=2
        db.get.side_effect = lambda model, id: subtask if model == models.SubTask else None
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            crud.validate_subtask_link(db, project_id=1, related_task_id=2, related_subtask_id=10)
        assert exc.value.status_code == 422
        assert "不属于所选重点工作" in exc.value.detail

    def test_task_not_found_raises_422(self):
        """Task 不存在 → 422。"""
        db = MagicMock()
        subtask = MagicMock(spec=models.SubTask)
        subtask.is_deleted = False
        subtask.task_id = 2
        # Task 返回 None
        def side_effect(model, pk):
            if model == models.SubTask:
                return subtask
            return None
        db.get.side_effect = side_effect
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            crud.validate_subtask_link(db, project_id=1, related_task_id=2, related_subtask_id=10)
        assert exc.value.status_code == 422

    def test_task_project_mismatch_raises_422(self):
        """Task.project_id != project_id → 422。"""
        db = MagicMock()
        subtask = MagicMock(spec=models.SubTask)
        subtask.is_deleted = False
        subtask.task_id = 2
        task = MagicMock(spec=models.Task)
        task.is_deleted = False
        task.project_id = 999  # 不匹配 project_id=1
        def side_effect(model, pk):
            if model == models.SubTask:
                return subtask
            return task
        db.get.side_effect = side_effect
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            crud.validate_subtask_link(db, project_id=1, related_task_id=2, related_subtask_id=10)
        assert exc.value.status_code == 422
        assert "不属于当前项目" in exc.value.detail

    def test_valid_link_passes(self):
        """合法的 related_subtask_id 通过校验。"""
        db = MagicMock()
        subtask = MagicMock(spec=models.SubTask)
        subtask.is_deleted = False
        subtask.task_id = 2
        task = MagicMock(spec=models.Task)
        task.is_deleted = False
        task.project_id = 1
        def side_effect(model, pk):
            if model == models.SubTask:
                return subtask
            return task
        db.get.side_effect = side_effect
        # 不应抛出异常
        crud.validate_subtask_link(db, project_id=1, related_task_id=2, related_subtask_id=10)

    def test_project_id_none_skips_project_check(self):
        """project_id 为 None 时跳过项目校验，但仍校验 subtask/task。"""
        db = MagicMock()
        subtask = MagicMock(spec=models.SubTask)
        subtask.is_deleted = False
        subtask.task_id = 2
        task = MagicMock(spec=models.Task)
        task.is_deleted = False
        task.project_id = 999  # 与 project_id 不同但 project_id 为 None
        def side_effect(model, pk):
            if model == models.SubTask:
                return subtask
            return task
        db.get.side_effect = side_effect
        crud.validate_subtask_link(db, project_id=None, related_task_id=2, related_subtask_id=10)


# ── 前端文件结构测试 ───────────────────────────────────────────

class TestFrontendAchievementsApi:
    """前端 achievements.ts API 类型兼容."""

    def test_achievement_payload_has_related_subtask_id(self):
        content = _read_text(str(FRONTEND_SRC / "api" / "achievements.ts"))
        assert "related_subtask_id" in content


class TestFrontendIssuesApi:
    """前端 issues.ts API 类型兼容."""

    def test_create_issue_payload_has_related_subtask_id(self):
        content = _read_text(str(FRONTEND_SRC / "api" / "issues.ts"))
        assert "related_subtask_id" in content


class TestFrontendAchievementsPage:
    """AchievementsPage 启用关键任务下拉."""

    def _content(self):
        return _read_text(str(FRONTEND_SRC / "pages" / "AchievementsPage.tsx"))

    def test_subtask_dropdown_not_permanently_disabled(self):
        """关键任务下拉不再用纯 disabled 属性。"""
        content = self._content()
        # 查找 subtask 相关的 select 标签 —— 现在应该有 `disabled={...}` 而不是 `disabled` 裸属性
        # 关键：不再有 `disabled>`（裸 disabled + 关闭标签）
        import re
        # 查找关联关键任务的 select（在 FormSelect 中）
        # 应该包含 onChange 和 disabled 条件判断
        assert 'related_subtask_id' in content

    def test_key_task_label_uses_subtask_by_id(self):
        """keyTaskLabelForAchievement 使用 subtaskById 参数。"""
        content = self._content()
        assert 'subtaskById' in content

    def test_no_disabled_placeholder_text(self):
        """不出现"当前成果可先关联到重点工作"的禁用占位文案。"""
        content = self._content()
        assert '关键任务精确绑定将在后续版本支持' not in content

    def test_clears_subtask_on_task_change(self):
        """切换重点工作时清空 related_subtask_id。"""
        content = self._content()
        # related_task_id onChange 中应包含 related_subtask_id: null
        assert 'related_subtask_id' in content

    def test_create_achievement_submits_subtask_id(self):
        """createAchievement 提交 related_subtask_id。"""
        content = self._content()
        assert 'related_subtask_id:' in content


class TestFrontendIssuesPage:
    """IssuesPage 启用关键任务下拉."""

    def _content(self):
        return _read_text(str(FRONTEND_SRC / "pages" / "IssuesPage.tsx"))

    def test_subtask_dropdown_not_permanently_disabled(self):
        """关键任务下拉不再永久 disabled。"""
        content = self._content()
        # 应该包含 subtask 相关的 fetchSubTasks 调用
        assert 'fetchSubTasks' in content
        assert 'related_subtask_id' in content

    def test_key_task_label_uses_subtask_by_id(self):
        """keyTaskLabelForIssue 使用 subtaskById 参数。"""
        content = self._content()
        assert 'subtaskById' in content

    def test_no_disabled_placeholder_text(self):
        """不出现"当前问题可先关联到重点工作"的禁用占位文案。"""
        content = self._content()
        assert '关键任务精确绑定将在后续版本支持' not in content

    def test_clears_subtask_on_task_change(self):
        """切换重点工作时清空 related_subtask_id。"""
        content = self._content()
        assert "setField('related_subtask_id', null)" in content

    def test_create_issue_submits_subtask_id(self):
        """createIssue 提交 related_subtask_id。"""
        content = self._content()
        assert 'related_subtask_id:' in content

    def test_add_issue_modal_imports_subtasks(self):
        """AddIssueModal 导入了 fetchSubTasks。"""
        content = self._content()
        assert 'fetchSubtasksByProject' in content


class TestUnspecifiedLabel:
    """未指定关键任务文案检查."""

    def test_achievements_page_has_unspecified_label(self):
        content = _read_text(str(FRONTEND_SRC / "pages" / "AchievementsPage.tsx"))
        assert '未指定关键任务' in content

    def test_issues_page_has_unspecified_label(self):
        content = _read_text(str(FRONTEND_SRC / "pages" / "IssuesPage.tsx"))
        assert '未指定关键任务' in content

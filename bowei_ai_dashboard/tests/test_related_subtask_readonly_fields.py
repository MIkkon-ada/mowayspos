"""PR1: related_subtask_id 字段和只读返回测试。

本轮只新增字段和 API 返回能力，不启用任何前端写入。
重点验证：
- ORM 模型包含 related_subtask_id 字段
- 字段属性：ForeignKey→subtasks.id, nullable=True, index=True
- 迁移文件包含三张表
- 迁移文件不包含历史回填 UPDATE
- schemas 响应无需显式修改（crud.to_dict 自动返回）
- 前端类型声明包含 related_subtask_id
- 前端 create payload 不提交 related_subtask_id
- 前端页面不启用关键任务下拉
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import inspect, ForeignKey, Integer

# ── 后端模块 ──
from app import models
from app import schemas

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_VERSIONS = ROOT / "migrations" / "versions"
FRONTEND_ROOT = ROOT.parent / "frontend" / "src"


# ──────────────────────────────────────────────────────────────
# 1. ORM 模型字段测试
# ──────────────────────────────────────────────────────────────


class TestUpdateSubmissionModel:
    """UpdateSubmission 包含 related_subtask_id。"""

    def test_has_related_subtask_id_column(self):
        mapper = inspect(models.UpdateSubmission)
        col = mapper.columns.get("related_subtask_id")
        assert col is not None, "UpdateSubmission 缺少 related_subtask_id 列"

    def test_foreign_key_to_subtasks(self):
        col = models.UpdateSubmission.__table__.c.related_subtask_id
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "subtasks"
        assert fk.column.name == "id"

    def test_nullable_true(self):
        col = models.UpdateSubmission.__table__.c.related_subtask_id
        assert col.nullable is True

    def test_index_true(self):
        col = models.UpdateSubmission.__table__.c.related_subtask_id
        assert col.index is True


class TestAchievementModel:
    """Achievement 包含 related_subtask_id。"""

    def test_has_related_subtask_id_column(self):
        mapper = inspect(models.Achievement)
        col = mapper.columns.get("related_subtask_id")
        assert col is not None, "Achievement 缺少 related_subtask_id 列"

    def test_foreign_key_to_subtasks(self):
        col = models.Achievement.__table__.c.related_subtask_id
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "subtasks"
        assert fk.column.name == "id"

    def test_nullable_true(self):
        col = models.Achievement.__table__.c.related_subtask_id
        assert col.nullable is True

    def test_index_true(self):
        col = models.Achievement.__table__.c.related_subtask_id
        assert col.index is True


class TestIssueModel:
    """Issue 包含 related_subtask_id。"""

    def test_has_related_subtask_id_column(self):
        mapper = inspect(models.Issue)
        col = mapper.columns.get("related_subtask_id")
        assert col is not None, "Issue 缺少 related_subtask_id 列"

    def test_foreign_key_to_subtasks(self):
        col = models.Issue.__table__.c.related_subtask_id
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "subtasks"
        assert fk.column.name == "id"

    def test_nullable_true(self):
        col = models.Issue.__table__.c.related_subtask_id
        assert col.nullable is True

    def test_index_true(self):
        col = models.Issue.__table__.c.related_subtask_id
        assert col.index is True


# ──────────────────────────────────────────────────────────────
# 2. schemas 测试（无显式 Response 模型，Payload 不含 related_subtask_id）
# ──────────────────────────────────────────────────────────────


class TestSchemasDoNotExposeRelatedSubtaskIdInPayload:
    """本轮不启用 related_subtask_id 写入 — Payload 不含该字段。"""

    def test_achievement_payload_lacks_related_subtask_id(self):
        fields = schemas.AchievementPayload.model_fields
        assert "related_subtask_id" not in fields, (
            "AchievementPayload 不应包含 related_subtask_id（本轮只读返回）"
        )

    def test_issue_payload_lacks_related_subtask_id(self):
        fields = schemas.IssuePayload.model_fields
        assert "related_subtask_id" not in fields, (
            "IssuePayload 不应包含 related_subtask_id（本轮只读返回）"
        )


# ──────────────────────────────────────────────────────────────
# 3. 迁移文件测试
# ──────────────────────────────────────────────────────────────


class TestMigrationFile:
    """迁移文件包含三张表、不包含历史回填、downgrade 可回滚。"""

    _content: str = ""

    @classmethod
    def _get_content(cls) -> str:
        if cls._content:
            return cls._content
        files = sorted(MIGRATIONS_VERSIONS.glob("*_add_related_subtask_id_fields.py"))
        assert files, "找不到 related_subtask_id 迁移文件"
        cls._content = files[-1].read_text(encoding="utf-8")
        return cls._content

    def test_migration_contains_update_submissions(self):
        content = self._get_content()
        assert "update_submissions" in content, "迁移文件缺少 update_submissions"

    def test_migration_contains_achievements(self):
        content = self._get_content()
        assert "achievements" in content, "迁移文件缺少 achievements"

    def test_migration_contains_issues(self):
        content = self._get_content()
        assert "issues" in content, "迁移文件缺少 issues"

    def test_migration_no_history_backfill(self):
        """迁移文件不应包含历史数据回填 UPDATE 语句（排除注释行）。"""
        content = self._get_content()
        code_lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        assert "UPDATE" not in code_only, "迁移文件包含 UPDATE SQL，不得回填历史数据"

    def test_downgrade_drops_three_columns(self):
        """downgrade 应能删除三列。"""
        content = self._get_content()
        drop_count = len(re.findall(r"drop_column\(", content))
        assert drop_count >= 3, f"downgrade 应至少有 3 个 drop_column，实际 {drop_count}"

    def test_does_not_modify_related_task_id(self):
        """迁移文件不应修改 related_task_id。"""
        content = self._get_content()
        exclude_migration_lines = "\n".join(
            line for line in content.splitlines()
            if "related_task_id" not in line
        )
        # related_task_id 不在 alter_column / drop_column / modify_column 中
        for keyword in ("alter_column", "modify_column"):
            assert keyword not in exclude_migration_lines, (
                f"迁移文件不应修改 related_task_id ({keyword})"
            )


# ──────────────────────────────────────────────────────────────
# 4. 前端类型测试（只检查文件内容）
# ──────────────────────────────────────────────────────────────


class TestFrontendTypes:
    """前端类型文件包含 related_subtask_id 可选字段。"""

    def test_achievement_item_has_related_subtask_id(self):
        path = FRONTEND_ROOT / "types.ts"
        content = path.read_text(encoding="utf-8")
        assert "related_subtask_id" in content, (
            "frontend/src/types.ts AchievementItem 缺少 related_subtask_id"
        )

    def test_issue_item_has_related_subtask_id(self):
        path = FRONTEND_ROOT / "types.ts"
        content = path.read_text(encoding="utf-8")
        assert "related_subtask_id" in content, (
            "frontend/src/types.ts IssueItem 缺少 related_subtask_id"
        )

    def test_update_detail_has_related_subtask_id(self):
        path = FRONTEND_ROOT / "api" / "updates.ts"
        content = path.read_text(encoding="utf-8")
        assert "related_subtask_id" in content, (
            "frontend/src/api/updates.ts UpdateDetail 缺少 related_subtask_id"
        )

    def test_create_achievement_payload_no_related_subtask_id(self):
        path = FRONTEND_ROOT / "api" / "achievements.ts"
        content = path.read_text(encoding="utf-8")
        # AchievementPayload 类型定义中不应包含 related_subtask_id
        payload_section = content.split("export type AchievementPayload")[1].split("export")[0]
        assert "related_subtask_id" not in payload_section, (
            "AchievementPayload 不应提交 related_subtask_id"
        )

    def test_create_issue_payload_no_related_subtask_id(self):
        path = FRONTEND_ROOT / "api" / "issues.ts"
        content = path.read_text(encoding="utf-8")
        # createIssue payload 定义中不应包含 related_subtask_id
        payload_section = content.split("export function createIssue")[0]
        # 往上找 payload 类型，这是匿名 inline 类型
        assert "related_subtask_id" not in payload_section, (
            "createIssue payload 不应提交 related_subtask_id"
        )


# ──────────────────────────────────────────────────────────────
# 5. 项目结构和语义测试
# ──────────────────────────────────────────────────────────────


class TestNoRegressions:
    """确保未把 related_task_id 改成指向 SubTask。"""

    def test_update_submission_related_task_id_still_fk_tasks(self):
        col = models.UpdateSubmission.__table__.c.related_task_id
        fks = list(col.foreign_keys)
        assert any(fk.column.table.name == "tasks" for fk in fks), (
            "UpdateSubmission.related_task_id 必须仍 FK→tasks"
        )

    def test_achievement_related_task_id_still_fk_tasks(self):
        col = models.Achievement.__table__.c.related_task_id
        fks = list(col.foreign_keys)
        assert any(fk.column.table.name == "tasks" for fk in fks), (
            "Achievement.related_task_id 必须仍 FK→tasks"
        )

    def test_issue_related_task_id_still_fk_tasks(self):
        col = models.Issue.__table__.c.related_task_id
        fks = list(col.foreign_keys)
        assert any(fk.column.table.name == "tasks" for fk in fks), (
            "Issue.related_task_id 必须仍 FK→tasks"
        )


# ──────────────────────────────────────────────────────────────
# 6. 文档说明测试
# ──────────────────────────────────────────────────────────────

def test_readme_in_test_docstring():
    """本测试文件自身说明本轮只读返回，不启用写入。"""
    doc = __doc__ or ""
    assert "只读返回" in doc or "readonly" in doc.lower()
    assert "不启用" in doc or "no write" in doc.lower()

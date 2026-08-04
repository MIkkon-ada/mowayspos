from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_and_issue_views_keep_project_scoped_navigation():
    tasks = _source("pages/TaskManagementPage.tsx")
    issues = _source("pages/IssuesPage.tsx")
    assert "useSearchParams" in tasks and "projectId" in tasks
    assert "useSearchParams" in issues and "projectId" in issues


def test_issue_reporting_preserves_task_and_subtask_bindings():
    issues = _source("pages/IssuesPage.tsx")
    assert "related_task_id" in issues
    assert "related_subtask_id" in issues
    assert "fetchSubtasksByProject" in issues


def test_achievement_library_remains_project_scoped():
    achievements = _source("pages/AchievementsPage.tsx")
    assert "useSearchParams" in achievements
    assert "projectId" in achievements

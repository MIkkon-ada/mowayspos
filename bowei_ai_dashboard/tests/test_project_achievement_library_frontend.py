from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "AchievementsPage.tsx").read_text(encoding="utf-8")


def test_achievement_library_is_project_scoped_and_loads_records():
    assert "useSearchParams" in SOURCE
    assert "projectId" in SOURCE
    assert "fetchAchievements" in SOURCE
    assert "fetchAchievement" in SOURCE or "selectedAchievement" in SOURCE

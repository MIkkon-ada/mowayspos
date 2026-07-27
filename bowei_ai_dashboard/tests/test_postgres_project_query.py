from pathlib import Path


def test_project_query_uses_portable_boolean_checks_and_recovers_transactions():
    source = (
        Path(__file__).resolve().parents[1] / "app" / "routers" / "projects.py"
    ).read_text(encoding="utf-8")

    assert "is_active = 1" not in source
    assert "CASE WHEN is_active IS TRUE" in source
    assert "except Exception:\n        db.rollback()\n        return None" in source
